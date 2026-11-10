// Eased, interruptible camera (climb step 5; UX section 12a). The camera always knows the
// viewport it is showing now. A move eases from there to its target over CAMERA_MS with the
// shared EASING curve. A new move, a drag or a wheel turn during a move starts from what is shown
// at that moment, so nothing jumps. Under prefers-reduced-motion every move is immediate.
//
// A fit is a longer move, FIT_MS, as in the earlier map: the point of the graph at the centre of
// the pane moves in a straight line, and the size changes in log space, so the graph does not
// swing aside while it grows or shrinks.

import { CAMERA_MS, EASING, FIT_MS, type Viewport } from "./renderer";
import { reducedMotion } from "./flow";

/** A CSS cubic-bezier(x1, y1, x2, y2) as a function of progress 0..1. */
export function cubicBezier(x1: number, y1: number, x2: number, y2: number): (t: number) => number {
  const bez = (a: number, b: number, t: number) => 3 * a * t * (1 - t) ** 2 + 3 * b * t * t * (1 - t) + t ** 3;
  const slope = (a: number, b: number, t: number) => 3 * a * (1 - t) ** 2 + 6 * (b - a) * t * (1 - t) + 3 * (1 - b) * t * t;
  return (x: number) => {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    // Solve bez(x1, x2, t) = x for t with Newton steps, then bisection if the slope is flat.
    let t = x;
    for (let i = 0; i < 8; i++) {
      const err = bez(x1, x2, t) - x;
      if (Math.abs(err) < 1e-5) return bez(y1, y2, t);
      const d = slope(x1, x2, t);
      if (Math.abs(d) < 1e-6) break;
      t -= err / d;
    }
    let lo = 0;
    let hi = 1;
    t = x;
    for (let i = 0; i < 30; i++) {
      const v = bez(x1, x2, t);
      if (Math.abs(v - x) < 1e-5) break;
      if (v < x) lo = t;
      else hi = t;
      t = (lo + hi) / 2;
    }
    return bez(y1, y2, t);
  };
}

/** The shared curve, read from EASING ("cubic-bezier(a, b, c, d)"), so the CSS and the camera agree. */
const [x1 = 0.25, y1 = 0.8, x2 = 0.3, y2 = 1] = (EASING.match(/-?[\d.]+/g) ?? []).map(Number);
export const ease = cubicBezier(x1, y1, x2, y2);

/**
 * The viewport at progress `k` (0 to 1) of a fit from `from` to `to`. `pivot` is the centre of
 * the clear part of the pane, in screen pixels. The graph point under the pivot moves linearly
 * and the zoom moves in log space.
 */
export function between(from: Viewport, to: Viewport, k: number, pivot: { x: number; y: number }): Viewport {
  const centre = (v: Viewport) => ({ x: (pivot.x - v.x) / v.zoom, y: (pivot.y - v.y) / v.zoom });
  const a = centre(from);
  const b = centre(to);
  const zoom = Math.exp(Math.log(from.zoom) + (Math.log(to.zoom) - Math.log(from.zoom)) * k);
  return { x: pivot.x - (a.x + (b.x - a.x) * k) * zoom, y: pivot.y - (a.y + (b.y - a.y) * k) * zoom, zoom };
}

/** The camera of one graph: it knows the viewport on screen and eases to each new one. */
export class Camera {
  private shown: Viewport = { x: 0, y: 0, zoom: 1 };
  private frame = 0;

  constructor(private readonly apply: (viewport: Viewport) => void) {}

  /** The viewport on screen now, mid-move included. */
  get current(): Viewport {
    return { ...this.shown };
  }

  /** Moves to `target`, eased from what is shown now, or at once. Cancels any running move. */
  moveTo(target: Viewport, animate: boolean): void {
    this.stop();
    if (!animate || reducedMotion()) {
      this.show(target);
      return;
    }
    const from = { ...this.shown };
    // Zoom eases in log space, so zooming in and out feel the same.
    this.run(CAMERA_MS, (k) => ({
      x: from.x + (target.x - from.x) * k,
      y: from.y + (target.y - from.y) * k,
      zoom: Math.exp(Math.log(from.zoom) + (Math.log(target.zoom) - Math.log(from.zoom)) * k),
    }));
  }

  /**
   * Eases to a fit over FIT_MS, from what is shown now, or at once. `pivot` is the centre of the
   * clear part of the pane (see `between`). Cancels any running move.
   */
  fitTo(target: Viewport, pivot: { x: number; y: number }, animate: boolean): void {
    this.stop();
    if (!animate || reducedMotion()) {
      this.show(target);
      return;
    }
    const from = { ...this.shown };
    this.run(FIT_MS, (k) => between(from, target, k, pivot));
  }

  private run(ms: number, at: (k: number) => Viewport): void {
    const start = performance.now();
    const step = (now: number) => {
      const p = Math.min(1, (now - start) / ms);
      this.show(at(ease(p)));
      this.frame = p < 1 ? requestAnimationFrame(step) : 0;
    };
    this.frame = requestAnimationFrame(step);
  }

  /** Ends a running move where it is. */
  stop(): void {
    if (this.frame) cancelAnimationFrame(this.frame);
    this.frame = 0;
  }

  get moving(): boolean {
    return this.frame !== 0;
  }

  private show(viewport: Viewport): void {
    this.shown = { ...viewport };
    this.apply(this.shown);
  }
}
