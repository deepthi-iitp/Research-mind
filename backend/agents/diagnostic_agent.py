"""
ResearchMind — Diagnostic Agent
Analyses the user's 5-question diagnostic answers and builds a knowledge profile.
Returns an adjusted learning path (which nodes are pre-mastered, entry level).
"""
from __future__ import annotations

import json
from langchain_core.messages import HumanMessage, SystemMessage

from core.clients import get_llm
from core.models import SessionState, GraphNode, KnowledgeGraph


SYSTEM_PROMPT = """You are ResearchMind's Diagnostic Agent.

Given a student's answers to 5 diagnostic questions about their background knowledge,
produce a JSON knowledge profile with exactly this shape:

{
  "level": "beginner" | "intermediate" | "advanced",
  "mastered_concepts": ["list of concept strings the student already knows"],
  "entry_point": "which topic to start from",
  "skip_prereqs": ["list of prerequisite IDs to skip"],
  "notes": "1-2 sentence personalised note about the student's profile"
}

The diagnostic questions were:
1. Prior machine learning experience (0=none, 1=some, 2=intermediate, 3=advanced)
2. Neural network familiarity     (0=none, 1=heard, 2=basics, 3=used)
3. Linear algebra strength        (0=none, 1=rusty, 2=comfortable, 3=strong)
4. Prior paper reading experience (0=never, 1=1-2, 2=several, 3=published)
5. Primary goal                   (0=understand, 1=implement, 2=research, 3=teach)

Return ONLY the JSON object, no markdown, no extra text.
"""


# Default graph for "Transformers in NLP" topic
DEFAULT_NODES = [
    GraphNode(id=0, label="Linear\nAlgebra",   mastered=False, edges=[2,3],   rx=.13, ry=.50, r=22),
    GraphNode(id=1, label="Calculus",           mastered=False, edges=[4],     rx=.13, ry=.20, r=22),
    GraphNode(id=2, label="Probability",        mastered=False, edges=[4,5],   rx=.32, ry=.33, r=20),
    GraphNode(id=3, label="Embeddings",         mastered=False, edges=[5,6],   rx=.32, ry=.68, r=20),
    GraphNode(id=4, label="Neural\nNetworks",   mastered=False, edges=[5,6],   rx=.50, ry=.18, r=24),
    GraphNode(id=5, label="Attention\nMech.",   mastered=False, edges=[6,7],   rx=.55, ry=.52, r=26),
    GraphNode(id=6, label="Transformers",       mastered=False, edges=[7],     rx=.74, ry=.32, r=28),
    GraphNode(id=7, label="BERT / GPT",         mastered=False, edges=[],      rx=.88, ry=.65, r=22),
]

CONCEPT_TO_NODE_IDX = {
    "linear algebra": 0,
    "calculus":       1,
    "probability":    2,
    "embeddings":     3,
    "neural networks":4,
    "attention":      5,
    "transformers":   6,
    "bert":           7,
    "gpt":            7,
}


async def run_diagnostic_agent(state: SessionState, diagnostic_answers: list[int]) -> SessionState:
    """
    Calls GPT to interpret diagnostic answers, marks mastered nodes,
    and updates the session state with the user profile.
    """
    llm = get_llm(fast=True)

    answer_str = "\n".join(
        f"Q{i+1}: {v}" for i, v in enumerate(diagnostic_answers)
    )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Student diagnostic answers:\n{answer_str}"),
    ]

    response = await llm.ainvoke(messages)
    raw = response.content.strip()

    try:
        profile = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback default profile
        profile = {
            "level": "intermediate",
            "mastered_concepts": ["linear algebra", "calculus"],
            "entry_point": "neural networks",
            "skip_prereqs": [],
            "notes": "Profile could not be parsed; using intermediate defaults.",
        }

    # Build knowledge graph with mastered nodes pre-marked
    mastered = {c.lower() for c in profile.get("mastered_concepts", [])}
    nodes = []
    for n in DEFAULT_NODES:
        label_key = n.label.replace("\n", " ").lower().strip()
        is_mastered = any(m in label_key or label_key in m for m in mastered)
        nodes.append(n.model_copy(update={"mastered": is_mastered}))

    state.graph              = KnowledgeGraph(nodes=nodes)
    state.user_profile       = profile
    state.diagnostic_ans     = diagnostic_answers
    state.agent_statuses["diagnostic"] = "done"

    return state
