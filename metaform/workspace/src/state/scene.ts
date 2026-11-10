// Builds the RenderScene from the view state and the server's reads. Every decision about
// meaning happens here, so the renderer only lays out and draws (src/graph/renderer.ts).

import type { Address, Role, ShallowGraph, SummarySheet } from "../source";
import type { AgentMark, RenderEdge, RenderNode, RenderScene } from "../graph/renderer";
import { hiddenCounts, initialDepth, levelsOf, visibleSet, type Levels } from "./depth";
import { FOCUS_REACH, categoryShown, currentView, layerShown, type ViewState } from "./view";
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

/** What the scene needs that the state does not hold: the project's reads and the agents the source reports (only the simulated source reports any). */
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
      // The project's own name for the element; an address that only groups shows its last segment.
      label: typeof fields.name === "string" && fields.name.trim() !== "" ? fields.name : lastSegment(address),
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

/**
 * Selection as focus. The selected element, the elements it wants and the elements that want it
 * stay clear, with their wants flowing; everything else is quiet. Only flags change, so nothing
 * moves. With no selection, nothing flows.
 */
export function focusOnSelection(scene: RenderScene, selected: Address | null): RenderScene {
  const near = new Set<Address>();
  if (selected !== null && scene.nodes.some((n) => n.address === selected)) {
    near.add(selected);
    for (const edge of scene.edges) {
      if (edge.from === selected) near.add(edge.to);
      if (edge.to === selected) near.add(edge.from);
    }
  }
  const focused = near.size > 0;
  // An expanded element stays clear while anything inside it is clear.
  const holds = (address: Address) => [...near].some((n) => n.startsWith(`${address}.`));
  const off = (edge: RenderEdge) => edge.dimmed || (focused && edge.from !== selected && edge.to !== selected);
  return {
    ...scene,
    nodes: scene.nodes.map((node) => ({ ...node, dimmed: node.dimmed || (focused && !near.has(node.address) && !holds(node.address)) })),
    // The lines of the selected element flow; with no selection the graph is still (the earlier
    // map's default: motion marks what the person is looking at).
    edges: scene.edges.map((edge) => ({ ...edge, dimmed: off(edge), flowing: focused && !off(edge) })),
  };
}

/** The categories in the order the page lists them: who the project serves, the project's own, what it relies on. */
const CATEGORY_ORDER = ["downstream", "code", "document", "data", "media", "upstream"];

/** An element's category: the first segment of its address (code, document, data, media, upstream, downstream). */
export function categoryOf(address: Address): string {
  const cut = address.indexOf(".");
  return cut < 0 ? address : address.slice(0, cut);
}

/** The categories that hold elements, with how many each holds; known categories first, in the page's order. */
export function categoriesOf(addresses: readonly Address[]): { category: string; elements: number }[] {
  const counts = new Map<string, number>();
  for (const address of addresses) counts.set(categoryOf(address), (counts.get(categoryOf(address)) ?? 0) + 1);
  const place = (category: string) => (CATEGORY_ORDER.includes(category) ? CATEGORY_ORDER.indexOf(category) : CATEGORY_ORDER.length);
  return [...counts]
    .map(([category, elements]) => ({ category, elements }))
    .sort((a, b) => place(a.category) - place(b.category) || (a.category < b.category ? -1 : 1));
}

/** The elements the functional graph can show: those in the container that carry a name or a role. */
export function functionalElements(state: ViewState, input: SceneInput): Address[] {
  const { container } = currentView(state);
  const inScope = (address: Address) => container === TOP || address === container || isBeneath(address, container);
  const isElement = (address: Address) => {
    const fields = input.fields.get(address);
    return fields !== undefined && ["technical_name", "name", "role"].some((key) => typeof fields[key] === "string");
  };
  return graphAddresses(input.graph).filter((address) => inScope(address) && isElement(address));
}

/** Levels already counted, by the reads they came from and the container, so a selection does not count them again. */
const levelCache = new WeakMap<object, WeakMap<object, Map<Address, Levels>>>();

/**
 * The levels of the functional graph in the current container (state/depth.ts). Every depth
 * action carries them. The same reads and container give the same object.
 */
export function functionalLevels(state: ViewState, input: SceneInput): Levels {
  const { container } = currentView(state);
  const byFields = levelCache.get(input.graph) ?? new WeakMap<object, Map<Address, Levels>>();
  levelCache.set(input.graph, byFields);
  const byContainer = byFields.get(input.fields) ?? new Map<Address, Levels>();
  byFields.set(input.fields, byContainer);
  const known = byContainer.get(container);
  if (known) return known;
  const elements = functionalElements(state, input);
  // A want held by an address that is not an element counts for the element above it, as the scene draws it.
  const { edges } = sceneEdges(input.graph, new Set(elements));
  const levels = levelsOf(elements, edges.map((edge) => [edge.from, edge.to] as const));
  byContainer.set(container, levels);
  return levels;
}

/**
 * The functional graph: the elements in the container, and the wants between them, with no
 * nesting. An address that only groups other addresses is not drawn; the namespace is in each
 * element's address, not in the picture. An element is labelled with the project's own name
 * for it.
 *
 * Depth decides which elements show (state/depth.ts). An element that holds hidden elements is
 * drawn collapsed, with their count; an element whose next level shows can be closed. A hidden
 * category's elements and their wants are left out. While a category is isolated, the other
 * categories are quiet and stay in place.
 *
 * When an element is selected, it, the elements it wants and the elements that want it stay
 * clear, and everything else recedes; only flags change, so nothing moves.
 */
export function functionalScene(state: ViewState, input: SceneInput): RenderScene {
  const view = currentView(state);
  const elements = functionalElements(state, input);
  const flat: ViewState = {
    ...state,
    views:
      state.project === null
        ? state.views
        : { ...state.views, [state.project]: { ...view, container: TOP, expanded: [] } },
  };
  const scene = buildScene(flat, { ...input, fullAddresses: graphAddresses(input.graph) }, elements);
  const levels = functionalLevels(state, input);
  const visible = visibleSet(levels, view.depth?.now ?? initialDepth());
  const shown = (address: Address) => categoryShown(state, categoryOf(address));
  const drawn = (address: Address) => visible.has(address) && shown(address);
  const hidden = hiddenCounts(levels, visible, shown);
  const quiet = (address: Address) => state.isolatedCategory !== null && categoryOf(address) !== state.isolatedCategory;
  const nodes = scene.nodes.filter((node) => drawn(node.address)).map((node) => {
    const held = hidden.get(node.address) ?? 0;
    // With nothing hidden, the count is the next level on screen, so the element can be closed.
    const open = (levels.children.get(node.address) ?? []).filter(drawn).length;
    return {
      ...node,
      beneath: held > 0 ? held : open,
      collapsed: held > 0,
      dimmed: node.dimmed || quiet(node.address),
      outside: view.container === TOP ? 0 : node.outside,
    };
  });
  const functional: RenderScene = {
    ...scene,
    functional: true,
    nodes,
    edges: scene.edges.filter((edge) => drawn(edge.from) && drawn(edge.to)),
  };
  if (state.isolatedCategory !== null) functional.scope = nodes.filter((node) => !quiet(node.address)).map((node) => node.address);
  return focusOnSelection(functional, view.selection);
}
