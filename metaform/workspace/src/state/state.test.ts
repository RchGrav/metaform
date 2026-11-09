import { describe, expect, it } from "vitest";
import type { ShallowGraph } from "../source";
import { buildScene, type SceneInput } from "./scene";
import { TOP, beneathCounts, layerCounts, layerNames, sceneEdges, visibleIn } from "./structure";
import { currentView, initialState, reduce, type Action, type ViewState } from "./view";

const graph: ShallowGraph = {
  addresses: [
    "code", "code.store", "code.store.memory", "code.store.cache", "code.server", "code.server.relay",
    "code.server-tools", "upstream", "upstream.ladybug", "layer", "layer.document", "layer.document.specification",
  ],
  edges: [
    ["code.server.relay", "code.store.memory"],
    ["code.server.relay", "code.store.cache"],
    ["code.server", "upstream.ladybug"],
    ["code.store.memory", "code.store.cache"],
  ],
  definitive: "code",
};

function run(actions: Action[], from: ViewState = initialState()): ViewState {
  return actions.reduce(reduce, from);
}

function input(overrides: Partial<SceneInput> = {}): SceneInput {
  return {
    graph,
    fields: new Map([["code", { role: "Definitive" }]]),
    layerCounts: new Map([["code.store", new Map([["specification", 2]])]]),
    layers: ["memory", "specification"],
    agents: [{ id: "ida", name: "Ida", at: "code.store.memory", active: true }],
    opensProject: (address) => address === "upstream.ladybug",
    ...overrides,
  };
}

describe("structure", () => {
  it("shows direct children and hides what lies beneath a collapsed element", () => {
    const visible = visibleIn(graph.addresses, "code", new Set());
    expect([...visible].sort()).toEqual(["code.server", "code.server-tools", "code.store"]);
    const opened = visibleIn(graph.addresses, "code", new Set(["code.store"]));
    expect(opened.has("code.store.memory")).toBe(true);
  });

  it("draws wants to collapsed elements as one arrow with a count, and counts wants that leave", () => {
    const visible = visibleIn(graph.addresses, "code", new Set());
    const { edges, outside } = sceneEdges(graph, visible);
    expect(edges).toEqual([{ from: "code.server", to: "code.store", count: 2 }]);
    expect(outside.get("code.server")).toBe(1);
  });

  it("drops a want whose two ends meet at one collapsed element", () => {
    const visible = visibleIn(graph.addresses, TOP, new Set());
    const { edges } = sceneEdges(graph, visible);
    expect(edges.find((e) => e.from === "code" && e.to === "code")).toBeUndefined();
    expect(edges).toEqual([{ from: "code", to: "upstream", count: 1 }]);
  });

  it("counts every address beneath an element", () => {
    expect(beneathCounts(graph.addresses).get("code")).toBe(6);
  });

  it("reads layer names and record counts from the raw dump", () => {
    const dump = {
      ".": {
        code: { store: { specification: [{ text: "a" }, { text: "b" }], memory: { memory: [{ fact: "x" }] } } },
        layer: { document: { specification: { instruction: "write prose" } }, system: { memory: { instruction: "facts" } } },
      },
    };
    const names = layerNames(dump);
    expect(names).toEqual(["memory", "specification"]);
    const counts = layerCounts(dump, names);
    expect(counts.get("code.store")?.get("specification")).toBe(2);
    expect(counts.get("code.store.memory")?.get("memory")).toBe(1);
  });
});

