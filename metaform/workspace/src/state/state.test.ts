import { describe, expect, it } from "vitest";
import type { ShallowGraph } from "../source";
import { buildScene, elementScene, type SceneInput } from "./scene";
import { TOP, beneathCounts, graphAddresses, layerCounts, layerNames, outsideAddress, sceneEdges, startBudget, startExpansion, visibleIn } from "./structure";
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
    expect(edges).toEqual([{ from: "code.server", to: "code.store", count: 2, members: [
      ["code.server.relay", "code.store.memory"], ["code.server.relay", "code.store.cache"],
    ] }]);
    expect(outside.get("code.server")).toBe(1);
  });

  it("drops a want whose two ends meet at one collapsed element", () => {
    const visible = visibleIn(graph.addresses, TOP, new Set());
    const { edges } = sceneEdges(graph, visible);
    expect(edges.find((e) => e.from === "code" && e.to === "code")).toBeUndefined();
    expect(edges).toEqual([{ from: "code", to: "upstream", count: 1, members: [["code.server", "upstream.ladybug"]] }]);
  });

  it("finds an outside element's address in its own project's map", () => {
    expect(outsideAddress("upstream.code.engine.game")).toBe("code.engine.game");
    expect(outsideAddress("downstream.service.chat")).toBe("service.chat");
    expect(outsideAddress("code.engine.game")).toBe("code.engine.game");
  });

  it("expands a first view level by level within a canvas-sized budget", () => {
    expect(startBudget(1440, 760)).toBe(18);
    expect(startBudget(100, 100)).toBe(10);
    expect(startBudget(4000, 3000)).toBe(60);
    // Top level: code, upstream (2). code has 3 children, upstream 1.
    expect(startExpansion(graphAddresses(graph), TOP, 6).sort()).toEqual(["code", "upstream"]);
    // Budget 4: code (3 children) does not fit, so upstream stays closed too: outside bands open
    // only once every project element at that level has opened.
    expect(startExpansion(graphAddresses(graph), TOP, 4)).toEqual([]);
    // Budget 9: both open (6), then code.server (1) and code.store (2) fit.
    expect(startExpansion(graphAddresses(graph), TOP, 9).sort()).toEqual(["code", "code.server", "code.store", "upstream"]);
    expect(startExpansion(graphAddresses(graph), TOP, 2)).toEqual([]);
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

  it("marks a container visited on its first view, and does it once", () => {
    const first = reduce(start, { type: "first-view", container: TOP, expand: ["code"] });
    expect(currentView(first)).toMatchObject({ expanded: ["code"], visited: [TOP] });
    expect(reduce(first, { type: "first-view", container: TOP, expand: ["upstream"] })).toBe(first);
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

  it("opens a link at the element it names: its container, with the element selected", () => {
    const moved = reduce(start, { type: "open-project", project: "metaform-2", from: "link", at: "code.server.tool" });
    expect(currentView(moved)).toMatchObject({ container: "code.server", selection: "code.server.tool" });
    const top = reduce(start, { type: "open-project", project: "metaform-3", from: "link", at: "code" });
    expect(currentView(top)).toMatchObject({ container: TOP, selection: "code" });
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

  it("gives each arrow its direction and, for a single want, its why", () => {
    const wants = new Map([
      ["code.server.relay", {
        "code.store.memory": { why: "keep facts", how: "holds them", direction: "outbound" },
        "code.store.cache": { why: "reuse reads", how: "keeps them", direction: "inbound" },
      }],
      ["code.server", { "upstream.ladybug": { why: "store maps", how: "persists graphs", direction: "outbound" } }],
    ]);
    const expanded = run([{ type: "toggle-expanded", address: "code.server" }], inCode);
    const scene = buildScene(expanded, input({ wants }));
    const arrow = scene.edges.find((e) => e.from === "code.server.relay" && e.to === "code.store");
    expect(arrow).toMatchObject({ count: 2, direction: "mixed", why: null, how: null, flowing: false });
    const single = buildScene(run([{ type: "select", address: "code.server" }], inCode), input({ wants }));
    expect(single.edges.find((e) => e.from === "code.server")).toMatchObject({ why: null, flowing: true });
    const collapsed = buildScene(inCode, input({ wants }));
    expect(collapsed.nodes.find((n) => n.address === "code.server")).toMatchObject({ outside: 1, technicalName: null });
  });

  it("dims without removing on isolate, so nothing moves", () => {
    const before = buildScene(inCode, input());
    const after = buildScene(reduce(inCode, { type: "isolate", layer: "specification" }), input());
    expect(after.nodes.map((n) => n.address)).toEqual(before.nodes.map((n) => n.address));
    expect(after.nodes.find((n) => n.address === "code.server")?.dimmed).toBe(true);
    expect(after.nodes.find((n) => n.address === "code.store")?.dimmed).toBe(false);
  });

  it("rolls the records of hidden elements up to their collapsed ancestor", () => {
    const deep = input({ layerCounts: new Map([["code.store.memory", new Map([["specification", 4]])]]) });
    const isolated = reduce(inCode, { type: "isolate", layer: "specification" });
    const store = buildScene(isolated, deep).nodes.find((n) => n.address === "code.store");
    expect(store).toMatchObject({ dimmed: false, layers: [{ layer: "specification", records: 4, style: 1 }] });
  });

  it("shows an element's wants in Element mode, including those held beneath it", () => {
    const scene = elementScene(inCode, input(), "code.server");
    expect(scene.nodes.map((n) => n.address).sort()).toEqual(["code.server", "code.store.cache", "code.store.memory", "upstream.ladybug"]);
    expect(scene.edges.map((e) => e.id).sort()).toEqual([
      "code.server->code.store.cache", "code.server->code.store.memory", "code.server->upstream.ladybug",
    ]);
  });

  it("puts the pivot on top and dims what lies beyond reach", () => {
    const state = reduce(inCode, { type: "set-focus", address: "code.server-tools" });
    const scene = buildScene(state, input());
    expect(scene.top).toBe("code.server-tools");
    expect(scene.nodes.find((n) => n.address === "code.store")?.dimmed).toBe(true);
  });
});
