// What each section of the specification holds, for a given scope. The Markdown and the outline
// both read these functions, so the two show the same elements in the same order.

import type { Address } from "../source/types";
import { elementEvidence } from "./evidence";
import { byText, definitiveOf, firstSegment, inScope, wantedBy } from "./model";
import type { Spec, SpecElement } from "./model";
import { GROUP_ORDER } from "./strings";
import type { OpenKind } from "./strings";

/** The functional elements that share the first segment of their address. */
export interface ElementGroup {
  /** The first segment, such as "code". */
  segment: string;
  elements: SpecElement[];
}

/** The project's own elements in the scope, grouped by first segment: code, document, data, media, then any other. */
export function functionalGroups(spec: Spec, scope: Address | null): ElementGroup[] {
  const bySegment = new Map<string, SpecElement[]>();
  for (const element of spec.elements) {
    if (element.band !== "project" || !inScope(element.address, scope)) continue;
    const segment = firstSegment(element.address);
    bySegment.set(segment, [...(bySegment.get(segment) ?? []), element]);
  }
  const rank = (segment: string) => {
    const at = GROUP_ORDER.indexOf(segment);
    return at < 0 ? GROUP_ORDER.length : at;
  };
  return [...bySegment.entries()]
    .sort(([a], [b]) => rank(a) - rank(b) || byText(a, b))
    .map(([segment, elements]) => ({ segment, elements }));
}

/** The outside elements a scope concerns: those the project serves and those it relies on. */
export interface Outside {
  /** Elements of the `downstream` band. */
  serves: SpecElement[];
  /** Elements of the `upstream` band. */
  reliesOn: SpecElement[];
}

/**
 * The outside elements for a scope. With no scope they are all of them. With a scope they are the
 * outside elements in the scope, those that rely on an element in the scope, and those that an
 * element in the scope relies on.
 */
export function outsideOf(spec: Spec, scope: Address | null): Outside {
  const related = (element: SpecElement): boolean => {
    if (inScope(element.address, scope)) return true;
    if (element.wants.some((want) => inScope(want.to, scope))) return true;
    return wantedBy(spec, element.address).some((held) => inScope(held.holder, scope));
  };
  const band = (name: "downstream" | "upstream") =>
    spec.elements.filter((element) => element.band === name && related(element));
  return { serves: band("downstream"), reliesOn: band("upstream") };
}

/**
 * Every element a document of this scope describes: the elements in the scope and the outside
 * elements related to them. Ordered by address.
 */
export function coveredElements(spec: Spec, scope: Address | null): SpecElement[] {
  const outside = outsideOf(spec, scope);
  const covered = new Set<SpecElement>([...outside.serves, ...outside.reliesOn]);
  for (const element of spec.elements) if (inScope(element.address, scope)) covered.add(element);
  return spec.elements.filter((element) => covered.has(element));
}

/**
 * The open items among the given elements, by kind: not built (the status `un_built`), Divergent
 * (the role), unverified (no source reference) and no role. An element can be in several kinds.
 */
export function openItems(elements: readonly SpecElement[]): Record<OpenKind, SpecElement[]> {
  return {
    notBuilt: elements.filter((element) => element.status === "un_built"),
    divergent: elements.filter((element) => element.role === "Divergent"),
    unverified: elements.filter((element) => elementEvidence(element).status === "unverified"),
    noRole: elements.filter((element) => element.role === undefined),
  };
}

/** What the overview shows: the Definitive element, who the project serves and what it relies on. */
export interface Overview {
  definitive: SpecElement | undefined;
  serves: SpecElement[];
  reliesOn: SpecElement[];
}

/** The overview for a scope. The Definitive element is the project's, whatever the scope. */
export function overviewOf(spec: Spec, scope: Address | null): Overview {
  return { definitive: definitiveOf(spec), ...outsideOf(spec, scope) };
}
