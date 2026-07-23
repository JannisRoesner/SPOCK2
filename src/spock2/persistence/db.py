"""SQLite-Schema, Migrationen und Verbindungshelfer."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from spock2.api.errors import DbError
from spock2.domain.print_job import utc_now_iso

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS print_jobs (
  id            INTEGER PRIMARY KEY,
  source_type   TEXT NOT NULL CHECK(source_type IN ('riker_order','picard_note','manual_test')),
  source_id     TEXT NOT NULL,
  target_role   TEXT NOT NULL CHECK(target_role IN ('kitchen','counter','small')),
  profile_name  TEXT NOT NULL,
  payload_json  TEXT NOT NULL,
  payload_hash  TEXT NOT NULL,
  status        TEXT NOT NULL,
  attempts      INTEGER NOT NULL DEFAULT 0,
  cups_job_id   INTEGER,
  last_error    TEXT,
  is_reprint    INTEGER NOT NULL DEFAULT 0,
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL,
  completed_at  TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_dedupe_auto
  ON print_jobs(source_type, source_id, target_role, payload_hash)
  WHERE is_reprint = 0 AND status NOT IN ('cancelled','failed');

CREATE TABLE IF NOT EXISTS source_ledger (
  source_type TEXT NOT NULL,
  source_id   TEXT NOT NULL,
  first_seen_at TEXT NOT NULL,
  last_seen_at  TEXT NOT NULL,
  auto_enqueued INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (source_type, source_id)
);

CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);
"""


def connect(db_path: str | Path, *, row_factory: bool = True) -> sqlite3.Connection:
    """Öffnet eine SQLite-Verbindung mit sinnvollen Defaults."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = sqlite3.connect(str(path), timeout=30.0)
    except sqlite3.Error as exc:
        raise DbError(f"Verbindung fehlgeschlagen: {path}", cause=exc) from exc
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    if row_factory:
        conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def connection(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    """Context-Manager um eine DB-Verbindung."""
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def current_version(conn: sqlite3.Connection) -> int:
    """Aktuelle Schema-Version (0 wenn noch nicht migriert)."""
    try:
        row = conn.execute(
            "SELECT MAX(version) AS v FROM schema_migrations"
        ).fetchone()
    except sqlite3.Error:
        return 0
    if row is None or row["v"] is None:
        return 0
    return int(row["v"])


def migrate(db_path: str | Path) -> int:
    """Wendet ausstehende Migrationen an. Gibt die neue Version zurück."""
    with connection(db_path) as conn:
        version = current_version(conn)
        if version < 1:
            try:
                conn.executescript(SCHEMA_SQL)
                conn.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (1, utc_now_iso()),
                )
            except sqlite3.Error as exc:
                raise DbError("Migration auf Version 1 fehlgeschlagen", cause=exc) from exc
            version = 1
        return version
