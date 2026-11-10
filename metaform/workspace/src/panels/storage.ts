// The saved layout: one JSON object in localStorage, with a `version` number. A value that does
// not parse, has another version, or does not have the expected parts is ignored, and the page
// uses the default layout. A value that names a panel that is not registered loses only that panel.

import {
  LAYOUT_VERSION, MIN_FLOATING, TEXT_SIZE, ZONES, ZONE_LIMITS, defaultLayout,
  type FloatingPanel, type Layout, type PanelSeed, type Zone,
} from "./layout";

/** The localStorage key that holds the saved layout. */
export const LAYOUT_KEY = "metaform-workspace-layout";

/** The part of the browser's storage this module uses. A test gives its own. */
export type LayoutStorage = Pick<Storage, "getItem" | "setItem">;

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isZone(value: unknown): value is Zone {
  return ZONES.some((zone) => zone === value);
}

/** A finite number within the limits, or the fallback when the value is not a finite number. */
function numberIn(value: unknown, min: number, max: number, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? Math.min(max, Math.max(min, Math.round(value))) : fallback;
}

/**
 * Reads a saved value. Returns null when the text is not JSON, when its version is not the
 * current one, or when a part has the wrong shape. Panels that are not registered are left out.
 * A registered panel the value does not name stays closed, with its default zone as its home.
 */
export function parseLayout(text: string, seeds: readonly PanelSeed[]): Layout | null {
  let saved: unknown;
  try {
    saved = JSON.parse(text);
  } catch {
    return null;
  }
  if (!isObject(saved) || saved.version !== LAYOUT_VERSION) return null;
  if (!isObject(saved.zones) || !Array.isArray(saved.floating)) return null;

  const layout = defaultLayout(seeds);
  const known = new Set(seeds.map((seed) => seed.id));
  const placed = new Set<string>();

  for (const zone of ZONES) {
    const state = saved.zones[zone];
    if (!isObject(state) || !Array.isArray(state.panels)) return null;
    const panels: string[] = [];
    for (const id of state.panels) {
      if (typeof id !== "string" || !known.has(id) || placed.has(id)) continue;
      placed.add(id);
      panels.push(id);
    }
    const active = typeof state.active === "string" && panels.includes(state.active) ? state.active : panels[0] ?? null;
    const limits = ZONE_LIMITS[zone];
    layout.zones[zone] = { panels, active, size: numberIn(state.size, limits.min, limits.max, layout.zones[zone].size) };
  }

  const floating: FloatingPanel[] = [];
  for (const panel of saved.floating) {
    if (!isObject(panel) || typeof panel.id !== "string" || !known.has(panel.id) || placed.has(panel.id)) continue;
    placed.add(panel.id);
    floating.push({
      id: panel.id,
      x: numberIn(panel.x, -100_000, 100_000, 0),
      y: numberIn(panel.y, -100_000, 100_000, 0),
      width: numberIn(panel.width, MIN_FLOATING.width, 100_000, MIN_FLOATING.width),
      height: numberIn(panel.height, MIN_FLOATING.height, 100_000, MIN_FLOATING.height),
    });
  }
  layout.floating = floating;

  if (isObject(saved.home)) {
    for (const [id, zone] of Object.entries(saved.home)) {
      if (known.has(id) && isZone(zone)) layout.home[id] = zone;
    }
  }
  if (isObject(saved.text)) {
    layout.text = {
      workspace: numberIn(saved.text.workspace, TEXT_SIZE.min, TEXT_SIZE.max, TEXT_SIZE.initial),
      panels: numberIn(saved.text.panels, TEXT_SIZE.min, TEXT_SIZE.max, TEXT_SIZE.initial),
    };
  }
  return layout;
}

/** The saved layout, or the default layout when there is none, it cannot be read, or it is ignored. */
export function loadLayout(storage: LayoutStorage | null, seeds: readonly PanelSeed[]): Layout {
  try {
    const text = storage?.getItem(LAYOUT_KEY);
    return (typeof text === "string" ? parseLayout(text, seeds) : null) ?? defaultLayout(seeds);
  } catch {
    // Storage can be blocked. The page then works with the default layout.
    return defaultLayout(seeds);
  }
}

/** Saves the layout. Returns false when the browser refuses the write; the page still works. */
export function saveLayout(storage: LayoutStorage | null, layout: Layout): boolean {
  try {
    if (!storage) return false;
    storage.setItem(LAYOUT_KEY, JSON.stringify(layout));
    return true;
  } catch {
    return false;
  }
}
