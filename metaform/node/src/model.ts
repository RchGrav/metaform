// Port of `metaform-core/src/model.rs`. The map model. In memory the map is flat, keyed by full
// address in the agent's snake_case form (R-4.12). The nested tree exists only in a raw dump.
//
// Not ported: `from_document`, `from_tree` and `to_document`, which serve the specification
// import and export that this form does not offer, and `child_map`, which no form sets.
//
// An `Element` is never adjusted after a map holds it. `commands` copies an element before it
// writes to it.

import type { Json, JsonObject } from "./json.ts";
import { equal, isArray, isObject } from "./json.ts";
import { ROOT, join } from "./names.ts";
import { Sorted, compare } from "./text.ts";

/** An element's own fields: scalars and native arrays. Objects are child elements, not fields. */
export type Fields = JsonObject;

/**
 * The intake fields, in R-6.15's order. They come first in an element; every other field follows,
 * sorted by name. One order makes an element's JSON the same after every reload and in every
 * form of Metaform, whatever order its fields were written in.
 */
export const FIELD_ORDER = ["technical_name", "name", "role", "uri", "status"];
/** The want-record fields, in R-6.17's order, first in a want record; any other follows by name. */
export const WANT_ORDER = ["why", "how", "direction"];

/** Whether `fields` is in canonical order: the names in `first`, in that order, then the rest by name. */
function isInOrder(fields: Fields, first: string[]): boolean {
  let rank = 0;
  let previous: string | null = null;
  for (const name of fields.keys()) {
    const at = first.indexOf(name);
    if (at !== -1) {
      if (previous !== null || at < rank) {
        return false;
      }
      rank = at + 1;
    } else {
      if (previous !== null && compare(previous, name) >= 0) {
        return false;
      }
      previous = name;
    }
  }
  return true;
}

/** `fields` in canonical order. The result is `fields` itself when it is already in order. */
function inOrder(fields: Fields, first: string[]): Fields {
  if (isInOrder(fields, first)) {
    return fields;
  }
  const out: Fields = new Map();
  for (const name of first) {
    const value = fields.get(name);
    if (value !== undefined) {
      out.set(name, value);
    }
  }
  for (const name of [...fields.keys()].filter((name) => !first.includes(name)).sort(compare)) {
    out.set(name, fields.get(name) as Json);
  }
  return out;
}

/** One element at one address (R-3.1). */
export class Element {
  fields: Fields;
  /** Want records keyed by the address of the other element (R-3.5). */
  wants: Sorted<Fields>;

  constructor(fields: Fields = new Map(), wants: Sorted<Fields> = new Sorted()) {
    this.fields = fields;
    this.wants = wants;
  }

  /** A copy whose fields and wants can be written without a change to this element. */
  copy(): Element {
    return new Element(new Map(this.fields), new Sorted(this.wants));
  }

  /**
   * The element with its fields and every want record in canonical order (`FIELD_ORDER`,
   * `WANT_ORDER`). The result is this element when it is already in order.
   */
  inOrder(): Element {
    const fields = inOrder(this.fields, FIELD_ORDER);
    let wants = this.wants;
    for (const [other, record] of this.wants.entries()) {
      const ordered = inOrder(record, WANT_ORDER);
      if (ordered !== record) {
        if (wants === this.wants) {
          wants = new Sorted(this.wants);
        }
        wants.set(other, ordered);
      }
    }
    return fields === this.fields && wants === this.wants ? this : new Element(fields, wants);
  }

  /** An element with nothing in it: a namespace branch that a write created. */
  isEmpty(): boolean {
    return this.fields.size === 0 && this.wants.size === 0;
  }

  /** The wants as the contract writes them: one dictionary keyed by provider address. */
  wantsJson(): JsonObject {
    return new Map(this.wants.entries());
  }

  /**
   * The fields an addressed read returns (R-5.10, R-5.21): scalar values only. Wants and
   * array-valued layers come back only when a read names them.
   */
  baseFields(): Fields {
    const out: Fields = new Map();
    for (const [name, value] of this.fields) {
      if (!isArray(value)) {
        out.set(name, value);
      }
    }
    return out;
  }

  /** The element's fields and wants, without child elements, in the agent's form. */
  view(): JsonObject {
    const out: JsonObject = new Map(this.fields);
    if (this.wants.size > 0) {
      out.set("wants", this.wantsJson());
    }
    return out;
  }

  /** Whether two elements hold the same fields and wants. The order of keys does not matter. */
  static same(a: Element | undefined, b: Element | undefined): boolean {
    if (a === b) {
      return true;
    }
    if (a === undefined || b === undefined || a.wants.size !== b.wants.size || !equal(a.fields, b.fields)) {
      return false;
    }
    for (const [other, record] of a.wants.entries()) {
      if (!equal(record, b.wants.get(other))) {
        return false;
      }
    }
    return true;
  }
}

