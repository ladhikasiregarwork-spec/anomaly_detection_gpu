"""
Penyimpanan pola (regex) yang sudah "dipelajari" - dipakai tahap "Have
Existing Pattern?" dan "Store New Pattern Regex" pada diagram.

Resource: SQLite file lokal - beban nyaris nol (baca/tulis milidetik),
tidak butuh service database terpisah. Cukup untuk skala kecil-menengah;
lihat PLAN §8 untuk jalur upgrade ke Postgres kalau volume pola membesar.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone

from app.config import settings

_lock = threading.Lock()  # SQLite file-based -> serialisasi write sederhana


@dataclass
class PatternRecord:
    id: int
    name: str
    signature_regex: str
    field_regex: dict[str, str]
    hit_count: int
    created_at: str


@contextmanager
def _connect():
    conn = sqlite3.connect(settings.pattern_db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                signature_regex TEXT NOT NULL,
                field_regex_json TEXT NOT NULL,
                hit_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )


def _row_to_record(row: sqlite3.Row) -> PatternRecord:
    return PatternRecord(
        id=row["id"],
        name=row["name"],
        signature_regex=row["signature_regex"],
        field_regex=json.loads(row["field_regex_json"]),
        hit_count=row["hit_count"],
        created_at=row["created_at"],
    )


def get_all_patterns() -> list[PatternRecord]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM patterns ORDER BY hit_count DESC").fetchall()
    return [_row_to_record(r) for r in rows]


def save_pattern(name: str, signature_regex: str, field_regex: dict[str, str]) -> PatternRecord:
    with _lock, _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO patterns (name, signature_regex, field_regex_json, hit_count, created_at)
            VALUES (?, ?, ?, 0, ?)
            """,
            (name, signature_regex, json.dumps(field_regex), datetime.now(timezone.utc).isoformat()),
        )
        new_id = cur.lastrowid
        row = conn.execute("SELECT * FROM patterns WHERE id = ?", (new_id,)).fetchone()
    return _row_to_record(row)


def increment_hit(pattern_id: int) -> None:
    with _lock, _connect() as conn:
        conn.execute("UPDATE patterns SET hit_count = hit_count + 1 WHERE id = ?", (pattern_id,))


def count_patterns() -> int:
    with _connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM patterns").fetchone()
    return row["c"]
