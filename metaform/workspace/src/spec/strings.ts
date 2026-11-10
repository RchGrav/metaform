// Every string of the specification outline, the Markdown preview and the generated Markdown.
// Terms: element, address, want, layer, record, role, source reference. The page says why, how
// and direction, and never shows an intake abbreviation.

import type { EvidenceStatus } from "./evidence";

/** The sections of the specification, in the order the Markdown and the outline show them. */
export const SECTION_KEYS = ["overview", "elements", "outside", "evidence", "open", "proposals"] as const;

/** One section of the specification. */
export type SectionKey = (typeof SECTION_KEYS)[number];

/** The title of each section. */
export const sectionTitles: Record<SectionKey, string> = {
  overview: "Project overview",
  elements: "Functional elements",
  outside: "Outside parties and dependencies",
  evidence: "Evidence",
  open: "Open items",
  proposals: "Proposals that are not accepted",
};

/** The word the page shows for each evidence status. */
export const statusWords: Record<EvidenceStatus, string> = {
  "source-backed": "source-backed",
  inferred: "inferred",
  unverified: "unverified",
  "user-authored": "user-authored",
  "agent-proposed": "agent-proposed",
  accepted: "accepted",
  rejected: "rejected",
};

/** The mark the page shows beside each status word, so that the status does not rely on colour. */
export const statusMarks: Record<EvidenceStatus, string> = {
  "source-backed": "●",
  inferred: "◐",
  unverified: "○",
  "user-authored": "✎",
  "agent-proposed": "◇",
  accepted: "✓",
  rejected: "✕",
};

/** What each status means, for a tooltip. */
export const statusMeanings: Record<EvidenceStatus, string> = {
  "source-backed": "The element has a source reference or a path in its sources layer.",
  inferred: "The map records this with no source reference of its own.",
  unverified: "The element has no source reference.",
  "user-authored": "Written or changed in this page. The server has not confirmed it yet.",
  "agent-proposed": "An agent proposed this. No one has reviewed it.",
  accepted: "A proposal that was accepted. It is part of the specification.",
  rejected: "A proposal that was rejected. It is not part of the specification.",
};

/** The headings for the groups of functional elements, by the first segment of the address. */
export const groupTitles: Record<string, string> = {
  code: "Code",
  document: "Document",
  data: "Data",
  media: "Media",
};

/** The order of the known groups. Any other first segment follows, in alphabetical order. */
export const GROUP_ORDER = ["code", "document", "data", "media"];

/** The heading for a group of functional elements. An unknown first segment is shown as it is. */
export function groupTitle(segment: string): string {
  return groupTitles[segment] ?? segment;
}

/** The words for the map's `status` values. A value the page does not know is shown as it is. */
export function statusValue(status: string): string {
  return status === "un_built" ? "not built" : status;
}

/** The kinds of open item, in the order the page lists them. */
export const OPEN_KINDS = ["notBuilt", "divergent", "unverified", "noRole"] as const;

/** One kind of open item. */
export type OpenKind = (typeof OPEN_KINDS)[number];

/** The heading of each kind of open item. */
export const openTitles: Record<OpenKind, string> = {
  notBuilt: "Not built",
  divergent: "Divergent",
  unverified: "Unverified: no source reference",
  noRole: "No role",
};

/** The wording shared by the outline and the Markdown. */
export const common = {
  whatItIs: "What the project is",
  serves: "Who the project serves",
  reliesOn: "What the project relies on",
  none: "None.",
  noDefinitive: "The map has no Definitive element, so it does not say what the project is.",
} as const;

