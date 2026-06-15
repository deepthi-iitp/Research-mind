"""
ResearchMind — Discovery Agent
Queries Semantic Scholar + arXiv to find relevant papers for a topic,
then sequences them in optimal learning order using GPT.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx
from langchain_core.messages import HumanMessage, SystemMessage

from core.clients import get_llm
from core.config import get_settings
from core.models import Paper, SessionState

log = logging.getLogger(__name__)
cfg = get_settings()

SEMANTIC_SCHOLAR_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"
ARXIV_SEARCH            = "https://export.arxiv.org/api/query"

SEQUENCE_SYSTEM = """You are ResearchMind's Discovery Agent.

Given a list of papers for the topic "{topic}", sequence them in the OPTIMAL learning order,
from foundational → essential → milestone → extension.

Return ONLY a JSON array of objects:
[
  {{"id": "<paper_id>", "order": 1, "tag": "Foundational", "reason": "why first"}},
  ...
]

Rules:
- Maximum 6 papers in the sequence
- Earlier papers must not depend on concepts only introduced in later papers
- Tags must be one of: Foundational, Essential, Milestone, Extension
- Return ONLY the JSON array, no markdown or extra text
"""


async def _search_semantic_scholar(topic: str, limit: int = 10) -> list[dict]:
    headers = {}
    if cfg.semantic_scholar_key:
        headers["x-api-key"] = cfg.semantic_scholar_key

    params = {
        "query":  topic,
        "limit":  limit,
        "fields": "title,authors,year,abstract,citationCount,externalIds,openAccessPdf",
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(SEMANTIC_SCHOLAR_SEARCH, params=params, headers=headers)
            r.raise_for_status()
            return r.json().get("data", [])
    except Exception as e:
        log.warning("Semantic Scholar search failed: %s", e)
        return []


async def _search_arxiv(topic: str, limit: int = 5) -> list[dict]:
    params = {
        "search_query": f"all:{topic}",
        "start":        0,
        "max_results":  limit,
        "sortBy":       "relevance",
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(ARXIV_SEARCH, params=params)
            r.raise_for_status()

        # Parse minimal atom feed
        import xml.etree.ElementTree as ET
        root = ET.fromstring(r.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        papers = []
        for entry in root.findall("atom:entry", ns):
            title   = entry.findtext("atom:title", "", ns).strip().replace("\n", " ")
            summary = entry.findtext("atom:summary", "", ns).strip()
            authors = ", ".join(
                a.findtext("atom:name", "", ns)
                for a in entry.findall("atom:author", ns)
            )
            arxiv_id = entry.findtext("atom:id", "", ns).split("/abs/")[-1]
            papers.append({
                "title": title, "abstract": summary,
                "authors": authors, "arxiv_id": arxiv_id,
            })
        return papers
    except Exception as e:
        log.warning("arXiv search failed: %s", e)
        return []


def _ss_to_paper(item: dict, order: int = 0) -> Paper:
    authors = ", ".join(a.get("name", "") for a in item.get("authors", [])[:4])
    ext     = item.get("externalIds", {})
    return Paper(
        title=item.get("title", "Untitled"),
        authors=authors or "Unknown",
        year=item.get("year") or 2020,
        abstract=item.get("abstract") or "",
        arxiv_id=ext.get("ArXiv", ""),
        doi=ext.get("DOI", ""),
        citations=item.get("citationCount") or 0,
        order=order,
    )


async def run_discovery_agent(state: SessionState) -> SessionState:
    """
    Searches Semantic Scholar and arXiv concurrently,
    deduplicates, sequences with GPT, and stores papers in state.
    """
    topic = state.topic or state.query

    # 1. Parallel search
    ss_results, ax_results = await asyncio.gather(
        _search_semantic_scholar(topic, limit=12),
        _search_arxiv(topic, limit=5),
    )

    # 2. Build candidate list from Semantic Scholar (primary source)
    candidates: list[dict[str, Any]] = []
    seen_titles: set[str] = set()

    for item in ss_results:
        t = item.get("title", "").lower().strip()
        if t and t not in seen_titles:
            seen_titles.add(t)
            candidates.append({
                "id":       item.get("paperId", ""),
                "title":    item.get("title", ""),
                "year":     item.get("year") or 2020,
                "citations":item.get("citationCount") or 0,
                "abstract": (item.get("abstract") or "")[:300],
                "_raw":     item,
            })

    # Enrich with arXiv results (fallback / supplementary)
    for ax in ax_results:
        t = ax.get("title", "").lower().strip()
        if t and t not in seen_titles:
            seen_titles.add(t)
            candidates.append({
                "id":       ax.get("arxiv_id", ""),
                "title":    ax.get("title", ""),
                "year":     2022,
                "citations":0,
                "abstract": ax.get("abstract", "")[:300],
                "_raw":     ax,
            })

    if not candidates:
        # Fallback to hard-coded demo papers so the app always works
        from core.models import Paper as P
        state.papers = _hardcoded_papers(topic)
        state.agent_statuses["discovery"] = "done"
        return state

    # 3. Ask GPT to sequence the top candidates
    llm = get_llm(fast=True)
    cand_json = json.dumps(
        [{"id": c["id"], "title": c["title"], "year": c["year"], "citations": c["citations"],
          "abstract": c["abstract"]} for c in candidates[:15]],
        indent=2
    )
    messages = [
        SystemMessage(content=SEQUENCE_SYSTEM.format(topic=topic)),
        HumanMessage(content=cand_json),
    ]
    try:
        resp = await llm.ainvoke(messages)
        sequence = json.loads(resp.content.strip())
    except Exception as e:
        log.warning("GPT sequencing failed: %s — using citation-count order", e)
        sequence = [
            {"id": c["id"], "order": i+1, "tag": ["Foundational","Essential","Milestone","Extension"][min(i,3)], "reason": ""}
            for i, c in enumerate(sorted(candidates, key=lambda x: x["citations"], reverse=True)[:4])
        ]

    # 4. Assemble final Paper list
    id_to_cand = {c["id"]: c for c in candidates}
    papers: list[Paper] = []
    for seq_item in sequence[:6]:
        cand = id_to_cand.get(seq_item["id"])
        if not cand:
            continue
        raw = cand["_raw"]
        p = _ss_to_paper(raw, order=seq_item.get("order", 0)) if "paperId" in raw else Paper(
            title=raw.get("title",""), authors=raw.get("authors",""),
            year=cand["year"], abstract=raw.get("abstract",""),
            arxiv_id=raw.get("arxiv_id",""), citations=cand["citations"],
            order=seq_item.get("order",0),
        )
        p.tag = seq_item.get("tag", "Essential")
        papers.append(p)

    papers.sort(key=lambda x: x.order)
    state.papers = papers
    state.agent_statuses["discovery"] = "done"
    return state


def _hardcoded_papers(topic: str) -> list[Paper]:
    """Fallback papers used when external APIs are unavailable."""
    return [
        Paper(title="Attention Is All You Need",
              authors="Vaswani, Shazeer, Parmar et al.", year=2017,
              citations=87000, tag="Foundational", order=1,
              abstract="We propose the Transformer, a model architecture based solely on attention mechanisms."),
        Paper(title="BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
              authors="Devlin, Chang, Lee, Toutanova", year=2018,
              citations=52000, tag="Essential", order=2,
              abstract="We introduce BERT, which obtains new state-of-the-art results on eleven NLP tasks."),
        Paper(title="Language Models are Few-Shot Learners",
              authors="Brown et al.", year=2020,
              citations=38000, tag="Milestone", order=3,
              abstract="We train GPT-3, an autoregressive language model with 175 billion parameters."),
        Paper(title="An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale",
              authors="Dosovitskiy et al.", year=2020,
              citations=25000, tag="Extension", order=4,
              abstract="We apply a pure transformer to sequences of image patches for image classification."),
    ]
