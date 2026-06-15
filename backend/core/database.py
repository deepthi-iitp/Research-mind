"""
ResearchMind — SQLite persistent paper database
Stores every processed paper, its explanation, and generated PDF paths
so analyses can be retrieved, downloaded, and deleted without reprocessing.

All public functions are synchronous; use asyncio.to_thread in async handlers.
The DB id matches the JSON-cache key so the two stores stay in sync.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)
_lock  = threading.RLock()
_path: Path | None = None

# ── Schema ────────────────────────────────────────────────────────────────────

_SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode  = WAL;

CREATE TABLE IF NOT EXISTS paper_records (
    id            TEXT PRIMARY KEY,       -- same key as JSON cache entry
    title         TEXT NOT NULL,
    authors       TEXT DEFAULT '',
    year          INTEGER DEFAULT 0,
    abstract      TEXT DEFAULT '',
    arxiv_id      TEXT DEFAULT '',
    doi           TEXT DEFAULT '',
    citations     INTEGER DEFAULT 0,
    url           TEXT DEFAULT '',
    tag           TEXT DEFAULT '',
    mode          TEXT DEFAULT 'single_paper',
    topic         TEXT DEFAULT '',
    reader_level  TEXT DEFAULT '',
    summary       TEXT DEFAULT '',
    tags_json     TEXT DEFAULT '[]',
    papers_json   TEXT DEFAULT '[]',      -- topic mastery: list of child papers
    explanation   TEXT DEFAULT '',        -- single paper: full explanation text
    pdf_path      TEXT DEFAULT '',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
"""

# ── Connection helpers ─────────────────────────────────────────────────────────

def _db_path() -> Path:
    global _path
    if _path is None:
        from core.config import get_settings
        cfg = get_settings()
        d   = cfg.export_dir.parent / "db"
        d.mkdir(parents=True, exist_ok=True)
        _path = d / "researchmind.db"
    return _path


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(_db_path()), check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["tags"]   = json.loads(d.pop("tags_json",   "[]") or "[]")
    d["papers"] = json.loads(d.pop("papers_json", "[]") or "[]")
    return d


# ── Public API ────────────────────────────────────────────────────────────────

def init_db() -> None:
    """Create tables. Safe to call multiple times."""
    with _lock:
        c = _conn()
        c.executescript(_SCHEMA)
        c.commit()
        c.close()
    log.info("SQLite paper database ready at %s", _db_path())


def upsert_record(data: dict) -> None:
    """
    Insert or update a paper record.
    Required keys: id, title, mode.
    Optional: authors, year, abstract, arxiv_id, doi, citations, url, tag,
              topic, reader_level, summary, tags (list), papers (list),
              explanation, pdf_path.
    """
    now = datetime.now().isoformat()
    with _lock:
        c = _conn()
        exists = c.execute("SELECT id FROM paper_records WHERE id=?",
                           (data["id"],)).fetchone()
        tags_json   = json.dumps(data.get("tags",   []))
        papers_json = json.dumps(data.get("papers", []))

        if exists:
            c.execute("""
                UPDATE paper_records SET
                    title=?, authors=?, year=?, abstract=?, arxiv_id=?, doi=?,
                    citations=?, url=?, tag=?, mode=?, topic=?, reader_level=?,
                    summary=?, tags_json=?, papers_json=?, explanation=?,
                    updated_at=?
                WHERE id=?
            """, (
                data.get("title", ""), data.get("authors", ""),
                data.get("year", 0),   data.get("abstract", ""),
                data.get("arxiv_id", ""), data.get("doi", ""),
                data.get("citations", 0), data.get("url", ""),
                data.get("tag", ""),   data.get("mode", "single_paper"),
                data.get("topic", ""), data.get("reader_level", ""),
                data.get("summary", ""), tags_json, papers_json,
                data.get("explanation", ""), now,
                data["id"],
            ))
        else:
            c.execute("""
                INSERT INTO paper_records (
                    id, title, authors, year, abstract, arxiv_id, doi,
                    citations, url, tag, mode, topic, reader_level, summary,
                    tags_json, papers_json, explanation, pdf_path,
                    created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                data["id"], data.get("title", ""), data.get("authors", ""),
                data.get("year", 0), data.get("abstract", ""),
                data.get("arxiv_id", ""), data.get("doi", ""),
                data.get("citations", 0), data.get("url", ""),
                data.get("tag", ""), data.get("mode", "single_paper"),
                data.get("topic", ""), data.get("reader_level", ""),
                data.get("summary", ""), tags_json, papers_json,
                data.get("explanation", ""), data.get("pdf_path", ""),
                now, now,
            ))
        c.commit()
        c.close()


def update_pdf_path(record_id: str, pdf_path: str) -> None:
    with _lock:
        c = _conn()
        c.execute("UPDATE paper_records SET pdf_path=?, updated_at=? WHERE id=?",
                  (pdf_path, datetime.now().isoformat(), record_id))
        c.commit()
        c.close()


def update_explanation(record_id: str, explanation: str) -> None:
    """Append / overwrite the full explanation for a single-paper record."""
    with _lock:
        c = _conn()
        c.execute(
            "UPDATE paper_records SET explanation=?, updated_at=? WHERE id=?",
            (explanation, datetime.now().isoformat(), record_id),
        )
        c.commit()
        c.close()


def get_records(mode: str | None = None) -> list[dict]:
    """Return all records (newest first). Optionally filter by mode."""
    with _lock:
        c = _conn()
        if mode:
            rows = c.execute(
                "SELECT * FROM paper_records WHERE mode=? ORDER BY updated_at DESC",
                (mode,)
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM paper_records ORDER BY updated_at DESC"
            ).fetchall()
        result = [_row_to_dict(r) for r in rows]
        c.close()
        return result


def get_record(record_id: str) -> dict | None:
    with _lock:
        c = _conn()
        row = c.execute("SELECT * FROM paper_records WHERE id=?",
                        (record_id,)).fetchone()
        c.close()
        return _row_to_dict(row) if row else None


def delete_record(record_id: str) -> str | None:
    """
    Delete the record and return its pdf_path so the caller can clean up
    the file on disk. Returns None if the record did not exist.
    """
    with _lock:
        c = _conn()
        row = c.execute("SELECT pdf_path FROM paper_records WHERE id=?",
                        (record_id,)).fetchone()
        pdf_path = row["pdf_path"] if row else None
        c.execute("DELETE FROM paper_records WHERE id=?", (record_id,))
        c.commit()
        c.close()
        return pdf_path or None


# ── Migration: JSON cache → SQLite ────────────────────────────────────────────

def migrate_from_cache() -> None:
    """
    One-time import of all existing JSON-cache history entries into SQLite.
    Already-imported records are skipped. Safe to call on every startup.
    """
    try:
        from core.cache import get_history
        entries = get_history()
    except Exception:
        return

    migrated = 0
    for entry in entries:
        if not entry.get("id"):
            continue
        if get_record(entry["id"]) is not None:
            continue
        upsert_record({
            "id":      entry["id"],
            "title":   entry.get("query", ""),
            "mode":    entry.get("mode", "single_paper"),
            "topic":   entry.get("query", ""),
            "summary": entry.get("summary", ""),
            "tags":    entry.get("tags", []),
            "papers":  entry.get("papers", []),
            "reader_level": entry.get("level", ""),
        })
        migrated += 1

    if migrated:
        log.info("Migrated %d cache history entries to SQLite", migrated)
