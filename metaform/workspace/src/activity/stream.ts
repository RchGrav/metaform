// The activity model: what has happened to the map while the person watches. A real item comes
// from comparing two `Spec` values, the one before a change the server announced and the one
// after. The types test result, build result, dependency change and runtime issue have no
// source in the page; a caller passes them only as simulated items. Every function is pure.

import type { Address } from "../source/types";
import { FIELD_NAMES, WANT_PARTS, labelOf } from "../spec/model";
import type { Spec, SpecElement, SpecWant } from "../spec/model";
import { statusValue } from "../spec/strings";
import { change as words, fieldWords, partWords } from "./strings";

/** The types of item that `diff` returns: changes to the map. */
export const MAP_TYPES = [
  "element-added",
  "element-removed",
  "field-changed",
  "want-added",
  "want-removed",
  "want-changed",
  "layer-changed",
] as const;

/** The types the page has no source for. An item of one of these types is always simulated. */
export const SOURCELESS_TYPES = ["test-result", "build-result", "dependency-change", "runtime-issue"] as const;

/** Every type of activity item, in the order the type filter lists them. */
export const ACTIVITY_TYPES = [...MAP_TYPES, ...SOURCELESS_TYPES] as const;

/** The type of an activity item. */
export type ActivityType = (typeof ACTIVITY_TYPES)[number];

/**
 * The status of an activity item. A change to the map is `recorded`: the server stored it. The
 * other statuses are for the types that have no source yet.
 */
export type ActivityStatus = "recorded" | "passed" | "failed" | "open" | "resolved";

/** One value that changed. `null` means that the map held no value. */
export interface ValueChange {
  /** What the value is, in words: a field, a part of a want, or the records of a layer. */
  what: string;
  before: string | null;
  after: string | null;
}

/** The details of an activity item. */
export interface ActivityDetails {
  /** One or more sentences. */
  text?: string;
  /** The values before and after, for a change. */
  changes?: ValueChange[];
}

/** One item of the activity stream. */
export interface ActivityItem {
  /** Unique in the stream. */
  id: string;
  type: ActivityType;
  time: Date;
  status: ActivityStatus;
  /** The address the item concerns, or null when it concerns the whole project. */
  scope: Address | null;
  /** The address of the element the item affects, or null when the map holds no such element. */
  element: Address | null;
  /** One line that says what happened. */
  summary: string;
  details?: ActivityDetails;
  /** True when no real source produced the item. */
  simulated: boolean;
}

/** True when the page must show the item as simulated: its flag is set, or its type has no source. */
export function isSimulated(item: ActivityItem): boolean {
  return item.simulated || (SOURCELESS_TYPES as readonly string[]).includes(item.type);
}

const shown = (field: string, value: string | undefined): string | null =>
  value === undefined ? null : field === "status" ? statusValue(value) : value;

const part = (value: string): string | null => (value === "" ? null : value);

function sameRecords(a: unknown[] | undefined, b: unknown[] | undefined): boolean {
  return JSON.stringify(a ?? []) === JSON.stringify(b ?? []);
}

function layerChange(layer: string, before: unknown[] | undefined, after: unknown[] | undefined): ActivityDetails {
  const counts: ValueChange = {
    what: words.recordsOf(layer),
    before: words.records(before?.length ?? 0),
    after: words.records(after?.length ?? 0),
  };
  return counts.before === counts.after ? { text: words.sameCount, changes: [counts] } : { changes: [counts] };
}

function layerNames(a: Record<string, unknown[]>, b: Record<string, unknown[]>): string[] {
  return [...new Set([...Object.keys(a), ...Object.keys(b)])].sort();
}

/**
 * The changes between two specifications of one project, as activity items with the time `at`.
 * `before` is the specification before a change the server announced, and `after` is the one
 * after it. The items are ordered by address. For one element they are in this order: the
 * element added or removed, its fields, its wants, its layers. Changes to the records at the
 * project's root come last. An added or removed element gives one item, which lists its fields;
 * its wants and layers give no further items. `simulated` marks every item, for sample data.
 */
