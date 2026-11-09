// The mock GraphSource and WorkspaceEvents (dev/graph_workspace_graph.md, section 5).
// SIMULATED: no Metaform server is involved. Each project is stored as its raw dump, and every
// read is derived from that dump by the same rules as metaform-core's reads.rs at 61ef6dc
// (`shallow`, `goto`, `read`, `raw`), so the mock returns the server's result shapes.

import type {
  Address,
  ElementFields,
  GraphSource,
  ProjectRef,
  RawDump,
  ShallowGraph,
  SummarySheet,
  Want,
  WorkspaceEvent,
  WorkspaceEvents,
} from "../source/types";
import { RefusalError } from "../source/errors";
import type { MockEvent, MockWorkspace, Tree } from "./workspace";

const LAYER_SCOPE = "layer";
/** Array fields that are not counted as layers in the summary sheet (reads.rs OWN_PARTS). */
const OWN_PARTS = new Set(["memory", "skills"]);
const DEFINITIVE = new Set(["de", "defining", "definitive"]);

interface Element {
  fields: Record<string, unknown>;
  wants: Record<Address, Want>;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Byte order, as Rust's BTreeMap<String, _> orders addresses. Addresses are ASCII. */
function byAddress(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

/** Flattens a raw dump into elements keyed by address. "" is the root. */
function flatten(tree: Tree): Map<Address, Element> {
  const out = new Map<Address, Element>();
  const walk = (node: Tree, address: Address): void => {
    const element: Element = { fields: {}, wants: {} };
    for (const [key, value] of Object.entries(node)) {
      if (key === "wants" && isObject(value)) element.wants = value as Record<Address, Want>;
      else if (isObject(value)) walk(value as Tree, address ? `${address}.${key}` : key);
      else element.fields[key] = value;
    }
    out.set(address, element);
  };
  walk(tree, "");
  return out;
}

function isDefinitive(role: unknown): boolean {
  return typeof role === "string" && DEFINITIVE.has(role.toLowerCase());
}

function isSkeleton(element: Element): boolean {
  return ["technical_name", "name", "role"].every((key) => {
    const value = element.fields[key];
    return typeof value === "string" && value.trim() !== "";
  });
}

function inLayerScope(address: Address): boolean {
  return address === LAYER_SCOPE || address.startsWith(`${LAYER_SCOPE}.`);
}

function baseFields(element: Element): ElementFields {
  return Object.fromEntries(
    Object.entries(element.fields).filter(([, value]) => !Array.isArray(value)),
  ) as ElementFields;
}

function notFound(command: object, address: Address): RefusalError {
  return new RefusalError({
    ...command,
    status: "error",
    code: "NOT_FOUND",
    message: `'${address}' does not exist`,
    remediation: { map: {} },
  });
}

/** One project's elements, rebuilt from its dump after every simulated write. */
class ProjectMap {
  readonly elements: Map<Address, Element>;
  readonly sorted: Address[];

  constructor(readonly tree: Tree) {
    this.elements = flatten(tree);
    this.sorted = [...this.elements.keys()].filter((a) => a !== "").sort(byAddress);
  }

  element(address: Address): Element | undefined {
    return address === "" ? undefined : this.elements.get(address);
  }

  /** Layer definitions: elements beneath `layer` with an `instruction`; the first by address wins a name. */
  definitions(): { layer: string; address: Address; instruction: string }[] {
    const out: { layer: string; address: Address; instruction: string }[] = [];
    for (const address of this.sorted) {
      const instruction = this.elements.get(address)?.fields["instruction"];
      if (!address.startsWith(`${LAYER_SCOPE}.`) || typeof instruction !== "string") continue;
      const layer = address.slice(address.lastIndexOf(".") + 1);
      if (!out.some((d) => d.layer === layer)) out.push({ layer, address, instruction });
    }
    return out;
  }

  recordsAllowed(address: Address): boolean {
    if (address === "") {
      return [...this.elements.values()].some((e) => isDefinitive(e.fields["role"]));
    }
    const element = this.elements.get(address);
    return !inLayerScope(address) && element !== undefined && isSkeleton(element);
  }
}

type Timer = ReturnType<typeof setTimeout>;

export interface MockOptions {
  /** Plays the simulated updates. Off for tests that need a fixed map. */
  playEvents?: boolean;
  /** Replaces setTimeout, so tests can play events without waiting. */
  schedule?: (run: () => void, ms: number) => Timer;
}

export class MockSource implements GraphSource, WorkspaceEvents {
  /** Shown by the views wherever this source supplies data. */
  readonly simulated = true;
  private readonly maps = new Map<string, ProjectMap>();
  /** Outside maps by repository uri. */
  private readonly outside = new Map<string, ProjectMap>();
  private readonly refs: ProjectRef[];
  private readonly listeners = new Map<string, Set<(event: WorkspaceEvent) => void>>();
  /** Layers whose guidance this source has already delivered, per project (R-6.27). */
  private readonly delivered = new Map<string, Set<string>>();
  private readonly timers: Timer[] = [];
  private readonly workspace: MockWorkspace;
  private readonly options: MockOptions;

  constructor(workspace: MockWorkspace, options: MockOptions = {}) {
    // A deep copy, so simulated writes never change the imported module's data.
    this.workspace = structuredClone(workspace);
    this.options = options;
    this.refs = Object.values(this.workspace.projects).map(({ id, name, folder }) => ({
      id,
      name,
      folder,
    }));
    for (const project of Object.values(this.workspace.projects)) {
      this.maps.set(project.id, new ProjectMap(project.dump));
    }
    for (const [uri, outside] of Object.entries(this.workspace.outside ?? {})) {
      this.outside.set(uri, new ProjectMap(outside.dump));
    }
    if (options.playEvents ?? true) this.play();
  }

  private project(id: string): ProjectMap {
    const map = this.maps.get(id);
    if (!map) throw notFound({ project: id }, id);
    return map;
  }

  async projects(): Promise<ProjectRef[]> {
    return this.refs.map((ref) => ({ ...ref }));
  }

  /**
   * {"map": {}} (reads.rs `shallow`). With `at`, the proposed read {"map": "<address>"}: the
   * outside project's map that the element at `at` names by its `uri`, in that map's own
   * addresses (SPEC c7f9eb2). Not in the server yet; an owner contract decision.
   */
  async map(project: string, at?: Address): Promise<ShallowGraph> {
    const map = at === undefined ? this.project(project) : this.outsideOf(project, at);
    const edges: [Address, Address][] = [];
    for (const address of map.sorted) {
      for (const other of Object.keys(map.elements.get(address)?.wants ?? {})) {
        edges.push([address, other]);
      }
    }
    const definitive =
      map.sorted.find((a) => isDefinitive(map.elements.get(a)?.fields["role"])) ?? null;
    return { addresses: [...map.sorted], edges, definitive };
  }

  /** The outside map an element names by its `uri`, or a refusal. */
  private outsideOf(project: string, at: Address): ProjectMap {
    const element = this.project(project).element(at);
    if (!element) throw notFound({ map: at }, at);
    const uri = element.fields["uri"];
    const outside = typeof uri === "string" ? this.outside.get(uri) : undefined;
    if (!outside) {
      // Mock wording: the server has no refusal for this read yet.
      throw new RefusalError({
        map: at,
        status: "error",
        code: "NOT_FOUND",
        message: `'${at}' names no outside map`,
        remediation: { goto: at },
      });
    }
    return outside;
  }

  /** {".": {}} (reads.rs `raw`): the stored nested tree, keyed by ".". */
  async dump(project: string): Promise<RawDump> {
    return { ".": structuredClone(this.project(project).tree) };
  }

  /** {"goto": "<address>"} (reads.rs `goto`). */
  async goto(project: string, at: Address): Promise<SummarySheet> {
    const map = this.project(project);
    const element = map.element(at);
    if (!element) throw notFound({ goto: at }, at);

    const wantedBy: Record<Address, Want> = {};
    for (const holder of map.sorted) {
      const want = holder === at ? undefined : map.elements.get(holder)?.wants[at];
      if (want) wantedBy[holder] = structuredClone(want);
    }

    const layers: Record<string, { records: number }> = {};
    for (const [key, value] of Object.entries(element.fields)) {
      if (Array.isArray(value) && !OWN_PARTS.has(key)) layers[key] = { records: value.length };
    }
    const defined = map.recordsAllowed(at) ? map.definitions() : [];
    for (const definition of defined) layers[definition.layer] ??= { records: 0 };

    const skills: SummarySheet["skills"] = {};
    const root = map.elements.get("");
    for (const holder of [root, element]) {
      const list = holder?.fields["skills"];
      if (!Array.isArray(list)) continue;
      for (const skill of list) {
        if (!isObject(skill)) continue;
        const front = isObject(skill["frontmatter"]) ? skill["frontmatter"] : skill;
        const name = front["name"];
        if (typeof name !== "string") continue;
        const entry: SummarySheet["skills"][string] = { name };
        if (typeof front["description"] === "string") entry.description = front["description"];
        if (typeof skill["uri"] === "string") entry.uri = skill["uri"];
        skills[name] = entry;
      }
    }

    const memory = element.fields["memory"];
    const sheet: SummarySheet = {
      at,
      element: baseFields(element),
      wants: structuredClone(element.wants),
      wanted_by: wantedBy,
      layers,
      skills,
      memory: { records: Array.isArray(memory) ? memory.length : 0 },
    };

    // The server delivers each layer's guidance once per connection; this source stands in for
    // one connection per project.
    const seen = this.delivered.get(project) ?? new Set<string>();
    this.delivered.set(project, seen);
    const fresh = defined.filter((d) => !seen.has(d.layer));
    if (fresh.length > 0) {
      sheet.instructions = Object.fromEntries(fresh.map((d) => [d.layer, d.instruction]));
      for (const d of fresh) seen.add(d.layer);
    }
    return sheet;
  }

  /** {"<address>": {"<layer>": {}}} (reads.rs `read`), unwrapped as MetaformSource does. */
  async layerRecords(project: string, at: Address, layer: string): Promise<unknown[]> {
    const map = this.project(project);
    const element = map.element(at);
    if (!element) throw notFound({ [at]: { [layer]: {} } }, at);
    const value = element.fields[layer];
    return Array.isArray(value) ? structuredClone(value) : [];
  }

  subscribe(project: string, listener: (event: WorkspaceEvent) => void): () => void {
    const set = this.listeners.get(project) ?? new Set();
    this.listeners.set(project, set);
    set.add(listener);
    // Announce where the simulated agents are now, so presence shows without waiting.
    for (const agent of this.workspace.agents) {
      if (agent.project !== project) continue;
      listener({
        kind: "agent-presence",
        project,
        agent: agent.id,
        at: agent.at,
        activity: agent.activity,
        simulated: true,
      });
    }
    return () => set.delete(listener);
  }

  /** Ends the simulated updates. */
  close(): void {
    for (const timer of this.timers) clearTimeout(timer);
    this.timers.length = 0;
  }

  private emit(event: WorkspaceEvent): void {
    for (const listener of this.listeners.get(event.project) ?? []) listener(event);
  }

  private play(): void {
    const schedule = this.options.schedule ?? ((run, ms) => setTimeout(run, ms));
    for (const event of this.workspace.events) {
      this.timers.push(schedule(() => this.apply(event), event.after_s * 1000));
    }
  }

  /** Applies one simulated update, then announces it as the server would. */
  apply(event: MockEvent): void {
    const project = this.workspace.projects[event.project];
    const agent = this.workspace.agents.find((a) => a.id === event.agent);
    if (!project || !agent) return;
    if (event.move !== undefined) {
      agent.at = event.move;
      agent.activity = "moved";
    }
    if (event.write) {
      let node: Tree = project.dump;
      for (const segment of event.address.split(".")) {
        const next = node[segment];
        if (!isObject(next)) return;
        node = next as Tree;
      }
      const records = node[event.write.layer];
      node[event.write.layer] = [...(Array.isArray(records) ? records : []), event.write.record];
      this.maps.set(project.id, new ProjectMap(project.dump));
      agent.at = event.address;
      agent.activity = `writing ${event.write.layer}`;
      this.emit({ kind: "map-changed", project: project.id, simulated: true });
    }
    this.emit({
      kind: "agent-presence",
      project: project.id,
      agent: agent.id,
      at: agent.at,
      activity: agent.activity,
      simulated: true,
    });
  }
}
