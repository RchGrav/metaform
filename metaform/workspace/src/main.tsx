import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { createRenderer } from "./graph";
import { createMockSource } from "./mock";
import "./styles.css";

// The prototype runs on simulated data until the host routes exist (seam doc, Transport).
// `?first-run` starts with no projects, so onboarding and the simulated intake show (UX section 12).
const source = createMockSource({ firstRun: new URLSearchParams(location.search).has("first-run") });
const renderer = createRenderer();
const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <App source={source} events={source} renderer={renderer} simulated={source.simulated} startCommand="npm run dev" />
    </StrictMode>,
  );
}
