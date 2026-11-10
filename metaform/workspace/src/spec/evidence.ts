// Evidence status (ARCHITECTURE.md section 2). The map records no status field. The statuses
// source-backed, inferred and unverified are derived here from what the map holds. The statuses
// user-authored and accepted come from a pending change, or from a record of the `review` layer.

import type { Address } from "../source/types";
import type { Change, Proposal } from "./changes";
import { elementAt } from "./model";
import type { FieldName, Mark, Origin, Spec, SpecElement } from "./model";

/** The statuses a claim can carry, in the order the page lists them. */
export const EVIDENCE_STATUSES = [
  "source-backed",
  "inferred",
  "unverified",
  "user-authored",
  "agent-proposed",
  "accepted",
  "rejected",
] as const;

/** The status of one claim the page shows. */
export type EvidenceStatus = (typeof EVIDENCE_STATUSES)[number];

/** A claim's status, with the source paths that support it. `paths` is empty when there are none. */
export interface Evidence {
  status: EvidenceStatus;
  paths: string[];
}

/** The layer that holds an element's additional source references. */
export const SOURCES_LAYER = "sources";

function pathOf(record: unknown): string | undefined {
  if (typeof record === "string") return record === "" ? undefined : record;
  if (record !== null && typeof record === "object" && !Array.isArray(record)) {
    const held = record as Record<string, unknown>;
    for (const key of ["path", "uri"]) {
      const value = held[key];
      if (typeof value === "string" && value !== "") return value;
    }
  }
  return undefined;
}

/**
 * An element's source paths: its source reference first, then the paths in its `sources` layer,
 * in the map's order, each path once. A `sources` record gives a path when it is a string or has
 * a `path` or `uri` field.
 */
export function sourcePaths(element: SpecElement): string[] {
  const paths: string[] = [];
  if (element.uri !== undefined) paths.push(element.uri);
  for (const record of element.layers[SOURCES_LAYER] ?? []) {
    const path = pathOf(record);
    if (path !== undefined && !paths.includes(path)) paths.push(path);
  }
  return paths;
}

/**
 * The status of an element: source-backed when it has a source reference or a path in its
 * `sources` layer, and unverified when it has neither.
 */
export function elementEvidence(element: SpecElement): Evidence {
  const paths = sourcePaths(element);
  return { status: paths.length > 0 ? "source-backed" : "unverified", paths };
}

/** The layer that holds the review history: one record for each accepted change and each rejected proposal. */
export const REVIEW_LAYER = "review";

/** One record of the `review` layer, kept at the element the change concerns. */
export interface ReviewRecord {
  /** The part the change concerns: a field name, "want <address>", or a layer name such as "specification". */
  what: string;
  /** Who wrote the change: the user, or an agent whose proposal the user reviewed. */
  by: Origin;
  state: "accepted" | "rejected";
  /** The ISO time of the review. */
  at: string;
  /** Why the change was made. It may be empty. */
  rationale: string;
  /** True when a local generator made the proposal and no agent service did. */
  simulated: boolean;
}

/** The name a review record gives the part that a change concerns. */
export function whatOf(change: Change): string {
  if (change.kind === "set-field") return change.field;
  if (change.kind === "set-layer") return change.layer;
  return `want ${change.to}`;
}

/** The value as a review record, or null when it does not have a record's fields. */
export function asReviewRecord(value: unknown): ReviewRecord | null {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return null;
  const held = value as Record<string, unknown>;
  if (typeof held.what !== "string" || typeof held.at !== "string") return null;
  if (held.by !== "user" && held.by !== "agent") return null;
  if (held.state !== "accepted" && held.state !== "rejected") return null;
  return {
    what: held.what,
    by: held.by,
    state: held.state,
    at: held.at,
    rationale: typeof held.rationale === "string" ? held.rationale : "",
    simulated: held.simulated === true,
  };
}

/** The review records an element holds, in the map's order. A record of another form is left out. */
export function reviewRecords(element: SpecElement): ReviewRecord[] {
  return (element.layers[REVIEW_LAYER] ?? []).flatMap((record) => asReviewRecord(record) ?? []);
}

/**
 * The status that the review history gives one part of an element: user-authored or accepted,
 * from the newest accepted record that names the part. Null when no accepted record names it.
 * The map records no author, so this status says who wrote the part when it was last reviewed in
 * the page; a later write from outside the page does not change it.
 */
export function recordedStatus(element: SpecElement | undefined, what: string): EvidenceStatus | null {
  if (element === undefined) return null;
  let newest: ReviewRecord | null = null;
  for (const record of reviewRecords(element)) {
    if (record.what !== what || record.state !== "accepted") continue;
    if (newest === null || record.at >= newest.at) newest = record;
  }
  return newest === null ? null : newest.by === "user" ? "user-authored" : "accepted";
}

function markedStatus(mark: Mark): EvidenceStatus {
  return mark.origin === "user" ? "user-authored" : "accepted";
}

/**
 * The status of a want held by the element at `address`. A want that a change set and the server
 * has not confirmed is user-authored, or accepted when it came from an agent's proposal. A want
 * that an accepted review record names has that record's status. Any other want is inferred:
 * intake records no source reference for a want.
 */
export function wantEvidence(spec: Spec, address: Address, to: Address): Evidence {
  const mark = spec.marks.find((other) => other.address === address && other.want === to);
  if (mark) return { status: markedStatus(mark), paths: [] };
  return { status: recordedStatus(elementAt(spec, address), `want ${to}`) ?? "inferred", paths: [] };
}

/**
 * The status of one field of the element at `address`. A field that a change set and the server
 * has not confirmed is user-authored, or accepted when it came from an agent's proposal. A field
 * that an accepted review record names has that record's status. Otherwise the source reference
 * itself is source-backed, and any other field is inferred.
 */
export function fieldEvidence(spec: Spec, address: Address, field: FieldName): Evidence {
  const mark = spec.marks.find((other) => other.address === address && other.field === field);
  if (mark) return { status: markedStatus(mark), paths: [] };
  const recorded = recordedStatus(elementAt(spec, address), field);
  if (recorded !== null) return { status: recorded, paths: [] };
  const uri = elementAt(spec, address)?.uri;
  if (field === "uri" && uri !== undefined) return { status: "source-backed", paths: [uri] };
  return { status: "inferred", paths: [] };
}

/**
 * The status of one layer's records at the element at `address`: from a change that replaced
 * them and that the server has not confirmed, or else from an accepted review record that names
 * the layer. Null when neither exists.
 */
export function layerEvidence(spec: Spec, address: Address, layer: string): Evidence | null {
  const mark = spec.marks.find((other) => other.address === address && other.layer === layer);
  if (mark) return { status: markedStatus(mark), paths: [] };
  const recorded = recordedStatus(elementAt(spec, address), layer);
  return recorded === null ? null : { status: recorded, paths: [] };
}

/**
 * The status of a proposal: agent-proposed until the user reviews it, then accepted or rejected.
 * The paths are the evidence the proposal cites.
 */
export function proposalEvidence(proposal: Proposal): Evidence {
  const status: EvidenceStatus = proposal.state === "proposed" ? "agent-proposed" : proposal.state;
  return { status, paths: [...proposal.evidence] };
}
