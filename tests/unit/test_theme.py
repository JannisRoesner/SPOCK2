"""Unit-Tests für UI-Theme und Skalierung."""

from __future__ import annotations

from PySide6.QtCore import QSize

from spock2.config.models import AppConfig, UiConfig
from spock2.ui.theme import effective_ui_scale, load_stylesheet, scale_stylesheet


def test_ui_defaults() -> None:
    cfg = AppConfig()
    assert cfg.ui.theme == "light"
    assert cfg.ui.ui_scale == 1.0
    assert cfg.ui.scale_with_window is True


def test_scale_stylesheet_pt_px() -> None:
    qss = "QLabel { font-size: 10pt; min-height: 40px; }"
    out = scale_stylesheet(qss, 1.5)
    assert "15pt" in out
    assert "60px" in out


def test_load_dark_stylesheet() -> None:
    qss = load_stylesheet("dark")
    assert "QMainWindow" in qss
    assert "#1c1c1a" in qss or "background" in qss


def test_effective_scale_clamped() -> None:
    ui = UiConfig(ui_scale=1.75, scale_with_window=True)
    # Very large window → clamped
    scale = effective_ui_scale(ui, QSize(4000, 3000))
    assert scale <= 1.75
    # Tiny window
    ui2 = UiConfig(ui_scale=0.75, scale_with_window=True)
    scale2 = effective_ui_scale(ui2, QSize(640, 400))
    assert scale2 >= 0.75
