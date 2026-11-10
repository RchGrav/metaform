// Layout for the ELK renderer (dev/graph_workspace_graph.md, sections 1 and 3).
// Pure functions: a RenderScene in, positions out. The ELK instance is passed in, so the
// browser runs it in a Web Worker and tests run the bundled build in Node.
//
// Each band (upstream, project, downstream) is laid out on its own with ELK's layered
// algorithm, top to bottom, and the bands are placed side by side: upstream on the left,
// downstream on the right (UX section 7). ELK's partitions run along the layer direction, so
// they cannot place bands beside each other. Wants inside a band are routed by ELK, including
// wants into expanded elements (compound nodes, hierarchyHandling INCLUDE_CHILDREN). Wants
// between bands are drawn as curves by the renderer.

import type { Address } from "../source/types";
import type { Band, RenderEdge, RenderNode, RenderScene } from "./renderer";

/** The part of the elkjs API this module uses. */
export interface ElkGraph {
  id: string;
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  layoutOptions?: Record<string, string>;
  children?: ElkGraph[];
  edges?: ElkEdge[];
}

export interface ElkEdge {
  id: string;
  sources: string[];
  targets: string[];
  sections?: { startPoint: Point; endPoint: Point; bendPoints?: Point[] }[];
}

export interface Elk {
  layout(graph: ElkGraph): Promise<ElkGraph>;
}

export interface Point {
  x: number;
  y: number;
}

export interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Layout {
  /** The key of the scene this layout was made for (see layoutKey). */
  key: string;
  /** Absolute boxes, in canvas units, for every node. */
  boxes: Map<Address, Box>;
  /** Polyline points for every edge, absolute. */
  routes: Map<string, Point[]>;
  /** True when each route is a spline: its start, then control points in threes, as ELK gives them. */
  curved?: boolean;
  /** The dashed separators between bands, as x positions with the band to their left/right. */
  separators: { x: number; band: Band }[];
  bounds: Box;
}

export const NODE_HEIGHT = 56;
const PAD = 16;
const MIN_WIDTH = 132;
const MAX_WIDTH = 300;
/** Estimated advance of one character: bold 13 px labels, regular 11 px badges. */
const LABEL_CHAR = 7.8;
const SMALL_CHAR = 6.4;
/** Room above an expanded element's children for its own label. */
export const HEADER = 36;

/**
 * One layout for the whole view, top to bottom, by purpose. A want runs from the element that
 * holds it down to the element that provides, so the parties the project serves are at the top,
 * each element is beneath what it serves, and what the project relies on is at the bottom. The
 * three bands are partitions, in that order. Every want, including one that crosses a band or
 * enters an expanded element, is routed by ELK around the elements between its ends. (Until
 * 2026-11-09 each band was laid out alone and a want between bands was drawn straight across
 * whatever lay between.)
 */
const ROOT_OPTIONS: Record<string, string> = {
  "elk.algorithm": "layered",
  "elk.direction": "DOWN",
  "elk.hierarchyHandling": "INCLUDE_CHILDREN",
  "elk.edgeRouting": "SPLINES",
  "elk.partitioning.activate": "true",
  "elk.layered.spacing.nodeNodeBetweenLayers": "84",
  "elk.spacing.nodeNode": "28",
  "elk.spacing.edgeNode": "18",
  "elk.spacing.edgeEdge": "10",
  "elk.layered.spacing.edgeNodeBetweenLayers": "18",
  "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
  "elk.layered.nodePlacement.bk.fixedAlignment": "BALANCED",
  "elk.layered.thoroughness": "40",
  // Absolute coordinates for nested nodes and edges (checked with elkjs 0.12.1).
  "elk.json.shapeCoords": "ROOT",
  "elk.json.edgeCoords": "ROOT",
};
/** Top to bottom: who the project serves, the project, what the project relies on. */
const PARTITION: Record<Band, number> = { downstream: 0, project: 1, upstream: 2 };
const COMPOUND_OPTIONS: Record<string, string> = {
  "elk.padding": `[top=${HEADER},left=16,bottom=16,right=16]`,
};

/**
 * Width that an expanded element's header needs on its one row: the label, the wants that leave
 * it, and the chevron. The count of elements beneath is not drawn there, because the elements
 * themselves are in view.
 */
