"""Unit tests for RikerClient (pytest-httpx)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from pytest_httpx import HTTPXMock

from spock2.api.errors import HttpStatusError, TimeoutError, ValidationError
from spock2.api.riker import RikerClient
from spock2.domain.orders import Order

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
ORDERS_JSON = FIXTURES / "orders.json"
BASE_URL = "http://riker.test"


@pytest.fixture
def sample_orders() -> list[dict]:
    return json.loads(ORDERS_JSON.read_text(encoding="utf-8"))


def test_get_open_orders_success(httpx_mock: HTTPXMock, sample_orders: list[dict]) -> None:
    httpx_mock.add_response(
        url=f"{BASE_URL}/api/orders?status=open",
        method="GET",
        json=sample_orders,
    )

    with RikerClient(BASE_URL) as client:
        orders = client.get_open_orders()

    assert len(orders) == 2
    assert all(isinstance(o, Order) for o in orders)
    assert orders[0].id == 42
    assert orders[0].display_table() == "7"
    assert len(orders[0].items) == 2
    assert orders[0].items[0].name == "Schnitzel"
    assert orders[0].items[0].category == "Speisen"
    assert orders[0].is_guest is False
    assert orders[1].is_guest is True
    assert orders[1].display_table() == "Max Mustermann"


def test_get_open_orders_empty_list(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{BASE_URL}/api/orders?status=open",
        method="GET",
        json=[],
    )
    with RikerClient(BASE_URL) as client:
        assert client.get_open_orders() == []


def test_get_open_orders_timeout(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_exception(
        httpx.ReadTimeout("timed out"),
        url=f"{BASE_URL}/api/orders?status=open",
        method="GET",
    )
    with RikerClient(BASE_URL) as client, pytest.raises(TimeoutError):
        client.get_open_orders()


def test_get_open_orders_bad_json(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{BASE_URL}/api/orders?status=open",
        method="GET",
        content=b"not-json{{",
        headers={"Content-Type": "application/json"},
    )
    with RikerClient(BASE_URL) as client, pytest.raises(ValidationError):
        client.get_open_orders()


def test_get_open_orders_http_500(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{BASE_URL}/api/orders?status=open",
        method="GET",
        status_code=500,
        json={"error": "internal"},
    )
    with RikerClient(BASE_URL) as client, pytest.raises(HttpStatusError) as exc_info:
        client.get_open_orders()
    assert exc_info.value.status_code == 500


def test_get_open_orders_invalid_shape(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{BASE_URL}/api/orders?status=open",
        method="GET",
        json={"orders": []},
    )
    with RikerClient(BASE_URL) as client, pytest.raises(ValidationError):
        client.get_open_orders()


def test_complete_order(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{BASE_URL}/api/orders/42/complete",
        method="POST",
        json={"ok": True},
    )
    with RikerClient(BASE_URL) as client:
        client.complete_order(42)


def test_test_connection(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{BASE_URL}/api/menu",
        method="GET",
        json={"categories": []},
    )
    with RikerClient(BASE_URL) as client:
        assert client.test_connection() is True
