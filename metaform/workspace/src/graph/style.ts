// The graph's own styles, scoped to .mf-graph. Dark first, with a light theme (UX section 2).
// Text contrast targets 4.5:1 and marks 3:1 against the canvas (WCAG 2.2 AA); the values are
// checked in the verification step, not assumed. The shell may override any --mf- token.

export const GRAPH_CSS = `
.mf-graph {
  --mf-canvas: #0f1216; --mf-node: #1a1f26; --mf-node-line: #3a4350; --mf-ink: #e6e9ee;
  --mf-muted: #a3adba; --mf-edge: #7d8796; --mf-accent: #6ea2ff; --mf-focus: #f0b45a;
  --mf-definitive: #e6e9ee; --mf-container: #141920; --mf-separator: #4a5463;
  --mf-definitive-role: #6ea2ff; --mf-supportive: #57c08a; --mf-notable: #c99be8; --mf-divergent: #ef7a6b; --mf-none: #59636f;
  --mf-l0: #6ea2ff; --mf-l1: #57c08a; --mf-l2: #e3a541; --mf-l3: #c99be8;
  --mf-l4: #4fc1c9; --mf-l5: #ef7a6b; --mf-l6: #b8c25a; --mf-l7: #e889b8;
  display: block; background: var(--mf-canvas); font: 13px/1.2 system-ui, sans-serif;
  user-select: none; touch-action: none; cursor: grab;
}
@media (prefers-color-scheme: light) {
  :root:not([data-theme="dark"]) .mf-graph {
    --mf-canvas: #f6f7f9; --mf-node: #ffffff; --mf-node-line: #b9c1cc; --mf-ink: #1b1f24;
    --mf-muted: #56606d; --mf-edge: #6b7584; --mf-accent: #2f6fed; --mf-focus: #a35f00;
    --mf-definitive: #1b1f24; --mf-container: #eef1f5; --mf-separator: #8a94a3;
    --mf-definitive-role: #2f6fed; --mf-supportive: #1f8a4c; --mf-notable: #8a4fb3; --mf-divergent: #c0392b; --mf-none: #8a94a3;
    --mf-l0: #2f6fed; --mf-l1: #1f8a4c; --mf-l2: #a86400; --mf-l3: #8a4fb3;
    --mf-l4: #0f7f88; --mf-l5: #c0392b; --mf-l6: #6b7a12; --mf-l7: #b0457e;
  }
}
:root[data-theme="light"] .mf-graph {
  --mf-canvas: #f6f7f9; --mf-node: #ffffff; --mf-node-line: #b9c1cc; --mf-ink: #1b1f24;
  --mf-muted: #56606d; --mf-edge: #6b7584; --mf-accent: #2f6fed; --mf-focus: #a35f00;
  --mf-definitive: #1b1f24; --mf-container: #eef1f5; --mf-separator: #8a94a3;
  --mf-definitive-role: #2f6fed; --mf-supportive: #1f8a4c; --mf-notable: #8a4fb3; --mf-divergent: #c0392b; --mf-none: #8a94a3;
  --mf-l0: #2f6fed; --mf-l1: #1f8a4c; --mf-l2: #a86400; --mf-l3: #8a4fb3;
  --mf-l4: #0f7f88; --mf-l5: #c0392b; --mf-l6: #6b7a12; --mf-l7: #b0457e;
}
.mf-graph.mf-panning { cursor: grabbing; }
.mf-background { fill: var(--mf-canvas); }
.mf-canvas { transform-origin: 0 0; }
.mf-node { cursor: pointer; outline: none; }
.mf-node.mf-dimmed { opacity: 0.3; }
.mf-box { fill: var(--mf-node); stroke: var(--mf-node-line); stroke-width: 1; }
.mf-container > .mf-box { fill: var(--mf-container); stroke-dasharray: 4 3; }
.mf-stack { fill: var(--mf-node); stroke: var(--mf-node-line); }
.mf-selected > .mf-box { stroke: var(--mf-accent); stroke-width: 2.5; }
.mf-focus > .mf-box { stroke: var(--mf-focus); stroke-width: 4; }
.mf-definitive-ring { fill: none; stroke: var(--mf-definitive); stroke-width: 1; }
.mf-node:focus-visible > .mf-box { stroke: var(--mf-accent); stroke-width: 3; stroke-dasharray: 6 3; }
.mf-role-bar { fill: var(--mf-none); }
.mf-role-definitive > .mf-role-bar { fill: var(--mf-definitive-role); }
.mf-role-supportive > .mf-role-bar { fill: var(--mf-supportive); }
.mf-role-notable > .mf-role-bar { fill: var(--mf-notable); }
.mf-role-divergent > .mf-role-bar { fill: var(--mf-divergent); }
.mf-label { fill: var(--mf-ink); font-weight: 600; }
.mf-beneath, .mf-outside, .mf-layer-count, .mf-band-label, .mf-edge-count { fill: var(--mf-muted); font-size: 11px; }
/* A want count sits on its line; a halo in the canvas color keeps other lines from striking through it. */
.mf-edge-count { paint-order: stroke; stroke: var(--mf-canvas); stroke-width: 4px; stroke-linejoin: round; }
.mf-chevron-hit { fill: transparent; }
.mf-chevron-mark { fill: none; stroke: var(--mf-muted); stroke-width: 1.6; }
.mf-chevron:hover .mf-chevron-mark { stroke: var(--mf-ink); }
.mf-separator { stroke: var(--mf-separator); stroke-dasharray: 6 5; }
.mf-edge path { fill: none; stroke: var(--mf-edge); stroke-width: 1.4; }
.mf-edge.mf-dimmed { opacity: 0.25; }
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
.mf-graph.mf-close .mf-want-detail { display: inline; }
.mf-want-plate { fill: var(--mf-canvas); fill-opacity: 0.88; stroke: var(--mf-node-line); }
.mf-want-line { fill: var(--mf-muted); font-size: 10px; }
.mf-flow-dot { fill: var(--mf-accent); stroke: var(--mf-canvas); stroke-width: 1.5; }
.mf-flow-chevron { fill: none; stroke: var(--mf-accent); stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.mf-project-link path { fill: none; stroke: var(--mf-accent); stroke-width: 1.6; }
`;
