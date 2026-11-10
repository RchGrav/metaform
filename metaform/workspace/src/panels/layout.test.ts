import { describe, expect, it } from "vitest";
import {
  DEFAULT_FLOATING, LAYOUT_VERSION, MIN_FLOATING, TEXT_SIZE, ZONE_LIMITS,
  closePanel, defaultLayout, dockPanel, fitFloating, floatPanel, movePanel, narrowLayout, openPanel,
  placeFloating, placeOf, resizeZone, restoreLayout, setTextSize, type PanelSeed,
} from "./layout";
import { LAYOUT_KEY, loadLayout, parseLayout, saveLayout, type LayoutStorage } from "./storage";

const SEEDS: PanelSeed[] = [
  { id: "entity", zone: "right", open: true },
  { id: "legend", zone: "right", open: false },
  { id: "outline", zone: "left", open: false },
  { id: "activity", zone: "bottom", open: false },
];
const AREA = { width: 1000, height: 600 };

/** A storage that holds its values in memory, or refuses every call. */
function memory(initial?: string, broken = false): LayoutStorage & { value: string | null } {
  const store = {
    value: initial ?? null,
    getItem: () => {
      if (broken) throw new Error("blocked");
      return store.value;
    },
    setItem: (_key: string, value: string) => {
      if (broken) throw new Error("blocked");
      store.value = value;
    },
  };
  return store;
}

describe("the default layout", () => {
  it("opens only the panels that are open at first, in their zones, at the default sizes", () => {
    const layout = defaultLayout(SEEDS);
    expect(layout.version).toBe(2);
    expect(layout.zones.right).toEqual({ panels: ["entity"], active: "entity", size: 400 });
    expect(layout.zones.left).toEqual({ panels: [], active: null, size: 300 });
    expect(layout.zones.bottom).toEqual({ panels: [], active: null, size: 220 });
    expect(layout.floating).toEqual([]);
    expect(layout.text).toEqual({ workspace: 14, panels: 14 });
  });
});

describe("open and close", () => {
  it("opens a closed panel in its home zone and shows it", () => {
    const layout = openPanel(defaultLayout(SEEDS), "legend");
    expect(layout.zones.right.panels).toEqual(["entity", "legend"]);
    expect(layout.zones.right.active).toBe("legend");
    expect(placeOf(layout, "legend")).toBe("right");
  });

  it("makes an open panel the active tab, and returns the same layout when it already is", () => {
    const two = openPanel(defaultLayout(SEEDS), "legend");
    const back = openPanel(two, "entity");
    expect(back.zones.right.active).toBe("entity");
    expect(openPanel(back, "entity")).toBe(back);
  });

  it("closes a panel and shows the neighbouring tab", () => {
    const two = openPanel(defaultLayout(SEEDS), "legend");
    const closed = closePanel(two, "legend");
    expect(closed.zones.right).toEqual({ panels: ["entity"], active: "entity", size: 400 });
    expect(placeOf(closed, "legend")).toBeNull();
    const empty = closePanel(closed, "entity");
    expect(empty.zones.right.panels).toEqual([]);
    expect(empty.zones.right.active).toBeNull();
  });

  it("ignores a panel that is not registered", () => {
    const layout = defaultLayout(SEEDS);
    expect(openPanel(layout, "nothing")).toBe(layout);
    expect(closePanel(layout, "nothing")).toBe(layout);
    expect(movePanel(layout, "nothing", "left")).toBe(layout);
    expect(floatPanel(layout, "nothing", AREA)).toBe(layout);
  });
});

describe("move", () => {
  it("moves a panel to another zone, which becomes its home", () => {
    const moved = movePanel(defaultLayout(SEEDS), "entity", "left");
    expect(moved.zones.right.panels).toEqual([]);
    expect(moved.zones.left).toEqual({ panels: ["entity"], active: "entity", size: 300 });
    expect(moved.home.entity).toBe("left");
    // Closed and opened again, it returns to the zone the user chose.
    expect(placeOf(openPanel(closePanel(moved, "entity"), "entity"), "entity")).toBe("left");
  });

  it("opens a closed panel in the zone it is moved to", () => {
    const moved = movePanel(defaultLayout(SEEDS), "activity", "right");
    expect(moved.zones.right.panels).toEqual(["entity", "activity"]);
    expect(moved.zones.bottom.panels).toEqual([]);
  });
});

