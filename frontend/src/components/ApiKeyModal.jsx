/**
 * ResearchMind — API Key Modal
 * Prompts the user for their OpenAI key on first visit.
 * Key is stored in localStorage and sent as X-OpenAI-Key on every request.
 */
import React, { useState } from "react";
import { useStore } from "@/stores/useStore";

export default function ApiKeyModal({ onClose }) {
  const { setApiKey } = useStore();
  const [input,   setInput]   = useState("");
  const [visible, setVisible] = useState(false);
  const [error,   setError]   = useState("");

  const save = () => {
    const trimmed = input.trim();
    if (!trimmed.startsWith("sk-")) {
      setError("Key should start with sk-");
      return;
    }
    setApiKey(trimmed);
    onClose();
  };

  const skip = () => {
    localStorage.setItem("rm-key-skipped", "1");
    onClose();
  };

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 10000,
      background: "rgba(0,0,0,.72)", backdropFilter: "blur(6px)",
      display: "flex", alignItems: "center", justifyContent: "center",
      padding: 20,
    }}>
      <div className="card fu" style={{ maxWidth: 480, width: "100%", padding: 32 }}>
        {/* Icon */}
        <div style={{
          width: 44, height: 44, borderRadius: 12,
          background: "#4f8eff18", border: "1px solid #4f8eff40",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 22, marginBottom: 20,
        }}>🔑</div>

        <h2 style={{ fontWeight: 900, fontSize: 20, marginBottom: 6 }}>
          Enter your OpenAI API Key
        </h2>
        <p className="serifi" style={{ color: "var(--mu)", fontSize: 14, lineHeight: 1.7, marginBottom: 24 }}>
          ResearchMind uses OpenAI to power its AI agents. Your key is stored
          only in your browser and is sent directly to the backend — we never
          store or log it on our servers.
        </p>

        {/* Input */}
        <div style={{ position: "relative", marginBottom: 6 }}>
          <input
            className="inp"
            type={visible ? "text" : "password"}
            placeholder="sk-proj-..."
            value={input}
            onChange={e => { setInput(e.target.value); setError(""); }}
            onKeyDown={e => e.key === "Enter" && save()}
            style={{ paddingRight: 44, fontFamily: "JetBrains Mono, monospace", fontSize: 13 }}
            autoFocus
          />
          <button
            onClick={() => setVisible(v => !v)}
            style={{
              position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)",
              background: "none", border: "none", cursor: "pointer",
              color: "var(--mu)", fontSize: 15, padding: 4,
            }}
          >
            {visible ? "🙈" : "👁"}
          </button>
        </div>
        {error && (
          <p className="mono" style={{ fontSize: 11, color: "var(--ro)", marginBottom: 12 }}>{error}</p>
        )}

        <a
          href="https://platform.openai.com/api-keys"
          target="_blank"
          rel="noreferrer"
          className="mono"
          style={{ fontSize: 11, color: "var(--az)", display: "block", marginBottom: 20 }}
        >
          Get a key at platform.openai.com/api-keys →
        </a>

        {/* Actions */}
        <div style={{ display: "flex", gap: 10 }}>
          <button
            className="btn bp"
            onClick={save}
            disabled={!input.trim()}
            style={{ flex: 1, padding: "12px" }}
          >
            Save & Continue
          </button>
          <button
            className="btn bg"
            onClick={skip}
            style={{ padding: "12px 16px", fontSize: 12 }}
          >
            Skip
          </button>
        </div>

        <p className="mono" style={{ fontSize: 10, color: "var(--mu)", textAlign: "center", marginTop: 14, lineHeight: 1.6 }}>
          Your key is never sent to anyone except OpenAI's API.
          You can update it later via the ⚙ button on the home screen.
        </p>
      </div>
    </div>
  );
}
