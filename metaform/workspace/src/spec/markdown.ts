// The Markdown of the specification (ARCHITECTURE.md section 3). `toMarkdown` is the one function
// behind the preview, the copy and the download. It reads only its arguments: no clock and no
// random value, so the same `Spec` and options give the same text.

import type { Address } from "../source/types";
import type { Change, Proposal } from "./changes";
import { elementEvidence } from "./evidence";
import { byText, elementAt, inScope, labelOf, wantedBy } from "./model";
import type { Mark, Spec, SpecElement, SpecWant } from "./model";
import { coveredElements, functionalGroups, openItems, outsideOf, overviewOf } from "./sections";
import { common, groupTitle, markdown as words, OPEN_KINDS, openTitles, sectionTitles, statusValue, statusWords } from "./strings";
import type { SectionKey } from "./strings";

/** The layer whose records are the prose of the specification. */
export const SPECIFICATION_LAYER = "specification";

/** What a generated document includes. */
export interface MarkdownOptions {
  /** Null for the whole project, or an address: the element there and everything beneath it. */
  scope: Address | null;
  /** The sections to include. A section that is absent here takes its default from `DEFAULT_SECTIONS`. */
  sections?: Partial<Record<SectionKey, boolean>>;
  /** The proposals the section "Proposals that are not accepted" may show. No other section reads them. */
  proposals?: readonly Proposal[];
}

/** Every section is included by default, except the proposals that are not accepted. */
export const DEFAULT_SECTIONS: Record<SectionKey, boolean> = {
  overview: true,
  elements: true,
  outside: true,
  evidence: true,
  open: true,
  proposals: false,
};

/** One line of text for a list item or a table cell: line breaks become spaces. */
function oneLine(text: string): string {
  return text.replace(/\s*\n\s*/g, " ").trim();
}

function cell(text: string): string {
  return oneLine(text).replace(/\|/g, "\\|");
}

function code(text: string): string {
  return `\`${text}\``;
}

function titled(element: SpecElement): string {
  return `${oneLine(labelOf(element))} (${code(element.address)})`;
}

function titledAt(spec: Spec, address: Address): string {
  const element = elementAt(spec, address);
  return element ? titled(element) : code(address);
}

function heading(level: number, text: string): string[] {
  return [`${"#".repeat(Math.min(6, level))} ${text}`, ""];
}

function summaryLine(element: SpecElement): string {
  const kind = element.technical_name === undefined ? "" : `: ${oneLine(element.technical_name)}`;
  return `- **${oneLine(labelOf(element))}** (${code(element.address)})${kind}`;
}

function summaryList(elements: readonly SpecElement[]): string[] {
  return elements.length === 0 ? [common.none, ""] : [...elements.map(summaryLine), ""];
}

function overviewSection(spec: Spec, scope: Address | null): string[] {
  const overview = overviewOf(spec, scope);
  const covered = coveredElements(spec, scope).length;
  return [
    ...heading(2, sectionTitles.overview),
    words.counts(covered, spec.elements.length),
    "",
    ...heading(3, common.whatItIs),
    ...(overview.definitive ? [summaryLine(overview.definitive), ""] : [common.noDefinitive, ""]),
    ...heading(3, common.serves),
    ...summaryList(overview.serves),
    ...heading(3, common.reliesOn),
    ...summaryList(overview.reliesOn),
  ];
}

/** The records of the specification layer as Markdown. A record's heading sits `level` levels below the element's. */
function specificationText(element: SpecElement, elementLevel: number): string[] {
  const lines: string[] = [];
  for (const record of element.layers[SPECIFICATION_LAYER] ?? []) {
    if (typeof record === "string") {
      if (record.trim() !== "") lines.push(record.trim(), "");
      continue;
    }
    if (record === null || typeof record !== "object") continue;
    const block = record as Record<string, unknown>;
    const title = typeof block.title === "string" ? block.title.trim() : "";
    const requirement = typeof block.code === "string" ? block.code.trim() : "";
    const body = typeof block.text === "string" ? block.text.trim() : "";
    const level = typeof block.level === "number" && block.level >= 1 ? Math.floor(block.level) : 1;
    const headingText = [requirement, title].filter((part) => part !== "").join(" ");
    if (headingText !== "") lines.push(...heading(elementLevel + level, headingText));
    if (body !== "") lines.push(body, "");
  }
  return lines;
}

