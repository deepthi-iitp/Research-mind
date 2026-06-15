import React, { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { openQuickExplainStream, getSession, uploadPDF, downloadExport } from "@/lib/api";
import { useStore }           from "@/stores/useStore";
import { Tag, PBar, TopBar } from "@/components/Primitives";
import ChatPanel              from "@/components/ChatPanel";
import SectionExplainer       from "@/components/SectionExplainer";
import toast                  from "react-hot-toast";

function StreamingCursor() {
  return (
    <span style={{
      display: "inline-block", width: 2, height: "1.1em",
      background: "#4f8eff", borderRadius: 1, marginLeft: 2,
      animation: "blink .9s step-end infinite", verticalAlign: "text-bottom",
    }} />
  );
}

function DepthToggle({ level, onChange, disabled }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span className="mono" style={{ fontSize: 9, color: "var(--mu)", letterSpacing: ".06em" }}>DEPTH</span>
      {["beginner", "expert"].map(l => (
        <button key={l} onClick={() => !disabled && onChange(l)} style={{
          padding: "3px 11px", borderRadius: 99, border: "none",
          cursor: disabled ? "not-allowed" : "pointer",
          fontFamily: "Geist Mono, monospace", fontWeight: 600, fontSize: 10,
          letterSpacing: ".04em", textTransform: "uppercase",
          background: level === l ? (l === "expert" ? "#9b6dff" : "#22d49a") : "var(--s3)",
          color: level === l ? (l === "expert" ? "#fff" : "#0b0b12") : "var(--mu)",
          opacity: disabled ? 0.5 : 1,
          transition: "all .18s",
        }}>{l}</button>
      ))}
    </div>
  );
}

