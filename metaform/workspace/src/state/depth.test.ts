import { describe, expect, it } from "vitest";
import type { ShallowGraph } from "../source";
import {
  applyDepth, chosenDepth, defaultDepth, hiddenCounts, initialDepth, levelsOf, maxDepth, shownDepth, visibleSet,
  type DepthRecord,
} from "./depth";
import { categoriesOf, categoryOf, functionalLevels, functionalScene, type SceneInput } from "./scene";
import { canUndoDepth, currentView, initialState, reduce, type Action, type ViewState } from "./view";

// a relies on b and c; b relies on d; c relies on d; d relies on e. f stands alone.
const addresses = ["a", "b", "c", "d", "e", "f"];
const wants: [string, string][] = [["a", "b"], ["a", "c"], ["b", "d"], ["c", "d"], ["d", "e"]];
const levels = levelsOf(addresses, wants);
const shown = (record: DepthRecord | null) => [...visibleSet(levels, record?.now ?? initialDepth())].sort();

describe("levels", () => {
  it("counts levels along the wants from the elements that nothing relies on", () => {
    expect(Object.fromEntries(levels.level)).toEqual({ a: 0, f: 0, b: 1, c: 1, d: 2, e: 3 });
    expect(levels.deepest).toBe(3);
  });

  it("hangs each element from the element that reached it first", () => {
    expect(levels.parent.get("a")).toBeNull();
    expect(levels.parent.get("d")).toBe("b");
    expect(levels.children.get("a")).toEqual(["b", "c"]);
    expect(levels.children.get("c")).toBeUndefined();
  });

  it("takes the first level that draws a want as depth 1", () => {
    expect(levels.first).toBe(1);
    expect(maxDepth(levels)).toBe(3);
    expect(levelsOf(["x", "y"], []).first).toBe(0);
  });

  it("gives a level to elements that only a cycle reaches, and ignores wants to unknown elements", () => {
    const cycle = levelsOf(["p", "q", "r"], [["p", "q"], ["q", "p"], ["r", "gone"], ["r", "r"]]);
    expect(Object.fromEntries(cycle.level)).toEqual({ r: 0, p: 0, q: 1 });
  });

  it("shows a map of up to 200 elements whole, and a larger one at depth 2", () => {
    expect(defaultDepth(levels)).toBe(3);
    const many = Array.from({ length: 201 }, (_, i) => `n${String(i).padStart(3, "0")}`);
    const chain = levelsOf(many, many.slice(1).map((to, i) => [many[i]!, to] as const));
    expect(maxDepth(chain)).toBe(200);
    expect(defaultDepth(chain)).toBe(2);
    expect(visibleSet(chain, initialDepth()).size).toBe(3);
  });
});

describe("visible sets and counts", () => {
  it("shows N levels from the first level that draws a want", () => {
    expect(shown(applyDepth(null, { type: "depth-set", levels, depth: 1 }))).toEqual(["a", "b", "c", "f"]);
    expect(shown(applyDepth(null, { type: "depth-set", levels, depth: 2 }))).toEqual(["a", "b", "c", "d", "f"]);
    expect(shown(null)).toEqual(addresses);
  });

  it("counts the hidden elements on the visible element that holds them", () => {
    const one = applyDepth(null, { type: "depth-collapse-all", levels });
    const visible = visibleSet(levels, one.now);
    expect([...hiddenCounts(levels, visible)]).toEqual([["b", 2]]);
    expect([...hiddenCounts(levels, visible, (address) => address !== "e")]).toEqual([["b", 1]]);
    expect(shownDepth(levels, visible)).toBe(1);
  });

  it("opens one element to its next level, and closes it again", () => {
    const one = applyDepth(null, { type: "depth-collapse-all", levels });
    const opened = applyDepth(one, { type: "depth-toggle", levels, address: "b" });
    expect(shown(opened)).toEqual(["a", "b", "c", "d", "f"]);
    expect([...hiddenCounts(levels, visibleSet(levels, opened.now))]).toEqual([["d", 1]]);
    expect(shown(applyDepth(opened, { type: "depth-toggle", levels, address: "b" }))).toEqual(["a", "b", "c", "f"]);
    // An element within the depth can be closed, and what hangs from it goes with it.
    const closed = applyDepth(null, { type: "depth-toggle", levels, address: "a" });
    expect(shown(closed)).toEqual(["a", "f"]);
    // An element that holds nothing does not change the state.
    expect(applyDepth(one, { type: "depth-toggle", levels, address: "c" })).toBe(one);
  });

  it("expands and collapses one level, with and without single openings", () => {
    const one = applyDepth(null, { type: "depth-collapse-all", levels });
    const two = applyDepth(one, { type: "depth-expand-level", levels });
    expect(chosenDepth(levels, two.now)).toBe(2);
    expect(shown(applyDepth(two, { type: "depth-collapse-level", levels }))).toEqual(["a", "b", "c", "f"]);
    const opened = applyDepth(one, { type: "depth-toggle", levels, address: "b" });
    expect(shown(applyDepth(opened, { type: "depth-expand-level", levels }))).toEqual(addresses);
    expect(shown(applyDepth(opened, { type: "depth-collapse-level", levels }))).toEqual(["a", "b", "c", "f"]);
    // The first level that draws a want always stays.
    expect(applyDepth(one, { type: "depth-collapse-level", levels })).toBe(one);
  });
});

