"""Source-Ledger: Dedup / Seen-Tracking über Restarts."""

from __future__ import annotations

import sqlite3

from spock2.api.errors import DbError
from spock2.domain.print_job import SourceType, utc_now_iso


def touch_source(
    conn: sqlite3.Connection,
    source_type: SourceType,
    source_id: str,
    *,
    auto_enqueued: bool | None = None,
) -> None:
    """Legt Ledger-Eintrag an oder aktualisiert ``last_seen_at``."""
    now = utc_now_iso()
    sid = str(source_id)
    st = source_type.value
    try:
        row = conn.execute(
            "SELECT source_type FROM source_ledger WHERE source_type = ? AND source_id = ?",
            (st, sid),
        ).fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO source_ledger (
                  source_type, source_id, first_seen_at, last_seen_at, auto_enqueued
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (st, sid, now, now, 1 if auto_enqueued else 0),
            )
        else:
            if auto_enqueued is None:
                conn.execute(
                    """
                    UPDATE source_ledger SET last_seen_at = ?
                    WHERE source_type = ? AND source_id = ?
                    """,
                    (now, st, sid),
                )
            else:
                conn.execute(
                    """
                    UPDATE source_ledger
                    SET last_seen_at = ?, auto_enqueued = ?
                    WHERE source_type = ? AND source_id = ?
                    """,
                    (now, 1 if auto_enqueued else 0, st, sid),
                )
    except sqlite3.Error as exc:
        raise DbError("source_ledger update fehlgeschlagen", cause=exc) from exc


def was_auto_enqueued(
    conn: sqlite3.Connection,
    source_type: SourceType,
    source_id: str,
) -> bool:
    """True, wenn die Quelle bereits automatisch enqueued wurde."""
    row = conn.execute(
        """
        SELECT auto_enqueued FROM source_ledger
        WHERE source_type = ? AND source_id = ?
        """,
        (source_type.value, str(source_id)),
    ).fetchone()
    if row is None:
        return False
    return bool(row["auto_enqueued"])


def mark_auto_enqueued(
    conn: sqlite3.Connection,
    source_type: SourceType,
    source_id: str,
) -> None:
    """Setzt auto_enqueued=1 (legt Eintrag bei Bedarf an)."""
    touch_source(conn, source_type, source_id, auto_enqueued=True)


def get_entry(
    conn: sqlite3.Connection,
    source_type: SourceType,
    source_id: str,
) -> dict[str, object] | None:
    row = conn.execute(
        """
        SELECT source_type, source_id, first_seen_at, last_seen_at, auto_enqueued
        FROM source_ledger
        WHERE source_type = ? AND source_id = ?
        """,
        (source_type.value, str(source_id)),
    ).fetchone()
    if row is None:
        return None
    return {
        "source_type": row["source_type"],
        "source_id": row["source_id"],
        "first_seen_at": row["first_seen_at"],
        "last_seen_at": row["last_seen_at"],
        "auto_enqueued": bool(row["auto_enqueued"]),
    }


def list_recent(
    conn: sqlite3.Connection,
    *,
    limit: int = 100,
) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT source_type, source_id, first_seen_at, last_seen_at, auto_enqueued
        FROM source_ledger
        ORDER BY last_seen_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [
        {
            "source_type": r["source_type"],
            "source_id": r["source_id"],
            "first_seen_at": r["first_seen_at"],
            "last_seen_at": r["last_seen_at"],
            "auto_enqueued": bool(r["auto_enqueued"]),
        }
        for r in rows
    ]
