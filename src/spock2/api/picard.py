"""PICARD HTTP client (Zettel / kitchen notes)."""

from __future__ import annotations

import logging
import ssl
from typing import Any

import httpx
from pydantic import ValidationError as PydanticValidationError

from spock2.api.errors import (
    HttpStatusError,
    NetworkError,
    SpockError,
    TimeoutError,
    TlsError,
    ValidationError,
)
from spock2.domain.notes import Note

logger = logging.getLogger(__name__)

# Normalized printable targets (casefold, spaces/hyphens → underscore stripped form)
KITCHEN_TARGET_VALUES: set[str] = {
    "ankueche",
    "an_kueche",
    "anküche",
    "an_küche",
    "kueche",
    "küche",
    "kitchen",
    # Broadcast targets — kitchen kiosk should print these too
    "analle",
    "an_alle",
    "alle",
    "all",
    "everyone",
}


def _normalize_target(value: object) -> str:
    text = str(value).strip().casefold().replace(" ", "").replace("-", "_")
    return text


def _is_tls_related(exc: BaseException) -> bool:
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, ssl.SSLError):
            return True
        name = type(current).__name__.lower()
        msg = str(current).lower()
        if "ssl" in name or "certificate" in msg or "tls" in msg:
            return True
        current = current.__cause__ or current.__context__
    return False


def _map_httpx_error(exc: Exception) -> SpockError:
    if isinstance(exc, httpx.TimeoutException):
        return TimeoutError(f"PICARD request timed out: {exc}", cause=exc)
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code if exc.response is not None else None
        return HttpStatusError(
            f"PICARD HTTP {status}: {exc}",
            status_code=status,
            cause=exc,
        )
    if _is_tls_related(exc):
        return TlsError(f"PICARD TLS error: {exc}", cause=exc)
    if isinstance(exc, httpx.RequestError):
        return NetworkError(f"PICARD network error: {exc}", cause=exc)
    return NetworkError(f"PICARD request failed: {exc}", cause=exc)


def _extract_session_id(payload: object) -> str | None:
    """Pull a session id from various PICARD response shapes."""
    if payload is None:
        return None
    if isinstance(payload, (str, int)):
        text = str(payload).strip()
        return text or None
    if not isinstance(payload, dict):
        return None

    for key in (
        "aktiveSitzung",
        "aktive_sitzung",
        "id",
        "sitzungId",
        "sessionId",
        "session_id",
    ):
        if key not in payload or payload[key] in (None, ""):
            continue
        value = payload[key]
        if isinstance(value, dict):
            nested = _extract_session_id(value)
            if nested:
                return nested
            continue
        return str(value)
    return None


def _session_id_from_list(sessions: list[Any]) -> str | None:
    for session in sessions:
        if not isinstance(session, dict):
            continue
        is_active = session.get("aktiv") or session.get("active") or session.get("isActive")
        if is_active:
            sid = (
                session.get("id")
                or session.get("sitzungId")
                or session.get("sessionId")
            )
            if sid is not None:
                return str(sid)

    latest: dict[str, Any] | None = None
    latest_ts = ""
    for session in sessions:
        if not isinstance(session, dict):
            continue
        ts = session.get("erstellt") or session.get("createdAt") or session.get("created_at")
        if ts is None:
            continue
        ts_str = str(ts)
        if latest is None or ts_str > latest_ts:
            latest = session
            latest_ts = ts_str
    if latest:
        sid = latest.get("id") or latest.get("sitzungId") or latest.get("sessionId")
        if sid is not None:
            return str(sid)
    return None


def _raw_note_target(raw: dict[str, Any]) -> object | None:
    for key in ("type", "typ", "target", "recipient", "empfaenger", "empfänger"):
        if key in raw and raw[key] is not None:
            return raw[key]
    return None


def _is_note_closed_raw(raw: dict[str, Any]) -> bool:
    """Tolerant closed-flag parsing (old SPOCK parity)."""
    for key in ("closed", "geschlossen", "isClosed", "is_closed", "status"):
        if key not in raw:
            continue
        value = raw.get(key)
        if value is None:
            continue
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            normalized = value.strip().casefold()
            if normalized in {"1", "true", "yes", "ja", "closed", "geschlossen"}:
                return True
            if normalized in {"0", "false", "no", "nein", "open", "offen", ""}:
                return False
    return False


def _is_kitchen_target_raw(raw: dict[str, Any], kitchen_types: list[str] | None = None) -> bool:
    recipient = _raw_note_target(raw)
    if recipient is None:
        return False
    normalized = _normalize_target(recipient)
    if normalized in KITCHEN_TARGET_VALUES:
        return True
    if kitchen_types:
        return any(normalized == _normalize_target(t) for t in kitchen_types)
    return False