describe("undo", () => {
  it("restores the visible set before each depth action, one step at a time", () => {
    const actions = [
      { type: "depth-collapse-all", levels },
      { type: "depth-toggle", levels, address: "b" },
      { type: "depth-expand-level", levels },
      { type: "depth-set", levels, depth: 2 },
      { type: "depth-collapse-level", levels },
      { type: "depth-expand-all", levels },
    ] as const;
    const seen: string[][] = [shown(null)];
    let record: DepthRecord | null = null;
    for (const action of actions) {
      record = applyDepth(record, action);
      seen.push(shown(record));
    }
    for (let i = actions.length - 1; i >= 0; i--) {
      record = applyDepth(record, { type: "depth-undo" });
      expect(shown(record)).toEqual(seen[i]);
    }
    expect(record?.undo).toEqual([]);
    expect(applyDepth(record, { type: "depth-undo" })).toBe(record);
  });

  it("keeps at least 20 steps, and does not record an action that shows the same elements", () => {
    let record: DepthRecord | null = null;
    for (let i = 0; i < 30; i++) record = applyDepth(record, { type: "depth-set", levels, depth: (i % 2) + 1 });
    expect(record?.undo.length).toBe(30);
    const again = applyDepth(record, { type: "depth-set", levels, depth: chosenDepth(levels, record!.now) });
    expect(again).toBe(record);
    for (let i = 0; i < 80; i++) record = applyDepth(record, { type: "depth-set", levels, depth: (i % 2) + 1 });
    expect(record?.undo.length).toBeGreaterThanOrEqual(20);
  });
});

const graph: ShallowGraph = {
  addresses: ["downstream", "downstream.user", "code", "code.app", "code.app.core", "code.store", "data", "data.table", "upstream", "upstream.db"],
  edges: [
    ["downstream.user", "code.app"], ["code.app", "code.app.core"], ["code.app.core", "code.store"],
    ["code.store", "data.table"], ["code.store", "upstream.db"],
  ],
  definitive: "code.app",
};
const input: SceneInput = {
  graph,
  fields: new Map(graph.addresses.filter((a) => a.includes(".")).map((a) => [a, { name: a.slice(a.lastIndexOf(".") + 1) }])),
  layerCounts: new Map(),
  layers: [],
  agents: [],
  opensProject: () => false,
};
const run = (actions: Action[]): ViewState => [{ type: "open-project", project: "p" } as Action, ...actions].reduce(reduce, initialState());
const drawn = (state: ViewState) => functionalScene(state, input).nodes.map((n) => n.address);

