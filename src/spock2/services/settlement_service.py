"""Cache und Complete für RIKER-Abrechnungszettel."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot

from spock2.domain.settlements import SettlementSlip

logger = logging.getLogger(__name__)

NewSettlementsCallback = Callable[[list[SettlementSlip]], None]


class SettlementCompleteWorker(QObject):
    """Führt ``RikerClient.complete_settlement`` im Worker-Thread aus."""

    finished = Signal(int, bool, object)  # slip_id, ok, error|None

    def __init__(self, riker_client: Any, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._riker = riker_client

    @Slot(int)
    def complete(self, slip_id: int) -> None:
        try:
            self._riker.complete_settlement(slip_id)
        except Exception as exc:  # noqa: BLE001 – an Controller weiterreichen
            logger.warning(
                "event=settlement_complete_failed slip_id=%s err=%s", slip_id, exc
            )
            self.finished.emit(slip_id, False, exc)
        else:
            logger.info("event=settlement_complete_ok slip_id=%s", slip_id)
            self.finished.emit(slip_id, True, None)


class SettlementService(QObject):
    """Hält offene Abrechnungszettel und steuert das Ack nach dem Druck."""

    settlements_changed = Signal(object)  # list[SettlementSlip]
    new_settlements_detected = Signal(object)  # list[SettlementSlip]
    complete_finished = Signal(int, bool, object)
    _request_complete = Signal(int)

    def __init__(
        self,
        riker_client: Any,
        *,
        on_new_settlements: NewSettlementsCallback | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._riker = riker_client
        self._on_new_settlements = on_new_settlements
        self._slips: list[SettlementSlip] = []
        self._known_ids: set[int] = set()
        self._bootstrapped = False
        self._completing_ids: set[int] = set()
        self._cache_updated_at: datetime | None = None

        self._complete_thread = QThread(self)
        self._complete_worker = SettlementCompleteWorker(riker_client)
        self._complete_worker.moveToThread(self._complete_thread)
        self._request_complete.connect(self._complete_worker.complete)
        self._complete_worker.finished.connect(self._on_complete_finished)
        self._complete_thread.start()

    @property
    def slips(self) -> list[SettlementSlip]:
        return list(self._slips)

    def is_completing(self, slip_id: int) -> bool:
        return slip_id in self._completing_ids

    def set_client(self, riker_client: Any) -> None:
        self._riker = riker_client
        self._complete_worker._riker = riker_client

    @Slot(object)
    def apply_poll_result(self, slips: object) -> None:
        """Übernimmt offene Zettel; erster Poll druckt bereits wartende mit."""
        if not isinstance(slips, list):
            logger.warning(
                "event=settlement_poll_bad_type type=%s", type(slips).__name__
            )
            return

        parsed: list[SettlementSlip] = []
        for item in slips:
            if isinstance(item, SettlementSlip):
                slip = item
            else:
                try:
                    slip = SettlementSlip.model_validate(item)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("event=settlement_parse_skip err=%s", exc)
                    continue
            if slip.is_open():
                parsed.append(slip)

        new_ids = {s.id for s in parsed}
        freshly_seen: list[SettlementSlip] = []
        if self._bootstrapped:
            for slip in parsed:
                if slip.id not in self._known_ids:
                    freshly_seen.append(slip)
        else:
            # Offene Zettel sollen auch nach einem Neustart noch gedruckt werden
            # (Ledger verhindert Doppeldruck).
            self._bootstrapped = True
            freshly_seen = list(parsed)

        self._slips = parsed
        self._known_ids = new_ids
        self._cache_updated_at = datetime.now(UTC)
        self.settlements_changed.emit(self.slips)

        if freshly_seen:
            logger.info(
                "event=new_settlements count=%s ids=%s",
                len(freshly_seen),
                [s.id for s in freshly_seen],
            )
            self.new_settlements_detected.emit(list(freshly_seen))
            if self._on_new_settlements is not None:
                try:
                    self._on_new_settlements(freshly_seen)
                except Exception:  # noqa: BLE001
                    logger.exception("event=on_new_settlements_callback_failed")

    def complete_slip(self, slip_id: int) -> bool:
        """Startet asynchrones Complete. False wenn bereits in flight."""
        if slip_id in self._completing_ids:
            logger.info("event=settlement_complete_skip_inflight slip_id=%s", slip_id)
            return False
        self._completing_ids.add(slip_id)
        self._request_complete.emit(slip_id)
        return True

    @Slot(int, bool, object)
    def _on_complete_finished(self, slip_id: int, ok: bool, error: object) -> None:
        self._completing_ids.discard(slip_id)
        if ok:
            self._slips = [s for s in self._slips if s.id != slip_id]
            self._known_ids.discard(slip_id)
            self._cache_updated_at = datetime.now(UTC)
            self.settlements_changed.emit(self.slips)
        self.complete_finished.emit(slip_id, ok, error)

    def shutdown(self) -> None:
        self._complete_thread.quit()
        if not self._complete_thread.wait(3000):
            logger.warning("event=settlement_thread_join_timeout")
            self._complete_thread.terminate()
            self._complete_thread.wait(1000)
