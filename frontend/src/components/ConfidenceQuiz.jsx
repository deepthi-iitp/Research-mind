/**
 * ResearchMind — Confidence Quiz
 */
import React, { useState } from "react";
import { submitQuiz } from "@/lib/api";
import { useStore }   from "@/stores/useStore";
import { Tag, PBar }  from "./Primitives";

export default function ConfidenceQuiz({ questions, onComplete }) {
  const sessionId = useStore(s => s.sessionId);
  const [qIdx,     setQIdx]     = useState(0);
  const [sel,      setSel]      = useState(null);
  const [submitted,setSubmitted]= useState(false);
  const [answers,  setAnswers]  = useState([]);   // selected option indices
  const [boolAns,  setBoolAns]  = useState([]);   // correct/wrong booleans
  const [done,     setDone]     = useState(false);
  const [loading,  setLoading]  = useState(false);

  if (!questions || questions.length === 0) {
    return (
      <div style={{ textAlign:"center", padding:"24px 0", color:"var(--mu)" }}>
        <p className="serifi">No questions available yet.</p>
      </div>
    );
  }

  const q = questions[qIdx];

  const handleSubmit = async () => {
    if (sel === null) return;
    setSel(sel); setSubmitted(true);

    const nextAnswers  = [...answers, sel];
    const nextBoolAns  = [...boolAns, sel === q.correct];

    setAnswers(nextAnswers);
    setBoolAns(nextBoolAns);

    setTimeout(async () => {
      if (qIdx + 1 < questions.length) {
        setQIdx(qIdx+1); setSel(null); setSubmitted(false);
      } else {
        setDone(true);
        setLoading(true);
        try {
          const result = await submitQuiz(sessionId, nextAnswers);
          onComplete(result);
        } catch {
          const pct = Math.round(nextBoolAns.filter(Boolean).length / nextBoolAns.length * 100);
          onComplete({ result:{ score_pct:pct, passed:pct>=70, answers:nextBoolAns }, weak_spots:{}, passed:pct>=70 });
        }
        setLoading(false);
      }
    }, 1700);
  };

  if (done) {
    const pct = Math.round(boolAns.filter(Boolean).length / boolAns.length * 100);
    return (
      <div className="fu" style={{ textAlign:"center", padding:"28px 0" }}>
        <div style={{ fontSize:46, marginBottom:10 }}>{pct>=70?"🎯":"📚"}</div>
        <div style={{ fontWeight:900, fontSize:28, marginBottom:8 }}>{pct}%</div>
        <Tag color={pct>=70?"#22d49a":"#ff6b8a"}>
          {loading ? "Submitting…" : pct>=70 ? "PASSED" : "NEEDS REVIEW"}
        </Tag>
        <p className="serifi" style={{ marginTop:14, color:"var(--mu)", fontSize:14 }}>
          {pct>=70 ? "Unlocking paper deep-dive…" : "Revisiting weak prerequisite concepts…"}
        </p>
      </div>
    );
  }

  return (
    <div className="fu">
      {/* Header */}
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:12 }}>
        <Tag color="#ffb84f">Q {qIdx+1} / {questions.length}</Tag>
        <div style={{ display:"flex", gap:5 }}>
          {boolAns.map((ok,i)=>(
            <div key={i} style={{ width:18,height:4,borderRadius:99, background:ok?"#22d49a":"#ff6b8a"}}/>
          ))}
        </div>
        <div style={{ width:100 }}>
          <PBar pct={Math.round(qIdx/questions.length*100)} color="#ffb84f"/>
        </div>
      </div>

      <p className="serif" style={{ fontSize:16.5, lineHeight:1.75, marginBottom:20, color:"var(--tx)" }}>
        {q.q}
      </p>

      <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
        {(q.opts||[]).map((opt, i) => {
          let bg = "var(--s2)", border = "var(--bd2)", color = "var(--mu)";
          if (sel===i && !submitted)              { bg="#4f8eff14"; border="#4f8eff"; color="var(--tx)"; }
          if (submitted && i===q.correct)         { bg="#22d49a12"; border="#22d49a"; color="#22d49a"; }
          if (submitted && sel===i && sel!==q.correct) { bg="#ff6b8a12"; border="#ff6b8a"; color="#ff6b8a"; }
          return (
            <button key={i} onClick={() => !submitted && setSel(i)} style={{
              textAlign:"left", padding:"11px 15px", borderRadius:10, cursor:submitted?"default":"pointer",
              fontFamily:"Instrument Serif,serif", fontSize:14.5, transition:"all .18s",
              background:bg, border:`1.5px solid ${border}`, color,
            }}>
              <span className="mono" style={{ fontSize:10, marginRight:10, opacity:.45 }}>
                {String.fromCharCode(65+i)}
              </span>
              {opt}
              {submitted && i===q.correct && <span style={{ float:"right" }}>✓</span>}
            </button>
          );
        })}
      </div>

      {submitted && q.explain && (
        <div className="fu" style={{
          marginTop:12, padding:"11px 14px", borderRadius:10,
          background: sel===q.correct ? "#22d49a0c" : "#ff6b8a0c",
          border: `1px solid ${sel===q.correct ? "#22d49a22":"#ff6b8a22"}`,
        }}>
          <span className="mono" style={{ fontSize:9, color:sel===q.correct?"#22d49a":"#ff6b8a", marginRight:8 }}>
            {sel===q.correct?"CORRECT":"INCORRECT"}
          </span>
          <span className="serifi" style={{ fontSize:13, color:"var(--mu)", lineHeight:1.65 }}>
            {q.explain}
          </span>
        </div>
      )}

      {!submitted && (
        <button className="btn bp" onClick={handleSubmit} disabled={sel===null}
          style={{ marginTop:16, width:"100%", padding:"13px" }}>
          Submit Answer
        </button>
      )}
    </div>
  );
}