export function headerWidth(node: Pick<RenderNode, "label" | "outside">, outsideText: (n: number) => string): number {
  const outside = node.outside > 0 ? outsideText(node.outside).length * SMALL_CHAR + 16 : 0;
  return Math.round(node.label.length * LABEL_CHAR + outside + 28 + 2 * PAD + 4);
}

/** Width that fits the node's two rows: label and chevron; layer marks, wants and beneath count. */
export function nodeWidth(node: Pick<RenderNode, "label" | "beneath" | "layers" | "outside">, beneathText: (n: number) => string, outsideText: (n: number) => string): number {
  const top = node.label.length * LABEL_CHAR + (node.beneath > 0 ? 28 : 0);
  const marks = node.layers.reduce((sum, mark) => sum + 18 + String(mark.records).length * SMALL_CHAR, 0);
  const right = (node.beneath > 0 ? beneathText(node.beneath).length * SMALL_CHAR : 0) +
    (node.outside > 0 ? outsideText(node.outside).length * SMALL_CHAR + 12 : 0);
  const bottom = marks + (marks > 0 && right > 0 ? 16 : 0) + right;
  return Math.round(Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, Math.max(top, bottom) + 2 * PAD + 4)));
}

/**
 * What a layout depends on: node addresses, parents, widths, bands, edge ids and the top element.
 * Selection, focus, dimming and unseen flags are left out, so a scene that changes only those
 * keeps its layout (renderer rule 1). Widths are in the key because marks change them.
 */
export function layoutKey(scene: RenderScene, widths: ReadonlyMap<Address, number>): string {
  const nodes = scene.nodes.map((n) => `${n.address}|${n.parent ?? ""}|${n.band}|${widths.get(n.address) ?? 0}`);
  const edges = scene.edges.map((e) => e.id).sort();
  return JSON.stringify([nodes, edges, scene.top, scene.functional === true]);
}

/** The band of each node's outermost container, so a nested node lays out with its parent. */
function bandOf(node: RenderNode, byAddress: Map<Address, RenderNode>): Band {
  let current = node;
  while (current.parent !== null) {
    const parent = byAddress.get(current.parent);
    if (!parent) break;
    current = parent;
  }
  return current.band;
}

/** Builds the one ELK graph of a scene. Nodes keep the scene's order (sorted by address). */
export function toElk(scene: RenderScene, widths: ReadonlyMap<Address, number>, headers: ReadonlyMap<Address, number> = new Map()): ElkGraph {
  const byAddress = new Map(scene.nodes.map((n) => [n.address, n]));
  const hasChildren = new Set(scene.nodes.flatMap((n) => (n.parent === null ? [] : [n.parent])));
  const elkNodes = new Map<Address, ElkGraph>();
  const root: ElkGraph = { id: "view", layoutOptions: { ...ROOT_OPTIONS }, children: [], edges: [] };
  for (const node of scene.nodes) {
    const elkNode: ElkGraph = hasChildren.has(node.address)
      ? {
        id: node.address,
        // An expanded element is at least as wide as its header, so the header's parts never
        // overlap when the elements beneath are narrow.
        layoutOptions: {
          ...COMPOUND_OPTIONS,
          "elk.nodeSize.constraints": "MINIMUM_SIZE",
          "elk.nodeSize.options": "MINIMUM_SIZE_ACCOUNTS_FOR_PADDING",
          "elk.nodeSize.minimum": `(${headers.get(node.address) ?? MIN_WIDTH},0)`,
        },
        children: [],
      }
      : { id: node.address, width: widths.get(node.address) ?? MIN_WIDTH, height: NODE_HEIGHT };
    const parent = node.parent === null ? undefined : elkNodes.get(node.parent);
    if (!parent) {
      elkNode.layoutOptions = { ...elkNode.layoutOptions, "elk.partitioning.partition": String(PARTITION[bandOf(node, byAddress)]) };
    }
    if (node.address === scene.top) {
      elkNode.layoutOptions = { ...elkNode.layoutOptions, "elk.layered.layering.layerConstraint": "FIRST" };
    }
    elkNodes.set(node.address, elkNode);
    (parent ?? root).children?.push(elkNode);
  }
  for (const edge of scene.edges) {
    if (!byAddress.has(edge.from) || !byAddress.has(edge.to)) continue;
    root.edges?.push({ id: edge.id, sources: [edge.from], targets: [edge.to] });
  }
  wrapLooseChildren(scene, byAddress, root, widths);
  return root;
}

