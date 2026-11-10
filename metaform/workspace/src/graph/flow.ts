// The flow along wants (UX section 12a; R-3.6), after the earlier map viewer
// (context/topogee-repo/experiments/map-viewer). It shows what a want's `direction` means, not a
// metronome: the request is never the direction, the substance is.
//
// - A want whose substance comes back to the holder (`inbound`, or `two-way`): a small white dot
//   runs from the holder to the provider. That is the request. Then a streak in the provider's
//   colour runs back. That is the answer, and its length is the amount of data, which differs
//   each time. On a `two-way` want a second streak runs the other way at the same time.
// - A want whose substance goes out from the holder (`outbound`): a card runs from the holder to
//   the provider and lands with a ring.
// - Timing is random: every wait and every size is `random() + random()` times a mean, so the
//   values gather around the mean and no two wants move in step. One thing is not random: when an
//   element answers a request, the records it sends go out at that moment, so an answer is seen
//   to cause what follows it.
//
// A route always runs from the holder (`from`) to the wanted element (`to`). One
// requestAnimationFrame loop drives everything; it runs only while lines exist, and the browser
// pauses it in a hidden tab. Under prefers-reduced-motion nothing moves: a still chevron at the
// middle of the line shows the direction instead.

export type FlowDirection = "outbound" | "inbound" | "two-way";

const SVG = "http://www.w3.org/2000/svg";

/** Seconds, except `data`, which is the mean size of an answer in units of the request's length. */
const TIME = { ask: 0.45, reply: 0.9, send: 0.8, burst: 0.55, wait: 3 };
const DATA = 5;
/** Canvas units of streak for one unit of data. */
const UNIT = 3.8;
/** Distance between the points a streak is drawn through. */
const STEP = 6;

/** Two uniform values added: between 0 and 2, most often near 1. */
const spread = (): number => Math.random() + Math.random();

interface Cycle {
  /** When this cycle started, on the flow clock. */
  at: number;
  /** The pause after the cycle, before the next one. */
  wait: number;
  /** How long this cycle's answer travels, and how much data it carries. */
  reply: number;
  size: number;
  /** A driven cycle starts only when its holder answers a request. */
  driven: boolean;
  answered: boolean;
}

interface Line {
  id: string;
  from: string;
  to: string;
  direction: FlowDirection;
  path: SVGPathElement;
  length: number;
  ask: SVGCircleElement;
  trains: SVGPathElement[];
  card: SVGRectElement;
  ring: SVGCircleElement;
  cycle: Cycle | null;
}

export function reducedMotion(): boolean {
  return typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
}

const smooth = (t: number): number => t * t * (3 - 2 * t);
const clamp = (t: number): number => Math.min(1, Math.max(0, t));

export class Flow {
  private lines: Line[] = [];
  private frame = 0;
  private layer: SVGGElement | null = null;
  private clock = 0;
  private last = 0;
  /** Elements that answer a request: the provider of some want whose substance comes back. */
  private answering = new Set<string>();
  /** The outbound wants each element holds, by element. */
  private sends = new Map<string, Line[]>();

  /** The group the flow is drawn into; the renderer makes a new one on every redraw. */
  setLayer(layer: SVGGElement): void {
    this.clear();
    this.layer = layer;
  }

  /**
   * Adds the flow of one want. `from` holds the want and `to` provides; `role` is the provider's
   * role, which colours the answer.
   */
  add(id: string, path: SVGPathElement, direction: FlowDirection, from = "", to = "", role = "none"): void {
    if (!this.layer) return;
    const length = path.getTotalLength();
    if (!(length > 0)) return;
    if (reducedMotion()) {
      const ways = direction === "two-way" ? [true, false] : [direction === "outbound"];
      for (const forward of ways) this.chevron(path, length, forward, ways.length === 2);
      return;
    }
    const make = <K extends keyof SVGElementTagNameMap>(tag: K, cls: string): SVGElementTagNameMap[K] => {
      const el = document.createElementNS(SVG, tag);
      el.setAttribute("class", cls);
      el.setAttribute("data-edge", id);
      el.style.display = "none";
      this.layer?.appendChild(el);
      return el;
    };
    const line: Line = {
      id, from, to, direction, path, length,
      trains: [make("path", `mf-flow-train mf-flow-${role}`), make("path", `mf-flow-train mf-flow-${role}`)],
      ask: make("circle", "mf-flow-ask"),
      card: make("rect", "mf-flow-card"),
      ring: make("circle", "mf-flow-ring"),
      cycle: null,
    };
    line.ask.setAttribute("r", "1.9");
    line.card.setAttribute("width", "9");
    line.card.setAttribute("height", "6.4");
    line.card.setAttribute("x", "-4.5");
    line.card.setAttribute("y", "-3.2");
    line.card.setAttribute("rx", "1.4");
    this.lines.push(line);
    if (direction === "outbound") this.sends.set(from, [...(this.sends.get(from) ?? []), line]);
    else this.answering.add(to);
    if (!this.frame) this.frame = requestAnimationFrame(this.tick);
  }

  clear(): void {
    if (this.frame) cancelAnimationFrame(this.frame);
    this.frame = 0;
    for (const line of this.lines) for (const el of [line.ask, line.card, line.ring, ...line.trains]) el.remove();
    this.lines = [];
    this.answering = new Set();
    this.sends = new Map();
    this.last = 0;
  }

