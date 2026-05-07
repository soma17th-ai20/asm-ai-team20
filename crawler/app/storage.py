from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Optional

from .models import RawNotice, StoredNotice

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "notices.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS notices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id   TEXT    NOT NULL,
    title       TEXT    NOT NULL,
    url         TEXT    NOT NULL,
    posted_at   TEXT,
    summary     TEXT,
    hash        TEXT    NOT NULL UNIQUE,
    fetched_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notices_source ON notices(source_id);
CREATE INDEX IF NOT EXISTS idx_notices_fetched_at ON notices(fetched_at DESC);
"""


def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def connect(db_path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    target = Path(db_path) if db_path else DB_PATH
    _ensure_dir(target)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def insert_many(conn: sqlite3.Connection, notices: Iterable[RawNotice]) -> tuple[int, int]:
    inserted = 0
    duplicates = 0
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for n in notices:
        try:
            conn.execute(
                """
                INSERT INTO notices (source_id, title, url, posted_at, summary, hash, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    n.source_id,
                    n.title.strip(),
                    str(n.url),
                    n.posted_at,
                    n.summary,
                    n.content_hash(),
                    fetched_at,
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            duplicates += 1
    return inserted, duplicates


def list_notices(
    conn: sqlite3.Connection,
    source_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[StoredNotice]:
    if source_id:
        rows = conn.execute(
            "SELECT * FROM notices WHERE source_id = ? ORDER BY fetched_at DESC, id DESC LIMIT ? OFFSET ?",
            (source_id, limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM notices ORDER BY fetched_at DESC, id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [StoredNotice(**dict(r)) for r in rows]


def count(conn: sqlite3.Connection, source_id: Optional[str] = None) -> int:
    if source_id:
        row = conn.execute("SELECT COUNT(*) AS c FROM notices WHERE source_id = ?", (source_id,)).fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) AS c FROM notices").fetchone()
    return int(row["c"])
