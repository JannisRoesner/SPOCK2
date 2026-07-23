"""Unit tests for ExponentialBackoff."""

from __future__ import annotations

import pytest

from spock2.api.backoff import ExponentialBackoff


def test_backoff_sequence() -> None:
    backoff = ExponentialBackoff(initial=3.0, factor=2.0, max=30.0)
    assert backoff.current == 3.0
    assert backoff.next_delay() == 3.0
    assert backoff.current == 6.0
    assert backoff.next_delay() == 6.0
    assert backoff.current == 12.0
    assert backoff.next_delay() == 12.0
    assert backoff.current == 24.0
    assert backoff.next_delay() == 24.0
    assert backoff.current == 30.0  # capped
    assert backoff.next_delay() == 30.0
    assert backoff.current == 30.0


def test_backoff_reset() -> None:
    backoff = ExponentialBackoff(initial=3.0, factor=2.0, max=30.0)
    backoff.next_delay()
    backoff.next_delay()
    assert backoff.current == 12.0
    backoff.reset()
    assert backoff.current == 3.0
    assert backoff.next_delay() == 3.0


def test_backoff_reset_on_success_flag() -> None:
    backoff = ExponentialBackoff(
        initial=5.0,
        factor=2.0,
        max=20.0,
        reset_on_success=True,
    )
    assert backoff.reset_on_success is True
    backoff = ExponentialBackoff(
        initial=5.0,
        factor=2.0,
        max=20.0,
        reset_on_success=False,
    )
    assert backoff.reset_on_success is False


def test_backoff_rejects_invalid_params() -> None:
    with pytest.raises(ValueError):
        ExponentialBackoff(initial=0)
    with pytest.raises(ValueError):
        ExponentialBackoff(factor=0.5)
    with pytest.raises(ValueError):
        ExponentialBackoff(max=-1)