  private readonly tick = (now: number): void => {
    // The clock never jumps: after a hidden tab or a slow frame it moves on by a tenth of a second.
    this.clock += Math.min(0.1, (now - (this.last || now)) / 1000);
    this.last = now;
    for (const line of this.lines) if (line.path.isConnected) this.draw(line);
    this.frame = this.lines.length > 0 ? requestAnimationFrame(this.tick) : 0;
  };

  /** A new cycle. A free one starts at a random moment in the past, so lines do not start together. */
  private fresh(driven: boolean): Cycle {
    const data = { reply: Math.max(0.3, spread() * TIME.reply), size: spread() * DATA };
    return driven
      ? { at: -Infinity, wait: Infinity, driven, answered: true, ...data }
      : { at: this.clock - Math.random() * 2 * TIME.wait, wait: 0, driven, answered: false, ...data };
  }

  /** The line's cycle, moved on to the present. `active` is how long the cycle's own motion lasts. */
  private cycleOf(line: Line, active: number, driven: boolean): Cycle {
    let cycle = line.cycle;
    if (!cycle || cycle.driven !== driven) cycle = line.cycle = this.fresh(driven);
    while (this.clock - cycle.at > active + cycle.reply + cycle.wait) {
      cycle.at += active + cycle.reply + cycle.wait;
      cycle.wait = spread() * TIME.wait;
      cycle.answered = false;
      cycle.reply = Math.max(0.3, spread() * TIME.reply);
      cycle.size = spread() * DATA;
    }
    return cycle;
  }

  /** Starts a driven send now, unless it is still on its way. */
  private fire(line: Line): void {
    const cycle = this.cycleOf(line, TIME.send + TIME.burst, true);
    if (this.clock - cycle.at >= TIME.send) cycle.at = this.clock;
  }

  private point(line: Line, share: number): DOMPoint {
    return line.path.getPointAtLength(clamp(share) * line.length);
  }

  /** The part of the line from `from` to `to` (shares of its length), as a path through its points. */
  private stretch(line: Line, from: number, to: number): string {
    const start = clamp(from) * line.length;
    const end = clamp(to) * line.length;
    const first = line.path.getPointAtLength(start);
    let d = `M${first.x.toFixed(1)},${first.y.toFixed(1)}`;
    if (end - start < 0.5) return `${d}h0.01`;
    for (let at = start + STEP; at < end; at += STEP) {
      const p = line.path.getPointAtLength(at);
      d += `L${p.x.toFixed(1)},${p.y.toFixed(1)}`;
    }
    const last = line.path.getPointAtLength(end);
    return `${d}L${last.x.toFixed(1)},${last.y.toFixed(1)}`;
  }

  private draw(line: Line): void {
    const show = (el: SVGElement, on: boolean) => {
      const value = on ? "" : "none";
      if (el.style.display !== value) el.style.display = value;
    };
    if (line.direction === "outbound") {
      // The holder sends a record. It is driven when the holder answers requests: the record
      // goes out as the answer does.
      const cycle = this.cycleOf(line, TIME.send + TIME.burst, this.answering.has(line.from));
      const since = this.clock - cycle.at;
      const travelling = since >= 0 && since < TIME.send;
      const ringing = !travelling && since >= TIME.send && since < TIME.send + TIME.burst;
      if (travelling) {
        const p = this.point(line, smooth(since / TIME.send));
        line.card.setAttribute("transform", `translate(${p.x.toFixed(1)} ${p.y.toFixed(1)})`);
      }
      if (ringing) {
        const u = (since - TIME.send) / TIME.burst;
        const p = this.point(line, 1);
        line.ring.setAttribute("cx", p.x.toFixed(1));
        line.ring.setAttribute("cy", p.y.toFixed(1));
        line.ring.setAttribute("r", (4 + 14 * u).toFixed(1));
        line.ring.style.opacity = Math.pow(1 - u, 1.5).toFixed(2);
      }
      show(line.card, travelling);
      show(line.ring, ringing);
      show(line.ask, false);
      for (const train of line.trains) show(train, false);
      return;
    }
    const cycle = this.cycleOf(line, TIME.ask, false);
    const since = this.clock - cycle.at;
    if (since >= TIME.ask && !cycle.answered) {
      cycle.answered = true;
      // The request has arrived. The provider answers, and what the provider sends goes out now.
      if (since < TIME.ask + cycle.reply) for (const send of this.sends.get(line.to) ?? []) this.fire(send);
    }
    const asking = since >= 0 && since < TIME.ask;
    const replying = !asking && since >= TIME.ask && since < TIME.ask + cycle.reply;
    if (asking) {
      const p = this.point(line, since / TIME.ask);
      line.ask.setAttribute("cx", p.x.toFixed(1));
      line.ask.setAttribute("cy", p.y.toFixed(1));
    }
    show(line.ask, asking);
    const ways = replying ? (line.direction === "two-way" ? 2 : 1) : 0;
    for (let i = 0; i < 2; i++) {
      const train = line.trains[i]!;
      if (i < ways) {
        // The streak's length is its data. Its head runs past the end, so the whole of it arrives.
        const long = Math.min(1, (cycle.size * UNIT) / Math.max(1, line.length));
        const head = ((since - TIME.ask) / cycle.reply) * (1 + long);
        const from = Math.max(0, head - long);
        const to = Math.min(1, head);
        // The answer runs from the provider back to the holder; on a two-way want the second
        // streak runs from the holder to the provider.
        const back = i === 0;
        train.setAttribute("d", from > to ? "" : back ? this.stretch(line, 1 - to, 1 - from) : this.stretch(line, from, to));
      }
      show(train, i < ways);
    }
    show(line.card, false);
    show(line.ring, false);
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
