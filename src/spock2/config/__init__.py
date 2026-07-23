"""Config-Paket."""

from spock2.config.loader import load_config, resolve_config_path
from spock2.config.models import AppConfig

__all__ = ["AppConfig", "load_config", "resolve_config_path"]
