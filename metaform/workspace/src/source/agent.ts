// The seam to an agent service that proposes changes to the specification (ARCHITECTURE.md
// section 3). No agent service is reachable from the host today, so the only implementation is
// the simulated one in src/mock/agent.ts. A real service implements the same interface.

import type { Proposal } from "../spec/changes";
import type { Spec } from "../spec/model";
import type { Address } from "./types";

/**
 * What a request for proposals covers: the whole project, a functional area (every element whose
 * address is `prefix` or lies beneath it), or one element.
 */
export type ProposalScope =
  | { kind: "project" }
  | { kind: "area"; prefix: Address }
  | { kind: "element"; address: Address };

/** A service that reads a specification and proposes changes to it. It never writes to the map. */
export interface AgentService {
  /** The name the page shows as the proposer. */
  readonly name: string;
  /** True when a local generator makes the proposals and no agent service does. */
  readonly simulated: boolean;
  /**
   * Proposes changes to the elements in the scope. Each proposal has the state `proposed`, a
   * rationale, and the text or the source path it was derived from as evidence.
   */
  propose(spec: Spec, scope: ProposalScope): Promise<Proposal[]>;
}

/** True when the address is in the scope. */
export function inProposalScope(address: Address, scope: ProposalScope): boolean {
  if (scope.kind === "project") return true;
  if (scope.kind === "element") return address === scope.address;
  return address === scope.prefix || address.startsWith(`${scope.prefix}.`);
}
