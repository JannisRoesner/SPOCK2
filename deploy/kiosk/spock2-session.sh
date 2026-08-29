#!/usr/bin/env bash
# SPOCK2 Kiosk-Session: Screensaver/DPMS aus, App Vollbild starten.
# Nutzung: Startmenü/Desktop-Icon (.desktop), Autostart, LightDM/GDM
# session wrapper, oder manuell.
#
# Erwartet: spock2 im PATH (Paket) oder SPOCK2_BIN gesetzt.
# Config: erste existierende Datei aus
#   $SPOCK2_CONFIG, ~/.config/spock2/spock2.toml, /etc/spock2/spock2.toml
# Fehlt alles, wird die Benutzer-Config aus der Beispieldatei angelegt.

set -uo pipefail

SPOCK2_BIN="${SPOCK2_BIN:-/usr/bin/spock2}"
USER_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/spock2/spock2.toml"
SYSTEM_CONFIG="/etc/spock2/spock2.toml"
EXAMPLE_CONFIG="/etc/spock2/spock2.toml.example"
LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/spock2"

# --- Config bestimmen (kein Abbruch bei fehlender Datei) ---
# Ein pauschal gesetztes SPOCK2_CONFIG auf eine nicht existierende Datei war
# der Grund, warum der Start aus dem Startmenü ohne Fenster endete.
if [[ -n "${SPOCK2_CONFIG:-}" && ! -f "${SPOCK2_CONFIG}" ]]; then
  echo "SPOCK2_CONFIG zeigt auf fehlende Datei: ${SPOCK2_CONFIG} – ignoriert" >&2
  unset SPOCK2_CONFIG
fi

if [[ -z "${SPOCK2_CONFIG:-}" ]]; then
  if [[ -f "${USER_CONFIG}" ]]; then
    export SPOCK2_CONFIG="${USER_CONFIG}"
  elif [[ -f "${SYSTEM_CONFIG}" ]]; then
    export SPOCK2_CONFIG="${SYSTEM_CONFIG}"
  elif [[ -f "${EXAMPLE_CONFIG}" ]]; then
    mkdir -p "$(dirname "${USER_CONFIG}")"
    cp "${EXAMPLE_CONFIG}" "${USER_CONFIG}"
    echo "Benutzer-Config aus Beispiel angelegt: ${USER_CONFIG}" >&2
    export SPOCK2_CONFIG="${USER_CONFIG}"
  fi
fi

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
if [[ ! -x "${SPOCK2_BIN}" ]]; then
  if command -v spock2 >/dev/null 2>&1; then
    SPOCK2_BIN="$(command -v spock2)"
  else
    echo "spock2 nicht gefunden (gesucht: ${SPOCK2_BIN})" >&2
    exit 127
  fi
fi

# Start ohne Terminal: stderr zusätzlich mitschreiben, damit Fehlstarts
# nachvollziehbar bleiben.
mkdir -p "${LOG_DIR}" 2>/dev/null || true
if [[ -w "${LOG_DIR}" ]]; then
  exec "${SPOCK2_BIN}" "$@" 2> >(tee -a "${LOG_DIR}/session.log" >&2)
fi

exec "${SPOCK2_BIN}" "$@"
