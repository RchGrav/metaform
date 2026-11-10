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
  // The one control Present mode shows: it brings the page's controls back.
  leavePresent: "Leave Present (Esc)",
} as const;

export const topBar = {
  projects: "Projects",
  // The accessible name of the breadcrumb navigation: one breadcrumb per address segment.
  address: "Address",
  zoom: (percent: number) => `Zoom ${Math.round(percent)}%`,
  // The first breadcrumb while the graph shows the whole project.
  wholeProject: "Whole project",
  selected: (name: string) => `Selected: ${name}`,
  connection: { connected: "Live", simulated: "Sample data", "not-connected": "Not connected" },
  connectionMark: { connected: "●", simulated: "◆", "not-connected": "○" },
  connectionTip: {
    connected: "The page reads this project's map from the Metaform server and follows every change.",
    simulated: "The page shows sample data. No Metaform server is read.",
    "not-connected": "The page lost the Metaform server. It shows the map as it was last read.",
  },
  elements: (n: number) => count(n, "element"),
  elementsTip: "How many elements the specification holds",
  unverified: (n: number) => `${n} unverified`,
  unverifiedTip: "Elements with no source reference. The Findings panel lists them.",
  pending: (n: number) => `${count(n, "edit")} not saved yet`,
  pendingTip: "Edits the server has not confirmed. The Review panel lists them.",
  proposals: (n: number) => `${count(n, "proposal")} to review`,
  proposalsTip: "Proposals that wait for you to accept or reject them. The Review panel lists them.",
  mainElement: (name: string) => `Main element: ${name}`,
  mainElementTip: "The Definitive element: the one without which the project is not what it is. Select it to read what the project is.",
  review: "Proposals",
  reviewTip: "Ask for proposals to improve the specification, and accept or reject each one",
  markdown: "Specification as Markdown",
  markdownTip: "Show the specification on screen as a Markdown document, to copy or download",
} as const;

export const rail = {
  fitToView: "Fit to view",
  zoomIn: "Zoom in",
  zoomOut: "Zoom out",
  resetZoom: "Zoom to 100%",
  back: "Back",
  more: "More",
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
  // Written on an element whose status is un_built.
  notBuilt: "not built",
  // Shown on the canvas when a project is registered and its map has no element.
  emptyMap: "This project's map has no elements yet. They appear here as an agent adds them.",
  // The visible badge on an element with elements beneath it.
  beneathBadge: (n: number) => `${n} beneath`,
  // The accessible name of the same badge; the badge alone is not a complete thought.
  beneathLabel: (n: number, address: string) => `${count(n, "element")} beneath ${address}`,
  // The count on one arrow that stands for wants to or from collapsed elements.
  wantsOnArrow: (n: number) => count(n, "want"),
  upstreamBand: "upstream",
  downstreamBand: "downstream",
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
  setAsFocus: "Show only this and its wants",
  setAsFocusTip: "Draw only this element, the elements it relies on and the elements that rely on it. A banner above the graph brings the whole graph back.",
  // What each role means, for the tooltip on the role (SPEC.md, section on roles).
  roleMeaning: {
    definitive: "Definitive: the element without which the project is not what it is.",
    supportive: "Supportive: an element coupled to the Definitive element, whose function is meant to assist it.",
    notable: "Notable: an independent feature, or an outside party or dependency, with its own significance to the project.",
    divergent: "Divergent: an element that does not align with the rest. It is to be investigated, then repaired or removed.",
  } as Record<string, string>,
  // Field and part names are shown exactly as the server returns them (R-3.4, R-5.30).
  wants: "wants",
  wantedBy: "wanted by",
  layers: "layers",
  // The folder of an element. "Serves" lists the elements that want this one; "relies on"
  // lists the elements this one wants.
  serves: (n: number) => (n === 1 ? "1 element relies on this" : `${n} elements rely on this`),
  reliesOn: (n: number) => (n === 1 ? "This relies on 1 element" : `This relies on ${n} elements`),
  notBuilt: "not built",
  source: "source",
  address: "The element's address in the map",
  layer: (layer: string, n: number) => `${layer} (${n === 1 ? "1 record" : `${n} records`})`,
  loading: "Reading…",
  // Shown for an address that only groups the elements beneath it.
  branch: (n: number) =>
    `This address groups ${count(n, "element")}. The arrows drawn at it belong to them. Select one to see its wants.`,
  noWants: "It relies on no other element.",
  // Shown in the Entity panel in place of the records of the review layer.
  reviewLayer: "The Review panel lists these records.",
  notWanted: "No element relies on it.",
} as const;

