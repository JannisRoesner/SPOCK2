"""RIKER HTTP client (orders)."""

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
from spock2.domain.orders import Order

logger = logging.getLogger(__name__)


def _is_tls_related(exc: BaseException) -> bool:
    """Detect TLS/certificate failures wrapped inside httpx errors."""
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
    """Map httpx exceptions to typed SPOCK2 errors."""
    if isinstance(exc, httpx.TimeoutException):
        return TimeoutError(f"RIKER request timed out: {exc}", cause=exc)
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code if exc.response is not None else None
        return HttpStatusError(
            f"RIKER HTTP {status}: {exc}",
            status_code=status,
            cause=exc,
        )
    if _is_tls_related(exc):
        return TlsError(f"RIKER TLS error: {exc}", cause=exc)
    if isinstance(exc, httpx.RequestError):
        return NetworkError(f"RIKER network error: {exc}", cause=exc)
    return NetworkError(f"RIKER request failed: {exc}", cause=exc)


class RikerClient:
    """Synchronous httpx client for the RIKER kitchen API."""

    def __init__(
        self,
        base_url: str,
        *,
        ssl_verify: bool = True,
        connect_timeout: float = 3.0,
        read_timeout: float = 10.0,
        ca_bundle: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        verify: bool | str = ssl_verify
        if ca_bundle:
            verify = ca_bundle
        elif not ssl_verify:
            logger.warning("RIKER SSL verification is DISABLED")

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

    def __enter__(self) -> RikerClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

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

    def get_open_orders(self) -> list[Order]:
        """
        Fetch open orders from ``GET /api/orders?status=open``.

        Raises typed errors on failure — never silently returns ``[]``.
        An empty list is only returned when the API responds with ``[]``.
        """
        response = self._request("GET", "/api/orders", params={"status": "open"})
        try:
            payload = response.json()
        except ValueError as exc:
            raise ValidationError(
                f"RIKER returned non-JSON body: {exc}",
                cause=exc,
            ) from exc

        if not isinstance(payload, list):
            raise ValidationError(
                f"RIKER orders response must be a list, got {type(payload).__name__}"
            )

        try:
            orders = [Order.model_validate(item) for item in payload]
        except PydanticValidationError as exc:
            raise ValidationError(
                f"RIKER order payload failed validation: {exc}",
                cause=exc,
            ) from exc

        logger.info("Retrieved %d open orders from RIKER", len(orders))
        return orders

    def complete_order(self, order_id: int) -> None:
        """Mark an order complete via ``POST /api/orders/:id/complete``."""
        response = self._request("POST", f"/api/orders/{order_id}/complete")
        try:
            payload = response.json()
        except ValueError:
            # Some servers may return empty body; treat 2xx as success.
            logger.info("Marked RIKER order %s complete (empty body)", order_id)
            return

        if isinstance(payload, dict) and payload.get("ok") is False:
            raise HttpStatusError(
                f"RIKER complete rejected for order {order_id}: {payload}",
                status_code=response.status_code,
            )
        logger.info("Marked RIKER order %s complete", order_id)

    def test_connection(self) -> bool:
        """
        Probe RIKER via ``GET /api/menu``.

        Returns ``True`` on success; may raise typed network/HTTP/TLS errors.
        """
        self._request("GET", "/api/menu")
        logger.info("RIKER connection test successful")
        return True
