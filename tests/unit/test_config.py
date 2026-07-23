"""Unit-Tests für TOML-Konfiguration."""

from __future__ import annotations

from pathlib import Path

from spock2.config.loader import load_config
from spock2.config.models import AppConfig


def test_example_toml_loads() -> None:
    example = Path(__file__).resolve().parents[2] / "config" / "spock2.example.toml"
    cfg = load_config(example)
    assert isinstance(cfg, AppConfig)
    assert cfg.polling.interval_s > 0
    assert cfg.routing.station_role in {"kitchen", "counter"}
    assert "kitchen" in {p.role for p in cfg.printers.values()} or cfg.printers == {}


def test_defaults() -> None:
    cfg = AppConfig()
    assert cfg.print.auto_complete_after_print is False
    assert cfg.tls.ssl_verify is True
