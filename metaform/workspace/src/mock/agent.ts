// SIMULATED. The local generator of proposals behind the `AgentService` interface
// (src/source/agent.ts). No agent service is reachable from the host, so this is the only
// implementation, and every proposal it makes has `simulated: true`.
//
// The generator reads only the specification it is given. It never reads the repository, so it
// proposes only what follows from the specification's own text:
// 1. A why reworded to the form the intake asks for: a goal that starts with a base verb.
// 2. A how reworded to the form the intake asks for: what the provider does.
// 3. A role for an outside party that has none: the role the map already gives most outside
//    parties of the same kind.
// 4. The status "not built" for an element the outline lists as an open item with no source reference.

import type { AgentService, ProposalScope } from "../source/agent";
import { inProposalScope } from "../source/agent";
import type { Address, Role } from "../source/types";
import type { Change, Proposal } from "../spec/changes";
import { elementEvidence } from "../spec/evidence";
import { wantedBy } from "../spec/model";
import type { Spec, SpecElement } from "../spec/model";
import { openItems } from "../spec/sections";
import { openTitles } from "../spec/strings";

/** The name the page shows as the proposer of every simulated proposal. */
export const SIMULATED_AGENT = "Simulated generator";

/** The most proposals one request returns, so a large map does not fill the Review panel. */
export const MAX_PROPOSALS = 10;

/** Words that open a why and say only that a goal follows. The goal is the text after them. */
const WHY_OPENINGS = /^(in order to|so that it can|so it can|wants to|needs to|to)\s+(?=\S)/i;

/** Words that open a how and name the provider. What the provider does is the text after them. */
const HOW_OPENINGS = /^(the provider|it|this|which|that)\s+(?=\S)/i;

/** Verbs whose base form does not follow from the spelling. */
const IRREGULAR: Record<string, string> = { is: "be", has: "have", does: "do", goes: "go" };

/** First words that end in "s" and are not a verb, and second words that show the first word is a subject. */
const NOT_A_VERB = new Set(["always", "its", "this", "as", "across", "unless", "plus", "towards", "perhaps", "sometimes", "thus", "yes"]);
const AFTER_A_SUBJECT = new Set(["can", "will", "must", "should", "may", "might", "is", "are", "was", "were", "has", "have", "do", "does"]);

/** The wording of the rationales and the evidence lines. */
const words = {
  whyOpening: (opening: string) =>
    `The why starts with "${opening}". The intake asks for a why that is a goal and starts with a base verb. This proposal removes the opening words and keeps the rest of the text.`,
  whyVerb: (found: string, base: string) =>
    `The why starts with "${found}", which reads as a verb that describes an action. The intake asks for a why that is a goal and starts with a base verb, here "${base}". This proposal changes that one word.`,
  howOpening: (opening: string) =>
    `The how starts with "${opening}", which names the provider. The intake asks for a how that says what the provider does. This proposal removes the opening words and keeps the rest of the text.`,
  roleFromMap: (role: string, same: number, band: string) =>
    `The element has no role. ${same} of the other ${band} elements in this map have the role ${role}, which is the most frequent role there. This proposal gives the element the same role.`,
  roleDownstream:
    "The element has no role, and no other downstream element in this map has one. A downstream party holds a want for the project: it states a demand. The intake gives the role Notable to an element that defines a demand.",
  roleUpstream:
    "The element has no role, and no other upstream element in this map has one. The project relies on an upstream element to perform its own function. The intake gives the role Supportive to an element whose function helps.",
  notBuilt: (title: string) =>
    `The outline lists this element as an open item under "${title}". The map holds no source path for it. If the element has no source because it is not built, accept this proposal. If the element is built, reject this proposal and add its source reference.`,
  wantText: (part: string, holder: string, to: string, text: string) => `The ${part} that ${holder} holds for ${to}: "${text}"`,
  reliedOnBy: (holder: string, why: string) => `${holder} relies on it. Why: "${why}"`,
  reliesOn: (to: string, why: string) => `It relies on ${to}. Why: "${why}"`,
  noWants: "The map holds no want that names this element.",
  noSource: (address: string) => `The map holds no source reference and no record in the sources layer at ${address}.`,
  openItem: (title: string) => `Outline, open items: ${title}`,
} as const;

function withCaseOf(model: string, text: string): string {
  const first = text.charAt(0);
  const upper = model.charAt(0) !== model.charAt(0).toLowerCase();
  return (upper ? first.toUpperCase() : first.toLowerCase()) + text.slice(1);
}

/** The base form of a verb that ends in "s", such as "keep" for "keeps". Null when the word does not read as one. */
export function baseVerb(word: string): string | null {
  const lower = word.toLowerCase();
  if (!/^[a-z]+$/.test(lower) || NOT_A_VERB.has(lower)) return null;
  const irregular = IRREGULAR[lower];
  if (irregular !== undefined) return irregular;
  if (lower.length < 4 || !lower.endsWith("s") || /(ss|us|is)$/.test(lower)) return null;
  if (lower.endsWith("ies")) return `${lower.slice(0, -3)}y`;
  if (/(ch|sh|x|z|ss|o)es$/.test(lower)) return lower.slice(0, -2);
  return lower.slice(0, -1);
}

