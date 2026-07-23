"""Exponential backoff for polling retries."""

from __future__ import annotations


class ExponentialBackoff:
    """Stateful delay calculator: initial → *factor → capped at max."""

    def __init__(
        self,
        initial: float = 3.0,
        factor: float = 2.0,
        max: float = 30.0,  # noqa: A002 – matches config key vocabulary
        *,
        reset_on_success: bool = True,
    ) -> None:
        if initial <= 0:
            raise ValueError("initial must be > 0")
        if factor < 1.0:
            raise ValueError("factor must be >= 1.0")
        if max <= 0:
            raise ValueError("max must be > 0")
        self._initial = float(initial)
        self._factor = float(factor)
        self._max = float(max)
        self.reset_on_success = reset_on_success
        self._current = self._initial

    @property
    def current(self) -> float:
        """Delay that will be returned by the next :meth:`next_delay` call."""
        return self._current

    @property
    def initial(self) -> float:
        return self._initial

    @property
    def factor(self) -> float:
        return self._factor

    @property
    def max(self) -> float:
        return self._max

    def next_delay(self) -> float:
        """Return the current delay, then advance (multiplied, capped)."""
        delay = self._current
        self._current = min(self._current * self._factor, self._max)
        return delay

    def reset(self) -> None:
        """Reset delay to the initial value."""
        self._current = self._initial

    def __repr__(self) -> str:
        return (
            f"ExponentialBackoff(initial={self._initial}, factor={self._factor}, "
            f"max={self._max}, current={self._current}, "
            f"reset_on_success={self.reset_on_success})"
        )
