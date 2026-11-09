import ELK from "elkjs/lib/elk.bundled.js";
import { describe, expect, it } from "vitest";
import { createMockSource } from "../mock";
import type { Address, ElementFields } from "../source/types";
import { buildScene } from "../state/scene";
import { layerCounts, layerNames } from "../state/structure";
import { initialState, reduce, type Action } from "../state/view";
import { type Box, type Elk, HEADER, layout, layoutKey } from "./layout";
import type { RenderScene } from "./renderer";

const elk = new ELK() as unknown as Elk;

async function sceneFor(project: string, actions: Action[] = []): Promise<RenderScene> {
  const source = createMockSource({ playEvents: false });
  const graph = await source.map(project);
  const dump = await source.dump(project);
  const fields = new Map<Address, ElementFields>();
  for (const address of graph.addresses) fields.set(address, (await source.goto(project, address)).element);
  const layers = layerNames(dump);
  const state = [{ type: "open-project", project } as Action, ...actions].reduce(reduce, initialState());
  return buildScene(state, {
    graph, fields, layers, layerCounts: layerCounts(dump, layers), agents: [],
    opensProject: (a) => String(fields.get(a)?.uri ?? "").startsWith("metaform://"),
  });
}

function overlaps(a: Box, b: Box): boolean {
  return a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;
}

function inside(child: Box, parent: Box): boolean {
  return child.x >= parent.x && child.y >= parent.y + HEADER - 1 &&
    child.x + child.width <= parent.x + parent.width && child.y + child.height <= parent.y + parent.height;
}

describe("ELK layout of a scene", () => {
  it("gives every node a box and every edge a route, without overlaps", async () => {
    const scene = await sceneFor("metaform");
    const result = await layout(elk, scene);
    expect(scene.nodes.length).toBeGreaterThan(0);
    for (const node of scene.nodes) expect(result.boxes.has(node.address)).toBe(true);
    for (const edge of scene.edges) expect(result.routes.get(edge.id)?.length).toBeGreaterThanOrEqual(2);
    const top = scene.nodes.filter((n) => n.parent === null).map((n) => result.boxes.get(n.address)!);
    for (let i = 0; i < top.length; i++) for (let j = i + 1; j < top.length; j++) {
      expect(overlaps(top[i]!, top[j]!)).toBe(false);
    }
  });

  it("places upstream left of the project and downstream right of it", async () => {
    const scene = await sceneFor("metaform");
    const result = await layout(elk, scene);
    const xs = (band: string) => scene.nodes.filter((n) => n.band === band).map((n) => result.boxes.get(n.address)!);
    const project = xs("project");
    for (const box of xs("upstream")) expect(box.x + box.width).toBeLessThan(Math.min(...project.map((b) => b.x)));
    for (const box of xs("downstream")) expect(box.x).toBeGreaterThan(Math.max(...project.map((b) => b.x + b.width)));
    expect(result.separators.map((s) => s.band)).toEqual(["upstream", "downstream"]);
  });

  it("gives the same layout for the same scene", async () => {
    const scene = await sceneFor("roundtable");
    const a = await layout(elk, scene);
    const b = await layout(elk, scene);
    expect([...a.boxes]).toEqual([...b.boxes]);
  });

  it("keeps the layout key when only marks and flags change", async () => {
    const scene = await sceneFor("metaform");
    const flagged: RenderScene = {
      ...scene,
      nodes: scene.nodes.map((n) => ({ ...n, selected: true, dimmed: true, unseen: true, layers: [], agents: [] })),
      edges: scene.edges.map((e) => ({ ...e, dimmed: true })),
    };
    expect(layoutKey(flagged)).toBe(layoutKey(scene));
    expect(layoutKey({ ...scene, nodes: scene.nodes.slice(1) })).not.toBe(layoutKey(scene));
  });

  it("draws the children of an expanded element inside it", async () => {
    const scene = await sceneFor("metaform", [
      { type: "open", address: "code", beneath: 1 },
      { type: "toggle-expanded", address: "code.store" },
    ]);
    const children = scene.nodes.filter((n) => n.parent === "code.store");
    expect(children.length).toBeGreaterThan(0);
    const result = await layout(elk, scene);
    const parent = result.boxes.get("code.store")!;
    for (const child of children) expect(inside(result.boxes.get(child.address)!, parent)).toBe(true);
  });

  it("puts the focus element at the top of its band", async () => {
    const base = await sceneFor("metaform", [{ type: "open", address: "code", beneath: 1 }]);
    const scene: RenderScene = { ...base, top: "code.store" };
    const result = await layout(elk, scene);
    const project = base.nodes.filter((n) => n.band === "project" && n.parent === null);
    const top = result.boxes.get("code.store")!.y;
    expect(Math.min(...project.map((n) => result.boxes.get(n.address)!.y))).toBe(top);
  });

  it("lays out the largest one-level scene quickly enough for an interaction", async () => {
    const scene = await sceneFor("roundtable", [{ type: "open", address: "code", beneath: 1 }]);
    await layout(elk, scene); // warm
    const start = performance.now();
    await layout(elk, scene);
    const ms = performance.now() - start;
    console.info(`roundtable/code: ${scene.nodes.length} nodes, ${scene.edges.length} edges, ${ms.toFixed(0)} ms`);
    expect(ms).toBeLessThan(500);
  });
});
