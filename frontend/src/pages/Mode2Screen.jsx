/**
 * ResearchMind — Mode 2: Topic Mastery Journey
 * Phases: diagnostic → pipeline → overview → explainer
 */
import React, { useState, useEffect } from "react";
import {
  submitDiagnostic, openPipelineStream,
  downloadExport, getQuiz,
} from "@/lib/api";
import { useStore }        from "@/stores/useStore";
import {
  Tag, PBar, StatusDot, Divider, TopBar, SkeletonLines
} from "@/components/Primitives";
import KnowledgeGraph   from "@/components/KnowledgeGraph";
import ConfidenceQuiz   from "@/components/ConfidenceQuiz";
import SectionExplainer from "@/components/SectionExplainer";
import ChatPanel        from "@/components/ChatPanel";
import toast            from "react-hot-toast";

// ── Diagnostic Quiz ───────────────────────────────────────────────────────────
const DIAG_QS = [
  { q:"Prior machine learning experience?",       opts:["None","Some basics","Intermediate","Advanced"] },
  { q:"Neural network familiarity?",              opts:["Not at all","Heard of them","Know the basics","Used them"] },
  { q:"Linear algebra / calculus comfort?",       opts:["Weak","Rusty","Comfortable","Very strong"] },
  { q:"Prior research paper reading?",            opts:["Never","1-2 papers","Several","Published researcher"] },
  { q:"Primary goal for this session?",           opts:["Understand basics","Build something","Do research","Teach others"] },
];

function DiagnosticPanel({ topic, onDone }) {
  const [qIdx, setQIdx] = useState(0);
  const [sel,  setSel]  = useState(null);
  const [ans,  setAns]  = useState([]);
  const [done, setDone] = useState(false);

  const submit = () => {
    if (sel === null) return;
    const next = [...ans, sel];
    setAns(next);
    if (qIdx + 1 < DIAG_QS.length) { setQIdx(qIdx+1); setSel(null); }
    else { setDone(true); setTimeout(() => onDone(next), 700); }
  };

  if (done) return (
    <div className="fu" style={{ textAlign:"center", padding:"28px 0" }}>
      <div style={{ fontSize:40, marginBottom:10 }}>🧠</div>
      <div style={{ fontWeight:800, fontSize:20, marginBottom:6 }}>Profile built</div>
      <div className="serifi" style={{ color:"var(--mu)", fontSize:14 }}>Launching your personalised journey…</div>
    </div>
  );

  const q = DIAG_QS[qIdx];
  return (
    <div className="fu">
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:16 }}>
        <Tag color="#4f8eff">Question {qIdx+1} / {DIAG_QS.length}</Tag>
        <div style={{ width:120 }}><PBar pct={Math.round(qIdx/DIAG_QS.length*100)} color="#4f8eff"/></div>
      </div>
      <p className="serif" style={{ fontSize:17, lineHeight:1.7, marginBottom:20 }}>{q.q}</p>
      <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
        {q.opts.map((o, i) => (
          <button key={i} onClick={() => setSel(i)} style={{
            textAlign:"left", padding:"11px 15px", borderRadius:10, cursor:"pointer",
            fontFamily:"Instrument Serif,serif", fontSize:14.5, transition:"all .18s",
            background: sel===i ? "#4f8eff14" : "var(--s2)",
            border:`1.5px solid ${sel===i?"#4f8eff":"var(--bd2)"}`,
            color: sel===i ? "var(--tx)" : "var(--mu)",
          }}>
            <span className="mono" style={{ fontSize:10, marginRight:10, opacity:.5 }}>{String.fromCharCode(65+i)}</span>{o}
          </button>
        ))}
      </div>
      <button className="btn bp" onClick={submit} disabled={sel===null} style={{ marginTop:16, width:"100%", padding:"13px" }}>
        Continue →
      </button>
    </div>
  );
}

