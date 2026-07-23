"""Popup für eingehende PICARD-Zettel."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from spock2.domain.notes import Note


class NotePopup(QDialog):
    """Modaler Hinweis bei neuem Zettel."""

    close_requested = Signal(str)
    print_requested = Signal(str)
    dismissed = Signal(str)

    def __init__(self, note: Note, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Neuer Zettel")
        self.setModal(True)
        self.setMinimumSize(480, 320)
        self._note_id = note.id

        root = QVBoxLayout(self)
        frame = QFrame()
        frame.setObjectName("notePopupFrame")
        frame.setFrameShape(QFrame.Shape.NoFrame)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(20, 16, 20, 16)
        frame_layout.setSpacing(12)

        banner = QLabel("Neuer Zettel")
        banner.setObjectName("notePopupTitle")
        banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(banner)

        meta_parts: list[str] = []
        if note.sender:
            meta_parts.append(f"Von: {note.sender}")
        if note.type:
            meta_parts.append(f"Typ: {note.type}")
        if note.priority is not None:
            meta_parts.append(f"Prio: {note.priority}")
        if note.timestamp is not None:
            meta_parts.append(str(note.timestamp))
        meta = QLabel(" · ".join(meta_parts) if meta_parts else f"ID {note.id}")
        meta.setObjectName("orderMeta")
        meta.setWordWrap(True)
        meta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(meta)

        body = QLabel(note.text or "(kein Text)")
        body.setObjectName("notePopupBody")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(body, stretch=1)

        root.addWidget(frame, stretch=1)

        buttons = QHBoxLayout()
        close_btn = QPushButton("Schließen (erledigt)")
        close_btn.setObjectName("doneButton")
        close_btn.clicked.connect(self._on_close)

        print_btn = QPushButton("Drucken")
        print_btn.setObjectName("reprintButton")
        print_btn.clicked.connect(self._on_print)

        ok_btn = QPushButton("OK")
        ok_btn.setObjectName("primaryButton")
        ok_btn.clicked.connect(self._on_dismiss)

        buttons.addWidget(close_btn)
        buttons.addWidget(print_btn)
        buttons.addWidget(ok_btn)
        root.addLayout(buttons)

    def _on_close(self) -> None:
        self.close_requested.emit(self._note_id)
        self.accept()

    def _on_print(self) -> None:
        self.print_requested.emit(self._note_id)
        # Popup bleibt offen, bis OK/Schließen

    def _on_dismiss(self) -> None:
        self.dismissed.emit(self._note_id)
        self.accept()

    @property
    def note_id(self) -> str:
        return self._note_id
