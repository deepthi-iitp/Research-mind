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

from langgraph.graph import StateGraph, END

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
# LangGraph nodes must be sync or async callables: state → state.

async def _diagnostic_node(state: SessionState) -> SessionState:
    state.agent_statuses["diagnostic"] = AgentStatus.RUNNING
    return await run_diagnostic_agent(state, state.diagnostic_ans)


async def _discovery_node(state: SessionState) -> SessionState:
    state.agent_statuses["discovery"] = AgentStatus.RUNNING
    return await run_discovery_agent(state)


async def _graph_node(state: SessionState) -> SessionState:
    state.agent_statuses["graph"] = AgentStatus.RUNNING
    return await run_graph_builder(state)


async def _scraper_node(state: SessionState) -> SessionState:
    state.agent_statuses["scraper"] = AgentStatus.RUNNING
    return await run_scraper_agent(state)


async def _quiz_node(state: SessionState) -> SessionState:
    state.agent_statuses["quiz"] = AgentStatus.RUNNING
    return await run_quiz_generator(state)


# ── Build graph ───────────────────────────────────────────────────────────────

def build_mode2_graph() -> StateGraph:
    """
    Returns a compiled LangGraph for the Topic Mastery pipeline.
    State schema is SessionState (Pydantic model — LangGraph handles serialisation).
    """
    builder = StateGraph(SessionState)

    builder.add_node("diagnostic",    _diagnostic_node)
    builder.add_node("discovery",     _discovery_node)
    builder.add_node("graph_builder", _graph_node)
    builder.add_node("scraper",       _scraper_node)
    builder.add_node("quiz_gen",      _quiz_node)

    builder.set_entry_point("diagnostic")
    builder.add_edge("diagnostic",    "discovery")
    builder.add_edge("discovery",     "graph_builder")
    builder.add_edge("graph_builder", "scraper")
    builder.add_edge("scraper",       "quiz_gen")
    builder.add_edge("quiz_gen",      END)

    return builder.compile()


# ── Streaming runner ──────────────────────────────────────────────────────────

NODES_IN_ORDER = [
    ("diagnostic",    _diagnostic_node,  15),
    ("discovery",     _discovery_node,   35),
    ("graph_builder", _graph_node,       52),
    ("scraper",       _scraper_node,     68),
    ("quiz_gen",      _quiz_node,        85),
]


async def stream_mode2_pipeline(
    state: SessionState,
    on_update: callable,
) -> SessionState:
    """
    Runs the full Mode 2 pipeline with progress callbacks after each node.
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
            await on_update(agent_id, AgentStatus.DONE, {
                "overall_pct": pct,
                "papers":    [p.model_dump() for p in state.papers]         if agent_id == "discovery"     else None,
                "graph":     state.graph.model_dump()                        if agent_id == "graph_builder" else None,
                "questions": [q.model_dump() for q in state.quiz_questions] if agent_id == "quiz_gen"      else None,
            })
        return state

    build_mode2_graph()

    for agent_id, node_fn, pct in NODES_IN_ORDER:
        state.agent_statuses[agent_id] = AgentStatus.RUNNING
        await on_update(agent_id, AgentStatus.RUNNING, {})

        try:
            state = await node_fn(state)
            state.agent_statuses[agent_id] = AgentStatus.DONE
            state.overall_pct = pct
            await on_update(agent_id, AgentStatus.DONE, {
                "overall_pct": pct,
                "papers":    [p.model_dump() for p in state.papers]         if agent_id == "discovery"     else None,
                "graph":     state.graph.model_dump()                        if agent_id == "graph_builder" else None,
                "questions": [q.model_dump() for q in state.quiz_questions] if agent_id == "quiz_gen"      else None,
            })
        except Exception as e:
            log.error("Agent %s failed: %s", agent_id, e, exc_info=True)
            state.agent_statuses[agent_id] = AgentStatus.FAILED
            await on_update(agent_id, AgentStatus.FAILED, {"error": str(e)})

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
