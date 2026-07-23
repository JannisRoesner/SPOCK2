"""PICARD-Zettel-Cache, Seen-IDs und Create/Close-Worker."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot

from spock2.domain.notes import Note
from spock2.domain.status import ApiStatus

logger = logging.getLogger(__name__)

NOTE_TARGETS = (
    "anAlle",
    "anModeration",
    "anTechnik",
    "anKulissen",
    "anKueche",
)

NewNotesCallback = Callable[[list[Note]], None]


class NoteActionWorker(QObject):
    """Create/Close von Zetteln im Worker-Thread."""

    create_finished = Signal(bool, object, object)  # ok, note_or_none, error
    close_finished = Signal(str, bool, object)  # note_id, ok, error

    def __init__(self, picard_client: Any, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._picard = picard_client

    @Slot(str, str, object, object)
    def create(
        self,
        text: str,
        target: str,
        priority: object = "normal",
        author: object = "Küche",
    ) -> None:
        try:
            result = self._picard.create_note(
                text,
                target=target,
                priority=priority if priority is not None else "normal",
                author=author if author is not None else "Küche",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("event=note_create_failed err=%s", exc)
            self.create_finished.emit(False, None, exc)
            return

        note: Note | None = None
        if isinstance(result, Note):
            note = result
        elif isinstance(result, dict):
            try:
                note = Note.model_validate(result)
            except Exception:  # noqa: BLE001
                note = None
        self.create_finished.emit(True, note, None)

    @Slot(str)
    def close(self, note_id: str) -> None:
        try:
            self._picard.close_note(note_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("event=note_close_failed note_id=%s err=%s", note_id, exc)
            self.close_finished.emit(note_id, False, exc)
        else:
            logger.info("event=note_close_ok note_id=%s", note_id)
            self.close_finished.emit(note_id, True, None)


class NoteService(QObject):
    """Hält offene PICARD-Zettel, Seen-IDs und steuert Create/Close."""

    notes_changed = Signal(object)  # list[Note]
    connection_changed = Signal(object)  # ApiStatus
    new_notes_detected = Signal(object)  # list[Note]
    create_finished = Signal(bool, object, object)
    close_finished = Signal(str, bool, object)

    _request_create = Signal(str, str, object, object)
    _request_close = Signal(str)

    def __init__(
        self,
        picard_client: Any | None,
        *,
        enabled: bool = True,
        on_new_notes: NewNotesCallback | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._picard = picard_client
        self._enabled = enabled and picard_client is not None
        self._on_new_notes = on_new_notes
        self._notes: list[Note] = []
        self._seen_ids: set[str] = set()
        self._own_ids: set[str] = set()  # selbst geschriebene Zettel → kein Popup
        self._bootstrapped = False
        self._closing_ids: set[str] = set()
        self._cache_updated_at: datetime | None = None
        self._api_status = ApiStatus()
        if not self._enabled:
            self._api_status.mark_error("PICARD deaktiviert", kind="disabled")

        self._thread: QThread | None = None
        self._worker: NoteActionWorker | None = None
        if self._enabled and picard_client is not None:
            self._thread = QThread(self)
            self._worker = NoteActionWorker(picard_client)
            self._worker.moveToThread(self._thread)
            self._request_create.connect(self._worker.create)
            self._request_close.connect(self._worker.close)
            self._worker.create_finished.connect(self._on_create_finished)
            self._worker.close_finished.connect(self._on_close_finished)
            self._thread.start()

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_client(self, picard_client: Any | None, *, enabled: bool | None = None) -> None:
        """Aktualisiert PICARD-Client; Action-Worker nur wenn bereits gestartet."""
        self._picard = picard_client
        if enabled is not None:
            self._enabled = bool(enabled) and picard_client is not None
        elif picard_client is None:
            self._enabled = False
        if self._worker is not None and picard_client is not None:
            self._worker._picard = picard_client
        if not self._enabled:
            self._api_status.mark_error("PICARD deaktiviert", kind="disabled")
            self.connection_changed.emit(self.api_status)

    @property
    def notes(self) -> list[Note]:
        return list(self._notes)

    @property
    def seen_ids(self) -> frozenset[str]:
        return frozenset(self._seen_ids)

    @property
    def api_status(self) -> ApiStatus:
        return self._api_status.model_copy(deep=True)

    @property
    def cache_updated_at(self) -> datetime | None:
        return self._cache_updated_at

    def is_closing(self, note_id: str) -> bool:
        return note_id in self._closing_ids

    def mark_own(self, note_id: str) -> None:
        """Unterdrückt Popup/Auto-Print für selbst erstellte Zettel."""
        self._own_ids.add(str(note_id))

    @Slot(object)
    def apply_poll_result(self, notes: object) -> None:
        if not self._enabled:
            return
        if not isinstance(notes, list):
            self.apply_poll_error(TypeError(f"Erwartete Note-Liste, bekam {type(notes)!r}"))
            return

        parsed: list[Note] = []
        for item in notes:
            if isinstance(item, Note):
                parsed.append(item)
            else:
                try:
                    parsed.append(Note.model_validate(item))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("event=note_parse_skip err=%s", exc)

        open_notes = [n for n in parsed if not n.closed]
        new_ids = {n.id for n in open_notes}
        freshly_seen: list[Note] = []
        if self._bootstrapped:
            for note in open_notes:
                if note.id not in self._seen_ids and note.id not in self._own_ids:
                    freshly_seen.append(note)
        else:
            self._bootstrapped = True
            self._seen_ids = set(new_ids)

        self._notes = open_notes
        self._seen_ids |= new_ids
        self._cache_updated_at = datetime.now(UTC)
        self._api_status.mark_success()
        self.connection_changed.emit(self.api_status)
        self.notes_changed.emit(self.notes)

        if freshly_seen:
            logger.info(
                "event=new_notes count=%s ids=%s",
                len(freshly_seen),
                [n.id for n in freshly_seen],
            )
            self.new_notes_detected.emit(list(freshly_seen))
            if self._on_new_notes is not None:
                try:
                    self._on_new_notes(freshly_seen)
                except Exception:  # noqa: BLE001
                    logger.exception("event=on_new_notes_callback_failed")

    @Slot(object)
    def apply_poll_error(self, err: object) -> None:
        if not self._enabled:
            return
        message = str(err) if err is not None else "Unbekannter Note-Poll-Fehler"
        kind = type(err).__name__ if err is not None else None
        self._api_status.mark_error(message, kind=kind)
        self.connection_changed.emit(self.api_status)
        self.notes_changed.emit(self.notes)
        logger.warning("event=note_poll_error kind=%s msg=%s", kind, message)

    def create_note(
        self,
        text: str,
        *,
        target: str = "anAlle",
        priority: str = "normal",
        author: str = "Küche",
    ) -> bool:
        if not self._enabled or self._worker is None:
            return False
        cleaned = text.strip()
        if not cleaned:
            return False
        if target not in NOTE_TARGETS:
            logger.warning("event=note_create_bad_target target=%s", target)
            return False
        self._request_create.emit(cleaned, target, priority, author)
        return True

    def close_note(self, note_id: str) -> bool:
        if not self._enabled or self._worker is None:
            return False
        nid = str(note_id)
        if nid in self._closing_ids:
            return False
        self._closing_ids.add(nid)
        self.notes_changed.emit(self.notes)
        self._request_close.emit(nid)
        return True

    @Slot(bool, object, object)
    def _on_create_finished(self, ok: bool, note: object, error: object) -> None:
        if ok and isinstance(note, Note):
            self._own_ids.add(note.id)
            self._seen_ids.add(note.id)
        self.create_finished.emit(ok, note, error)

    @Slot(str, bool, object)
    def _on_close_finished(self, note_id: str, ok: bool, error: object) -> None:
        self._closing_ids.discard(note_id)
        if ok:
            self._notes = [n for n in self._notes if n.id != note_id]
            self._cache_updated_at = datetime.now(UTC)
        self.notes_changed.emit(self.notes)
        self.close_finished.emit(note_id, ok, error)

    def shutdown(self) -> None:
        if self._thread is None:
            return
        self._thread.quit()
        if not self._thread.wait(3000):
            logger.warning("event=note_thread_join_timeout")
            self._thread.terminate()
            self._thread.wait(1000)
