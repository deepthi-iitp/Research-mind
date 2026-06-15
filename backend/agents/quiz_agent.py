"""
ResearchMind — Quiz Agent
Generates personalised confidence-check questions based on the papers and
the student's knowledge profile.  Also grades submitted answers.
"""
from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from core.clients import get_llm
from core.models import QuizQuestion, QuizResult, SessionState
from core.config import get_settings

log = logging.getLogger(__name__)
cfg = get_settings()

GENERATE_SYSTEM = """You are ResearchMind's Quiz Agent.

Generate exactly {n} multiple-choice questions to test whether a student
understands the prerequisites and core concepts needed for: "{topic}".

Calibrate difficulty to level: {level}  (beginner / intermediate / advanced).

Return ONLY a JSON array:
[
  {{
    "q":       "Question text?",
    "opts":    ["Option A", "Option B", "Option C", "Option D"],
    "correct": 0,   // 0-indexed
    "explain": "One-sentence explanation of the correct answer."
  }},
  ...
]

Rules:
- Mix conceptual understanding, applied reasoning, and "why" questions
- Wrong options must be plausible (no obviously silly distractors)
- Questions should be self-contained — no "according to the paper" phrasing
- Return ONLY the JSON array, no markdown, no preamble
"""

GRADE_SYSTEM = """You are ResearchMind's Quiz Grader.
Given a list of questions and the student's chosen option indices, identify
which concepts the student is weak on and suggest targeted resources.

Return ONLY JSON:
{{
  "weak_concepts": ["concept1", "concept2"],
  "strong_concepts": ["concept3"],
  "advice": "1-2 sentences of personalised study advice"
}}
"""

FALLBACK_QUESTIONS = [
    QuizQuestion(
        q="What is the core mechanism that allows Transformers to capture long-range dependencies without recurrence?",
        opts=["Convolutional feature maps","Self-attention with positional encodings","Gated recurrent units","Bidirectional LSTM layers"],
        correct=1,
        explain="Self-attention relates all positions simultaneously, removing the sequential bottleneck of RNNs.",
    ),
    QuizQuestion(
        q="Why is dot-product attention scaled by 1/√d_k before the softmax?",
        opts=["To normalise outputs to [0,1]","To prevent exploding gradients","To avoid tiny softmax gradients in high dimensions","To reduce GPU memory usage"],
        correct=2,
        explain="Large d_k causes dot products to grow large, pushing softmax into saturated low-gradient regions.",
    ),
    QuizQuestion(
        q="What does multi-head attention achieve over single-head attention?",
        opts=["Faster training","Attending to multiple representation subspaces simultaneously","A larger context window","Fewer total parameters"],
        correct=1,
        explain="Multiple heads allow joint attention to different representation subspaces at different positions.",
    ),
    QuizQuestion(
        q="How does BERT's pre-training differ from GPT's?",
        opts=["BERT uses causal LM; GPT uses masked LM","BERT uses bidirectional MLM + NSP; GPT uses causal left-to-right LM","Both use identical objectives","BERT trains on code"],
        correct=1,
        explain="BERT masks random tokens bidirectionally (MLM) and also predicts sentence order (NSP). GPT predicts the next token causally.",
    ),
    QuizQuestion(
        q="What are positional encodings used for in the original Transformer?",
        opts=["Replacing word embeddings","Injecting token order into a permutation-invariant architecture","Computing cross-attention","Scaling feed-forward outputs"],
        correct=1,
        explain="Self-attention is permutation-invariant. Sinusoidal positional encodings add order information to token embeddings.",
    ),
]


async def run_quiz_generator(state: SessionState, n_questions: int = 5) -> SessionState:
    """
    Generates quiz questions tailored to the topic and student level.
    Falls back to FALLBACK_QUESTIONS if LLM fails.
    """
    topic  = state.topic or state.query
    level  = state.user_profile.get("level", "intermediate")

    llm = get_llm(fast=True)
    messages = [
        SystemMessage(content=GENERATE_SYSTEM.format(n=n_questions, topic=topic, level=level)),
        HumanMessage(content=f"Generate {n_questions} quiz questions for topic: {topic}"),
    ]

    try:
        resp = await llm.ainvoke(messages)
        raw  = resp.content.strip()
        qs   = json.loads(raw)
        state.quiz_questions = [QuizQuestion(**q) for q in qs[:n_questions]]
    except Exception as e:
        log.warning("Quiz generator failed: %s — using fallback questions", e)
        state.quiz_questions = FALLBACK_QUESTIONS[:n_questions]

    state.agent_statuses["quiz"] = "done"
    return state


def grade_quiz(questions: list[QuizQuestion], answers: list[int]) -> QuizResult:
    """
    Grades a submitted quiz.  Returns QuizResult with score_pct and passed flag.
    """
    correct_list = [
        a == q.correct
        for q, a in zip(questions, answers)
    ]
    score = round(sum(correct_list) / max(len(correct_list), 1) * 100)
    return QuizResult(
        score_pct=score,
        passed=score >= cfg.pass_threshold,
        answers=correct_list,
    )


async def analyse_weak_spots(
    questions: list[QuizQuestion],
    answers: list[int],
    state: SessionState,
) -> dict:
    """
    After grading, asks GPT to identify weak concepts and give advice.
    """
    wrong_qs = [
        {"question": q.q, "correct_answer": q.opts[q.correct], "student_answer": q.opts[a], "explanation": q.explain}
        for q, a in zip(questions, answers) if a != q.correct
    ]
    if not wrong_qs:
        return {"weak_concepts": [], "strong_concepts": [], "advice": "Excellent work — no weak spots detected!"}

    llm = get_llm(fast=True)
    messages = [
        SystemMessage(content=GRADE_SYSTEM),
        HumanMessage(content=json.dumps(wrong_qs, indent=2)),
    ]
    try:
        resp = await llm.ainvoke(messages)
        return json.loads(resp.content.strip())
    except Exception:
        return {"weak_concepts": [], "strong_concepts": [], "advice": "Review the incorrect questions above before proceeding."}
