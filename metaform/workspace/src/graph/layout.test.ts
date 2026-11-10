import { describe, expect, it } from "vitest";
import { createMockSource } from "../mock";
import type { Address, ElementFields } from "../source/types";
import { buildScene } from "../state/scene";
import { layerCounts, layerNames } from "../state/structure";
import { initialState, reduce, type Action } from "../state/view";
import { graph as text } from "../strings";
import ELK from "elkjs/lib/elk.bundled.js";
import { type Box, type Elk, HEADER, layout as run, layoutKey, nodeWidth } from "./layout";
import type { RenderScene } from "./renderer";

const widthsOf = (scene: RenderScene) =>
  new Map(scene.nodes.map((n) => [n.address, nodeWidth(n, text.beneathBadge, text.wantsOutside)]));
const elk = new ELK() as unknown as Elk;
const layout = (engine: Elk, scene: RenderScene) => run(engine, scene, widthsOf(scene));

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

  it("places what the project serves above it and what it relies on beneath it", async () => {
    // The layout is by purpose, top to bottom (2026-11-09). Before, the bands stood side by side.
    const scene = await sceneFor("metaform");
    const result = await layout(elk, scene);
    const tops = (band: string) => scene.nodes.filter((n) => n.band === band && n.parent === null).map((n) => result.boxes.get(n.address)!);
    const project = tops("project");
    for (const box of tops("downstream")) expect(box.y + box.height).toBeLessThanOrEqual(Math.min(...project.map((b) => b.y)));
    for (const box of tops("upstream")) expect(box.y).toBeGreaterThanOrEqual(Math.max(...project.map((b) => b.y + b.height)));
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
      nodes: scene.nodes.map((n) => ({ ...n, selected: true, dimmed: true, unseen: true, agents: [] })),
      edges: scene.edges.map((e) => ({ ...e, dimmed: true })),
    };
    expect(layoutKey(flagged, widthsOf(scene))).toBe(layoutKey(scene, widthsOf(scene)));
    const fewer = { ...scene, nodes: scene.nodes.slice(1) };
    expect(layoutKey(fewer, widthsOf(fewer))).not.toBe(layoutKey(scene, widthsOf(scene)));
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

  it("places every node and routes every edge in every container, all expanded, of every project", async () => {
    for (const project of ["metaform", "roundtable", "mashtrac"]) {
      const graph = await createMockSource({ playEvents: false }).map(project);
      const parents = new Set(graph.addresses.map((a) => a.split(".").slice(0, -1).join(".")).filter(Boolean));
      const containers = [".", ...graph.addresses.filter((a) => parents.has(a))];
      for (const container of containers) {
        const actions: Action[] = container === "." ? [] : [{ type: "open", address: container, beneath: 1 }];
        actions.push({ type: "expand-all", addresses: graph.addresses });
        const scene = await sceneFor(project, actions);
        const result = await layout(elk, scene);
        for (const node of scene.nodes) expect(result.boxes.has(node.address), `${project} ${container} ${node.address}`).toBe(true);
        for (const edge of scene.edges) expect(result.routes.has(edge.id), `${project} ${container} ${edge.id}`).toBe(true);
        const siblings = new Map<string | null, Box[]>();
        for (const node of scene.nodes) siblings.set(node.parent, [...(siblings.get(node.parent) ?? []), result.boxes.get(node.address)!]);
        for (const [parent, boxes] of siblings) {
          for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
            expect(overlaps(boxes[i]!, boxes[j]!), `${project} ${container} under ${parent}`).toBe(false);
          }
        }
      }
    }
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
