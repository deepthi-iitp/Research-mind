import React, { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { openExplainStream } from "@/lib/api";
import { useStore } from "@/stores/useStore";
import { Tag } from "./Primitives";
import ChatPanel from "./ChatPanel";

const SECTIONS = [
  { id: "abstract",   label: "Abstract",           icon: "§", desc: "Core problem, proposed solution & key claims" },
  { id: "intro",      label: "Introduction",        icon: "¶", desc: "Motivation, prior work & research gap" },
  { id: "arch",       label: "Architecture",        icon: "◧", desc: "Model components & design decisions" },
  { id: "attention",  label: "Attention Mechanism", icon: "⊛", desc: "Attention math, multi-head & positional encoding" },
  { id: "training",   label: "Training",            icon: "⊙", desc: "Data, objective function & optimisation setup" },
  { id: "results",    label: "Results",             icon: "◈", desc: "Benchmarks, ablations & qualitative analysis" },
  { id: "conclusion", label: "Conclusion",          icon: "◉", desc: "Takeaways, limitations & future directions" },
];

function DepthToggle({ level, onChange }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span style={{ fontSize: 10, color: "var(--mu)", fontFamily: "JetBrains Mono, monospace", letterSpacing: ".06em" }}>DEPTH</span>
      {["beginner", "expert"].map(l => (
        <button key={l} onClick={() => onChange(l)} style={{
          padding: "4px 12px", borderRadius: 99, border: "none", cursor: "pointer",
          fontFamily: "Inter, sans-serif", fontWeight: 600, fontSize: 11,
          letterSpacing: ".03em", textTransform: "uppercase",
          background: level === l ? (l === "expert" ? "#9b6dff" : "#22d49a") : "var(--s3)",
          color: level === l ? (l === "expert" ? "#fff" : "#0b0b12") : "var(--mu)",
          transition: "all .18s",
        }}>{l}</button>
      ))}
    </div>
  );
}

function StreamingCursor() {
  return (
    <span style={{
      display: "inline-block", width: 2, height: "1.1em",
      background: "#4f8eff", borderRadius: 1, marginLeft: 2,
      animation: "blink .9s step-end infinite", verticalAlign: "text-bottom",
    }} />
  );
}

