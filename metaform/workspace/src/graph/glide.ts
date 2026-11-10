// Layout motion, as in the earlier Metaform map. Between two layouts, every element slides from
// where it is drawn now to its new place over LAYOUT_MS, fast at first and slower at the end
// (ease-out cubic). A new element grows from the place of the element it hangs from. A removed
// element fades out where it was. The wants, their flow and their detail fade in once the elements
// have arrived. A new layout during the motion starts from the positions on screen at that
// moment, so nothing jumps. Under prefers-reduced-motion everything is placed at once.

import type { Address } from "../source/types";
import { reducedMotion } from "./flow";
import { LAYOUT_MS, MAX_ANIMATION_MS } from "./renderer";

/** One drawn element, and where the new layout puts it. */
export interface GlideItem {
  address: Address;
  group: SVGGElement;
  to: { x: number; y: number };
  width: number;
  height: number;
  /**
   * For an element that was not drawn before: the elements it may grow from, best first. The
   * first one that was drawn before is used. With none, the element grows in its own place.
   */
  origins?: readonly Address[];
}

/** The size a new element starts at, as a part of its full size. */
const GROW_FROM = 0.3;

/** Progress with a fast start and a slow end. */
export function easeOutCubic(t: number): number {
  const p = Math.min(1, Math.max(0, t));
  return 1 - (1 - p) ** 3;
}

interface Shown {
  x: number;
  y: number;
  width: number;
  height: number;
  group: SVGGElement;
}

/** Moves the drawn elements of one graph from each layout to the next. */
export class Glide {
  /** Where each element is drawn now (top-left and size, canvas units), and its SVG group. */
  private readonly shown = new Map<Address, Shown>();
  private frame = 0;
  /** Removed elements that are still fading out. */
  private leaving: SVGGElement[] = [];
  /** The motion in progress: when it started, and where each element started and is going. */
  private motion: { start: number; from: Map<Address, Shown | null>; origin: Map<Address, Shown | null>; to: Map<Address, { x: number; y: number }> } | null = null;

  /**
   * Moves the drawn elements to their places. `after` fades in once they have arrived. Elements
   * drawn before and absent from `items` fade out in `leavingLayer`.
   */
  run(items: GlideItem[], after: (SVGElement | HTMLElement)[], leavingLayer?: SVGGElement): void {
    // The same elements drawn again with the same places, while they are moving: the motion goes
    // on from where it is. Starting it again on every redraw would hold the elements still.
    const going = this.frame !== 0 ? this.motion : null;
    const same = going !== null && going.to.size === items.length && items.every((i) => going.to.get(i.address)?.x === i.to.x && going.to.get(i.address)?.y === i.to.y);
    if (this.frame) cancelAnimationFrame(this.frame);
    this.frame = 0;
    if (!same) for (const ghost of this.leaving.splice(0)) ghost.remove();
    // The redraw made a new layer for the fading elements; they move into it.
    else if (leavingLayer) for (const ghost of this.leaving) leavingLayer.appendChild(ghost);
    const moving = !reducedMotion();
    const first = this.shown.size === 0;
    const before = new Map(this.shown);
    const keep = new Set(items.map((i) => i.address));
    for (const [address, was] of before) {
      if (keep.has(address)) continue;
      this.shown.delete(address);
      if (moving && leavingLayer) this.leave(was, leavingLayer);
    }

    const moves = items.map((item) => {
      if (same && going) return { item, from: going.from.get(item.address) ?? null, origin: going.origin.get(item.address) ?? null };
      const from = before.get(item.address) ?? null;
      const origin = from === null && !first ? (item.origins ?? []).map((a) => before.get(a)).find((o) => o !== undefined) ?? null : null;
      return { item, from, origin };
    });
    const unmoved = this.leaving.length === 0 && moves.every(({ item, from }) => from !== null && from.x === item.to.x && from.y === item.to.y);
    if (unmoved || !moving) {
      for (const { item } of moves) this.place(item, item.to, 1);
      for (const layer of after) layer.style.opacity = "";
      this.motion = null;
      return;
    }
    for (const layer of after) {
      layer.style.transition = "";
      layer.style.opacity = "0";
    }
    const start = same && going ? going.start : performance.now();
    this.motion = {
      start,
      from: new Map(moves.map((m) => [m.item.address, m.from])),
      origin: new Map(moves.map((m) => [m.item.address, m.origin])),
      to: new Map(items.map((i) => [i.address, i.to])),
    };
    const step = (now: number) => {
      const p = Math.min(1, (now - start) / LAYOUT_MS);
      const k = easeOutCubic(p);
      for (const { item, from, origin } of moves) {
        if (from !== null) {
          this.place(item, { x: from.x + (item.to.x - from.x) * k, y: from.y + (item.to.y - from.y) * k }, 1);
          continue;
        }
        // A new element: its centre moves from the centre of the element it hangs from.
        const scale = GROW_FROM + (1 - GROW_FROM) * k;
        const end = { x: item.to.x + item.width / 2, y: item.to.y + item.height / 2 };
        const begin = origin ? { x: origin.x + origin.width / 2, y: origin.y + origin.height / 2 } : end;
        const centre = { x: begin.x + (end.x - begin.x) * k, y: begin.y + (end.y - begin.y) * k };
        this.place(item, { x: centre.x - (item.width * scale) / 2, y: centre.y - (item.height * scale) / 2 }, k, scale);
      }
      const fade = Math.max(0, 1 - (now - start) / MAX_ANIMATION_MS);
      for (const ghost of this.leaving) ghost.style.opacity = String(fade);
      if (p < 1) {
        this.frame = requestAnimationFrame(step);
        return;
      }
      this.frame = 0;
      this.motion = null;
      for (const ghost of this.leaving.splice(0)) ghost.remove();
      for (const layer of after) {
        layer.style.transition = `opacity ${MAX_ANIMATION_MS}ms ease-out`;
        layer.style.opacity = "";
      }
    };
    // Paint the first frame now, so a fresh element never shows at full size first.
    step(same ? performance.now() : start);
  }

  /** Ends the motion and forgets every position. */
  stop(): void {
    if (this.frame) cancelAnimationFrame(this.frame);
    this.frame = 0;
    for (const ghost of this.leaving.splice(0)) ghost.remove();
    this.shown.clear();
    this.motion = null;
  }

  /** Keeps a removed element's drawing on screen, where it was, without a name or a focus stop. */
  private leave(was: Shown, layer: SVGGElement): void {
    const ghost = was.group;
    for (const name of ["data-address", "tabindex", "role", "aria-label", "aria-pressed"]) ghost.removeAttribute(name);
    ghost.setAttribute("aria-hidden", "true");
    ghost.setAttribute("transform", `translate(${was.x},${was.y})`);
    ghost.style.transition = "none";
    ghost.style.pointerEvents = "none";
    layer.appendChild(ghost);
    this.leaving.push(ghost);
  }

  private place(item: GlideItem, at: { x: number; y: number }, opacity: number, scale = 1): void {
    // While it grows, an element is recorded at its full size around its centre, so an
    // interrupted move continues from where the element is.
    const dx = (item.width * (1 - scale)) / 2;
    const dy = (item.height * (1 - scale)) / 2;
    this.shown.set(item.address, { x: at.x - dx, y: at.y - dy, width: item.width, height: item.height, group: item.group });
    item.group.setAttribute("transform", scale === 1 ? `translate(${at.x},${at.y})` : `translate(${at.x},${at.y}) scale(${scale})`);
    item.group.style.opacity = opacity === 1 ? "" : String(opacity);
  }
}