/** One want as a list item: the other element, then the why, the how and the direction beneath it. */
function wantLines(spec: Spec, other: Address, want: SpecWant): string[] {
  const part = (label: string, value: string) => `  - ${label}: ${value === "" ? words.notRecorded : oneLine(value)}`;
  return [
    `- ${titledAt(spec, other)}`,
    part(words.why, want.why),
    part(words.how, want.how),
    part(words.direction, want.direction),
  ];
}

function elementBlock(spec: Spec, element: SpecElement, level: number): string[] {
  const evidence = elementEvidence(element);
  const lines = [
    ...heading(level, titled(element)),
    `- ${words.kind}: ${element.technical_name === undefined ? words.notRecorded : oneLine(element.technical_name)}`,
    `- ${words.role}: ${element.role ?? words.noRole}`,
  ];
  if (element.status !== undefined) lines.push(`- ${words.status}: ${statusValue(element.status)}`);
  lines.push(
    `- ${words.source}: ${element.uri === undefined ? words.noSource : code(element.uri)}`,
    `- ${words.evidence}: ${statusWords[evidence.status]}`,
    "",
    ...specificationText(element, level),
  );
  if (element.wants.length > 0) {
    lines.push(`**${words.reliesOn}**`, "", ...element.wants.flatMap((want) => wantLines(spec, want.to, want)), "");
  }
  const holders = wantedBy(spec, element.address);
  if (holders.length > 0) {
    lines.push(`**${words.reliedOnBy}**`, "", ...holders.flatMap((held) => wantLines(spec, held.holder, held.want)), "");
  }
  return lines;
}

function elementsSection(spec: Spec, scope: Address | null): string[] {
  const groups = functionalGroups(spec, scope);
  const lines = heading(2, sectionTitles.elements);
  if (groups.length === 0) return [...lines, words.noElements, ""];
  for (const group of groups) {
    lines.push(...heading(3, groupTitle(group.segment)));
    for (const element of group.elements) lines.push(...elementBlock(spec, element, 4));
  }
  return lines;
}

function outsideSection(spec: Spec, scope: Address | null): string[] {
  const outside = outsideOf(spec, scope);
  const lines = heading(2, sectionTitles.outside);
  if (outside.serves.length === 0 && outside.reliesOn.length === 0) return [...lines, words.noOutside, ""];
  for (const [title, elements] of [
    [common.serves, outside.serves],
    [common.reliesOn, outside.reliesOn],
  ] as const) {
    lines.push(...heading(3, title));
    if (elements.length === 0) lines.push(common.none, "");
    for (const element of elements) lines.push(...elementBlock(spec, element, 4));
  }
  return lines;
}

function markTarget(mark: Mark): string {
  if (mark.field !== undefined) return words.pendingField(mark.field);
  if (mark.want !== undefined) return words.pendingWant(mark.want);
  return words.pendingLayer(mark.layer ?? "");
}

function evidenceSection(spec: Spec, scope: Address | null): string[] {
  const covered = coveredElements(spec, scope);
  const lines = [...heading(2, sectionTitles.evidence), words.evidenceNote, ""];
  if (covered.length === 0) lines.push(common.none, "");
  else {
    lines.push(`| ${words.evidenceColumns.join(" | ")} |`, `|${words.evidenceColumns.map(() => "---").join("|")}|`);
    for (const element of covered) {
      const evidence = elementEvidence(element);
      const paths = evidence.paths.length === 0 ? words.noSource : evidence.paths.map((path) => code(cell(path))).join(", ");
      lines.push(`| ${cell(labelOf(element))} | ${code(element.address)} | ${statusWords[evidence.status]} | ${paths} |`);
    }
    lines.push("");
  }
  const marks = spec.marks
    .filter((mark) => covered.some((element) => element.address === mark.address))
    .map((mark) => `- ${code(mark.address)}, ${markTarget(mark)}: ${statusWords[mark.origin === "user" ? "user-authored" : "accepted"]}`)
    .sort(byText);
  if (marks.length > 0) lines.push(...heading(3, words.pendingTitle), ...marks, "");
  return lines;
}

