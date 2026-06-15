/**
 * ResearchMind — Home Screen
 */
import React, { useState, useEffect } from "react";
import {
  createSession, restoreSession,
  getPapers, deletePaper, downloadPaperPdf,
  getHistory, deleteHistory, clearHistory,
} from "@/lib/api";
import { useStore } from "@/stores/useStore";
import { Tag }      from "@/components/Primitives";
import toast        from "react-hot-toast";

const FEATURES = [
  { icon:"◎", title:"Multi-Agent Pipeline",  desc:"5 specialised agents orchestrated end-to-end" },
  { icon:"⬡", title:"Knowledge Graph",        desc:"Interactive concept map with dependencies" },
  { icon:"◈", title:"Confidence Quiz",        desc:"Gated 70% pass-gate before advancing" },
  { icon:"⊕", title:"Socratic + Devil Mode",  desc:"AI that questions and challenges your thinking" },
  { icon:"⊗", title:"Spaced Repetition",      desc:"Live Claude-powered quick-recall sessions" },
  { icon:"↺", title:"Section-by-Section",     desc:"Papers explained with concept linking" },
];

const MODE_COLORS = { single_paper: "#4f8eff", topic_mastery: "#9b6dff" };
const MODE_LABELS = { single_paper: "Single Paper", topic_mastery: "Topic Mastery" };

function fmt(iso) {
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  } catch { return ""; }
}

