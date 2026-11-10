// The graph's own styles, scoped to .mf-graph. Dark first, with a light theme (UX section 2).
// Text contrast targets 4.5:1 and marks 3:1 against the canvas (WCAG 2.2 AA); the values are
// checked in the verification step, not assumed. The shell may override any --mf- token.

export const GRAPH_CSS = `
.mf-graph {
  /* The dark theme of the earlier Metaform map (its "space" theme): a near-black ground, quiet
     boxes and lines, and two signal colours kept for selection. */
  --mf-canvas: #020408; --mf-node: #10151c; --mf-node-line: #67778d; --mf-ink: #f5f7fa;
  --mf-muted: #9aa2ad; --mf-edge: #67778d; --mf-accent: #53a0ff; --mf-focus: #ffbe55;
  --mf-signal: #00fdea; --mf-node-selected: #003833; --mf-spark: #ffffff; --mf-record: #ffbe55;
  --mf-definitive: #f5f7fa; --mf-container: #080d13; --mf-separator: #4a5463;
  --mf-definitive-role: #ffffff; --mf-supportive: #57c08a; --mf-notable: #c99be8; --mf-divergent: #ef7a6b; --mf-none: #59636f;
  --mf-l0: #6ea2ff; --mf-l1: #57c08a; --mf-l2: #e3a541; --mf-l3: #c99be8;
  --mf-l4: #4fc1c9; --mf-l5: #ef7a6b; --mf-l6: #b8c25a; --mf-l7: #e889b8;
  display: block; background: var(--mf-canvas); font: 500 12px/1.2 "IBM Plex Sans", system-ui, sans-serif;
  user-select: none; touch-action: none; cursor: grab;
}
@media (prefers-color-scheme: light) {
  :root:not([data-theme="dark"]) .mf-graph {
    --mf-canvas: #f6f7f9; --mf-node: #ffffff; --mf-node-line: #b9c1cc; --mf-ink: #1b1f24;
    --mf-muted: #56606d; --mf-edge: #6b7584; --mf-accent: #2f6fed; --mf-focus: #a35f00;
    --mf-signal: #007a70; --mf-node-selected: #d6f5f1; --mf-spark: #1b1f24; --mf-record: #a35f00;
    --mf-definitive: #1b1f24; --mf-container: #eef1f5; --mf-separator: #8a94a3;
    --mf-definitive-role: #2f6fed; --mf-supportive: #1f8a4c; --mf-notable: #8a4fb3; --mf-divergent: #c0392b; --mf-none: #8a94a3;
    --mf-l0: #2f6fed; --mf-l1: #1f8a4c; --mf-l2: #a86400; --mf-l3: #8a4fb3;
    --mf-l4: #0f7f88; --mf-l5: #c0392b; --mf-l6: #6b7a12; --mf-l7: #b0457e;
  }
}
:root[data-theme="light"] .mf-graph {
  --mf-canvas: #f6f7f9; --mf-node: #ffffff; --mf-node-line: #b9c1cc; --mf-ink: #1b1f24;
  --mf-muted: #56606d; --mf-edge: #6b7584; --mf-accent: #2f6fed; --mf-focus: #a35f00;
    --mf-signal: #007a70; --mf-node-selected: #d6f5f1; --mf-spark: #1b1f24; --mf-record: #a35f00;
  --mf-definitive: #1b1f24; --mf-container: #eef1f5; --mf-separator: #8a94a3;
  --mf-definitive-role: #2f6fed; --mf-supportive: #1f8a4c; --mf-notable: #8a4fb3; --mf-divergent: #c0392b; --mf-none: #8a94a3;
  --mf-l0: #2f6fed; --mf-l1: #1f8a4c; --mf-l2: #a86400; --mf-l3: #8a4fb3;
  --mf-l4: #0f7f88; --mf-l5: #c0392b; --mf-l6: #6b7a12; --mf-l7: #b0457e;
}
.mf-graph.mf-panning { cursor: grabbing; }
.mf-background { fill: var(--mf-canvas); }
.mf-canvas { transform-origin: 0 0; }
.mf-node { cursor: pointer; outline: none; }
.mf-box { fill: var(--mf-node); stroke: var(--mf-node-line); stroke-width: 1; }
.mf-container > .mf-box { fill: var(--mf-container); stroke-dasharray: 4 3; }
.mf-stack { fill: var(--mf-node); stroke: var(--mf-node-line); }
/* The functional graph. A party the project serves is a pill; what the project relies on has a
   dashed outline; the Definitive element is filled with its role colour. Selection is focus:
   everything that is not the selected element or joined to it by a want recedes. */
.mf-node:not(.mf-container).mf-band-downstream > .mf-box { rx: 28px; stroke: var(--mf-muted); }
.mf-node:not(.mf-container).mf-band-downstream > .mf-role-bar { display: none; }
.mf-node:not(.mf-container).mf-band-upstream > .mf-box { stroke-dasharray: 5 4; fill: var(--mf-container); }
.mf-node:not(.mf-container).mf-definitive:not(.mf-selected) > .mf-box { fill: color-mix(in srgb, var(--mf-definitive-role) 14%, var(--mf-node)); stroke: var(--mf-definitive-role); stroke-width: 2; }
.mf-node.mf-dimmed > .mf-label { fill: var(--mf-muted); opacity: 0.55; }
.mf-node.mf-dimmed > .mf-box { stroke-opacity: 0.45; }
.mf-node.mf-dimmed > .mf-role-bar { opacity: 0.4; }
.mf-node, .mf-edge { transition: opacity 180ms ease; }
.mf-unbuilt > .mf-box { stroke-dasharray: 3 3; fill: transparent; }
.mf-unbuilt > .mf-label { opacity: 0.7; }
.mf-status { fill: var(--mf-divergent); font-size: 11px; }
/* Selection, as the earlier map showed it: the selected element in the signal colour, the
   elements joined to it and their lines in the second colour, and the rest quiet, not hidden. */
.mf-selected > .mf-box { fill: var(--mf-node-selected); stroke: var(--mf-signal); stroke-width: 2; }
.mf-focused .mf-node:not(.mf-dimmed):not(.mf-selected) > .mf-box { stroke: var(--mf-accent); stroke-width: 1.6; }
.mf-focused .mf-edge:not(.mf-dimmed) path:not(.mf-edge-hit) { stroke: var(--mf-accent); stroke-width: 1.8; }
.mf-focus > .mf-box { stroke: var(--mf-focus); stroke-width: 4; }
.mf-definitive-ring { fill: none; stroke: var(--mf-definitive); stroke-width: 1; }
.mf-node:focus-visible > .mf-box { stroke: var(--mf-accent); stroke-width: 3; stroke-dasharray: 6 3; }
.mf-role-bar { fill: var(--mf-none); }
.mf-role-definitive > .mf-role-bar { fill: var(--mf-definitive-role); }
.mf-role-supportive > .mf-role-bar { fill: var(--mf-supportive); }
.mf-role-notable > .mf-role-bar { fill: var(--mf-notable); }
.mf-role-divergent > .mf-role-bar { fill: var(--mf-divergent); }
.mf-label { fill: var(--mf-ink); font-size: 15px; font-weight: 600; }
.mf-beneath, .mf-outside, .mf-layer-count, .mf-band-label, .mf-edge-count { fill: var(--mf-muted); font-size: 11px; }
/* A want count sits on its line; a halo in the canvas color keeps other lines from striking through it. */
.mf-edge-count { paint-order: stroke; stroke: var(--mf-canvas); stroke-width: 4px; stroke-linejoin: round; }
.mf-chevron-hit { fill: transparent; }
.mf-chevron-mark { fill: none; stroke: var(--mf-muted); stroke-width: 1.6; }
.mf-chevron:hover .mf-chevron-mark { stroke: var(--mf-ink); }
.mf-separator { stroke: var(--mf-separator); stroke-dasharray: 6 5; }
.mf-edge path { fill: none; stroke: var(--mf-edge); stroke-width: 1.2; }
.mf-edge.mf-dimmed { opacity: 0.3; }
.mf-edge.mf-half { opacity: 0.55; }
.mf-arrowhead { fill: var(--mf-edge); }
.mf-layer-0 { fill: var(--mf-l0); } .mf-layer-1 { fill: var(--mf-l1); }
.mf-layer-2 { fill: var(--mf-l2); } .mf-layer-3 { fill: var(--mf-l3); }
.mf-layer-4 { fill: var(--mf-l4); } .mf-layer-5 { fill: var(--mf-l5); }
.mf-layer-6 { fill: var(--mf-l6); } .mf-layer-7 { fill: var(--mf-l7); }
.mf-layer .mf-layer-count { fill: var(--mf-muted); }
.mf-agent circle { fill: var(--mf-node); stroke: var(--mf-accent); stroke-width: 1.5; }
.mf-agent.mf-agent-active circle { fill: var(--mf-accent); }
.mf-agent text { fill: var(--mf-ink); font-size: 9px; font-weight: 700; }
.mf-agent.mf-agent-active text { fill: var(--mf-canvas); }
.mf-unseen { fill: var(--mf-focus); }
.mf-want-detail { display: none; pointer-events: none; }
.mf-want-detail.mf-show { display: inline; }
.mf-edge path.mf-edge-hit { fill: none; stroke: transparent; stroke-width: 14; pointer-events: stroke; }
.mf-edge.mf-lit path:not(.mf-edge-hit) { stroke: var(--mf-accent); stroke-width: 2.2; }
.mf-want-plate { fill: var(--mf-canvas); fill-opacity: 0.96; stroke: var(--mf-node-line); }
.mf-want-line { fill: var(--mf-ink); font-size: 12px; white-space: pre; }
.mf-want-inner { transform: scale(var(--mf-unzoom, 1)); transform-origin: 0 0; }
/* The flow. A request is a small white dot. An answer is a streak in the colour of the element
   it comes from. A record that is sent is a card, and it lands with a ring. */
.mf-flow-ask { fill: var(--mf-spark); color: var(--mf-spark); }
.mf-flow-train { fill: none; stroke-width: 4.2; stroke-linecap: round; stroke-linejoin: round; stroke: currentColor; color: var(--mf-muted); }
.mf-flow-definitive { color: var(--mf-definitive-role); }
.mf-flow-supportive { color: var(--mf-supportive); }
.mf-flow-notable { color: var(--mf-notable); }
.mf-flow-divergent { color: var(--mf-divergent); }
.mf-flow-card { fill: var(--mf-record); stroke: var(--mf-spark); stroke-width: 0.6; }
.mf-flow-ring { fill: none; stroke: var(--mf-record); stroke-width: 1.4; }
.mf-flow-chevron { fill: none; stroke: var(--mf-accent); stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.mf-project-link path { fill: none; stroke: var(--mf-accent); stroke-width: 1.6; }
`;
