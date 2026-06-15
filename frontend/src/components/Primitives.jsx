/**
 * ResearchMind — Shared UI Primitives
 */
import React from "react";

export function Spinner({ size = 16, color = "#4f8eff" }) {
  return (
    <span style={{
      display: "inline-block", width: size, height: size, flexShrink: 0,
      border: "2px solid rgba(255,255,255,.1)", borderTopColor: color,
      borderRadius: "50%", animation: "spin .7s linear infinite",
    }}/>
  );
}

export function Tag({ children, color = "#4f8eff", dot = false, style: s = {} }) {
  return (
    <span className="tag" style={{
      background: `${color}1a`, color, border: `1px solid ${color}30`, ...s,
    }}>
      {dot && (
        <span style={{ width:5, height:5, borderRadius:"50%", background:color, flexShrink:0 }}/>
      )}
      {children}
    </span>
  );
}

export function PBar({ pct = 0, color = "#4f8eff", label, sub, height = 5 }) {
  return (
    <div>
      {(label || sub) && (
        <div style={{ display:"flex", justifyContent:"space-between", marginBottom:5 }}>
          {label && <span className="mono" style={{ fontSize:10, color:"var(--mu)", letterSpacing:".04em" }}>{label}</span>}
          {sub   && <span className="mono" style={{ fontSize:10, color }}>{sub}</span>}
        </div>
      )}
      <div className="pbar-track" style={{ height }}>
        <div className="pbar-fill" style={{ width:`${pct}%`, background:`linear-gradient(90deg,${color}bb,${color})` }}/>
      </div>
    </div>
  );
}

export function StatusDot({ done, active, color = "#4f8eff" }) {
  return (
    <div style={{
      width: 8, height: 8, borderRadius: "50%", flexShrink: 0,
      background: done ? "#22d49a" : active ? color : "var(--fa)",
      boxShadow:  active ? `0 0 10px ${color}` : "none",
      animation:  active ? "pulse 1.4s ease infinite" : "none",
      transition: "all .3s",
    }}/>
  );
}

export function Divider({ label }) {
  return (
    <div style={{ display:"flex", alignItems:"center", gap:10, margin:"4px 0" }}>
      <div style={{ flex:1, height:1, background:"var(--bd)" }}/>
      {label && <span className="mono" style={{ fontSize:9, color:"var(--mu)", letterSpacing:".08em" }}>{label}</span>}
      <div style={{ flex:1, height:1, background:"var(--bd)" }}/>
    </div>
  );
}

export function SkeletonLines({ n = 7 }) {
  const ws = [100,80,95,65,88,72,100,60,85,90];
  return (
    <div style={{ display:"flex", flexDirection:"column", gap:12 }}>
      {Array.from({ length: n }).map((_, i) => (
        <div key={i} className="skel" style={{ height:14, width:`${ws[i % ws.length]}%`, animationDelay:`${i*.1}s` }}/>
      ))}
    </div>
  );
}

export function TopBar({ children, onBack, backLabel = "← Home" }) {
  return (
    <div style={{
      padding: "12px 20px", borderBottom: "1px solid var(--bd)",
      display: "flex", alignItems: "center", gap: 12, flexShrink: 0, flexWrap: "wrap",
    }}>
      {onBack && (
        <button className="btn bg" onClick={onBack} style={{ fontSize:12, padding:"7px 13px" }}>
          {backLabel}
        </button>
      )}
      {children}
    </div>
  );
}
