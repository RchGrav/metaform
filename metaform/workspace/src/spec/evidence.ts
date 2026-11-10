// Evidence status (ARCHITECTURE.md section 2). The map records no status field. The statuses
// source-backed, inferred and unverified are derived here from what the map holds.

import type { Address } from "../source/types";
import type { Proposal } from "./changes";
import { elementAt } from "./model";
import type { FieldName, Mark, Spec, SpecElement } from "./model";

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

function markedStatus(mark: Mark): EvidenceStatus {
  return mark.origin === "user" ? "user-authored" : "accepted";
}

/**
 * The status of a want held by the element at `address`. A want that a change set and the server
 * has not confirmed is user-authored, or accepted when it came from an agent's proposal. Any
 * other want is inferred: intake records no source reference for a want.
 */
export function wantEvidence(spec: Spec, address: Address, to: Address): Evidence {
  const mark = spec.marks.find((other) => other.address === address && other.want === to);
  return { status: mark ? markedStatus(mark) : "inferred", paths: [] };
}

/**
 * The status of one field of the element at `address`. A field that a change set and the server
 * has not confirmed is user-authored, or accepted when it came from an agent's proposal. The
 * source reference itself is source-backed. Any other field is inferred.
 */
export function fieldEvidence(spec: Spec, address: Address, field: FieldName): Evidence {
  const mark = spec.marks.find((other) => other.address === address && other.field === field);
  if (mark) return { status: markedStatus(mark), paths: [] };
  const uri = elementAt(spec, address)?.uri;
  if (field === "uri" && uri !== undefined) return { status: "source-backed", paths: [uri] };
  return { status: "inferred", paths: [] };
}

/**
 * The status of one layer's records at the element at `address`, when a change replaced them and
 * the server has not confirmed it. Null when no change is pending there.
 */
export function layerEvidence(spec: Spec, address: Address, layer: string): Evidence | null {
  const mark = spec.marks.find((other) => other.address === address && other.layer === layer);
  return mark ? { status: markedStatus(mark), paths: [] } : null;
}

/**
 * The status of a proposal: agent-proposed until the user reviews it, then accepted or rejected.
 * The paths are the evidence the proposal cites.
 */
export function proposalEvidence(proposal: Proposal): Evidence {
  const status: EvidenceStatus = proposal.state === "proposed" ? "agent-proposed" : proposal.state;
  return { status, paths: [...proposal.evidence] };
}
