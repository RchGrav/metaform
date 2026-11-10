import { describe, expect, it } from "vitest";
import { applyChange, current, toCommand } from "./changes";
import type { Change, Proposal } from "./changes";
import { handDump } from "./fixtures/hand-dump";
import { elementAt, fromDump } from "./model";

const saved = fromDump("quake", handDump);
const frozen = JSON.stringify(saved);

const setName: Change = { id: "c1", kind: "set-field", address: "code.engine.game", field: "name", value: "Quake engine" };
const clearStatus: Change = { id: "c2", kind: "set-field", address: "code.queue.dead_letter", field: "status", value: null };
const setWhy: Change = {
  id: "c3", kind: "set-want", address: "code.engine.game", to: "code.bus.data.event", part: "why", value: "read input each frame",
};
const addWant: Change = {
  id: "c4", kind: "add-want", address: "code.bus.data.event", to: "data.schema.message",
  why: "decode events", how: "gives the event layout", direction: "inbound",
};
const removeWant: Change = { id: "c5", kind: "remove-want", address: "code.engine.game", to: "code.bus.data.event" };
const setLayer: Change = {
  id: "c6", kind: "set-layer", address: "code.engine.game", layer: "specification", records: [{ text: "Rewritten." }],
};

describe("toCommand", () => {
  it("gives the project-map command for each kind of change", () => {
    expect(toCommand(setName)).toEqual({ update: { "code.engine.game": { name: "Quake engine" } } });
    expect(toCommand(clearStatus)).toEqual({ update: { "code.queue.dead_letter": { status: null } } });
    expect(toCommand(setWhy)).toEqual({
      update: { "code.engine.game": { wants: { "code.bus.data.event": { why: "read input each frame" } } } },
    });
    expect(toCommand(addWant)).toEqual({
      update: {
        "code.bus.data.event": {
          wants: { "data.schema.message": { why: "decode events", how: "gives the event layout", direction: "inbound" } },
        },
      },
    });
    expect(toCommand(removeWant)).toEqual({ delete: { "code.engine.game": { wants: ["code.bus.data.event"] } } });
    expect(toCommand(setLayer)).toEqual({ update: { "code.engine.game": { specification: [{ text: "Rewritten." }] } } });
  });
});

describe("applyChange", () => {
  it("sets a field and marks it, and leaves the given specification as it was", () => {
    const next = applyChange(saved, setName);
    expect(elementAt(next, "code.engine.game")?.name).toBe("Quake engine");
    expect(next.marks).toEqual([{ id: "c1", address: "code.engine.game", origin: "user", field: "name" }]);
    expect(JSON.stringify(saved)).toBe(frozen);
  });

  it("removes a field when the value is null", () => {
    const next = applyChange(saved, clearStatus);
    expect(elementAt(next, "code.queue.dead_letter")).not.toHaveProperty("status");
  });

  it("sets one part of a want and keeps the other parts", () => {
    const want = elementAt(applyChange(saved, setWhy), "code.engine.game")?.wants[0];
    expect(want).toEqual({ to: "code.bus.data.event", why: "read input each frame", how: "dispatches event streams", direction: "inbound" });
  });

  it("adds a want and removes a want", () => {
    expect(elementAt(applyChange(saved, addWant), "code.bus.data.event")?.wants).toEqual([
      { to: "data.schema.message", why: "decode events", how: "gives the event layout", direction: "inbound" },
    ]);
    const removed = applyChange(saved, removeWant);
    expect(elementAt(removed, "code.engine.game")?.wants.map((want) => want.to)).toEqual(["upstream.code.engine.physics"]);
    expect(removed.marks[0]).toEqual({ id: "c5", address: "code.engine.game", origin: "user", want: "code.bus.data.event" });
  });

  it("replaces a layer's records, and an empty list leaves no entry for the layer", () => {
    const next = applyChange(saved, setLayer);
    expect(elementAt(next, "code.engine.game")?.layers.specification).toEqual([{ text: "Rewritten." }]);
    const emptied = applyChange(saved, { ...setLayer, records: [] });
    expect(elementAt(emptied, "code.engine.game")?.layers).not.toHaveProperty("specification");
  });

  it("makes an element when a field is set at an address that has none", () => {
    const next = applyChange(saved, { id: "c7", kind: "set-field", address: "code.cache.response", field: "name", value: "Reply store" });
    expect(elementAt(next, "code.cache.response")).toEqual({
      address: "code.cache.response", band: "project", name: "Reply store", wants: [], layers: {},
    });
    expect(next.elements.map((element) => element.address)).toEqual([...next.elements.map((element) => element.address)].sort());
  });

  it("returns the given specification when the change does not apply", () => {
    expect(applyChange(saved, { ...setWhy, to: "code.not.wanted" })).toBe(saved);
    expect(applyChange(saved, { ...removeWant, to: "code.not.wanted" })).toBe(saved);
    expect(applyChange(saved, { ...addWant, address: "code.not.there" })).toBe(saved);
  });

  it("keeps one mark for a part that two changes set", () => {
    const next = applyChange(applyChange(saved, setName), { ...setName, id: "c8", value: "Quake III" }, "agent");
    expect(next.marks).toEqual([{ id: "c8", address: "code.engine.game", origin: "agent", field: "name" }]);
  });
});

describe("current", () => {
  const proposal = (state: Proposal["state"], change: Change): Proposal => ({
    change, rationale: "The header names it so.", evidence: ["./src/engine.h"], proposedBy: "Sample agent", simulated: true, state,
  });

  it("applies the user's edits and accepted proposals, and no other proposal", () => {
    const role: Change = { id: "p1", kind: "set-field", address: "code.queue.dead_letter", field: "role", value: "Notable" };
    const uri: Change = { id: "p2", kind: "set-field", address: "code.queue.dead_letter", field: "uri", value: "./src/dlq.c" };
    const next = current(saved, [setName, proposal("accepted", role), proposal("proposed", uri), proposal("rejected", clearStatus)]);
    expect(elementAt(next, "code.engine.game")?.name).toBe("Quake engine");
    const queue = elementAt(next, "code.queue.dead_letter");
    expect(queue?.role).toBe("Notable");
    expect(queue?.uri).toBeUndefined();
    expect(queue?.status).toBe("un_built");
    expect(next.marks.map((mark) => [mark.id, mark.origin])).toEqual([["c1", "user"], ["p1", "agent"]]);
  });

  it("gives the saved specification when nothing is pending", () => {
    expect(current(saved, [])).toBe(saved);
  });
});
