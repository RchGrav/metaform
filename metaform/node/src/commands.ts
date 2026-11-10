// Port of `metaform-core/src/commands.rs`. The commands of the `project-map` tool: `add`,
// `update`, `delete`, `orphaned` and addressed reads (R-5.1 to R-5.12, R-5.21 to R-5.25).
//
// A command takes a map and returns either a result, with a new map and its effect for a write,
// or throws a `Refusal`. The input map is never adjusted, so a refused command stores nothing
// (R-5.8).
//
// Not ported: the two JSON Schema checks (`contract.check_input`, `contract.check_element`). The
// shape check gives every message an agent reads (design document, section 2).

import type { Json, JsonObject } from "./json.ts";
import { equal, isArray, isObject, obj } from "./json.ts";
import type { Effect } from "./model.ts";
import { Element, MapModel, flatten, isWantUpdates } from "./model.ts";
import * as names from "./names.ts";
import { ROOT } from "./names.ts";
import * as reads from "./reads.ts";
import { Code, Refusal } from "./refusal.ts";
import * as rules from "./rules.ts";
import * as shape from "./shape.ts";
import * as specification from "./specification.ts";
import { Sorted, compare, count, trim } from "./text.ts";

/** What an accepted command produced. `write` is absent for a read. */
export type Outcome = {
  /** The result an agent receives. */
  result: Json;
  /** For a write: the new map, and the effect that turns the old map into it. */
  write?: { map: MapModel; effect: Effect };
};

/**
 * Perform one command on a map. The command's shape is checked by hand (`shape`), then its names
 * (R-4.11). Then it is applied to a copy of the map.
 */
export function execute(map: MapModel, command: Json): Outcome {
  shape.check(command);
  names.checkCommand(command);
  const [verb, body] = only(command);
  if (verb === "orphaned") {
    return { result: reads.orphaned(map) };
  }
  if (verb === "map") {
    return { result: reads.shallow(map) };
  }
  if (verb === "goto") {
    return { result: reads.goto(map, body as string) };
  }
  if (verb === "add" || verb === "update" || verb === "delete") {
    const [selector, supplied] = only(body);
    if (verb !== "delete" && isObject(supplied)) {
      rules.checkLayerValues(map, verb, selector, supplied);
    }
    const work = new Work(map);
    if (verb === "add") {
      work.addCommand = [selector, supplied as JsonObject];
      work.add(selector, supplied as JsonObject);
    } else if (verb === "update") {
      work.update(selector, supplied as JsonObject);
    } else {
      work.delete(selector, supplied);
    }
    const write = work.finish();
    // A successful write answers with its status alone. It does not repeat the command: the
    // agent sent it and has it. A refusal still repeats the command, so the agent sees what was
    // refused beside the reason.
    return { result: obj(["status", "ok"]), write };
  }
  if (verb.startsWith(".")) {
    return { result: reads.raw(map, verb) };
  }
  return { result: reads.read(map, verb, body) };
}

/** The single entry of an object that the shape check has already accepted. */
function only(value: Json): [string, Json] {
  return (value as JsonObject).entries().next().value as [string, Json];
}

/** A copy of the map being adjusted, and the addresses the write touched. */
class Work {
  before: MapModel;
  elements: Sorted<Element>;
  touched = new Set<string>();
  /** The addresses whose element in `elements` is this write's own copy. */
  private own = new Set<string>();
  /**
   * The wants this command wrote, in the order it wrote them: the holder, the other element, and
   * which of `why` and `how` the command supplied. `finish` checks their grammar.
   */
  private writtenWants: [string, string, string[]][] = [];
  /**
   * The selector and the body of the command when it is an `add`. A grammar refusal for a want
   * of an element the command made gives the command back as its remediation.
   */
  addCommand?: [string, JsonObject];

  constructor(before: MapModel) {
    this.before = before;
    this.elements = new Sorted(before.raw());
  }

  /** The touched addresses in order, as the Rust form's `BTreeSet` gives them. */
  private touchedInOrder(): string[] {
    return [...this.touched].sort(compare);
  }

  /** Create the address and every missing branch above it (R-5.4). */
  ensure(address: string): void {
    for (const prefix of names.prefixes(address)) {
      if (!this.elements.has(prefix)) {
        names.checkScope(prefix);
        this.elements.set(prefix, new Element());
        this.own.add(prefix);
        this.touched.add(prefix);
      }
    }
  }

