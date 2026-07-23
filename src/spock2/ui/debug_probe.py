"""Temporäre Debug-Instrumentierung (Session 269bca)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

_SESSION = "269bca"
_LOG = Path(__file__).resolve().parents[2] / "debug-269bca.log"


def agent_log(
    location: str,
    message: str,
    data: dict[str, Any],
    *,
    hypothesis_id: str,
    run_id: str = "pre-fix",
) -> None:
    # region agent log
    try:
        payload = {
            "sessionId": _SESSION,
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with _LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        pass
    # endregion


def _color_hex(color: Any) -> str:
    if color is None:
        return "none"
    try:
        return f"#{color.red():02x}{color.green():02x}{color.blue():02x}"
    except Exception:  # noqa: BLE001
        return str(color)


def probe_buttons(root: Any, *, location: str) -> None:
    """Loggt Style und Farben aller QPushButton unter root."""
    from PySide6.QtWidgets import QPushButton

    style_name = root.style().objectName() if hasattr(root, "style") else "?"
    app_style = ""
    app = root.window().windowHandle().screen().virtualSiblings() if False else None  # noqa: F841
    from PySide6.QtWidgets import QApplication

    qapp = QApplication.instance()
    if qapp is not None:
        app_style = qapp.style().objectName()

    buttons: list[QPushButton] = root.findChildren(QPushButton)
    samples: list[dict[str, Any]] = []
    for btn in buttons[:12]:
        pal = btn.palette()
        samples.append(
            {
                "text": btn.text(),
                "objectName": btn.objectName(),
                "enabled": btn.isEnabled(),
                "btnColor": _color_hex(pal.button().color()),
                "btnTextColor": _color_hex(pal.buttonText().color()),
                "windowText": _color_hex(pal.windowText().color()),
                "widgetStyleSheetLen": len(btn.styleSheet() or ""),
            }
        )

    agent_log(
        location,
        "button_probe",
        {
            "widgetStyle": app_style,
            "buttonCount": len(buttons),
            "buttons": samples,
        },
        hypothesis_id="B,C,E",
    )
