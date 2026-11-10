import { describe, expect, it } from "vitest";
import { handDump } from "./fixtures/hand-dump";
import { definitiveOf, elementAt, fromDump, inScope, labelAt, wantedBy } from "./model";

const spec = fromDump("quake", handDump);

describe("fromDump", () => {
  it("keeps the project's name and lists every element in address order", () => {
    expect(spec.project).toBe("quake");
    expect(spec.elements.map((element) => element.address)).toEqual([
      "code.bus.data.event",
      "code.engine.game",
      "code.queue.dead_letter",
      "data.schema.message",
      "downstream.developer.game",
      "upstream.code.engine.physics",
    ]);
  });

  it("does not record an address that has no technical name, name or role", () => {
    for (const address of ["code", "code.engine", "code.bus.data", "downstream", "upstream.code"]) {
      expect(elementAt(spec, address)).toBeUndefined();
    }
  });

  it("keeps layer definitions apart from elements", () => {
    expect(spec.elements.some((element) => element.address.startsWith("layer"))).toBe(false);
    expect(spec.layerDefinitions).toEqual([
      {
        address: "layer.document.specification",
        field: "specification",
        name: "Specification",
        description: "Prose that the skeleton leaves out.",
      },
    ]);
  });

  it("sets the three bands", () => {
    expect(elementAt(spec, "code.engine.game")?.band).toBe("project");
    expect(elementAt(spec, "downstream.developer.game")?.band).toBe("downstream");
    expect(elementAt(spec, "upstream.code.engine.physics")?.band).toBe("upstream");
  });

  it("reads the fields, the wants in address order and the layer records", () => {
    const engine = elementAt(spec, "code.engine.game");
    expect(engine).toMatchObject({
      name: "Quake core",
      technical_name: "game engine",
      role: "Definitive",
      uri: "./src/engine.c",
    });
    expect(engine?.status).toBeUndefined();
    expect(engine?.wants).toEqual([
      { to: "code.bus.data.event", why: "receive player input", how: "dispatches event streams", direction: "inbound" },
      { to: "upstream.code.engine.physics", why: "resolve collisions", how: "steps rigid bodies", direction: "two-way" },
    ]);
    expect(Object.keys(engine?.layers ?? {})).toEqual(["sources", "specification"]);
    expect(engine?.layers.specification).toHaveLength(3);
    expect(elementAt(spec, "code.queue.dead_letter")?.status).toBe("un_built");
  });

  it("keeps the records at the project's root and starts with no marks", () => {
    expect(spec.rootLayers).toEqual({ specification: [{ text: "A note at the root." }] });
    expect(spec.marks).toEqual([]);
  });

  it("gives an empty specification for a dump with no tree", () => {
    expect(fromDump("empty", {})).toEqual({ project: "empty", elements: [], layerDefinitions: [], rootLayers: {}, marks: [] });
    expect(fromDump("empty", { ".": {} }).elements).toEqual([]);
  });
});

describe("reads of a specification", () => {
  it("finds the Definitive element and who relies on an element", () => {
    expect(definitiveOf(spec)?.address).toBe("code.engine.game");
    expect(wantedBy(spec, "code.engine.game").map((held) => held.holder)).toEqual(["downstream.developer.game"]);
  });

  it("labels an address by name, then technical name, then address", () => {
    expect(labelAt(spec, "code.engine.game")).toBe("Quake core");
    expect(labelAt(spec, "code.queue.dead_letter")).toBe("dead letter queue");
    expect(labelAt(spec, "code.not.there")).toBe("code.not.there");
  });

  it("holds an address and everything beneath it in a scope", () => {
    expect(inScope("code.engine.game", "code.engine")).toBe(true);
    expect(inScope("code.engine", "code.engine")).toBe(true);
    expect(inScope("code.engines", "code.engine")).toBe(false);
    expect(inScope("data.schema", null)).toBe(true);
  });
});
