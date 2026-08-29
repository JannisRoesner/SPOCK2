"""Background PICARD note poll worker (Qt)."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from spock2.api.backoff import ExponentialBackoff
from spock2.api.errors import SpockError
from spock2.api.picard import PicardClient
from spock2.domain.status import ApiStatus, ConnectionState

logger = logging.getLogger(__name__)


class NotePollWorker(QObject):
    """
    Single-flight PICARD note poller (when PICARD is enabled).

    Emits:
      - notes_fetched(list[Note])
      - poll_error(SpockError | Exception)
      - status_changed(ApiStatus)
    """

    notes_fetched = Signal(object)
    poll_error = Signal(object)
    status_changed = Signal(object)

    def __init__(
        self,
        client: PicardClient,
        *,
        interval_s: float = 3.0,
        backoff: ExponentialBackoff | None = None,
        include_closed: bool = False,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._interval_s = float(interval_s)
        self._include_closed = include_closed
        self._backoff = backoff or ExponentialBackoff(
            initial=interval_s,
            factor=2.0,
            max=30.0,
            reset_on_success=True,
        )
        self._in_flight = False
        self._running = False
        self._status = ApiStatus()
        self._timer = QTimer(self)
        self._timer.setSingleShot(False)
        self._timer.timeout.connect(self.poll_once)

    @property
    def in_flight(self) -> bool:
        return self._in_flight

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def status(self) -> ApiStatus:
        return self._status

    @Slot()
    def start_polling(self) -> None:
        if not self._client.enabled:
            logger.info("NotePollWorker: PICARD disabled — not starting")
            return
        self._running = True
        interval_ms = max(1, int(self._interval_s * 1000))
        self._timer.setInterval(interval_ms)
        if not self._timer.isActive():
            self._timer.start()
        self.poll_once()

    @Slot()
    def stop_polling(self) -> None:
        """Stoppt den Poll-Timer (im Worker-Thread aufrufen)."""
        self._running = False
        self._timer.stop()

    @Slot(float)
    def set_interval(self, interval_s: float) -> None:
        """Aktualisiert das Erfolgs-Intervall (im Worker-Thread aufrufen)."""
        self._interval_s = max(0.1, float(interval_s))
        if self._running and not self._in_flight:
            self._timer.setInterval(max(1, int(self._interval_s * 1000)))

    @Slot(object)
    def set_client(self, client: object) -> None:
        """Tauscht den PICARD-Client zur Laufzeit."""
        if isinstance(client, PicardClient):
            self._client = client

    @Slot()
    def apply_pending_client(self) -> None:
        """Übernimmt ``_pending_client`` (thread-sicher via BlockingQueuedConnection)."""
        client = getattr(self, "_pending_client", None)
        self._pending_client = None
        self.set_client(client)

    @Slot()
    def poll_once(self) -> None:
        if not self._client.enabled:
            return
        if self._in_flight:
            logger.debug("NotePollWorker: skip (in flight)")
            return

        self._in_flight = True
        self._status.mark_connecting()
        self.status_changed.emit(self._status.model_copy(deep=True))

        try:
            notes = self._client.get_notes(include_closed=self._include_closed)
        except SpockError as exc:
            self._handle_error(exc)
        except Exception as exc:  # noqa: BLE001
            logger.exception("NotePollWorker: unexpected error")
            self._handle_error(exc)
        else:
            self._status.mark_success()
            self.status_changed.emit(self._status.model_copy(deep=True))
            self.notes_fetched.emit(notes)
            if self._backoff.reset_on_success:
                self._backoff.reset()
            if self._running:
                self._timer.setInterval(max(1, int(self._interval_s * 1000)))
        finally:
            self._in_flight = False

    def _handle_error(self, exc: BaseException) -> None:
        kind = type(exc).__name__
        message = getattr(exc, "message", None) or str(exc)
        self._status.mark_error(message, kind=kind)
        if self._status.state != ConnectionState.OFFLINE:
            self._status.state = ConnectionState.OFFLINE
        self.status_changed.emit(self._status.model_copy(deep=True))
        self.poll_error.emit(exc)
        delay = self._backoff.next_delay()
        if self._running:
            self._timer.setInterval(max(1, int(delay * 1000)))
        logger.warning("NotePollWorker error (%s), next delay=%.1fs", kind, delay)
