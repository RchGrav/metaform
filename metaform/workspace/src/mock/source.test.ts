import { describe, expect, it, vi } from "vitest";
import { RefusalError } from "../source/errors";
import type { WorkspaceEvent } from "../source/types";
import { MockSource, workspace } from "./index";

const fixed = () => new MockSource(workspace, { playEvents: false });

describe("MockSource reads", () => {
  it("lists the three simulated projects with opaque ids", async () => {
    const projects = await fixed().projects();
    expect(projects.map((p) => p.id)).toEqual(["metaform", "roundtable", "mashtrac"]);
    expect(Object.keys(projects[0] ?? {})).toEqual(["id", "name", "folder"]);
  });

  it("returns the shallow graph sorted by address, without the root", async () => {
    const graph = await fixed().map("metaform");
    expect(graph.addresses).toHaveLength(119);
    expect(graph.edges).toHaveLength(68);
    expect([...graph.addresses].sort()).toEqual(graph.addresses);
    expect(graph.addresses).not.toContain("");
    expect(graph.definitive).toBe("code.system.management.knowledge");
  });

  it("keeps every want edge between existing addresses", async () => {
    for (const id of ["metaform", "roundtable", "mashtrac"]) {
      const graph = await fixed().map(id);
      const known = new Set(graph.addresses);
      for (const [holder, wanted] of graph.edges) {
        expect(known.has(holder) && known.has(wanted)).toBe(true);
      }
    }
  });

  it("builds the summary sheet with counts, not records", async () => {
    const sheet = await fixed().goto("metaform", "code.server.tool");
    expect(Object.keys(sheet)).toEqual([
      "at", "element", "wants", "wanted_by", "layers", "skills", "memory", "instructions",
    ]);
    expect(sheet.layers).toEqual({ specification: { records: 1 } });
    expect(sheet.memory).toEqual({ records: 1 });
    expect(Object.values(sheet.element).some(Array.isArray)).toBe(false);
  });

  it("delivers layer guidance once per project", async () => {
    const source = fixed();
    const first = await source.goto("metaform", "code.server.tool");
    const second = await source.goto("metaform", "code.store.memory");
    expect(Object.keys(first.instructions ?? {})).toEqual(["specification"]);
    expect(second.instructions).toBeUndefined();
  });

  it("lists wanted_by as the reverse of the edges", async () => {
    const source = fixed();
    const graph = await source.map("metaform");
    const sheet = await source.goto("metaform", "code.store.memory");
    const holders = graph.edges.filter(([, w]) => w === "code.store.memory").map(([h]) => h);
    expect(Object.keys(sheet.wanted_by).sort()).toEqual(holders.sort());
  });

  it("returns layer records, and an empty list for a layer the element does not hold", async () => {
    const source = fixed();
    const records = await source.layerRecords("metaform", "code.server.tool", "specification");
    expect(records).toHaveLength(1);
    expect(await source.layerRecords("metaform", "code.server.tool", "nothing")).toEqual([]);
  });

  it("refuses an address that does not exist, in the refusal structure", async () => {
    const error = await fixed().goto("metaform", "code.nowhere").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(RefusalError);
    const refusal = (error as RefusalError).refusal;
    expect(refusal.code).toBe("NOT_FOUND");
    expect(refusal.remediation).toEqual({ map: {} });
    expect(Object.keys(refusal).slice(0, 2)).toEqual(["goto", "status"]);
  });

  it("returns a copy of the dump under the '.' key", async () => {
    const source = fixed();
    const dump = (await source.dump("metaform"))["."] as Record<string, unknown>;
    expect(Object.keys(dump)).toEqual(["code", "document", "downstream", "layer", "upstream"]);
    delete dump["code"];
    expect(Object.keys(((await source.dump("metaform"))["."]) as object)).toContain("code");
  });

  it("lists an outside project as one element, and answers its own map under its own id", async () => {
    const source = fixed();
    const graph = await source.map("metaform");
    expect(graph.addresses.filter((a) => a.startsWith("upstream.code.engine.workflow"))).toEqual(["upstream.code.engine.workflow"]);
    const ref = await source.outsideMap("metaform", "upstream.code.engine.workflow");
    expect(ref).toEqual({
      id: "outside:https://example.invalid/mock/workflow-engine",
      name: "workflow-engine",
      uri: "https://example.invalid/mock/workflow-engine",
    });
    const outside = await source.map(ref!.id);
    expect(outside.definitive).toBe("code.engine.workflow");
    expect(outside.edges).toContainEqual(["code.engine.workflow", "code.interpreter.flow"]);
    expect(outside.addresses.some((a) => a.startsWith("upstream.code.engine.workflow"))).toBe(false);
    expect((await source.goto(ref!.id, "code.transport.call")).wanted_by).toHaveProperty("code.interpreter.flow");
    expect(Object.keys(((await source.dump(ref!.id))["."]) as object)).toContain("code");
    expect(await source.outsideMap("metaform", "code.store")).toBeNull();
    expect((await source.projects()).map((p) => p.id)).not.toContain(ref!.id);
  });

  it("names cross-project links with the map URI and the element as fragment", async () => {
    const sheet = await fixed().goto("roundtable", "upstream.service.metaform");
    expect(sheet.element.uri).toBe("metaform://map/project/metaform/main#code.server.tool");
  });
});

