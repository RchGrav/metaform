// Structure the view derives from the server's reads (seam rule 2): nesting, what a container
// shows, arrows to collapsed elements, wants that leave the container, pivot distance, and layer
// counts. Pure functions, so the mock and the real source give the same view.

import type { Address, RawDump, ShallowGraph } from "../source";

/** The view's own name for the project's top level. Never sent in an addressed read: {".": {}} is the raw dump (R-5.34). */
export const TOP = ".";

/** The root scope that holds layer definitions (R-6.24). It describes the map, not the project, so the graph leaves it out. */
export const LAYER_SCOPE = "layer";

export function parentOf(address: Address): Address {
  const cut = address.lastIndexOf(".");
  return cut < 0 ? TOP : address.slice(0, cut);
}

export function lastSegment(address: Address): string {
  return address.slice(address.lastIndexOf(".") + 1);
}

/** True when `address` is strictly beneath `container`. */
export function isBeneath(address: Address, container: Address): boolean {
  return container === TOP ? address !== TOP : address.startsWith(`${container}.`);
}

export function inLayerScope(address: Address): boolean {
  return address === LAYER_SCOPE || address.startsWith(`${LAYER_SCOPE}.`);
}

export function bandOf(address: Address): "project" | "upstream" | "downstream" {
  const scope = address.split(".")[0];
  return scope === "upstream" || scope === "downstream" ? scope : "project";
}

/** Every address the graph can show: the map's addresses without the `layer` scope. */
export function graphAddresses(graph: ShallowGraph): Address[] {
  return graph.addresses.filter((address) => !inLayerScope(address));
}

/** For each address, how many addresses are beneath it at any depth. */
export function beneathCounts(addresses: readonly Address[]): Map<Address, number> {
  const counts = new Map<Address, number>(addresses.map((address) => [address, 0]));
  for (const address of addresses) {
    let parent = parentOf(address);
    while (parent !== TOP) {
      counts.set(parent, (counts.get(parent) ?? 0) + 1);
      parent = parentOf(parent);
    }
  }
  return counts;
}

/**
 * The elements a container shows. Its direct children always show. An element deeper down shows
 * only when every element between it and the container is expanded. Elements with elements
 * beneath start collapsed, so a first view is not crowded (prompt: "without overwhelming").
 */
export function visibleIn(
  addresses: readonly Address[],
  container: Address,
  expanded: ReadonlySet<Address>,
): Set<Address> {
  const visible = new Set<Address>();
  for (const address of addresses) {
    if (!isBeneath(address, container)) continue;
    let parent = parentOf(address);
    let shown = true;
    while (parent !== container) {
      if (!expanded.has(parent)) {
        shown = false;
        break;
      }
      parent = parentOf(parent);
    }
    if (shown) visible.add(address);
  }
  return visible;
}

/** The visible element that stands for `address`: itself or its nearest visible ancestor; null when it lies outside the container. */
export function representative(address: Address, visible: ReadonlySet<Address>): Address | null {
  let at = address;
  while (at !== TOP) {
    if (visible.has(at)) return at;
    at = parentOf(at);
  }
  return null;
}

export interface SceneEdge {
  from: Address;
  to: Address;
  count: number;
  /** The wants this arrow stands for, as [holder, wanted]. */
  members: [Address, Address][];
}

/**
 * The arrows a container shows. Each want's two ends map to their representatives; wants whose
 * ends meet at one element are dropped; parallel wants merge into one arrow with a count. A want
 * with one end outside the container counts toward `outside` on the other end's representative.
 */
export function sceneEdges(
  graph: ShallowGraph,
  visible: ReadonlySet<Address>,
): { edges: SceneEdge[]; outside: Map<Address, number> } {
  const merged = new Map<string, SceneEdge>();
  const outside = new Map<Address, number>();
  for (const [holder, wanted] of graph.edges) {
    if (inLayerScope(holder) || inLayerScope(wanted)) continue;
    const from = representative(holder, visible);
    const to = representative(wanted, visible);
    if (from === null && to === null) continue;
    if (from === null || to === null) {
      const inside = (from ?? to) as Address;
      outside.set(inside, (outside.get(inside) ?? 0) + 1);
      continue;
    }
    if (from === to) continue;
    const id = `${from}->${to}`;
    const edge = merged.get(id);
    if (edge) {
      edge.count += 1;
      edge.members.push([holder, wanted]);
    } else merged.set(id, { from, to, count: 1, members: [[holder, wanted]] });
  }
  return { edges: [...merged.values()], outside };
}

/** Distance from `focus` along wants, holder to wanted, up to `limit` steps (UX section 10). */
export function wantDistances(focus: Address, edges: readonly SceneEdge[], limit: number): Map<Address, number> {
  const distance = new Map<Address, number>([[focus, 0]]);
  let frontier = [focus];
  for (let step = 1; step <= limit && frontier.length > 0; step += 1) {
    const next: Address[] = [];
    for (const edge of edges) {
      if (frontier.includes(edge.from) && !distance.has(edge.to)) {
        distance.set(edge.to, step);
        next.push(edge.to);
      }
    }
    frontier = next;
  }
  return distance;
}

/** The nested tree inside a raw dump: {".": tree}. */
function dumpTree(dump: RawDump): Record<string, unknown> {
  const tree = dump[TOP];
  return tree !== null && typeof tree === "object" && !Array.isArray(tree) ? (tree as Record<string, unknown>) : {};
}

function isObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/**
 * Layer names, from the definitions beneath `layer` in the dump: an element there with an
 * `instruction` defines the layer named by its last segment (R-6.24).
 */
export function layerNames(dump: RawDump): string[] {
  const names: string[] = [];
  const walk = (node: Record<string, unknown>, address: Address): void => {
    if (typeof node.instruction === "string" && address !== LAYER_SCOPE) names.push(lastSegment(address));
    for (const [key, value] of Object.entries(node)) {
      if (isObject(value) && key !== "wants") walk(value, `${address}.${key}`);
    }
  };
  const root = dumpTree(dump)[LAYER_SCOPE];
  if (isObject(root)) walk(root, LAYER_SCOPE);
  return names.sort();
}

/**
 * Record counts per address per layer: every array-valued field of an element in the dump is a
 * layer's records (R-6.24). Only the named layers are counted.
 */
export function layerCounts(dump: RawDump, layers: readonly string[]): Map<Address, Map<string, number>> {
  const counts = new Map<Address, Map<string, number>>();
  const walk = (node: Record<string, unknown>, address: Address): void => {
    for (const [key, value] of Object.entries(node)) {
      if (Array.isArray(value) && layers.includes(key) && value.length > 0) {
        const at = counts.get(address) ?? new Map<string, number>();
        at.set(key, value.length);
        counts.set(address, at);
      } else if (isObject(value) && key !== "wants") {
        walk(value, address === TOP ? key : `${address}.${key}`);
      }
    }
  };
  walk(dumpTree(dump), TOP);
  return counts;
}

/** Each element's scalar fields, from the raw dump: what a read of the element returns (R-5.10). */
export function fieldsFromDump(dump: RawDump): Map<Address, Record<string, unknown>> {
  const out = new Map<Address, Record<string, unknown>>();
  const walk = (node: Record<string, unknown>, address: Address): void => {
    const own: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(node)) {
      if (isObject(value)) {
        if (key !== "wants") walk(value, address === TOP ? key : `${address}.${key}`);
      } else if (!Array.isArray(value)) {
        own[key] = value;
      }
    }
    if (address !== TOP) out.set(address, own);
  };
  walk(dumpTree(dump), TOP);
  return out;
}

/**
 * The address an outside element has in its own project's map (SPEC R-4.15): our
 * upstream.code.engine.game is their code.engine.game. Addresses inside the project are unchanged.
 */
export function outsideAddress(address: Address): Address {
  return bandOf(address) === "project" ? address : address.slice(address.indexOf(".") + 1);
}

/** Each element's want records, from the raw dump: holder → wanted → record (R-3.5, R-3.6). */
export function wantsFromDump(dump: RawDump): Map<Address, Record<Address, Record<string, unknown>>> {
  const out = new Map<Address, Record<Address, Record<string, unknown>>>();
  const walk = (node: Record<string, unknown>, address: Address): void => {
    for (const [key, value] of Object.entries(node)) {
      if (!isObject(value)) continue;
      if (key === "wants") {
        const records: Record<Address, Record<string, unknown>> = {};
        for (const [other, record] of Object.entries(value)) if (isObject(record)) records[other] = record;
        if (address !== TOP) out.set(address, records);
      } else {
        walk(value, address === TOP ? key : `${address}.${key}`);
      }
    }
  };
  walk(dumpTree(dump), TOP);
  return out;
}

/** One element per this many square pixels of canvas, for the start-up budget (UX section 12a). */
export const PIXELS_PER_ELEMENT = 34_000;
export const MIN_START_ELEMENTS = 12;
export const MAX_START_ELEMENTS = 60;

/** How many elements a first view of a container may show on a canvas of this size. */
export function startBudget(width: number, height: number): number {
  const fits = Math.round((Math.max(0, width) * Math.max(0, height)) / PIXELS_PER_ELEMENT);
  return Math.min(MAX_START_ELEMENTS, Math.max(MIN_START_ELEMENTS, fits));
}

/**
 * The elements to expand on a first view of a container, so the start-up fills the screen
 * (owner, 2026-11-09: "barely shows anything"). Within a level, elements open smallest first while
 * the visible count stays within the budget; the next level is tried only after the whole level
 * opened, so the view never goes deep on one side while a sibling stays closed.
 */
export function startExpansion(addresses: readonly Address[], container: Address, budget: number): Address[] {
  const childrenOf = new Map<Address, Address[]>();
  for (const address of addresses) {
    if (!isBeneath(address, container)) continue;
    const parent = parentOf(address);
    const list = childrenOf.get(parent) ?? [];
    list.push(address);
    childrenOf.set(parent, list);
  }
  const count = (address: Address) => childrenOf.get(address)?.length ?? 0;
  let level = childrenOf.get(container) ?? [];
  let visible = level.length;
  const expanded: Address[] = [];
  for (;;) {
    const candidates = level
      .filter((address) => count(address) > 0)
      .sort((a, b) => count(a) - count(b) || (a < b ? -1 : 1));
    const opened: Address[] = [];
    for (const address of candidates) {
      if (visible + count(address) > budget) continue;
      opened.push(address);
      visible += count(address);
    }
    expanded.push(...opened);
    if (opened.length < candidates.length || opened.length === 0) return expanded;
    level = opened.flatMap((address) => childrenOf.get(address) ?? []);
  }
}
