// Findings: what the specification itself shows to be open. Every finding is read from a `Spec`
// and nothing else. No function here reads a repository or performs an analysis, and each
// finding carries the evidence it rests on: a value the map holds, or the absence of one.

import type { Address } from "../source/types";
import { elementEvidence } from "../spec/evidence";
import { byText, labelOf } from "../spec/model";
import type { Spec, SpecElement } from "../spec/model";
import { finding as words, partWords } from "./strings";

/** The kinds of finding, in the order the page lists them. */
export const FINDING_KINDS = [
  "notBuilt",
  "divergent",
  "noRole",
  "noSource",
  "isolated",
  "blankWant",
  "unknownAddress",
  "sameName",
] as const;

/** One kind of finding. */
export type FindingKind = (typeof FINDING_KINDS)[number];

/** One finding: a fact about one element that the specification shows to be open. */
export interface Finding {
  /** Unique among the findings of one `Spec`, and the same on every pass. */
  id: string;
  kind: FindingKind;
  /** The address of the element the finding concerns. For a want, it is the element that holds the want. */
  address: Address;
  /** One sentence that states the finding. */
  sentence: string;
  /** What the finding rests on: the value the map holds, or the absence of one. */
  evidence: string;
}

/** The findings of one kind. */
export interface FindingGroup {
  kind: FindingKind;
  findings: Finding[];
}

function ofElement(element: SpecElement, wanted: ReadonlySet<Address>): Finding[] {
  const label = labelOf(element);
  const out: Finding[] = [];
  const add = (kind: FindingKind, sentence: string, evidence: string, part = "") =>
    out.push({ id: `${kind}:${element.address}${part === "" ? "" : `:${part}`}`, kind, address: element.address, sentence, evidence });

  if (element.status === "un_built") add("notBuilt", words.notBuilt(label), words.notBuiltEvidence(element.status));
  if (element.role === "Divergent") add("divergent", words.divergent(label), words.divergentEvidence);
  if (element.role === undefined) add("noRole", words.noRole(label), words.noRoleEvidence);
  if (elementEvidence(element).status === "unverified") add("noSource", words.noSource(label), words.noSourceEvidence);
  if (element.wants.length === 0 && !wanted.has(element.address)) add("isolated", words.isolated(label), words.isolatedEvidence);
  return out;
}

function ofWants(element: SpecElement, addresses: ReadonlySet<Address>): Finding[] {
  const label = labelOf(element);
  const out: Finding[] = [];
  for (const want of element.wants) {
    const blank = (["why", "how"] as const).filter((part) => want[part].trim() === "").map((part) => partWords[part]);
    if (blank.length > 0) {
      out.push({
        id: `blankWant:${element.address}:${want.to}`,
        kind: "blankWant",
        address: element.address,
        sentence: words.blankWant(label, want.to, blank),
        evidence: words.blankWantEvidence(blank),
      });
    }
    if (!addresses.has(want.to)) {
      out.push({
        id: `unknownAddress:${element.address}:${want.to}`,
        kind: "unknownAddress",
        address: element.address,
        sentence: words.unknownAddress(label, want.to),
        evidence: words.unknownAddressEvidence(want.to),
      });
    }
  }
  return out;
}

function ofNames(spec: Spec): Finding[] {
  const byName = new Map<string, SpecElement[]>();
  for (const element of spec.elements) {
    const name = element.name ?? element.technical_name;
    if (name !== undefined) byName.set(name, [...(byName.get(name) ?? []), element]);
  }
  const out: Finding[] = [];
  for (const [name, sharers] of byName) {
    if (sharers.length < 2) continue;
    for (const element of sharers) {
      const others = sharers.filter((other) => other !== element).map((other) => other.address);
      out.push({
        id: `sameName:${element.address}`,
        kind: "sameName",
        address: element.address,
        sentence: words.sameName(labelOf(element), others.length),
        evidence: words.sameNameEvidence(name, others),
      });
    }
  }
  return out;
}

/**
 * Every finding the specification shows, ordered by kind and then by address.
 *
 * - notBuilt: the element's status is `un_built`.
 * - divergent: the element's role is Divergent.
 * - noRole: the element has no role.
 * - noSource: the element has no source reference and no path in its `sources` layer. This is
 *   the rule that gives an element the evidence status "unverified".
 * - isolated: the element holds no want, and no want names its address.
 * - blankWant: a want the element holds has a blank why or how. One finding for each such want.
 * - unknownAddress: a want the element holds names an address at which the map holds no element.
 * - sameName: another element has the same name. The name compared is the one the page shows:
 *   the project name, or the technical name when the element has no project name. One finding
 *   for each element that shares the name.
 */
export function findingsOf(spec: Spec): Finding[] {
  const addresses = new Set(spec.elements.map((element) => element.address));
  const wanted = new Set(spec.elements.flatMap((element) => element.wants.map((want) => want.to)));
  const all = [
    ...spec.elements.flatMap((element) => [...ofElement(element, wanted), ...ofWants(element, addresses)]),
    ...ofNames(spec),
  ];
  const rank = (kind: FindingKind) => FINDING_KINDS.indexOf(kind);
  return all.sort((a, b) => rank(a.kind) - rank(b.kind) || byText(a.address, b.address) || byText(a.id, b.id));
}

/** The findings grouped by kind, in the order of `FINDING_KINDS`. A kind with no finding has an empty group. */
export function groupByKind(findings: readonly Finding[]): FindingGroup[] {
  return FINDING_KINDS.map((kind) => ({ kind, findings: findings.filter((finding) => finding.kind === kind) }));
}
