// The words of the graph's depth marks and of the graph controls (views/GraphControls.tsx).
// The page says why, how and direction, and never an intake abbreviation.

const count = (n: number, noun: string) => `${n} ${noun}${n === 1 ? "" : "s"}`;

/** Depth marks on an element of the functional graph. */
export const depth = {
  // The count on an element that holds hidden elements.
  hiddenBadge: (n: number) => `${n} hidden`,
  hiddenTip: "Number at the right: how many hidden elements this element holds. They are reached through it along the wants.",
  stackTip: "Stacked outline: this element holds hidden elements",
  chevronOpen: "Chevron: show the next level of elements this element holds",
  chevronClose: "Chevron: hide the elements this element holds",
  chevronLabel: (label: string, collapsed: boolean) => (collapsed ? `Show the next level from ${label}` : `Hide the elements that ${label} holds`),
  // The accessible name of an element: its name, its role, and the hidden elements it holds.
  nodeName: (label: string, role: string | null, hidden: number) =>
    [label, role, hidden > 0 ? `holds ${count(hidden, "hidden element")}` : null].filter((part) => part !== null).join(", "),
};

/** The state of a category, as a word and as a mark, so it does not depend on colour. */
export const categoryState = {
  shown: { word: "shown", mark: "✓" },
  hidden: { word: "hidden", mark: "–" },
  isolated: { word: "only", mark: "◉" },
} as const;

/** The names of the categories: the first segment of an element's address. */
const CATEGORY_NAMES: Record<string, string> = {
  downstream: "Served parties",
  code: "Code",
  document: "Document",
  data: "Data",
  media: "Media",
  upstream: "Dependencies",
};

/** What each category holds, for its tooltip. */
const CATEGORY_MEANINGS: Record<string, string> = {
  downstream: "the outside parties the project serves (addresses under downstream)",
  code: "the project's own code",
  document: "the project's own documents",
  data: "the project's own data",
  media: "the project's own media",
  upstream: "what the project relies on outside itself (addresses under upstream)",
};

/** The graph controls. Each control has a short label and a tooltip that says what it does. */
export const controls = {
  label: "Graph controls",
  fit: {
    group: "Fit",
    graph: { label: "Graph", tip: "Fit graph: show the whole graph" },
    selection: { label: "Selection", tip: "Fit selection: show the selected element and the elements directly connected to it" },
    branch: { label: "Branch", tip: "Fit branch: show the selected element and everything it relies on, directly or through other elements" },
    needsSelection: "Select an element first.",
  },
  depth: {
    group: "Depth",
    less: { label: "−", tip: "Collapse one level: hide the deepest level on screen" },
    more: { label: "+", tip: "Expand one level: show the next level of every element that holds hidden elements" },
    current: (shown: number, most: number) => `Depth ${shown} of ${most}: how many levels of elements the graph shows, counted from the top.`,
    expandAll: { label: "Expand all", tip: "Expand all: show every level" },
    collapseAll: { label: "Collapse all", tip: "Collapse all: show only the top level. Each element then shows how many hidden elements it holds." },
    undo: { label: "Undo", tip: "Undo: show the elements that were on screen before the last depth action" },
    nothingToUndo: "No depth action to undo.",
  },
  categories: {
    group: "Categories",
    name: (category: string) => CATEGORY_NAMES[category] ?? category,
    toggle: (name: string, elements: number, state: keyof typeof categoryState, category?: string) =>
      `${name}: ${CATEGORY_MEANINGS[category ?? ""] ?? "a category of elements"}. ${count(elements, "element")}, ${categoryState[state].word}. ${state === "hidden" ? "Show" : "Hide"} them.`,
    isolate: { label: "Only", tip: (name: string) => `Only ${name}: keep these elements clear and fade the other categories. Nothing moves.` },
    endIsolation: (name: string) => `Make every category clear again, not only ${name}.`,
    showAll: { label: "Show all", tip: "Show every category" },
    hideAll: { label: "Hide all", tip: "Hide every category" },
    restore: { label: "Reset", tip: "Reset: show every category, all clear" },
  },
} as const;
