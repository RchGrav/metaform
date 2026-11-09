// A plain GraphRenderer, so the shell runs before Jorge's ELK renderer lands. It keeps every rule
// in renderer.ts, with a simple layered top-down layout: each element sits one row below the
// lowest element that wants it. Jorge's renderer replaces it; nothing else depends on it.

import * as strings from "../strings";
import {
  MAX_ANIMATION_MS,
  MAX_ZOOM,
  MIN_ZOOM,
  type GraphRenderer,
  type RenderNode,
  type RenderScene,
  type RendererEvents,
  type Viewport,
} from "./renderer";

const SVG = "http://www.w3.org/2000/svg";
const NODE_W = 168;
const NODE_H = 48;
const GAP_X = 40;
const GAP_Y = 72;
const FIT_MARGIN = 48;

interface Box {
  x: number;
  y: number;
}

function el<K extends keyof SVGElementTagNameMap>(name: K, attrs: Record<string, string | number> = {}): SVGElementTagNameMap[K] {
  const node = document.createElementNS(SVG, name);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
  return node;
}

function reducedMotion(): boolean {
  return typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Rows by want depth: an element sits one row below the deepest element that wants it. */
function layout(scene: RenderScene): Map<string, Box> {
  const row = new Map<string, number>(scene.nodes.map((n) => [n.address, 0]));
  if (scene.top !== null) row.set(scene.top, 0);
  // Longest path, bounded by the node count so cycles end.
  for (let pass = 0; pass < scene.nodes.length; pass += 1) {
    let changed = false;
    for (const edge of scene.edges) {
      if (edge.to === scene.top) continue;
      const next = (row.get(edge.from) ?? 0) + 1;
      if (next > (row.get(edge.to) ?? 0) && next <= scene.nodes.length) {
        row.set(edge.to, next);
        changed = true;
      }
    }
    if (!changed) break;
  }
  const bands: Record<RenderNode["band"], number> = { upstream: 0, project: 1, downstream: 2 };
  const columns = new Map<string, number>();
  const boxes = new Map<string, Box>();
  let bandOffset = 0;
  for (const band of ["upstream", "project", "downstream"] as const) {
    const members = scene.nodes.filter((n) => n.band === band);
    let widest = 0;
    for (const node of members) {
      const r = row.get(node.address) ?? 0;
      const key = `${bands[band]}:${r}`;
      const c = columns.get(key) ?? 0;
      columns.set(key, c + 1);
      widest = Math.max(widest, c + 1);
      boxes.set(node.address, { x: bandOffset + c * (NODE_W + GAP_X), y: r * (NODE_H + GAP_Y) });
    }
    if (members.length > 0) bandOffset += widest * (NODE_W + GAP_X) + GAP_X * 2;
  }
  return boxes;
}

export class FallbackRenderer implements GraphRenderer {
  private host: HTMLElement | null = null;
  private svg: SVGSVGElement | null = null;
  private world: SVGGElement | null = null;
  private events: RendererEvents | null = null;
  private boxes = new Map<string, Box>();
  private shape = "";
  private viewport: Viewport = { x: 48, y: 48, zoom: 1 };
  private drag: { x: number; y: number; moved: boolean } | null = null;
  private settle: ReturnType<typeof setTimeout> | null = null;

  mount(host: HTMLElement, events: RendererEvents): void {
    this.host = host;
    this.events = events;
    const svg = el("svg", { class: "graph", role: "group", "aria-roledescription": "graph" });
    const world = el("g");
    svg.append(world);
    host.append(svg);
    this.svg = svg;
    this.world = world;
    svg.addEventListener("pointerdown", (e) => {
      if ((e.target as Element).closest(".node")) return;
      this.drag = { x: e.clientX, y: e.clientY, moved: false };
      svg.setPointerCapture(e.pointerId);
    });
    svg.addEventListener("pointermove", (e) => {
      if (!this.drag) return;
      const dx = e.clientX - this.drag.x;
      const dy = e.clientY - this.drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 2) this.drag.moved = true;
      this.drag.x = e.clientX;
      this.drag.y = e.clientY;
      this.apply({ ...this.viewport, x: this.viewport.x + dx, y: this.viewport.y + dy }, false);
    });
    svg.addEventListener("pointerup", () => {
      if (this.drag && !this.drag.moved) this.events?.backgroundClick();
      this.drag = null;
    });
    svg.addEventListener(
      "wheel",
      (e) => {
        e.preventDefault();
        const rect = svg.getBoundingClientRect();
        const px = e.clientX - rect.left;
        const py = e.clientY - rect.top;
        const zoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, this.viewport.zoom * Math.exp(-e.deltaY * 0.0015)));
        const k = zoom / this.viewport.zoom;
        this.apply({ zoom, x: px - (px - this.viewport.x) * k, y: py - (py - this.viewport.y) * k }, false);
      },
      { passive: false },
    );
  }

  async render(scene: RenderScene): Promise<void> {
    const world = this.world;
    if (!world) return;
    const shape = `${scene.top ?? ""}|${scene.nodes.map((n) => n.address).join(",")}|${scene.edges.map((e) => e.id).join(",")}`;
    if (shape !== this.shape) {
      // Rule 1: lay out only when the node or edge set changes.
      this.boxes = layout(scene);
      this.shape = shape;
    }
    world.replaceChildren();
    const edges = el("g", { class: "edges" });
    for (const edge of scene.edges) {
      const a = this.boxes.get(edge.from);
      const b = this.boxes.get(edge.to);
      if (!a || !b) continue;
      const x1 = a.x + NODE_W / 2;
      const y1 = a.y + NODE_H;
      const x2 = b.x + NODE_W / 2;
      const y2 = b.y;
      const mid = (y1 + y2) / 2;
      const path = el("path", {
        d: `M${x1},${y1} C${x1},${mid} ${x2},${mid} ${x2},${y2}`,
        class: `edge${edge.dimmed ? " dimmed" : ""}`,
        "marker-end": "url(#arrow)",
      });
      edges.append(path);
      if (edge.count > 1) {
        const label = el("text", { x: (x1 + x2) / 2 + 6, y: mid, class: "edge-count" });
        label.textContent = strings.graph.wantsOnArrow(edge.count);
        edges.append(label);
      }
    }
    const defs = el("defs");
    const marker = el("marker", { id: "arrow", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" });
    marker.append(el("path", { d: "M0,0 L10,5 L0,10 z", class: "arrowhead" }));
    defs.append(marker);
    world.append(defs, edges);
    for (const node of scene.nodes) world.append(this.drawNode(node));
    this.apply(this.viewport, false);
  }

  private drawNode(node: RenderNode): SVGGElement {
    const box = this.boxes.get(node.address) ?? { x: 0, y: 0 };
    const classes = ["node", node.role ? `role-${node.role.toLowerCase()}` : "role-none"];
    if (node.selected) classes.push("selected");
    if (node.focus) classes.push("focus");
    if (node.dimmed) classes.push("dimmed");
    if (node.definitive) classes.push("definitive");
    if (node.beneath > 0 && node.collapsed) classes.push("collapsed");
    const g = el("g", {
      class: classes.join(" "),
      transform: `translate(${box.x},${box.y})`,
      tabindex: 0,
      role: "button",
      "data-address": node.address,
      "aria-label": [node.label, node.role ?? "", node.beneath > 0 ? strings.graph.beneathLabel(node.beneath, node.address) : ""]
        .filter(Boolean)
        .join(", "),
      "aria-pressed": node.selected ? "true" : "false",
    });
    if (node.beneath > 0 && node.collapsed) {
      g.append(el("rect", { x: 5, y: 5, width: NODE_W, height: NODE_H, rx: 6, class: "stack" }));
    }
    g.append(el("rect", { width: NODE_W, height: NODE_H, rx: 6, class: "body" }));
    const label = el("text", { x: 12, y: 20, class: "label" });
    label.textContent = node.label;
    g.append(label);
    const sub = el("text", { x: 12, y: 37, class: "sub" });
    sub.textContent = [node.role ?? "", node.status ?? ""].filter(Boolean).join(" · ");
    g.append(sub);
    if (node.beneath > 0) {
      const chevron = el("g", { class: "chevron", transform: `translate(${NODE_W - 22},${NODE_H / 2})` });
      chevron.append(el("path", { d: node.collapsed ? "M-3,-5 L3,0 L-3,5" : "M-5,-3 L0,3 L5,-3" }));
      const count = el("text", { x: -10, y: 18, class: "beneath", "text-anchor": "end" });
      count.textContent = strings.graph.beneathBadge(node.beneath);
      chevron.append(count);
      chevron.addEventListener("click", (e) => {
        e.stopPropagation();
        this.events?.chevronClick(node.address);
      });
      g.append(chevron);
    }
    node.layers.forEach((mark, i) => {
      const x = 12 + i * 30;
      const shape = mark.style % 3 === 0 ? el("rect", { x, y: NODE_H + 4, width: 8, height: 8 }) : mark.style % 3 === 1 ? el("circle", { cx: x + 4, cy: NODE_H + 8, r: 4.5 }) : el("path", { d: `M${x + 4},${NODE_H + 3} L${x + 9},${NODE_H + 12} L${x - 1},${NODE_H + 12} z` });
      shape.setAttribute("class", `layer-mark layer-${mark.style % 6}`);
      const text = el("text", { x: x + 11, y: NODE_H + 12, class: "layer-count" });
      text.textContent = String(mark.records);
      g.append(shape, text);
    });
    node.agents.forEach((agent, i) => {
      const a = el("g", { class: `agent${agent.active ? " active" : ""}`, transform: `translate(${NODE_W - 4 - i * 22},-6)` });
      a.append(el("circle", { r: 10 }));
      const t = el("text", { "text-anchor": "middle", y: 4 });
      t.textContent = agent.initials;
      a.append(t);
      g.append(a);
    });
    if (node.unseen) g.append(el("circle", { cx: 4, cy: 4, r: 4, class: "unseen" }));
    if (node.outside > 0) {
      const out = el("text", { x: NODE_W - 8, y: -6, class: "outside", "text-anchor": "end" });
      out.textContent = `↗ ${node.outside}`;
      g.append(out);
    }
    g.addEventListener("click", (e) => this.events?.nodeClick(node.address, { up: e.ctrlKey || e.metaKey, shift: e.shiftKey }));
    g.addEventListener("dblclick", (e) => {
      e.preventDefault();
      this.events?.nodeDoubleClick(node.address);
    });
    return g;
  }

  private apply(viewport: Viewport, animate: boolean): void {
    this.viewport = viewport;
    if (!this.world) return;
    const ms = animate && !reducedMotion() ? MAX_ANIMATION_MS : 0;
    this.world.style.transition = ms > 0 ? `transform ${ms}ms ease-out` : "none";
    this.world.style.transform = `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom})`;
    if (this.settle) clearTimeout(this.settle);
    this.settle = setTimeout(() => this.events?.viewportChange(this.viewport), 120);
  }

  setViewport(viewport: Viewport, animate: boolean): void {
    this.apply(viewport, animate);
  }

  async fit(animate: boolean): Promise<Viewport> {
    const host = this.host;
    if (!host || this.boxes.size === 0) return this.viewport;
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const box of this.boxes.values()) {
      minX = Math.min(minX, box.x);
      minY = Math.min(minY, box.y - 16);
      maxX = Math.max(maxX, box.x + NODE_W);
      maxY = Math.max(maxY, box.y + NODE_H + 16);
    }
    const width = Math.max(1, host.clientWidth - FIT_MARGIN * 2);
    const height = Math.max(1, host.clientHeight - FIT_MARGIN * 2);
    const zoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Math.min(width / (maxX - minX), height / (maxY - minY))));
    const viewport = {
      zoom,
      x: FIT_MARGIN + (width - (maxX - minX) * zoom) / 2 - minX * zoom,
      y: FIT_MARGIN + (height - (maxY - minY) * zoom) / 2 - minY * zoom,
    };
    this.apply(viewport, animate);
    return viewport;
  }

  focusNode(address: string): void {
    const node = this.svg?.querySelector<SVGGElement>(`[data-address="${CSS.escape(address)}"]`);
    node?.focus({ preventScroll: true });
  }

  unmount(): void {
    this.svg?.remove();
    this.svg = null;
    this.world = null;
    this.host = null;
    if (this.settle) clearTimeout(this.settle);
  }
}