describe("view state", () => {
  const start = run([{ type: "open-project", project: "metaform" }]);

  it("opens an element with elements beneath, goes up one level, and goes back", () => {
    const opened = run([{ type: "open", address: "code", beneath: 6 }, { type: "open", address: "code.store", beneath: 2 }], start);
    expect(currentView(opened).container).toBe("code.store");
    const up = reduce(opened, { type: "up" });
    expect(currentView(up).container).toBe("code");
    expect(currentView(up).selection).toBe("code.store");
    const back = reduce(up, { type: "back" });
    expect(currentView(back).container).toBe("code.store");
    expect(back.gestureHintDone).toBe(true);
  });

  it("opens a leaf in Element mode", () => {
    const leaf = reduce(start, { type: "open", address: "code.server-tools", beneath: 0 });
    expect(leaf.mode).toBe("element");
    expect(currentView(leaf).selection).toBe("code.server-tools");
  });

  it("keeps project, container, selection and focus across mode switches", () => {
    const set = run([
      { type: "open", address: "code", beneath: 6 },
      { type: "set-focus", address: "code.server" },
      { type: "mode", mode: "present" },
      { type: "mode", mode: "graph" },
    ], start);
    expect(set.project).toBe("metaform");
    expect(currentView(set)).toMatchObject({ container: "code", selection: "code.server", focus: "code.server" });
  });

  it("restores each project's place and shows a return chip after a link", () => {
    const moved = run([
      { type: "open", address: "code", beneath: 6 },
      { type: "open-project", project: "ladybug", from: "link" },
    ], start);
    expect(moved.returnTo).toMatchObject({ project: "metaform", container: "code" });
    const back = reduce(moved, { type: "back" });
    expect(back.project).toBe("metaform");
    expect(currentView(back).container).toBe("code");
    expect(back.returnTo).toBeNull();
  });

  it("keeps the visible set while a layer is isolated and restores it after", () => {
    const hidden = run([{ type: "layer", layer: "memory", visibility: "hidden" }, { type: "isolate", layer: "specification" }], start);
    expect(hidden.isolated).toBe("specification");
    const left = reduce(hidden, { type: "isolate", layer: null });
    expect(left.layers.memory).toBe("hidden");
  });

  it("moves a vanished container to its nearest parent with a notice, on map-changed", () => {
    const deep = run([
      { type: "open", address: "code", beneath: 6 },
      { type: "open", address: "code.store", beneath: 2 },
      { type: "select", address: "code.store.cache" },
    ], start);
    const changed = reduce(deep, { type: "map-changed", project: "metaform", addresses: ["code", "code.server"] });
    expect(currentView(changed).container).toBe("code");
    expect(currentView(changed).selection).toBe("code");
    expect(changed.notice).toEqual({ kind: "moved", missing: "code.store", showing: "code" });
  });

  it("marks activity unseen without moving the selection, and clears it on select", () => {
    const busy = run([{ type: "select", address: "code" }, { type: "activity", project: "metaform", address: "code.store" }], start);
    expect(currentView(busy).selection).toBe("code");
    expect(currentView(busy).unseen).toEqual(["code.store"]);
    expect(currentView(reduce(busy, { type: "select", address: "code.store" })).unseen).toEqual([]);
  });
});

describe("scene", () => {
  const inCode = run([{ type: "open-project", project: "metaform" }, { type: "open", address: "code", beneath: 6 }]);

  it("sorts nodes, marks parents, layers, agents and unseen activity", () => {
    const state = run([
      { type: "toggle-expanded", address: "code.store" },
      { type: "activity", project: "metaform", address: "code.store.cache" },
    ], inCode);
    const scene = buildScene(state, input());
    const addresses = scene.nodes.map((n) => n.address);
    expect(addresses).toEqual([...addresses].sort());
    const memory = scene.nodes.find((n) => n.address === "code.store.memory");
    expect(memory).toMatchObject({ parent: "code.store", agents: [{ id: "ida", initials: "ID", active: true }] });
    const store = scene.nodes.find((n) => n.address === "code.store");
    expect(store).toMatchObject({ collapsed: false, beneath: 2, layers: [{ layer: "specification", records: 2, style: 1 }] });
    expect(scene.nodes.find((n) => n.address === "code.store.cache")?.unseen).toBe(true);
  });

  it("dims without removing on isolate, so nothing moves", () => {
    const before = buildScene(inCode, input());
    const after = buildScene(reduce(inCode, { type: "isolate", layer: "specification" }), input());
    expect(after.nodes.map((n) => n.address)).toEqual(before.nodes.map((n) => n.address));
    expect(after.nodes.find((n) => n.address === "code.server")?.dimmed).toBe(true);
    expect(after.nodes.find((n) => n.address === "code.store")?.dimmed).toBe(false);
  });

  it("puts the pivot on top and dims what lies beyond reach", () => {
    const state = reduce(inCode, { type: "set-focus", address: "code.server-tools" });
    const scene = buildScene(state, input());
    expect(scene.top).toBe("code.server-tools");
    expect(scene.nodes.find((n) => n.address === "code.store")?.dimmed).toBe(true);
  });
});
