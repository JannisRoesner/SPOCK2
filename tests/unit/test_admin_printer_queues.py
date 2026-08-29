"""Unit-Tests: Admin-Drucker-Dropdown und Collect."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QComboBox

from spock2.config.models import AppConfig, PrinterConfig, TlsConfig
from spock2.ui.dialogs.admin_dialog import AdminDialog


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    assert isinstance(app, QApplication)
    return app


def test_admin_collect_queue_from_combo(qapp: QApplication) -> None:
    cfg = AppConfig(
        printers={
            "kitchen": PrinterConfig(
                role="kitchen", queue="spock-kitchen", profile="tsp100"
            ),
            "counter": PrinterConfig(
                role="counter", queue="spock-counter", profile="tsp100"
            ),
            "small": PrinterConfig(
                role="small", queue="spock-small", profile="pos5890k"
            ),
        }
    )

    def fake_list(_mode: str) -> list[str]:
        return ["Star Kitchen", "POS-58", "Theke"]

    dlg = AdminDialog(cfg, list_queues=fake_list)
    kitchen_combo = dlg._printer_widgets["kitchen"]["queue"]
    assert isinstance(kitchen_combo, QComboBox)
    kitchen_combo.setCurrentText("Star Kitchen")

    counter_combo = dlg._printer_widgets["counter"]["queue"]
    assert isinstance(counter_combo, QComboBox)
    counter_combo.setCurrentText("Star Kitchen")

    collected = dlg._collect()
    assert collected is not None
    assert collected.printer_for_role("kitchen") is not None
    assert collected.printer_for_role("kitchen").queue == "Star Kitchen"  # type: ignore[union-attr]
    assert collected.printer_for_role("counter").queue == "Star Kitchen"  # type: ignore[union-attr]
    dlg.close()


def test_admin_shows_and_collects_tls_settings(qapp: QApplication) -> None:
    cfg = AppConfig(tls=TlsConfig(ssl_verify=False, ca_bundle="/etc/ssl/riker-ca.pem"))
    dlg = AdminDialog(cfg, list_queues=lambda _m: [])

    assert dlg._ssl_verify.isChecked() is False
    assert dlg._ca_bundle.text() == "/etc/ssl/riker-ca.pem"

    collected = dlg._collect()
    assert collected is not None
    assert collected.tls.ssl_verify is False
    assert collected.tls.ca_bundle == "/etc/ssl/riker-ca.pem"

    dlg._ssl_verify.setChecked(True)
    dlg._ca_bundle.setText("  /tmp/neu.pem  ")
    changed = dlg._collect()
    assert changed is not None
    assert changed.tls.ssl_verify is True
    assert changed.tls.ca_bundle == "/tmp/neu.pem"
    dlg.close()


def test_admin_collect_keeps_untouched_sections(qapp: QApplication) -> None:
    cfg = AppConfig()
    cfg.routing.station_role = "counter"
    cfg.riker.complete_retries = 7
    cfg.picard.session_id = "42"

    dlg = AdminDialog(cfg, list_queues=lambda _m: [])
    collected = dlg._collect()
    assert collected is not None
    assert collected.routing.station_role == "counter"
    assert collected.riker.complete_retries == 7
    assert collected.picard.session_id == "42"
    dlg.close()


def test_admin_keeps_unknown_queue_in_combo(qapp: QApplication) -> None:
    cfg = AppConfig(
        printers={
            "kitchen": PrinterConfig(
                role="kitchen", queue="legacy-name", profile="tsp100"
            ),
        }
    )
    dlg = AdminDialog(cfg, list_queues=lambda _m: ["A", "B"])
    combo = dlg._printer_widgets["kitchen"]["queue"]
    assert isinstance(combo, QComboBox)
    assert combo.currentText() == "legacy-name"
    items = [combo.itemText(i) for i in range(combo.count())]
    assert "legacy-name" in items
    assert "A" in items
    dlg.close()
