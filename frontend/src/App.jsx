/**
 * ResearchMind — Root App
 */
import React, { useEffect, useState } from "react";
import { Toaster } from "react-hot-toast";
import { useStore } from "@/stores/useStore";
import HomeScreen   from "@/pages/HomeScreen";
import Mode1Screen  from "@/pages/Mode1Screen";
import Mode2Screen  from "@/pages/Mode2Screen";
import ApiKeyModal  from "@/components/ApiKeyModal";

export default function App() {
  const screen     = useStore(s => s.screen);
  const theme      = useStore(s => s.theme);
  const setTheme   = useStore(s => s.setTheme);
  const apiKey     = useStore(s => s.apiKey);

  // Show modal if no key and user hasn't explicitly skipped
  const [showKeyModal, setShowKeyModal] = useState(
    !apiKey && !localStorage.getItem("rm-key-skipped")
  );

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const isLight = theme === "light";

  return (
    <>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: isLight ? "#ffffff" : "#1f1f2e",
            color:      isLight ? "#0f172a" : "#dcdcf0",
            border:     `1px solid ${isLight ? "rgba(0,0,0,.12)" : "rgba(255,255,255,.1)"}`,
            fontFamily: "Inter, sans-serif",
            fontSize:   "12px",
          },
        }}
      />

      {/* Fixed toolbar — top-right */}
      <div style={{
        position: "fixed", top: 14, right: 16, zIndex: 9999,
        display: "flex", gap: 8,
      }}>
        {/* API key button */}
        <button
          onClick={() => setShowKeyModal(true)}
          title={apiKey ? "Change OpenAI API key" : "Set OpenAI API key"}
          style={{
            width: 36, height: 36, borderRadius: "50%",
            background: apiKey ? "#22d49a18" : "#ff6b8a18",
            border: `1px solid ${apiKey ? "#22d49a40" : "#ff6b8a40"}`,
            cursor: "pointer", display: "flex", alignItems: "center",
            justifyContent: "center", fontSize: 15, transition: "all .2s",
          }}
        >
          {apiKey ? "🔑" : "⚠️"}
        </button>

        {/* Theme toggle */}
        <button
          onClick={() => setTheme(isLight ? "dark" : "light")}
          title={isLight ? "Switch to dark mode" : "Switch to light mode"}
          style={{
            width: 36, height: 36, borderRadius: "50%",
            background: "var(--s2)", border: "1px solid var(--bd2)",
            cursor: "pointer", display: "flex", alignItems: "center",
            justifyContent: "center", fontSize: 16, transition: "all .2s",
            color: "var(--tx)",
          }}
        >
          {isLight ? "🌙" : "☀️"}
        </button>
      </div>

      {showKeyModal && <ApiKeyModal onClose={() => setShowKeyModal(false)} />}

      {screen === "home"  && <HomeScreen/>}
      {screen === "mode1" && <Mode1Screen/>}
      {screen === "mode2" && <Mode2Screen/>}
    </>
  );
}
