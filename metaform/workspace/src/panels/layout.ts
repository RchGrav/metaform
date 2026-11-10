// The layout of the panels: which panels are open, the zone each one is in, the size of each zone,
// the floating panels, and the two text sizes. Every function here is pure and returns a new
// layout, or the same object when nothing differs. Reading and writing the saved value is in
// storage.ts.

/** A zone beside the graph that holds a stack of panels. */
export type Zone = "left" | "right" | "bottom";

/** The zones, in the order the page lists them. */
export const ZONES: readonly Zone[] = ["left", "right", "bottom"];

/** The version of the saved value. A saved value with another version is ignored. */
export const LAYOUT_VERSION = 2;

/** What the layout needs to know about a registered panel: its id, its default zone, and whether it is open at first. */
export interface PanelSeed {
  id: string;
  zone: Zone;
  open: boolean;
}

/** One zone: its open panels in tab order, the panel whose body shows, and its size in pixels. */
export interface ZoneState {
  panels: string[];
  active: string | null;
  /** The width of the left and right zones; the height of the bottom zone. */
  size: number;
}

/** A panel that floats over the graph. `x` and `y` are measured from the top left corner of the graph area. */
export interface FloatingPanel {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

/** The two text sizes the user can set, in pixels. */
export interface TextSize {
  workspace: number;
  panels: number;
}

/** The whole layout. This object, as JSON, is the saved value. */
export interface Layout {
  version: typeof LAYOUT_VERSION;
  zones: Record<Zone, ZoneState>;
  /** The floating panels, in drawing order: the last one is on top. */
  floating: FloatingPanel[];
  /** For each registered panel, the zone it opens in and docks in. */
  home: Record<string, Zone>;
  text: TextSize;
}

/** A width and a height in pixels, such as the size of the graph area. */
export interface Area {
  width: number;
  height: number;
}

/** The default size of each zone, in pixels. */
export const DEFAULT_ZONE_SIZE: Record<Zone, number> = { left: 300, right: 400, bottom: 220 };
/** The smallest and largest size of each zone, in pixels. */
export const ZONE_LIMITS: Record<Zone, { min: number; max: number }> = {
  left: { min: 180, max: 720 },
  right: { min: 180, max: 720 },
  bottom: { min: 100, max: 560 },
};
/** The size a panel has when it first floats, in pixels. */
export const DEFAULT_FLOATING: Area = { width: 420, height: 360 };
/** The smallest size of a floating panel, in pixels. */
export const MIN_FLOATING: Area = { width: 240, height: 160 };
/** The default, smallest and largest text size, in pixels. */
export const TEXT_SIZE = { initial: 14, min: 11, max: 20 } as const;

/** The distance kept between a new floating panel and the edge of the graph area, and between two new floating panels. */
const FLOAT_MARGIN = 16;
const FLOAT_STEP = 24;

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/** The layout a new browser starts with: each panel that is open at first, in its default zone. */
export function defaultLayout(seeds: readonly PanelSeed[], text?: TextSize): Layout {
  const zones = Object.fromEntries(
    ZONES.map((zone) => {
      const panels = seeds.filter((seed) => seed.open && seed.zone === zone).map((seed) => seed.id);
      return [zone, { panels, active: panels[0] ?? null, size: DEFAULT_ZONE_SIZE[zone] }];
    }),
  ) as Record<Zone, ZoneState>;
  return {
    version: LAYOUT_VERSION,
    zones,
    floating: [],
    home: Object.fromEntries(seeds.map((seed) => [seed.id, seed.zone])),
    text: text ?? { workspace: TEXT_SIZE.initial, panels: TEXT_SIZE.initial },
  };
}

/** Where a panel is: a zone, "floating", or null when the panel is closed. */
export function placeOf(layout: Layout, id: string): Zone | "floating" | null {
  if (layout.floating.some((panel) => panel.id === id)) return "floating";
  return ZONES.find((zone) => layout.zones[zone].panels.includes(id)) ?? null;
}

/** The layout with the panel in no zone and not floating. A zone that loses its active panel shows the next one. */
function without(layout: Layout, id: string): Layout {
  const zones = { ...layout.zones };
  for (const zone of ZONES) {
    const state = zones[zone];
    const index = state.panels.indexOf(id);
    if (index < 0) continue;
    const panels = state.panels.filter((panel) => panel !== id);
    const active = state.active === id ? panels[index] ?? panels[index - 1] ?? null : state.active;
    zones[zone] = { ...state, panels, active };
  }
  return { ...layout, zones, floating: layout.floating.filter((panel) => panel.id !== id) };
}

/** The layout with the panel added to the end of a zone's tabs and shown there. */
function addTo(layout: Layout, id: string, zone: Zone): Layout {
  const state = layout.zones[zone];
  return { ...layout, zones: { ...layout.zones, [zone]: { ...state, panels: [...state.panels, id], active: id } } };
}

/**
 * Shows a panel. A closed panel opens in its home zone. A panel in a zone becomes the zone's
 * active tab. A floating panel comes to the top. A panel that is not registered is ignored.
 */
export function openPanel(layout: Layout, id: string): Layout {
  const place = placeOf(layout, id);
  if (place === "floating") {
    const panel = layout.floating.find((p) => p.id === id);
    if (!panel || layout.floating[layout.floating.length - 1] === panel) return layout;
    return { ...layout, floating: [...layout.floating.filter((p) => p.id !== id), panel] };
  }
  if (place !== null) {
    if (layout.zones[place].active === id) return layout;
    return { ...layout, zones: { ...layout.zones, [place]: { ...layout.zones[place], active: id } } };
  }
  const home = layout.home[id];
  return home === undefined ? layout : addTo(layout, id, home);
}

/** Closes a panel. The panel keeps its home zone, so it opens there again. */
export function closePanel(layout: Layout, id: string): Layout {
  return placeOf(layout, id) === null ? layout : without(layout, id);
}

/** Moves a panel to a zone, from another zone, from floating or from closed. That zone becomes its home. */
export function movePanel(layout: Layout, id: string, zone: Zone): Layout {
  if (layout.home[id] === undefined) return layout;
  if (placeOf(layout, id) === zone) return openPanel(layout, id);
  const moved = addTo(without(layout, id), id, zone);
  return { ...moved, home: { ...moved.home, [id]: zone } };
}

/**
 * Floats a panel over the graph, at the default size, inside the graph area. Each further
 * floating panel is placed a step down and to the left of the one before, so no title is covered.
 */
export function floatPanel(layout: Layout, id: string, area: Area): Layout {
  if (layout.home[id] === undefined) return layout;
  if (placeOf(layout, id) === "floating") return openPanel(layout, id);
  const step = layout.floating.length * FLOAT_STEP;
  const panel = fitFloating(
    {
      id,
      x: area.width - DEFAULT_FLOATING.width - FLOAT_MARGIN - step,
      y: FLOAT_MARGIN + step,
      width: DEFAULT_FLOATING.width,
      height: DEFAULT_FLOATING.height,
    },
    area,
  );
  const rest = without(layout, id);
  return { ...rest, floating: [...rest.floating, panel] };
}

/** Docks a floating panel in its home zone. */
export function dockPanel(layout: Layout, id: string): Layout {
  const home = layout.home[id];
  if (placeOf(layout, id) !== "floating" || home === undefined) return layout;
  return addTo(without(layout, id), id, home);
}

/** Sets the size of a zone, kept within the zone's limits. */
export function resizeZone(layout: Layout, zone: Zone, size: number): Layout {
  const limits = ZONE_LIMITS[zone];
  const next = clamp(Math.round(size), limits.min, limits.max);
  if (next === layout.zones[zone].size) return layout;
  return { ...layout, zones: { ...layout.zones, [zone]: { ...layout.zones[zone], size: next } } };
}

/** Sets the position, the size or both of a floating panel. The size is never below the smallest size. */
export function placeFloating(layout: Layout, id: string, rect: Partial<Omit<FloatingPanel, "id">>): Layout {
  const index = layout.floating.findIndex((panel) => panel.id === id);
  const panel = layout.floating[index];
  if (!panel) return layout;
  const next: FloatingPanel = {
    id,
    x: Math.round(rect.x ?? panel.x),
    y: Math.round(rect.y ?? panel.y),
    width: Math.max(MIN_FLOATING.width, Math.round(rect.width ?? panel.width)),
    height: Math.max(MIN_FLOATING.height, Math.round(rect.height ?? panel.height)),
  };
  if (next.x === panel.x && next.y === panel.y && next.width === panel.width && next.height === panel.height) return layout;
  return { ...layout, floating: layout.floating.map((p, i) => (i === index ? next : p)) };
}

/**
 * A floating panel's rectangle as the page draws it: no larger than the graph area and wholly
 * inside it. The saved rectangle is not adjusted, so the panel returns to its place when the
 * window grows again.
 */
export function fitFloating(panel: FloatingPanel, area: Area): FloatingPanel {
  const width = Math.max(1, Math.min(panel.width, area.width));
  const height = Math.max(1, Math.min(panel.height, area.height));
  return {
    id: panel.id,
    width,
    height,
    x: clamp(panel.x, 0, Math.max(0, area.width - width)),
    y: clamp(panel.y, 0, Math.max(0, area.height - height)),
  };
}

/** Sets the workspace's text size or the panels' text size, kept within the limits. */
export function setTextSize(layout: Layout, which: keyof TextSize, size: number): Layout {
  const next = clamp(Math.round(size), TEXT_SIZE.min, TEXT_SIZE.max);
  if (next === layout.text[which]) return layout;
  return { ...layout, text: { ...layout.text, [which]: next } };
}

/**
 * The default layout again: the default panels, zones and sizes, and no floating panel. The two
 * text sizes are kept, because each has its own control.
 */
export function restoreLayout(layout: Layout, seeds: readonly PanelSeed[]): Layout {
  return defaultLayout(seeds, layout.text);
}

/**
 * The layout as a narrow window shows it: every open panel in one zone under the graph, and no
 * floating panel. The saved layout is not adjusted, so a wide window shows it again as it was.
 * `active` is the panel the user last chose in the narrow window, if it is still open.
 */
export function narrowLayout(layout: Layout, active: string | null): Layout {
  const panels = [
    ...layout.zones.bottom.panels,
    ...layout.zones.left.panels,
    ...layout.zones.right.panels,
    ...layout.floating.map((panel) => panel.id),
  ];
  const shown =
    active !== null && panels.includes(active)
      ? active
      : layout.zones.bottom.active ?? layout.zones.right.active ?? layout.zones.left.active ?? panels[0] ?? null;
  return {
    ...layout,
    zones: {
      left: { ...layout.zones.left, panels: [], active: null },
      right: { ...layout.zones.right, panels: [], active: null },
      bottom: { ...layout.zones.bottom, panels, active: shown },
    },
    floating: [],
  };
}
