"""Druckerprofil-Factory."""

from __future__ import annotations

from spock2.printing.profiles.base import PrinterProfile
from spock2.printing.profiles.pos5890k import POS5890K
from spock2.printing.profiles.tsp100 import TSP100

_PROFILES: dict[str, PrinterProfile] = {
    TSP100.name: TSP100,
    POS5890K.name: POS5890K,
}


def get_profile(name: str) -> PrinterProfile:
    """Liefert ein bekanntes Profil; unbekannt → tsp100-Default."""
    key = (name or "").strip().casefold()
    if key in _PROFILES:
        return _PROFILES[key]
    # Alias-Toleranz
    aliases = {
        "tsp-100": "tsp100",
        "star": "tsp100",
        "pos58": "pos5890k",
        "5890k": "pos5890k",
        "5890": "pos5890k",
    }
    mapped = aliases.get(key)
    if mapped and mapped in _PROFILES:
        return _PROFILES[mapped]
    return TSP100


def list_profiles() -> list[str]:
    return sorted(_PROFILES)
