"""Dialog zum Schreiben eines PICARD-Zettels."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from spock2.services.note_service import NOTE_TARGETS

TARGET_LABELS: dict[str, str] = {
    "anAlle": "An alle",
    "anModeration": "An Moderation",
    "anTechnik": "An Technik",
    "anKulissen": "An Kulissen",
    "anKueche": "An Küche",
}

PRIORITY_VALUES = ("normal", "wichtig", "dringend")


class NoteDialog(QDialog):
    """Zettel schreiben mit Zielwahl und Priorität."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Zettel schreiben")
        self.setModal(True)
        self.setMinimumSize(520, 360)

        layout = QVBoxLayout(self)
        title = QLabel("Neuen Zettel senden")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(12)

        self._target = QComboBox()
        for key in NOTE_TARGETS:
            self._target.addItem(TARGET_LABELS.get(key, key), key)
        # Default anAlle
        idx = list(NOTE_TARGETS).index("anAlle")
        self._target.setCurrentIndex(idx)
        form.addRow("Ziel:", self._target)

        self._priority = QComboBox()
        self._priority.addItems(list(PRIORITY_VALUES))
        form.addRow("Priorität:", self._priority)

        self._text = QPlainTextEdit()
        self._text.setPlaceholderText("Nachricht an das Team…")
        self._text.setMinimumHeight(140)
        form.addRow("Text:", self._text)

        layout.addLayout(form)

        self._error = QLabel("")
        self._error.setObjectName("statusErr")
        self._error.setWordWrap(True)
        layout.addWidget(self._error)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok is not None:
            ok.setText("Senden")
            ok.setObjectName("primaryButton")
            ok.setMinimumHeight(56)
        if cancel is not None:
            cancel.setText("Abbrechen")
            cancel.setMinimumHeight(56)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        if not self._text.toPlainText().strip():
            self._error.setText("Bitte einen Text eingeben.")
            return
        self.accept()

    def note_text(self) -> str:
        return self._text.toPlainText().strip()

    def target(self) -> str:
        data = self._target.currentData(Qt.ItemDataRole.UserRole)
        return str(data) if data is not None else "anAlle"

    def priority(self) -> str:
        return self._priority.currentText()

    @classmethod
    def prompt(cls, parent: QWidget | None = None) -> tuple[str, str, str] | None:
        """Gibt (text, target, priority) oder None bei Abbruch."""
        dlg = cls(parent)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return dlg.note_text(), dlg.target(), dlg.priority()
