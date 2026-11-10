// Port of `metaform-core/src/refusal.rs`. Refusals (R-5.24): a fixed error code, a message in
// plain words, the tested sentence where one applies, and the remediation command that fixes it.
// The rule each code stands for is documentation in the Rust file and is not part of an answer.

import type { Json, JsonObject } from "./json.ts";
import { obj } from "./json.ts";

/** The fixed error codes, as an agent receives them. */
export const Code = {
  TechnicalNameAlignmentFailure: "TECHNICAL_NAME_ALIGNMENT_FAILURE",
  CanonicalNameCollisionFailure: "CANONICAL_NAME_COLLISION_FAILURE",
  RoleTaxonomyFailure: "ROLE_TAXONOMY_FAILURE",
  GrammarConstraintViolation: "GRAMMAR_CONSTRAINT_VIOLATION",
  FieldMismatch: "FIELD_MISMATCH",
  RootScopeNotAllowed: "ROOT_SCOPE_NOT_ALLOWED",
  FieldElementCollision: "FIELD_ELEMENT_COLLISION",
  LayerNotRegistered: "LAYER_NOT_REGISTERED",
  DependencyLock: "DEPENDENCY_LOCK",
  NameRoundTripFailure: "NAME_ROUND_TRIP_FAILURE",
  NotFound: "NOT_FOUND",
  ElementsBeneath: "ELEMENTS_BENEATH",
  WantIncomplete: "WANT_INCOMPLETE",
  ElementNotInSkeleton: "ELEMENT_NOT_IN_SKELETON",
  HeadingLevelInvalid: "HEADING_LEVEL_INVALID",
  HeadingInText: "HEADING_IN_TEXT",
  LayerDefinitionLocked: "LAYER_DEFINITION_LOCKED",
  CodeNotUnique: "CODE_NOT_UNIQUE",
  LayerNameCollision: "LAYER_NAME_COLLISION",
  InternalError: "INTERNAL_ERROR",
} as const;

export type CodeName = (typeof Code)[keyof typeof Code];

/** A refused command. A refused command stores nothing (R-5.8). The core throws it. */
export class Refusal {
  code: CodeName;
  reason: string;
  /** The tested sentence, where the rule tests one. */
  sentence: string | null = null;
  /** The command that fixes the problem, or `null` where no command can be derived. */
  remediation: Json;

  constructor(code: CodeName, reason: string, remediation: Json | undefined) {
    this.code = code;
    this.reason = reason;
    this.remediation = remediation ?? null;
  }

  /**
   * The refusal's own fields, in the founder's order: `code`, `message`, the `tested_sentence`
   * where one applies, and `remediation`. The store puts the echoed command and
   * `"status": "error"` in front (`refusalJson` in `store.ts`).
   */
  toJson(): JsonObject {
    const out = obj(["code", this.code], ["message", this.reason]);
    if (this.sentence !== null) {
      out.set("tested_sentence", this.sentence);
    }
    out.set("remediation", this.remediation);
    return out;
  }
}
