/**
 * ResearchMind — Global State (Zustand)
 */
import { create } from "zustand";

export const useStore = create((set, get) => ({
  // ── Theme ──────────────────────────────────────────────────────────────────
  theme: localStorage.getItem("rm-theme") || "dark",
  setTheme: (t) => { localStorage.setItem("rm-theme", t); set({ theme: t }); },

  // ── OpenAI API key (user-supplied) ─────────────────────────────────────────
  apiKey: localStorage.getItem("rm-api-key") || "",
  setApiKey: (k) => { localStorage.setItem("rm-api-key", k); set({ apiKey: k }); },
  clearApiKey: () => { localStorage.removeItem("rm-api-key"); set({ apiKey: "" }); },

  // ── Navigation ─────────────────────────────────────────────────────────────
  screen: "home",       // home | mode1 | mode2
  setScreen: (s) => set({ screen: s }),

  // ── Session ────────────────────────────────────────────────────────────────
  sessionId:   null,
  query:       "",
  topic:       "",
  setSessionId:(id) => set({ sessionId: id }),
  setQuery:    (q)  => set({ query: q }),
  setTopic:    (t)  => set({ topic: t }),

  // ── Mode 2 pipeline state ──────────────────────────────────────────────────
  agentStatuses:  {},   // { [agentId]: "pending"|"running"|"done"|"failed" }
  activeAgentIdx: -1,
  papers:         [],
  graph:          { nodes: [] },
  quizQuestions:  [],
  quizResult:     null,
  diagnosticAns:  null,
  overallPct:     0,
  unlockedSections: ["abstract", "intro"],

  setAgentStatus: (id, status) =>
    set(s => ({ agentStatuses: { ...s.agentStatuses, [id]: status } })),
  setActiveAgentIdx: (i)    => set({ activeAgentIdx: i }),
  setPapers:         (p)    => set({ papers: p }),
  setGraph:          (g)    => set({ graph: g }),
  setQuizQuestions:  (qs)   => set({ quizQuestions: qs }),
  setQuizResult:     (r)    => set({ quizResult: r }),
  setDiagnosticAns:  (a)    => set({ diagnosticAns: a }),
  setOverallPct:     (p)    => set({ overallPct: p }),
  unlockSection: (id) =>
    set(s => ({
      unlockedSections: s.unlockedSections.includes(id)
        ? s.unlockedSections
        : [...s.unlockedSections, id],
    })),

  // ── Mode 2 phase ───────────────────────────────────────────────────────────
  mode2Phase: "diagnostic",   // diagnostic | pipeline | overview | explainer
  setMode2Phase: (p) => set({ mode2Phase: p }),
  activePaper: null,
  setActivePaper: (p) => set({ activePaper: p }),

  // ── Mode 1 ─────────────────────────────────────────────────────────────────
  mode1Explanation: "",
  mode1Loading:     false,
  setMode1Explanation: (t)  => set({ mode1Explanation: t }),
  setMode1Loading:     (v)  => set({ mode1Loading: v }),

  // ── Reset ──────────────────────────────────────────────────────────────────
  reset: () => set({
    sessionId: null, query: "", topic: "",
    agentStatuses: {}, activeAgentIdx: -1,
    papers: [], graph: { nodes: [] },
    quizQuestions: [], quizResult: null,
    diagnosticAns: null, overallPct: 0,
    unlockedSections: ["abstract","intro"],
    mode2Phase: "diagnostic", activePaper: null,
    mode1Explanation: "", mode1Loading: false,
    screen: "home",
  }),
}));
