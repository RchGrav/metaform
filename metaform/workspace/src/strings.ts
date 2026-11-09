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
  // The accessible name of the breadcrumb navigation: one breadcrumb per address segment.
  address: "Address",
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
  // A node's accessible name: label, role, and the elements beneath it. Empty parts are left out.
  nodeName: (label: string, role: string | null, beneath: number) =>
    [label, role, beneath > 0 ? count(beneath, "element") + " beneath" : null]
      .filter((part): part is string => part !== null && part !== "")
      .join(", "),
  // The badge for wants between this element and elements outside the current view.
  wantsOutside: (n: number) => `${count(n, "want")} outside`,
  wantsOutsideLabel: (n: number, container: string) =>
    `${count(n, "want")} cross outside ${container}`,
} as const;

export const details = {
  close: "Close",
  openProject: "Open project",
  // An outside element's own functional map, opened like another project (SPEC R-4.15, seam gap 4).
  openItsMap: "Open its map",
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
  // The tooltip on a layer's mark at an element.
  mark: (layer: string, n: number) => `${layer}: ${count(n, "record")}`,
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
  // A refusal from the Metaform server: its message and code, unchanged (R-5.24).
  refused: (message: string, code: string) => `The server refused the command: ${message} (${code})`,
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
    // The owner named the command (2026-11-09). It is not in the CLI yet, so it shows with
    // onboarding.register.plannedLabel until the host provides it.
    command: "metaform gui",
    // Also shown: the command the host reports it was started with.
    prototypeCommand: (command: string) => `This prototype was started with: ${command}`,
  },
} as const;

/** The keyboard help list, in the order the panel shows it. Keys follow the UX design, section 3 to 11. */
export const keyboard = {
  title: "Keyboard shortcuts",
  keys: (platform: Platform) =>
    [
      { keys: "1, 2, 3", action: `Switch to ${modes.graph}, ${modes.element} or ${modes.present}` },
      { keys: "+, −", action: "Zoom in or out" },
      { keys: "0", action: "Fit to view" },
      { keys: "Shift+0", action: "Zoom to 100%" },
      { keys: platform === "mac" ? "Backspace, ⌥←" : "Backspace, Alt+Left", action: "Back" },
      { keys: "Enter", action: "Open the selected element" },
      { keys: "Shift+Enter", action: "Go up one address level" },
      { keys: "Space", action: "Collapse or expand the selected element" },
      { keys: "F", action: "Set the selected element as focus" },
      { keys: "M", action: "Show the menu" },
      { keys: "Esc", action: "Close the panel, or leave Present" },
      { keys: "Arrow keys", action: "In Present, move the selection along wants" },
    ] as const,
} as const;