export function diff(before: Spec, after: Spec, at: Date, simulated = false): ActivityItem[] {
  const items: ActivityItem[] = [];
  const stamp = at.getTime();
  const add = (type: ActivityType, scope: Address | null, element: Address | null, key: string, summary: string, details: ActivityDetails) =>
    items.push({ id: `${stamp}:${type}:${scope ?? ""}:${key}`, type, time: at, status: "recorded", scope, element, summary, details, simulated });

  const was = new Map(before.elements.map((element) => [element.address, element]));
  const is = new Map(after.elements.map((element) => [element.address, element]));
  const addresses = [...new Set([...was.keys(), ...is.keys()])].sort();

  const whole = (element: SpecElement, added: boolean): ValueChange[] => {
    const value = (text: string | null) => (added ? { before: null, after: text } : { before: text, after: null });
    return [
      { what: words.address, ...value(element.address) },
      ...FIELD_NAMES.filter((field) => element[field] !== undefined).map((field) => ({
        what: fieldWords[field],
        ...value(shown(field, element[field])),
      })),
      { what: words.wants, ...value(String(element.wants.length)) },
    ];
  };

  for (const address of addresses) {
    const old = was.get(address);
    const now = is.get(address);
    if (old === undefined && now !== undefined) {
      add("element-added", address, address, "", words.elementAdded(labelOf(now)), { changes: whole(now, true) });
      continue;
    }
    if (old !== undefined && now === undefined) {
      add("element-removed", address, null, "", words.elementRemoved(labelOf(old)), { changes: whole(old, false) });
      continue;
    }
    if (old === undefined || now === undefined) continue;
    const label = labelOf(now);

    for (const field of FIELD_NAMES) {
      if (old[field] === now[field]) continue;
      const word = fieldWords[field];
      const summary =
        old[field] === undefined ? words.fieldSet(word, label) : now[field] === undefined ? words.fieldCleared(word, label) : words.fieldChanged(word, label);
      add("field-changed", address, address, field, summary, {
        changes: [{ what: word, before: shown(field, old[field]), after: shown(field, now[field]) }],
      });
    }

    const wantsWas = new Map(old.wants.map((want) => [want.to, want]));
    const wantsIs = new Map(now.wants.map((want) => [want.to, want]));
    const parts = (want: SpecWant | undefined, other: SpecWant | undefined, added: boolean): ValueChange[] =>
      WANT_PARTS.filter((name) => (want?.[name] ?? "") !== (other?.[name] ?? "")).map((name) => ({
        what: partWords[name],
        before: part((added ? other : want)?.[name] ?? ""),
        after: part((added ? want : other)?.[name] ?? ""),
      }));
    for (const to of [...new Set([...wantsWas.keys(), ...wantsIs.keys()])].sort()) {
      const wantWas = wantsWas.get(to);
      const wantIs = wantsIs.get(to);
      if (wantWas === undefined && wantIs !== undefined) {
        add("want-added", address, address, to, words.wantAdded(label, to), { changes: parts(wantIs, undefined, true) });
      } else if (wantWas !== undefined && wantIs === undefined) {
        add("want-removed", address, address, to, words.wantRemoved(label, to), { changes: parts(wantWas, undefined, false) });
      } else if (wantWas !== undefined && wantIs !== undefined) {
        const changed = parts(wantWas, wantIs, false);
        if (changed.length > 0) {
          add("want-changed", address, address, to, words.wantChanged(label, to, changed.map((value) => value.what)), { changes: changed });
        }
      }
    }

    for (const layer of layerNames(old.layers, now.layers)) {
      if (sameRecords(old.layers[layer], now.layers[layer])) continue;
      add("layer-changed", address, address, layer, words.layerChanged(layer, label), layerChange(layer, old.layers[layer], now.layers[layer]));
    }
  }

  for (const layer of layerNames(before.rootLayers, after.rootLayers)) {
    if (sameRecords(before.rootLayers[layer], after.rootLayers[layer])) continue;
    add("layer-changed", null, null, layer, words.rootLayerChanged(layer), layerChange(layer, before.rootLayers[layer], after.rootLayers[layer]));
  }
  return items;
}

/** The pause of the Activity panel: the id of the newest item when the pause started, or null when there was no item. */
export interface Pause {
  lastId: string | null;
}

/** The items a paused or running list shows, oldest first, and the number held back. */
export interface Held {
  listed: ActivityItem[];
  waiting: number;
}

/**
 * Splits the items, oldest first, by a pause. With no pause every item is listed. With a pause,
 * the items up to the one the pause names are listed and the later ones wait. When the stream
 * no longer holds the named item, every item arrived after the pause started, so every item waits.
 */
export function hold(items: readonly ActivityItem[], pause: Pause | null): Held {
  if (pause === null) return { listed: [...items], waiting: 0 };
  const at = pause.lastId === null ? -1 : items.findIndex((item) => item.id === pause.lastId);
  return { listed: items.slice(0, at + 1), waiting: items.length - (at + 1) };
}

/**
 * The items, oldest first, that came after the item with this id. A null id gives every item.
 * When no item has the id, the result is every item: none of them was listed when the id was noted.
 */
export function after(items: readonly ActivityItem[], id: string | null): ActivityItem[] {
  if (id === null) return [...items];
  return items.slice(items.findIndex((item) => item.id === id) + 1);
}

/** The filters of the Activity panel. */
export interface ActivityFilter {
  /** One type, or null for every type. */
  type: ActivityType | null;
  /** When not null, only the items that affect the element at this address. */
  element: Address | null;
}

/** The items that pass the filter, in the order given. */
export function filterItems(items: readonly ActivityItem[], filter: ActivityFilter): ActivityItem[] {
  return items.filter(
    (item) => (filter.type === null || item.type === filter.type) && (filter.element === null || item.element === filter.element),
  );
}
