// Every string of the Findings panel and the Activity panel.
// Terms: element, address, want, layer, record, role, source reference. The page says why, how
// and direction, and never shows an intake abbreviation.

import type { FieldName, WantPart } from "../spec/model";
import type { FindingKind } from "./findings";
import type { ActivityStatus, ActivityType } from "./stream";

const count = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** The heading of each kind of finding. */
export const kindTitles: Record<FindingKind, string> = {
  notBuilt: "Not built",
  divergent: "Divergent",
  noRole: "No role",
  noSource: "No source reference",
  isolated: "No wants in either direction",
  blankWant: "Want with a blank why or how",
  unknownAddress: "Want for an address the map does not hold",
  sameName: "Same name as another element",
};

/** The mark beside each kind of finding, so that a kind does not rely on colour. */
export const kindMarks: Record<FindingKind, string> = {
  notBuilt: "□",
  divergent: "≠",
  noRole: "?",
  noSource: "○",
  isolated: "·",
  blankWant: "…",
  unknownAddress: "↯",
  sameName: "=",
};

/** What each kind of finding means, in one sentence. The empty state lists these. */
export const kindMeanings: Record<FindingKind, string> = {
  notBuilt: "An element whose status is \"not built\".",
  divergent: "An element whose role is Divergent.",
  noRole: "An element with no role.",
  noSource: "An element with no source reference and no path in its sources layer.",
  isolated: "An element that relies on no element and that no element relies on.",
  blankWant: "A want whose why or how is blank.",
  unknownAddress: "A want for an address at which the map holds no element.",
  sameName: "Two or more elements with the same name.",
};

/** The words for the parts of a want. */
export const partWords: Record<WantPart, string> = { why: "why", how: "how", direction: "direction" };

/** The words for an element's fields. */
export const fieldWords: Record<FieldName, string> = {
  name: "name",
  technical_name: "technical name",
  role: "role",
  status: "status",
  uri: "source reference",
};

const list = (words: string[]) =>
  words.length <= 1 ? words.join("") : `${words.slice(0, -1).join(", ")} and ${words[words.length - 1]}`;

/** The sentence and the evidence of each kind of finding. */
export const finding = {
  notBuilt: (label: string) => `${label} is not built.`,
  notBuiltEvidence: (status: string) => `The map holds the status "${status}".`,
  divergent: (label: string) => `${label} has the role Divergent.`,
  divergentEvidence: "The map holds the role \"Divergent\".",
  noRole: (label: string) => `${label} has no role.`,
  noRoleEvidence: "The map holds no role for this element.",
  noSource: (label: string) => `${label} has no source reference.`,
  noSourceEvidence: "The map holds no source reference for this element and no path in its sources layer.",
  isolated: (label: string) => `${label} relies on no element, and no element relies on it.`,
  isolatedEvidence: "This element holds no want, and no want in the map names its address.",
  blankWant: (label: string, to: string, parts: string[]) =>
    `The want that ${label} holds for ${to} has a blank ${list(parts)}.`,
  blankWantEvidence: (parts: string[]) =>
    parts.length === 1 ? `The map holds no ${parts[0]} for this want.` : `The map holds no ${list(parts)} for this want.`,
  unknownAddress: (label: string, to: string) => `${label} holds a want for ${to}, and the map holds no element there.`,
  unknownAddressEvidence: (to: string) => `The want names "${to}". No element in the map has that address.`,
  sameName: (label: string, others: number) =>
    `${label} has the same name as ${count(others, "other element", "other elements")}.`,
  sameNameEvidence: (name: string, others: string[]) => `The name "${name}" is also at ${list(others)}.`,
} as const;

/** The wording of the Findings panel. */
export const findings = {
  label: "Findings",
  origin:
    "The page reads these findings from the specification as the map holds it. The page performed no analysis of the repository.",
  filterLabel: "Show findings of one kind",
  all: "All kinds",
  withCount: (title: string, n: number) => `${title} (${n})`,
  total: (n: number) => count(n, "finding", "findings"),
  evidence: "Evidence",
  empty: "The specification has no open findings of the kinds this page checks.",
  emptyKinds: "The page checks these kinds:",
  noElements: "The map holds no elements yet, so there is nothing to check.",
} as const;

