"""Unit-Tests: Admin-Drucker-Dropdown und Collect."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QComboBox

from spock2.config.models import AppConfig, PrinterConfig
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
