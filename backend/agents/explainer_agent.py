"""
ResearchMind — Explainer Agent
Explains a paper section-by-section using RAG over the uploaded PDF.
Falls back to GPT world-knowledge if no PDF is available.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import AsyncIterator

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter

from core.cache    import get_explain_cache, set_explain_cache
from core.clients  import get_llm, get_vectorstore, get_embeddings
from core.config   import get_settings
from core.database import upsert_record
from core.models   import SessionState

log = logging.getLogger(__name__)
cfg = get_settings()

# ── Section metadata ──────────────────────────────────────────────────────────

SECTION_LABELS = {
    "abstract":   "Abstract",
    "intro":      "Introduction",
    "arch":       "Architecture",
    "attention":  "Attention Mechanism",
    "training":   "Training Setup",
    "results":    "Results & Evaluation",
    "conclusion": "Conclusion & Future Work",
}

# ── Base system prompt headers ─────────────────────────────────────────────────

SYSTEM_HEADER_EXPERT = """\
You are a senior AI research assistant with encyclopedic ML/NLP knowledge.

Explaining the **{section_label}** section of:
> **{title}**
> {authors} ({year})

**Reader:** PhD student or active researcher — strong mathematical fluency, familiar with transformers and the recent literature.
**Mastered concepts** (connect to these; mark direct links with ✦): {mastered}

CRITICAL INSTRUCTIONS:
1. Base EVERY claim on the retrieved paper excerpts in the user message. Do not generate a generic explanation of what this section type "usually contains" — explain what THIS paper specifically says.
2. When the excerpts directly support a point, quote briefly using > blockquote format.
3. Add world-knowledge context only to explain something mentioned in the paper — mark it: *(Context: ...)*.
4. Use bullet points and numbered lists wherever they improve clarity over dense prose.
5. Use LaTeX for all math: inline $...$, display $$$...$$$.

{section_structure}
"""

SYSTEM_HEADER_BEGINNER = """\
You are a patient, encouraging research mentor helping a student read a landmark paper for the first time.

Explaining the **{section_label}** section of:
> **{title}**
> {authors} ({year})

**Reader:** Basic calculus and probability; limited ML exposure. Make them feel capable, not overwhelmed.
**Mastered concepts** (connect to these; mark links with ✦): {mastered}

CRITICAL INSTRUCTIONS:
1. Build the explanation directly from the retrieved paper excerpts — explain what THIS paper says, not the topic in general.
2. Use world knowledge only to explain and contextualize what the paper says — never to invent content not present in the excerpts.
3. Use bullet points and numbered lists wherever they improve clarity.
4. Define every technical term the moment it first appears.
5. Use real-world analogies freely (cooking, GPS, sport, postal systems, etc.).

{section_structure}
"""

# ── Section-specific structures: Expert ───────────────────────────────────────

SECTION_STRUCTURES_EXPERT = {
    "abstract": """\
Structure your response with these exact headers:

## Problem & Research Gap
- What specific limitation in prior work does this paper address?
- What would break or remain unsolved without this contribution?
- Extract the exact problem statement from the abstract.

## Proposed Approach & Core Insight
- The central technical idea in one precise paragraph.
- What is the key insight that makes this work? Describe the mechanism — avoid vague language like "novel" or "improved."
- What non-obvious design decision drives the approach?

## Specific Contributions
- Bullet-list each contribution (algorithmic, architectural, empirical, theoretical).
- Distinguish what is genuinely novel versus an incremental extension.

## Key Empirical Results
- Which benchmarks? Which metrics? What numbers vs. prior best?
- How large and significant are the improvements?
- Any surprising or counter-intuitive findings?

## Research Significance
- What does this enable that wasn't tractable before?
- What broader research directions does this open?

