"""Typisierte API-/Infrastruktur-Fehler."""

from __future__ import annotations


class SpockError(Exception):
    """Basisfehler für SPOCK2."""

    def __init__(self, message: str = "", *, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.__cause__ = cause


class NetworkError(SpockError):
    """Netzwerk nicht erreichbar / DNS / Connection refused."""


class TimeoutError(SpockError):  # noqa: A001 – bewusster Domain-Name
    """Request-Timeout."""


class HttpStatusError(SpockError):
    """Unerwarteter HTTP-Status."""

    def __init__(
        self,
        message: str = "",
        *,
        status_code: int | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.status_code = status_code


class ValidationError(SpockError):
    """Antwort ließ sich nicht in Domain-Modelle parsen."""


class TlsError(SpockError):
    """TLS/Zertifikatsfehler."""


class AuthError(SpockError):
    """Authentifizierung fehlgeschlagen (für spätere API-Auth)."""


class DbError(SpockError):
    """SQLite-/Persistenzfehler."""


class CupsUnavailable(SpockError):
    """CUPS-Dienst oder Queue nicht verfügbar."""


class QueueStopped(SpockError):
    """Druckqueue nimmt keine Jobs an."""


class PrintFailed(SpockError):
    """Druckauftrag fehlgeschlagen."""


class ConfigError(SpockError):
    """Konfigurationsfehler."""


class InvalidTransitionError(SpockError):
    """Ungültiger PrintJob-Statusübergang."""
