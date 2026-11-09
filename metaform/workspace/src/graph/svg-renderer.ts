// The ELK renderer: lays out a RenderScene with ELK and draws it as SVG (renderer.ts rules 1–4).
// It reads no GraphSource and decides no meaning; it reports raw input to the state layer.

import type { Address } from "../source/types";
import { graph as text } from "../strings";
import { type Box, type Elk, HEADER, type Layout, layout, layoutKey, nodeWidth, type Point } from "./layout";
import {
  type GraphRenderer,
  MAX_ANIMATION_MS,
  MAX_ZOOM,
  MIN_ZOOM,
  type RenderEdge,
  type RenderNode,
  type RendererEvents,
  type RenderScene,
  type Viewport,
} from "./renderer";
import { GRAPH_CSS } from "./style";

const SVG = "http://www.w3.org/2000/svg";
const FIT_MARGIN = 48;
/** How long after the last wheel or drag a viewport change counts as settled. */
const SETTLE_MS = 150;
/** Layer mark shapes, by style index, so marks do not depend on colour alone. */
const SHAPES = ["square", "circle", "diamond", "triangle"] as const;

function el<K extends keyof SVGElementTagNameMap>(
  name: K,
  attrs: Record<string, string | number> = {},
  parent?: Element,
): SVGElementTagNameMap[K] {
  const node = document.createElementNS(SVG, name);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
  parent?.appendChild(node);
  return node;
}

function clampZoom(zoom: number): number {
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom));
}