describe("MockSource simulated updates", () => {
  it("announces presence on subscribe, then a write as map-changed", async () => {
    const run: (() => void)[] = [];
    const source = new MockSource(workspace, {
      schedule: (fn) => {
        run.push(fn);
        return 0 as unknown as ReturnType<typeof setTimeout>;
      },
    });
    const events: WorkspaceEvent[] = [];
    const stop = source.subscribe("metaform", (e) => events.push(e));
    expect(events.map((e) => e.kind)).toEqual(["agent-presence", "agent-presence"]);
    expect(events.every((e) => e.simulated)).toBe(true);

    run[0]?.(); // Ida writes a specification block at code.store.memory.
    expect(events.at(-2)).toEqual({ kind: "map-changed", project: "metaform", simulated: true });
    const sheet = await source.goto("metaform", "code.store.memory");
    expect(sheet.layers["specification"]).toEqual({ records: 2 });

    stop();
    run[1]?.();
    expect(events).toHaveLength(4);
  });

  it("starts a first run with no projects, and fills the sample over the simulated intake", async () => {
    const run: (() => void)[] = [];
    const source = new MockSource(workspace, {
      firstRun: true,
      playEvents: false,
      schedule: (fn) => {
        run.push(fn);
        return 0 as unknown as ReturnType<typeof setTimeout>;
      },
    });
    expect(await source.projects()).toEqual([]);
    const events: WorkspaceEvent[] = [];
    source.subscribe("mashtrac", (e) => events.push(e));
    const sample = await source.simulateIntake();
    expect(sample.id).toBe("mashtrac");
    expect((await source.projects()).map((p) => p.id)).toEqual(["mashtrac"]);
    expect((await source.map("mashtrac")).addresses).toEqual([]);
    run[0]?.();
    expect((await source.map("mashtrac")).addresses).toHaveLength(1);
    for (const step of run.slice(1)) step();
    const full = await new MockSource(workspace, { playEvents: false }).map("mashtrac");
    expect(await source.map("mashtrac")).toEqual(full);
    expect(events.filter((e) => e.kind === "map-changed")).toHaveLength(run.length + 1);
  });

  it("sends each agent's name with its presence", () => {
    const events: WorkspaceEvent[] = [];
    new MockSource(workspace, { playEvents: false }).subscribe("metaform", (e) => events.push(e));
    expect(events.map((e) => (e.kind === "agent-presence" ? e.name : null))).toEqual(["Ida", "Marcus"]);
  });

  it("never changes the imported workspace data", () => {
    const source = new MockSource(workspace, { playEvents: false });
    const before = JSON.stringify(workspace);
    for (const event of workspace.events) source.apply(event);
    expect(JSON.stringify(workspace)).toBe(before);
  });

  it("stops its timers on close", () => {
    vi.useFakeTimers();
    const source = new MockSource(workspace);
    const events: WorkspaceEvent[] = [];
    source.subscribe("metaform", (e) => events.push(e));
    source.close();
    vi.advanceTimersByTime(60_000);
    expect(events.filter((e) => e.kind === "map-changed")).toHaveLength(0);
    vi.useRealTimers();
  });
});