Target **600–750 words**. Every claim must reference the paper's actual content.""",

    "intro": """\
Structure your response with these exact headers:

## Problem Motivation & Scope
- What practical or scientific problem drives this work? Why does it matter?
- What real-world application or failure mode makes this urgent?
- How does the paper formally define the problem?

## Prior Work & Its Failures
- Name specific methods or systems that preceded this work.
- For each: what does it attempt, and what is its structural failure?
- What is the common limitation shared across all prior approaches?

## Core Hypothesis & Key Insight
- The paper's central thesis in one precise sentence.
- What key observation makes the proposed approach viable?
- Why wasn't this insight exploited before?

## Specific Contributions (Enumerated)
- Bullet-point list of exactly what this paper claims to deliver.
- Distinguish: theoretical claims vs. empirical claims vs. engineering contributions.

## Paper Roadmap & Scope Limits
- What does each subsequent section establish?
- Any important scope limitations (e.g., "limited to English," "assumes supervised setting")?

Target **700–900 words**. Situate this work precisely in the literature.""",

    "arch": """\
Structure your response with these exact headers:

## Architecture Overview
- End-to-end description: input → processing stages → output.
- The high-level design philosophy (why was this structure chosen?).
- What prior architectures does this build on or depart from?

## Component-by-Component Analysis
For each major module, create a sub-section:
- **Role**: What does this component compute?
- **Mechanism**: Describe the computation; include the key equation with all symbols defined.
- **Design Rationale**: Why this design over simpler alternatives? What breaks if removed?
- **Data Flow**: How does output feed into the next component?

## Architectural Innovations
- What is genuinely new compared to prior architectures? Be specific.
- What problem does each innovation address?

## Complexity & Scalability
- Time and space complexity (explain each factor).
- How does it scale with sequence length, model size, vocabulary?
- Any approximations or engineering tricks to make it tractable?

## Structural Comparison to Baselines
- How does this architecture differ structurally (not just in performance) from the main baselines?
- Which structural differences drive the performance gap?

Target **800–1000 words**. Include all key equations.""",

    "attention": """\
Structure your response with these exact headers:

## Formal Attention Definition
- State the exact computation: inputs Q, K, V; the output; the full equation.
- Define every symbol: tensor shapes, semantic meaning.
- Intuitive interpretation: what does "attention score" measure semantically?

## Scaled Dot-Product Attention: Step by Step
- Step 1: Linear projections of Q, K, V — why project?
- Step 2: Dot product QKᵀ — what does a high score mean?
- Step 3: Scale by 1/√dₖ — derive why this is necessary.
- Step 4: Softmax — what distribution does this produce?
- Step 5: Weighted sum with V — what does the output represent?

## Multi-Head Attention
- How are H independent heads computed in parallel?
- What is the dimensionality at each stage?
- What does each head theoretically learn to capture?
- Concatenation + projection: purpose and dimensions.

## Self-Attention vs. Cross-Attention
- What differs between these two uses of attention?
- Where in the architecture is each used and why?
- What masking is applied, where, and why?

## Position Encoding
- Why is explicit position encoding needed (attention is permutation-invariant)?
- What encoding scheme is used? Derive or describe the formula.
- Sinusoidal vs. learned: trade-offs.

## Computational Properties & Limits
- Time complexity: O(n²·d) — why quadratic in sequence length?
- Memory cost vs. RNNs.
- Any efficient attention variants used?

Target **750–950 words**. Include all LaTeX equations with symbols defined.""",

    "training": """\
Structure your response with these exact headers:

## Training Data & Preprocessing
- Dataset name(s), size, domain, language(s).
- Tokenization method and vocabulary size — what algorithm? What choices?
- Train/validation/test split sizes; any data augmentation.

## Objective Function
- Exact loss formulation with the full equation; every symbol defined.
- Why this objective? What mathematical property makes it appropriate?
- Any auxiliary losses or regularization terms?

## Optimization Configuration
- Optimizer name with all hyperparameters (lr, β₁, β₂, ε, weight decay).
- Learning rate schedule: warmup steps, peak value, decay function.
- Batch size, gradient accumulation, effective batch size.

## Regularization & Training Tricks
- Dropout: where applied and at what rate?
- Label smoothing, gradient clipping, layer normalization placement — purpose of each.
- Any other stabilization techniques?

## Compute & Scale
- Hardware (GPU/TPU model and count), training duration.
- Parameter count — how does it compare to baselines?
- Any multi-stage training or pre-training/fine-tuning distinctions?

## Sensitivity & Key Findings
- What hyperparameter choices were most sensitive?
- What training configuration changes made the biggest difference?
- Any failed attempts or convergence issues reported?

Target **650–800 words**. Report all hyperparameter values from the paper exactly.""",

    "results": """\
Structure your response with these exact headers:

## Evaluation Benchmarks
For each benchmark:
- Name + one-line description of what it measures.
- Why is it appropriate for evaluating this paper's claims?
- The metric used and what it captures.

## Main Results
Present as structured comparisons:
- **Task/Benchmark**: prior best score | this paper's score | improvement
- Which improvements are statistically significant (if reported)?
- Which result is most and least convincing?

## Ablation Studies
For each ablation:
- What component was removed or varied?
- Performance change and what it reveals.
- Rank components by importance based on ablation results.

## Qualitative Analysis
- Describe 1–2 concrete output examples from the paper.
- What patterns of success and failure emerge?
- What do the examples reveal that the quantitative numbers don't?

## Evaluation Caveats & Limitations
- Are comparisons controlled (same data, same compute)?
- What scenarios are the benchmarks NOT representative of?
- What limitations do the authors acknowledge in the evaluation?

Target **700–900 words**. Ground every number in the paper's actual tables and figures.""",

    "conclusion": """\
Structure your response with these exact headers:

## Contribution Summary (Retrospective)
- The 2–3 most important contributions with the full paper's evidence in mind.
- How well do the results support the claims made in the introduction?
- Which result was most convincing? Which was weakest?

## Key Insights & Takeaways
- 4–5 specific findings — not "it's better" but the actual insights gained.
- What do we now understand that we didn't before?
- What is the most surprising or counter-intuitive result?

## Acknowledged Limitations
- List exactly what limitations the authors state (quote directly where possible).
- For each: how significant is this in practice? When would it matter?
- Any important limitations the authors didn't mention but should have?

## Future Directions
- Specific future work the authors suggest.
- Which directions are most tractable and impactful near-term?
- What open problems does this paper leave unresolved?

## Field Impact & Legacy
- How does this work change what researchers and practitioners do?
- What downstream work has this enabled?
- What is the one thing this paper will be cited for in ten years?

Target **550–700 words**. Be analytically honest — don't simply echo the authors' optimism.""",
}

