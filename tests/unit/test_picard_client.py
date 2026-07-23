"""Unit-Tests für PicardClient."""

from __future__ import annotations

import httpx
import pytest
from pytest_httpx import HTTPXMock

from spock2.api.errors import HttpStatusError, NetworkError
from spock2.api.picard import PicardClient


@pytest.fixture
def client() -> PicardClient:
    return PicardClient(
        "https://picard.test",
        ssl_verify=True,
        connect_timeout=1.0,
        read_timeout=2.0,
        session_id="sess-1",
    )


def test_get_notes_filters_kitchen(httpx_mock: HTTPXMock, client: PicardClient) -> None:
    httpx_mock.add_response(
        url="https://picard.test/api/sitzung/sess-1/zettel",
        json=[
            {
                "id": "n1",
                "text": "Mehr Pommes",
                "type": "anKueche",
                "priority": "wichtig",
                "sender": "Moderation",
                "timestamp": "2026-07-23T12:00:00",
                "geschlossen": 0,
            },
            {
                "id": "n2",
                "text": "Technik bitte",
                "type": "anTechnik",
                "priority": "normal",
                "sender": "Regie",
                "timestamp": "2026-07-23T12:01:00",
                "geschlossen": 0,
            },
        ],
    )
    notes = client.get_notes()
    assert len(notes) == 1
    assert notes[0].id == "n1"
    assert notes[0].text == "Mehr Pommes"


def test_missing_session_and_no_active_returns_empty(httpx_mock: HTTPXMock) -> None:
    c = PicardClient("https://picard.test", session_id=None)
    httpx_mock.add_response(
        url="https://picard.test/api/aktive-sitzung",
        json={"aktiveSitzung": None},
    )
    httpx_mock.add_response(
        url="https://picard.test/api/sitzungen",
        json=[],
    )
    assert c.get_notes() == []


def test_get_active_session_id_discovers(httpx_mock: HTTPXMock) -> None:
    c = PicardClient("https://picard.test", session_id=None)
    httpx_mock.add_response(
        url="https://picard.test/api/aktive-sitzung",
        json={"aktiveSitzung": {"id": "uuid-abc"}},
    )
    assert c.get_active_session_id() == "uuid-abc"


def test_configured_session_id_preferred(client: PicardClient) -> None:
    assert client.get_active_session_id() == "sess-1"


def test_http_error(httpx_mock: HTTPXMock, client: PicardClient) -> None:
    httpx_mock.add_response(
        url="https://picard.test/api/sitzung/sess-1/zettel",
        status_code=500,
    )
    with pytest.raises(HttpStatusError):
        client.get_notes()


def test_network_error(httpx_mock: HTTPXMock, client: PicardClient) -> None:
    httpx_mock.add_exception(
        httpx.ConnectError("refused"),
        url="https://picard.test/api/sitzung/sess-1/zettel",
    )
    with pytest.raises(NetworkError):
        client.get_notes()
