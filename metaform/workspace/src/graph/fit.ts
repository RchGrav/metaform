// What each fit frames, and the viewport that frames it. Pure functions; the renderer eases the
// camera to the result (camera.ts).

import type { Address } from "../source/types";
import type { Box } from "./layout";
import { type Insets, MAX_ZOOM, MIN_ZOOM, type RenderScene, type Viewport } from "./renderer";

/** No part of the pane is covered. */
export const NO_INSETS: Insets = { left: 0, right: 0, top: 0, bottom: 0 };

/** The part of a pane that nothing covers, in screen pixels. It keeps a least size, so a fit always has room. */
export function clearPart(pane: { width: number; height: number }, insets: Insets): Box {
  const width = Math.max(40, pane.width - insets.left - insets.right);
  const height = Math.max(40, pane.height - insets.top - insets.bottom);
  return { x: Math.min(insets.left, Math.max(0, pane.width - width)), y: Math.min(insets.top, Math.max(0, pane.height - height)), width, height };
}

/** The smallest box around the given boxes, or null when there is none. */
export function around(boxes: readonly Box[]): Box | null {
  if (boxes.length === 0) return null;
  const x = Math.min(...boxes.map((b) => b.x));
  const y = Math.min(...boxes.map((b) => b.y));
  return { x, y, width: Math.max(...boxes.map((b) => b.x + b.width)) - x, height: Math.max(...boxes.map((b) => b.y + b.height)) - y };
}

/**
 * The viewport that shows `target` (canvas units) centred in `clear` (screen pixels) with
 * `margin` around it, never magnified past `maxZoom`. A small clear part gets a smaller margin.
 */
export function fitViewport(target: Box, clear: Box, margin: number, maxZoom: number): Viewport {
  const room = Math.min(margin, clear.width / 6, clear.height / 6);
  const zoom = Math.min(
    MAX_ZOOM,
    Math.max(MIN_ZOOM, Math.min(maxZoom, (clear.width - 2 * room) / Math.max(target.width, 1), (clear.height - 2 * room) / Math.max(target.height, 1))),
  );
  return {
    x: clear.x + (clear.width - target.width * zoom) / 2 - target.x * zoom,
    y: clear.y + (clear.height - target.height * zoom) / 2 - target.y * zoom,
    zoom,
  };
}

/** The element and the elements joined to it by a want, in either direction. */
export function joinedTo(scene: RenderScene, address: Address): Address[] {
  const found = new Set<Address>([address]);
  for (const edge of scene.edges) {
    if (edge.from === address) found.add(edge.to);
    if (edge.to === address) found.add(edge.from);
  }
  return [...found];
}

/** The element and everything reached from it along its wants: what it relies on, directly or through others. */
export function branchOf(scene: RenderScene, address: Address): Address[] {
  const wanted = new Map<Address, Address[]>();
  for (const edge of scene.edges) wanted.set(edge.from, [...(wanted.get(edge.from) ?? []), edge.to]);
  const found = new Set<Address>([address]);
  const queue = [address];
  for (let at = queue.shift(); at !== undefined; at = queue.shift()) {
    for (const next of wanted.get(at) ?? []) {
      if (found.has(next)) continue;
      found.add(next);
      queue.push(next);
    }
  }
  return [...found];
}