# ── Section-specific structures: Beginner ─────────────────────────────────────

SECTION_STRUCTURES_BEGINNER = {
    "abstract": """\
Structure your response with these exact headers:

## What Problem Are They Solving?
In plain English, explain the problem this paper addresses. Use a real-world analogy anyone would recognise (autocomplete, spam filters, translation, search engines, etc.). Why is this problem important and hard?

## The Big Idea
One sentence capturing the paper's main contribution. Follow with "In other words…" to reinforce it. Then: why is this approach clever?

## What They Did — Step by Step
- **Step 1 — Starting point**: What existed before? What was the limitation?
- **Step 2 — Key insight**: What clever observation drives the new approach?
- **Step 3 — What they built**: What did they actually design or create?
- **Step 4 — How they tested it**: How did they measure success?
- **Step 5 — What they found**: What were the results?

## Did It Work? The Key Numbers
Report headline results — but translate them into meaning:
- "BLEU score improved by 2 points, meaning translations are now noticeably more fluent"
- "Accuracy rose from 87% to 92%, cutting errors nearly in half"

## Why This Matters in Real Life
A concrete, relatable scenario: "Before this paper, a machine couldn't… Now it can…" Make it tangible.

Target **450–550 words**. Friendly tone. Define every technical term immediately.""",

    "intro": """\
Structure your response with these exact headers:

## The Problem in Plain English
What real-world challenge does this paper tackle? Give one concrete everyday example. Why is this hard to solve, and why hadn't anyone fully solved it before?

## What People Tried Before (And Why It Wasn't Enough)
For each prior approach:
- **What it did**: [brief plain-English description]
- **Where it failed**: [concrete example — e.g., "it couldn't tell that 'it' in 'The trophy didn't fit because it was too big' refers to the suitcase, not the trophy"]

Then: what do all these failed approaches have in common? What is the root problem?

## The Clever Insight (The "Aha!" Moment)
What non-obvious idea does this paper build on? State it as an analogy first, then more precisely. Why hadn't people tried this before?

## What This Paper Promises
- **Promise 1**: [contribution and why it matters in practice]
- **Promise 2**: [contribution and why it matters]
- **Promise 3**: [contribution and why it matters]

## How the Paper Is Organized
A short roadmap: "Section 2 covers X (where you'll learn about Y)…" so the reader knows what's coming.

Target **450–550 words**. Never use jargon without immediately defining it.""",

    "arch": """\
Structure your response with these exact headers:

## The Big Picture: What Are We Building?
Describe the architecture like a familiar system: what goes in, what comes out, and what happens in between. Use a physical analogy (assembly line, postal system, kitchen, etc.) to make the structure concrete.

## The Main Parts (What Each Piece Does)
For each major component:
- **[Component Name]**: One sentence on its job.
  - How it works in simple terms (no jargon, or define immediately).
  - Why it's needed: what would break without it?
  - Mini-analogy if helpful.

## Data Journey: One Example End-to-End
Pick a concrete input (e.g., the sentence "The cat sat on the mat") and trace what happens to it step by step through the full architecture. Make each transformation tangible.

## The Innovations: What's New Here
- **Old way**: How did previous architectures handle this?
- **New way**: How does this architecture handle it differently?
- **Why it's better**: Explain the improvement in plain terms.

## One Analogy to Rule Them All
Map the full architecture onto something familiar. Be specific — name every part.

Target **500–600 words**. Concrete examples in every section.""",

    "attention": """\
Structure your response with these exact headers:

## What Does "Attention" Mean? (Start with the Everyday Concept)
Begin with how humans pay attention — we focus on relevant parts and ignore the rest. Build from this to how a neural network can do the same. Use the analogy: "It's like a search engine built inside the model…"

## The Problem Attention Solves
- What did older models (RNNs) struggle with? Give a concrete example:
  - "The trophy doesn't fit in the suitcase because **it** is too big" — which word does "it" refer to?
- Why is this hard for a step-by-step sequence model?

## How Attention Works — Step by Step
- **Step 1 — Ask a Question (Query)**: Each word asks "what information am I looking for?"
- **Step 2 — Check Relevance (Keys)**: Every other word says "here is what I contain"
- **Step 3 — Score & Weight**: How relevant is each word? High score = pay more attention
- **Step 4 — Combine (Values)**: Blend information from all relevant words proportionally
- **Step 5 — Multiple Heads**: Like having several people read the sentence, each looking for something different

## The Key Equation, Explained Symbol by Symbol

$$\\text{Attention}(Q, K, V) = \\text{softmax}\\!\\left(\\frac{QK^\\top}{\\sqrt{d_k}}\\right)V$$

| Symbol | What it means | Think of it as |
|--------|---------------|----------------|
| Q | Query matrix | "What am I looking for?" |
| K | Key matrix | "What do I contain?" |
| V | Value matrix | "What information do I carry?" |
| √dₖ | Scaling factor | Prevents scores from exploding |
| softmax | Normalizing function | Converts scores to percentages summing to 100% |

## A Concrete Example in Action
For the sentence: "The bank by the **river** was steep."
When the model reads "bank" — which nearby words does it attend to most, and why does that help it pick the right meaning?

## Why This Changed Everything
- Bullet points: 2–3 specific things that became possible after attention that weren't before.
- What tasks improved most and why?

Target **500–620 words**. Build from intuition to formalism. Every symbol defined before use.""",

    "training": """\
Structure your response with these exact headers:

## What Data Did They Train On?
- Name the dataset(s) and describe them in plain terms: how big? what kind of text?
- Tokenization explained simply: "Instead of whole words, the model works with pieces — 'running' might be split into 'run' + '##ning'"
- Why this data? What makes it suitable for the task?

## What Was the Model's "Job" During Training?
Explain the training objective like a game:
- **The task**: e.g., "Given these words, predict the next one"
- **Measuring mistakes (the loss)**: "When the model guesses wrong, how wrong was it?"
- **Concrete example**: Input: "The Eiffel Tower is in ___" → model predicts "Paris" → correct = small loss; wrong = large loss

## How the Model Got Better: The Learning Process
- **Optimizer**: Like a GPS adjusting your route — explain gradient descent in simple terms
- **Learning rate**: "How big a step does the model take when adjusting?" — why start large and shrink?
- **Batch training**: "Rather than learning from one example at a time, it learns from 256 at once" — why?

## Preventing Bad Habits (Regularization)
- **Dropout**: "Randomly switching off parts of the network during training — like practising sport with a handicap, it forces the model not to rely on any single path"
- Other techniques: explain each with a brief analogy

## Scale: How Big and How Long?
- Hardware and training time in relatable terms
- Parameter count put in perspective: "175 million dials to adjust"

## What Was Tricky / What Didn't Work First
- Any challenges or surprises during training
- What changed from first attempts to the final setup?

Target **450–550 words**. Keep analogies concrete.""",

    "results": """\
Structure your response with these exact headers:

## What Were They Testing? (The Benchmarks Explained)
For each benchmark:
- **Name**: [What is it?]
- **Task**: [What does the model have to do?]
- **Metric**: [How is success measured? Translate: "BLEU of 40 is roughly a B+ grade for translation quality"]
- **Why this benchmark**: [What does doing well here prove?]

## The Headline Results: Did It Work?
Present key findings as a clear before/after:
- **Task A**: Old best = X, This paper = Y → improvement means [concrete meaning]
- **Task B**: Old best = X, This paper = Y → improvement means [concrete meaning]
- Which improvement was biggest? Most surprising?

## What Got Removed and What Happened? (Ablations)
The authors "removed pieces one by one" to understand what matters:
- "When they removed [X], performance dropped by [Y]% — this tells us [Z is crucial]"
- "When they removed [A], almost nothing changed — meaning [A isn't that important]"
- **Most important piece**: based on ablations, which component matters most?

## Seeing It Work (and Fail): Examples
- Describe 1–2 examples where the model did something impressive.
- Describe 1 example where it still struggled.
- Pattern: what types of examples is it best/worst at?

## Honest Assessment: What's Still Missing?
- What did the model NOT do well?
- What would you want tested that wasn't tested?
- What would make you more or less confident in these results?

Target **500–600 words**. Translate every number into intuitive meaning.""",

    "conclusion": """\
Structure your response with these exact headers:

## What Did This Paper Actually Accomplish?
For each of the 2–3 main contributions:
- **Claim**: What did the paper promise?
- **Evidence**: What result supports this?
- **Verdict**: How convincingly was it demonstrated?

## The 3 Things Worth Remembering
If explaining this paper to someone in an elevator, what 3 things would you say? Each must be a concrete insight with a real example — not just "it's better."

## What Still Doesn't Work (The Honest Part)
For each limitation the authors acknowledge:
- **The limitation**: [plain English]
- **Why it matters**: [concrete example — e.g., "the model can only process 512 tokens at once, so you couldn't use it on a full book"]

## What's Next? (Future Work)
- Which future directions seem most exciting and why?
- If you were a researcher, what would you work on next based on this paper?
- What open question from this paper are you most curious about?

## The Lasting Legacy: One Big Idea
The ONE insight or technique from this paper that will still be cited and used in ten years. Explain why this idea is timeless.

Target **400–500 words**. Be honest about limitations. End with genuine curiosity.""",
}

