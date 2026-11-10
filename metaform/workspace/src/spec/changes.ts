// Edits and proposals (ARCHITECTURE.md section 1). A `Change` is one edit to the specification.
// `applyChange` gives the specification with the edit in it, and `toCommand` gives the one
// `project-map` command that performs the same edit on the server. Every function here is pure.

import type { Address } from "../source/types";
import { bandOf, byText, elementAt } from "./model";
import type { FieldName, Mark, Origin, Spec, SpecElement, SpecWant, WantPart } from "./model";

/** Sets one field of an element. A null value removes the field. */
export interface SetField {
  /** Supplied by the caller, so a pending change can be dropped when the server confirms it. */
  id: string;
  kind: "set-field";
  address: Address;
  field: FieldName;
  value: string | null;
}

/** Sets the why, the how or the direction of a want the element already holds. */
export interface SetWant {
  id: string;
  kind: "set-want";
  /** The element that holds the want. */
  address: Address;
  /** The element the want names. */
  to: Address;
  part: WantPart;
  value: string;
}

/** Adds a want with all three parts. The server refuses a new want that lacks one. */
export interface AddWant {
  id: string;
  kind: "add-want";
  address: Address;
  to: Address;
  why: string;
  how: string;
  direction: string;
}

/** Removes one want from the element that holds it. */
export interface RemoveWant {
  id: string;
  kind: "remove-want";
  address: Address;
  to: Address;
}

/** Replaces every record of one layer at an element. An empty list leaves the layer with no records. */
export interface SetLayer {
  id: string;
  kind: "set-layer";
  address: Address;
  layer: string;
  records: unknown[];
}

/** One edit to the specification. */
export type Change = SetField | SetWant | AddWant | RemoveWant | SetLayer;

/** Where a proposal is in its review. */
export type ReviewState = "proposed" | "accepted" | "rejected";

/** A change that someone other than the user proposes, with what the user needs to review it. */
export interface Proposal {
  change: Change;
  /** Why the proposer suggests the change. */
  rationale: string;
  /** The evidence the proposal cites: source paths where there are any. */
  evidence: string[];
  /** The name of the agent or service that proposed the change. */
  proposedBy: string;
  /** True when a local generator made the proposal and no agent service did. */
  simulated: boolean;
  state: ReviewState;
}

/** One `project-map` command, as the server's tool takes it. */
export type Command =
  | { update: Record<Address, Record<string, unknown>> }
  | { delete: Record<Address, { wants: Address[] }> };

/**
 * The one `project-map` command that performs a change on the server. The forms are those of
 * `metaform/Intake.md` section 4 and `metaform/conformance/cases.json`: `update` writes a field,
 * a want or a layer's whole list, and `delete` with `wants` removes a want.
 */
export function toCommand(change: Change): Command {
  switch (change.kind) {
    case "set-field":
      return { update: { [change.address]: { [change.field]: change.value } } };
    case "set-want":
      return { update: { [change.address]: { wants: { [change.to]: { [change.part]: change.value } } } } };
    case "add-want":
      return {
        update: {
          [change.address]: {
            wants: { [change.to]: { why: change.why, how: change.how, direction: change.direction } },
          },
        },
      };
    case "remove-want":
      return { delete: { [change.address]: { wants: [change.to] } } };
    case "set-layer":
      return { update: { [change.address]: { [change.layer]: change.records } } };
  }
}

function markOf(change: Change, origin: Origin): Mark {
  const mark: Mark = { id: change.id, address: change.address, origin };
  if (change.kind === "set-field") mark.field = change.field;
  else if (change.kind === "set-layer") mark.layer = change.layer;
  else mark.want = change.to;
  return mark;
}

function sameTarget(a: Mark, b: Mark): boolean {
  return a.address === b.address && a.field === b.field && a.want === b.want && a.layer === b.layer;
}

function withField(element: SpecElement, field: FieldName, value: string | null): SpecElement {
  const next: SpecElement = { ...element };
  if (value === null || value === "") delete next[field];
  else next[field] = value;
  return next;
}

function withWants(element: SpecElement, wants: SpecWant[]): SpecElement {
  return { ...element, wants: [...wants].sort((a, b) => byText(a.to, b.to)) };
}

/** The element after the change, or null when the change does not apply to it. */
function changed(element: SpecElement, change: Change): SpecElement | null {
  switch (change.kind) {
    case "set-field":
      return withField(element, change.field, change.value);
    case "set-want": {
      if (!element.wants.some((want) => want.to === change.to)) return null;
      return withWants(
        element,
        element.wants.map((want) => (want.to === change.to ? { ...want, [change.part]: change.value } : want)),
      );
    }
    case "add-want": {
      const added: SpecWant = { to: change.to, why: change.why, how: change.how, direction: change.direction };
      return withWants(element, [...element.wants.filter((want) => want.to !== change.to), added]);
    }
    case "remove-want": {
      if (!element.wants.some((want) => want.to === change.to)) return null;
      return withWants(element, element.wants.filter((want) => want.to !== change.to));
    }
    case "set-layer": {
      const layers = { ...element.layers };
      if (change.records.length === 0) delete layers[change.layer];
      else layers[change.layer] = [...change.records];
      return { ...element, layers };
    }
  }
}

/**
 * The specification with one change applied. The given specification is not altered.
 * The changed part gets a mark with the change's `id` and its origin, until the server confirms.
 *
 * A `set-field` at an address with no element makes the element there, as the server does.
 * Any other change at an address with no element, and a `set-want` or `remove-want` for a want
 * the element does not hold, has no effect: the result is the given specification.
 */
export function applyChange(spec: Spec, change: Change, origin: Origin = "user"): Spec {
  const existing = elementAt(spec, change.address);
  let base = existing;
  if (base === undefined) {
    if (change.kind !== "set-field" || change.value === null || change.value === "") return spec;
    base = { address: change.address, band: bandOf(change.address), wants: [], layers: {} };
  }
  const next = changed(base, change);
  if (next === null) return spec;
  const elements =
    existing === undefined
      ? [...spec.elements, next].sort((a, b) => byText(a.address, b.address))
      : spec.elements.map((element) => (element.address === change.address ? next : element));
  const mark = markOf(change, origin);
  return { ...spec, elements, marks: [...spec.marks.filter((other) => !sameTarget(other, mark)), mark] };
}

/** True when the entry is a proposal and not a bare change. */
export function isProposal(entry: Change | Proposal): entry is Proposal {
  return "change" in entry;
}

/**
 * The specification the page shows: the saved one with every accepted change that the server has
 * not confirmed yet, applied in the order given. A bare `Change` is the user's own edit. A
 * `Proposal` is applied only when its state is `accepted`; a proposed or rejected one is never
 * applied. The caller drops an entry, by its change's `id`, when the server confirms it.
 */
export function current(saved: Spec, pending: readonly (Change | Proposal)[]): Spec {
  let spec = saved;
  for (const entry of pending) {
    if (!isProposal(entry)) spec = applyChange(spec, entry, "user");
    else if (entry.state === "accepted") spec = applyChange(spec, entry.change, "agent");
  }
  return spec;
}