describe("float and dock", () => {
  it("floats a panel at the default size, inside the graph area", () => {
    const layout = floatPanel(defaultLayout(SEEDS), "entity", AREA);
    expect(placeOf(layout, "entity")).toBe("floating");
    expect(layout.zones.right.panels).toEqual([]);
    const panel = layout.floating[0]!;
    expect(panel.width).toBe(DEFAULT_FLOATING.width);
    expect(panel.height).toBe(DEFAULT_FLOATING.height);
    expect(panel.x).toBeGreaterThanOrEqual(0);
    expect(panel.y).toBeGreaterThanOrEqual(0);
    expect(panel.x + panel.width).toBeLessThanOrEqual(AREA.width);
    expect(panel.y + panel.height).toBeLessThanOrEqual(AREA.height);
  });

  it("places a second floating panel away from the first, and keeps both inside a small area", () => {
    const one = floatPanel(defaultLayout(SEEDS), "entity", AREA);
    const two = floatPanel(one, "legend", AREA);
    expect(two.floating.map((p) => p.id)).toEqual(["entity", "legend"]);
    expect(two.floating[1]!.y).toBeGreaterThan(two.floating[0]!.y);
    const small = floatPanel(defaultLayout(SEEDS), "entity", { width: 300, height: 200 }).floating[0]!;
    expect(small).toEqual({ id: "entity", x: 0, y: 0, width: 300, height: 200 });
  });

  it("brings a floating panel to the top when it is opened", () => {
    const two = floatPanel(floatPanel(defaultLayout(SEEDS), "entity", AREA), "legend", AREA);
    const raised = openPanel(two, "entity");
    expect(raised.floating.map((p) => p.id)).toEqual(["legend", "entity"]);
    expect(openPanel(raised, "entity")).toBe(raised);
  });

  it("docks a floating panel in its home zone", () => {
    const floating = floatPanel(defaultLayout(SEEDS), "entity", AREA);
    const docked = dockPanel(floating, "entity");
    expect(docked.floating).toEqual([]);
    expect(docked.zones.right).toEqual({ panels: ["entity"], active: "entity", size: 400 });
    expect(dockPanel(docked, "entity")).toBe(docked);
  });

  it("moves and resizes a floating panel, and never makes it smaller than the smallest size", () => {
    const floating = floatPanel(defaultLayout(SEEDS), "entity", AREA);
    const moved = placeFloating(floating, "entity", { x: 40, y: 50 });
    expect(moved.floating[0]).toMatchObject({ x: 40, y: 50, width: 420, height: 360 });
    const sized = placeFloating(moved, "entity", { width: 10, height: 500 });
    expect(sized.floating[0]).toMatchObject({ x: 40, y: 50, width: MIN_FLOATING.width, height: 500 });
    expect(placeFloating(sized, "entity", { x: 40 })).toBe(sized);
    expect(placeFloating(sized, "legend", { x: 1 })).toBe(sized);
  });

  it("draws a floating panel inside the graph area without adjusting the saved rectangle", () => {
    const panel = { id: "entity", x: 900, y: -20, width: 420, height: 900 };
    expect(fitFloating(panel, AREA)).toEqual({ id: "entity", x: 580, y: 0, width: 420, height: 600 });
    expect(panel.x).toBe(900);
  });
});

describe("resize", () => {
  it("sets a zone's size within its limits", () => {
    const layout = defaultLayout(SEEDS);
    expect(resizeZone(layout, "left", 350.4).zones.left.size).toBe(350);
    expect(resizeZone(layout, "left", 5).zones.left.size).toBe(ZONE_LIMITS.left.min);
    expect(resizeZone(layout, "bottom", 5000).zones.bottom.size).toBe(ZONE_LIMITS.bottom.max);
    expect(resizeZone(layout, "right", 400)).toBe(layout);
  });

  it("sets each text size within the limits", () => {
    const layout = setTextSize(defaultLayout(SEEDS), "panels", 16);
    expect(layout.text).toEqual({ workspace: 14, panels: 16 });
    expect(setTextSize(layout, "workspace", 99).text.workspace).toBe(TEXT_SIZE.max);
    expect(setTextSize(layout, "workspace", 1).text.workspace).toBe(TEXT_SIZE.min);
  });
});

describe("restore", () => {
  it("returns to the default panels and sizes, and keeps the text sizes", () => {
    let layout = defaultLayout(SEEDS);
    layout = movePanel(layout, "entity", "left");
    layout = floatPanel(layout, "legend", AREA);
    layout = resizeZone(layout, "bottom", 400);
    layout = setTextSize(layout, "panels", 18);
    const restored = restoreLayout(layout, SEEDS);
    expect(restored).toEqual({ ...defaultLayout(SEEDS), text: { workspace: 14, panels: 18 } });
  });
});

describe("a narrow window", () => {
  it("shows every open panel in one zone under the graph, and docks the floating panels", () => {
    let layout = openPanel(defaultLayout(SEEDS), "outline");
    layout = openPanel(layout, "activity");
    layout = floatPanel(layout, "legend", AREA);
    const narrow = narrowLayout(layout, null);
    expect(narrow.zones.left.panels).toEqual([]);
    expect(narrow.zones.right.panels).toEqual([]);
    expect(narrow.floating).toEqual([]);
    expect(narrow.zones.bottom.panels).toEqual(["activity", "outline", "entity", "legend"]);
    expect(narrow.zones.bottom.active).toBe("activity");
    expect(narrowLayout(layout, "legend").zones.bottom.active).toBe("legend");
    expect(narrowLayout(layout, "closed-panel").zones.bottom.active).toBe("activity");
    // The layout itself is unchanged, so a wide window shows it as before.
    expect(placeOf(layout, "legend")).toBe("floating");
  });
});

