// The ELK renderer: lays out a RenderScene with ELK and draws it as SVG (renderer.ts rules 1–4).
// It reads no GraphSource and decides no meaning; it reports raw input to the state layer.

import type { Address } from "../source/types";
import { graph as text, intake, legend } from "../strings";
import { Camera } from "./camera";
import { around, branchOf, clearPart, fitViewport, joinedTo, NO_INSETS } from "./fit";
import { Flow } from "./flow";
import { Glide, type GlideItem } from "./glide";
import { aspectBucket, type Box, type Elk, FIT_MARGIN, type Layout, layout, layoutKey, nodeWidth, type Pane, type Point, headerWidth } from "./layout";
import { drawDetail } from "./details";
import { drawNode } from "./node";
import { midpoint, offset, pathFor } from "./paths";
import { depth as depthText } from "./strings";
import { el, tip } from "./svg";
import {
  type GraphRenderer,
  type Insets,
  MAX_FIT_ZOOM,
  MAX_ZOOM,
  MIN_ZOOM,
  type RenderEdge,
  type RendererEvents,
  type RenderScene,
  type Viewport,
} from "./renderer";
import { GRAPH_CSS } from "./style";

/** A fit of a selection or a branch never magnifies past this zoom. */
const PART_FIT_ZOOM = 1.25;
/** How long after the last wheel or drag a viewport change counts as settled. */
const SETTLE_MS = 150;

function clampZoom(zoom: number): number {
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom));
}

function isMac(): boolean {
  return typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
}

