"""
ResearchMind — Quiz Agent
Generates personalised confidence-check questions based on the papers and
the student's knowledge profile.  Also grades submitted answers.
"""
from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from core.llm_json import parse_llm_json
from core.clients import get_llm
from core.models import QuizQuestion, QuizResult, SessionState
from core.config import get_settings

log = logging.getLogger(__name__)
cfg = get_settings()

GENERATE_SYSTEM = """You are ResearchMind's Quiz Agent.

Generate exactly {n} multiple-choice questions to test whether a student
understands the prerequisites and core concepts needed for: "{topic}".

Calibrate difficulty to level: {level}  (beginner / intermediate / advanced).
{focus_block}
Return ONLY a JSON array:
[
  {{
    "q":       "Question text?",
    "opts":    ["Option A", "Option B", "Option C", "Option D"],
    "correct": 0
    "explain": "One-sentence explanation of the correct answer."
  }},
  ...
]

Rules:
- Mix conceptual understanding, applied reasoning, and "why" questions
- Wrong options must be plausible (no obviously silly distractors)
- Questions should be self-contained — no "according to the paper" phrasing
- "correct" is the 0-based index of the right option
- Return ONLY the JSON array, no markdown, no comments, no preamble
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


LEVELS = ["beginner", "intermediate", "advanced"]


def next_level(current: str, score_pct: int) -> str:
    """Adaptive difficulty: step up after a strong round, step down after a weak one."""
    i = LEVELS.index(current) if current in LEVELS else 1
    if score_pct >= 80:
        i = min(i + 1, len(LEVELS) - 1)
    elif score_pct < 50:
        i = max(i - 1, 0)
    return LEVELS[i]


async def run_quiz_generator(
    state: SessionState,
    n_questions: int = 5,
    level: str | None = None,
    focus_concepts: list[str] | None = None,
    avoid_questions: list[str] | None = None,
) -> SessionState:
    """
    Generates quiz questions tailored to the topic and student level.
    In adaptive rounds, `focus_concepts` (weak spots from the last round) and
    `avoid_questions` (already asked) steer the next set.
    Falls back to FALLBACK_QUESTIONS if LLM fails.
    """
    topic = state.topic or state.query
    level = level or state.user_profile.get("quiz_level") or state.user_profile.get("level", "intermediate")

    focus_block = ""
    if focus_concepts:
        focus_block += (
            f"\nThe student just got these concepts WRONG: {', '.join(focus_concepts)}.\n"
            f"At least {min(3, n_questions)} questions must test these concepts from a new angle.\n"
        )
    if avoid_questions:
        focus_block += "Do NOT repeat or rephrase these earlier questions:\n" + "\n".join(f"- {q}" for q in avoid_questions) + "\n"

    messages = [
        SystemMessage(content=GENERATE_SYSTEM.format(n=n_questions, topic=topic, level=level, focus_block=focus_block)),
        HumanMessage(content=f"Generate {n_questions} quiz questions for topic: {topic}"),
    ]

    # Try the fast model, then retry once with the main model before falling back.
    for attempt, fast in enumerate((True, False), start=1):
        try:
            resp = await get_llm(fast=fast).ainvoke(messages)
            qs   = parse_llm_json(resp.content, expect=list)
            questions = [QuizQuestion(**q) for q in qs[:n_questions]
                         if isinstance(q, dict) and 0 <= int(q.get("correct", -1)) < len(q.get("opts", []))]
            if not questions:
                raise ValueError("no valid questions in reply")
            state.quiz_questions = questions
            break
        except Exception as e:
            log.warning("Quiz generator attempt %d failed: %s", attempt, e)
    else:
        if not avoid_questions:
            log.warning("Quiz generator using fallback questions for topic=%r", topic)
            state.quiz_questions = FALLBACK_QUESTIONS[:n_questions]

    state.agent_statuses["quiz"] = "done"
    return state


async def adapt_quiz(state: SessionState, result: QuizResult, weak_spots: dict) -> dict:
    """
    Builds the next quiz round from the last one:
      • difficulty moves up/down based on the score
      • questions focus on the concepts the student got wrong
      • questions already asked are not repeated
    """
    current = state.user_profile.get("quiz_level") or state.user_profile.get("level", "intermediate")
    new_level = next_level(current, result.score_pct)
    focus = (weak_spots or {}).get("weak_concepts") or []
    asked = [q.q for q in state.quiz_questions]

    history = state.user_profile.setdefault("quiz_history", [])
    history.append({"round": len(history) + 1, "level": current, "score_pct": result.score_pct, "weak": focus})

    previous = list(state.quiz_questions)
    await run_quiz_generator(state, level=new_level, focus_concepts=focus, avoid_questions=asked)
    if state.quiz_questions == previous:          # generation failed — keep the old round
        return {"next_questions": [], "next_level": current, "focus_concepts": focus}

    state.user_profile["quiz_level"] = new_level
    return {
        "next_questions": [q.model_dump() for q in state.quiz_questions],
        "next_level":     new_level,
        "focus_concepts": focus,
    }


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
        return parse_llm_json(resp.content, expect=dict)
    except Exception:
        return {"weak_concepts": [], "strong_concepts": [], "advice": "Review the incorrect questions above before proceeding."}