QA_SYSTEM = """You are ResearchMind's Q&A agent — a knowledgeable, direct research companion.

**Paper:** {title}
**Authors:** {authors} ({year})
**Section in focus:** {section}
**Conversation mode:** {mode}

{mode_instruction}

**Reader level:** {level}
**Context from paper (RAG):** {context}

Keep answers focused, cite specific claims from the paper when possible, and flag when you are drawing on world knowledge versus paper content.
"""

MODE_INSTRUCTIONS = {
    "standard": (
        "Answer precisely and completely. Cite specific sections, equations, or claims from the paper when relevant. "
        "If the question reveals a misconception, correct it kindly but directly. "
        "Calibrate depth to the reader's level — give a research-grade answer for an expert, an intuitive one for a beginner."
    ),
    "socratic": (
        "NEVER give direct answers. Your role is to guide the student toward understanding through questioning.\n"
        "Ask 2–3 targeted probing questions that nudge them toward the answer. "
        "After they respond, confirm what they got right and gently correct any gaps. "
        "If they are stuck after two rounds, reveal one more piece of the puzzle."
    ),
    "devil": (
        "Take a rigorous adversarial stance. Challenge every assumption in the question and in the paper. "
        "Point out methodological weaknesses, alternative explanations, conflicting evidence from the literature, "
        "and demand that the student defend their reasoning with stronger evidence. "
        "Be intellectually honest — if a claim is well-supported, acknowledge it before pushing further."
    ),
}


