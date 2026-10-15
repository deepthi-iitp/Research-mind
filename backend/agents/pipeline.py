"""
ResearchMind — LangGraph Orchestration Pipeline
Wires all agents into a stateful directed graph using LangGraph.

Graph (Mode 2):
  START
    └─► diagnostic  ──► discovery  ──► graph_builder
                                            └─► scraper  ──► quiz_gen  ──► END

Each node is an async function that receives SessionState and returns SessionState.
A SSE stream publishes agent status updates back to the frontend.
"""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from functools import lru_cache
from typing import Callable

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END

from core.models import SessionState, AgentStatus, Paper, KnowledgeGraph, QuizQuestion
from core.cache  import get_pipeline_cache, set_pipeline_cache
from core.database import upsert_record
from agents.diagnostic_agent import run_diagnostic_agent
from agents.discovery_agent  import run_discovery_agent
from agents.graph_builder     import run_graph_builder
from agents.scraper_agent     import run_scraper_agent
from agents.quiz_agent        import run_quiz_generator

log = logging.getLogger(__name__)

# ── Node wrappers ─────────────────────────────────────────────────────────────
# Each agent is wrapped so that it:
#   1. reports RUNNING / DONE / FAILED over SSE (callback passed via LangGraph config)
#   2. never crashes the graph — a failing agent is marked FAILED and the
#      pipeline continues with whatever state it has (per-agent failure isolation)

NODES_IN_ORDER = [
    ("diagnostic",    run_diagnostic_agent, 15),
    ("discovery",     run_discovery_agent,  35),
    ("graph_builder", run_graph_builder,    52),
    ("scraper",       run_scraper_agent,    68),
    ("quiz_gen",      run_quiz_generator,   85),
]

MAX_DISCOVERY_RETRIES = 1


def _payload(agent_id: str, state: SessionState, pct: int) -> dict:
    return {
        "overall_pct": pct,
        "papers":    [p.model_dump() for p in state.papers]         if agent_id == "discovery"     else None,
        "graph":     state.graph.model_dump()                        if agent_id == "graph_builder" else None,
        "questions": [q.model_dump() for q in state.quiz_questions] if agent_id == "quiz_gen"      else None,
    }


def _make_node(agent_id: str, agent_fn: Callable, pct: int):
    async def node(state: SessionState, config: RunnableConfig) -> SessionState:
        on_update = config["configurable"]["on_update"]
        state.agent_statuses[agent_id] = AgentStatus.RUNNING
        await on_update(agent_id, AgentStatus.RUNNING, {})
        try:
            if agent_id == "diagnostic":
                state = await agent_fn(state, state.diagnostic_ans)
            else:
                if agent_id == "discovery" and state.user_profile.get("discovery_attempts", 0) > 0:
                    await asyncio.sleep(2)          # back off before retrying (API rate limits)
                state = await agent_fn(state)
            if agent_id == "discovery":
                state.user_profile["discovery_attempts"] = state.user_profile.get("discovery_attempts", 0) + 1
            state.agent_statuses[agent_id] = AgentStatus.DONE
            state.overall_pct = pct
            await on_update(agent_id, AgentStatus.DONE, _payload(agent_id, state, pct))
        except Exception as e:
            log.error("Agent %s failed: %s", agent_id, e, exc_info=True)
            if agent_id == "discovery":
                state.user_profile["discovery_attempts"] = state.user_profile.get("discovery_attempts", 0) + 1
            state.agent_statuses[agent_id] = AgentStatus.FAILED
            await on_update(agent_id, AgentStatus.FAILED, {"error": str(e)})
        return state
    node.__name__ = f"{agent_id}_node"
    return node


def _route_after_discovery(state: SessionState) -> str:
    """Conditional edge: retry discovery once if no papers came back."""
    attempts = state.user_profile.get("discovery_attempts", 0)
    if not state.papers and attempts <= MAX_DISCOVERY_RETRIES:
        log.info("Discovery returned no papers (attempt %d) — retrying", attempts)
        return "discovery"
    return "graph_builder"


# ── Build graph ───────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def build_mode2_graph():
    """
    Compiled LangGraph for the Topic Mastery pipeline.

      diagnostic → discovery ─┬─► graph_builder → scraper → quiz_gen → END
                       ▲      │
                       └──────┘  (retry once if no papers were found)
    """
    builder = StateGraph(SessionState)
    for agent_id, fn, pct in NODES_IN_ORDER:
        builder.add_node(agent_id, _make_node(agent_id, fn, pct))

    builder.add_edge(START,           "diagnostic")
    builder.add_edge("diagnostic",    "discovery")
    builder.add_conditional_edges("discovery", _route_after_discovery,
                                  {"discovery": "discovery", "graph_builder": "graph_builder"})
    builder.add_edge("graph_builder", "scraper")
    builder.add_edge("scraper",       "quiz_gen")
    builder.add_edge("quiz_gen",      END)
    return builder.compile()


# ── Streaming runner ──────────────────────────────────────────────────────────

async def stream_mode2_pipeline(
    state: SessionState,
    on_update: Callable,
) -> SessionState:
    """
    Runs the Mode 2 LangGraph pipeline, emitting progress via on_update after each node.
    Returns cached results immediately if the same topic was processed before.
    """
    topic = state.topic or state.query
    cached = get_pipeline_cache(topic)

    if cached:
        log.info("Cache hit for topic=%r — skipping agents", topic)
        state.papers         = [Paper(**p)         for p in cached.get("papers",         [])]
        state.graph          = KnowledgeGraph(**cached.get("graph", {"nodes": []}))
        state.quiz_questions = [QuizQuestion(**q)  for q in cached.get("quiz_questions", [])]
        state.overall_pct    = 88
        for agent_id, _, pct in NODES_IN_ORDER:
            state.agent_statuses[agent_id] = AgentStatus.DONE
            await on_update(agent_id, AgentStatus.DONE, _payload(agent_id, state, pct))
        return state

    state.user_profile.pop("discovery_attempts", None)
    graph = build_mode2_graph()
    result = await graph.ainvoke(
        state,
        config={"configurable": {"on_update": on_update}, "recursion_limit": 25},
    )
    state = result if isinstance(result, SessionState) else SessionState(**result)

    # Persist results so the same topic is instant next time
    papers_dump = [p.model_dump() for p in state.papers]
    set_pipeline_cache(topic, {
        "papers":         papers_dump,
        "graph":          state.graph.model_dump(),
        "quiz_questions": [q.model_dump() for q in state.quiz_questions],
    })

    # Persist to SQLite for the "Previous Papers" front-page section
    import hashlib as _hashlib
    cache_key = "pipeline:" + _hashlib.md5(topic.lower().strip()[:80].encode()).hexdigest()
    tags = list({p.get("tag", "") for p in papers_dump if p.get("tag")})[:5]
    upsert_record({
        "id":      cache_key,
        "title":   topic,
        "mode":    "topic_mastery",
        "topic":   topic,
        "summary": f"{len(papers_dump)} papers curated on this topic",
        "tags":    tags,
        "papers":  [
            {"title": p.get("title", ""), "authors": p.get("authors", ""),
             "year": p.get("year", 0), "tag": p.get("tag", "")}
            for p in papers_dump[:4]
        ],
    })

    state.overall_pct = 88
    return state
