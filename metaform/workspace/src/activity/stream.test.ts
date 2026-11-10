// `diff` for each kind of change to the map, and the pause and filter functions.

import { describe, expect, it } from "vitest";
import { handDump } from "../spec/fixtures/hand-dump";
import { fromDump } from "../spec/model";
import type { Spec, SpecElement } from "../spec/model";
import { after, diff, filterItems, hold, isSimulated } from "./stream";
import type { ActivityItem } from "./stream";

const at = new Date("2026-11-10T09:30:00Z");
const base = fromDump("quake", handDump);
const GAME = "code.engine.game";

/** A copy of the hand specification with one element replaced, added or removed. */
function withElement(address: string, edit: (element: SpecElement) => SpecElement | null): Spec {
  const elements = base.elements.flatMap((element) => {
    if (element.address !== address) return [element];
    const edited = edit({ ...element, wants: element.wants.map((want) => ({ ...want })), layers: { ...element.layers } });
    return edited === null ? [] : [edited];
  });
  return { ...base, elements };
}

describe("diff", () => {
  it("returns nothing for two equal specifications", () => {
    expect(diff(base, fromDump("quake", handDump), at)).toEqual([]);
  });

  it("reports an added element, with its fields as the values after", () => {
    const before = withElement("code.queue.dead_letter", () => null);
    const items = diff(before, base, at);
    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({
      type: "element-added", time: at, status: "recorded", scope: "code.queue.dead_letter", element: "code.queue.dead_letter",
      summary: "dead letter queue was added to the map.", simulated: false,
    });
    expect(items[0]?.details?.changes).toEqual([
      { what: "address", before: null, after: "code.queue.dead_letter" },
      { what: "technical name", before: null, after: "dead letter queue" },
      { what: "status", before: null, after: "not built" },
      { what: "wants held", before: null, after: "0" },
    ]);
  });

  it("reports a removed element once, with no affected element and no item for its wants", () => {
    const items = diff(base, withElement("downstream.developer.game", () => null), at);
    expect(items.map((item) => [item.type, item.scope, item.element, item.summary])).toEqual([
      ["element-removed", "downstream.developer.game", null, "Studio developer was removed from the map."],
    ]);
    expect(items[0]?.details?.changes?.[0]).toEqual({ what: "address", before: "downstream.developer.game", after: null });
  });

  it("reports a field that changed, was set or was removed, with before and after", () => {
    const after = withElement(GAME, (element) => {
      const { uri: _uri, ...rest } = element;
      return { ...rest, name: "Quake heart", status: "un_built" };
    });
    const items = diff(base, after, at);
    expect(items.map((item) => [item.type, item.summary, item.details?.changes])).toEqual([
      ["field-changed", "The name of Quake heart changed.", [{ what: "name", before: "Quake core", after: "Quake heart" }]],
      ["field-changed", "The status of Quake heart was set.", [{ what: "status", before: null, after: "not built" }]],
      ["field-changed", "The source reference of Quake heart was removed.", [{ what: "source reference", before: "./src/engine.c", after: null }]],
    ]);
    expect(items.every((item) => item.element === GAME && item.scope === GAME)).toBe(true);
  });

  it("reports a want added, removed and changed", () => {
    const after = withElement(GAME, (element) => ({
      ...element,
      wants: [
        { to: "code.bus.data.event", why: "receive player input", how: "polls the queue", direction: "" },
        { to: "data.schema.message", why: "read the wire format", how: "", direction: "inbound" },
      ],
    }));
    const items = diff(base, after, at);
    expect(items.map((item) => [item.type, item.summary])).toEqual([
      ["want-changed", "The how and direction of the want that Quake core holds for code.bus.data.event changed."],
      ["want-added", "Quake core now relies on data.schema.message."],
      ["want-removed", "Quake core no longer relies on upstream.code.engine.physics."],
    ]);
    expect(items[0]?.details?.changes).toEqual([
      { what: "how", before: "dispatches event streams", after: "polls the queue" },
      { what: "direction", before: "inbound", after: null },
    ]);
    expect(items[1]?.details?.changes).toEqual([
      { what: "why", before: null, after: "read the wire format" },
      { what: "direction", before: null, after: "inbound" },
    ]);
    expect(items[2]?.details?.changes?.[0]).toEqual({ what: "why", before: "resolve collisions", after: null });
  });

  it("reports layer records that changed at an element and at the project's root", () => {
    const edited = withElement(GAME, (element) => ({
      ...element,
      layers: { ...element.layers, specification: [{ text: "A new block." }], sources: ["./docs/engine.md", { path: "./docs/loop.md" }, "./src/main.c"] },
    }));
    const items = diff(base, { ...edited, rootLayers: {} }, at);
    expect(items.map((item) => [item.type, item.scope, item.element, item.summary])).toEqual([
      ["layer-changed", GAME, GAME, 'The records of the layer "sources" at Quake core changed.'],
      ["layer-changed", GAME, GAME, 'The records of the layer "specification" at Quake core changed.'],
      ["layer-changed", null, null, 'The records of the layer "specification" at the project\'s root changed.'],
    ]);
    expect(items[0]?.details).toEqual({
      text: "The number of records is the same. The content of at least one record changed.",
      changes: [{ what: 'records of "sources"', before: "3 records", after: "3 records" }],
    });
    expect(items[1]?.details).toEqual({ changes: [{ what: 'records of "specification"', before: "3 records", after: "1 record" }] });
    expect(items[2]?.details?.changes?.[0]).toMatchObject({ before: "1 record", after: "0 records" });
  });

  it("gives every item a different id, and marks the items as simulated when told to", () => {
    const after = withElement(GAME, (element) => ({ ...element, name: "Other", role: "Notable", wants: [] }));
    const items = diff(base, after, at, true);
    expect(new Set(items.map((item) => item.id)).size).toBe(items.length);
    expect(items.every((item) => item.simulated && isSimulated(item))).toBe(true);
    expect(diff(base, after, at).every((item) => !isSimulated(item))).toBe(true);
  });
});

