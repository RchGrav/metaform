// The boundary between the workspace's state and the graph drawing.
// Ida (metaform-14) owns this file; Jorge (metaform-50) owns every renderer behind it.
// Change it only by agreement between the two (dev/user_agent_interfaces-ux.md).
//
// The state layer decides everything about meaning: which elements are visible, which arrows
// stand for wants to collapsed elements, what is dimmed, selected or unseen. The renderer only
// lays out and draws a RenderScene, and reports raw input. It never reads a GraphSource.

import type { Address, Role } from "../source";

/** Where an element sits relative to the project boundary (UX section 7). */
export type Band = "project" | "upstream" | "downstream";

/** One layer mark on an element (UX section 8). `style` picks a colour and a shape, so marks work without colour vision. */
export interface LayerMark {
  layer: string;
  records: number;
  /** 0-based index into the renderer's layer palette; stable for one layer name. */
  style: number;
}

/** One agent shown at an element (UX section 9). Always simulated in this prototype. */
export interface AgentMark {
  id: string;
  initials: string;
  active: boolean;
}

export interface RenderNode {
  /** The element's full address; the node's identity across scenes. */
  address: Address;
  /** The last address segment (the terms sheet: a node's label is its last segment). */
  label: string;
  /** The expanded element that contains this node in the scene, or null at the container's top level. Lets a compound layout route wants into an expanded element in one pass. */
  parent: Address | null;
  role: Role | null;
  status: string | null;
  band: Band;
  /** How many elements are beneath it in the map; 0 for a leaf. Leafs show no chevron. */
  beneath: number;
  /** True when its elements beneath are hidden (drawn as a stack); false when expanded. Ignored when beneath is 0. */
  collapsed: boolean;
  definitive: boolean;
  selected: boolean;
  /** The pivot element (UX section 10). Must never look like the Definitive element. */
  focus: boolean;
  /** Drawn at reduced opacity (isolate, pivot distance); still laid out in place. */
  dimmed: boolean;
  /** New activity the user has not seen (UX section 9). */
  unseen: boolean;
  /** Wants that leave the current container, as a count on the node. */
  outside: number;
  /** True when the element names another project (UX section 7). */
  opensProject: boolean;
  layers: LayerMark[];
  agents: AgentMark[];
}

export interface RenderEdge {
  /** Stable identity: `${from}->${to}`. */
  id: string;
  /** The holder of the want, or its nearest visible ancestor. */
  from: Address;
  /** The wanted element, or its nearest visible ancestor. */
  to: Address;
  /** How many wants this arrow stands for; 1 for a single want, more when it reaches a collapsed element. */
  count: number;
  dimmed: boolean;
}

export interface RenderScene {
  /** Sorted by address, so the same scene always gives the same layout. A node's parent comes before it. */
  nodes: RenderNode[];
  edges: RenderEdge[];
  /** The element the layered layout puts at the top, or null for the default (UX sections 10 and 13, UI-U4). */
  top: Address | null;
}

/** Zoom 1 is 100%. x and y are the canvas translation in screen pixels. */
export interface Viewport {
  x: number;
  y: number;
  zoom: number;
}

export const MIN_ZOOM = 0.1;
export const MAX_ZOOM = 4;
/** Every renderer animation is at most this long; 0 under prefers-reduced-motion (UX section 4). */
export const MAX_ANIMATION_MS = 200;

export interface Modifiers {
  /** Ctrl on Linux and Windows, Cmd on macOS: "go up" (UX section 5). */
  up: boolean;
  shift: boolean;
}

/** Raw input the renderer reports. The state layer decides what each one means. */
export interface RendererEvents {
  nodeClick(address: Address, modifiers: Modifiers): void;
  nodeDoubleClick(address: Address): void;
  chevronClick(address: Address): void;
  backgroundClick(): void;
  /** Every pan or zoom the user makes, after it settles. */
  viewportChange(viewport: Viewport): void;
}

/**
 * Rules every renderer keeps:
 * 1. Layout runs only when the set of node addresses or edge ids changes. A scene that changes
 *    only marks, dimming, selection, focus flags or unseen flags redraws in place, so isolating a
 *    layer or receiving activity never moves an element (UX sections 8 and 9).
 * 2. The renderer never changes the viewport by itself, except when `setViewport` or `fit` is called.
 * 3. Every node is focusable and has an accessible name: "<label>, <role>, <beneath> beneath".
 * 4. Animations last at most MAX_ANIMATION_MS, and none under prefers-reduced-motion.
 */
export interface GraphRenderer {
  mount(host: HTMLElement, events: RendererEvents): void;
  /** Resolves once the scene is laid out and drawn; layout may run in a worker. A newer render supersedes an older one, which then resolves without drawing. */
  render(scene: RenderScene): Promise<void>;
  setViewport(viewport: Viewport, animate: boolean): void;
  /** Frames every node with a 48 px margin, after any pending layout, and resolves to the resulting viewport. */
  fit(animate: boolean): Promise<Viewport>;
  /** Moves keyboard focus to a node, without changing the viewport unless the node is off screen. */
  focusNode(address: Address): void;
  unmount(): void;
}
