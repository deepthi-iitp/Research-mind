"""
Robust JSON extraction from LLM replies.

Models often wrap JSON in ```json fences, add a sentence before/after it,
copy // comments from the prompt, or leave trailing commas. A bare json.loads()
fails on all of these and silently sends agents to their fallback output.
"""
from __future__ import annotations

import json
import re
from typing import Any


def _strip_comments(text: str) -> str:
    """Remove // line comments that are not inside strings."""
    out, in_str, esc, i = [], False, False, 0
    while i < len(text):
        c = text[i]
        if in_str:
            out.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
            out.append(c)
        elif c == "/" and text[i:i + 2] == "//":
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        else:
            out.append(c)
        i += 1
    return "".join(out)


def _outermost(text: str, open_ch: str, close_ch: str) -> str | None:
    start = text.find(open_ch)
    if start == -1:
        return None
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def parse_llm_json(text: str, expect: type = None) -> Any:
    """
    Parse JSON from an LLM reply. `expect` may be list or dict to pick the
    right outer structure when the reply contains both.
    Raises ValueError if nothing parseable is found.
    """
    if not isinstance(text, str):
        raise ValueError("LLM reply is not text")
    raw = text.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I).strip()

    candidates = [raw]
    order = [("[", "]"), ("{", "}")] if expect is not list and expect is not dict else (
        [("[", "]")] if expect is list else [("{", "}")])
    if expect is None:
        # whichever structure starts first
        order.sort(key=lambda p: (raw.find(p[0]) if raw.find(p[0]) != -1 else 10**9))
    for o, c in order:
        block = _outermost(raw, o, c)
        if block:
            candidates.append(block)

    for cand in candidates:
        for fix in (lambda s: s,
                    _strip_comments,
                    lambda s: re.sub(r",\s*([\]}])", r"\1", _strip_comments(s))):
            try:
                val = json.loads(fix(cand))
            except (json.JSONDecodeError, TypeError):
                continue
            if expect is None or isinstance(val, expect):
                return val
    raise ValueError(f"Could not parse JSON from LLM reply: {raw[:200]!r}")