export class ElkRenderer implements GraphRenderer {
  private host: HTMLElement | null = null;
  private events: RendererEvents | null = null;
  private svg: SVGSVGElement | null = null;
  private canvas: SVGGElement | null = null;
  /** The viewport last asked for: the target of a running camera move, or where it rests. */
  private viewport: Viewport = { x: 0, y: 0, zoom: 1 };
  /** What is on screen now; moves ease from here (camera.ts). */
  private readonly camera = new Camera((shown) => this.paintViewport(shown));
  private current: Layout | null = null;
  private scene: RenderScene | null = null;
  private pending: Promise<void> = Promise.resolve();
  private generation = 0;
  private settleTimer: ReturnType<typeof setTimeout> | undefined;
  private drag: { pointer: number; x: number; y: number; moved: boolean } | null = null;
  private readonly cleanup: (() => void)[] = [];
  private readonly flow = new Flow();
  private readonly glide = new Glide();
  /** Whether the layout being drawn gives its routes as splines. */
  private curved = false;
  /** Whether the scene being drawn is the functional graph. */
  private functional = false;
  /** Wants with a why or a how to show while the pointer is on them, collected while edges are drawn. */
  private details: { edge: RenderEdge; at: Point }[] = [];
  /** What covers the pane; every fit stays clear of it. */
  private insets: Insets = NO_INSETS;
  private resizeObserver: ResizeObserver | null = null;
  /** The scene the last call of `render` asked for. `scene` is the one drawn. */
  private asked: RenderScene | null = null;
  /** The shape of the pane that call laid out for, or null when the pane had no size. */
  private askedAspect: ReturnType<typeof aspectBucket> | null = null;

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
    this.camera.moveTo(this.viewport, false);
    this.listen();
    if (typeof ResizeObserver === "function") {
      this.resizeObserver = new ResizeObserver(() => this.paneChanged());
      this.resizeObserver.observe(host);
    }
  }

  unmount(): void {
    this.generation++;
    this.flow.clear();
    this.glide.stop();
    for (const off of this.cleanup.splice(0)) off();
    clearTimeout(this.settleTimer);
    this.camera.stop();
    this.resizeObserver?.disconnect();
    this.resizeObserver = null;
    this.svg?.remove();
    this.svg = this.canvas = this.host = null;
    this.events = null;
    this.current = this.scene = this.asked = null;
  }

  render(scene: RenderScene): Promise<void> {
    const generation = ++this.generation;
    this.asked = scene;
    const widths = this.widths(scene);
    const pane = this.pane();
    this.askedAspect = pane ? aspectBucket(pane) : null;
    if (this.current?.key === layoutKey(scene, widths) && (pane === undefined || this.current.aspect === aspectBucket(pane))) {
      // Only flags changed: redraw in place, never lay out again (rule 1).
      const known = this.current;
      this.scene = scene;
      this.draw(scene, known);
      return this.pending;
    }
    const headers = new Map(scene.nodes.map((n) => [n.address, headerWidth(n, text.wantsOutside)]));
    this.pending = layout(this.elk(), scene, widths, headers, pane).then((next) => {
      if (generation !== this.generation || !this.canvas) return; // superseded
      this.current = next;
      this.scene = scene;
      this.draw(scene, next);
    });
    return this.pending;
  }

  setViewport(viewport: Viewport, animate: boolean): void {
    this.viewport = { ...viewport, zoom: clampZoom(viewport.zoom) };
    this.camera.moveTo(this.viewport, animate);
  }

  setInsets(insets: Partial<Insets>): void {
    const next = { ...NO_INSETS, ...insets };
    if (next.left === this.insets.left && next.right === this.insets.right && next.top === this.insets.top && next.bottom === this.insets.bottom) return;
    this.insets = next;
    this.paneChanged();
  }

  /** Fit graph. It may magnify a small graph up to MAX_FIT_ZOOM, so a first view uses the pane. */
  async fit(animate: boolean): Promise<Viewport> {
    await this.pending;
    const bounds = this.current?.bounds;
    if (!bounds || bounds.width === 0 || bounds.height === 0) return { ...this.viewport };
    return this.fitTo(bounds, animate, FIT_MARGIN, MAX_FIT_ZOOM);
  }

  async fitSelection(animate: boolean, address?: Address): Promise<Viewport> {
    await this.pending;
    const at = address ?? this.scene?.nodes.find((n) => n.selected)?.address;
    if (at === undefined || !this.scene || !this.current?.boxes.has(at)) return { ...this.viewport };
    return this.frame(joinedTo(this.scene, at), animate);
  }

  async fitBranch(animate: boolean, address?: Address): Promise<Viewport> {
    await this.pending;
    const at = address ?? this.scene?.nodes.find((n) => n.selected)?.address;
    if (at === undefined || !this.scene || !this.current?.boxes.has(at)) return { ...this.viewport };
    return this.frame(branchOf(this.scene, at), animate);
  }

  async fitScope(animate: boolean): Promise<Viewport> {
    await this.pending;
    const scope = this.scene?.scope;
    if (scope === undefined || scope.length === 0) return this.fit(animate);
    return this.frame(scope, animate, MAX_FIT_ZOOM);
  }

  /**
   * Frames the given elements, after any pending layout: the camera eases to show all of them
   * with room around, and never magnifies past `maxZoom`. With no address it frames everything.
   */
  async frame(addresses: readonly Address[], animate: boolean, maxZoom = PART_FIT_ZOOM): Promise<Viewport> {
    await this.pending;
    const target = around(addresses.map((a) => this.current?.boxes.get(a)).filter((b): b is Box => b !== undefined));
    if (!target) return this.fit(animate);
    return this.fitTo(target, animate, FIT_MARGIN * 1.6, maxZoom);
  }

  /** Eases the camera to show `target` in the clear part of the pane. */
  private fitTo(target: Box, animate: boolean, margin: number, maxZoom: number): Viewport {
    const size = this.host?.getBoundingClientRect();
    if (!size || size.width === 0 || size.height === 0) return { ...this.viewport };
    const clear = clearPart(size, this.insets);
    this.viewport = fitViewport(target, clear, margin, maxZoom);
    this.camera.fitTo(this.viewport, { x: clear.x + clear.width / 2, y: clear.y + clear.height / 2 }, animate);
    return { ...this.viewport };
  }

  private widths(scene: RenderScene): Map<Address, number> {
    const beneath = scene.functional === true ? depthText.hiddenBadge : text.beneathBadge;
    // An open element of the functional graph shows no count, so it needs no room for one.
    const none = () => "";
    return new Map(scene.nodes.map((n) => [n.address, nodeWidth(n, scene.functional === true && !n.collapsed ? none : beneath, text.wantsOutside)]));
  }

  /** The clear part of the pane, which the layout is chosen for; undefined before the pane has a size. */
  private pane(): Pane | undefined {
    const size = this.host?.getBoundingClientRect();
    if (!size || size.width === 0 || size.height === 0) return undefined;
    const clear = clearPart(size, this.insets);
    return { width: clear.width, height: clear.height };
  }

  /**
   * The pane or its insets changed. When its shape moved to another step, the scene is laid out
   * for the new shape. If the layout then runs in another direction, the old viewport no longer
   * shows the graph, so the scope is fitted and the viewport reported (rule 2).
   */
  private paneChanged(): void {
    const pane = this.pane();
    // The scene asked for last, which may still be in layout. Laying out the scene drawn last
    // would supersede it and leave an old scene on screen.
    const scene = this.asked;
    const before = this.current;
    // A layout for this scene and this shape of pane may be in progress already; it is not started again.
    if (!pane || !scene || !before || this.askedAspect === aspectBucket(pane)) return;
    void this.render(scene).then(() => {
      const now = this.current;
      if (!now || now === before || this.asked !== scene) return;
      if (now.direction === before.direction && now.wrapped === before.wrapped) return;
      void this.fitScope(true).then((viewport) => this.events?.viewportChange(viewport));
    });
  }

  /** The addresses whose box lies wholly outside the viewport on screen now, mid-move included. */
  outsideView(addresses: readonly Address[]): Address[] {
    const size = this.host?.getBoundingClientRect();
    const boxes = this.current?.boxes;
    if (!size || !boxes) return [];
    const { x, y, zoom } = this.camera.current;
    return addresses.filter((address) => {
      const box = boxes.get(address);
      if (!box) return false;
      const left = box.x * zoom + x;
      const top = box.y * zoom + y;
      return left + box.width * zoom <= 0 || top + box.height * zoom <= 0 || left >= size.width || top >= size.height;
    });
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

  private draw(scene: RenderScene, next: Layout): void {
    const canvas = this.canvas;
    if (!canvas) return;
    const focused = (document.activeElement as Element | null)?.getAttribute?.("data-address") ?? null;
    canvas.replaceChildren();
    const bands = el("g", { class: "mf-bands" }, canvas);
    for (const separator of next.separators) {
      const line = el("line", {
        class: "mf-separator", x1: separator.x, x2: separator.x,
        y1: -24, y2: next.bounds.height + 24,
      }, bands);
      tip(line, legend.band);
      const label = el("text", { class: "mf-band-label", x: separator.x + (separator.band === "upstream" ? -8 : 8), y: -32 }, bands);
      label.setAttribute("text-anchor", separator.band === "upstream" ? "end" : "start");
      label.textContent = separator.band === "upstream" ? text.upstreamBand : text.downstreamBand;
    }
    // Containers first, then edges, then leaf nodes, so arrows run above container fills.
    const containers = el("g", { class: "mf-containers" }, canvas);
    const leaving = el("g", { class: "mf-leaving", "aria-hidden": "true" }, canvas);
    const edges = el("g", { class: "mf-edges" }, canvas);
    const flowLayer = el("g", { class: "mf-flows", "aria-hidden": "true" }, canvas);
    this.flow.setLayer(flowLayer);
    const nodes = el("g", { class: "mf-nodes" }, canvas);
    const parents = new Set(scene.nodes.flatMap((n) => (n.parent === null ? [] : [n.parent])));
    this.curved = next.curved === true;
    this.functional = scene.functional === true;
    this.svg?.classList.toggle("mf-focused", scene.nodes.some((n) => n.selected));
    const glides: GlideItem[] = [];
    for (const node of scene.nodes) {
      const box = next.boxes.get(node.address);
      if (!box) continue;
      const group = drawNode(node, box, parents.has(node.address), parents.has(node.address) ? containers : nodes, this.functional, (address) => this.events?.chevronClick(address));
      // A new element grows from an element that relies on it, or else from one it relies on.
      const origins = [
        ...scene.edges.filter((e) => e.to === node.address).map((e) => e.from),
        ...scene.edges.filter((e) => e.from === node.address).map((e) => e.to),
      ];
      glides.push({ address: node.address, group, to: { x: box.x, y: box.y }, width: box.width, height: box.height, origins });
    }
    const ids = new Set(scene.edges.map((e) => e.id));
    this.details = [];
    for (const edge of scene.edges) {
      const route = next.routes.get(edge.id);
      if (!route) continue;
      // Two wants in opposite directions would share one line: move each 4 px to its own side.
      const paired = ids.has(`${edge.to}->${edge.from}`);
      this.drawEdge(edge, paired ? offset(route, 4) : route, edges, scene);
    }
    const details = el("g", { class: "mf-details" }, canvas);
    this.placeDetails(scene, details);
    // Elements glide from where they are drawn now; wants, flow and detail fade in after.
    this.glide.run(glides, [edges, flowLayer, details], leaving);
    if (focused) {
      const again = this.canvas?.querySelector<SVGGElement>(`[data-address="${CSS.escape(focused)}"]`);
      if (again && typeof again.focus === "function") again.focus({ preventScroll: true });
    }
  }

  private drawEdge(edge: RenderEdge, route: Point[], parent: SVGGElement, scene: RenderScene): void {
    // The base fades with its elements (climb step 9; viewer plan): a want between two dimmed
    // elements is dimmed, and a want with one dimmed end is half faded, so a layer's elements
    // keep their context while the rest of the skeleton recedes.
    const dimmedEnds = [edge.from, edge.to].filter((a) => scene.nodes.find((n) => n.address === a)?.dimmed).length;
    const fade = edge.dimmed || dimmedEnds === 2 ? " mf-dimmed" : dimmedEnds === 1 ? " mf-half" : "";
    const g = el("g", { class: `mf-edge${fade}`, "data-edge": edge.id }, parent);
    const direction = edge.direction;
    // An arrowhead is where the substance of the want arrives (R-3.6). A route runs from the
    // holder to the provider, so an inbound want has its head at the start, an outbound want at
    // the end, and a two-way want at both. A line with no recorded direction has no head.
    const heads: Record<string, string> = {};
    if (direction === "inbound" || direction === "two-way" || direction === "mixed") heads["marker-start"] = "url(#mf-arrow)";
    if (direction === "outbound" || direction === "two-way" || direction === "mixed") heads["marker-end"] = "url(#mf-arrow)";
    const path = el("path", { d: pathFor(route, this.curved), ...heads }, g);
    // A wide, unseen line over the want makes it easy to point at. While the pointer is on it,
    // the want is lit and its why and how are shown.
    el("path", { d: pathFor(route, this.curved), class: "mf-edge-hit" }, g);
    const plate = () => this.svg?.querySelector(`.mf-want-detail[data-edge="${CSS.escape(edge.id)}"]`);
    g.addEventListener("pointerenter", () => {
      g.classList.add("mf-lit");
      plate()?.classList.add("mf-show");
    });
    g.addEventListener("pointerleave", () => {
      g.classList.remove("mf-lit");
      plate()?.classList.remove("mf-show");
    });
    if (direction === "outbound" || direction === "inbound" || direction === "two-way") {
      const label = (address: Address) => scene.nodes.find((n) => n.address === address)?.label ?? address;
      tip(g, intake.ifdLine(direction, label(edge.from), label(edge.to)));
      // UX section 12a: the flow runs where it helps; the scene marks those wants `flowing`.
      if (!fade.includes("mf-dimmed") && edge.flowing) {
        const provider = scene.nodes.find((n) => n.address === edge.to);
        this.flow.add(edge.id, path, direction, edge.from, edge.to, (provider?.role ?? "none").toLowerCase());
      }
    } else {
      tip(g, legend.arrow);
    }
    if (edge.why || edge.how) this.details.push({ edge, at: midpoint(route) });
    if (edge.count > 1) {
      const mid = midpoint(route);
      const label = el("text", { class: "mf-edge-count", x: mid.x + 6, y: mid.y - 4 }, g);
      label.textContent = text.wantsOnArrow(edge.count);
      tip(label, legend.arrowCount);
    }
  }

  /**
   * Places the plate of every want, with its why and how, hidden. A plate appears only while the pointer is on
   * its want's line. The page never puts this text on the graph by itself: it would cover the lines.
   */
  private placeDetails(scene: RenderScene, parent: SVGGElement): void {
    const selected = new Set(scene.nodes.filter((n) => n.selected).map((n) => n.address));
    const order = [...this.details].sort(
      (a, b) => Number(selected.has(b.edge.from) || selected.has(b.edge.to)) - Number(selected.has(a.edge.from) || selected.has(a.edge.to)),
    );
    for (const { edge, at } of order) {
      drawDetail(parent, at, edge.why, edge.how).setAttribute("data-edge", edge.id);
    }
  }

  // Viewport and input ------------------------------------------------------------------------

  /** Paints one camera frame. No CSS transition: the camera does the easing (camera.ts). */
  private paintViewport(shown: Viewport): void {
    if (!this.canvas) return;
    this.canvas.style.transition = "";
    this.canvas.style.transform = `translate(${shown.x}px, ${shown.y}px) scale(${shown.zoom})`;
    // A want's plate keeps its size on screen: it is scaled by the inverse of the zoom.
    this.svg?.style.setProperty("--mf-unzoom", String(1 / Math.max(shown.zoom, 0.05)));
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
      // From what is on screen now, so a turn during a camera move continues it, not its target.
      const { x, y, zoom } = this.camera.current;
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
      const shown = this.camera.current;
      this.setViewport({ ...shown, x: shown.x + dx, y: shown.y + dy }, false);
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