describe("depth in the functional scene", () => {
  it("draws the visible set, and a collapsed element with the count of what it holds", () => {
    const start = run([]);
    const sceneLevels = functionalLevels(start, input);
    expect(functionalLevels(start, input)).toBe(sceneLevels);
    expect(drawn(start)).toHaveLength(6);
    const one = reduce(start, { type: "depth-collapse-all", levels: sceneLevels });
    const scene = functionalScene(one, input);
    expect(scene.nodes.map((n) => n.address)).toEqual(["code.app", "downstream.user"]);
    expect(scene.edges.map((e) => e.id)).toEqual(["downstream.user->code.app"]);
    const app = scene.nodes.find((n) => n.address === "code.app");
    expect([app?.beneath, app?.collapsed]).toEqual([4, true]);
    // An element whose next level shows can be closed: it has a count and is not collapsed.
    const user = scene.nodes.find((n) => n.address === "downstream.user");
    expect([user?.beneath, user?.collapsed]).toEqual([1, false]);
  });

  it("undoes a depth action through the reducer, and leaves the selection alone", () => {
    const start = run([{ type: "select", address: "code.store" }]);
    const sceneLevels = functionalLevels(start, input);
    const one = reduce(start, { type: "depth-collapse-all", levels: sceneLevels });
    expect(canUndoDepth(start)).toBe(false);
    expect(canUndoDepth(one)).toBe(true);
    expect(currentView(one).selection).toBe("code.store");
    const back = reduce(one, { type: "depth-undo" });
    expect(drawn(back)).toEqual(drawn(start));
    expect(canUndoDepth(back)).toBe(false);
    // Undo covers depth actions only: a category action is not undone.
    const hidden = reduce(one, { type: "category-toggle", category: "code" });
    expect(reduce(hidden, { type: "depth-undo" }).categories).toEqual({ code: "hidden" });
  });
});

describe("categories", () => {
  it("names an element's category by the first segment of its address", () => {
    expect(categoryOf("code.app.core")).toBe("code");
    expect(categoriesOf(["upstream.db", "code.app", "code.store", "zeta.x", "downstream.user"])).toEqual([
      { category: "downstream", elements: 1 }, { category: "code", elements: 2 },
      { category: "upstream", elements: 1 }, { category: "zeta", elements: 1 },
    ]);
  });

  it("does not draw a hidden category's elements or their lines", () => {
    const scene = functionalScene(run([{ type: "category-toggle", category: "upstream" }]), input);
    expect(scene.nodes.some((n) => n.address === "upstream.db")).toBe(false);
    expect(scene.edges.some((e) => e.to === "upstream.db")).toBe(false);
    expect(scene.nodes).toHaveLength(5);
    expect(drawn(run([{ type: "category-toggle", category: "upstream" }, { type: "category-toggle", category: "upstream" }]))).toHaveLength(6);
  });

  it("quiets the other categories while one is isolated, without removing them", () => {
    const state = run([{ type: "category-toggle", category: "data" }, { type: "category-isolate", category: "code" }]);
    const scene = functionalScene(state, input);
    expect(scene.nodes).toHaveLength(5);
    expect(scene.nodes.filter((n) => !n.dimmed).map((n) => n.address)).toEqual(["code.app", "code.app.core", "code.store"]);
    expect(scene.scope).toEqual(["code.app", "code.app.core", "code.store"]);
    // Isolating does not alter which categories are shown or hidden.
    expect(state.categories).toEqual({ data: "hidden" });
    expect(reduce(state, { type: "category-isolate", category: null }).categories).toEqual({ data: "hidden" });
  });

  it("shows all, hides all, and restores", () => {
    const all = ["downstream", "code", "data", "upstream"];
    const none = run([{ type: "categories-hide-all", categories: all }]);
    expect(drawn(none)).toEqual([]);
    expect(drawn(reduce(none, { type: "categories-show-all" }))).toHaveLength(6);
    const isolated = run([{ type: "category-toggle", category: "data" }, { type: "category-isolate", category: "code" }]);
    expect(reduce(isolated, { type: "categories-show-all" }).isolatedCategory).toBe("code");
    const restored = reduce(isolated, { type: "categories-restore" });
    expect([restored.categories, restored.isolatedCategory]).toEqual([{}, null]);
    expect(functionalScene(restored, input).nodes.every((n) => !n.dimmed)).toBe(true);
  });
});
