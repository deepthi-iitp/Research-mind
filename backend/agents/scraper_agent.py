"""
ResearchMind — Scraper Agent
Fetches prerequisite learning resources:
  • Wikipedia summaries
  • YouTube video recommendations
  • Distill.pub / TowardsDataScience articles (heuristic search)
"""
from __future__ import annotations

import asyncio
import logging
import urllib.parse

import httpx
from bs4 import BeautifulSoup

from core.config import get_settings
from core.models import SessionState

log = logging.getLogger(__name__)
cfg = get_settings()

WIKIPEDIA_API  = "https://en.wikipedia.org/api/rest_v1/page/summary/{}"
YOUTUBE_SEARCH = "https://www.googleapis.com/youtube/v3/search"
YT_NO_KEY_URL  = "https://www.youtube.com/results?search_query={}"


# ── Wikipedia ─────────────────────────────────────────────────────────────────

async def _fetch_wikipedia(concept: str) -> dict:
    slug = concept.replace(" ", "_")
    url  = WIKIPEDIA_API.format(urllib.parse.quote(slug))
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            if r.status_code == 200:
                data = r.json()
                return {
                    "source":  "Wikipedia",
                    "title":   data.get("title", concept),
                    "summary": data.get("extract", "")[:600],
                    "url":     data.get("content_urls", {}).get("desktop", {}).get("page", ""),
                }
    except Exception as e:
        log.debug("Wikipedia fetch failed for %s: %s", concept, e)
    return {"source": "Wikipedia", "title": concept, "summary": "", "url": ""}


# ── YouTube ───────────────────────────────────────────────────────────────────

async def _fetch_youtube(concept: str, max_results: int = 3) -> list[dict]:
    if cfg.youtube_api_key:
        return await _youtube_api(concept, max_results)
    return _youtube_fallback(concept)


async def _youtube_api(concept: str, max_results: int) -> list[dict]:
    params = {
        "part":       "snippet",
        "q":          f"{concept} explained tutorial",
        "type":       "video",
        "maxResults": max_results,
        "order":      "relevance",
        "key":        cfg.youtube_api_key,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(YOUTUBE_SEARCH, params=params)
            r.raise_for_status()
            items = r.json().get("items", [])
            return [
                {
                    "title":    i["snippet"]["title"],
                    "channel":  i["snippet"]["channelTitle"],
                    "video_id": i["id"]["videoId"],
                    "url":      f"https://youtu.be/{i['id']['videoId']}",
                    "thumbnail":i["snippet"]["thumbnails"]["medium"]["url"],
                }
                for i in items
            ]
    except Exception as e:
        log.debug("YouTube API failed: %s", e)
    return _youtube_fallback(concept)


def _youtube_fallback(concept: str) -> list[dict]:
    """
    Curated high-quality video recommendations for common ML prerequisites.
    Used when YouTube API key is not configured.
    """
    CURATED: dict[str, list[dict]] = {
        "linear algebra": [
            {"title":"Essence of Linear Algebra","channel":"3Blue1Brown","url":"https://youtu.be/fNk_zzaMoSs","video_id":"fNk_zzaMoSs"},
            {"title":"Linear Algebra Full Course","channel":"Gilbert Strang / MIT","url":"https://youtu.be/QVKj3LADCnA","video_id":"QVKj3LADCnA"},
        ],
        "calculus": [
            {"title":"Essence of Calculus","channel":"3Blue1Brown","url":"https://youtu.be/WUvTyaaNkzM","video_id":"WUvTyaaNkzM"},
        ],
        "neural networks": [
            {"title":"Neural Networks: Zero to Hero","channel":"Andrej Karpathy","url":"https://youtu.be/VMj-3S1tku0","video_id":"VMj-3S1tku0"},
            {"title":"But What is a Neural Network?","channel":"3Blue1Brown","url":"https://youtu.be/aircAruvnKk","video_id":"aircAruvnKk"},
        ],
        "attention": [
            {"title":"Attention Is All You Need — Paper Explained","channel":"Yannic Kilcher","url":"https://youtu.be/iDulhoQ2pro","video_id":"iDulhoQ2pro"},
            {"title":"Illustrated Guide to Transformers","channel":"The A.I. Hacker","url":"https://youtu.be/4Bdc55j80l8","video_id":"4Bdc55j80l8"},
        ],
        "transformers": [
            {"title":"Transformers from Scratch","channel":"Andrej Karpathy","url":"https://youtu.be/kCc8FmEb1nY","video_id":"kCc8FmEb1nY"},
            {"title":"The Illustrated Transformer","channel":"CodeEmporium","url":"https://youtu.be/TQQlZhbC5ps","video_id":"TQQlZhbC5ps"},
        ],
        "probability": [
            {"title":"Statistics and Probability","channel":"Khan Academy","url":"https://youtu.be/uzkc-qNVoOk","video_id":"uzkc-qNVoOk"},
        ],
        "embeddings": [
            {"title":"Word Embeddings — Stanford NLP","channel":"Stanford / Chris Manning","url":"https://youtu.be/ERibwqs9p38","video_id":"ERibwqs9p38"},
        ],
    }
    key = concept.lower()
    for k, videos in CURATED.items():
        if k in key or key in k:
            return videos

    # Generic fallback
    return [{"title":f"{concept} explained","channel":"Search on YouTube","url":YT_NO_KEY_URL.format(urllib.parse.quote(concept)),"video_id":""}]


# ── Main agent ────────────────────────────────────────────────────────────────

async def run_scraper_agent(state: SessionState) -> SessionState:
    """
    For each unmastered node in the knowledge graph,
    fetches Wikipedia summary + YouTube videos.
    Stores resource data in user_profile["resources"].
    """
    graph = state.graph
    if not graph.nodes:
        state.agent_statuses["scraper"] = "done"
        return state

    unmastered = [n for n in graph.nodes if not n.mastered]

    # Fetch all concepts concurrently
    async def fetch_concept(node) -> tuple[str, dict]:
        concept = node.label.replace("\n", " ")
        wiki, yt = await asyncio.gather(
            _fetch_wikipedia(concept),
            _fetch_youtube(concept),
        )
        return concept, {"wikipedia": wiki, "youtube": yt}

    results = await asyncio.gather(*[fetch_concept(n) for n in unmastered])

    resources: dict[str, dict] = {}
    for concept, data in results:
        resources[concept] = data

    state.user_profile["resources"] = resources
    state.agent_statuses["scraper"] = "done"
    return state
