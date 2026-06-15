"""
ResearchMind — Paper result cache + history
File-backed JSON cache keyed by normalized topic/title.
Maintains a history index so the UI can list previously analysed papers.
"""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

_TTL_DAYS  = 30
_HIST_KEY  = "_history"
_lock      = threading.Lock()
_mem: dict[str, Any] = {}
_loaded    = False


# ── Storage helpers ───────────────────────────────────────────────────────────

def _cache_path() -> Path:
    from core.config import get_settings
    p = get_settings().export_dir.parent / "cache" / "paper_cache.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load() -> None:
    global _mem, _loaded
    if _loaded:
        return
    try:
        path = _cache_path()
        if path.exists():
            _mem = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _mem = {}
    _loaded = True


def _save() -> None:
    try:
        _cache_path().write_text(json.dumps(_mem, indent=2), encoding="utf-8")
    except Exception:
        pass


def _key(prefix: str, *parts: str) -> str:
    raw = ":".join(p.lower().strip()[:80] for p in parts)
    return f"{prefix}:{hashlib.md5(raw.encode()).hexdigest()}"


def _fresh(entry: dict) -> bool:
    try:
        return datetime.now() - datetime.fromisoformat(entry["cached_at"]) < timedelta(days=_TTL_DAYS)
    except Exception:
        return False


# ── History helpers ───────────────────────────────────────────────────────────

def _upsert_history(entry: dict) -> None:
    """Insert or replace a history entry matched by cache_key."""
    entries: list[dict] = _mem.get(_HIST_KEY, [])
    idx = next((i for i, e in enumerate(entries) if e.get("id") == entry.get("id")), None)
    if idx is not None:
        entries[idx] = entry
    else:
        entries.append(entry)
    _mem[_HIST_KEY] = entries


def get_history() -> list[dict]:
    """Return all history entries, most-recent first."""
    with _lock:
        _load()
        return sorted(
            _mem.get(_HIST_KEY, []),
            key=lambda e: e.get("cached_at", ""),
            reverse=True,
        )


def remove_history_entry(entry_id: str) -> None:
    """Remove a history entry AND its associated cache data."""
    with _lock:
        _load()
        entries: list[dict] = _mem.get(_HIST_KEY, [])
        entry = next((e for e in entries if e.get("id") == entry_id), None)
        if entry:
            # Remove the raw cached payload too
            if entry_id in _mem:
                del _mem[entry_id]
            _mem[_HIST_KEY] = [e for e in entries if e.get("id") != entry_id]
            _save()


def clear_history() -> None:
    """Remove all history entries and their cached data."""
    with _lock:
        _load()
        for entry in _mem.get(_HIST_KEY, []):
            eid = entry.get("id", "")
            if eid and eid in _mem:
                del _mem[eid]
        _mem[_HIST_KEY] = []
        _save()


# ── Pipeline cache ────────────────────────────────────────────────────────────

def get_pipeline_cache(topic: str) -> dict | None:
    with _lock:
        _load()
        entry = _mem.get(_key("pipeline", topic))
        if entry and _fresh(entry):
            return entry["data"]
    return None


def set_pipeline_cache(topic: str, data: dict) -> None:
    with _lock:
        _load()
        ck = _key("pipeline", topic)
        now = datetime.now().isoformat()
        _mem[ck] = {"data": data, "cached_at": now}

        papers = data.get("papers", [])
        tags   = list({p.get("tag", "") for p in papers if p.get("tag")})[:5]
        _upsert_history({
            "id":          ck,
            "query":       topic,
            "mode":        "topic_mastery",
            "cached_at":   now,
            "summary":     f"{len(papers)} papers curated on this topic",
            "paper_count": len(papers),
            "papers":      [
                {"title": p.get("title",""), "authors": p.get("authors",""), "year": p.get("year",0)}
                for p in papers[:4]
            ],
            "tags": tags,
        })
        _save()


# ── Explanation cache (world-knowledge only — not PDF RAG) ────────────────────

def get_explain_cache(title: str, section: str, level: str) -> str | None:
    with _lock:
        _load()
        entry = _mem.get(_key("explain", title, section, level))
        if entry and _fresh(entry):
            return entry["data"]
    return None


def set_explain_cache(title: str, section: str, level: str, text: str) -> None:
    with _lock:
        _load()
        ck  = _key("explain", title, section, level)
        now = datetime.now().isoformat()
        _mem[ck] = {"data": text, "cached_at": now}

        # Only single-paper "full" explanations go into the visible history
        if section == "full":
            summary = " ".join(text[:300].split())
            if len(text) > 300:
                summary += "…"
            _upsert_history({
                "id":          ck,
                "query":       title,
                "mode":        "single_paper",
                "cached_at":   now,
                "summary":     summary,
                "paper_count": 1,
                "papers":      [{"title": title}],
                "tags":        [level],
                "level":       level,
            })
        _save()
