"""Bestätigung vor „Erledigt“."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from spock2.domain.orders import Order


class CompleteConfirmDialog(QDialog):
    """Touch-große Bestätigung für Markierung als erledigt."""

    def __init__(
        self,
        order: Order,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Bestellung erledigen")
        self.setModal(True)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        title = QLabel("Als erledigt markieren?")
        title.setObjectName("dialogTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        body = QLabel(
            f"Tisch / Gast: <b>{order.display_table()}</b><br/>"
            f"Bestellung #{order.id}"
        )
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setWordWrap(True)
        layout.addWidget(body)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No
        )
        yes = buttons.button(QDialogButtonBox.StandardButton.Yes)
        no = buttons.button(QDialogButtonBox.StandardButton.No)
        if yes is not None:
            yes.setText("Erledigt")
            yes.setObjectName("doneButton")
            yes.setMinimumHeight(56)
        if no is not None:
            no.setText("Abbrechen")
            no.setMinimumHeight(56)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def ask(order: Order, parent: QWidget | None = None) -> bool:
        dlg = CompleteConfirmDialog(order, parent)
        return dlg.exec() == QDialog.DialogCode.Accepted
