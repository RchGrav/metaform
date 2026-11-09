// Every string the graph workspace shows. Other modules import from here and add no literals,
// so one file holds the product's wording and one review covers it.
//
// Terms follow dev/graph_workspace_terms.md: element, address, want, wanted by, layer, record,
// upstream, downstream, role, focus. Interaction follows dev/user_agent_interfaces-ux.md.
// Owner of this file: Matthew. Send changes to Matthew before they ship.

export type Platform = "mac" | "other";

/** "1 record", "3 records". English plural by count; every counted noun here takes an -s. */
function count(n: number, noun: string): string {
  return `${n} ${noun}${n === 1 ? "" : "s"}`;
}

export const modes = {
  graph: "Graph",
  // Proposed to Ida as "Element" so that "focus" names only the pivot. Not yet accepted.
  element: "Element",
  present: "Present",
} as const;

export const topBar = {
  projects: "Projects",
  zoom: (percent: number) => `Zoom ${Math.round(percent)}%`,
} as const;

export const rail = {
  fitToView: "Fit to view",
  zoomIn: "Zoom in",
  zoomOut: "Zoom out",
  resetZoom: "Zoom to 100%",
  back: "Back",
  more: "More",
  collapseAll: "Collapse all",
  expandAll: "Expand all",
  theme: "Theme",
  keyboardHelp: "Keyboard shortcuts",
  gettingStarted: "Getting started",
  // The handle that stays at the left edge while the menu is hidden.
  showMenu: "Show menu",
} as const;

export const hints = {
  // Shown once, near the first selected element, until the user opens or goes up.
  openOrGoUp: (platform: Platform) =>
    platform === "mac"
      ? "Double-click to open. ⌘-click to go up."
      : "Double-click to open. Ctrl-click to go up.",
} as const;

export const graph = {
  // The visible badge on an element with elements beneath it.
  beneathBadge: (n: number) => `${n} beneath`,
  // The accessible name of the same badge; the badge alone is not a complete thought.
  beneathLabel: (n: number, address: string) => `${count(n, "element")} beneath ${address}`,
  // The count on one arrow that stands for wants to or from collapsed elements.
  wantsOnArrow: (n: number) => count(n, "want"),
  upstreamBand: "upstream",
  downstreamBand: "downstream",
  opensAnotherProject: "Opens another project",
  containerGone: (gone: string, shown: string) => `${gone} no longer exists. Showing ${shown}.`,
} as const;

export const details = {
  close: "Close",
  openProject: "Open project",
  setAsFocus: "Set as focus",
  // Field and part names are shown exactly as the server returns them (R-3.4, R-5.30).
  wants: "wants",
  wantedBy: "wanted by",
  layers: "layers",
  noWants: "No wants.",
  notWanted: "No element wants this one.",
} as const;

export const focus = {
  banner: (address: string, hops: number) =>
    `Focus: ${address} · elements up to ${count(hops, "want")} away`,
  clear: "Clear focus",
} as const;

export const layers = {
  showAll: "Show all layers",
  hideAll: "Hide all layers",
  show: (layer: string) => `Show ${layer}`,
  hide: (layer: string) => `Hide ${layer}`,
  isolate: "Isolate",
  isolated: "Isolated",
  records: (n: number) => count(n, "record"),
} as const;

export const activity = {
  summary: (unseen: number) => `Activity (${unseen} new)`,
  // A real map-changed event carries no author, address or diff (seam doc, Transport).
  mapChanged: (time: string) => `Map changed · ${time}`,
  // Only simulated events name an agent; always shown with the Simulated badge.
  simulatedWrite: (agent: string, layer: string, address: string) =>
    `${agent} wrote ${layer} at ${address}`,
} as const;

export const presence = {
  // The server does not publish presence, so every presence line is simulated.
  at: (agent: string, address: string, doing?: string) =>
    doing ? `${agent} at ${address} · ${doing}` : `${agent} at ${address}`,
  active: "Active",
  idle: "Idle",
} as const;

export const simulated = {
  badge: "Simulated",
  tooltip: "Simulated: not connected to a Metaform server.",
} as const;

export const connection = {
  // `reason` is the host's or the server's text, shown unchanged.
  notConnected: (reason: string) => `Not connected: ${reason}`,
} as const;

export const navigation = {
  backTo: (project: string, address: string) => `Back to ${project} · ${address}`,
} as const;

export const onboarding = {
  title: "Getting started",
  register: {
    title: "Register a project",
    body: "Connect an agent from the project's folder. Its first connection registers the folder.",
    command: "metaform mcp --project <folder>",
    // From the owner's prompt; not in the CLI at 61ef6dc.
    plannedLabel: "Planned command",
    plannedCommand: "metaform register <project_name>",
  },
  intake: {
    title: "Run a first intake",
    button: "Run a simulated intake",
    body: "An agent runs a real intake by following metaform/Intake.md.",
  },
  reopen: {
    title: "Open this view again",
    // The product's own reopen command is an owner decision (UI-U1). Until it exists, show the
    // command the host reports it was started with; never a name invented here.
    prototypeCommand: (command: string) => `This prototype was started with: ${command}`,
  },
} as const;
