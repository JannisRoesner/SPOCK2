"""Test-Setup: Qt läuft in den Tests immer headless."""

from __future__ import annotations

import os

# Muss vor dem ersten QApplication passieren, sonst öffnen UI-Tests echte Fenster.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
