// Every string of editing, the Evidence panel and the Review panel. Terms: element, address,
// want, layer, record, role, source reference, proposal, change. The page says why, how and
// direction, and never shows an intake abbreviation.

import type { FieldName, WantPart } from "../spec/model";

function count(n: number, noun: string): string {
  return `${n} ${noun}${n === 1 ? "" : "s"}`;
}

/** The wording the store writes into the map. */
export const store = {
  // The `instruction` of the review layer's definition: one sentence.
  layerInstruction:
    "Add one record for each accepted change and each rejected proposal, with what, by, state, at, rationale and simulated.",
} as const;

/** The name of each element field, as a label. */
export const fieldLabels: Record<FieldName, string> = {
  name: "name",
  technical_name: "technical name",
  role: "role",
  status: "status",
  uri: "source reference",
};

/** The name of each part of a want, as a label. */
export const partLabels: Record<WantPart, string> = { why: "why", how: "how", direction: "direction" };

/** The four roles, in the order the page offers them. */
export const ROLES = ["Definitive", "Supportive", "Notable", "Divergent"] as const;

/** The three directions, in the order the page offers them. */
export const DIRECTIONS = ["inbound", "outbound", "two-way"] as const;

/** The wording of the edit controls. */
export const edit = {
  edit: "Edit",
  editWhat: (what: string) => `Edit the ${what}`,
  confirm: "Confirm",
  cancel: "Cancel",
  // One line that says why the controls are disabled, or where an edit goes.
  readOnly: "This page is read-only: the host was started with --read-only",
  sample: "Sample data: edits are kept in this page only",
  unreachable: "This page cannot store an edit: the host did not answer.",
  pending: "Sent. The server has not confirmed it yet.",
  refused: (message: string, code: string | null) => `The server refused the edit: ${message}${code === null ? "" : ` (${code})`}`,
  remedy: "Send the correction the server gives",
  remedyCommand: "The correction, as one command:",
  dismiss: "Dismiss",
  historyFailed: (message: string) => `The edit is stored. The review history could not be recorded: ${message}`,
  built: "built",
  notBuilt: "not built",
  none: "none recorded",
  noRole: "no role",
  fields: "Fields",
  blocks: "specification",
  addBlock: "Add a block",
  editBlock: (n: number) => `Edit block ${n}`,
  removeBlock: "Remove",
  removeBlockWhat: (n: number) => `Remove block ${n}`,
  removeBlockAsk: "Remove this block?",
  level: "Level",
  levelIntro: "Introduction, with no heading",
  levelN: (n: number) => `Heading level ${n}`,
  title: "Title",
  text: "Text",
  noBlocks: "This element has no specification blocks.",
  wantHeldBy: (holder: string) => `${holder} holds this want`,
} as const;

/** The wording of the Evidence panel. */
export const evidence = {
  label: "Evidence",
  noElement: (address: string) => `The specification has no element at ${address}. The address groups the elements beneath it.`,
  element: "Element",
  derived: "The map records no status field. The page derives each status from what the map holds and from the review history.",
  sourcePaths: "Source paths",
  sourceReference: "source reference",
  sourcesLayer: "sources layer",
  noPaths: "The map holds no source path for this element.",
  fields: "Fields",
  relationships: "Relationships",
  noRelationships: "The element holds no want.",
  reliesOn: (other: string) => `relies on ${other}`,
  layers: "Layers",
  notSet: "not set",
  records: (n: number) => count(n, "record"),
  // The meaning of user-authored once the server has confirmed the change.
  userAuthoredRecorded: "Written or changed in this page. The review history in the map records it.",
  acceptedRecorded: "A proposal that was accepted. The review history in the map records it.",
} as const;

/** The wording of the Review panel. */
export const review = {
  label: "Review",
  ask: "Ask for proposals",
  askProject: "For the project",
  askArea: (prefix: string) => `For the area ${prefix}`,
  askElement: (address: string) => `For ${address}`,
  asking: "Asking for proposals…",
  asked: (n: number) => (n === 0 ? "The request returned no new proposal." : `The request returned ${count(n, "new proposal")}.`),
  askFailed: (reason: string) => `The request for proposals failed: ${reason}`,
  simulatedNote:
    "No agent service is connected. A generator in this page makes the proposals from the specification's own text. It does not read the repository.",
  simulated: "Simulated",
  waiting: (n: number) => `Proposals waiting (${n})`,
  noneWaiting: "No proposal waits for review.",
  proposedBy: (who: string) => `Proposed by ${who}`,
  before: "Before",
  after: "After",
  empty: "(not set)",
  rationale: "Rationale",
  evidence: "Evidence",
  accept: "Accept",
  reject: "Reject",
  editFirst: "Edit, then accept",
  acceptEdited: "Accept as edited",
  editedValue: "The text to accept",
  notInSpec: "A proposal is not part of the specification until you accept it.",
  history: (n: number) => `Review history (${n})`,
  historyNote: "From the records of the review layer in the map, newest first.",
  noHistory: "The map holds no review record yet.",
  rejected: (n: number) => `Rejected (${n})`,
  rejectedNote: "A rejected proposal alters nothing in the map, so the map holds no record of it. This list lasts until the page is loaded again.",
  byUser: "user",
  byAgent: "agent",
  what: (what: string) => what,
  // The words for what a change concerns, in a proposal's heading.
  fieldOf: (field: string, name: string) => `The ${field} of ${name}`,
  wantOf: (part: string, holder: string, to: string) => `The ${part} of the want that ${holder} holds for ${to}`,
  addWant: (holder: string, to: string) => `A new want: ${holder} relies on ${to}`,
  removeWant: (holder: string, to: string) => `The want that ${holder} holds for ${to}, to remove`,
  layerOf: (layer: string, name: string) => `The ${layer} records of ${name}`,
  records: (n: number) => count(n, "record"),
  removed: "(removed)",
} as const;
