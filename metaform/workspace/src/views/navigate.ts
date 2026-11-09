// Arrow keys move the selection along wants (UX section 12a; the earlier intake graph viewer plan:
// "smoothly move between connected nodes with arrow keys").

import type { Address } from "../source";
import type { RenderScene } from "../graph/renderer";

export type Arrow = "ArrowRight" | "ArrowLeft" | "ArrowUp" | "ArrowDown";

const DIRECTIONS: Record<Arrow, { x: number; y: number }> = {
  ArrowRight: { x: 1, y: 0 },
  ArrowLeft: { x: -1, y: 0 },
  ArrowUp: { x: 0, y: -1 },
  ArrowDown: { x: 0, y: 1 },
};

export function isArrow(key: string): key is Arrow {
  return key in DIRECTIONS;
}

/** The elements joined to `at` by a want drawn in the scene, either way. */
export function connected(scene: RenderScene, at: Address): Address[] {
  const out = new Set<Address>();
  for (const edge of scene.edges) {
    if (edge.from === at) out.add(edge.to);
    if (edge.to === at) out.add(edge.from);
  }
  out.delete(at);
  return [...out];
}

/**
 * The connected element that lies most nearly in the arrow's direction from `at`, or null when none
 * lies on that side. Distance counts, and so does the angle: an element 30° off the arrow costs as
 * much as one twice as far away straight ahead.
 */
export function nearestInDirection(
  at: Address,
  candidates: readonly Address[],
  centres: ReadonlyMap<Address, { x: number; y: number }>,
  arrow: Arrow,
): Address | null {
  const from = centres.get(at);
  if (!from) return null;
  const d = DIRECTIONS[arrow];
  let best: { address: Address; cost: number } | null = null;
  for (const address of candidates) {
    const c = centres.get(address);
    if (!c) continue;
    const dx = c.x - from.x;
    const dy = c.y - from.y;
    const distance = Math.hypot(dx, dy);
    if (distance === 0) continue;
    const cos = (dx * d.x + dy * d.y) / distance;
    if (cos <= 0.2) continue;
    const cost = distance * (1 + 2 * (1 - cos));
    if (!best || cost < best.cost) best = { address, cost };
  }
  return best?.address ?? null;
}

/** The on-screen centre of each drawn node, from the renderer's `data-address` marks (renderer rule 5). */
export function nodeCentres(host: ParentNode = document): Map<Address, { x: number; y: number }> {
  const centres = new Map<Address, { x: number; y: number }>();
  for (const node of host.querySelectorAll<Element>(".canvas [data-address]")) {
    const address = node.getAttribute("data-address");
    const r = node.getBoundingClientRect();
    if (address && r.width > 0) centres.set(address, { x: r.left + r.width / 2, y: r.top + r.height / 2 });
  }
  return centres;
}
