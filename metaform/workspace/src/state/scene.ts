// Builds the RenderScene from the view state and the server's reads. Every decision about
// meaning happens here, so the renderer only lays out and draws (src/graph/renderer.ts).

import type { Address, Role, ShallowGraph, SummarySheet } from "../source";
import type { AgentMark, RenderEdge, RenderNode, RenderScene } from "../graph/renderer";
import { FOCUS_REACH, currentView, layerShown, type ViewState } from "./view";
import {
  TOP,
  bandOf,
  beneathCounts,
  graphAddresses,
  lastSegment,
  parentOf,
  sceneEdges,
  visibleIn,
  wantDistances,
} from "./structure";

/** What the scene needs that the state does not hold: the project's reads and the simulated agents. */
export interface SceneInput {
  graph: ShallowGraph;
  /** The whole map's addresses, for beneath counts when `graph` is a part of it (Element mode). */
  fullAddresses?: readonly Address[];
  /** Element fields by address, from the raw dump; role and status drive node marks. */
  fields: ReadonlyMap<Address, SummarySheet["element"]>;
  /** Record counts per address per layer, from the raw dump. */
  layerCounts: ReadonlyMap<Address, ReadonlyMap<string, number>>;
  /** Every layer name, in a stable order; a layer's index is its style. */
  layers: readonly string[];
  agents: readonly { id: string; name: string; at: Address | null; active: boolean }[];
  /** True for an element that names another project (seam gap 3). */
  opensProject: (address: Address) => boolean;
}

const ROLES: readonly Role[] = ["Definitive", "Supportive", "Notable", "Divergent"];

function roleOf(value: unknown): Role | null {
  return ROLES.find((role) => typeof value === "string" && role.toLowerCase() === value.toLowerCase()) ?? null;
}

function initials(name: string): string {
  const words = name.split(/\s+/).filter(Boolean);
  const letters = words.length > 1 ? `${words[0]?.[0] ?? ""}${words[1]?.[0] ?? ""}` : name.slice(0, 2);
  return letters.toUpperCase();
}

/** The nearest visible element for an address, or null when it lies outside the container. */
function nearestVisible(address: Address, visible: ReadonlySet<Address>): Address | null {
  let at = address;
  while (at !== TOP) {
    if (visible.has(at)) return at;
    at = parentOf(at);
  }
  return null;
}

/**
 * The graph scene. `only` replaces the container's visible set with exactly these addresses
 * (Element mode); beneath counts still come from the whole map.
 */
export function buildScene(state: ViewState, input: SceneInput, only?: readonly Address[]): RenderScene {
  const view = currentView(state);
  const addresses = graphAddresses(input.graph);
  const counts = beneathCounts(only ? input.fullAddresses ?? addresses : addresses);
  const expanded = new Set(view.expanded);
  const visible = only ? new Set(only) : visibleIn(addresses, view.container, expanded);
  const { edges, outside } = sceneEdges(input.graph, visible);

  const reach = view.focus !== null && visible.has(view.focus) ? wantDistances(view.focus, edges, FOCUS_REACH) : null;
  const unseen = new Set<Address>();
  for (const address of view.unseen) {
    const shown = nearestVisible(address, visible);
    if (shown !== null) unseen.add(shown);
  }
  const agentsAt = new Map<Address, AgentMark[]>();
  for (const agent of input.agents) {
    if (agent.at === null) continue;
    const shown = nearestVisible(agent.at, visible);
    if (shown === null) continue;
    const marks = agentsAt.get(shown) ?? [];
    marks.push({ id: agent.id, initials: initials(agent.name), active: agent.active });
    agentsAt.set(shown, marks);
  }

  // A collapsed element carries the records of the elements hidden beneath it, as its arrows
  // carry their wants; otherwise an isolated layer whose records sit deeper looks absent.
  const rolled = new Map<Address, Map<string, number>>();
  for (const [address, perLayer] of input.layerCounts) {
    const shown = only ? (visible.has(address) ? address : null) : nearestVisible(address, visible);
    if (shown === null) continue;
    const into = rolled.get(shown) ?? new Map<string, number>();
    for (const [layer, n] of perLayer) into.set(layer, (into.get(layer) ?? 0) + n);
    rolled.set(shown, into);
  }

  const shownLayers = input.layers.filter((layer) => layerShown(state, layer));
  const nodes: RenderNode[] = [...visible].sort().map((address) => {
    const fields = input.fields.get(address) ?? {};
    const role = roleOf(fields.role);
    const own = rolled.get(address);
    const parent = parentOf(address);
    const isolatedMissing = state.isolated !== null && !(own?.get(state.isolated) ?? 0);
    const tooFar = reach !== null && !reach.has(address);
    return {
      address,
      label: lastSegment(address),
      parent: !only && parent !== view.container && visible.has(parent) ? parent : null,
      role,
      status: typeof fields.status === "string" ? fields.status : null,
      band: bandOf(address),
      beneath: counts.get(address) ?? 0,
      collapsed: !expanded.has(address),
      definitive: input.graph.definitive === address || role === "Definitive",
      selected: view.selection === address,
      focus: view.focus === address,
      dimmed: isolatedMissing || tooFar,
      unseen: unseen.has(address),
      outside: outside.get(address) ?? 0,
      opensProject: input.opensProject(address),
      layers: shownLayers
        .map((layer) => ({ layer, records: own?.get(layer) ?? 0, style: input.layers.indexOf(layer) }))
        .filter((mark) => mark.records > 0),
      agents: agentsAt.get(address) ?? [],
    };
  });

  const renderEdges: RenderEdge[] = edges
    .map((edge) => ({
      id: `${edge.from}->${edge.to}`,
      from: edge.from,
      to: edge.to,
      count: edge.count,
      dimmed: reach !== null && !(reach.has(edge.from) && reach.has(edge.to)),
    }))
    .sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));

  return { nodes, edges: renderEdges, top: reach !== null ? view.focus : null };
}

/**
 * The Element mode scene (UX section 3): the element in the middle, what it wants below it, and
 * what wants it above it, each as a full address. Uses the same marks as the graph scene.
 */
export function elementScene(state: ViewState, input: SceneInput, at: Address, sheet: SummarySheet): RenderScene {
  const wanted = Object.keys(sheet.wants);
  const wanters = Object.keys(sheet.wanted_by);
  const addresses = [...new Set([at, ...wanted, ...wanters])];
  const edges: [Address, Address][] = [
    ...wanters.map((holder): [Address, Address] => [holder, at]),
    ...wanted.map((other): [Address, Address] => [at, other]),
  ];
  const graph = { addresses, edges, definitive: input.graph.definitive };
  // Every address shown at the top level, with the element's wanters placed above it by the layout.
  const flat: ViewState = {
    ...state,
    views: state.project === null ? state.views : {
      ...state.views,
      [state.project]: { ...currentView(state), container: TOP, focus: null, expanded: [] },
    },
  };
  const scene = buildScene(flat, { ...input, graph, fullAddresses: graphAddresses(input.graph) }, addresses);
  return { ...scene, top: wanters.length > 0 ? null : at };
}