// ── Pipeline Feed ─────────────────────────────────────────────────────────────
const AGENT_STEPS = [
  { id:"diagnostic",   icon:"◎", label:"Diagnostic Agent",  sub:"Profiling your knowledge baseline" },
  { id:"discovery",    icon:"⊕", label:"Discovery Agent",   sub:"Querying Semantic Scholar · arXiv" },
  { id:"graph_builder",icon:"⬡", label:"Graph Builder",     sub:"Mapping concept dependencies" },
  { id:"scraper",      icon:"⊗", label:"Scraper Agent",     sub:"Fetching prerequisites · YouTube · Wikipedia" },
  { id:"quiz_gen",     icon:"◈", label:"Quiz Agent",        sub:"Generating confidence-check questions" },
];

function PipelineFeed({ agentStatuses }) {
  return (
    <div style={{ display:"flex", flexDirection:"column", gap:7 }}>
      {AGENT_STEPS.map((s, i) => {
        const status = agentStatuses[s.id] || "pending";
        const done   = status === "done";
        const active = status === "running";
        return (
          <div key={s.id} className="fu" style={{
            animationDelay:`${i*.06}s`, display:"flex", alignItems:"center", gap:12,
            padding:"11px 15px", borderRadius:10,
            background: active ? "var(--s2)" : "var(--s1)",
            border:`1px solid ${active?"#4f8eff30":done?"#22d49a1a":"var(--bd)"}`,
            opacity: status==="pending" ? .38 : 1, transition:"all .3s",
          }}>
            <StatusDot done={done} active={active}/>
            <div style={{ flex:1 }}>
              <div style={{ fontSize:13, fontWeight:700, marginBottom:2, color:done?"#22d49a":active?"var(--tx)":"var(--mu)" }}>
                <span className="mono" style={{ fontSize:10, marginRight:8, opacity:.55 }}>{s.icon}</span>{s.label}
              </div>
              <div className="mono" style={{ fontSize:10, color:"var(--mu)" }}>{s.sub}</div>
            </div>
            {active && <div style={{ width:13,height:13,border:"2px solid rgba(255,255,255,.1)",borderTopColor:"#4f8eff",borderRadius:"50%",animation:"spin .7s linear infinite"}}/>}
            {done   && <span style={{ color:"#22d49a", fontSize:14 }}>✓</span>}
          </div>
        );
      })}
    </div>
  );
}

// ── Spaced Repetition ─────────────────────────────────────────────────────────
const SPACED = [
  { concept:"Scaled Dot-Product Attention", due:"1 day",  strength:32 },
  { concept:"Positional Encoding",          due:"3 days", strength:55 },
  { concept:"Multi-Head Attention",         due:"1 day",  strength:28 },
  { concept:"Feed-Forward Sublayer",        due:"6 days", strength:72 },
  { concept:"Encoder–Decoder Stack",        due:"2 days", strength:44 },
];

