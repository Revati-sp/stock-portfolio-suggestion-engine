import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import StrategySelector from "./components/StrategySelector";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <main className="mx-auto flex min-h-screen max-w-5xl items-start bg-white px-6 py-10">
      <StrategySelector />
    </main>
  </StrictMode>,
);