/** The word for each type of activity item. */
export const typeWords: Record<ActivityType, string> = {
  "element-added": "Element added",
  "element-removed": "Element removed",
  "field-changed": "Field changed",
  "want-added": "Want added",
  "want-removed": "Want removed",
  "want-changed": "Want changed",
  "layer-changed": "Layer records changed",
  "test-result": "Test result",
  "build-result": "Build result",
  "dependency-change": "Dependency change",
  "runtime-issue": "Runtime issue",
};

/** The word for each status of an activity item. */
export const statusWords: Record<ActivityStatus, string> = {
  recorded: "recorded",
  passed: "passed",
  failed: "failed",
  open: "open",
  resolved: "resolved",
};

/** The mark beside each status word. */
export const statusMarks: Record<ActivityStatus, string> = {
  recorded: "●",
  passed: "✓",
  failed: "✕",
  open: "!",
  resolved: "✓",
};

/** The one-line summaries and the details of the items that `diff` returns. */
export const change = {
  elementAdded: (label: string) => `${label} was added to the map.`,
  elementRemoved: (label: string) => `${label} was removed from the map.`,
  fieldChanged: (field: string, label: string) => `The ${field} of ${label} changed.`,
  fieldSet: (field: string, label: string) => `The ${field} of ${label} was set.`,
  fieldCleared: (field: string, label: string) => `The ${field} of ${label} was removed.`,
  wantAdded: (label: string, to: string) => `${label} now relies on ${to}.`,
  wantRemoved: (label: string, to: string) => `${label} no longer relies on ${to}.`,
  wantChanged: (label: string, to: string, parts: string[]) =>
    `The ${list(parts)} of the want that ${label} holds for ${to} changed.`,
  layerChanged: (layer: string, label: string) => `The records of the layer "${layer}" at ${label} changed.`,
  rootLayerChanged: (layer: string) => `The records of the layer "${layer}" at the project's root changed.`,
  address: "address",
  wants: "wants held",
  records: (n: number) => count(n, "record", "records"),
  recordsOf: (layer: string) => `records of "${layer}"`,
  sameCount: "The number of records is the same. The content of at least one record changed.",
} as const;

/** The wording of the Activity panel. */
export const activity = {
  label: "Activity",
  connected: "Connected. A change to the map is listed when the server announces it.",
  simulated: "Sample data. Every item is simulated; no server sent it.",
  notConnected: "Not connected. No new item can arrive until the page reaches the server again.",
  connectionMarks: { connected: "●", simulated: "◇", "not-connected": "✕" },
  paused: (n: number) => `Paused. ${n} waiting.`,
  pause: "Pause",
  resume: "Resume",
  pauseHint: "While the list is paused, new items are held and counted, and the list does not grow.",
  typeLabel: "Type",
  allTypes: "All types",
  onlySelected: "Only items that affect the selected element",
  noSelection: "No element is selected.",
  empty: "No activity yet.",
  emptyNotConnected: "No activity is listed.",
  emptyPaused: "No item arrived before the pause.",
  noMatch: (hidden: number) => `No item matches the filters. The filters hide ${count(hidden, "item", "items")}.`,
  newAbove: (n: number) => `${count(n, "new item", "new items")} above. Go to the top`,
  simulatedBadge: "Simulated",
  simulatedHint: "No real source produced this item.",
  scopeProject: "the project",
  scope: "Scope",
  element: "Affected element",
  noElement: "none",
  status: "Status",
  time: "Time",
  what: "What changed",
  before: "Before",
  after: "After",
  absent: "not recorded",
  back: "Back to where I was",
  backHint: "Selects again what was selected before you chose this item.",
  listLabel: "Activity items, newest first",
  detailsOf: (summary: string) => `Details: ${summary}`,
} as const;
