import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import StrategySelector from "./components/StrategySelector";
import StreamlitStrategySelector from "./StreamlitStrategySelector";
import "./index.css";

const root = document.getElementById("root");

if (!root) {
  throw new Error("Missing #root element");
}

const isStreamlitEmbed = window.parent !== window;

if (isStreamlitEmbed) {
  document.documentElement.classList.add("streamlit-embed");
  document.body.classList.add("streamlit-embed");
}

createRoot(root).render(
  isStreamlitEmbed ? (
    <StreamlitStrategySelector />
  ) : (
    <StrictMode>
      <main className="mx-auto flex min-h-screen max-w-6xl items-start bg-white px-6 py-10">
        <StrategySelector />
      </main>
    </StrictMode>
  ),
);
