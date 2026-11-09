// Layout motion (climb step 6a; UX section 12a). After a relayout, every element glides from where
// it is drawn now to its new place over LAYOUT_MS on the shared curve; a new element fades and
// grows in (opacity 0 to 1, scale .92 to 1); the wants, their flow and their detail fade in once
// the elements have arrived. A new layout during a glide starts from the positions on screen at
// that moment, so nothing jumps. Under prefers-reduced-motion everything is placed at once.

import type { Address } from "../source/types";
import { ease } from "./camera";
import { reducedMotion } from "./flow";
import { LAYOUT_MS, MAX_ANIMATION_MS } from "./renderer";

export interface GlideItem {
  address: Address;
  group: SVGGElement;
  to: { x: number; y: number };
  width: number;
  height: number;
}

const GROW_FROM = 0.92;

export class Glide {
  /** Where each element is drawn now (top-left, canvas units). */
  private readonly shown = new Map<Address, { x: number; y: number }>();
  private frame = 0;

  /** Moves the drawn elements to their places; `after` fades in once they have arrived. */
  run(items: GlideItem[], after: (SVGElement | HTMLElement)[]): void {
    if (this.frame) cancelAnimationFrame(this.frame);
    this.frame = 0;
    const keep = new Set(items.map((i) => i.address));
    for (const address of [...this.shown.keys()]) if (!keep.has(address)) this.shown.delete(address);

    const moves = items.map((item) => ({ item, from: this.shown.get(item.address) ?? null }));
    const still = moves.every(({ item, from }) => from !== null && from.x === item.to.x && from.y === item.to.y);
    if (still || reducedMotion()) {
      for (const { item } of moves) this.place(item, item.to, 1);
      for (const layer of after) layer.style.opacity = "";
      return;
    }
    for (const layer of after) {
      layer.style.transition = "";
      layer.style.opacity = "0";
    }
    const start = performance.now();
    const step = (now: number) => {
      const p = Math.min(1, (now - start) / LAYOUT_MS);
      const k = ease(p);
      for (const { item, from } of moves) {
        if (from === null) this.place(item, item.to, k, GROW_FROM + (1 - GROW_FROM) * k);
        else this.place(item, { x: from.x + (item.to.x - from.x) * k, y: from.y + (item.to.y - from.y) * k }, 1);
      }
      if (p < 1) {
        this.frame = requestAnimationFrame(step);
        return;
      }
      this.frame = 0;
      for (const layer of after) {
        layer.style.transition = `opacity ${MAX_ANIMATION_MS}ms ease-out`;
        layer.style.opacity = "";
      }
    };
    // Paint the starting frame now, so a fresh element never shows at full size first.
    step(start);
  }

  stop(): void {
    if (this.frame) cancelAnimationFrame(this.frame);
    this.frame = 0;
    this.shown.clear();
  }

  private place(item: GlideItem, at: { x: number; y: number }, opacity: number, scale = 1): void {
    this.shown.set(item.address, at);
    const dx = (item.width * (1 - scale)) / 2;
    const dy = (item.height * (1 - scale)) / 2;
    item.group.setAttribute(
      "transform",
      scale === 1 ? `translate(${at.x},${at.y})` : `translate(${at.x + dx},${at.y + dy}) scale(${scale})`,
    );
    item.group.style.opacity = opacity === 1 ? "" : String(opacity);
  }
}