function reducedMotion(): boolean {
  return typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function isMac(): boolean {
  return typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
}

/** "<label>, <role>, <beneath> beneath" (renderer rule 3). */
function accessibleName(node: RenderNode): string {
  const parts = [node.label];
  if (node.role) parts.push(node.role);
  if (node.beneath > 0) parts.push(text.beneathBadge(node.beneath));
  return parts.join(", ");
}

/** Corner radius of a routed edge's bends. */
const CORNER = 8;

/**
 * The SVG path for a route. ELK routes edges orthogonally, so a route with bend points is drawn
 * as straight segments with rounded corners. A two-point route between bands is an S-curve.
 */
function pathFor(points: Point[]): string {
  const [first, second] = points;
  if (!first || !second) return "";
  if (points.length === 2) {
    if (first.x === second.x || first.y === second.y) return `M${first.x},${first.y} L${second.x},${second.y}`;
    if (Math.abs(second.x - first.x) > Math.abs(second.y - first.y)) {
      const mid = (first.x + second.x) / 2;
      return `M${first.x},${first.y} C${mid},${first.y} ${mid},${second.y} ${second.x},${second.y}`;
    }
    const mid = (first.y + second.y) / 2;
    return `M${first.x},${first.y} C${first.x},${mid} ${second.x},${mid} ${second.x},${second.y}`;
  }
  let d = `M${first.x},${first.y}`;
  for (let i = 1; i < points.length - 1; i++) {
    const prev = points[i - 1]!;
    const at = points[i]!;
    const next = points[i + 1]!;
    const into = Math.hypot(at.x - prev.x, at.y - prev.y);
    const out = Math.hypot(next.x - at.x, next.y - at.y);
    const r = Math.min(CORNER, into / 2, out / 2);
    const a = { x: at.x - ((at.x - prev.x) / (into || 1)) * r, y: at.y - ((at.y - prev.y) / (into || 1)) * r };
    const b = { x: at.x + ((next.x - at.x) / (out || 1)) * r, y: at.y + ((next.y - at.y) / (out || 1)) * r };
    d += ` L${a.x},${a.y} Q${at.x},${at.y} ${b.x},${b.y}`;
  }
  const last = points[points.length - 1]!;
  return `${d} L${last.x},${last.y}`;
}

/** The route moved sideways by `d`, to the right of its direction of travel. */
function offset(points: Point[], d: number): Point[] {
  const first = points[0];
  const last = points[points.length - 1];
  if (!first || !last) return points;
  const length = Math.hypot(last.x - first.x, last.y - first.y) || 1;
  const nx = (-(last.y - first.y) / length) * d;
  const ny = ((last.x - first.x) / length) * d;
  return points.map((p) => ({ x: p.x + nx, y: p.y + ny }));
}

function midpoint(points: Point[]): Point {
  const a = points[Math.floor((points.length - 1) / 2)] ?? { x: 0, y: 0 };
  const b = points[Math.ceil((points.length - 1) / 2)] ?? a;
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}

export class ElkRenderer implements GraphRenderer {
  private host: HTMLElement | null = null;
  private events: RendererEvents | null = null;
  private svg: SVGSVGElement | null = null;
  private canvas: SVGGElement | null = null;
  private viewport: Viewport = { x: 0, y: 0, zoom: 1 };
  private current: Layout | null = null;
  private scene: RenderScene | null = null;
  private pending: Promise<void> = Promise.resolve();
  private generation = 0;
  private settleTimer: ReturnType<typeof setTimeout> | undefined;
  private drag: { pointer: number; x: number; y: number; moved: boolean } | null = null;
  private readonly cleanup: (() => void)[] = [];

  constructor(private readonly elk: () => Elk) {}


  mount(host: HTMLElement, events: RendererEvents): void {
    this.host = host;
    this.events = events;
    const svg = el("svg", { class: "mf-graph", width: "100%", height: "100%", role: "group" });
    const style = el("style", {}, svg);
    style.textContent = GRAPH_CSS;
    const defs = el("defs", {}, svg);
    const marker = el("marker", {
      id: "mf-arrow", viewBox: "0 0 10 10", refX: 9, refY: 5,
      markerWidth: 8, markerHeight: 8, orient: "auto-start-reverse",
    }, defs);
    el("path", { d: "M0,0 L10,5 L0,10 z", class: "mf-arrowhead" }, marker);
    el("rect", { class: "mf-background", width: "100%", height: "100%" }, svg);
    this.canvas = el("g", { class: "mf-canvas" }, svg);
    host.appendChild(svg);
    this.svg = svg;
    this.applyViewport(false);
    this.listen();
  }

  unmount(): void {
    this.generation++;
    for (const off of this.cleanup.splice(0)) off();
    clearTimeout(this.settleTimer);
    this.svg?.remove();
    this.svg = this.canvas = this.host = null;
    this.events = null;
    this.current = this.scene = null;
  }

  render(scene: RenderScene): Promise<void> {
    const generation = ++this.generation;
    const widths = new Map(scene.nodes.map((n) => [n.address, nodeWidth(n, text.beneathBadge, text.wantsOnArrow)]));
    if (this.current?.key === layoutKey(scene, widths)) {
      // Only flags changed: redraw in place, never lay out again (rule 1).
      const known = this.current;
      this.scene = scene;
      this.draw(scene, known, null);
      return this.pending;
    }
    const previous = this.current;
    this.pending = layout(this.elk(), scene, widths).then((next) => {
      if (generation !== this.generation || !this.canvas) return; // superseded
      this.current = next;
      this.scene = scene;
      this.draw(scene, next, previous);
    });
    return this.pending;
  }

  setViewport(viewport: Viewport, animate: boolean): void {
    this.viewport = { ...viewport, zoom: clampZoom(viewport.zoom) };
    this.applyViewport(animate);
  }

  async fit(animate: boolean): Promise<Viewport> {
    await this.pending;
    const bounds = this.current?.bounds;
    const size = this.host?.getBoundingClientRect();
    if (!bounds || !size || bounds.width === 0 || bounds.height === 0) return { ...this.viewport };
    // Fit frames the graph but never magnifies past 100%: a small graph stays at reading size.
    const zoom = clampZoom(Math.min(
      1,
      (size.width - 2 * FIT_MARGIN) / bounds.width,
      (size.height - 2 * FIT_MARGIN) / bounds.height,
    ));
    this.setViewport({
      x: (size.width - bounds.width * zoom) / 2 - bounds.x * zoom,
      y: (size.height - bounds.height * zoom) / 2 - bounds.y * zoom,
      zoom,
    }, animate);
    return { ...this.viewport };
  }

  focusNode(address: Address): void {
    const node = this.canvas?.querySelector<SVGGElement>(`[data-address="${CSS.escape(address)}"]`);
    const box = this.current?.boxes.get(address);
    const size = this.host?.getBoundingClientRect();
    if (!node || !box) return;
    if (size) {
      const { x, y, zoom } = this.viewport;
      const left = box.x * zoom + x;
      const top = box.y * zoom + y;
      const off = left < 0 || top < 0 || left + box.width * zoom > size.width || top + box.height * zoom > size.height;
      if (off) {
        this.setViewport({
          x: size.width / 2 - (box.x + box.width / 2) * zoom,
          y: size.height / 2 - (box.y + box.height / 2) * zoom,
          zoom,
        }, true);
        this.events?.viewportChange({ ...this.viewport });
      }
    }
    // Every current browser has SVGElement.focus; an engine without it must not crash the app.
    if (typeof node.focus === "function") node.focus({ preventScroll: true });
  }

  // Drawing ------------------------------------------------------------------------------------

  private draw(scene: RenderScene, next: Layout, previous: Layout | null): void {
    const canvas = this.canvas;
    if (!canvas) return;
    const focused = (document.activeElement as Element | null)?.getAttribute?.("data-address") ?? null;
    canvas.replaceChildren();
    const bands = el("g", { class: "mf-bands" }, canvas);
    for (const separator of next.separators) {
      el("line", {
        class: "mf-separator", x1: separator.x, x2: separator.x,
        y1: -24, y2: next.bounds.height + 24,
      }, bands);
      const label = el("text", { class: "mf-band-label", x: separator.x + (separator.band === "upstream" ? -8 : 8), y: -32 }, bands);
      label.setAttribute("text-anchor", separator.band === "upstream" ? "end" : "start");
      label.textContent = separator.band === "upstream" ? text.upstreamBand : text.downstreamBand;
    }
    // Containers first, then edges, then leaf nodes, so arrows run above container fills.
    const containers = el("g", { class: "mf-containers" }, canvas);
    const edges = el("g", { class: "mf-edges" }, canvas);
    const nodes = el("g", { class: "mf-nodes" }, canvas);
    const parents = new Set(scene.nodes.flatMap((n) => (n.parent === null ? [] : [n.parent])));
    const animate = previous !== null && !reducedMotion();
    for (const node of scene.nodes) {
      const box = next.boxes.get(node.address);
      if (!box) continue;
      const group = this.drawNode(node, box, parents.has(node.address), parents.has(node.address) ? containers : nodes);
      const old = previous?.boxes.get(node.address);
      if (animate && old && (old.x !== box.x || old.y !== box.y)) {
        group.style.transform = `translate(${old.x - box.x}px, ${old.y - box.y}px)`;
        requestAnimationFrame(() => {
          group.style.transition = `transform ${MAX_ANIMATION_MS}ms ease-out`;
          group.style.transform = "";
        });
      }
    }
    const ids = new Set(scene.edges.map((e) => e.id));
    for (const edge of scene.edges) {
      const route = next.routes.get(edge.id);
      if (!route) continue;
      // Two wants in opposite directions would share one line: move each 4 px to its own side.
      const paired = ids.has(`${edge.to}->${edge.from}`);
      this.drawEdge(edge, paired ? offset(route, 4) : route, edges, animate);
    }
    if (focused) {
      const again = this.canvas?.querySelector<SVGGElement>(`[data-address="${CSS.escape(focused)}"]`);
      if (again && typeof again.focus === "function") again.focus({ preventScroll: true });
    }
  }

  private drawNode(node: RenderNode, box: Box, container: boolean, parent: SVGGElement): SVGGElement {
    const classes = ["mf-node", `mf-band-${node.band}`, `mf-role-${(node.role ?? "none").toLowerCase()}`];
    if (container) classes.push("mf-container");
    if (node.selected) classes.push("mf-selected");
    if (node.focus) classes.push("mf-focus");
    if (node.definitive) classes.push("mf-definitive");
    if (node.dimmed) classes.push("mf-dimmed");
    if (node.beneath > 0 && node.collapsed) classes.push("mf-collapsed");
    const g = el("g", {
      class: classes.join(" "), "data-address": node.address, tabindex: 0, role: "button",
      "aria-label": accessibleName(node), transform: `translate(${box.x},${box.y})`,
    }, parent);
    if (node.selected) g.setAttribute("aria-pressed", "true");
    if (node.beneath > 0 && node.collapsed && !container) {
      el("rect", { class: "mf-stack", x: 5, y: 5, width: box.width, height: box.height, rx: 6 }, g);
    }
    el("rect", { class: "mf-box", width: box.width, height: box.height, rx: 6 }, g);
    if (node.definitive) el("rect", { class: "mf-definitive-ring", x: 3, y: 3, width: box.width - 6, height: box.height - 6, rx: 4 }, g);
    el("rect", { class: "mf-role-bar", width: 4, height: container ? HEADER : box.height, rx: 2 }, g);
    // Row 1: the label, and the chevron at the right. Row 2: layer marks at the left; the wants
    // that leave the container and the count beneath at the right (nodeWidth sizes both rows).
    const row1 = container ? HEADER / 2 + 5 : 23;
    const row2 = container ? HEADER / 2 + 5 : 43;
    const label = el("text", { class: "mf-label", x: 16, y: row1 }, g);
    label.textContent = node.label;
    let right = box.width - 16;
    if (node.beneath > 0) {
      const chevron = el("g", {
        class: "mf-chevron", role: "button", tabindex: -1,
        "aria-label": text.beneathLabel(node.beneath, node.address),
        "aria-expanded": String(!node.collapsed),
        transform: `translate(${right - 12},${row1 - 11})`,
      }, g);
      el("rect", { width: 16, height: 16, rx: 3, class: "mf-chevron-hit" }, chevron);
      el("path", { d: node.collapsed ? "M6,4 L11,8 L6,12" : "M4,6 L8,11 L12,6", class: "mf-chevron-mark" }, chevron);
      chevron.addEventListener("click", (event) => {
        event.stopPropagation();
        this.events?.chevronClick(node.address);
      });
      if (container) right -= 24;
    }
    const counts: string[] = [];
    if (node.beneath > 0) counts.push(text.beneathBadge(node.beneath));
    if (node.outside > 0) counts.unshift(text.wantsOnArrow(node.outside));
    if (counts.length > 0) {
      const badge = el("text", { class: "mf-beneath", x: right + (container || node.beneath === 0 ? 0 : 4), y: row2, "text-anchor": "end", "aria-hidden": "true" }, g);
      badge.textContent = counts.join(" · ");
    }
    let x = container ? 16 + node.label.length * 7.8 + 12 : 16;
    for (const mark of node.layers) {
      const shape = SHAPES[mark.style % SHAPES.length] ?? "square";
      const m = el("g", { class: `mf-layer mf-layer-${mark.style % 8}`, transform: `translate(${x},${row2 - 4})` }, g);
      el("title", {}, m).textContent = `${mark.layer}: ${mark.records}`;
      if (shape === "circle") el("circle", { cx: 3.5, cy: 0, r: 4 }, m);
      else if (shape === "diamond") el("path", { d: "M3.5,-4.5 L8,0 L3.5,4.5 L-1,0 z" }, m);
      else if (shape === "triangle") el("path", { d: "M3.5,-4.5 L8,4 L-1,4 z" }, m);
      else el("rect", { x: 0, y: -3.5, width: 7, height: 7 }, m);
      const count = el("text", { class: "mf-layer-count", x: 11, y: 4 }, m);
      count.textContent = String(mark.records);
      x += 18 + String(mark.records).length * 6.4;
    }
    // Agents sit on the top border near the left corner: wants between bands attach at the
    // sides, and wants within a band attach spread along the middle of the top and bottom.
    node.agents.forEach((agent, i) => {
      const a = el("g", { class: `mf-agent${agent.active ? " mf-agent-active" : ""}`, transform: `translate(${22 + i * 20},0)` }, g);
      el("circle", { r: 9 }, a);
      const initials = el("text", { "text-anchor": "middle", y: 3.5 }, a);
      initials.textContent = agent.initials;
    });
    if (node.unseen) el("circle", { class: "mf-unseen", cx: 0, cy: 0, r: 4.5 }, g);
    if (node.opensProject) {
      const link = el("g", { class: "mf-project-link", transform: `translate(${16 + node.label.length * 7.8 + 6},${row1 - 10})` }, g);
      el("title", {}, link).textContent = text.opensAnotherProject;
      el("path", { d: "M2,10 L10,2 M5,2 L10,2 L10,7" }, link);
    }
    return g;
  }

  private drawEdge(edge: RenderEdge, route: Point[], parent: SVGGElement, animate: boolean): void {
    const g = el("g", { class: `mf-edge${edge.dimmed ? " mf-dimmed" : ""}`, "data-edge": edge.id }, parent);
    el("path", { d: pathFor(route), "marker-end": "url(#mf-arrow)" }, g);
    if (edge.count > 1) {
      const mid = midpoint(route);
      const label = el("text", { class: "mf-edge-count", x: mid.x + 6, y: mid.y - 4 }, g);
      label.textContent = text.wantsOnArrow(edge.count);
    }
    if (animate) {
      g.style.opacity = "0";
      setTimeout(() => {
        g.style.transition = `opacity ${MAX_ANIMATION_MS / 2}ms ease-out`;
        g.style.opacity = "";
      }, MAX_ANIMATION_MS / 2);
    }
  }

  // Viewport and input ------------------------------------------------------------------------

  private applyViewport(animate: boolean): void {
    if (!this.canvas) return;
    const { x, y, zoom } = this.viewport;
    this.canvas.style.transition = animate && !reducedMotion() ? `transform ${MAX_ANIMATION_MS}ms ease-out` : "";
    this.canvas.style.transform = `translate(${x}px, ${y}px) scale(${zoom})`;
  }

  private settled(): void {
    clearTimeout(this.settleTimer);
    this.settleTimer = setTimeout(() => this.events?.viewportChange({ ...this.viewport }), SETTLE_MS);
  }

  private nodeAt(target: EventTarget | null): SVGGElement | null {
    return target instanceof Element ? target.closest<SVGGElement>("[data-address]") : null;
  }

  private listen(): void {
    const svg = this.svg;
    if (!svg) return;
    const on = <K extends keyof SVGElementEventMap>(type: K, handler: (e: SVGElementEventMap[K]) => void, options?: AddEventListenerOptions) => {
      svg.addEventListener(type, handler as EventListener, options);
      this.cleanup.push(() => svg.removeEventListener(type, handler as EventListener, options));
    };
    on("wheel", (e) => {
      e.preventDefault();
      const rect = svg.getBoundingClientRect();
      const px = e.clientX - rect.left;
      const py = e.clientY - rect.top;
      const { x, y, zoom } = this.viewport;
      const next = clampZoom(zoom * Math.exp(-e.deltaY * (e.deltaMode === 1 ? 0.05 : 0.0015)));
      this.setViewport({ x: px - ((px - x) * next) / zoom, y: py - ((py - y) * next) / zoom, zoom: next }, false);
      this.settled();
    }, { passive: false });
    on("pointerdown", (e) => {
      if (e.button !== 0 || this.nodeAt(e.target)) return;
      this.drag = { pointer: e.pointerId, x: e.clientX, y: e.clientY, moved: false };
      svg.setPointerCapture(e.pointerId);
    });
    on("pointermove", (e) => {
      const drag = this.drag;
      if (!drag || drag.pointer !== e.pointerId) return;
      const dx = e.clientX - drag.x;
      const dy = e.clientY - drag.y;
      if (!drag.moved && Math.hypot(dx, dy) < 3) return;
      drag.moved = true;
      drag.x = e.clientX;
      drag.y = e.clientY;
      this.setViewport({ ...this.viewport, x: this.viewport.x + dx, y: this.viewport.y + dy }, false);
      svg.classList.add("mf-panning");
    });
    const endDrag = (e: PointerEvent) => {
      const drag = this.drag;
      if (!drag || drag.pointer !== e.pointerId) return;
      this.drag = null;
      svg.classList.remove("mf-panning");
      if (drag.moved) this.settled();
      else if (e.type === "pointerup") this.events?.backgroundClick();
    };
    on("pointerup", endDrag);
    on("pointercancel", endDrag);
    // A double-click is read from the click count, not from the dblclick event: the first click
    // selects, the redraw replaces the node's elements, and the browser then sends no dblclick
    // because the two clicks no longer share a target. The count survives the redraw.
    on("click", (e) => {
      const node = this.nodeAt(e.target);
      const address = node?.getAttribute("data-address");
      if (!address) return;
      if (e.detail === 2) this.events?.nodeDoubleClick(address);
      else if (e.detail <= 1) this.events?.nodeClick(address, { up: isMac() ? e.metaKey : e.ctrlKey, shift: e.shiftKey });
    });
    on("keydown", (e) => {
      const address = this.nodeAt(e.target)?.getAttribute("data-address");
      if (!address) return;
      // UX section 5: Enter opens like a double-click; Shift+Enter goes up like Ctrl-click.
      // UX section 6: Space toggles the chevron.
      if (e.key === "Enter") {
        e.preventDefault();
        if (e.shiftKey) this.events?.nodeClick(address, { up: true, shift: false });
        else this.events?.nodeDoubleClick(address);
      } else if (e.key === " ") {
        e.preventDefault();
        const node = this.scene?.nodes.find((n) => n.address === address);
        if (node && node.beneath > 0) this.events?.chevronClick(address);
      }
    });
  }
}