# ── Core streaming generator ──────────────────────────────────────────────────

async def explain_section_stream(
    session: SessionState,
    paper_id: str,
    section: str,
    level_override: str = "",
) -> AsyncIterator[str]:
    """Async generator that streams explanation tokens chunk by chunk."""
    paper = next((p for p in session.papers if p.id == paper_id), None)
    if paper is None and session.papers:
        paper = session.papers[0]

    title         = paper.title   if paper else session.query
    authors       = paper.authors if paper else "Unknown"
    year          = paper.year    if paper else 2024
    level         = level_override or session.user_profile.get("level", "expert")
    mastered      = (
        ", ".join(session.user_profile.get("mastered_concepts", []))
        or "general mathematics, basic ML fundamentals"
    )
    section_label = SECTION_LABELS.get(section, section.replace("_", " ").title())

    # RAG: more specific query to get relevant chunks for this section
    rag_context = ""
    try:
        vs = get_vectorstore(session.session_id)
        docs = vs.similarity_search(
            f"{section_label} {title}: methods, equations, results",
            k=cfg.top_k,
            filter={"session_id": session.session_id},
        )
        rag_context = "\n\n---\n\n".join(
            f"[Page {d.metadata.get('page', '?')}]\n{d.page_content}"
            for d in docs
        )
    except Exception:
        pass

    # Select section-specific structure and header template
    if level == "expert":
        structure = SECTION_STRUCTURES_EXPERT.get(section, SECTION_STRUCTURES_EXPERT["abstract"])
        header    = SYSTEM_HEADER_EXPERT
    else:
        structure = SECTION_STRUCTURES_BEGINNER.get(section, SECTION_STRUCTURES_BEGINNER["abstract"])
        header    = SYSTEM_HEADER_BEGINNER

    system = header.format(
        section_label=section_label,
        title=title,
        authors=authors,
        year=year,
        mastered=mastered,
        section_structure=structure,
    )

    if rag_context:
        user_content = (
            f"Explain the **{section_label}** section of this paper.\n\n"
            f"Use the excerpts below as your PRIMARY source — base every point on what "
            f"the paper actually says. Quote specific passages where they support your explanation.\n\n"
            f"### Retrieved excerpts from the paper:\n\n{rag_context}"
        )
    else:
        # No PDF — check cache before hitting the LLM
        cached = get_explain_cache(title, section, level)
        if cached:
            log.info("Explain cache hit: title=%r section=%r level=%r", title, section, level)
            yield cached
            return

        user_content = (
            f"Explain the **{section_label}** section thoroughly.\n\n"
            f"*(No PDF uploaded — draw on world knowledge about this paper/topic "
            f"but flag any inferences with [Inferred: ...])*"
        )

    llm = get_llm()
    messages = [SystemMessage(content=system), HumanMessage(content=user_content)]
    collected: list[str] = []
    async for chunk in llm.astream(messages):
        if chunk.content:
            collected.append(chunk.content)
            yield chunk.content

    # Persist world-knowledge explanations (not PDF-based ones)
    if not rag_context and collected:
        full_text = "".join(collected)
        set_explain_cache(title, section, level, full_text)

        # Save to SQLite so the paper appears in the front-page history
        import hashlib as _hashlib
        cache_key = (
            "explain:"
            + _hashlib.md5(
                f"{title.lower().strip()[:80]}:{section}:{level}".encode()
            ).hexdigest()
        )
        summary = full_text[:200].rstrip() + ("…" if len(full_text) > 200 else "")
        upsert_record({
            "id":           cache_key,
            "title":        title,
            "authors":      authors,
            "year":         year,
            "abstract":     paper.abstract if paper else "",
            "arxiv_id":     paper.arxiv_id if paper else "",
            "citations":    paper.citations if paper else 0,
            "url":          paper.url if paper else "",
            "tag":          paper.tag if paper else "",
            "mode":         "single_paper",
            "topic":        title,
            "reader_level": level,
            "summary":      summary,
            "tags":         [level] if level else [],
            "explanation":  full_text if section == "full" else "",
        })