class PicardClient:
    """Synchronous httpx client for the PICARD Zettel API."""

    KITCHEN_TARGET_VALUES = KITCHEN_TARGET_VALUES

    def __init__(
        self,
        base_url: str,
        *,
        ssl_verify: bool = True,
        connect_timeout: float = 3.0,
        read_timeout: float = 10.0,
        ca_bundle: str | None = None,
        session_id: str | None = None,
        kitchen_note_types: list[str] | None = None,
        enabled: bool = True,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session_id: str | None = str(session_id) if session_id else None
        self.kitchen_note_types = list(kitchen_note_types or [])
        self.enabled = enabled

        verify: bool | str = ssl_verify
        if ca_bundle:
            verify = ca_bundle
        elif not ssl_verify:
            logger.warning("PICARD SSL verification is DISABLED")

        timeout = httpx.Timeout(
            connect=connect_timeout,
            read=read_timeout,
            write=read_timeout,
            pool=connect_timeout,
        )
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            verify=verify,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> PicardClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def set_session(self, session_id: str | int | None) -> None:
        self.session_id = str(session_id) if session_id is not None else None

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self._client.request(method, path, **kwargs)
            response.raise_for_status()
            return response
        except SpockError:
            raise
        except httpx.HTTPStatusError as exc:
            raise _map_httpx_error(exc) from exc
        except httpx.RequestError as exc:
            raise _map_httpx_error(exc) from exc

    def get_active_session_id(self) -> str | None:
        """
        Resolve the active PICARD session.

        1. Configured ``session_id`` if already set
        2. ``GET /api/aktive-sitzung``
        3. Fallback ``GET /api/sitzungen`` (active flag / latest)
        """
        if self.session_id:
            return self.session_id

        # Primary: dedicated active-session endpoint
        try:
            response = self._request("GET", "/api/aktive-sitzung")
            payload = response.json()
            sid = _extract_session_id(payload)
            if sid:
                self.session_id = sid
                return sid
        except SpockError as exc:
            logger.info("PICARD /api/aktive-sitzung unavailable: %s", exc)

        # Fallback: session list
        try:
            response = self._request("GET", "/api/sitzungen")
            payload = response.json()
            if isinstance(payload, list):
                sid = _session_id_from_list(payload)
                if sid:
                    self.session_id = sid
                    return sid
        except SpockError as exc:
            logger.warning("PICARD session list failed: %s", exc)
            raise

        logger.warning("PICARD: no active session could be determined")
        return None

    def get_notes(self, include_closed: bool = False) -> list[Note]:
        """
        Fetch printable Zettel for the current session (kitchen + broadcast targets).

        Missing session → ``[]`` with a warning (not a raised SpockError).
        HTTP failures raise typed errors.
        """
        if not self.enabled:
            logger.debug("PICARD disabled; skipping note fetch")
            return []

        if not self.session_id:
            resolved = self.get_active_session_id()
            if not resolved:
                logger.warning("PICARD session_id missing; cannot fetch notes")
                return []

        assert self.session_id is not None
        response = self._request("GET", f"/api/sitzung/{self.session_id}/zettel")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ValidationError(
                f"PICARD returned non-JSON body: {exc}",
                cause=exc,
            ) from exc

        if not isinstance(payload, list):
            raise ValidationError(
                f"PICARD notes response must be a list, got {type(payload).__name__}"
            )

        notes: list[Note] = []
        for raw in payload:
            if not isinstance(raw, dict):
                continue
            if not _is_kitchen_target_raw(raw, self.kitchen_note_types):
                continue
            if not include_closed and _is_note_closed_raw(raw):
                continue
            try:
                notes.append(Note.model_validate(raw))
            except PydanticValidationError as exc:
                raise ValidationError(
                    f"PICARD note payload failed validation: {exc}",
                    cause=exc,
                ) from exc

        logger.info("Retrieved %d PICARD kitchen notes", len(notes))
        return notes

    def create_note(
        self,
        text: str,
        target: str = "anKueche",
        priority: str | int = "normal",
        author: str | None = None,
    ) -> Note:
        """Create a Zettel via ``POST /api/sitzung/:id/zettel``."""
        if not self.enabled:
            raise SpockError("PICARD is disabled")
        if not self.session_id:
            resolved = self.get_active_session_id()
            if not resolved:
                raise SpockError("PICARD session_id missing; cannot create note")

        payload = {
            "text": text,
            "type": target,
            "priority": priority,
            "sender": author if author is not None else "Küche",
        }
        response = self._request(
            "POST",
            f"/api/sitzung/{self.session_id}/zettel",
            json=payload,
        )
        try:
            body = response.json()
        except ValueError as exc:
            raise ValidationError(
                f"PICARD create-note returned non-JSON: {exc}",
                cause=exc,
            ) from exc

        try:
            note = Note.model_validate(body if isinstance(body, dict) else payload)
        except PydanticValidationError as exc:
            raise ValidationError(
                f"PICARD create-note response invalid: {exc}",
                cause=exc,
            ) from exc

        logger.info("Created PICARD note %s", note.id)
        return note

    def close_note(self, note_id: str) -> None:
        """Close a Zettel via ``DELETE /api/sitzung/:id/zettel/:note_id``."""
        if not self.enabled:
            raise SpockError("PICARD is disabled")
        if not self.session_id:
            resolved = self.get_active_session_id()
            if not resolved:
                raise SpockError("PICARD session_id missing; cannot close note")

        self._request(
            "DELETE",
            f"/api/sitzung/{self.session_id}/zettel/{note_id}",
        )
        logger.info("Closed PICARD note %s", note_id)

    def test_connection(self) -> bool:
        """
        Probe PICARD via ``GET /api/sitzungen``.

        Returns ``True`` on success; may raise typed errors.
        """
        self._request("GET", "/api/sitzungen")
        logger.info("PICARD connection test successful")
        return True

    def is_kitchen_target(self, note: Note | dict[str, Any]) -> bool:
        """Public helper: kitchen-target check with tolerant field parsing."""
        raw = note.model_dump() if isinstance(note, Note) else note
        return _is_kitchen_target_raw(raw, self.kitchen_note_types)

    def is_note_closed(self, note: Note | dict[str, Any]) -> bool:
        if isinstance(note, Note):
            return note.closed
        return _is_note_closed_raw(note)