  /** The element at an address, as a copy this write may adjust. The address was ensured. */
  elementMut(address: string): Element {
    this.touched.add(address);
    let element = this.elements.get(address) as Element;
    if (!this.own.has(address)) {
      element = element.copy();
      this.elements.set(address, element);
      this.own.add(address);
    }
    return element;
  }

  /**
   * Write a want. Supplied fields adjust the current record; the result needs every field
   * (R-5.6). The element the want names is created if it is not there (R-5.4).
   */
  writeWant(holder: string, other: string, change: Json): void {
    const record: JsonObject = new Map(this.elements.get(holder)?.wants.get(other));
    let written: string[] = [];
    if (isObject(change)) {
      written = ["why", "how"].filter((key) => change.has(key));
      for (const [key, value] of change) {
        record.set(key, value);
      }
    }
    const filled = (key: string): boolean => {
      const value = record.get(key);
      return typeof value === "string" && trim(value) !== "";
    };
    const missing = ["why", "how", "direction"].filter((key) => !filled(key));
    if (missing.length > 0) {
      const complete = new Map(record);
      for (const key of missing) {
        complete.set(key, `<${key}>`);
      }
      throw new Refusal(
        Code.WantIncomplete,
        `'${holder}' wants '${other}': the want has no ${missing.join(", ")}`,
        obj(["update", obj([holder, obj(["wants", obj([other, complete])])])]),
      );
    }
    this.ensure(other);
    this.elementMut(holder).wants.set(other, record);
    this.writtenWants.push([holder, other, written]);
  }

  writeWants(holder: string, wants: JsonObject): void {
    for (const [other, change] of wants) {
      this.writeWant(holder, other, change);
    }
  }

  /** `add` keeps what is there: arrays grow, and other values are written (R-5.5). */
  add(address: string, supplied: JsonObject): void {
    const suppliedElements = new Sorted<Element>();
    flatten(supplied, address, suppliedElements);
    for (const [at, given] of suppliedElements.entries()) {
      this.ensure(at);
      const element = this.elementMut(at);
      for (const [key, value] of given.fields) {
        const current = element.fields.get(key);
        if (value === null) {
          element.fields.delete(key);
        } else if (isArray(current) && isArray(value)) {
          element.fields.set(key, [...current, ...value]);
        } else {
          element.fields.set(key, value);
        }
      }
    }
    for (const [at, given] of suppliedElements.entries()) {
      for (const [other, record] of given.wants.entries()) {
        this.writeWant(at, other, record);
      }
    }
  }

  /** `update` writes to a path; `null` removes a field (R-5.5). */
  update(address: string, supplied: JsonObject): void {
    this.ensure(address);
    for (const [key, value] of supplied) {
      if (isObject(value) && key === "wants" && isWantUpdates(value)) {
        this.writeWants(address, value);
      } else if (value === null) {
        this.elementMut(address).fields.delete(key);
      } else if (isObject(value)) {
        this.update(names.join(address, key), value);
      } else {
        this.elementMut(address).fields.set(key, value);
      }
    }
  }

  /**
   * `delete` removes the named wants, or the element. An element that something still wants is
   * refused, with the command that removes the want (R-5.7, R-5.25).
   */
  delete(address: string, supplied: Json): void {
    if (!this.elements.has(address)) {
      return;
    }
    const wants = isObject(supplied) ? supplied.get("wants") : undefined;
    if (isArray(wants)) {
      for (const other of wants) {
        if (typeof other === "string" && this.elements.get(address)?.wants.has(other)) {
          this.elementMut(address).wants.delete(other);
          this.prune(other);
        }
      }
      return;
    }
    const receivers = MapModel.receivers(this.elements, address);
    if (receivers.length > 0) {
      const first = receivers[0];
      const message =
        receivers.length > 1
          ? `cannot delete '${address}': these elements still want it: ${receivers.map((r) => `'${r}'`).join(", ")}. Remove their wants first.`
          : `cannot delete '${address}': '${first}' still wants it. Remove that want first.`;
      throw new Refusal(
        Code.DependencyLock,
        message,
        obj(["delete", obj([first, obj(["wants", [address]])])]),
      );
    }
    // The deepest element beneath; of several at one depth, the last in order, as Rust's
    // `max_by_key` gives.
    let deepest: string | null = null;
    let depth = -1;
    for (const child of this.elements.keys()) {
      if (names.isBeneath(child, address) && count(child, ".") >= depth) {
        deepest = child;
        depth = count(child, ".");
      }
    }
    if (deepest !== null) {
      throw new Refusal(
        Code.ElementsBeneath,
        `cannot delete, '${address}', has elements beneath it`,
        obj(["delete", obj([deepest, obj()])]),
      );
    }
    const wanted = [...(this.elements.get(address) as Element).wants.keys()];
    this.remove(address);
    const parent = names.parent(address);
    if (parent !== null) {
      this.prune(parent);
    }
    for (const other of wanted) {
      this.prune(other);
    }
  }