/**
 * The final value of every element a write touched: the whole element, or `null` if removed.
 * The store writes it to the database as a difference from the map before the write.
 */
export type Effect = Sorted<Element | null>;

/** One map: a root at `.` and the elements beneath it. */
export class MapModel {
  private all: Sorted<Element>;

  private constructor(elements: Sorted<Element>) {
    this.all = elements;
  }

  /** An empty map: the root alone. */
  static empty(): MapModel {
    return MapModel.fromElements(new Sorted());
  }

  /**
   * A map from its elements, keyed by address in the agent's form. The root is added if it is
   * missing, and every element is put in canonical order. `elements` itself is not adjusted.
   */
  static fromElements(elements: Sorted<Element>): MapModel {
    const out = new Sorted(elements);
    if (!out.has(ROOT)) {
      out.set(ROOT, new Element());
    }
    for (const [address, element] of elements.entries()) {
      const ordered = element.inOrder();
      if (ordered !== element) {
        out.set(address, ordered);
      }
    }
    return new MapModel(out);
  }

  raw(): Sorted<Element> {
    return this.all;
  }

  /** The element at an address; `.` is the root. */
  element(address: string): Element | undefined {
    return this.all.get(address);
  }

  /** Every element, the root first, then by address. */
  elements(): Generator<[string, Element]> {
    return this.all.entries();
  }

  /** The nested map in the agent's form, without the project name. */
  toTree(): JsonObject {
    const root: JsonObject = new Map();
    for (const [address, element] of this.all.entries()) {
      let node = root;
      if (address !== ROOT) {
        for (const segment of address.split(".")) {
          let entry = node.get(segment);
          if (entry === undefined) {
            entry = new Map();
            node.set(segment, entry);
          }
          // A write that would make a field and an element share a name is refused, so the entry
          // is an object.
          node = entry as JsonObject;
        }
      }
      for (const [key, value] of element.view()) {
        node.set(key, value);
      }
    }
    return root;
  }

  /** The addresses of the elements whose wants name `address`. */
  static receivers(elements: Sorted<Element>, address: string): string[] {
    const out: string[] = [];
    for (const [holder, element] of elements.entries()) {
      if (holder !== address && element.wants.has(address)) {
        out.push(holder);
      }
    }
    return out;
  }

  /** Every address that some element wants. */
  wanted(): Set<string> {
    const out = new Set<string>();
    for (const element of this.all.values()) {
      for (const other of element.wants.keys()) {
        out.add(other);
      }
    }
    return out;
  }
}

/** A wants update: a dictionary keyed by provider address whose values change want fields. */
export function isWantUpdates(map: JsonObject): boolean {
  if (map.size === 0) {
    return false;
  }
  for (const change of map.values()) {
    if (!isObject(change) || !WANT_ORDER.some((field) => change.has(field))) {
      return false;
    }
  }
  return true;
}

/**
 * A value read as want records: one dictionary keyed by provider address whose values are all
 * want records (the contract's and the canonical map's form), or an older list of such objects.
 * Anything else named `wants` is a namespace branch, as in the stored-document schema.
 */
function readWants(value: Json): Sorted<Fields> | null {
  const isRecord = (record: Json): boolean =>
    isObject(record) && typeof record.get("why") === "string" && typeof record.get("how") === "string";
  let groups: JsonObject[];
  if (isArray(value)) {
    if (!value.every(isObject)) {
      return null;
    }
    groups = value as JsonObject[];
  } else if (isObject(value) && value.size > 0 && [...value.values()].every(isRecord)) {
    groups = [value];
  } else {
    return null;
  }
  const wants = new Sorted<Fields>();
  for (const group of groups) {
    for (const [other, record] of group) {
      if (!isObject(record)) {
        return null;
      }
      wants.set(other, record);
    }
  }
  return wants;
}

/** Split a nested object into one element per address. An object value is a child element. */
export function flatten(node: JsonObject, address: string, out: Sorted<Element>): void {
  const element = new Element();
  const children: [string, JsonObject][] = [];
  for (const [key, value] of node) {
    const wants = key === "wants" ? readWants(value) : null;
    if (wants !== null) {
      element.wants = wants;
    } else if (isObject(value)) {
      children.push([join(address, key), value]);
    } else {
      element.fields.set(key, value);
    }
  }
  out.set(address, element);
  for (const [childAddress, child] of children) {
    flatten(child, childAddress, out);
  }
}
