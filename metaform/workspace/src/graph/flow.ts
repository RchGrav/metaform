// Want direction flow (climb step 4; UX section 12a; R-3.6). Small markers move slowly along a
// want's line: `outbound` from the holder to the wanted element, `inbound` from the wanted element
// back to the holder, `two-way` both ways. A route always runs from the holder (`from`) to the
// wanted element (`to`), so "forward" means holder to wanted.
// One requestAnimationFrame loop drives every marker; it runs only while markers exist, and the
// browser pauses it in a hidden tab. Under prefers-reduced-motion nothing moves: a still chevron
// at the middle of the line shows the direction instead.

export type FlowDirection = "outbound" | "inbound" | "two-way";

const SVG = "http://www.w3.org/2000/svg";
/** One trip along a line takes this long: slow enough to read as flow, not as traffic. */
const PERIOD_MS = 2400;
/** Markers per direction on one line, evenly spaced. */
const PER_WAY = 3;
const RADIUS = 3.5;

interface Dot {
  el: SVGCircleElement;
  forward: boolean;
  offset: number;
}

interface Line {
  path: SVGPathElement;
  length: number;
  dots: Dot[];
}

/** A stable phase per line from its id, so neighbouring lines do not pulse in step. */
function phaseOf(id: string): number {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  return (h % 1000) / 1000;
}

export function reducedMotion(): boolean {
  return typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export class Flow {
  private lines: Line[] = [];
  private frame = 0;
  private layer: SVGGElement | null = null;

  /** The group markers are drawn into; the renderer makes a new one on every redraw. */
  setLayer(layer: SVGGElement): void {
    this.clear();
    this.layer = layer;
  }

  /** Adds the direction to one line. `id` gives the line its own phase. */
  add(id: string, path: SVGPathElement, direction: FlowDirection): void {
    if (!this.layer) return;
    const length = path.getTotalLength();
    if (!(length > 0)) return;
    const ways = direction === "two-way" ? [true, false] : [direction === "outbound"];
    if (reducedMotion()) {
      for (const forward of ways) this.chevron(path, length, forward, ways.length === 2);
      return;
    }
    const phase = phaseOf(id);
    const dots: Dot[] = [];
    for (const forward of ways) {
      for (let i = 0; i < PER_WAY; i++) {
        const el = document.createElementNS(SVG, "circle");
        el.setAttribute("r", String(RADIUS));
        el.setAttribute("class", "mf-flow-dot");
        el.setAttribute("data-forward", String(forward));
        el.setAttribute("data-edge", id);
        this.layer.appendChild(el);
        // Two-way lines offset their two streams by half a gap, so the dots do not meet in pairs.
        dots.push({ el, forward, offset: (phase + i / PER_WAY + (forward ? 0 : 0.5 / PER_WAY)) % 1 });
      }
    }
    this.lines.push({ path, length, dots });
    this.place(performance.now());
    if (!this.frame) this.frame = requestAnimationFrame(this.tick);
  }

  clear(): void {
    if (this.frame) cancelAnimationFrame(this.frame);
    this.frame = 0;
    for (const line of this.lines) for (const dot of line.dots) dot.el.remove();
    this.lines = [];
  }

  private readonly tick = (now: number): void => {
    this.place(now);
    this.frame = this.lines.length > 0 ? requestAnimationFrame(this.tick) : 0;
  };

  private place(now: number): void {
    const u = now / PERIOD_MS;
    for (const line of this.lines) {
      if (!line.path.isConnected) continue;
      for (const dot of line.dots) {
        const f = (u + dot.offset) % 1;
        const at = line.path.getPointAtLength((dot.forward ? f : 1 - f) * line.length);
        dot.el.setAttribute("cx", at.x.toFixed(1));
        dot.el.setAttribute("cy", at.y.toFixed(1));
        // Fade in after leaving one end and out before reaching the other.
        dot.el.style.opacity = Math.sin(Math.PI * f).toFixed(2);
        dot.el.setAttribute("data-u", f.toFixed(3));
      }
    }
  }

  /** A still chevron pointing along the flow, for reduced motion. */
  private chevron(path: SVGPathElement, length: number, forward: boolean, pair: boolean): void {
    if (!this.layer) return;
    const at = length * (pair ? (forward ? 0.42 : 0.58) : 0.5);
    const a = path.getPointAtLength(Math.max(0, at - 2));
    const b = path.getPointAtLength(Math.min(length, at + 2));
    const angle = (Math.atan2(b.y - a.y, b.x - a.x) * 180) / Math.PI + (forward ? 0 : 180);
    const mid = path.getPointAtLength(at);
    const el = document.createElementNS(SVG, "path");
    el.setAttribute("d", "M-4,-4 L2,0 L-4,4");
    el.setAttribute("class", "mf-flow-chevron");
    el.setAttribute("transform", `translate(${mid.x.toFixed(1)},${mid.y.toFixed(1)}) rotate(${angle.toFixed(1)})`);
    this.layer.appendChild(el);
  }
}