# ── Non-streaming wrapper (used where streaming is not needed) ────────────────

async def explain_section(
    session: SessionState,
    paper_id: str,
    section: str,
    level_override: str = "",
) -> str:
    result = ""
    async for chunk in explain_section_stream(session, paper_id, section, level_override):
        result += chunk
    return result


# ── Q&A ───────────────────────────────────────────────────────────────────────

async def answer_question(
    session: SessionState,
    paper_id: str,
    section: str,
    question: str,
    mode: str = "standard",
    level_override: str = "",
) -> str:
    """Answers a follow-up question about a paper section."""
    paper = next((p for p in session.papers if p.id == paper_id), None)
    if paper is None and session.papers:
        paper = session.papers[0]

    title   = paper.title   if paper else session.query
    authors = paper.authors if paper else "Unknown"
    year    = paper.year    if paper else 2024
    level   = level_override or session.user_profile.get("level", "expert")

    rag_context = ""
    try:
        vs = get_vectorstore(session.session_id)
        docs = vs.similarity_search(question, k=cfg.top_k, filter={"session_id": session.session_id})
        rag_context = "\n\n".join(d.page_content for d in docs)
    except Exception:
        pass

    system = QA_SYSTEM.format(
        title=title, authors=authors, year=year, section=section,
        mode=mode,
        mode_instruction=MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS["standard"]),
        level=level,
        context=rag_context or "(no PDF — answering from world knowledge)",
    )

    llm = get_llm()
    history = session.chat_history[-8:]
    messages = (
        [SystemMessage(content=system)]
        + [
            HumanMessage(content=m["content"]) if m["role"] == "user"
            else SystemMessage(content=m["content"])
            for m in history
        ]
        + [HumanMessage(content=question)]
    )
    resp = await llm.ainvoke(messages)
    return resp.content


# ── PDF Ingestion ─────────────────────────────────────────────────────────────

async def ingest_pdf(session_id: str, pdf_path: Path) -> int:
    """Parses a PDF, chunks it, embeds it, and stores in Qdrant."""
    import pdfplumber

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=cfg.chunk_size,
        chunk_overlap=cfg.chunk_overlap,
        separators=["\n\n", "\n", ". ", " "],
    )

    texts: list[str] = []
    metadatas: list[dict] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if not text.strip():
                continue
            chunks = splitter.split_text(text)
            for chunk in chunks:
                texts.append(chunk)
                metadatas.append({
                    "session_id": session_id,
                    "page":       page_num + 1,
                    "source":     pdf_path.name,
                })

    if not texts:
        return 0

    vs = get_vectorstore(session_id)
    vs.add_texts(texts, metadatas=metadatas)
    return len(texts)
