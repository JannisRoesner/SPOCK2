"""App-Logo und Fenster-Icon (GCC-Bildmarke aus dem klassischen SPOCK)."""

from __future__ import annotations

import logging
from functools import lru_cache
from importlib import resources

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap

logger = logging.getLogger(__name__)

_RESOURCE_PACKAGE = "spock2.ui.resources"
_LOGO_LARGE = "bildmarke.png"
_LOGO_SMALL = "bildmarke_small.png"
_ICON_ICO = "bildmarke.ico"

__all__ = [
    "app_icon",
    "logo_pixmap",
]


def _read_bytes(name: str) -> bytes | None:
    try:
        data = resources.files(_RESOURCE_PACKAGE).joinpath(name).read_bytes()
    except (FileNotFoundError, ModuleNotFoundError, TypeError, OSError) as exc:
        logger.debug("event=asset_missing name=%s error=%s", name, exc)
        return None
    return data or None


def _pixmap_from_resource(name: str) -> QPixmap:
    data = _read_bytes(name)
    if data is None:
        return QPixmap()
    pixmap = QPixmap()
    if not pixmap.loadFromData(data):
        logger.warning("event=asset_load_failed name=%s", name)
        return QPixmap()
    return pixmap


@lru_cache(maxsize=1)
def app_icon() -> QIcon:
    """Fenster-/Taskleisten-Icon; bevorzugt ``.ico``, sonst PNG."""
    icon = QIcon()
    for name in (_ICON_ICO, _LOGO_SMALL, _LOGO_LARGE):
        pixmap = _pixmap_from_resource(name)
        if not pixmap.isNull():
            icon.addPixmap(pixmap)
    if icon.isNull():
        logger.warning("event=app_icon_missing")
    return icon


def logo_pixmap(*, small: bool = True, height: int | None = None) -> QPixmap:
    """Bildmarke als Pixmap; optional auf ``height`` skaliert."""
    name = _LOGO_SMALL if small else _LOGO_LARGE
    pixmap = _pixmap_from_resource(name)
    if pixmap.isNull() and small:
        pixmap = _pixmap_from_resource(_LOGO_LARGE)
    if pixmap.isNull():
        logger.warning("event=logo_missing small=%s", small)
        return pixmap
    if height is not None and height > 0 and pixmap.height() != height:
        return pixmap.scaledToHeight(
            height,
            Qt.TransformationMode.SmoothTransformation,
        )
    return pixmap