const MD_COMPONENTS = {
  h2: ({ children }) => (
    <h2 style={{
      fontFamily: "Plus Jakarta Sans, sans-serif", fontWeight: 700, fontSize: 17,
      color: "var(--tx)", marginTop: 32, marginBottom: 12,
      paddingBottom: 7, borderBottom: "1px solid var(--bd)", letterSpacing: "-.01em",
    }}>{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 style={{
      fontFamily: "Plus Jakarta Sans, sans-serif", fontWeight: 600, fontSize: 12,
      color: "#9b6dff", marginTop: 24, marginBottom: 8,
      textTransform: "uppercase", letterSpacing: ".07em",
    }}>{children}</h3>
  ),
  p: ({ children }) => (
    <p style={{
      fontFamily: "Inter, sans-serif", fontSize: 15, lineHeight: 1.85,
      color: "var(--tx)", marginBottom: 14,
    }}>{children}</p>
  ),
  li: ({ children }) => (
    <li style={{
      fontFamily: "Inter, sans-serif", fontSize: 15, lineHeight: 1.8,
      color: "var(--tx)", marginBottom: 7,
    }}>{children}</li>
  ),
  strong: ({ children }) => (
    <strong style={{ color: "#e2e8f0", fontWeight: 600 }}>{children}</strong>
  ),
  blockquote: ({ children }) => (
    <blockquote style={{
      borderLeft: "3px solid #4f8eff66", paddingLeft: 18,
      margin: "18px 0", color: "var(--mu)", fontStyle: "italic",
      background: "#4f8eff08", borderRadius: "0 6px 6px 0", padding: "8px 8px 8px 18px",
    }}>{children}</blockquote>
  ),
  code: ({ inline, children }) => inline
    ? <code style={{
        background: "var(--s3)", color: "#ffb84f",
        padding: "2px 7px", borderRadius: 5, fontSize: 13,
        fontFamily: "JetBrains Mono, monospace",
      }}>{children}</code>
    : <pre style={{
        background: "var(--s2)", border: "1px solid var(--bd)",
        borderRadius: 8, padding: "14px 20px", overflowX: "auto", marginBottom: 18,
      }}><code style={{
        fontFamily: "JetBrains Mono, monospace", fontSize: 13, color: "#e2e8f0",
      }}>{children}</code></pre>,
  table: ({ children }) => (
    <div style={{ overflowX: "auto", marginBottom: 18 }}>
      <table style={{
        width: "100%", borderCollapse: "collapse", fontSize: 14,
        borderRadius: 8, overflow: "hidden",
      }}>{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th style={{
      background: "var(--s2)", padding: "9px 14px",
      border: "1px solid var(--bd)", textAlign: "left",
      fontFamily: "Inter, sans-serif", fontWeight: 600,
      fontSize: 11, textTransform: "uppercase", letterSpacing: ".05em",
      color: "var(--mu)",
    }}>{children}</th>
  ),
  td: ({ children }) => (
    <td style={{
      padding: "8px 14px", border: "1px solid var(--bd)",
      fontFamily: "Inter, sans-serif", fontSize: 14,
    }}>{children}</td>
  ),
};

export default function SectionExplainer({ paper, onBack }) {
  const sessionId = useStore(s => s.sessionId);
  const { unlockedSections, unlockSection } = useStore(s => ({
    unlockedSections: s.unlockedSections,
    unlockSection:    s.unlockSection,
  }));

  const [active,     setActive]     = useState(null);
  const [cache,      setCache]      = useState({});
  const [streamText, setStreamText] = useState("");
  const [streaming,  setStreaming]  = useState(false);
  const [subTab,     setSubTab]     = useState("explain");
  const [level,      setLevel]      = useState("expert");

  const esRef = useRef(null);

  useEffect(() => () => esRef.current?.close(), []);

  const cacheKey = (secId) => `${secId}:${level}`;

  const openSection = (sec, forceLevel) => {
    const depth = forceLevel ?? level;
    if (!unlockedSections.includes(sec.id)) return;

    esRef.current?.close();
    setActive(sec.id);
    setSubTab("explain");

    const key = `${sec.id}:${depth}`;
    if (cache[key]) {
      setStreamText("");
      setStreaming(false);
      return;
    }

    setStreamText("");
    setStreaming(true);

    const paperId = paper?.id || "";
    let text = "";

    esRef.current = openExplainStream(sessionId, paperId, sec.id, depth, {
      onChunk: (chunk) => {
        text += chunk;
        setStreamText(text);
      },
      onDone: (data) => {
        setCache(c => ({ ...c, [key]: text || " " }));
        (data.unlocked_sections || []).forEach(id => unlockSection(id));
        setStreaming(false);
      },
      onError: (err) => {
        console.error("Explain stream error:", err);
        let errText;
        if (typeof err === "string") {
          const truncated = err.length > 400 ? err.slice(0, 400) + "…" : err;
          errText = `Error: ${truncated}`;
        } else {
          errText = "Error: Connection lost — make sure the backend server is running on port 8000.";
        }
        setStreamText(errText);
        setCache(c => ({ ...c, [key]: errText }));
        setStreaming(false);
      },
    });
  };

  const handleLevelChange = (newLevel) => {
    setLevel(newLevel);
    if (active) {
      const sec = SECTIONS.find(s => s.id === active);
      if (sec) openSection(sec, newLevel);
    }
  };

  const activeSec   = SECTIONS.find(s => s.id === active);
  const displayText = cache[cacheKey(active)] ?? streamText;
  const isError     = displayText?.startsWith("Error:") || displayText?.startsWith("Failed to");

  // Reading progress
  const readCount = SECTIONS.filter(s => {
    const k = `${s.id}:${level}`;
    return !!cache[k] && !cache[k].startsWith("Error") && !cache[k].startsWith("Failed");
  }).length;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "252px 1fr", gap: 16, height: "100%" }}>

      {/* ── Sidebar ── */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <button className="btn bg" onClick={onBack} style={{ fontSize: 12.5, padding: "8px 14px", width: "100%", justifyContent: "flex-start" }}>
          ← Back to papers
        </button>

        {/* Progress */}
        <div className="card" style={{ padding: "12px 14px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <span style={{ fontSize: 10, color: "var(--mu)", fontFamily: "JetBrains Mono, monospace", letterSpacing: ".06em" }}>PROGRESS</span>
            <span style={{ fontSize: 11, fontWeight: 600, color: readCount === SECTIONS.length ? "#22d49a" : "var(--mu)" }}>
              {readCount} / {SECTIONS.length}
            </span>
          </div>
          <div className="pbar-track">
            <div className="pbar-fill" style={{
              width: `${(readCount / SECTIONS.length) * 100}%`,
              background: readCount === SECTIONS.length ? "#22d49a" : "#4f8eff",
            }} />
          </div>
        </div>

        {/* Section list */}
        <div className="card" style={{ padding: "12px 10px", flex: 1 }}>
          <div style={{ fontSize: 10, color: "var(--mu)", marginBottom: 10, paddingLeft: 4, fontFamily: "JetBrains Mono, monospace", letterSpacing: ".06em" }}>
            SECTIONS
          </div>
          {SECTIONS.map(sec => {
            const isU  = unlockedSections.includes(sec.id);
            const isA  = active === sec.id;
            const key  = `${sec.id}:${level}`;
            const isDone = !!cache[key] && !cache[key].startsWith("Error") && !cache[key].startsWith("Failed");
            return (
              <button key={sec.id} onClick={() => openSection(sec)} style={{
                display: "flex", alignItems: "flex-start", gap: 10, width: "100%",
                padding: "10px 10px", borderRadius: 8, border: "none",
                cursor: isU ? "pointer" : "not-allowed",
                background: isA ? "#4f8eff12" : "transparent",
                borderLeft: `2px solid ${isA ? "#4f8eff" : "transparent"}`,
                textAlign: "left", marginBottom: 2,
                opacity: isU ? 1 : 0.35, transition: "all .15s",
              }}>
                <span style={{
                  fontSize: 13, lineHeight: 1,
                  color: isDone ? "#22d49a" : isU ? "#4f8eff" : "var(--mu)",
                  marginTop: 2, flexShrink: 0,
                  fontFamily: "JetBrains Mono, monospace",
                }}>
                  {isDone ? "✓" : isU ? "◎" : "⊗"}
                </span>
                <div style={{ minWidth: 0 }}>
                  <div style={{
                    fontSize: 13, fontWeight: 600,
                    fontFamily: "Inter, sans-serif",
                    color: isA ? "#4f8eff" : isU ? "var(--tx)" : "var(--mu)",
                    marginBottom: 2,
                  }}>
                    {sec.label}
                  </div>
                  {isU && (
                    <div style={{
                      fontSize: 11, color: "var(--mu)", lineHeight: 1.4,
                      fontFamily: "Inter, sans-serif",
                    }}>
                      {sec.desc}
                    </div>
                  )}
                </div>
              </button>
            );
          })}
        </div>

        {/* Legend */}
        <div className="card" style={{ padding: "10px 12px", display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{ fontSize: 10, color: "var(--mu)", fontFamily: "JetBrains Mono, monospace", letterSpacing: ".06em", marginBottom: 2 }}>LEGEND</div>
          {[["#22d49a", "✓", "Read"], ["#4f8eff", "◎", "Available"], ["var(--mu)", "⊗", "Locked"]].map(([col, sym, label]) => (
            <div key={label} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 11, color: col, fontFamily: "JetBrains Mono, monospace" }}>{sym}</span>
              <span style={{ fontSize: 11, color: "var(--mu)", fontFamily: "Inter, sans-serif" }}>{label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Content area ── */}
      <div style={{ display: "flex", flexDirection: "column", overflow: "hidden", height: "100%" }}>
        {!active ? (
          /* Welcome / start card */
          <div className="card fu" style={{
            flex: 1, display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center", gap: 18,
            background: "linear-gradient(160deg, var(--s1) 0%, #162540 100%)",
          }}>
            <div style={{ fontSize: 52, lineHeight: 1 }}>📄</div>
            <div style={{ textAlign: "center", maxWidth: 480 }}>
              <h3 style={{
                fontFamily: "Plus Jakarta Sans, sans-serif", fontWeight: 800,
                fontSize: 22, letterSpacing: "-.02em", marginBottom: 8,
              }}>
                {paper?.title || "Research Paper"}
              </h3>
              {paper?.authors && (
                <p style={{ color: "var(--mu)", fontSize: 14, fontFamily: "Instrument Serif, serif", fontStyle: "italic" }}>
                  {paper.authors}{paper.year ? ` · ${paper.year}` : ""}
                </p>
              )}
            </div>
            <p style={{ color: "var(--mu)", fontSize: 13.5, textAlign: "center", maxWidth: 400, lineHeight: 1.7, fontFamily: "Inter, sans-serif" }}>
              Work through each section in order. Reading a section unlocks the next. Choose your depth level before starting.
            </p>
            <DepthToggle level={level} onChange={setLevel} />
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", justifyContent: "center" }}>
              <button className="btn bp" onClick={() => openSection(SECTIONS[0])}>
                Begin with Abstract →
              </button>
              <button className="btn bg" onClick={() => {}} style={{ fontSize: 12 }}>
                {level === "beginner" ? "🎓 Beginner mode on" : "🔬 Expert mode on"}
              </button>
            </div>
            {/* Section overview chips */}
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "center", maxWidth: 480, marginTop: 4 }}>
              {SECTIONS.map(sec => (
                <span key={sec.id} style={{
                  padding: "4px 10px", borderRadius: 99, fontSize: 11,
                  fontFamily: "Inter, sans-serif", fontWeight: 500,
                  background: "var(--s3)", color: "var(--mu)",
                  border: "1px solid var(--bd)",
                }}>{sec.label}</span>
              ))}
            </div>
          </div>
        ) : (
          <div className="card" style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", padding: 0 }}>

            {/* Section header */}
            <div style={{
              padding: "14px 24px 0",
              background: "linear-gradient(180deg, var(--s2) 0%, var(--s1) 100%)",
              borderBottom: "1px solid var(--bd)",
              flexShrink: 0,
            }}>
              {/* Paper title */}
              <div style={{
                fontSize: 11, color: "var(--mu)", marginBottom: 6,
                fontFamily: "Inter, sans-serif", letterSpacing: ".02em",
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
              }}>
                {paper?.title || "Paper"}{paper?.year ? ` · ${paper.year}` : ""}
              </div>

              {/* Section name + description */}
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
                <div>
                  <h2 style={{
                    fontFamily: "Plus Jakarta Sans, sans-serif", fontWeight: 700,
                    fontSize: 18, letterSpacing: "-.01em", color: "var(--tx)", margin: 0,
                  }}>
                    {activeSec?.label}
                  </h2>
                  <p style={{
                    fontSize: 12, color: "var(--mu)", marginTop: 2,
                    fontFamily: "Inter, sans-serif",
                  }}>
                    {activeSec?.desc}
                  </p>
                </div>
                <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 10 }}>
                  <DepthToggle level={level} onChange={handleLevelChange} />
                </div>
              </div>

              {/* Sub-tabs */}
              <div style={{ display: "flex", gap: 0 }}>
                {[["explain", "Explanation"], ["chat", "Ask Questions"]].map(([id, label]) => (
                  <button key={id} onClick={() => setSubTab(id)} style={{
                    padding: "9px 18px", border: "none", cursor: "pointer",
                    fontFamily: "Inter, sans-serif", fontWeight: 600, fontSize: 13,
                    background: "transparent",
                    color: subTab === id ? "var(--tx)" : "var(--mu)",
                    borderBottom: `2px solid ${subTab === id ? "#4f8eff" : "transparent"}`,
                    transition: "all .15s",
                  }}>{label}</button>
                ))}
              </div>
            </div>

            {subTab === "explain" ? (
              <div className="scroll" style={{ flex: 1, padding: "32px 40px", maxWidth: 880 }}>

                {/* Skeleton */}
                {!displayText && streaming && (
                  <div>
                    <div style={{ marginBottom: 24, display: "flex", flexDirection: "column", gap: 8 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <div style={{
                          width: 10, height: 10, borderRadius: "50%",
                          border: "2px solid rgba(255,255,255,.08)",
                          borderTopColor: "#4f8eff",
                          animation: "spin .7s linear infinite", flexShrink: 0,
                        }} />
                        <span style={{ fontSize: 11, color: "#4f8eff", fontFamily: "JetBrains Mono, monospace", letterSpacing: ".04em" }}>
                          GENERATING EXPLANATION
                        </span>
                      </div>
                      <p style={{ fontSize: 13, color: "var(--mu)", margin: 0, lineHeight: 1.7, paddingLeft: 20, fontFamily: "Inter, sans-serif" }}>
                        Analysing the {activeSec?.label} section — grounding explanation in paper content…
                      </p>
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                      {[100, 80, 95, 65, 88, 72, 100, 60, 85, 75].map((w, i) => (
                        <div key={i} className="skel" style={{ height: 14, width: `${w}%`, animationDelay: `${i * 0.08}s` }} />
                      ))}
                    </div>
                  </div>
                )}

                {/* Error state */}
                {displayText && isError && (
                  <div style={{ padding: "20px 0" }}>
                    <div style={{ background: "#ff6b8a0a", border: "1px solid #ff6b8a28", borderRadius: 10, padding: "18px 22px" }}>
                      <p style={{ fontSize: 11, color: "#ff6b8a", marginBottom: 8, fontFamily: "JetBrains Mono, monospace", letterSpacing: ".04em" }}>
                        STREAM ERROR
                      </p>
                      <p style={{ fontSize: 14, color: "var(--mu)", lineHeight: 1.7, marginBottom: 12, wordBreak: "break-word", fontFamily: "Inter, sans-serif" }}>
                        {displayText.replace(/^Error:\s*/, "")}
                      </p>
                      {(displayText.includes("api_key") || displayText.includes("Incorrect API") || displayText.includes("authentication") || displayText.includes("401")) && (
                        <div style={{ fontSize: 11, color: "#ffb84f", padding: "8px 12px", background: "#ffb84f08", borderRadius: 6, border: "1px solid #ffb84f22", marginBottom: 10, fontFamily: "JetBrains Mono, monospace" }}>
                          ⚠ API key issue — verify OPENAI_API_KEY in backend/.env is valid and not expired.
                        </div>
                      )}
                      {(displayText.includes("Connection lost") || displayText.includes("ECONNREFUSED") || displayText.includes("connect")) && (
                        <div style={{ fontSize: 11, color: "#ffb84f", padding: "8px 12px", background: "#ffb84f08", borderRadius: 6, border: "1px solid #ffb84f22", marginBottom: 10, fontFamily: "JetBrains Mono, monospace" }}>
                          ⚠ Backend offline — run: <span style={{ color: "#4f8eff" }}>uvicorn main:app --reload</span> in the backend folder.
                        </div>
                      )}
                      <button className="btn bg" onClick={() => {
                        setCache(c => { const n = {...c}; delete n[cacheKey(active)]; return n; });
                        openSection(activeSec);
                      }} style={{ fontSize: 12, padding: "7px 14px" }}>
                        Retry
                      </button>
                    </div>
                  </div>
                )}

                {/* Explanation content */}
                {displayText && !isError && (
                  <div className="md-body">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm, remarkMath]}
                      rehypePlugins={[rehypeKatex]}
                      components={MD_COMPONENTS}
                    >
                      {displayText}
                    </ReactMarkdown>
                    {streaming && <StreamingCursor />}
                  </div>
                )}
              </div>
            ) : (
              <div style={{ flex: 1, overflow: "hidden" }}>
                <ChatPanel context={`${paper?.title || ""} — ${activeSec?.label || active} section`} level={level} />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