function SpacedPanel() {
  const [reviewed, setReviewed] = useState([]);
  return (
    <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:4 }}>
        <h4 style={{ fontWeight:800, fontSize:14 }}>🔁 Spaced Repetition</h4>
        <Tag color="#ffb84f">{SPACED.filter((_,i)=>!reviewed.includes(i)).length} due</Tag>
      </div>
      {SPACED.map((c,i) => {
        const done = reviewed.includes(i);
        return (
          <div key={i} style={{ padding:"12px 14px", borderRadius:10, background:"var(--s2)", border:`1px solid ${done?"#22d49a18":"var(--bd)"}`, opacity:done?.5:1, transition:"all .3s" }}>
            <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:8 }}>
              <span style={{ fontWeight:700, fontSize:13 }}>{c.concept}</span>
              <Tag color={done?"#22d49a":"#ffb84f"}>{done?"Done":"Due in "+c.due}</Tag>
            </div>
            <PBar pct={done?100:c.strength} color={done?"#22d49a":"#9b6dff"} label="Memory strength" sub={`${done?100:c.strength}%`}/>
            {!done && (
              <button className="btn be" onClick={() => setReviewed(r=>[...r,i])} style={{ marginTop:9,width:"100%",fontSize:11,padding:"7px" }}>
                Mark reviewed ✓
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Prerequisites Panel ───────────────────────────────────────────────────────
const PREREQS = [
  { concept:"Linear Algebra",   yt:"3Blue1Brown — Essence of Linear Algebra",   topics:"Matrices · Eigenvalues · Vector spaces" },
  { concept:"Calculus",         yt:"3Blue1Brown — Essence of Calculus",          topics:"Derivatives · Chain rule · Gradients" },
  { concept:"Neural Networks",  yt:"Andrej Karpathy — Neural Nets: Zero to Hero",topics:"Backprop · Activations · Loss functions" },
  { concept:"Embeddings",       yt:"Stanford CS224N — Word Vectors",             topics:"Word2Vec · GloVe · Semantic similarity" },
  { concept:"Attention",        yt:"Yannic Kilcher — Attention Is All You Need", topics:"Self-attention · Keys, Queries, Values" },
];

function PrereqPanel() {
  const [open, setOpen] = useState(null);
  const [done, setDone] = useState([]);
  return (
    <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:4 }}>
        <h4 style={{ fontWeight:800, fontSize:14 }}>📚 Prerequisites</h4>
        <Tag color="#22d49a">{done.length}/{PREREQS.length} cleared</Tag>
      </div>
      {PREREQS.map((r, i) => {
        const isDone = done.includes(i);
        const isOpen = open === i;
        return (
          <div key={i} style={{ borderRadius:10, border:`1px solid ${isDone?"#22d49a1a":"var(--bd)"}`, overflow:"hidden", opacity:isDone?.6:1 }}>
            <button onClick={() => setOpen(isOpen?null:i)} style={{ width:"100%", padding:"11px 14px", background:"var(--s2)", border:"none", cursor:"pointer", display:"flex", justifyContent:"space-between", alignItems:"center", color:"var(--tx)", fontFamily:"Cabinet Grotesk,sans-serif", fontWeight:700, fontSize:13 }}>
              <div style={{ display:"flex", alignItems:"center", gap:9 }}>
                <StatusDot done={isDone} active={false}/>
                {r.concept}
              </div>
              <span className="mono" style={{ fontSize:12, color:"var(--mu)" }}>{isOpen?"▲":"▼"}</span>
            </button>
            {isOpen && (
              <div className="fu" style={{ padding:"12px 14px", background:"var(--s1)", borderTop:"1px solid var(--bd)" }}>
                <div className="mono" style={{ fontSize:9, color:"#ff6b8a", marginBottom:5 }}>▶ YOUTUBE</div>
                <div style={{ fontSize:13, color:"var(--tx)", fontWeight:600, marginBottom:10 }}>{r.yt}</div>
                <div className="mono" style={{ fontSize:9, color:"#4f8eff", marginBottom:5 }}>📖 KEY CONCEPTS</div>
                <div className="mono" style={{ fontSize:11, color:"var(--mu)", lineHeight:1.6, marginBottom:12 }}>{r.topics}</div>
                <button className="btn be" onClick={() => { setDone(d=>[...d,i]); setOpen(null); }} style={{ width:"100%", fontSize:12, padding:"8px" }}>Mark understood ✓</button>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Main Mode 2 Screen ────────────────────────────────────────────────────────
export default function Mode2Screen() {
  const {
    sessionId, topic, setScreen,
    mode2Phase, setMode2Phase,
    agentStatuses, setAgentStatus,
    papers, setPapers,
    graph, setGraph,
    quizQuestions, setQuizQuestions,
    quizResult, setQuizResult,
    overallPct, setOverallPct,
    activePaper, setActivePaper,
    setDiagnosticAns,
  } = useStore();

  const [sideTab,  setSideTab]  = useState("graph");
  const [userLevel, setUserLevel] = useState("intermediate");

  const SIDE_TABS = [
    { id:"graph",   label:"⬡ Graph"   },
    { id:"prereq",  label:"📚 Prereqs" },
    { id:"quiz",    label:"◈ Quiz"    },
    { id:"spaced",  label:"🔁 Spaced"  },
    { id:"profile", label:"◎ Profile" },
    { id:"chat",    label:"💬 Chat"   },
  ];

  // ── Diagnostic done → submit + start pipeline SSE ──────────────────────────
  const handleDiagDone = async (answers) => {
    setDiagnosticAns(answers);
    try {
      await submitDiagnostic(sessionId, answers, topic);
    } catch { toast.error("Could not submit diagnostic"); }

    setMode2Phase("pipeline");

    // Mark diagnostic done, start pipeline stream
    setAgentStatus("diagnostic", "done");
    const es = openPipelineStream(
      sessionId,
      (msg) => {
        const { agent_id, status, data } = msg;
        setAgentStatus(agent_id, status);
        if (data?.overall_pct)  setOverallPct(data.overall_pct);
        if (data?.papers)       setPapers(data.papers);
        if (data?.graph)        setGraph(data.graph);
        if (data?.questions)    setQuizQuestions(data.questions);
      },
      (done) => {
        setOverallPct(done.overall_pct || 88);
        setMode2Phase("overview");
      },
      () => {
        toast.error("Pipeline stream error");
        setMode2Phase("overview"); // still proceed
      }
    );
    return () => es?.close();
  };

  // ── Quiz complete ─────────────────────────────────────────────────────────
  const handleQuizComplete = (result) => {
    setQuizResult(result.result || result);
    setOverallPct(result.result?.passed || result.passed ? 92 : 80);
  };

  // ── Phases ────────────────────────────────────────────────────────────────
  if (mode2Phase === "diagnostic") return (
    <div style={{ minHeight:"100vh", display:"flex", flexDirection:"column" }}>
      <TopBar onBack={() => setScreen("home")}>
        <Tag color="#9b6dff" dot>Topic Mastery Journey</Tag>
        <span className="mono" style={{ fontSize:11, color:"var(--mu)" }}>{topic}</span>
      </TopBar>
      <div style={{ flex:1, display:"flex", alignItems:"center", justifyContent:"center", padding:40 }}>
        <div style={{ maxWidth:500, width:"100%" }}>
          <div className="card gvi fu">
            <div className="mono" style={{ fontSize:10, color:"#9b6dff", marginBottom:8, letterSpacing:".06em" }}>STEP 1 OF 4 · DIAGNOSTIC</div>
            <h2 style={{ fontWeight:900, fontSize:22, marginBottom:6 }}>Knowledge check</h2>
            <p className="serifi" style={{ color:"var(--mu)", fontSize:14, marginBottom:24 }}>
              5 quick questions to calibrate your learning path for "{topic}"
            </p>
            <DiagnosticPanel topic={topic} onDone={handleDiagDone}/>
          </div>
        </div>
      </div>
    </div>
  );

  if (mode2Phase === "pipeline") return (
    <div style={{ minHeight:"100vh", display:"flex", flexDirection:"column" }}>
      <TopBar onBack={() => setScreen("home")}>
        <Tag color="#9b6dff" dot>Agents Running</Tag>
        <span className="mono" style={{ fontSize:11, color:"var(--mu)" }}>{topic}</span>
        <div style={{ marginLeft:"auto", width:160 }}>
          <PBar pct={overallPct} color="#9b6dff" label="Overall" sub={`${overallPct}%`}/>
        </div>
      </TopBar>
      <div style={{ flex:1, display:"flex", alignItems:"center", justifyContent:"center", padding:40 }}>
        <div style={{ maxWidth:500, width:"100%" }}>
          <div className="card gvi fu">
            <div className="mono" style={{ fontSize:10, color:"#9b6dff", marginBottom:8, letterSpacing:".06em" }}>STEP 2 OF 4 · PIPELINE</div>
            <h2 style={{ fontWeight:900, fontSize:22, marginBottom:6 }}>Agents at work</h2>
            <p className="serifi" style={{ color:"var(--mu)", fontSize:14, marginBottom:20 }}>
              Building your personalised learning path for "{topic}"
            </p>
            <PipelineFeed agentStatuses={agentStatuses}/>
          </div>
        </div>
      </div>
    </div>
  );

  if (mode2Phase === "explainer") return (
    <div style={{ height:"100vh", display:"flex", flexDirection:"column", overflow:"hidden" }}>
      <TopBar onBack={() => { setActivePaper(null); setMode2Phase("overview"); }} backLabel="← Overview">
        <Tag color="#22d49a" dot>Paper Explainer</Tag>
        {activePaper && <span className="mono" style={{ fontSize:11, color:"var(--mu)" }}>{activePaper.title}</span>}
        <div style={{ marginLeft:"auto", display:"flex", gap:12, alignItems:"center" }}>
          <button className="btn bg" onClick={() => downloadExport(sessionId)} style={{ fontSize:12, padding:"7px 13px" }}>↓ Export PDF</button>
          <div style={{ width:160 }}><PBar pct={overallPct} color="#22d49a" sub={`${overallPct}%`}/></div>
        </div>
      </TopBar>
      <div style={{ flex:1, overflow:"hidden", padding:20 }}>
        {activePaper ? (
          <SectionExplainer paper={activePaper} onBack={() => setActivePaper(null)}/>
        ) : (
          <div style={{ display:"grid", gridTemplateColumns:"repeat(2,1fr)", gap:16, maxWidth:900, margin:"0 auto" }}>
            <div className="card fu" style={{ gridColumn:"1/-1", padding:16, border:"1px solid #22d49a22" }}>
              <div className="mono" style={{ fontSize:9, color:"#22d49a", marginBottom:4 }}>STEP 4 OF 4 · PAPER DEEP-DIVE</div>
              <p className="serifi" style={{ fontSize:14, color:"var(--mu)" }}>
                Quiz passed ({quizResult?.score_pct}%). Select a paper for section-by-section AI walkthrough.
              </p>
            </div>
            {(papers.length ? papers : [
              { id:"1",title:"Attention Is All You Need",authors:"Vaswani et al.",year:2017,citations:87000,tag:"Foundational",color:"#ffb84f" },
              { id:"2",title:"BERT",authors:"Devlin et al.",year:2018,citations:52000,tag:"Essential",color:"#4f8eff" },
              { id:"3",title:"GPT-3",authors:"Brown et al.",year:2020,citations:38000,tag:"Milestone",color:"#9b6dff" },
              { id:"4",title:"ViT",authors:"Dosovitskiy et al.",year:2020,citations:25000,tag:"Extension",color:"#22d49a" },
            ]).map((p,i) => (
              <div key={p.id||i} className="card fu" style={{ cursor:"pointer", border:`1px solid ${p.color||"#4f8eff"}25`, transition:"all .2s" }}
                onClick={() => setActivePaper(p)}>
                <div style={{ display:"flex", justifyContent:"space-between", marginBottom:12 }}>
                  <div style={{ width:30,height:30,borderRadius:8,background:`${p.color||"#4f8eff"}18`,border:`1px solid ${p.color||"#4f8eff"}40`,display:"flex",alignItems:"center",justifyContent:"center" }}>
                    <span className="mono" style={{ fontSize:12,fontWeight:700,color:p.color||"#4f8eff"}}>{i+1}</span>
                  </div>
                  <Tag color={p.color||"#4f8eff"}>{p.tag||"Paper"}</Tag>
                </div>
                <div style={{ fontWeight:800,fontSize:15,marginBottom:4,lineHeight:1.3 }}>{p.title}</div>
                <div className="mono" style={{ fontSize:10,color:"var(--mu)",marginBottom:10 }}>{p.authors} · {p.year}</div>
                <button className="btn bg" style={{ width:"100%",fontSize:12,padding:"8px",color:p.color||"#4f8eff",borderColor:`${p.color||"#4f8eff"}40`}}>
                  Open Section Explainer →
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );

  // ── Overview ──────────────────────────────────────────────────────────────
  const displayPapers = papers.length ? papers : [
    { id:"1",title:"Attention Is All You Need",authors:"Vaswani et al.",year:2017,citations:87000,tag:"Foundational",color:"#ffb84f" },
    { id:"2",title:"BERT: Pre-training Deep Bidirectional Transformers",authors:"Devlin et al.",year:2018,citations:52000,tag:"Essential",color:"#4f8eff" },
    { id:"3",title:"Language Models are Few-Shot Learners (GPT-3)",authors:"Brown et al.",year:2020,citations:38000,tag:"Milestone",color:"#9b6dff" },
    { id:"4",title:"An Image is Worth 16×16 Words (ViT)",authors:"Dosovitskiy et al.",year:2020,citations:25000,tag:"Extension",color:"#22d49a" },
  ];
  const displayNodes = (graph?.nodes?.length ? graph.nodes : [
    { id:0,label:"Linear\nAlgebra",mastered:true, edges:[2,3],rx:.13,ry:.50,r:22 },
    { id:1,label:"Calculus",       mastered:true, edges:[4],  rx:.13,ry:.20,r:22 },
    { id:2,label:"Probability",    mastered:true, edges:[4,5],rx:.32,ry:.33,r:20 },
    { id:3,label:"Embeddings",     mastered:false,edges:[5,6],rx:.32,ry:.68,r:20 },
    { id:4,label:"Neural\nNetworks",mastered:false,edges:[5,6],rx:.50,ry:.18,r:24},
    { id:5,label:"Attention\nMech.",mastered:false,edges:[6,7],rx:.55,ry:.52,r:26},
    { id:6,label:"Transformers",   mastered:false,edges:[7],  rx:.74,ry:.32,r:28 },
    { id:7,label:"BERT / GPT",     mastered:false,edges:[],   rx:.88,ry:.65,r:22 },
  ]);
  const quizPassed = quizResult?.passed || quizResult?.score_pct >= 70;
  const quizScore  = quizResult?.score_pct;

  return (
    <div style={{ height:"100vh", display:"flex", flexDirection:"column", overflow:"hidden" }}>
      <TopBar onBack={() => setScreen("home")}>
        <Tag color="#9b6dff" dot>Step 3 — Overview</Tag>
        <span className="mono" style={{ fontSize:11, color:"var(--mu)" }}>{topic}</span>
        <div style={{ marginLeft:"auto", display:"flex", alignItems:"center", gap:14, flexWrap:"wrap" }}>
          {quizScore != null && <Tag color={quizPassed?"#22d49a":"#ff6b8a"}>Quiz {quizScore}% {quizPassed?"✓":"✗"}</Tag>}
          {quizPassed && (
            <button className="btn be" onClick={() => setMode2Phase("explainer")} style={{ fontSize:13, padding:"8px 16px" }}>
              Paper Explainer →
            </button>
          )}
          <button className="btn bg" onClick={() => downloadExport(sessionId)} style={{ fontSize:12, padding:"7px 13px" }}>↓ Export</button>
          <div style={{ width:180 }}><PBar pct={overallPct} color="#9b6dff" label="Journey" sub={`${overallPct}%`}/></div>
        </div>
      </TopBar>

      <div style={{ flex:1, overflow:"hidden", display:"grid", gridTemplateColumns:"1fr 380px" }}>
        {/* Left — papers */}
        <div className="scroll" style={{ padding:18, display:"flex", flexDirection:"column", gap:14 }}>
          <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center" }}>
            <h2 style={{ fontWeight:900, fontSize:18 }}>📚 Reading Sequence</h2>
            <Tag color="#22d49a">{displayPapers.length} papers curated</Tag>
          </div>

          {displayPapers.map((p, i) => (
            <div key={p.id||i} className="card fu" style={{ animationDelay:`${i*.07}s`, padding:16 }}>
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:10 }}>
                <div style={{ display:"flex", alignItems:"center", gap:9 }}>
                  <div style={{ width:28,height:28,borderRadius:7,background:`${p.color||"#4f8eff"}18`,border:`1px solid ${p.color||"#4f8eff"}40`,display:"flex",alignItems:"center",justifyContent:"center" }}>
                    <span className="mono" style={{ fontSize:12,fontWeight:700,color:p.color||"#4f8eff"}}>{i+1}</span>
                  </div>
                  <Tag color={p.color||"#4f8eff"}>{p.tag||"Paper"}</Tag>
                </div>
                <span className="mono" style={{ fontSize:10,color:"var(--mu)"}}>{p.year}</span>
              </div>
              <div style={{ fontWeight:800,fontSize:15,marginBottom:3,lineHeight:1.35 }}>{p.title}</div>
              <div className="mono" style={{ fontSize:10,color:"var(--mu)",marginBottom:10}}>{p.authors}</div>
              {p.citations > 0 && <PBar pct={Math.min(Math.round(p.citations/1000),100)} color={p.color||"#4f8eff"} label={`${Math.round(p.citations/1000)}k citations`} sub=""/>}
              <div style={{ display:"flex",gap:8,marginTop:12 }}>
                <button className="btn bg" onClick={() => { setActivePaper(p); setMode2Phase("explainer"); }}
                  style={{ flex:1,fontSize:12,padding:"8px",color:p.color||"#4f8eff",borderColor:`${p.color||"#4f8eff"}40`}}>
                  Explain this paper →
                </button>
              </div>
            </div>
          ))}

          {/* Lineage */}
          <div className="card" style={{ padding:16, border:"1px solid #9b6dff22" }}>
            <div className="mono" style={{ fontSize:9,color:"#9b6dff",marginBottom:12,letterSpacing:".06em"}}>CONCEPTUAL LINEAGE</div>
            {[
              ["Attention Is All You Need","Introduced the transformer — self-attention replaces recurrence"],
              ["BERT","Extended with bidirectional pre-training (MLM + NSP)"],
              ["GPT-3","Scaled to 175B params — few-shot emergent capabilities"],
              ["ViT","Applied the same architecture to computer vision"],
            ].map(([t,d],i)=>(
              <div key={i} style={{ padding:"9px 0",borderBottom:i<3?"1px solid var(--bd)":"none"}}>
                <div style={{ fontWeight:700,fontSize:13,marginBottom:3}}>{t}</div>
                <div className="serifi" style={{ fontSize:13,color:"var(--mu)",lineHeight:1.55}}>{d}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Right — side panels */}
        <div style={{ borderLeft:"1px solid var(--bd)",display:"flex",flexDirection:"column",overflow:"hidden"}}>
          <div style={{ display:"flex",borderBottom:"1px solid var(--bd)",flexShrink:0,overflowX:"auto"}}>
            {SIDE_TABS.map(t=>(
              <button key={t.id} onClick={()=>setSideTab(t.id)} style={{
                padding:"10px 13px",border:"none",cursor:"pointer",
                fontFamily:"Geist Mono,monospace",fontSize:10,fontWeight:500,
                background:sideTab===t.id?"var(--s2)":"transparent",
                color:sideTab===t.id?"var(--tx)":"var(--mu)",
                borderBottom:`2px solid ${sideTab===t.id?"#9b6dff":"transparent"}`,
                whiteSpace:"nowrap",flexShrink:0,transition:"all .18s",
              }}>{t.label}</button>
            ))}
          </div>

          <div className="scroll" style={{ flex:1,padding:16 }}>
            {sideTab==="graph" && (
              <div style={{ display:"flex",flexDirection:"column",gap:14}}>
                <div style={{ display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                  <h3 style={{ fontWeight:800,fontSize:15}}>🕸️ Knowledge Graph</h3>
                  <Tag color="#9b6dff">{displayNodes.filter(n=>n.mastered).length}/{displayNodes.length} mastered</Tag>
                </div>
                <KnowledgeGraph nodes={displayNodes}/>
                <div className="card" style={{ padding:14}}>
                  <div className="mono" style={{ fontSize:9,color:"var(--mu)",marginBottom:10,letterSpacing:".06em"}}>PREREQUISITE ORDER</div>
                  {displayNodes.map((n,i)=>(
                    <div key={i} style={{ display:"flex",alignItems:"center",gap:9,padding:"6px 0",borderBottom:i<displayNodes.length-1?"1px solid var(--bd)":"none"}}>
                      <StatusDot done={n.mastered} active={false}/>
                      <span style={{ fontSize:12,flex:1,color:n.mastered?"#22d49a":"var(--mu)",fontWeight:n.mastered?700:400}}>{(n.label||"").replace("\n"," ")}</span>
                      {n.mastered && <Tag color="#22d49a">✓</Tag>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {sideTab==="prereq" && <PrereqPanel/>}

            {sideTab==="quiz" && (
              <div>
                <div style={{ display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:16}}>
                  <h3 style={{ fontWeight:800,fontSize:15}}>🎯 Confidence Check</h3>
                  {quizScore != null && <Tag color={quizPassed?"#22d49a":"#ff6b8a"}>{quizScore}%</Tag>}
                </div>
                {quizScore != null ? (
                  <div style={{ textAlign:"center",padding:"22px 0"}}>
                    <div style={{ fontSize:50,marginBottom:12}}>{quizPassed?"🏆":"🔄"}</div>
                    <div style={{ fontWeight:900,fontSize:26,marginBottom:8}}>{quizScore}%</div>
                    <Tag color={quizPassed?"#22d49a":"#ff6b8a"}>{quizPassed?"PASSED":"RETRY"}</Tag>
                    {quizPassed && (
                      <button className="btn be" onClick={()=>setMode2Phase("explainer")} style={{ marginTop:16,width:"100%",fontSize:13}}>
                        Start Paper Explainer →
                      </button>
                    )}
                  </div>
                ) : (
                  <ConfidenceQuiz
                    questions={quizQuestions.length ? quizQuestions : null}
                    onComplete={handleQuizComplete}
                  />
                )}
              </div>
            )}

            {sideTab==="spaced"  && <SpacedPanel/>}

            {sideTab==="profile" && (
              <div style={{ display:"flex",flexDirection:"column",gap:14}}>
                <div style={{ display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                  <h4 style={{ fontWeight:800,fontSize:14}}>📊 Knowledge Profile</h4>
                  <Tag color="#9b6dff" dot>Adaptive</Tag>
                </div>
                {[
                  { l:"LINEAR ALGEBRA",   p:100, c:"#22d49a" },
                  { l:"CALCULUS",         p:100, c:"#22d49a" },
                  { l:"PROBABILITY",      p:80,  c:"#22d49a" },
                  { l:"NEURAL NETWORKS",  p:50,  c:"#4f8eff" },
                  { l:"ATTENTION MECH.",  p:quizScore?Math.min(quizScore,75):0, c:"#4f8eff" },
                  { l:"TRANSFORMERS",     p:quizPassed?35:0, c:"#9b6dff" },
                ].map(s=>(
                  <PBar key={s.l} pct={s.p} color={s.c} label={s.l} sub={`${s.p}%`}/>
                ))}
                <Divider label="MASTERED CONCEPTS"/>
                <div style={{ display:"flex",flexWrap:"wrap",gap:6}}>
                  {["Linear Algebra","Calculus","Probability"].map(m=><Tag key={m} color="#22d49a">✓ {m}</Tag>)}
                  {quizPassed && <Tag color="#4f8eff">✓ Attention Basics</Tag>}
                </div>
              </div>
            )}

            {sideTab==="chat" && (
              <div style={{ height:520,display:"flex",flexDirection:"column",borderRadius:10,overflow:"hidden",border:"1px solid var(--bd)"}}>
                <ChatPanel context={topic}/>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