/** The wording of the generated Markdown. */
export const markdown = {
  title: (project: string) => `Functional specification: ${project}`,
  scopeWhole: "Scope: the whole project.",
  scopeElement: (address: string) => `Scope: \`${address}\` and every element beneath that address.`,
  origin: "Metaform generated this document from the project's map.",
  counts: (shown: number, all: number) =>
    shown === all
      ? `This document covers all ${all} elements of the map.`
      : `This document covers ${shown} of the ${all} elements of the map.`,
  kind: "Kind",
  role: "Role",
  status: "Status",
  source: "Source",
  evidence: "Evidence",
  noSource: "none recorded",
  noRole: "none recorded",
  reliesOn: "Relies on",
  reliedOnBy: "Relied on by",
  why: "Why",
  how: "How",
  direction: "Direction",
  notRecorded: "not recorded",
  noElements: "The scope holds no functional elements.",
  noOutside: "The scope has no outside parties and no dependencies.",
  evidenceNote:
    "The map records no status field. Each status here is derived from what the map holds: " +
    "an element is source-backed when it has a source reference or a path in its `sources` layer, " +
    "and unverified when it has neither. Every want is inferred, because the map records no source " +
    "reference for a want.",
  evidenceColumns: ["Element", "Address", "Status", "Source paths"],
  pendingTitle: "Changes the server has not confirmed",
  pendingField: (field: string) => `the field \`${field}\``,
  pendingWant: (to: string) => `the want for \`${to}\``,
  pendingLayer: (layer: string) => `the records of the layer \`${layer}\``,
  proposalsNote:
    "The proposals in this section are not part of the specification. No other section of this " +
    "document includes them.",
  proposalState: "State",
  proposedBy: "Proposed by",
  simulated: "simulated; no agent service made this proposal",
  rationale: "Rationale",
  proposalEvidence: "Evidence cited",
  noProposals: "There are no proposals in this scope that are not accepted.",
  setField: (field: string, address: string, value: string | null) =>
    value === null
      ? `Remove the field \`${field}\` of \`${address}\``
      : `Set the field \`${field}\` of \`${address}\` to "${value}"`,
  setWant: (part: string, address: string, to: string, value: string) =>
    `Set the ${part} of the want that \`${address}\` holds for \`${to}\` to "${value}"`,
  addWant: (address: string, to: string) => `Add a want: \`${address}\` relies on \`${to}\``,
  removeWant: (address: string, to: string) => `Remove the want that \`${address}\` holds for \`${to}\``,
  setLayer: (layer: string, address: string, records: number) =>
    `Replace the records of the layer \`${layer}\` at \`${address}\` with ${records} ${records === 1 ? "record" : "records"}`,
  fileSuffix: "specification",
} as const;

/** The wording of the specification outline. */
export const outline = {
  label: "Specification outline",
  empty: "The map holds no elements yet.",
  statusOf: (word: string) => `Evidence status: ${word}`,
} as const;

/** The wording of the Markdown preview. */
export const preview = {
  label: "Specification as Markdown",
  scopeLegend: "Scope",
  scopeWhole: "The whole project",
  scopeElement: (address: string) => `${address} and every element beneath it`,
  sectionsLegend: "Sections to include",
  proposalsHint: "Off unless you choose it. The Markdown puts proposals in one marked section.",
  textLabel: "Generated Markdown",
  summary: (lines: number, characters: number) =>
    `${lines} ${lines === 1 ? "line" : "lines"}, ${characters} ${characters === 1 ? "character" : "characters"}`,
  sameState:
    "The preview, the copy and the download are one text, generated from the specification that the page shows now.",
  copy: "Copy",
  copied: "Copied the Markdown to the clipboard.",
  copyFailed: (reason: string) => `The copy failed: ${reason}`,
  noClipboard: "this browser does not give the page access to the clipboard",
  download: "Download",
  downloadNote:
    "The browser saves the file to its downloads folder. This page cannot write a file into the project's folder.",
  downloaded: (name: string) => `The browser received ${name} to save. The page cannot confirm where the browser saved it.`,
  downloadFailed: (reason: string) => `The download failed: ${reason}`,
  unknownReason: "the browser gave no reason",
} as const;
