"""Admin-Dialog: Config-Übersicht und Testprint-Hooks."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from spock2.config.models import AppConfig

TestPrintCallback = Callable[[str], None]


class AdminDialog(QDialog):
    """Zeigt Config-Zusammenfassung und Testprint-Buttons je Rolle."""

    def __init__(
        self,
        config: AppConfig,
        *,
        on_test_print: TestPrintCallback | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Administration")
        self.setModal(True)
        self.setMinimumSize(640, 520)
        self._on_test_print = on_test_print

        layout = QVBoxLayout(self)
        title = QLabel("SPOCK2 – Administration")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        summary = QTextEdit()
        summary.setReadOnly(True)
        summary.setPlainText(self._build_summary(config))
        layout.addWidget(summary, stretch=1)

        btn_row = QHBoxLayout()
        for role in ("kitchen", "counter", "small"):
            btn = QPushButton(f"Testprint {role}")
            btn.setObjectName("reprintButton")
            btn.clicked.connect(lambda _checked=False, r=role: self._test_print(r))
            btn_row.addWidget(btn)
        layout.addLayout(btn_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close is not None:
            close.setText("Schließen")
            close.setMinimumHeight(56)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _test_print(self, role: str) -> None:
        if self._on_test_print is None:
            QMessageBox.information(
                self,
                "Testprint",
                f"Kein Testprint-Hook verdrahtet (Rolle: {role}).",
            )
            return
        try:
            self._on_test_print(role)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Testprint fehlgeschlagen", str(exc))
            return
        QMessageBox.information(self, "Testprint", f"Testprint für „{role}“ enqueued.")

    @staticmethod
    def _build_summary(config: AppConfig) -> str:
        lines = [
            f"RIKER URL: {config.riker.base_url}",
            f"PICARD: {'an' if config.picard.enabled else 'aus'} ({config.picard.base_url})",
            f"Station: {config.routing.station_role}",
            f"Poll-Intervall: {config.polling.interval_s}s",
            f"Auto-Print Orders: {config.print.auto_print_new_orders}",
            f"Auto-Print Notes: {config.print.auto_print_new_notes}",
            f"Auto-Complete after Print: {config.print.auto_complete_after_print}",
            f"Fullscreen: {config.ui.fullscreen}",
            f"Confirm Complete: {config.ui.confirm_complete}",
            f"SSL verify: {config.tls.ssl_verify}",
            f"DB: {config.db.resolved_path()}",
            "",
            "Drucker:",
        ]
        if not config.printers:
            lines.append("  (keine)")
        for name, printer in config.printers.items():
            flag = "an" if printer.enabled else "aus"
            lines.append(
                f"  [{flag}] {name}: role={printer.role} "
                f"queue={printer.cups_queue} profile={printer.profile}"
            )
        lines.append("")
        lines.append("Kategorie-Routing:")
        if not config.routing.category_routing:
            lines.append("  (keine Regeln)")
        for cat, roles in config.routing.category_routing.items():
            lines.append(f"  {cat} → {', '.join(roles)}")
        return "\n".join(lines)

    @classmethod
    def open_admin(
        cls,
        config: AppConfig,
        *,
        on_test_print: TestPrintCallback | None = None,
        parent: QWidget | None = None,
        admin_pin: str = "",
    ) -> None:
        if admin_pin:
            text, ok = QInputDialog.getText(
                parent,
                "Admin-PIN",
                "PIN eingeben:",
                QLineEdit.EchoMode.Password,
            )
            if not ok:
                return
            if text != admin_pin:
                QMessageBox.warning(parent, "Admin", "Falscher PIN.")
                return
        dlg = cls(config, on_test_print=on_test_print, parent=parent)
        dlg.exec()