  /**
   * Remove an element that a deletion left with nothing in it, and then each branch above it
   * that is left the same way: no fields, no wants, nothing beneath it and nothing that wants
   * it. A write creates the element a want names (R-5.4); when the last want that names it is
   * gone and it was never filled in, it goes too, so no empty address stays in the map.
   */
  prune(address: string): void {
    let branch: string | null = address;
    while (branch !== null && branch !== ROOT) {
      const at = branch;
      const empty = this.elements.get(at)?.isEmpty() ?? false;
      const hasChildren = this.elements.keys().some((child) => names.isBeneath(child, at));
      if (!empty || hasChildren || MapModel.receivers(this.elements, at).length > 0) {
        break;
      }
      this.remove(at);
      branch = names.parent(at);
    }
  }

  remove(address: string): void {
    this.elements.delete(address);
    this.touched.add(address);
  }

  /** Check every touched element against the rules that read the map, then build the effect. */
  finish(): { map: MapModel; effect: Effect } {
    this.normalizeSpecifications();
    const touched = this.touchedInOrder();
    for (const address of touched) {
      const element = this.elements.get(address);
      if (element !== undefined) {
        this.elements.set(address, element.inOrder());
      }
    }
    const defined = specification.definitions(MapModel.fromElements(this.elements)).map((d) => d.layer);
    for (const address of touched) {
      const element = this.elements.get(address);
      if (element === undefined) {
        continue;
      }
      this.checkLayersDefined(address, element, defined);
      rules.check(this.before, address, element);
      this.checkCollisions(address, element);
    }
    this.checkDefinitive();
    // The grammar of `why` and `how` is checked last, so every earlier refusal stays as it was.
    // The first want that breaks the rule, in the order the command wrote them, is reported.
    for (const [holder, other, written] of this.writtenWants) {
      rules.checkWantGrammar(this.before, this.elements, holder, other, written, this.addCommand);
    }
    const effect: Effect = new Sorted();
    for (const address of touched) {
      const after = this.elements.get(address);
      if (!Element.same(after, this.before.element(address))) {
        effect.set(address, after ?? null);
      }
    }
    return { map: MapModel.fromElements(this.elements), effect };
  }

  /**
   * Check the layer records a write adjusted, for every layer the map defines (R-6.24 to
   * R-6.26). Records must be a list and sit where records are allowed. Records of a
   * `markdown_blocks` layer are normalized and their heading rules checked; an empty list
   * removes the field. Records the write did not adjust are not checked again, so an intake
   * correction elsewhere is never refused because of them. The code-defined specification
   * layer definition can only be written as `specification.definition()` (R-6.11, R-6.22).
   */
  normalizeSpecifications(): void {
    if (this.touched.has(specification.DEFINITION_ADDRESS)) {
      const after = this.elements.get(specification.DEFINITION_ADDRESS);
      const before = this.before.element(specification.DEFINITION_ADDRESS);
      if (
        !Element.same(after, before) &&
        (after === undefined || !equal(after.fields, specification.definition()) || after.wants.size > 0)
      ) {
        throw new Refusal(
          Code.LayerDefinitionLocked,
          `'${specification.DEFINITION_ADDRESS}' is defined by the server; agents write its records at receiving elements, not its definition`,
          null,
        );
      }
    }
    const touched = this.touchedInOrder();
    const after = MapModel.fromElements(this.elements);
    const definesLayer = (element: Element | undefined): boolean =>
      typeof element?.fields.get("instruction") === "string";
    // A layer's field name is its key at every receiving element, so two definitions may not
    // share a last segment (R-6.24).
    for (const address of touched) {
      if (!definesLayer(this.elements.get(address)) || !specification.inLayerScope(address)) {
        continue;
      }
      const layer = names.lastSegment(address);
      for (const [existing, element] of after.elements()) {
        if (
          existing !== address &&
          specification.inLayerScope(existing) &&
          names.lastSegment(existing) === layer &&
          definesLayer(element)
        ) {
          throw new Refusal(
            Code.LayerNameCollision,
            `'${address}' would define the layer ${layer}, which '${existing}' already defines; a layer's last segment is its field name and must be unique`,
            obj(["update", obj([address, obj(["instruction", null])])]),
          );
        }
      }
    }
    const definitions = specification.definitions(after);
    const blocks: [string, string, specification.Block[]][] = [];
    for (const address of touched) {
      const element = this.elements.get(address);
      if (element === undefined) {
        continue;
      }
      for (const definition of definitions) {
        const layer = definition.layer;
        const value = element.fields.get(layer);
        if (value === undefined) {
          continue;
        }
        const before = this.before.element(address)?.fields.get(layer);
        if (before !== undefined && equal(before, value)) {
          continue;
        }
        const records = specification.records(layer, address, value);
        if (records.length > 0) {
          specification.checkAllowed(after, address, layer);
        }
        if (definition.format === specification.MARKDOWN_BLOCKS) {
          const found = specification.blocksOf(layer, address, value);
          specification.checkBlocks(address, layer, found);
          specification.checkCodes(after, address, layer, found);
          blocks.push([address, layer, found]);
        } else if (records.length === 0) {
          blocks.push([address, layer, []]);
        }
      }
    }
    for (const [address, layer, found] of blocks) {
      const fields = this.elementMut(address).fields;
      if (found.length === 0) {
        fields.delete(layer);
      } else {
        fields.set(layer, specification.toJson(found));
      }
    }
  }

