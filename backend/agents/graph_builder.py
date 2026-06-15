"""
ResearchMind — Graph Builder Agent
Extracts concepts from discovered papers and builds a prerequisite knowledge graph.
"""
from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from core.clients import get_llm
from core.models import GraphNode, KnowledgeGraph, SessionState

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are ResearchMind's Graph Builder Agent.

Given a list of papers and their abstracts, extract the key prerequisite concepts
needed to understand these papers and build a dependency graph.

Return ONLY a JSON array of concept nodes:
[
  {
    "id": 0,
    "label": "Short concept name (max 2 words, use \\n for line break if needed)",
    "mastered": false,
    "edges": [list of node IDs this concept depends on — empty for root nodes],
    "rx": 0.0,   // relative X position 0.0-1.0 (left to right = simpler to harder)
    "ry": 0.5,   // relative Y position 0.0-1.0
    "r": 20      // radius 18-28 (bigger = more central)
  },
  ...
]

Rules:
- Include 6-10 nodes total
- Order from fundamental (left, low rx) to advanced (right, high rx)
- Edges point FROM a concept TO concepts that require it
- Root nodes (no prerequisites) have empty edges arrays
- Spread nodes so they don't overlap (vary rx and ry)
- Return ONLY the JSON array, no markdown or extra text
"""


def _default_graph() -> KnowledgeGraph:
    nodes = [
        GraphNode(id=0, label="Linear\nAlgebra",  mastered=False, edges=[2,3],  rx=.13, ry=.50, r=22),
        GraphNode(id=1, label="Calculus",          mastered=False, edges=[4],    rx=.13, ry=.20, r=22),
        GraphNode(id=2, label="Probability",       mastered=False, edges=[4,5],  rx=.32, ry=.33, r=20),
        GraphNode(id=3, label="Embeddings",        mastered=False, edges=[5,6],  rx=.32, ry=.68, r=20),
        GraphNode(id=4, label="Neural\nNetworks",  mastered=False, edges=[5,6],  rx=.50, ry=.18, r=24),
        GraphNode(id=5, label="Attention\nMech.",  mastered=False, edges=[6,7],  rx=.55, ry=.52, r=26),
        GraphNode(id=6, label="Transformers",      mastered=False, edges=[7],    rx=.74, ry=.32, r=28),
        GraphNode(id=7, label="BERT / GPT",        mastered=False, edges=[],     rx=.88, ry=.65, r=22),
    ]
    return KnowledgeGraph(nodes=nodes)


async def run_graph_builder(state: SessionState) -> SessionState:
    """
    Uses GPT to extract concepts from discovered papers and build a dependency graph.
    Merges with any already-mastered nodes from the diagnostic agent.
    """
    papers = state.papers
    if not papers:
        state.graph = _default_graph()
        state.agent_statuses["graph"] = "done"
        return state

    paper_summaries = "\n\n".join(
        f"Title: {p.title}\nAuthors: {p.authors} ({p.year})\nAbstract: {p.abstract[:400]}"
        for p in papers[:4]
    )

    llm = get_llm(fast=True)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Papers:\n\n{paper_summaries}"),
    ]

    try:
        resp  = await llm.ainvoke(messages)
        nodes_raw = json.loads(resp.content.strip())
        nodes = [GraphNode(**n) for n in nodes_raw]
    except Exception as e:
        log.warning("Graph builder LLM failed: %s — using default graph", e)
        state.graph = _default_graph()
        state.agent_statuses["graph"] = "done"
        return state

    # Apply mastered status from user profile
    mastered_concepts = {
        c.lower() for c in state.user_profile.get("mastered_concepts", [])
    }
    updated_nodes = []
    for node in nodes:
        label_key = node.label.replace("\n", " ").lower()
        is_mastered = any(m in label_key or label_key in m for m in mastered_concepts)
        updated_nodes.append(node.model_copy(update={"mastered": is_mastered}))

    state.graph = KnowledgeGraph(nodes=updated_nodes)
    state.agent_statuses["graph"] = "done"
    return state
