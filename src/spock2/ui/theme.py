"""Appearance: Light/Dark-Chrome, QSS-Laden und UI-Skalierung."""

from __future__ import annotations

import contextlib
import logging
import re
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

from spock2.config.models import UiConfig, UiTheme

logger = logging.getLogger(__name__)

_REF_WIDTH = 1280
_REF_HEIGHT = 800
_SCALE_MIN = 0.75
_SCALE_MAX = 1.75
# Dämpfung der automatischen Skalierung: ein 1920×1280-Tablet ergäbe sonst
# Faktor 1.5 – Karten und Statusleiste passen dann nicht mehr aufs Display.
_AUTO_DAMPING = 0.4
_AUTO_MIN = 0.85
_AUTO_MAX = 1.2

_PT_RE = re.compile(r"(\d+(?:\.\d+)?)pt")
_PX_RE = re.compile(r"(\d+(?:\.\d+)?)px")


def load_stylesheet(theme: UiTheme = "light") -> str:
    name = "styles_dark.qss" if theme == "dark" else "styles.qss"
    path = Path(__file__).resolve().parent / name
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("event=stylesheet_missing theme=%s err=%s", theme, exc)
        if theme != "light":
            return load_stylesheet("light")
        return ""


def scale_stylesheet(qss: str, scale: float) -> str:
    """Skaliert absolute pt/px-Angaben im QSS."""
    if abs(scale - 1.0) < 0.01:
        return qss

    def _pt(match: re.Match[str]) -> str:
        return f"{max(1, round(float(match.group(1)) * scale))}pt"

    def _px(match: re.Match[str]) -> str:
        return f"{max(1, round(float(match.group(1)) * scale))}px"

    return _PX_RE.sub(_px, _PT_RE.sub(_pt, qss))


def effective_ui_scale(ui: UiConfig, window_size: QSize | None = None) -> float:
    """Kombiniert Nutzer-Skalierung mit optionaler Fenster-/Bildschirmgröße."""
    scale = float(ui.ui_scale)
    if ui.scale_with_window:
        w = h = 0
        if window_size is not None and window_size.width() > 0 and window_size.height() > 0:
            w, h = window_size.width(), window_size.height()
        else:
            screen = QGuiApplication.primaryScreen()
            if screen is not None:
                geo = screen.availableGeometry()
                w, h = geo.width(), geo.height()
        if w > 0 and h > 0:
            auto = min(w / _REF_WIDTH, h / _REF_HEIGHT)
            auto = 1.0 + (auto - 1.0) * _AUTO_DAMPING
            scale *= max(_AUTO_MIN, min(_AUTO_MAX, auto))
    return max(_SCALE_MIN, min(_SCALE_MAX, scale))


def apply_chrome(app: QApplication, theme: UiTheme) -> None:
    """Fusion-Palette + ColorScheme, unabhängig vom OS-Dark-Mode."""
    if theme == "dark":
        with contextlib.suppress(Exception):
            app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
        pal = QPalette()
        window = QColor("#1c1c1a")
        base = QColor("#2a2a28")
        text = QColor("#f0f0ec")
        button = QColor("#3a3a36")
        highlight = QColor("#b35c00")
        pal.setColor(QPalette.ColorRole.Window, window)
        pal.setColor(QPalette.ColorRole.WindowText, text)
        pal.setColor(QPalette.ColorRole.Base, base)
        pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#242422"))
        pal.setColor(QPalette.ColorRole.Text, text)
        pal.setColor(QPalette.ColorRole.Button, button)
        pal.setColor(QPalette.ColorRole.ButtonText, text)
        pal.setColor(QPalette.ColorRole.ToolTipBase, base)
        pal.setColor(QPalette.ColorRole.ToolTipText, text)
        pal.setColor(QPalette.ColorRole.PlaceholderText, QColor("#999990"))
        pal.setColor(QPalette.ColorRole.Highlight, highlight)
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        pal.setColor(QPalette.ColorRole.Link, QColor("#7dffa0"))
        app.setPalette(pal)
        return

    with contextlib.suppress(Exception):
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    pal = QPalette()
    window = QColor("#f4f4f0")
    base = QColor("#ffffff")
    text = QColor("#111111")
    button = QColor("#ecece4")
    highlight = QColor("#ffe8b8")
    pal.setColor(QPalette.ColorRole.Window, window)
    pal.setColor(QPalette.ColorRole.WindowText, text)
    pal.setColor(QPalette.ColorRole.Base, base)
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#ecece4"))
    pal.setColor(QPalette.ColorRole.Text, text)
    pal.setColor(QPalette.ColorRole.Button, button)
    pal.setColor(QPalette.ColorRole.ButtonText, text)
    pal.setColor(QPalette.ColorRole.ToolTipBase, base)
    pal.setColor(QPalette.ColorRole.ToolTipText, text)
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor("#666666"))
    pal.setColor(QPalette.ColorRole.Highlight, highlight)
    pal.setColor(QPalette.ColorRole.HighlightedText, text)
    pal.setColor(QPalette.ColorRole.Link, QColor("#0f4d26"))
    app.setPalette(pal)


def apply_appearance(
    app: QApplication,
    ui: UiConfig,
    *,
    window_size: QSize | None = None,
) -> float:
    """Setzt Style, Palette und skaliertes Theme-Stylesheet. Gibt effektive Scale zurück."""
    app.setStyle("Fusion")
    apply_chrome(app, ui.theme)
    scale = effective_ui_scale(ui, window_size)
    # min_touch_target_px skaliert relativ zur QSS-Basis (56px)
    combined = scale * (ui.min_touch_target_px / 56.0)
    combined = max(_SCALE_MIN, min(_SCALE_MAX, combined))
    qss = load_stylesheet(ui.theme)
    app.setStyleSheet(scale_stylesheet(qss, combined) if qss else "")
    return combined