const MD_COMPONENTS = {
  h1: ({ children }) => (
    <h1 style={{ fontFamily: "Cabinet Grotesk, sans-serif", fontWeight: 900, fontSize: 26, marginBottom: 8, letterSpacing: "-.02em", color: "var(--tx)" }}>{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 style={{ fontFamily: "Cabinet Grotesk, sans-serif", fontWeight: 900, fontSize: 18, color: "var(--tx)", marginTop: 32, marginBottom: 10, paddingBottom: 6, borderBottom: "1px solid var(--bd)", letterSpacing: "-.01em" }}>{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 style={{ fontFamily: "Cabinet Grotesk, sans-serif", fontWeight: 800, fontSize: 13, color: "#9b6dff", marginTop: 22, marginBottom: 8, textTransform: "uppercase", letterSpacing: ".04em" }}>{children}</h3>
  ),
  p: ({ children }) => (
    <p style={{ fontFamily: "Instrument Serif, serif", fontSize: 16.5, lineHeight: 1.95, color: "var(--tx)", marginBottom: 16 }}>{children}</p>
  ),
  li: ({ children }) => (
    <li style={{ fontFamily: "Instrument Serif, serif", fontSize: 16, lineHeight: 1.85, color: "var(--tx)", marginBottom: 7 }}>{children}</li>
  ),
  strong: ({ children }) => <strong style={{ color: "#dcdcf0", fontWeight: 700 }}>{children}</strong>,
  blockquote: ({ children }) => (
    <blockquote style={{ borderLeft: "3px solid #4f8eff", paddingLeft: 16, margin: "16px 0", color: "var(--mu)", fontStyle: "italic" }}>{children}</blockquote>
  ),
  code: ({ inline, children }) => inline
    ? <code style={{ background: "var(--s3)", color: "#ffb84f", padding: "1px 6px", borderRadius: 4, fontSize: 13, fontFamily: "Geist Mono, monospace" }}>{children}</code>
    : <pre style={{ background: "var(--s2)", border: "1px solid var(--bd)", borderRadius: 8, padding: "14px 18px", overflowX: "auto", marginBottom: 16 }}><code style={{ fontFamily: "Geist Mono, monospace", fontSize: 13, color: "#dcdcf0" }}>{children}</code></pre>,
};

export default function Mode1Screen() {
  const { sessionId, query, setScreen } = useStore();

  const [explanation, setExplanation] = useState("");
  const [streaming,   setStreaming]   = useState(false);
  const [done,        setDone]        = useState(false);
  const [status,      setStatus]      = useState("discovering");
  const [tab,         setTab]         = useState("read");
  const [level,       setLevel]       = useState("expert");

  const esRef = useRef(null);
  const fakePaper = { id: sessionId || "1", title: query, authors: "", year: 2024 };

  const runStream = (depth) => {
    esRef.current?.close();
    setExplanation("");
    setStreaming(true);
    setDone(false);
    setStatus("discovering");

    let text = "";

    esRef.current = openQuickExplainStream(sessionId, depth, {
      onStatus: (s) => setStatus(s),
      onChunk: (chunk) => {
        text += chunk;
        setExplanation(text);
      },
      onDone: () => {
        setDone(true);
        setStreaming(false);
      },
      onError: (err) => {
        console.error("Quick explain stream error:", err);
        // Detect session-not-found (backend reloaded and cleared in-memory sessions)
        if (String(err).includes("404") || String(err).includes("not found") || String(err).includes("Session")) {
          toast.error("Session expired — please go back and start again.");
          setTimeout(() => setScreen("home"), 2000);
        } else {
          toast.error(`Failed to generate explanation: ${err}`);
        }
        setStreaming(false);
      },
    });
  };

  // On mount: verify session still exists, then stream
  useEffect(() => {
    if (!sessionId) return;
    getSession(sessionId)
      .then(() => runStream(level))
      .catch(() => {
        toast.error("Session expired — please go back and start again.");
        setTimeout(() => setScreen("home"), 2000);
      });
    return () => esRef.current?.close();
  }, [sessionId]);

  const handleLevelChange = (newLevel) => {
    setLevel(newLevel);
    runStream(newLevel);
  };

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !sessionId) return;
    toast.promise(
      uploadPDF(sessionId, file),
      { loading: "Indexing PDF…", success: "PDF indexed!", error: "Upload failed" }
    );
  };

  const TABS = [["read", "Explanation"], ["sections", "Sections"], ["chat", "Q&A"]];
  const isLoading = streaming && !explanation;

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <TopBar onBack={() => setScreen("home")}>
        <Tag color="#4f8eff" dot>Mode 1 — Deep Dive</Tag>
        <span className="mono" style={{ fontSize: 11, color: "var(--mu)", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {query}
        </span>
        <label className="btn bg" style={{ fontSize: 12, padding: "7px 13px", cursor: "pointer" }}>
          📄 Upload PDF
          <input type="file" accept=".pdf" style={{ display: "none" }} onChange={handleUpload} />
        </label>
        <button className="btn bg" onClick={() => downloadExport(sessionId)} style={{ fontSize: 12, padding: "7px 13px" }}>
          ↓ Export PDF
        </button>
        {streaming && (
          <span className="mono" style={{ fontSize: 10, color: "var(--mu)" }}>
            {status === "discovering" ? "Finding paper…" : "Generating…"}
          </span>
        )}
        {done && !streaming && <Tag color="#22d49a">Ready</Tag>}
      </TopBar>

      {/* Indeterminate progress bar while streaming */}
      {streaming && (
        <div style={{ height: 2, background: "var(--fa)", flexShrink: 0, overflow: "hidden" }}>
          <div style={{
            height: "100%", background: "linear-gradient(90deg, #4f8eff, #9b6dff)",
            borderRadius: 99, animation: "indeterminate 1.6s ease infinite",
          }} />
        </div>
      )}

      {/* Sub-tabs */}
      <div style={{ display: "flex", alignItems: "center", borderBottom: "1px solid var(--bd)", flexShrink: 0 }}>
        {TABS.map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)} style={{
            padding: "11px 20px", border: "none", cursor: "pointer",
            fontFamily: "Cabinet Grotesk, sans-serif", fontWeight: 700, fontSize: 13,
            background: "transparent", color: tab === id ? "var(--tx)" : "var(--mu)",
            borderBottom: `2px solid ${tab === id ? "#4f8eff" : "transparent"}`,
            transition: "all .18s",
          }}>{label}</button>
        ))}
        {tab === "read" && (
          <div style={{ marginLeft: "auto", padding: "8px 16px" }}>
            <DepthToggle level={level} onChange={handleLevelChange} disabled={streaming} />
          </div>
        )}
      </div>

      <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>

        {tab === "read" && (
          <div className="scroll" style={{ flex: 1, padding: "32px 44px", maxWidth: 900, width: "100%", margin: "0 auto" }}>
            {isLoading && (
              <div>
                <div style={{ marginBottom: 28, display: "flex", flexDirection: "column", gap: 10 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <div style={{ width: 10, height: 10, borderRadius: "50%", border: "2px solid rgba(255,255,255,.1)", borderTopColor: "#4f8eff", animation: "spin .7s linear infinite", flexShrink: 0 }} />
                    <span className="mono" style={{ fontSize: 11, color: "#4f8eff", letterSpacing: ".04em" }}>
                      {status === "discovering" ? "SEARCHING DATABASES" : "GENERATING EXPLANATION"}
                    </span>
                  </div>
                  <p style={{ fontFamily: "Instrument Serif, serif", fontSize: 15, color: "var(--mu)", margin: 0, lineHeight: 1.7, paddingLeft: 22 }}>
                    {status === "discovering"
                      ? "Searching Semantic Scholar and arXiv for your paper — this takes a moment…"
                      : "Building your AI-powered explanation. Data will be loaded in a few minutes."}
                  </p>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  {[100, 80, 95, 65, 88, 72, 100, 60, 85, 90].map((w, i) => (
                    <div key={i} className="skel" style={{ height: 15, width: `${w}%`, animationDelay: `${i * 0.1}s` }} />
                  ))}
                </div>
              </div>
            )}
            {explanation && (
              <>
                <div style={{ marginBottom: 28 }}>
                  <h1 style={{
                    fontFamily: "Cabinet Grotesk, sans-serif", fontWeight: 900,
                    fontSize: 28, letterSpacing: "-.025em", color: "var(--tx)", marginBottom: 8,
                  }}>
                    {query}
                  </h1>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div style={{ flex: 1, height: 1, background: "var(--bd)" }} />
                    <span className="mono" style={{ fontSize: 9, color: "var(--mu)", letterSpacing: ".08em" }}>
                      {level === "expert" ? "EXPERT ANALYSIS" : "BEGINNER OVERVIEW"} · AI-GENERATED
                    </span>
                    <div style={{ flex: 1, height: 1, background: "var(--bd)" }} />
                  </div>
                </div>
                <div className="md-body">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm, remarkMath]}
                    rehypePlugins={[rehypeKatex]}
                    components={MD_COMPONENTS}
                  >
                    {explanation}
                  </ReactMarkdown>
                  {streaming && <StreamingCursor />}
                </div>
              </>
            )}
          </div>
        )}

        {tab === "sections" && (
          <div style={{ flex: 1, overflow: "hidden", padding: 20 }}>
            <SectionExplainer paper={fakePaper} onBack={() => setTab("read")} />
          </div>
        )}

        {tab === "chat" && (
          <div style={{ flex: 1, overflow: "hidden" }}>
            <ChatPanel context={query} level={level} />
          </div>
        )}
      </div>
    </div>
  );
}