export const focus = {
  banner: (address: string, hops: number) =>
    `Focus: ${address} · elements up to ${count(hops, "want")} away`,
  clear: "Clear focus",
} as const;

export const layers = {
  group: "Knowledge layers",
  chip: (layer: string, n: number) => `${layer}: ${count(n, "record")}`,
  groupTip: "A layer holds records of one kind, such as sources. An element that holds records of a layer carries that layer's mark.",
  show: (layer: string) => `Show the ${layer} marks on the elements that hold ${layer} records`,
  hide: (layer: string) => `Hide the ${layer} marks on the elements`,
  only: "Only",
  onlyTip: (layer: string) => `Keep clear only the elements that hold ${layer} records. The other elements recede and stay in place.`,
  endOnly: (layer: string) => `Make every element clear again, with or without ${layer} records.`,
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

export const offView = {
  // Climb step 6b (UX section 12a): elements with new activity that lie outside the view.
  chip: (n: number, arrow: string) => `${n} new ${arrow}`,
  label: (n: number) =>
    `${count(n, "element")} with new activity outside the view. Show ${n === 1 ? "it" : "them"}.`,
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
  // Shown when the host answers with an empty project list. Never shown when the host fails.
  noProject: "No project is registered in this home yet.",
  // The button that reads the project list again, and its result when the list is still empty.
  checkAgain: "Check for projects",
  stillNoProject: "The home still has no project.",
  register: {
    title: "Register a project",
    body: "Connect an agent from the project's folder. Its first connection registers the folder.",
    command: "metaform mcp --project <folder>",
    // Any connection from a folder registers it (`open_project`); one read from a terminal is enough.
    terminalBody:
      "Or register a folder from a terminal with one read of its map. If you gave --home to metaform gui, give the same --home here.",
    terminalCommand: "metaform call --project <folder> '{\"map\": {}}'",
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
    body: "Run this command from any folder:",
    // The owner's reopen command (2026-11-09); it works since Jorge's 1a03bf2.
    command: "metaform gui",
    // Show only when the host was started another way, such as `npm run dev`, so the panel
    // never shows the same command twice.
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

/**
 * Intake terms on wants (climb step 2). The stored fields keep the intake's meaning: `why` is the
 * Operative purpose (OP), `how` is the Encounter function (EF), and `direction` is the
 * Information flow direction (IFD). The element that holds the want is the Receiving element
 * (RE); the element it names is the Providing element (PE). Sources: SPEC R-3.4 to R-3.6; the
 * founder's term mapping (context/topogee-repo/DECISIONS.md); the earlier graph
 * (context/brain/digital-typology-hhgg-graph-fixed.html).
 */
export const intake = {
  // The parts of a want, in the words the tool and the specification use (R-3.4 to R-3.6).
  re: { short: "holder", long: "held by" },
  pe: { short: "provider", long: "provided by" },
  op: { short: "why", long: "why" },
  ef: { short: "how", long: "how" },
  ifd: { short: "direction", long: "direction" },
  // What the holder seeks, and what the provider supplies, as shown on a want.
  opLine: (why: string) => `why: ${why}`,
  efLine: (how: string) => `how: ${how}`,
  // The direction is relative to the element that holds the want, never to the project, and the
  // request is never the direction (R-3.6). `ifdValue` is the value alone, for a place that
  // already shows the label (the Details panel); `ifdLine` carries the label (a line's tooltip).
  ifdValue: (direction: "inbound" | "outbound" | "two-way", re: string, pe: string) =>
    direction === "outbound"
      ? `outbound: ${re} sends to ${pe}`
      : direction === "inbound"
        ? `inbound: ${re} receives from ${pe}`
        : `two-way: ${re} and ${pe} send to each other`,
  ifdLine: (direction: "inbound" | "outbound" | "two-way", re: string, pe: string) =>
    `direction: ${intake.ifdValue(direction, re, pe)}`,
} as const;

/**
 * The legend (climb step 1): one entry per mark the renderer draws (graph/svg-renderer.ts).
 * The same text serves as each mark's tooltip, so a mark never appears without its meaning.
 */
export const legend = {
  title: "Legend",
  show: "Show legend",
  hide: "Hide legend",
  roleBar: "Coloured bar: the element's role, Definitive, Supportive, Notable or Divergent",
  definitive: "Inner ring: the Definitive element, the one without which the project is not what it is",
  stack: "Stacked outline: this element holds hidden elements",
  chevron: "Chevron: show or hide the next level of elements this element holds",
  beneath: "\"N hidden\": how many hidden elements this element holds. They are reached through it along the wants",
  outside: "\"N wants outside\": wants to or from elements outside this view",
  layerMark: "Small shape with a number: a layer's records at this element",
  agent: "Circle with initials: an agent at this address (simulated)",
  agentActive: "Filled ring: the agent is active",
  agentIdle: "Outlined ring: the agent is idle",
  unseen: "Dot at the corner: activity here you have not looked at yet",
  projectLink: "Link mark: this element opens another project",
  arrow: "Line: a want, between the element that holds it and the element that provides. The arrowhead is where the substance arrives: at the holder (inbound), at the provider (outbound) or at both ends (two-way)",
  arrowCount: "Number on an arrow: several wants drawn as one line",
  // Drawn only by a layout that has bands; the functional graph has none.
  band: "Dashed line: the project boundary",
} as const;

/**
 * The panel system (dev/gui_specification.md, phase 2): the zones around the graph, the panels
 * they hold, and the Panels menu in the top bar.
 */
export const panels = {
  // The one menu in the top bar that lists every panel with its state.
  menu: "Panels",
  title: {
    entity: "Entity",
    legend: "Legend",
    activity: "Activity",
    outline: "Outline",
    markdown: "Markdown",
    evidence: "Evidence",
    findings: "Findings",
    review: "Review",
  },
  zone: { left: "left zone", right: "right zone", bottom: "bottom zone" },
  // In a narrow window every open panel is in one zone under the graph.
  narrowZone: "zone under the graph",
  // The state of a panel, shown beside its title in the Panels menu.
  floating: "floating",
  closed: "closed",
  // The tabs of one zone, and the actions on the panel a zone or a floating frame shows.
  tabs: (zone: string) => `Panels in the ${zone}`,
  actions: (title: string) => `Actions for the ${title} panel`,
  close: (title: string) => `Close the ${title} panel`,
  moveTo: (zone: string) => `Move to the ${zone}`,
  float: "Float over the graph",
  dock: (zone: string) => `Dock in the ${zone}`,
  // Dividers and floating panels can be dragged, or adjusted from the keyboard.
  resizeZone: (zone: string) => `Resize the ${zone}. Drag, or press the arrow keys.`,
  moveFloating: (title: string) => `Move the ${title} panel. Drag, or press the arrow keys.`,
  resizeFloating: (title: string) => `Resize the ${title} panel. Drag, or press the arrow keys.`,
  restore: "Restore the default layout",
  workspaceText: "Workspace text size",
  panelText: "Panel text size",
  smaller: (what: string) => `${what}: smaller`,
  larger: (what: string) => `${what}: larger`,
  pixels: (n: number) => `${n} px`,
  // Shown in the Entity panel while no element is selected.
  noProject: "No project is open.",
  noSelection: "Select an element in the graph to see its details here: what it is, what relies on it, and what it relies on.",
  // Shown in the Evidence panel while no element is selected.
  noSelectionEvidence: "Select an element in the graph to see its evidence here.",
  // Shown in the Activity panel while its list is empty.
  noActivity: "No activity yet. Changes to the map appear here.",
  // The body of a panel that is registered and not built yet.
} as const;
