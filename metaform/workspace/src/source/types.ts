// The seam between the graph workspace and its data (dev/graph_workspace_seam.md).
// Each result type is the Metaform server's own result, unchanged, as read at commit 61ef6dc.
// The mock and the Metaform adapter both implement GraphSource and WorkspaceEvents.

/** A dotted element address, such as "code.server.relay" (R-3.2). The root is never named. */
export type Address = string;

export type Role = "Definitive" | "Supportive" | "Notable" | "Divergent";

/** A project registered in the home. `id` is opaque: never parse it. */
export interface ProjectRef {
  id: string;
  name: string;
  folder: string;
}

/** The result of {"map": {}} (R-5.11): addresses, want edges and the one Definitive element. */
export interface ShallowGraph {
  addresses: Address[];
  /** [holder, wanted]: the holder wants the wanted element. */
  edges: [holder: Address, wanted: Address][];
  definitive: Address | null;
}

/** One want, held by the element that wants (R-3.6). */
export interface Want {
  why?: string;
  how?: string;
  direction?: string;
  [field: string]: unknown;
}

/** An element's scalar fields (`model.rs` `base_fields`). */
export interface ElementFields {
  technical_name?: string;
  name?: string;
  role?: Role;
  uri?: string;
  status?: string;
  [field: string]: unknown;
}

/** The result of {"goto": "<address>"} (R-5.30, R-6.27). */
export interface SummarySheet {
  at: Address;
  element: ElementFields;
  wants: Record<Address, Want>;
  wanted_by: Record<Address, Want>;
  layers: Record<string, { records: number }>;
  skills: Record<string, { name: string; description?: string; uri?: string }>;
  memory: { records: number };
  /** Layer guidance; the server delivers each entry once per connection. */
  instructions?: Record<string, string>;
}

/** The result of {".": {}} (R-5.34): {".": <the stored nested tree, every layer included>}. */
export type RawDump = { [path: string]: unknown };

/**
 * A refusal or store failure, as the server sends it (`refusal_json`): the echoed command,
 * then `status`, `code`, `message`, `remediation`, and `tested_sentence` where one applies.
 */
export interface Refusal {
  status: "error";
  code: string;
  message: string;
  remediation: unknown;
  tested_sentence?: string;
  [echoed: string]: unknown;
}

export interface GraphSource {
  projects(): Promise<ProjectRef[]>;
  map(project: string): Promise<ShallowGraph>;
  dump(project: string): Promise<RawDump>;
  goto(project: string, at: Address): Promise<SummarySheet>;
  layerRecords(project: string, at: Address, layer: string): Promise<unknown[]>;
}

/** `map-changed` carries no diff: the view refetches `map` and `dump` (seam rule 1). */
export type WorkspaceEvent =
  | { kind: "map-changed"; project: string; simulated: boolean }
  | {
      kind: "agent-presence";
      project: string;
      agent: string;
      /** The agent's display name, when the source knows it. Show `name ?? agent`. */
      name?: string;
      at: Address | null;
      activity: string;
      /** Always true: Metaform has no presence source yet (seam gap 2). */
      simulated: true;
    };

/** Named WorkspaceEvents, not EventSource, so it does not shadow the browser's EventSource. */
export interface WorkspaceEvents {
  /** Returns a function that unsubscribes. */
  subscribe(project: string, listener: (event: WorkspaceEvent) => void): () => void;
}
