"""Unit-Tests: Config-Pfadauflösung und vollständige Übernahme."""

from __future__ import annotations

from pathlib import Path

import pytest

from spock2.config import loader
from spock2.config.loader import (
    ENV_CONFIG,
    default_writable_config_path,
    load_config_result,
    resolve_config_path,
    user_config_path,
)
from spock2.config.models import AppConfig, PrinterConfig, TlsConfig, apply_config_inplace


def _no_other_configs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Suche auf einen leeren Pfad beschränken (keine echten Benutzerdateien)."""
    monkeypatch.setattr(
        loader, "_default_search_paths", lambda: (tmp_path / "nothing.toml",)
    )
    monkeypatch.delenv(ENV_CONFIG, raising=False)


def test_env_config_pointing_nowhere_does_not_raise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kiosk-Starter setzen SPOCK2_CONFIG pauschal – das darf den Start nicht töten."""
    _no_other_configs(tmp_path, monkeypatch)
    monkeypatch.setenv(ENV_CONFIG, str(tmp_path / "fehlt.toml"))

    assert resolve_config_path() is None
    loaded = load_config_result()
    assert loaded.path is None
    assert isinstance(loaded.config, AppConfig)


def test_env_config_is_used_when_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_other_configs(tmp_path, monkeypatch)
    target = tmp_path / "spock2.toml"
    target.write_text('[riker]\nbase_url = "https://riker.test"\n', encoding="utf-8")
    monkeypatch.setenv(ENV_CONFIG, str(target))

    loaded = load_config_result()
    assert loaded.path == target
    assert loaded.config.riker.base_url == "https://riker.test"


def test_explicit_override_still_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        resolve_config_path(tmp_path / "fehlt.toml")


def test_user_config_wins_over_system() -> None:
    paths = list(loader._default_search_paths())
    user = user_config_path()
    assert user in paths
    system = Path("/etc/spock2/spock2.toml")
    if system in paths:
        assert paths.index(user) < paths.index(system)


def test_writable_path_is_absolute_when_not_in_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Aus dem Startmenü ist das CWD $HOME – dort darf nichts abgelegt werden."""
    monkeypatch.chdir(tmp_path)
    assert default_writable_config_path() == user_config_path()

    (tmp_path / "config").mkdir()
    assert default_writable_config_path() == Path("config/spock2.toml")


def test_apply_config_inplace_keeps_every_section() -> None:
    live = AppConfig(tls=TlsConfig(ssl_verify=False, ca_bundle="/etc/ssl/riker-ca.pem"))
    live.routing.station_role = "counter"

    # So sieht die Rückgabe des Admin-Dialogs aus: tiefe Kopie plus Änderungen.
    edited = live.model_copy(deep=True)
    edited.riker.base_url = "https://riker.test"
    edited.printers = {
        "kitchen": PrinterConfig(role="kitchen", queue="Star_TSP100", profile="tsp100")
    }

    apply_config_inplace(live, edited)

    assert live.riker.base_url == "https://riker.test"
    assert live.printers["kitchen"].queue == "Star_TSP100"
    # Abschnitte ohne UI-Felder dürfen nicht auf Defaults zurückfallen.
    assert live.tls.ssl_verify is False
    assert live.tls.ca_bundle == "/etc/ssl/riker-ca.pem"
    assert live.routing.station_role == "counter"


def test_apply_config_inplace_writes_tls_changes() -> None:
    live = AppConfig()
    edited = live.model_copy(deep=True)
    edited.tls.ssl_verify = False
    edited.tls.ca_bundle = "/tmp/ca.pem"

    apply_config_inplace(live, edited)

    assert live.tls.ssl_verify is False
    assert live.tls.ca_bundle == "/tmp/ca.pem"
