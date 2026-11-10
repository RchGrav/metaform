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
  isolated: { word: "isolated", mark: "◉" },
} as const;

/** The names of the categories: the first segment of an element's address. */
const CATEGORY_NAMES: Record<string, string> = {
  downstream: "Downstream",
  code: "Code",
  document: "Document",
  data: "Data",
  media: "Media",
  upstream: "Upstream",
};

/** The graph controls. Each control has a short label and a tooltip that says what it does. */
export const controls = {
  label: "Graph controls",
  fit: {
    group: "Fit",
    graph: { label: "Graph", tip: "Fit graph: show the whole graph" },
    selection: { label: "Selection", tip: "Fit selection: show the selected element and the elements joined to it by a want" },
    branch: { label: "Branch", tip: "Fit branch: show the selected element and everything it relies on, directly or through other elements" },
    needsSelection: "Select an element first.",
  },
  depth: {
    group: "Depth",
    less: { label: "−", tip: "Collapse one level: hide the deepest level on screen" },
    more: { label: "+", tip: "Expand one level: show the next level of every element that holds hidden elements" },
    current: (shown: number, most: number) => `Depth ${shown} of ${most}. Depth 1 is the first level that draws a want.`,
    expandAll: { label: "All", tip: "Expand all: show every level" },
    collapseAll: { label: "First", tip: "Collapse all: show only the first level that draws a want" },
    undo: { label: "Undo", tip: "Undo: show the elements that were on screen before the last depth action" },
    nothingToUndo: "No depth action to undo.",
  },
  categories: {
    group: "Categories",
    name: (category: string) => CATEGORY_NAMES[category] ?? category,
    toggle: (name: string, elements: number, state: keyof typeof categoryState) =>
      `${name}: ${count(elements, "element")}, ${categoryState[state].word}. ${state === "hidden" ? "Show" : "Hide"} this category.`,
    isolate: { label: "Only", tip: (name: string) => `Isolate ${name}: quiet every other category. The other categories stay in place.` },
    endIsolation: (name: string) => `End the isolation of ${name}.`,
    showAll: { label: "Show all", tip: "Show every category" },
    hideAll: { label: "Hide all", tip: "Hide every category" },
    restore: { label: "Restore", tip: "Restore: end the isolation and show every category" },
  },
} as const;
