/**
 * ResearchMind — Chat Panel
 * Supports Standard / Socratic / Devil's Advocate modes.
 */
import React, { useState, useRef, useEffect } from "react";
import { sendChat } from "@/lib/api";
import { Spinner } from "./Primitives";
import { useStore } from "@/stores/useStore";

const MODES = [
  { id:"standard", label:"Standard",         col:"#4f8eff", desc:"Direct answers with citations" },
  { id:"socratic",  label:"Socratic",          col:"#9b6dff", desc:"I guide you to the answer" },
  { id:"devil",     label:"Devil's Advocate",  col:"#ff6b8a", desc:"I challenge every claim" },
];

export default function ChatPanel({ context = "" }) {
  const sessionId = useStore(s => s.sessionId);
  const [msgs,    setMsgs]    = useState([]);
  const [input,   setInput]   = useState("");
  const [loading, setLoading] = useState(false);
  const [mode,    setMode]    = useState("standard");
  const endRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior:"smooth" }); }, [msgs]);

  const send = async () => {
    if (!input.trim() || loading || !sessionId) return;
    const text = input.trim();
    setMsgs(m => [...m, { role:"user", content:text }]);
    setInput(""); setLoading(true);
    try {
      const { reply } = await sendChat(sessionId, text, mode, context);
      setMsgs(m => [...m, { role:"assistant", content:reply }]);
    } catch {
      setMsgs(m => [...m, { role:"assistant", content:"Error reaching server. Please try again." }]);
    }
    setLoading(false);
  };

  const mc = MODES.find(m=>m.id===mode).col;

  return (
    <div style={{ display:"flex", flexDirection:"column", height:"100%" }}>
      {/* Mode selector */}
      <div style={{ padding:"8px 12px", borderBottom:"1px solid var(--bd)", display:"flex", gap:6, flexShrink:0 }}>
        {MODES.map(m => (
          <button key={m.id} onClick={() => setMode(m.id)} style={{
            padding:"4px 11px", borderRadius:99, border:"none", cursor:"pointer",
            fontFamily:"Cabinet Grotesk,sans-serif", fontWeight:700, fontSize:11,
            background: mode===m.id ? m.col : "var(--s3)",
            color:      mode===m.id ? "#fff" : "var(--mu)",
            transition:"all .18s",
          }}>{m.label}</button>
        ))}
      </div>
      <div style={{ padding:"5px 12px", background:"var(--s2)", borderBottom:"1px solid var(--bd)", flexShrink:0 }}>
        <span className="mono" style={{ fontSize:10, color:mc }}>
          {MODES.find(m=>m.id===mode).desc}
        </span>
      </div>

      {/* Messages */}
      <div className="scroll" style={{ flex:1, padding:12, display:"flex", flexDirection:"column", gap:11 }}>
        {msgs.length === 0 && (
          <div style={{ flex:1, display:"flex", alignItems:"center", justifyContent:"center", minHeight:80 }}>
            <p className="serifi" style={{ color:"var(--mu)", fontSize:13, textAlign:"center" }}>
              Ask anything — I'm ready to help.
            </p>
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className="fu" style={{
            display:"flex", gap:9,
            flexDirection: m.role==="user" ? "row-reverse" : "row",
            alignItems:"flex-end",
          }}>
            <div style={{
              width:26, height:26, borderRadius:"50%", flexShrink:0,
              display:"flex", alignItems:"center", justifyContent:"center", fontSize:11,
              background: m.role==="user" ? "#ff6b8a1a" : `${mc}1a`,
              border:     `1px solid ${m.role==="user" ? "#ff6b8a40" : mc+"40"}`,
            }}>
              {m.role==="user" ? "U" : "◎"}
            </div>
            <div style={{
              maxWidth:"80%", padding:"10px 14px", borderRadius:10,
              fontSize:13.5, lineHeight:1.75, fontFamily:"Instrument Serif,serif",
              color:"var(--tx)", whiteSpace:"pre-wrap",
              background: m.role==="user" ? "var(--s2)" : "var(--s1)",
              border: `1px solid ${m.role==="user" ? "var(--bd)" : mc+"20"}`,
            }}>
              {m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ display:"flex", gap:8, alignItems:"center" }}>
            <div style={{ width:26,height:26,borderRadius:"50%",flexShrink:0,display:"flex",alignItems:"center",justifyContent:"center",background:`${mc}1a`,border:`1px solid ${mc}40`,fontSize:11 }}>◎</div>
            <div style={{ display:"flex", gap:4 }}>
              {[0,1,2].map(j=>(
                <div key={j} style={{ width:5,height:5,borderRadius:"50%",background:mc,animation:`pulse .9s ${j*.2}s ease infinite`}}/>
              ))}
            </div>
          </div>
        )}
        <div ref={endRef}/>
      </div>

      {/* Input */}
      <div style={{ padding:10, borderTop:"1px solid var(--bd)", display:"flex", gap:8, flexShrink:0 }}>
        <input
          className="inp"
          value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key==="Enter" && !e.shiftKey && send()}
          placeholder="Ask anything…"
          style={{ fontSize:13, padding:"9px 13px" }}
        />
        <button className="btn bp" onClick={send} disabled={loading||!input.trim()||!sessionId}
          style={{ padding:"9px 15px", flexShrink:0 }}>
          {loading ? <Spinner size={13} color="#fff"/> : "↑"}
        </button>
      </div>
    </div>
  );
}
