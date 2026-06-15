/**
 * ResearchMind — Knowledge Graph (Canvas)
 */
import React, { useEffect, useRef, useState, useCallback } from "react";

export default function KnowledgeGraph({ nodes = [] }) {
  const canvasRef = useRef(null);
  const hovRef    = useRef(-1);
  const rafRef    = useRef(null);
  const [tip, setTip] = useState(null);

  useEffect(() => {
    if (!nodes.length) return;
    const canvas = canvasRef.current;
    const ctx    = canvas.getContext("2d");

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      canvas.width  = canvas.offsetWidth  * dpr;
      canvas.height = canvas.offsetHeight * dpr;
      ctx.scale(dpr, dpr);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    const px = n => n.rx * canvas.offsetWidth;
    const py = n => n.ry * canvas.offsetHeight;

    const draw = () => {
      const W = canvas.offsetWidth, H = canvas.offsetHeight;
      ctx.clearRect(0, 0, W, H);

      // Edges
      nodes.forEach(n => {
        (n.edges || []).forEach(eid => {
          const t = nodes[eid]; if (!t) return;
          const ax = px(n), ay = py(n), bx = px(t), by = py(t);
          ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(bx, by);
          ctx.strokeStyle = n.mastered && t.mastered ? "#22d49a22" : "#4f8eff1a";
          ctx.lineWidth = 1.5; ctx.setLineDash([4,6]); ctx.stroke(); ctx.setLineDash([]);
          // Arrow
          const dx = bx-ax, dy = by-ay, len = Math.hypot(dx,dy);
          const ux = dx/len, uy = dy/len;
          const r2 = (t.r || 20) + 3;
          const tx2 = bx - ux*r2, ty2 = by - uy*r2;
          const perp = 5;
          ctx.beginPath();
          ctx.moveTo(tx2, ty2);
          ctx.lineTo(tx2 - ux*8 + (-uy*perp), ty2 - uy*8 + (ux*perp));
          ctx.lineTo(tx2 - ux*8 - (-uy*perp), ty2 - uy*8 - (ux*perp));
          ctx.closePath();
          ctx.fillStyle = n.mastered && t.mastered ? "#22d49a35" : "#4f8eff28";
          ctx.fill();
        });
      });

      // Nodes
      nodes.forEach((n, i) => {
        const x = px(n), y = py(n);
        const hov = hovRef.current === i;
        const r   = (n.r || 20) + (hov ? 4 : 0);
        const col = n.mastered ? "#22d49a" : "#4f8eff";

        if (hov) {
          const g = ctx.createRadialGradient(x, y, r-2, x, y, r+14);
          g.addColorStop(0, col+"50"); g.addColorStop(1, "transparent");
          ctx.beginPath(); ctx.arc(x, y, r+14, 0, Math.PI*2);
          ctx.fillStyle = g; ctx.fill();
        }

        const grd = ctx.createRadialGradient(x, y - r*.25, r*.1, x, y, r);
        grd.addColorStop(0, col+"55"); grd.addColorStop(1, col+"18");
        ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI*2);
        ctx.fillStyle = grd; ctx.fill();
        ctx.strokeStyle = col + (hov ? "ff" : "88");
        ctx.lineWidth = hov ? 2 : 1.5; ctx.stroke();

        ctx.textAlign = "center"; ctx.textBaseline = "middle";
        if (n.mastered) {
          ctx.font = `bold ${r*.75}px Cabinet Grotesk, sans-serif`;
          ctx.fillStyle = "#22d49a";
          ctx.fillText("✓", x, y);
        } else {
          ctx.font = `600 ${r*.6}px Geist Mono, monospace`;
          ctx.fillStyle = col+"cc";
          ctx.fillText(String(i+1), x, y);
        }

        ctx.font = "500 9.5px Geist Mono, monospace";
        ctx.fillStyle = n.mastered ? "#22d49acc" : hov ? col : "#6b6b9a";
        const lines = (n.label || "").split("\n");
        lines.forEach((ln, li) => ctx.fillText(ln, x, y + r + 11 + li*12));
      });

      rafRef.current = requestAnimationFrame(draw);
    };
    draw();
    return () => { cancelAnimationFrame(rafRef.current); ro.disconnect(); };
  }, [nodes]);

  const onMove = useCallback((e) => {
    const rect = canvasRef.current.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    const W = canvasRef.current.offsetWidth, H = canvasRef.current.offsetHeight;
    const hit = nodes.findIndex(n =>
      Math.hypot(n.rx*W - mx, n.ry*H - my) < (n.r||20) + 6
    );
    hovRef.current = hit;
    setTip(hit >= 0 ? { x:mx, y:my, n:nodes[hit] } : null);
  }, [nodes]);

  return (
    <div style={{ position:"relative", borderRadius:12, overflow:"hidden", border:"1px solid var(--bd)" }}>
      <canvas
        ref={canvasRef}
        onMouseMove={onMove}
        onMouseLeave={() => { hovRef.current = -1; setTip(null); }}
        style={{ width:"100%", height:270, display:"block", cursor: tip ? "pointer" : "default" }}
      />
      {tip && (
        <div style={{
          position:"absolute", left:tip.x+12, top:tip.y-8, pointerEvents:"none",
          background:"var(--s1)", border:"1px solid var(--bd2)", borderRadius:8,
          padding:"6px 12px", fontSize:12, fontFamily:"Geist Mono,monospace", zIndex:10, whiteSpace:"nowrap",
        }}>
          <div style={{ fontWeight:600 }}>{(tip.n.label||"").replace("\n"," ")}</div>
          <div style={{ fontSize:10, color: tip.n.mastered ? "#22d49a" : "var(--mu)", marginTop:2 }}>
            {tip.n.mastered ? "✓ Mastered" : "Not yet mastered"}
          </div>
        </div>
      )}
      <div style={{ position:"absolute", bottom:8, right:10, display:"flex", gap:10 }}>
        {[["#22d49a","Mastered"],["#4f8eff","To learn"]].map(([c,l])=>(
          <div key={l} style={{ display:"flex", alignItems:"center", gap:4 }}>
            <div style={{ width:6, height:6, borderRadius:"50%", background:c }}/>
            <span className="mono" style={{ fontSize:9, color:"var(--mu)" }}>{l}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
