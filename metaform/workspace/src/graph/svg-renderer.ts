// The ELK renderer: lays out a RenderScene with ELK and draws it as SVG (renderer.ts rules 1–4).
// It reads no GraphSource and decides no meaning; it reports raw input to the state layer.

import type { Address } from "../source/types";
import { graph as text } from "../strings";
import { type Box, type Elk, HEADER, type Layout, layout, layoutKey, type Point } from "./layout";
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

function pathFor(points: Point[]): string {
  const [first, ...rest] = points;
  if (!first) return "";
  if (points.length === 2 && rest[0]) {
    // A want between bands: a horizontal S-curve.
    const end = rest[0];
    const mid = (first.x + end.x) / 2;
    return `M${first.x},${first.y} C${mid},${first.y} ${mid},${end.y} ${end.x},${end.y}`;
  }
  return `M${first.x},${first.y} ${rest.map((p) => `L${p.x},${p.y}`).join(" ")}`;
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
    const key = layoutKey(scene);
    if (this.current?.key === key) {
      // Only marks or flags changed: redraw in place, never lay out again (rule 1).
      const known = this.current;
      this.scene = scene;
      this.draw(scene, known, null);
      return this.pending;
    }
    const previous = this.current;
    this.pending = layout(this.elk(), scene).then((next) => {
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
    const zoom = clampZoom(Math.min(
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
    node.focus({ preventScroll: true });
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
    for (const edge of scene.edges) {
      const route = next.routes.get(edge.id);
      if (route) this.drawEdge(edge, route, edges, animate);
    }
    if (focused) {
      this.canvas?.querySelector<SVGGElement>(`[data-address="${CSS.escape(focused)}"]`)?.focus({ preventScroll: true });
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
    const labelY = container ? HEADER / 2 + 5 : box.height / 2 + 5;
    const label = el("text", { class: "mf-label", x: 14, y: labelY }, g);
    label.textContent = node.label;
    let right = box.width - 10;
    if (node.beneath > 0) {
      const chevron = el("g", {
        class: "mf-chevron", role: "button", tabindex: -1,
        "aria-label": text.beneathLabel(node.beneath, node.address),
        "aria-expanded": String(!node.collapsed),
        transform: `translate(${right - 12},${labelY - 10})`,
      }, g);
      el("rect", { width: 14, height: 14, rx: 3, class: "mf-chevron-hit" }, chevron);
      el("path", { d: node.collapsed ? "M5,3 L10,7 L5,11" : "M3,5 L7,10 L11,5", class: "mf-chevron-mark" }, chevron);
      chevron.addEventListener("click", (event) => {
        event.stopPropagation();
        this.events?.chevronClick(node.address);
      });
      right -= 20;
      const badge = el("text", { class: "mf-beneath", x: right, y: labelY, "text-anchor": "end", "aria-hidden": "true" }, g);
      badge.textContent = text.beneathBadge(node.beneath);
    }
    // Layer marks, agents, outside count and project link along the bottom edge.
    let x = 14;
    const markY = container ? HEADER - 6 : box.height - 9;
    for (const mark of node.layers) {
      const shape = SHAPES[mark.style % SHAPES.length] ?? "square";
      const m = el("g", { class: `mf-layer mf-layer-${mark.style % 8}`, transform: `translate(${x},${markY})` }, g);
      el("title", {}, m).textContent = `${mark.layer}: ${mark.records}`;
      if (shape === "circle") el("circle", { cx: 3, cy: 0, r: 3.5 }, m);
      else if (shape === "diamond") el("path", { d: "M3,-4 L7,0 L3,4 L-1,0 z" }, m);
      else if (shape === "triangle") el("path", { d: "M3,-4 L7,3 L-1,3 z" }, m);
      else el("rect", { x: 0, y: -3.5, width: 7, height: 7 }, m);
      const count = el("text", { class: "mf-layer-count", x: 10, y: 3.5 }, m);
      count.textContent = String(mark.records);
      x += 18 + String(mark.records).length * 6;
    }
    if (node.outside > 0) {
      const out = el("text", { class: "mf-outside", x: box.width - 10, y: markY + 3.5, "text-anchor": "end" }, g);
      out.textContent = text.wantsOnArrow(node.outside);
    }
    node.agents.forEach((agent, i) => {
      const a = el("g", { class: `mf-agent${agent.active ? " mf-agent-active" : ""}`, transform: `translate(${box.width - 8 - i * 20},-6)` }, g);
      el("circle", { r: 9 }, a);
      const initials = el("text", { "text-anchor": "middle", y: 3.5 }, a);
      initials.textContent = agent.initials;
    });
    if (node.unseen) el("circle", { class: "mf-unseen", cx: -3, cy: -3, r: 4 }, g);
    if (node.opensProject) {
      const link = el("g", { class: "mf-project-link", transform: `translate(${box.width - 24},${box.height - 16})` }, g);
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
    on("click", (e) => {
      const node = this.nodeAt(e.target);
      const address = node?.getAttribute("data-address");
      if (!address) return;
      this.events?.nodeClick(address, { up: isMac() ? e.metaKey : e.ctrlKey, shift: e.shiftKey });
    });
    on("dblclick", (e) => {
      const address = this.nodeAt(e.target)?.getAttribute("data-address");
      if (address) this.events?.nodeDoubleClick(address);
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
