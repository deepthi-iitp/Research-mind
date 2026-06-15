"""
ResearchMind — shared data models
Used by agents, API routes, and the frontend contract.
"""
from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
import uuid


# ── Enums ─────────────────────────────────────────────────────────────────────

class Mode(str, Enum):
    SINGLE_PAPER = "single_paper"
    TOPIC_MASTERY = "topic_mastery"


class AgentStatus(str, Enum):
    PENDING  = "pending"
    RUNNING  = "running"
    DONE     = "done"
    FAILED   = "failed"


class ChatMode(str, Enum):
    STANDARD = "standard"
    SOCRATIC  = "socratic"
    DEVIL     = "devil"


# ── Paper ────────────────────────────────────────────────────────────────────

class Paper(BaseModel):
    id:        str   = Field(default_factory=lambda: str(uuid.uuid4()))
    title:     str
    authors:   str
    year:      int
    abstract:  str   = ""
    arxiv_id:  str   = ""
    doi:       str   = ""
    citations: int   = 0
    url:       str   = ""
    tag:       str   = ""          # Foundational / Essential / Milestone / Extension
    pdf_path:  str   = ""
    order:     int   = 0           # position in reading sequence


# ── Knowledge graph ───────────────────────────────────────────────────────────

class GraphNode(BaseModel):
    id:       int
    label:    str
    mastered: bool  = False
    edges:    list[int] = []       # indices of prerequisite nodes
    rx:       float = 0.5          # relative X position 0-1
    ry:       float = 0.5          # relative Y position 0-1
    r:        int   = 20           # node radius px


class KnowledgeGraph(BaseModel):
    nodes: list[GraphNode] = []


# ── Quiz ─────────────────────────────────────────────────────────────────────

class QuizQuestion(BaseModel):
    q:       str
    opts:    list[str]
    correct: int
    explain: str = ""


class QuizResult(BaseModel):
    score_pct: int
    passed:    bool
    answers:   list[bool] = []


# ── Session state ─────────────────────────────────────────────────────────────

class SessionState(BaseModel):
    session_id:      str = Field(default_factory=lambda: str(uuid.uuid4()))
    mode:            Mode = Mode.TOPIC_MASTERY
    query:           str = ""
    topic:           str = ""
    overall_pct:     int = 0
    papers:          list[Paper]        = []
    graph:           KnowledgeGraph     = Field(default_factory=KnowledgeGraph)
    quiz_questions:  list[QuizQuestion] = []
    quiz_result:     QuizResult | None  = None
    diagnostic_ans:  list[int]          = []
    agent_statuses:  dict[str, AgentStatus] = {}
    user_profile:    dict[str, Any]         = {}
    chat_history:    list[dict]             = []
    unlocked_sections: list[str]            = ["abstract", "intro"]
    section_explanations: dict[str, dict[str, str]] = {}   # paper_id → {section → text}


# ── API request / response models ─────────────────────────────────────────────

class StartSessionRequest(BaseModel):
    mode:  Mode
    query: str


class StartSessionResponse(BaseModel):
    session_id: str


class ChatRequest(BaseModel):
    session_id: str
    message:    str
    chat_mode:  ChatMode = ChatMode.STANDARD
    context:    str = ""


class ExplainSectionRequest(BaseModel):
    session_id:     str
    paper_id:       str
    section:        str
    level_override: str = ""   # "beginner" | "expert" | "" (uses session default)


class QuizSubmitRequest(BaseModel):
    session_id: str
    answers:    list[int]


class DiagnosticRequest(BaseModel):
    session_id: str
    answers:    list[int]
    topic:      str


class AgentStatusUpdate(BaseModel):
    agent_id:  str
    status:    AgentStatus
    message:   str = ""
    data:      dict = {}