/** A reworded text with the reason for the rewording. */
export interface Rewording {
  after: string;
  rationale: string;
}

/**
 * A why in the form the intake asks for, or null when the why already has that form. The result
 * holds no word that the given text does not hold, except the base form of its first word.
 */
export function rewordWhy(why: string): Rewording | null {
  const text = why.trim();
  const opening = WHY_OPENINGS.exec(text);
  if (opening) {
    return { after: withCaseOf(text, text.slice(opening[0].length)), rationale: words.whyOpening(opening[0].trim()) };
  }
  const [first = "", second = ""] = text.split(/\s+/);
  if (AFTER_A_SUBJECT.has(second.toLowerCase())) return null;
  const base = baseVerb(first);
  if (base === null) return null;
  return { after: withCaseOf(first, base) + text.slice(first.length), rationale: words.whyVerb(first, withCaseOf(first, base)) };
}

/** A how in the form the intake asks for, or null when no rule applies. The result is the end of the given text. */
export function rewordHow(how: string): Rewording | null {
  const text = how.trim();
  const opening = HOW_OPENINGS.exec(text);
  if (!opening) return null;
  return { after: withCaseOf(text, text.slice(opening[0].length)), rationale: words.howOpening(opening[0].trim()) };
}

/** The role this map gives most outside elements of the band, with how many have it. Null when none has a role. */
function usualRole(spec: Spec, band: SpecElement["band"], except: Address): { role: string; count: number } | null {
  const counts = new Map<string, number>();
  for (const element of spec.elements) {
    if (element.band !== band || element.address === except || element.role === undefined) continue;
    // An outside element is not the project's Definitive element, so that role is never proposed.
    if (element.role === "Definitive") continue;
    counts.set(element.role, (counts.get(element.role) ?? 0) + 1);
  }
  let best: { role: string; count: number } | null = null;
  for (const [role, count] of [...counts.entries()].sort(([a], [b]) => (a < b ? -1 : 1))) {
    if (best === null || count > best.count) best = { role, count };
  }
  return best;
}

/** The wants that name an element or that it holds, as evidence lines. */
function wantLines(spec: Spec, element: SpecElement): string[] {
  const lines = [
    ...wantedBy(spec, element.address).map((held) => words.reliedOnBy(held.holder, held.want.why)),
    ...element.wants.map((want) => words.reliesOn(want.to, want.why)),
  ];
  return lines.length > 0 ? lines.slice(0, 3) : [words.noWants];
}

/** A change with no id yet. The service gives each proposal's change its id. */
type Unnumbered = Change extends infer One ? (One extends Change ? Omit<One, "id"> : never) : never;

/** The simulated agent service. Each instance numbers its own proposals. */
export class SimulatedAgent implements AgentService {
  readonly name = SIMULATED_AGENT;
  readonly simulated = true;
  private made = 0;

  private proposal(change: Unnumbered, rationale: string, evidence: string[]): Proposal {
    this.made += 1;
    return {
      change: { ...change, id: `simulated-${this.made}` } as Change,
      rationale,
      evidence,
      proposedBy: this.name,
      simulated: true,
      state: "proposed",
    };
  }

  async propose(spec: Spec, scope: ProposalScope): Promise<Proposal[]> {
    const out: Proposal[] = [];
    const elements = spec.elements.filter((element) => inProposalScope(element.address, scope));

    for (const element of elements) {
      for (const want of element.wants) {
        const why = want.why === "" ? null : rewordWhy(want.why);
        if (why && why.after !== want.why) {
          out.push(this.proposal(
            { kind: "set-want", address: element.address, to: want.to, part: "why", value: why.after },
            why.rationale,
            [words.wantText("why", element.address, want.to, want.why)],
          ));
        }
        const how = want.how === "" ? null : rewordHow(want.how);
        if (how && how.after !== want.how) {
          out.push(this.proposal(
            { kind: "set-want", address: element.address, to: want.to, part: "how", value: how.after },
            how.rationale,
            [words.wantText("how", element.address, want.to, want.how)],
          ));
        }
      }
    }

    for (const element of elements) {
      if (element.band === "project" || element.role !== undefined) continue;
      const usual = usualRole(spec, element.band, element.address);
      const role: Role | string = usual?.role ?? (element.band === "downstream" ? "Notable" : "Supportive");
      const rationale = usual
        ? words.roleFromMap(usual.role, usual.count, element.band)
        : element.band === "downstream" ? words.roleDownstream : words.roleUpstream;
      out.push(this.proposal({ kind: "set-field", address: element.address, field: "role", value: role }, rationale, wantLines(spec, element)));
    }

    const open = openItems(elements.filter((element) => element.band === "project"));
    for (const element of open.unverified) {
      if (element.status === "un_built" || elementEvidence(element).status !== "unverified") continue;
      out.push(this.proposal(
        { kind: "set-field", address: element.address, field: "status", value: "un_built" },
        words.notBuilt(openTitles.unverified),
        [words.openItem(openTitles.unverified), words.noSource(element.address)],
      ));
    }
    return out.slice(0, MAX_PROPOSALS);
  }
}

/** Makes the simulated agent service. */
export function createSimulatedAgent(): AgentService {
  return new SimulatedAgent();
}