  /**
   * A list at an element is a layer's records, so its name must be a layer: one defined beneath
   * `layer` (R-6.24) or a system layer (R-6.15). Only lists this write adjusted are checked, so
   * older data never blocks an unrelated write.
   */
  checkLayersDefined(address: string, element: Element, defined: string[]): void {
    const before = this.before.element(address);
    for (const [name, value] of element.fields) {
      const stored = before?.fields.get(name);
      if (
        !isArray(value) ||
        specification.SYSTEM_LAYERS.includes(name) ||
        defined.includes(name) ||
        (stored !== undefined && equal(stored, value))
      ) {
        continue;
      }
      throw new Refusal(
        Code.LayerNotRegistered,
        `'${name}' at '${address}' is not a layer. A list can be written only to a layer defined beneath the layer root, such as layer.document.specification, or to skills, memory or sources.`,
        obj(["map", obj()]),
      );
    }
  }

  /**
   * The stored map nests fields and child elements in one object, so a field cannot share a
   * name with a child element.
   */
  checkCollisions(address: string, element: Element): void {
    let clash: [string, string] | null = null;
    for (const key of element.fields.keys()) {
      if (this.elements.has(names.join(address, key))) {
        clash = [address, key];
        break;
      }
    }
    const parent = names.parent(address);
    if (clash === null && parent !== null) {
      const segment = names.lastSegment(address);
      if (this.elements.get(parent)?.fields.has(segment)) {
        clash = [parent, segment];
      }
    }
    if (clash === null) {
      return;
    }
    const [holder, key] = clash;
    throw new Refusal(
      Code.FieldElementCollision,
      `'${holder}': '${key}' cannot be both a field and an element beneath it`,
      obj(["update", obj([holder, obj([key, null])])]),
    );
  }

  /**
   * A project has one Definitive element (R-3.13). A write that would make a second is refused.
   * Elements under a root prefix do not count, because those prefixes are outside the project
   * (R-3.3, R-3.7).
   */
  checkDefinitive(): void {
    const definitive: string[] = [];
    for (const [address, element] of this.elements.entries()) {
      if (reads.isProjectDefinitive(address, element.fields.get("role"))) {
        definitive.push(address);
      }
    }
    if (definitive.length < 2) {
      return;
    }
    const existing = definitive.find((address) => !this.touched.has(address)) ?? definitive[0];
    const added = definitive.find((address) => address !== existing) ?? definitive[1];
    // The remediation gives the new element another role. It never removes the role of the
    // element that is Definitive already: an agent that followed it would lose the one element
    // that says what the project is.
    const otherRole = "<Supportive, Notable or Divergent>";
    const element = this.elements.get(added);
    let remediation: Json;
    if (this.before.element(added) === undefined && element !== undefined) {
      const view = element.view();
      view.set("role", otherRole);
      remediation = obj(["add", obj([added, view])]);
    } else {
      remediation = obj(["update", obj([added, obj(["role", otherRole])])]);
    }
    throw new Refusal(
      Code.RoleTaxonomyFailure,
      `'${added}' cannot be Definitive: '${existing}' already is, and a map has one Definitive element`,
      remediation,
    );
  }
}
