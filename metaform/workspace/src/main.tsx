import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { createRenderer } from "./graph";
import { createMockSource } from "./mock";
import { createSimulatedAgent } from "./mock/agent";
import { HOST_MARK, MetaformEvents, MetaformSource, chooseSource } from "./source";
import "./styles.css";

// The host's routes when the host serves this page; otherwise the simulated data, as under
// `npm run dev`. `?mock` always gives the simulated data. The test is in src/source/choose.ts.
const hostMark = document.querySelector(`meta[name="${HOST_MARK}"]`) !== null;
const renderer = createRenderer();
// SIMULATED: no agent service is reachable from the host, so proposals come from the local generator (ARCHITECTURE.md section 3).
const agent = createSimulatedAgent();
const root = document.getElementById("root");
if (root) {
  let app: JSX.Element;
  if (chooseSource(location.search, hostMark) === "host") {
    app = <App source={new MetaformSource()} events={new MetaformEvents()} renderer={renderer} agent={agent} simulated={false} startCommand="metaform gui" />;
  } else {
    // `?first-run` starts with no projects, so onboarding and the simulated intake show (UX section 12).
    const mock = createMockSource({ firstRun: new URLSearchParams(location.search).has("first-run") });
    // The host's own start command when the host serves the mock (`?mock`).
    app = <App source={mock} events={mock} renderer={renderer} agent={agent} simulated={mock.simulated} startCommand={hostMark ? "metaform gui" : "npm run dev"} />;
  }
  createRoot(root).render(<StrictMode>{app}</StrictMode>);
}