function HistoryCard({ entry, onOpen, onDelete, onReanalyze }) {
  const col = MODE_COLORS[entry.mode] || "#4f8eff";
  return (
    <div className="card fu" style={{
      padding: 18, display: "flex", flexDirection: "column", gap: 10,
      border: `1px solid ${col}22`, transition: "border-color .2s",
    }}
      onMouseEnter={e => e.currentTarget.style.borderColor = `${col}55`}
      onMouseLeave={e => e.currentTarget.style.borderColor = `${col}22`}
    >
      {/* Header row */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
        <Tag color={col} style={{ flexShrink: 0 }}>{MODE_LABELS[entry.mode]}</Tag>
        <span className="mono" style={{ fontSize: 10, color: "var(--mu)", whiteSpace: "nowrap" }}>
          {fmt(entry.cached_at)}
        </span>
      </div>

      {/* Title */}
      <div style={{ fontWeight: 800, fontSize: 14, lineHeight: 1.35, color: "var(--tx)" }}>
        {entry.query}
      </div>

      {/* Paper sub-list (mode 2) */}
      {entry.mode === "topic_mastery" && entry.papers?.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
          {entry.papers.slice(0, 3).map((p, i) => (
            <div key={i} className="mono" style={{ fontSize: 10, color: "var(--mu)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {i + 1}. {p.title} {p.year ? `(${p.year})` : ""}
            </div>
          ))}
          {entry.paper_count > 3 && (
            <div className="mono" style={{ fontSize: 10, color: "var(--mu)" }}>+{entry.paper_count - 3} more</div>
          )}
        </div>
      )}

      {/* Summary */}
      {entry.summary && (
        <p className="serifi" style={{ fontSize: 12.5, color: "var(--mu)", lineHeight: 1.6, margin: 0 }}>
          {entry.summary}
        </p>
      )}

      {/* Tags */}
      {entry.tags?.filter(Boolean).length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
          {entry.tags.filter(Boolean).map((t, i) => (
            <span key={i} className="tag" style={{ background: `${col}14`, color: col, border: `1px solid ${col}28`, fontSize: 9 }}>
              {t}
            </span>
          ))}
        </div>
      )}

      {/* Actions */}
      <div style={{ display: "flex", gap: 7, marginTop: 2 }}>
        <button
          className="btn bp"
          onClick={() => onOpen(entry)}
          style={{ flex: 1, fontSize: 12, padding: "8px 12px", background: col, boxShadow: `0 2px 10px ${col}33` }}
        >
          View Explanation →
        </button>
        <button
          onClick={() => onReanalyze(entry)}
          title="Delete cache and reanalyse"
          className="btn bg"
          style={{ padding: "8px 10px", fontSize: 11 }}
        >
          ↺
        </button>
        <button
          onClick={() => onDelete(entry)}
          title="Remove from history"
          className="btn bg"
          style={{ padding: "8px 10px", fontSize: 11, color: "var(--ro)" }}
        >
          🗑
        </button>
      </div>
    </div>
  );
}

export default function HomeScreen() {
  const {
    setScreen, setSessionId, setQuery, setTopic, reset,
    setPapers, setGraph, setQuizQuestions, setOverallPct,
    setAgentStatus, setMode2Phase,
  } = useStore();

  const [input,     setInput]     = useState("");
  const [tab,       setTab]       = useState(0);
  const [loading,   setLoading]   = useState(false);

  // History state
  const [history,     setHistory]     = useState([]);
  const [histLoading, setHistLoading] = useState(true);
  const [search,      setSearch]      = useState("");
  const [modeFilter,  setModeFilter]  = useState("all");

  useEffect(() => {
    getHistory()
      .then(d => setHistory(d.entries || []))
      .catch(() => {})
      .finally(() => setHistLoading(false));
  }, []);

  const filteredHistory = history.filter(e => {
    const q = search.toLowerCase();
    const matchSearch = !q || e.query.toLowerCase().includes(q) ||
      e.papers?.some(p => p.title?.toLowerCase().includes(q));
    const matchMode = modeFilter === "all" || e.mode === modeFilter;
    return matchSearch && matchMode;
  });

  // ── Start new session ─────────────────────────────────────────────────────
  const start = async () => {
    if (!input.trim() || loading) return;
    setLoading(true);
    try {
      const mode = tab === 0 ? "single_paper" : "topic_mastery";
      const { session_id } = await createSession(mode, input.trim());
      reset();
      setSessionId(session_id);
      if (tab === 0) { setQuery(input.trim()); setScreen("mode1"); }
      else           { setTopic(input.trim()); setScreen("mode2"); }
    } catch {
      toast.error("Failed to create session. Is the backend running?");
    }
    setLoading(false);
  };

  // ── Open from history ─────────────────────────────────────────────────────
  const openEntry = async (entry) => {
    setLoading(true);
    try {
      const mode = entry.mode === "single_paper" ? "single_paper" : "topic_mastery";
      const { session_id } = await createSession(mode, entry.query);
      reset();
      setSessionId(session_id);

      if (mode === "single_paper") {
        setQuery(entry.query);
        setScreen("mode1");  // Mode1Screen auto-streams; cache makes it instant
      } else {
        setTopic(entry.query);
        // Restore cached pipeline state — skip the diagnostic phase
        const data = await restoreSession(session_id, entry.id);
        if (data.papers?.length)         setPapers(data.papers);
        if (data.graph)                  setGraph(data.graph);
        if (data.quiz_questions?.length) setQuizQuestions(data.quiz_questions);
        setOverallPct(data.overall_pct || 88);
        Object.entries(data.agent_statuses || {}).forEach(([id, st]) => setAgentStatus(id, st));
        setMode2Phase("overview");
        setScreen("mode2");
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not open this entry");
    }
    setLoading(false);
  };

  // ── Delete from history ───────────────────────────────────────────────────
  const removeEntry = async (entry) => {
    await deleteHistory(entry.id).catch(() => {});
    setHistory(h => h.filter(e => e.id !== entry.id));
    toast.success("Removed from history");
  };

  // ── Reanalyze (delete cache + open fresh) ────────────────────────────────
  const reanalyzeEntry = async (entry) => {
    await deleteHistory(entry.id).catch(() => {});
    setHistory(h => h.filter(e => e.id !== entry.id));
    setInput(entry.query);
    setTab(entry.mode === "single_paper" ? 0 : 1);
    toast("Cache cleared — click Start to reanalyse", { icon: "↺" });
  };

  const handleClearAll = async () => {
    if (!window.confirm("Clear all history and cached results?")) return;
    await clearHistory().catch(() => {});
    setHistory([]);
    toast.success("History cleared");
  };

  return (
    <div className="dot-bg" style={{ minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", padding: "40px 20px 80px", position: "relative" }}>
      {/* Ambient glows */}
      <div style={{ position: "fixed", top: "8%", left: "50%", transform: "translateX(-50%)", width: 900, height: 500, background: "radial-gradient(ellipse,#4f8eff08 0%,transparent 70%)", pointerEvents: "none" }} />
      <div style={{ position: "fixed", bottom: "5%", right: "8%", width: 500, height: 500, background: "radial-gradient(ellipse,#9b6dff06 0%,transparent 70%)", pointerEvents: "none" }} />

      <div style={{ maxWidth: 700, width: "100%" }}>

        {/* ── Logo ────────────────────────────────────────────────────────── */}
        <div className="fu" style={{ textAlign: "center", marginBottom: 52 }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 9, padding: "5px 18px", borderRadius: 99, background: "var(--s1)", border: "1px solid var(--bd2)", marginBottom: 24 }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#4f8eff", animation: "pulse 2s ease infinite" }} />
            <span className="mono" style={{ fontSize: 10, color: "var(--mu)", letterSpacing: ".1em" }}>MULTI-AGENT AI RESEARCH PLATFORM</span>
          </div>
          <h1 style={{ fontFamily: "Cabinet Grotesk,sans-serif", fontWeight: 900, fontSize: "clamp(48px,9vw,82px)", letterSpacing: "-.04em", lineHeight: .92, marginBottom: 20 }}>
            Research<span style={{ color: "#4f8eff" }}>Mind</span>
          </h1>
          <p className="serifi" style={{ fontSize: 19, color: "var(--mu)", lineHeight: 1.65, maxWidth: 500, margin: "0 auto" }}>
            From paper upload to deep mastery — AI agents guide your entire research journey.
          </p>
        </div>

        {/* ── Input card ──────────────────────────────────────────────────── */}
        <div className="card gaz fu1" style={{ marginBottom: 14, padding: 26 }}>
          <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
            {[["📄  Single Paper Deep Dive", "#4f8eff"], ["🗺️  Topic Mastery Journey", "#9b6dff"]].map(([label, col], i) => (
              <button key={i} onClick={() => setTab(i)} style={{
                flex: 1, padding: "11px", borderRadius: 10, cursor: "pointer",
                fontFamily: "Cabinet Grotesk,sans-serif", fontWeight: 700, fontSize: 13,
                background: tab === i ? col : "var(--s2)",
                color: tab === i ? "#fff" : "var(--mu)",
                border: `1px solid ${tab === i ? "transparent" : "var(--bd)"}`,
                transition: "all .2s",
              }}>{label}</button>
            ))}
          </div>
          <label className="mono" style={{ display: "block", fontSize: 10, color: "var(--mu)", letterSpacing: ".08em", marginBottom: 9 }}>
            {tab === 0 ? "PAPER TITLE · ARXIV LINK · DOI" : "RESEARCH TOPIC · CONCEPT · FIELD"}
          </label>
          <textarea
            className="inp" rows={3} value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === "Enter" && e.ctrlKey && start()}
            placeholder={tab === 0
              ? "e.g.  Attention Is All You Need  ·  arxiv:1706.03762  ·  GPT-4 Technical Report"
              : "e.g.  Transformers in NLP  ·  Diffusion Models  ·  RLHF"}
          />
          <button
            className={`btn ${tab === 0 ? "bp" : "bv"}`}
            onClick={start}
            disabled={!input.trim() || loading}
            style={{ marginTop: 13, width: "100%", padding: "14px", fontSize: 15 }}
          >
            {loading ? "Starting…" : tab === 0 ? "Start Deep Dive →" : "Begin Mastery Journey →"}
          </button>
          <p className="mono" style={{ fontSize: 9, color: "var(--mu)", textAlign: "center", marginTop: 10 }}>Ctrl+Enter to start</p>
        </div>

        {/* ── Features grid ───────────────────────────────────────────────── */}
        <div className="fu2" style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 10, marginBottom: 56 }}>
          {FEATURES.map((f, i) => (
            <div key={i} className="card" style={{ padding: "15px 13px" }}>
              <div className="mono" style={{ fontSize: 17, color: "#4f8eff", marginBottom: 8 }}>{f.icon}</div>
              <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 4 }}>{f.title}</div>
              <div className="mono" style={{ fontSize: 10, color: "var(--mu)", lineHeight: 1.5 }}>{f.desc}</div>
            </div>
          ))}
        </div>

        {/* ── Previous Papers & Explanations ──────────────────────────────── */}
        <div className="fu3">
          {/* Section header */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
            <div>
              <h2 style={{ fontWeight: 900, fontSize: 18, marginBottom: 3 }}>
                📚 Previous Papers &amp; Explanations
              </h2>
              <p className="mono" style={{ fontSize: 10, color: "var(--mu)" }}>
                Instantly reopen any past analysis — no reprocessing needed
              </p>
            </div>
            {history.length > 0 && (
              <button className="btn bg" onClick={handleClearAll} style={{ fontSize: 11, padding: "6px 12px", color: "var(--ro)" }}>
                Clear All
              </button>
            )}
          </div>

          {/* Search + filter row */}
          {history.length > 0 && (
            <div style={{ display: "flex", gap: 10, marginBottom: 18, flexWrap: "wrap" }}>
              <input
                className="inp"
                placeholder="Search by title or topic…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                style={{ flex: 1, minWidth: 180, padding: "9px 13px", fontSize: 13 }}
              />
              <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                {[["all", "All"], ["single_paper", "Single Paper"], ["topic_mastery", "Topic Mastery"]].map(([val, label]) => (
                  <button key={val} onClick={() => setModeFilter(val)} style={{
                    padding: "8px 14px", borderRadius: 8, border: "none", cursor: "pointer",
                    fontFamily: "Inter, sans-serif", fontWeight: 600, fontSize: 12,
                    background: modeFilter === val ? (val === "topic_mastery" ? "#9b6dff" : val === "single_paper" ? "#4f8eff" : "var(--az)") : "var(--s2)",
                    color: modeFilter === val ? "#fff" : "var(--mu)",
                    transition: "all .18s",
                  }}>{label}</button>
                ))}
              </div>
            </div>
          )}

          {/* Cards grid */}
          {histLoading ? (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 12 }}>
              {[1, 2, 3, 4].map(i => (
                <div key={i} className="card" style={{ padding: 18, display: "flex", flexDirection: "column", gap: 10 }}>
                  <div className="skel" style={{ height: 20, width: "40%" }} />
                  <div className="skel" style={{ height: 14, width: "80%" }} />
                  <div className="skel" style={{ height: 12, width: "60%" }} />
                  <div className="skel" style={{ height: 32, width: "100%" }} />
                </div>
              ))}
            </div>
          ) : filteredHistory.length === 0 ? (
            <div className="card" style={{ padding: "32px 20px", textAlign: "center", border: "1px dashed var(--bd2)" }}>
              {history.length === 0 ? (
                <>
                  <div style={{ fontSize: 32, marginBottom: 10 }}>📭</div>
                  <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 6 }}>No history yet</div>
                  <p className="serifi" style={{ fontSize: 13, color: "var(--mu)", margin: 0 }}>
                    Your analysed papers will appear here for instant re-access.
                  </p>
                </>
              ) : (
                <>
                  <div style={{ fontSize: 28, marginBottom: 8 }}>🔍</div>
                  <div style={{ fontWeight: 700, fontSize: 14 }}>No results for "{search}"</div>
                </>
              )}
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 12 }}>
              {filteredHistory.map(entry => (
                <HistoryCard
                  key={entry.id}
                  entry={entry}
                  onOpen={openEntry}
                  onDelete={removeEntry}
                  onReanalyze={reanalyzeEntry}
                />
              ))}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
