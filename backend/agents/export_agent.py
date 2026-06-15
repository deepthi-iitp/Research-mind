"""
ResearchMind — PDF Export Agent v3
Clean white-background PDF with:
  • Professional light colour scheme (readable on paper / screen)
  • Cover page with progress bar
  • Clickable Table of Contents (two-pass multiBuild)
  • PDF bookmarks / outline (h1 → h2 → h3)
  • Page numbers + thin header rule on every page after cover
  • Numbered section hierarchy with consistent typography
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate, Frame, HRFlowable, KeepTogether,
    NextPageTemplate, PageBreak, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

from core.config import get_settings
from core.models import SessionState

log = logging.getLogger(__name__)
cfg = get_settings()

W, H  = A4
LM = RM = 2.2 * cm
TM = BM = 2.0 * cm

# ── Light colour palette (white-background PDF) ───────────────────────────────
C_BODY    = colors.HexColor("#0f172a")   # near-black body text
C_NAVY    = colors.HexColor("#1e3a5f")   # deep navy — H1, table headers, cover
C_BLUE    = colors.HexColor("#2563eb")   # vivid blue — H2, links, accents
C_VIOLET  = colors.HexColor("#6d28d9")   # violet — H3, quiz section
C_EMERALD = colors.HexColor("#059669")   # emerald — tags, pass
C_AMBER   = colors.HexColor("#b45309")   # amber — reading sequence
C_ROSE    = colors.HexColor("#dc2626")   # red — fail
C_MUTED   = colors.HexColor("#64748b")   # slate — captions, metadata
C_RULE    = colors.HexColor("#e2e8f0")   # light border / rule
C_ROW_A   = colors.HexColor("#f8fafc")   # table even rows
C_ROW_B   = colors.white                 # table odd rows
C_HDR_BG  = colors.HexColor("#1e3a5f")   # table header background
C_BAR_FG  = colors.HexColor("#2563eb")   # progress bar fill
C_BAR_BG  = colors.HexColor("#e2e8f0")   # progress bar track
C_WHITE   = colors.white

TAG_PALETTE = {
    "Foundational": C_AMBER,
    "Essential":    C_BLUE,
    "Milestone":    C_VIOLET,
    "Extension":    C_EMERALD,
}


# ── Page decorations ───────────────────────────────────────────────────────────

def _draw_page(canvas, doc):
    """Thin top rule, right-aligned header text, centred page number."""
    canvas.saveState()
    pg = canvas.getPageNumber()

    canvas.setStrokeColor(C_RULE)
    canvas.setLineWidth(0.7)
    canvas.line(LM, H - TM * 0.6, W - RM, H - TM * 0.6)

    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(C_MUTED)
    canvas.drawRightString(W - RM, H - TM * 0.46,
                           "ResearchMind  ·  Learning Session Export")

    canvas.line(LM, BM * 0.72, W - RM, BM * 0.72)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(C_NAVY)
    canvas.drawCentredString(W / 2, BM * 0.34, str(pg))

    canvas.restoreState()


# ── Document class ─────────────────────────────────────────────────────────────

class _RMDoc(BaseDocTemplate):
    def __init__(self, path: str, **kw):
        BaseDocTemplate.__init__(self, path, **kw)
        inner_w = self.width
        inner_h = self.height

        cover_frame  = Frame(LM, BM, inner_w, inner_h, id="cover")
        normal_frame = Frame(LM, BM + 0.9 * cm,
                             inner_w, inner_h - 0.9 * cm, id="normal")

        self.addPageTemplates([
            PageTemplate(id="Cover",  frames=[cover_frame]),
            PageTemplate(id="Normal", frames=[normal_frame], onPage=_draw_page),
        ])

    def afterFlowable(self, flowable):
        if not hasattr(flowable, "style"):
            return
        level_map = {"rm_h1": 0, "rm_h2": 1, "rm_h3": 2}
        level = level_map.get(flowable.style.name)
        if level is None:
            return
        text = flowable.getPlainText()
        key  = f"bk_{abs(id(flowable))}"
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(text, key, level=level, closed=level > 0)
        self.notify("TOCEntry", (level, text, self.page, key))


# ── Styles ─────────────────────────────────────────────────────────────────────

def _styles() -> dict:
    return {
        "cover_brand": ParagraphStyle("cover_brand",
            fontSize=38, fontName="Helvetica-Bold", textColor=C_NAVY,
            leading=42, spaceAfter=4),
        "cover_sub": ParagraphStyle("cover_sub",
            fontSize=16, fontName="Helvetica", textColor=C_MUTED,
            leading=22, spaceAfter=10),
        "cover_meta": ParagraphStyle("cover_meta",
            fontSize=9.5, fontName="Courier", textColor=C_BODY,
            leading=15, spaceAfter=5),
        "cover_pct": ParagraphStyle("cover_pct",
            fontSize=11, fontName="Helvetica-Bold", textColor=C_BLUE,
            spaceAfter=4),
        "toc_title": ParagraphStyle("toc_title",
            fontSize=20, fontName="Helvetica-Bold", textColor=C_NAVY,
            spaceBefore=0, spaceAfter=14),
        # Tracked headings — names MUST match level_map in afterFlowable
        "rm_h1": ParagraphStyle("rm_h1",
            fontSize=15, fontName="Helvetica-Bold", textColor=C_NAVY,
            spaceBefore=24, spaceAfter=4, leading=19),
        "rm_h2": ParagraphStyle("rm_h2",
            fontSize=12, fontName="Helvetica-Bold", textColor=C_BLUE,
            spaceBefore=14, spaceAfter=3, leading=15, leftIndent=10),
        "rm_h3": ParagraphStyle("rm_h3",
            fontSize=10.5, fontName="Helvetica-Bold", textColor=C_VIOLET,
            spaceBefore=9, spaceAfter=3, leading=13, leftIndent=22),
        "body": ParagraphStyle("body",
            fontSize=9.5, fontName="Helvetica", textColor=C_BODY,
            leading=15, spaceAfter=4),
        "body_sm": ParagraphStyle("body_sm",
            fontSize=8.5, fontName="Helvetica", textColor=C_BODY,
            leading=13, spaceAfter=3),
        "mono": ParagraphStyle("mono",
            fontSize=8.5, fontName="Courier", textColor=C_MUTED,
            leading=13, spaceAfter=3),
        "caption": ParagraphStyle("caption",
            fontSize=8, fontName="Helvetica-Oblique", textColor=C_MUTED,
            leading=12, spaceAfter=5),
        "chat_q": ParagraphStyle("chat_q",
            fontSize=9.5, fontName="Helvetica-Bold", textColor=C_NAVY,
            leading=14, spaceAfter=2),
        "chat_a": ParagraphStyle("chat_a",
            fontSize=9.5, fontName="Helvetica", textColor=C_BODY,
            leading=15, spaceAfter=10, leftIndent=14),
        # Explanation markdown styles
        "expl_h2": ParagraphStyle("expl_h2",
            fontSize=10, fontName="Helvetica-Bold", textColor=C_BLUE,
            spaceBefore=10, spaceAfter=3, leading=13, leftIndent=12),
        "expl_h3": ParagraphStyle("expl_h3",
            fontSize=9.5, fontName="Helvetica-Bold", textColor=C_VIOLET,
            spaceBefore=7, spaceAfter=2, leading=12, leftIndent=24),
        "expl_body": ParagraphStyle("expl_body",
            fontSize=9.5, fontName="Helvetica", textColor=C_BODY,
            leading=15, spaceAfter=4, leftIndent=12),
        "expl_bullet": ParagraphStyle("expl_bullet",
            fontSize=9.5, fontName="Helvetica", textColor=C_BODY,
            leading=15, spaceAfter=3, leftIndent=26, firstLineIndent=-14),
        "expl_quote": ParagraphStyle("expl_quote",
            fontSize=9.0, fontName="Helvetica-Oblique", textColor=C_MUTED,
            leading=13, spaceAfter=4, leftIndent=30),
        "expl_code": ParagraphStyle("expl_code",
            fontSize=8.5, fontName="Courier", textColor=C_BODY,
            leading=13, spaceAfter=4, leftIndent=22, backColor=colors.HexColor("#f1f5f9")),
    }


def _hr(col=C_RULE, thick=0.6, before=4, after=8):
    return HRFlowable(width="100%", thickness=thick, color=col,
                      spaceBefore=before, spaceAfter=after)


def _section_rule(col=C_NAVY):
    return HRFlowable(width="100%", thickness=1.8, color=col,
                      spaceBefore=2, spaceAfter=10)


def _meta_table(rows: list, doc_width: float) -> Table:
    t = Table(rows, colWidths=[4.0 * cm, doc_width - 4.0 * cm])
    t.setStyle(TableStyle([
        ("FONTNAME",       (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",       (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE",       (0, 0), (-1, -1), 9),
        ("TEXTCOLOR",      (0, 0), (0, -1), C_MUTED),
        ("TEXTCOLOR",      (1, 0), (1, -1), C_BODY),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [C_ROW_A, C_ROW_B]),
        ("GRID",           (0, 0), (-1, -1), 0.5, C_RULE),
        ("TOPPADDING",     (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 7),
        ("LEFTPADDING",    (0, 0), (-1, -1), 10),
    ]))
    return t


# ── Explanation section metadata ──────────────────────────────────────────────

_EXPL_SECTION_LABELS = {
    "abstract":   "Abstract",
    "intro":      "Introduction",
    "arch":       "Architecture",
    "attention":  "Attention Mechanism",
    "training":   "Training Setup",
    "results":    "Results & Evaluation",
    "conclusion": "Conclusion & Future Work",
    "full":       "Full Paper Explanation",
}
_EXPL_SECTION_ORDER = [
    "abstract", "intro", "arch", "attention", "training", "results", "conclusion", "full"
]


def _md_inline(raw: str) -> str:
    """Escape XML special chars then convert inline markdown to ReportLab markup."""
    text = raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*([^*\n]+?)\*", r"<i>\1</i>", text)
    text = re.sub(r"`([^`\n]+?)`", r'<font face="Courier" fontSize="8">\1</font>', text)
    return text


def _markdown_to_story(md_text: str, S: dict) -> list:
    """Convert a markdown explanation block to a list of ReportLab flowables."""
    flowables: list = []
    lines = md_text.split("\n")
    i = 0
    blank_streak = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Empty line
        if not stripped:
            blank_streak += 1
            if blank_streak == 1:
                flowables.append(Spacer(1, 0.1 * cm))
            i += 1
            continue
        blank_streak = 0

        # Horizontal rule
        if re.match(r"^[-*]{3,}$", stripped):
            flowables.append(_hr(C_RULE, thick=0.4, before=3, after=5))
            i += 1
            continue

        # H2: ## heading
        if stripped.startswith("## "):
            flowables.append(Paragraph(_md_inline(stripped[3:]), S["expl_h2"]))
            i += 1
            continue

        # H3: ### heading
        if stripped.startswith("### "):
            flowables.append(Paragraph(_md_inline(stripped[4:]), S["expl_h3"]))
            i += 1
            continue

        # H1: # (treat as H2 within explanation context)
        if re.match(r"^#[^#]", stripped):
            flowables.append(Paragraph(_md_inline(stripped[2:]), S["expl_h2"]))
            i += 1
            continue

        # Blockquote: > text
        if stripped.startswith("> "):
            flowables.append(Paragraph(_md_inline(stripped[2:]), S["expl_quote"]))
            i += 1
            continue

        # Table rows: | col | col |
        if stripped.startswith("|"):
            # Skip separator rows like |---|---|
            if re.match(r"^[\|\-\s:]+$", stripped):
                i += 1
                continue
            cells = [c.strip() for c in stripped.split("|") if c.strip()]
            if cells:
                flowables.append(Paragraph(_md_inline("  ·  ".join(cells)), S["expl_body"]))
            i += 1
            continue

        # Display math block: $$ ... $$
        if stripped.startswith("$$"):
            math_lines: list[str] = []
            # Single-line: $$math$$
            if stripped.endswith("$$") and len(stripped) > 4:
                math = stripped[2:-2].strip()
                safe = math.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                flowables.append(Paragraph(
                    f'<font face="Courier" fontSize="8.5">{safe}</font>', S["expl_body"]
                ))
                i += 1
                continue
            # Multi-line: $$ \n ... \n $$
            i += 1
            while i < len(lines):
                l = lines[i].strip()
                if l == "$$":
                    i += 1
                    break
                math_lines.append(l)
                i += 1
            math = " ".join(math_lines)
            safe = math.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            flowables.append(Paragraph(
                f'<font face="Courier" fontSize="8.5">{safe}</font>', S["expl_body"]
            ))
            continue

        # Numbered list item: 1. text
        m = re.match(r"^(\d+)\.\s+(.+)", stripped)
        if m:
            num, content = m.group(1), m.group(2)
            flowables.append(Paragraph(
                f"{num}.  {_md_inline(content)}", S["expl_bullet"]
            ))
            i += 1
            continue

        # Bullet: - text | * text | • text
        m = re.match(r"^[-*•]\s+(.+)", stripped)
        if m:
            flowables.append(Paragraph(f"•  {_md_inline(m.group(1))}", S["expl_bullet"]))
            i += 1
            continue

        # Indented sub-bullet
        if re.match(r"^\s{2,}[-*•]\s+", line):
            content = re.sub(r"^\s+[-*•]\s+", "", line)
            flowables.append(Paragraph(f"    ◦  {_md_inline(content)}", S["expl_bullet"]))
            i += 1
            continue

        # Regular paragraph
        flowables.append(Paragraph(_md_inline(stripped), S["expl_body"]))
        i += 1

    return flowables


# ── Main export ────────────────────────────────────────────────────────────────

def export_session_pdf(session: SessionState) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = f"researchmind_{session.session_id[:8]}_{timestamp}.pdf"
    out_path  = cfg.export_dir / filename

    doc = _RMDoc(
        str(out_path),
        pagesize=A4,
        leftMargin=LM, rightMargin=RM,
        topMargin=TM,  bottomMargin=BM,
        title="ResearchMind — Learning Session Export",
        author="ResearchMind AI",
        subject=session.topic or session.query,
    )

    S      = _styles()
    story  = []
    pct    = max(0, min(100, session.overall_pct))
    topic  = session.topic or session.query or "—"
    now_s  = datetime.now().strftime("%d %B %Y, %H:%M")

    _sec = [0]
    _sub = [0]

    def h1(text: str) -> Paragraph:
        _sec[0] += 1; _sub[0] = 0
        return Paragraph(f"{_sec[0]}.  {text}", S["rm_h1"])

    def h2(text: str) -> Paragraph:
        _sub[0] += 1
        return Paragraph(f"  {_sec[0]}.{_sub[0]}  {text}", S["rm_h2"])

    def h3(text: str) -> Paragraph:
        return Paragraph(f"     {text}", S["rm_h3"])

    # ── Cover ──────────────────────────────────────────────────────────────────
    story.append(NextPageTemplate("Normal"))
    story.append(Spacer(1, 2.5 * cm))
    story.append(Paragraph("ResearchMind", S["cover_brand"]))
    story.append(Paragraph("Learning Session Export", S["cover_sub"]))
    story.append(_hr(C_NAVY, thick=2.0, before=0, after=14))
    story.append(Paragraph(f"<b>Topic:</b>  {topic}", S["cover_meta"]))
    story.append(Paragraph(
        f"<b>Exported:</b>  {now_s}  ·  <b>Session ID:</b>  {session.session_id[:8]}",
        S["cover_meta"]))
    story.append(Spacer(1, 0.6 * cm))

    bar_w  = doc.width
    filled = bar_w * pct / 100
    pb_cols = [max(filled, 0.5), max(bar_w - filled, 0.5)]
    pb = Table([["", ""]], colWidths=pb_cols, rowHeights=[14])
    pb.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, 0), C_BAR_FG if pct > 0 else C_BAR_BG),
        ("BACKGROUND",    (1, 0), (1, 0), C_BAR_BG),
        ("LINEABOVE",     (0, 0), (-1, 0), 0.5, C_RULE),
        ("LINEBELOW",     (0, 0), (-1, 0), 0.5, C_RULE),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(pb)
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f"Overall Progress: {pct}%", S["cover_pct"]))
    story.append(PageBreak())

    # ── Table of Contents ──────────────────────────────────────────────────────
    story.append(Paragraph("Table of Contents", S["toc_title"]))
    story.append(_section_rule(C_NAVY))
    toc = TableOfContents()
    toc.dotsMinLevel = 0
    toc.levelStyles  = [
        ParagraphStyle("toc0", fontName="Helvetica-Bold", fontSize=11,
            textColor=C_NAVY, spaceBefore=8, spaceAfter=1, leading=15, leftIndent=0),
        ParagraphStyle("toc1", fontName="Helvetica", fontSize=9.5,
            textColor=C_BLUE, spaceBefore=3, spaceAfter=1, leading=13, leftIndent=18),
        ParagraphStyle("toc2", fontName="Helvetica", fontSize=8.5,
            textColor=C_MUTED, spaceBefore=2, spaceAfter=0, leading=12, leftIndent=36),
    ]
    story.append(toc)
    story.append(PageBreak())

    # ── §1 Session Overview ────────────────────────────────────────────────────
    story.append(h1("Session Overview"))
    story.append(_section_rule(C_NAVY))

    story.append(h2("Topic & Metadata"))
    mode_label = "Topic Mastery Journey" if session.topic else "Single Paper Deep Dive"
    story.append(_meta_table([
        ["Topic",      topic],
        ["Mode",       mode_label],
        ["Session ID", session.session_id],
        ["Exported",   now_s],
    ], doc.width))
    story.append(Spacer(1, 0.4 * cm))

    story.append(h2("Progress Summary"))
    story.append(Paragraph(
        f"Overall completion: <b>{pct}%</b>"
        + (" — session exported before pipeline completed." if pct == 0 else "."),
        S["body"]))

    agents = session.agent_statuses
    if agents:
        labels = {
            "diagnostic":    "Diagnostic Agent",
            "discovery":     "Discovery Agent",
            "graph_builder": "Graph Builder",
            "scraper":       "Scraper Agent",
            "quiz_gen":      "Quiz Generator",
        }
        status_str = {
            "done": "✓  Done", "running": "⟳  Running",
            "failed": "✗  Failed", "pending": "○  Pending",
        }
        arows = [["Agent", "Status"]]
        for aid, alabel in labels.items():
            arows.append([alabel, status_str.get(agents.get(aid, "pending"), "○  Pending")])
        at = Table(arows, colWidths=[8 * cm, doc.width - 8 * cm])
        at.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1,  0), C_HDR_BG),
            ("TEXTCOLOR",     (0, 0), (-1,  0), C_WHITE),
            ("FONTNAME",      (0, 0), (-1,  0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [C_ROW_A, C_ROW_B]),
            ("TEXTCOLOR",     (0, 1), (-1, -1), C_BODY),
            ("GRID",          (0, 0), (-1, -1), 0.5, C_RULE),
            ("TOPPADDING",    (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ]))
        story.append(Spacer(1, 0.3 * cm))
        story.append(at)
    story.append(Spacer(1, 0.5 * cm))

    # ── §2 Knowledge Profile ───────────────────────────────────────────────────
    story.append(h1("Knowledge Profile"))
    story.append(_section_rule(C_VIOLET))

    profile  = session.user_profile
    level    = profile.get("level", "")
    mastered = profile.get("mastered_concepts", [])
    notes    = profile.get("notes", "")

    story.append(h2("Reader Level"))
    story.append(Paragraph(
        level.capitalize() if level else "Not yet assessed — complete the diagnostic.",
        S["body"]))

    story.append(h2("Mastered Concepts"))
    if mastered:
        for concept in mastered:
            story.append(Paragraph(f"  ✓  {concept}", S["body"]))
    else:
        story.append(Paragraph("No concepts recorded yet.", S["caption"]))

    if notes:
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph(f"<i>Notes: {notes}</i>", S["caption"]))
    story.append(Spacer(1, 0.5 * cm))

    # ── §3 Reading Sequence ────────────────────────────────────────────────────
    if session.papers:
        story.append(h1("Reading Sequence"))
        story.append(_section_rule(C_AMBER))
        story.append(Paragraph(
            f"{len(session.papers)} papers curated in recommended reading order.",
            S["caption"]))
        story.append(Spacer(1, 0.3 * cm))

        for i, paper in enumerate(session.papers):
            items = [
                Paragraph(f"{i + 1}.  {paper.title}", S["rm_h2"]),
                Paragraph(
                    (f"{paper.authors}  ·  {paper.year}"
                     + (f"  ·  {paper.citations:,} citations" if paper.citations else "")
                     + (f"  ·  [{paper.tag}]" if paper.tag else "")),
                    S["mono"]),
            ]
            if paper.abstract:
                items.append(Paragraph(
                    paper.abstract[:500] + ("…" if len(paper.abstract) > 500 else ""),
                    S["body_sm"]))
            if paper.url:
                items.append(Paragraph(
                    f'<a href="{paper.url}" color="#2563eb">{paper.url}</a>',
                    S["caption"]))
            items.append(Spacer(1, 0.35 * cm))
            story.append(KeepTogether(items))

    # ── §4 Paper Explanations ─────────────────────────────────────────────────
    if session.section_explanations:
        story.append(h1("Paper Explanations"))
        story.append(_section_rule(C_BLUE))
        story.append(Paragraph(
            "Full AI-generated section-by-section explanations as viewed in the app.",
            S["caption"]))
        story.append(Spacer(1, 0.3 * cm))

        paper_lookup = {p.id: p for p in session.papers}

        for paper_id, sections in session.section_explanations.items():
            if not sections:
                continue

            paper = paper_lookup.get(paper_id)
            paper_title = paper.title if paper else paper_id

            story.append(h2(paper_title))
            if paper and (paper.authors or paper.year):
                meta = f"{paper.authors}  ·  {paper.year}"
                if paper.tag:
                    meta += f"  ·  [{paper.tag}]"
                story.append(Paragraph(meta, S["mono"]))
            story.append(Spacer(1, 0.2 * cm))

            for section_key in _EXPL_SECTION_ORDER:
                expl_text = sections.get(section_key, "")
                if not expl_text:
                    continue
                section_label = _EXPL_SECTION_LABELS.get(section_key, section_key.title())
                story.append(h3(section_label))
                story.append(_hr(C_RULE, thick=0.4, before=2, after=6))
                story.extend(_markdown_to_story(expl_text, S))
                story.append(Spacer(1, 0.5 * cm))

            story.append(PageBreak())

    # ── §5 Confidence Quiz Results ─────────────────────────────────────────────
    if session.quiz_result:
        qr = session.quiz_result
        story.append(h1("Confidence Quiz Results"))
        story.append(_section_rule(C_EMERALD))

        story.append(h2("Score Summary"))
        verdict = "PASSED ✓" if qr.passed else "NEEDS REVIEW ✗"
        v_col   = "#059669" if qr.passed else "#dc2626"
        story.append(Paragraph(
            f'Score: <b><font color="{v_col}">{qr.score_pct}%  —  {verdict}</font></b>',
            S["body"]))
        story.append(Paragraph(
            "Pass threshold: 70%.  "
            + ("Well done — proceed to the Paper Explainer." if qr.passed
               else "Review the material and try again."),
            S["caption"]))
        story.append(Spacer(1, 0.3 * cm))

        if session.quiz_questions and qr.answers:
            story.append(h2("Question Review"))
            for j, (q, correct) in enumerate(zip(session.quiz_questions, qr.answers)):
                mark = "✓" if correct else "✗"
                fg   = "#059669" if correct else "#dc2626"
                items = [
                    Paragraph(f"<b>Q{j + 1}.</b>  {q.q}", S["body"]),
                    Paragraph(
                        f'<font color="{fg}"><b>{mark}</b></font>  '
                        f'{q.opts[q.correct]}'
                        + (f"  —  <i>{q.explain}</i>" if q.explain else ""),
                        S["body_sm"]),
                    Spacer(1, 0.2 * cm),
                ]
                story.append(KeepTogether(items))
        story.append(Spacer(1, 0.5 * cm))

    # ── §6 Q&A History ─────────────────────────────────────────────────────────
    if session.chat_history:
        story.append(h1("Q&A History"))
        story.append(_section_rule(C_BLUE))
        turns = len([m for m in session.chat_history if m.get("role") == "user"])
        story.append(Paragraph(
            f"{turns} exchange{'s' if turns != 1 else ''} recorded.", S["caption"]))
        story.append(Spacer(1, 0.2 * cm))

        pair_no = [0]
        for msg in session.chat_history:
            role    = msg.get("role", "user")
            content = (msg.get("content", "") or "").strip()
            if not content:
                continue
            if role == "user":
                pair_no[0] += 1
                story.append(h3(f"Exchange {pair_no[0]}"))
                story.append(Paragraph(f"<b>You:</b>  {content}", S["chat_q"]))
            else:
                story.append(Paragraph(content, S["chat_a"]))
        story.append(Spacer(1, 0.5 * cm))

    # ── §7 Spaced Repetition Schedule ─────────────────────────────────────────
    story.append(h1("Spaced Repetition Schedule"))
    story.append(_section_rule(C_VIOLET))
    story.append(Paragraph(
        "Review these concepts at the intervals shown to maximise long-term retention.",
        S["body"]))
    story.append(Spacer(1, 0.3 * cm))

    sr_data = [
        ["Concept",                       "Due In",  "Memory Strength"],
        ["Scaled Dot-Product Attention",  "1 day",   "32%"],
        ["Positional Encoding",           "3 days",  "55%"],
        ["Multi-Head Attention",          "1 day",   "28%"],
        ["Feed-Forward Sublayer",         "6 days",  "72%"],
        ["Encoder–Decoder Stack",         "2 days",  "44%"],
    ]
    c3 = max(doc.width - 9 * cm - 3.5 * cm, 2 * cm)
    sr = Table(sr_data, colWidths=[9 * cm, 3.5 * cm, c3])
    sr.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1,  0), C_HDR_BG),
        ("TEXTCOLOR",     (0, 0), (-1,  0), C_WHITE),
        ("FONTNAME",      (0, 0), (-1,  0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [C_ROW_A, C_ROW_B]),
        ("TEXTCOLOR",     (0, 1), (-1, -1), C_BODY),
        ("GRID",          (0, 0), (-1, -1), 0.5, C_RULE),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("ALIGN",         (1, 0), (2, -1), "CENTER"),
    ]))
    story.append(sr)
    story.append(Spacer(1, 0.8 * cm))

    story.append(_hr(C_RULE, thick=0.5, before=8, after=4))
    story.append(Paragraph(
        f"Generated by ResearchMind  ·  AI-powered research learning platform  ·  {now_s}",
        S["caption"]))

    doc.multiBuild(story)
    log.info("PDF exported → %s", out_path)
    return out_path
