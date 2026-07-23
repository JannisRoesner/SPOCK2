#!/usr/bin/env bash
# SPOCK2 Kiosk-Session: Screensaver/DPMS aus, App Vollbild starten.
# Nutzung: Autostart (.desktop), LightDM/GDM session wrapper, oder manuell.
#
# Erwartet: spock2 im PATH (Paket) oder SPOCK2_BIN gesetzt.
# Config: SPOCK2_CONFIG=/etc/spock2/spock2.toml (Default unten).

set -euo pipefail

export SPOCK2_CONFIG="${SPOCK2_CONFIG:-/etc/spock2/spock2.toml}"
SPOCK2_BIN="${SPOCK2_BIN:-/usr/bin/spock2}"

# --- Display Blanking / Screensaver unterdrücken (Event-kritisch) ---
if command -v xset >/dev/null 2>&1; then
  xset s off          2>/dev/null || true
  xset s noblank      2>/dev/null || true
  xset -dpms          2>/dev/null || true
fi

if command -v xdg-screensaver >/dev/null 2>&1; then
  # „reset“ hält manchen Screensaver wach; zusätzlich inhibit falls verfügbar
  xdg-screensaver reset 2>/dev/null || true
fi

# GNOME / Session-Idle (best effort, Fehler ignorieren)
if command -v gsettings >/dev/null 2>&1; then
  gsettings set org.gnome.desktop.session idle-delay 0 2>/dev/null || true
  gsettings set org.gnome.desktop.screensaver lock-enabled false 2>/dev/null || true
  gsettings set org.gnome.desktop.screensaver idle-activation-enabled false 2>/dev/null || true
fi

# --- SPOCK2 starten (Vollbild über TOML [ui] fullscreen = true) ---
if [[ ! -x "$SPOCK2_BIN" ]] && ! command -v spock2 >/dev/null 2>&1; then
  echo "spock2 nicht gefunden (gesucht: $SPOCK2_BIN)" >&2
  exit 127
fi

exec "${SPOCK2_BIN}" "$@"
