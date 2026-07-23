"""Order-Cache, Poll-Diff und asynchrones Complete."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot

from spock2.domain.orders import Order
from spock2.domain.status import ApiStatus

logger = logging.getLogger(__name__)

NewOrdersCallback = Callable[[list[Order]], None]


class CompleteWorker(QObject):
    """Führt ``RikerClient.complete_order`` im Worker-Thread aus."""

    finished = Signal(int, bool, object)  # order_id, ok, error|None

    def __init__(self, riker_client: Any, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._riker = riker_client

    @Slot(int)
    def complete(self, order_id: int) -> None:
        """Markiert eine Bestellung auf dem Server als erledigt."""
        try:
            self._riker.complete_order(order_id)
        except Exception as exc:  # noqa: BLE001 – an UI weiterreichen
            logger.warning("event=complete_failed order_id=%s err=%s", order_id, exc)
            self.finished.emit(order_id, False, exc)
        else:
            logger.info("event=complete_ok order_id=%s", order_id)
            self.finished.emit(order_id, True, None)


class OrderService(QObject):
    """Hält die letzte gute Bestellliste und steuert Complete/Auto-Print-Diff."""

    orders_changed = Signal(object)  # list[Order]
    connection_changed = Signal(object)  # ApiStatus
    complete_finished = Signal(int, bool, object)  # order_id, ok, error
    new_orders_detected = Signal(object)  # list[Order]
    _request_complete = Signal(int)

    def __init__(
        self,
        riker_client: Any,
        *,
        on_new_orders: NewOrdersCallback | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._riker = riker_client
        self._on_new_orders = on_new_orders
        self._orders: list[Order] = []
        self._known_ids: set[int] = set()
        self._bootstrapped = False
        self._completing_ids: set[int] = set()
        self._cache_updated_at: datetime | None = None
        self._api_status = ApiStatus()

        self._complete_thread = QThread(self)
        self._complete_worker = CompleteWorker(riker_client)
        self._complete_worker.moveToThread(self._complete_thread)
        self._request_complete.connect(self._complete_worker.complete)
        self._complete_worker.finished.connect(self._on_complete_finished)
        self._complete_thread.start()

    @property
    def orders(self) -> list[Order]:
        return list(self._orders)

    @property
    def completing_ids(self) -> frozenset[int]:
        return frozenset(self._completing_ids)

    @property
    def api_status(self) -> ApiStatus:
        return self._api_status.model_copy(deep=True)

    @property
    def cache_updated_at(self) -> datetime | None:
        return self._cache_updated_at

    def is_completing(self, order_id: int) -> bool:
        return order_id in self._completing_ids

    def get_order(self, order_id: int) -> Order | None:
        for order in self._orders:
            if order.id == order_id:
                return order
        return None

    @Slot(object)
    def apply_poll_result(self, orders: object) -> None:
        """Übernimmt erfolgreichen Poll; behält Cache und Diff für Auto-Print."""
        if not isinstance(orders, list):
            self.apply_poll_error(TypeError(f"Erwartete Order-Liste, bekam {type(orders)!r}"))
            return

        parsed: list[Order] = []
        for item in orders:
            if isinstance(item, Order):
                parsed.append(item)
            else:
                try:
                    parsed.append(Order.model_validate(item))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("event=order_parse_skip err=%s", exc)

        new_ids = {o.id for o in parsed}
        freshly_seen: list[Order] = []
        if self._bootstrapped:
            for order in parsed:
                if order.id not in self._known_ids:
                    freshly_seen.append(order)
        else:
            # Erster Poll: kein Auto-Print-Sturm für bereits offene Orders
            self._bootstrapped = True

        self._orders = parsed
        self._known_ids = new_ids
        self._cache_updated_at = datetime.now(UTC)
        self._api_status.mark_success()
        self.connection_changed.emit(self.api_status)
        self.orders_changed.emit(self.orders)

        if freshly_seen:
            logger.info(
                "event=new_orders count=%s ids=%s",
                len(freshly_seen),
                [o.id for o in freshly_seen],
            )
            self.new_orders_detected.emit(list(freshly_seen))
            if self._on_new_orders is not None:
                try:
                    self._on_new_orders(freshly_seen)
                except Exception:  # noqa: BLE001
                    logger.exception("event=on_new_orders_callback_failed")

    @Slot(object)
    def apply_poll_error(self, err: object) -> None:
        """Markiert Offline; behält die letzte gute Bestellliste."""
        message = str(err) if err is not None else "Unbekannter Poll-Fehler"
        kind = type(err).__name__ if err is not None else None
        self._api_status.mark_error(message, kind=kind)
        self.connection_changed.emit(self.api_status)
        self.orders_changed.emit(self.orders)
        logger.warning("event=poll_error kind=%s msg=%s", kind, message)

    def complete_order(self, order_id: int) -> bool:
        """Startet asynchrones Complete. False wenn bereits in flight / unbekannt."""
        if order_id in self._completing_ids:
            logger.info("event=complete_skip_inflight order_id=%s", order_id)
            return False
        if not any(o.id == order_id for o in self._orders):
            logger.warning("event=complete_unknown_id order_id=%s", order_id)
            return False

        self._completing_ids.add(order_id)
        self.orders_changed.emit(self.orders)
        self._request_complete.emit(order_id)
        return True

    def mark_connecting(self) -> None:
        self._api_status.mark_connecting()
        self.connection_changed.emit(self.api_status)

    @Slot(int, bool, object)
    def _on_complete_finished(self, order_id: int, ok: bool, error: object) -> None:
        self._completing_ids.discard(order_id)
        if ok:
            self._orders = [o for o in self._orders if o.id != order_id]
            self._known_ids.discard(order_id)
            self._cache_updated_at = datetime.now(UTC)
        self.orders_changed.emit(self.orders)
        self.complete_finished.emit(order_id, ok, error)

    def shutdown(self) -> None:
        """Stoppt den Complete-Worker-Thread."""
        self._complete_thread.quit()
        if not self._complete_thread.wait(3000):
            logger.warning("event=complete_thread_join_timeout")
            self._complete_thread.terminate()
            self._complete_thread.wait(1000)
