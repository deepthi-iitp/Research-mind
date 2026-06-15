"""
Request-scoped OpenAI API key via ContextVar.
asyncio.create_task copies the current context at creation time, so setting
this in a FastAPI dependency propagates correctly into pipeline sub-tasks.
"""
from __future__ import annotations
from contextvars import ContextVar

_openai_key: ContextVar[str | None] = ContextVar("openai_key", default=None)


def get_request_api_key() -> str | None:
    return _openai_key.get()


def set_request_api_key(key: str | None) -> None:
    _openai_key.set(key)