const item = (id: string, fields: Partial<ActivityItem> = {}): ActivityItem => ({
  id, type: "field-changed", time: at, status: "recorded", scope: "code.a", element: "code.a", summary: id, simulated: false, ...fields,
});

describe("isSimulated", () => {
  it("is true for a type the page has no source for, whatever the flag says", () => {
    expect(isSimulated(item("t", { type: "test-result", status: "passed" }))).toBe(true);
    expect(isSimulated(item("m"))).toBe(false);
  });
});

describe("hold and after", () => {
  const items = [item("1"), item("2"), item("3"), item("4")];

  it("lists every item when there is no pause", () => {
    expect(hold(items, null)).toEqual({ listed: items, waiting: 0 });
  });

  it("holds the items that arrived after the pause started", () => {
    const held = hold(items, { lastId: "2" });
    expect(held.listed.map((each) => each.id)).toEqual(["1", "2"]);
    expect(held.waiting).toBe(2);
  });

  it("holds every item when the list was empty at the pause, or when the named item is gone", () => {
    expect(hold(items, { lastId: null })).toEqual({ listed: [], waiting: 4 });
    expect(hold(items, { lastId: "0" })).toEqual({ listed: [], waiting: 4 });
  });

  it("gives the items after an id", () => {
    expect(after(items, "3").map((each) => each.id)).toEqual(["4"]);
    expect(after(items, "4")).toEqual([]);
    expect(after(items, null)).toHaveLength(4);
    expect(after(items, "gone")).toHaveLength(4);
  });
});

describe("filterItems", () => {
  const items = [item("1"), item("2", { type: "want-added", element: "code.b" }), item("3", { type: "layer-changed", scope: null, element: null })];

  it("filters by type, by the affected element, and by both", () => {
    expect(filterItems(items, { type: null, element: null })).toHaveLength(3);
    expect(filterItems(items, { type: "want-added", element: null }).map((each) => each.id)).toEqual(["2"]);
    expect(filterItems(items, { type: null, element: "code.a" }).map((each) => each.id)).toEqual(["1"]);
    expect(filterItems(items, { type: "want-added", element: "code.a" })).toEqual([]);
  });
});
