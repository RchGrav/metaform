// Builds the RenderScene from the view state and the server's reads. Every decision about
// meaning happens here, so the renderer only lays out and draws (src/graph/renderer.ts).

import type { Address, Role, ShallowGraph, SummarySheet } from "../source";
import type { AgentMark, RenderEdge, RenderNode, RenderScene } from "../graph/renderer";
import { FOCUS_REACH, currentView, layerShown, type ViewState } from "./view";
import {
  TOP,
  inLayerScope,
  isBeneath,
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
  /** Want records per holder, from the raw dump: direction and why for each arrow. */
  wants?: ReadonlyMap<Address, Record<Address, Record<string, unknown>>>;
  /** Record counts per address per layer, from the raw dump. */
  layerCounts: ReadonlyMap<Address, ReadonlyMap<string, number>>;
  /** Every layer name, in a stable order; a layer's index is its style. */
  layers: readonly string[];
  agents: readonly { id: string; name: string; at: Address | null; active: boolean; doing?: string | null }[];
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
    marks.push({ id: agent.id, name: agent.name, initials: initials(agent.name), active: agent.active, doing: agent.doing ?? null });
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
      technicalName: typeof fields.technical_name === "string" ? fields.technical_name : null,
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

  const DIRECTIONS = ["outbound", "inbound", "two-way"] as const;
  const recordOf = ([holder, wanted]: [Address, Address]) => input.wants?.get(holder)?.[wanted];
  const directionOf = (members: [Address, Address][]): RenderEdge["direction"] => {
    const found = new Set(
      members.map((m) => recordOf(m)?.direction).filter((d): d is (typeof DIRECTIONS)[number] => DIRECTIONS.includes(d as never)),
    );
    if (found.size === 0) return null;
    return found.size === 1 ? [...found][0] ?? null : "mixed";
  };
  const renderEdges: RenderEdge[] = edges
    .map((edge) => {
      const single = edge.members.length === 1 && edge.members[0] ? recordOf(edge.members[0]) : undefined;
      return {
      id: `${edge.from}->${edge.to}`,
      from: edge.from,
      to: edge.to,
      count: edge.count,
      direction: directionOf(edge.members),
      why: typeof single?.why === "string" ? single.why : null,
      how: typeof single?.how === "string" ? single.how : null,
      flowing:
        state.mode === "present" ||
        (view.selection !== null && (edge.from === view.selection || edge.to === view.selection)) ||
        unseen.has(edge.from) ||
        unseen.has(edge.to),
      dimmed: reach !== null && !(reach.has(edge.from) && reach.has(edge.to)),
      };
    })
    .sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));

  return { nodes, edges: renderEdges, top: reach !== null ? view.focus : null };
}

/**
 * The Element mode scene (UX section 3): the element, the elements it wants, and the elements that
 * want it. Wants held by or aimed at elements beneath it count as its own, as the graph does for a
 * collapsed element, so an element whose wants sit on its children is not shown alone.
 */
export function elementScene(state: ViewState, input: SceneInput, at: Address): RenderScene {
  const within = (address: Address) => address === at || isBeneath(address, at);
  const edges = [...input.graph.edges.filter(([h, w]) => !inLayerScope(h) && !inLayerScope(w))]
    .map(([h, w]): [Address, Address] => [within(h) ? at : h, within(w) ? at : w])
    .filter(([from, to]) => from !== to && (from === at || to === at));
  const addresses = [...new Set([at, ...edges.flat()])];
  const graph = { addresses, edges, definitive: input.graph.definitive };
  const flat: ViewState = {
    ...state,
    views:
      state.project === null
        ? state.views
        : { ...state.views, [state.project]: { ...currentView(state), container: TOP, focus: null, expanded: [] } },
  };
  const scene = buildScene(flat, { ...input, graph, fullAddresses: graphAddresses(input.graph) }, addresses);
  const wanters = edges.some(([, to]) => to === at);
  return { ...scene, top: wanters ? null : at };
}
