import { describe, expect, it } from "vitest";
import { between } from "./camera";
import { around, branchOf, clearPart, fitViewport, joinedTo, NO_INSETS } from "./fit";
import { easeOutCubic } from "./glide";
import type { RenderScene } from "./renderer";

const edge = (from: string, to: string) => ({ id: `${from}->${to}`, from, to }) as RenderScene["edges"][number];
const scene = { nodes: [], edges: [edge("a", "b"), edge("b", "c"), edge("x", "b"), edge("c", "a"), edge("y", "z")], top: null } as RenderScene;

describe("what a fit frames", () => {
  it("frames the selection with the elements joined to it", () => {
    expect(joinedTo(scene, "b").sort()).toEqual(["a", "b", "c", "x"]);
  });

  it("frames a branch: the element and everything reached from it along its wants", () => {
    expect(branchOf(scene, "x").sort()).toEqual(["a", "b", "c", "x"]);
    expect(branchOf(scene, "y").sort()).toEqual(["y", "z"]);
    expect(branchOf(scene, "z")).toEqual(["z"]);
  });

  it("puts the target in the middle of the part of the pane that nothing covers", () => {
    const pane = { width: 1000, height: 600 };
    const target = { x: 100, y: 50, width: 400, height: 200 };
    const clear = clearPart(pane, { left: 300, right: 0, top: 40, bottom: 60 });
    expect(clear).toEqual({ x: 300, y: 40, width: 700, height: 500 });
    const v = fitViewport(target, clear, 48, 4);
    const left = target.x * v.zoom + v.x;
    const top = target.y * v.zoom + v.y;
    expect(left).toBeGreaterThanOrEqual(300 + 48 - 0.001);
    expect(left + target.width * v.zoom).toBeLessThanOrEqual(1000 - 48 + 0.001);
    expect(top).toBeGreaterThanOrEqual(40 + 48 - 0.001);
    expect(top + target.height * v.zoom).toBeLessThanOrEqual(540 - 48 + 0.001);
    expect(left + (target.width * v.zoom) / 2).toBeCloseTo(650);
    expect(top + (target.height * v.zoom) / 2).toBeCloseTo(290);
    expect(fitViewport(target, clearPart(pane, NO_INSETS), 48, 1).zoom).toBe(1);
    expect(around([target, { x: 0, y: 0, width: 10, height: 300 }])).toEqual({ x: 0, y: 0, width: 500, height: 300 });
    expect(around([])).toBeNull();
  });
});

describe("motion", () => {
  it("moves the centre linearly and the size in log space during a fit", () => {
    const pivot = { x: 400, y: 300 };
    const from = { x: 0, y: 0, zoom: 1 };
    const to = { x: -1200, y: -500, zoom: 4 };
    expect(between(from, to, 0, pivot)).toEqual(from);
    const end = between(from, to, 1, pivot);
    expect([end.x, end.y, end.zoom].map((n) => Math.round(n * 1000) / 1000)).toEqual([-1200, -500, 4]);
    const half = between(from, to, 0.5, pivot);
    expect(half.zoom).toBeCloseTo(2);
    const centre = (v: typeof from) => ({ x: (pivot.x - v.x) / v.zoom, y: (pivot.y - v.y) / v.zoom });
    expect(centre(half).x).toBeCloseTo((centre(from).x + centre(to).x) / 2);
    expect(centre(half).y).toBeCloseTo((centre(from).y + centre(to).y) / 2);
  });

  it("slides fast at first and slower at the end", () => {
    expect([easeOutCubic(0), easeOutCubic(1)]).toEqual([0, 1]);
    expect(easeOutCubic(0.5)).toBeCloseTo(0.875);
  });
});
