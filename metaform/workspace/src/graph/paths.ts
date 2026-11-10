// The SVG paths of the wants: from the points of a route to the path that is drawn.

import type { Point } from "./layout";

/** Corner radius of a routed edge's bends. */
const CORNER = 8;

/**
 * The path of a spline route from ELK: the start point, then cubic segments of two control
 * points and an end point. A route whose points do not divide into such segments is drawn
 * through its points, so a line is never dropped.
 */
function splineFor(points: Point[]): string {
  const [first] = points;
  if (!first || points.length < 2) return "";
  let d = `M${first.x},${first.y}`;
  if ((points.length - 1) % 3 !== 0) {
    for (const p of points.slice(1)) d += ` L${p.x},${p.y}`;
    return d;
  }
  for (let i = 1; i + 2 < points.length; i += 3) {
    const [a, b, c] = [points[i]!, points[i + 1]!, points[i + 2]!];
    d += ` C${a.x},${a.y} ${b.x},${b.y} ${c.x},${c.y}`;
  }
  return d;
}

/**
 * The SVG path for a route. A spline route is drawn as ELK gives it. Any other route with bend
 * points is drawn as straight segments with rounded corners, and a two-point route as an S-curve.
 */
export function pathFor(points: Point[], curved = false): string {
  if (curved && points.length > 2) return splineFor(points);
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
export function offset(points: Point[], d: number): Point[] {
  const first = points[0];
  const last = points[points.length - 1];
  if (!first || !last) return points;
  const length = Math.hypot(last.x - first.x, last.y - first.y) || 1;
  const nx = (-(last.y - first.y) / length) * d;
  const ny = ((last.x - first.x) / length) * d;
  return points.map((p) => ({ x: p.x + nx, y: p.y + ny }));
}

/** The middle of a route, where its count and its detail are placed. */
export function midpoint(points: Point[]): Point {
  const a = points[Math.floor((points.length - 1) / 2)] ?? { x: 0, y: 0 };
  const b = points[Math.ceil((points.length - 1) / 2)] ?? a;
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}
