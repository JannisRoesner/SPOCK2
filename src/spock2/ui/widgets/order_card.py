"""Touch-freundliche Bestellkarte."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from spock2.domain.orders import Order, OrderItem


def _parse_created(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        # ISO mit Z
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        return None


def format_wait_time(created_at: Any, *, now: datetime | None = None) -> tuple[str, bool]:
    """Gibt (Anzeige, is_hot) zurück. Hot ab 10 Minuten."""
    created = _parse_created(created_at)
    if created is None:
        return ("—", False)
    current = now or datetime.now(UTC)
    seconds = max(0, int((current - created.astimezone(UTC)).total_seconds()))
    minutes = seconds // 60
    hot = minutes >= 10
    if minutes < 1:
        return ("< 1 Min", False)
    if minutes < 60:
        return (f"{minutes} Min", hot)
    hours, rem = divmod(minutes, 60)
    if hours < 24:
        return (f"{hours}:{rem:02d} h", True)
    # Alte Testbestellungen sonst als „893 h 36 Min“ – unlesbar.
    days, rest_hours = divmod(hours, 24)
    return (f"{days} T {rest_hours} h", True)


def _group_items(items: list[OrderItem]) -> list[tuple[str | None, list[OrderItem]]]:
    groups: dict[str | None, list[OrderItem]] = {}
    order_keys: list[str | None] = []
    for item in items:
        key = (item.category or "").strip() or None
        if key not in groups:
            groups[key] = []
            order_keys.append(key)
        groups[key].append(item)
    return [(k, groups[k]) for k in order_keys]


class OrderCard(QFrame):
    """Karte: Tisch groß, Wartezeit, Artikel, Erledigt / Nachdruck."""

    done_clicked = Signal(int)
    reprint_clicked = Signal(int)

    def __init__(
        self,
        order: Order,
        *,
        completing: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("orderCard")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFrameShadow(QFrame.Shadow.Plain)
        self._order_id = order.id
        # Vertikal Minimum: die Karte darf nie unter ihren Inhalt schrumpfen,
        # sonst werden Artikel und Buttons abgeschnitten.
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.setMinimumWidth(280)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 10)
        root.setSpacing(2)

        header = QHBoxLayout()
        header.setSpacing(8)
        table = QLabel(order.display_table())
        table.setObjectName("tableNumber")
        table.setWordWrap(True)
        header.addWidget(table, stretch=1)

        wait_text, hot = format_wait_time(order.created_at)
        wait = QLabel(wait_text)
        wait.setObjectName("waitTimeHot" if hot else "waitTime")
        wait.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(wait)
        root.addLayout(header)

        meta_parts: list[str] = [f"#{order.id}"]
        if order.waiter:
            meta_parts.append(str(order.waiter))
        if order.is_guest:
            meta_parts.append("Gast")
        meta = QLabel(" · ".join(meta_parts))
        meta.setObjectName("orderMeta")
        root.addWidget(meta)

        for category, items in _group_items(order.items):
            if category:
                cat = QLabel(f"[{category}]")
                cat.setObjectName("categoryHeader")
                root.addWidget(cat)
            for item in items:
                line = QLabel(f"{item.qty}×  {item.name}")
                line.setObjectName("itemLine")
                line.setWordWrap(True)
                root.addWidget(line)
                if item.notes:
                    notes = QLabel(f"  → {item.notes}")
                    notes.setObjectName("itemNotes")
                    notes.setWordWrap(True)
                    root.addWidget(notes)

        if not order.items:
            empty = QLabel("(keine Artikel)")
            empty.setObjectName("itemNotes")
            root.addWidget(empty)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.setContentsMargins(0, 6, 0, 0)
        self._done_btn = QPushButton("Erledigt")
        self._done_btn.setObjectName("doneButton")
        self._done_btn.setEnabled(not completing)
        if completing:
            self._done_btn.setText("…")
        self._done_btn.clicked.connect(lambda: self.done_clicked.emit(self._order_id))

        self._reprint_btn = QPushButton("Nachdruck")
        self._reprint_btn.setObjectName("reprintButton")
        self._reprint_btn.clicked.connect(lambda: self.reprint_clicked.emit(self._order_id))

        buttons.addWidget(self._done_btn, stretch=2)
        buttons.addWidget(self._reprint_btn, stretch=1)
        root.addLayout(buttons)

    @property
    def order_id(self) -> int:
        return self._order_id

    def set_completing(self, completing: bool) -> None:
        self._done_btn.setEnabled(not completing)
        self._done_btn.setText("…" if completing else "Erledigt")