function openSection(spec: Spec, scope: Address | null): string[] {
  const items = openItems(coveredElements(spec, scope));
  const lines = heading(2, sectionTitles.open);
  for (const kind of OPEN_KINDS) {
    lines.push(...heading(3, openTitles[kind]));
    lines.push(...(items[kind].length === 0 ? [common.none] : items[kind].map((element) => `- ${titled(element)}`)), "");
  }
  return lines;
}

/** One change in words, for the proposals section. */
export function describeChange(change: Change): string {
  switch (change.kind) {
    case "set-field":
      return words.setField(change.field, change.address, change.value === null ? null : oneLine(change.value));
    case "set-want":
      return words.setWant(change.part, change.address, change.to, oneLine(change.value));
    case "add-want":
      return words.addWant(change.address, change.to);
    case "remove-want":
      return words.removeWant(change.address, change.to);
    case "set-layer":
      return words.setLayer(change.layer, change.address, change.records.length);
  }
}

function proposalsSection(spec: Spec, scope: Address | null, proposals: readonly Proposal[]): string[] {
  const open = proposals.filter((proposal) => proposal.state !== "accepted" && inScope(proposal.change.address, scope));
  const lines = [...heading(2, sectionTitles.proposals), `> ${words.proposalsNote}`, ""];
  if (open.length === 0) return [...lines, words.noProposals, ""];
  open.forEach((proposal, index) => {
    const change = proposal.change;
    const by = oneLine(proposal.proposedBy) + (proposal.simulated ? ` (${words.simulated})` : "");
    lines.push(
      ...heading(3, `${index + 1}. ${describeChange(change)}`),
      `- ${words.proposalState}: ${statusWords[proposal.state === "proposed" ? "agent-proposed" : "rejected"]}`,
      `- ${words.proposedBy}: ${by}`,
      `- ${words.rationale}: ${oneLine(proposal.rationale)}`,
    );
    if (change.kind === "add-want") {
      lines.push(`- ${words.why}: ${oneLine(change.why)}`, `- ${words.how}: ${oneLine(change.how)}`, `- ${words.direction}: ${oneLine(change.direction)}`);
    }
    const cited = proposal.evidence.map((path) => code(oneLine(path))).join(", ");
    lines.push(`- ${words.proposalEvidence}: ${cited === "" ? words.noSource : cited}`, "");
  });
  return lines;
}

/**
 * The specification as Markdown. The sections come in a fixed order: project overview, functional
 * elements, outside parties and dependencies, evidence, open items, and, only when the options
 * ask for it, the proposals that are not accepted. A proposal that is not accepted appears in
 * that last section and nowhere else.
 */
export function toMarkdown(spec: Spec, options: MarkdownOptions): string {
  const include = { ...DEFAULT_SECTIONS, ...options.sections };
  const scope = options.scope;
  const lines = [
    ...heading(1, words.title(spec.project)),
    scope === null ? words.scopeWhole : words.scopeElement(scope),
    "",
    words.origin,
    "",
  ];
  if (include.overview) lines.push(...overviewSection(spec, scope));
  if (include.elements) lines.push(...elementsSection(spec, scope));
  if (include.outside) lines.push(...outsideSection(spec, scope));
  if (include.evidence) lines.push(...evidenceSection(spec, scope));
  if (include.open) lines.push(...openSection(spec, scope));
  if (include.proposals) lines.push(...proposalsSection(spec, scope, options.proposals ?? []));
  return `${lines.join("\n").trimEnd()}\n`;
}

/** The file name for a download: the project's name and the scope, with only letters, digits, dots and hyphens. */
export function fileName(spec: Spec, scope: Address | null): string {
  const parts = [spec.project, ...(scope === null ? [] : [scope]), words.fileSuffix];
  return `${parts.join("-").replace(/[^A-Za-z0-9.-]+/g, "-").replace(/^-+|-+$/g, "") || words.fileSuffix}.md`;
}