/** Width over height that a wrapped block of children aims for (climb step 3a). */
const WRAP_ASPECT = 1.6;

/**
 * Children of an expanded element that have no wants to their siblings would all fall into one
 * layer, one long row (8 for roundtable's upstream). They are chained into a grid with edges used
 * only for layout, `wrap:` ids, never drawn: child i points to child i + columns. Children joined
 * by wants keep ELK's own layering. Columns are chosen so the block is about WRAP_ASPECT wide.
 */
function wrapLooseChildren(
  scene: RenderScene,
  byAddress: Map<Address, RenderNode>,
  root: ElkGraph,
  widths: ReadonlyMap<Address, number>,
): void {
  const childOf = (address: Address, container: Address): Address | null => {
    let current = byAddress.get(address);
    while (current && current.parent !== null && current.parent !== container) current = byAddress.get(current.parent);
    return current && current.parent === container ? current.address : null;
  };
  const containers = new Set(scene.nodes.flatMap((n) => (n.parent === null ? [] : [n.parent])));
  for (const container of containers) {
    const members = scene.nodes.filter((n) => n.parent === container).map((n) => n.address);
    const joined = new Set<Address>();
    for (const edge of scene.edges) {
      const a = childOf(edge.from, container);
      const b = childOf(edge.to, container);
      if (a && b && a !== b) {
        joined.add(a);
        joined.add(b);
      }
    }
    const loose = members.filter((m) => !joined.has(m));
    if (loose.length < 4) continue;
    const width = loose.reduce((sum, m) => sum + (widths.get(m) ?? MIN_WIDTH), 0) / loose.length;
    // Columns c and rows r = k / c with c * (width + gap) ≈ WRAP_ASPECT * r * (height + gap).
    const cell = { w: width + 32, h: NODE_HEIGHT + 56 };
    const columns = Math.max(2, Math.round(Math.sqrt((WRAP_ASPECT * loose.length * cell.h) / cell.w)));
    for (let i = 0; i + columns < loose.length; i++) {
      root.edges?.push({ id: `wrap:${loose[i]}->${loose[i + columns]}`, sources: [loose[i]!], targets: [loose[i + columns]!] });
    }
  }
}

function collectBoxes(node: ElkGraph, dx: number, out: Map<Address, Box>): void {
  for (const child of node.children ?? []) {
    out.set(child.id, {
      x: (child.x ?? 0) + dx,
      y: child.y ?? 0,
      width: child.width ?? 0,
      height: child.height ?? 0,
    });
    collectBoxes(child, dx, out);
  }
}

/**
 * The points of every routed edge. A spline is its start, then control points in threes; an
 * edge that ELK routes in several sections is joined at the points the sections share.
 */
function collectRoutes(node: ElkGraph, out: Map<string, Point[]>): void {
  for (const edge of node.edges ?? []) {
    const points: Point[] = [];
    for (const section of edge.sections ?? []) {
      const part = [section.startPoint, ...(section.bendPoints ?? []), section.endPoint];
      const last = points[points.length - 1];
      const joined = last !== undefined && part[0] !== undefined && last.x === part[0].x && last.y === part[0].y;
      points.push(...(joined ? part.slice(1) : part).map((p) => ({ x: p.x, y: p.y })));
    }
    if (points.length >= 2) out.set(edge.id, points);
  }
  for (const child of node.children ?? []) collectRoutes(child, out);
}

/** Runs ELK once for the whole scene and reads the boxes and the routes. */
export async function layout(elk: Elk, scene: RenderScene, widths: ReadonlyMap<Address, number>, headers: ReadonlyMap<Address, number> = new Map()): Promise<Layout> {
  const key = layoutKey(scene, widths);
  const boxes = new Map<Address, Box>();
  const routes = new Map<string, Point[]>();
  if (scene.nodes.length === 0) return { key, boxes, routes, separators: [], curved: true, bounds: { x: 0, y: 0, width: 0, height: 0 } };
  const result = await elk.layout(toElk(scene, widths, headers));
  collectBoxes(result, 0, boxes);
  collectRoutes(result, routes);
  return { key, boxes, routes, separators: [], curved: true, bounds: { x: 0, y: 0, width: result.width ?? 0, height: result.height ?? 0 } };
}
