// The shape of workspace.json, written by build_mock.py. SIMULATED data.

import type { Address } from "../source/types";

/** A raw dump: the nested tree that {".": {}} returns under the "." key. */
export type Tree = { [key: string]: unknown };

export interface MockProject {
  id: string;
  name: string;
  folder: string;
  dump: Tree;
}

/** A simulated agent. Metaform has no presence source yet (seam gap 2). */
export interface MockAgent {
  id: string;
  name: string;
  project: string;
  at: Address | null;
  activity: string;
}

/** A simulated update, played `after_s` seconds after the source starts. */
export interface MockEvent {
  after_s: number;
  agent: string;
  project: string;
  address: Address;
  /** Appends one record to a layer at `address`. */
  write?: { layer: string; record: unknown };
  /** Moves the agent's presence to another address. */
  move?: Address;
}

export interface MockWorkspace {
  simulated: true;
  projects: Record<string, MockProject>;
  agents: MockAgent[];
  events: MockEvent[];
}