describe("the saved layout", () => {
  it("is one JSON object with a version, and reads back as it was written", () => {
    let layout = movePanel(defaultLayout(SEEDS), "entity", "left");
    layout = floatPanel(layout, "legend", AREA);
    layout = resizeZone(layout, "bottom", 300);
    layout = setTextSize(layout, "workspace", 16);
    const storage = memory();
    expect(saveLayout(storage, layout)).toBe(true);
    expect(JSON.parse(storage.value ?? "").version).toBe(LAYOUT_VERSION);
    expect(loadLayout(storage, SEEDS)).toEqual(layout);
  });

  it("drops a panel that no longer exists and keeps the rest", () => {
    const saved = {
      version: 2,
      zones: {
        left: { panels: ["removed", "outline"], active: "removed", size: 320 },
        right: { panels: ["entity", "entity"], active: "entity", size: 410 },
        bottom: { panels: [], active: null, size: 200 },
      },
      floating: [{ id: "gone", x: 1, y: 2, width: 300, height: 300 }, { id: "legend", x: 10, y: 20, width: 300, height: 200 }],
      home: { removed: "left", entity: "bottom", legend: "nowhere" },
      text: { workspace: 15, panels: 13 },
    };
    const layout = parseLayout(JSON.stringify(saved), SEEDS)!;
    expect(layout.zones.left).toEqual({ panels: ["outline"], active: "outline", size: 320 });
    expect(layout.zones.right).toEqual({ panels: ["entity"], active: "entity", size: 410 });
    expect(layout.floating).toEqual([{ id: "legend", x: 10, y: 20, width: 300, height: 200 }]);
    expect(layout.home).toEqual({ entity: "bottom", legend: "right", outline: "left", activity: "bottom" });
    expect(layout.text).toEqual({ workspace: 15, panels: 13 });
    // A registered panel the saved value does not name stays closed and can be opened.
    expect(placeOf(layout, "activity")).toBeNull();
    expect(placeOf(openPanel(layout, "activity"), "activity")).toBe("bottom");
  });

  it("keeps sizes within the limits when the saved numbers are out of range or not numbers", () => {
    const saved = {
      version: 2,
      zones: {
        left: { panels: [], active: null, size: 99999 },
        right: { panels: [], active: null, size: "wide" },
        bottom: { panels: [], active: null, size: -5 },
      },
      floating: [{ id: "entity", x: null, y: 5, width: 1, height: 1 }],
      text: { workspace: 400, panels: "big" },
    };
    const layout = parseLayout(JSON.stringify(saved), SEEDS)!;
    expect(layout.zones.left.size).toBe(ZONE_LIMITS.left.max);
    expect(layout.zones.right.size).toBe(400);
    expect(layout.zones.bottom.size).toBe(ZONE_LIMITS.bottom.min);
    expect(layout.floating[0]).toEqual({ id: "entity", x: 0, y: 5, width: MIN_FLOATING.width, height: MIN_FLOATING.height });
    expect(layout.text).toEqual({ workspace: TEXT_SIZE.max, panels: TEXT_SIZE.initial });
  });

  it("ignores a value with another version, a value that does not parse, and a value with the wrong shape", () => {
    const good = JSON.stringify(defaultLayout(SEEDS));
    expect(parseLayout(good, SEEDS)).not.toBeNull();
    expect(parseLayout(good.replace('"version":2', '"version":3'), SEEDS)).toBeNull();
    expect(parseLayout("{not json", SEEDS)).toBeNull();
    expect(parseLayout("null", SEEDS)).toBeNull();
    expect(parseLayout("[1]", SEEDS)).toBeNull();
    expect(parseLayout('{"version":1}', SEEDS)).toBeNull();
    expect(parseLayout('{"version":1,"zones":{"left":{}},"floating":[]}', SEEDS)).toBeNull();
    for (const text of ["{not json", '{"version":2}']) {
      expect(loadLayout(memory(text), SEEDS)).toEqual(defaultLayout(SEEDS));
    }
  });

  it("uses the default layout when the storage is empty, missing or blocked", () => {
    expect(loadLayout(memory(), SEEDS)).toEqual(defaultLayout(SEEDS));
    expect(loadLayout(null, SEEDS)).toEqual(defaultLayout(SEEDS));
    expect(loadLayout(memory(undefined, true), SEEDS)).toEqual(defaultLayout(SEEDS));
    expect(saveLayout(memory(undefined, true), defaultLayout(SEEDS))).toBe(false);
    expect(saveLayout(null, defaultLayout(SEEDS))).toBe(false);
    expect(LAYOUT_KEY).toBe("metaform-workspace-layout");
  });
});
