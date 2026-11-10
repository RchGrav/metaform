// Port of `metaform-core/src/reads.rs`. Reads: an addressed read (R-5.10, R-5.21), the raw dump
// (R-5.34), `map` (R-5.11), `orphaned` (R-5.23) and the `goto` summary sheet (R-5.30). Reads
// never adjust the map, and every element is named by its full address (R-4.12).

import type { Json, JsonObject } from "./json.ts";
import { get, isArray, isObject, obj } from "./json.ts";
import type { MapModel } from "./model.ts";
import { ROOT, inProject } from "./names.ts";
import { Code, Refusal } from "./refusal.ts";
import * as specification from "./specification.ts";

/**
 * Role values that mark the Definitive element: `definitive`, R-3.13's name, which the intake
 * writes; `DE`, its abbreviation; `defining`, an earlier name of DE in the canonical map.
 */
export function isDefinitive(role: Json | undefined): boolean {
  if (typeof role !== "string") {
    return false;
  }
  // Rust compares with `eq_ignore_ascii_case`, so only the letters A to Z are lowered.
  const lowered = role.replace(/[A-Z]/g, (letter) => letter.toLowerCase());
  return lowered === "de" || lowered === "defining" || lowered === "definitive";
}

/**
 * The project's own Definitive element at an address: a Definitive role on an element inside the
 * project (`inProject`). An element under `upstream`, `downstream` or `layer` is outside the
 * project (R-3.3, R-3.7), so a Definitive role there does not count (R-3.13).
 */
export function isProjectDefinitive(address: string, role: Json | undefined): boolean {
  return inProject(address) && isDefinitive(role);
}

/**
 * `{"<address>": {}}` returns that element's own fields, keyed by its address: the form in which
 * data is entered (R-5.10). `{"<address>": {"<layer>": {}, ...}}` adds each named layer held
 * there (R-5.21). A named layer the element does not hold comes back empty when it is a layer
 * that applies there, and is left out otherwise.
 */
export function read(map: MapModel, address: string, body: Json): Json {
  const named = isObject(body) ? [...body.keys()] : [];
  const element = map.element(address);
  if (element === undefined) {
    throw notFound(address);
  }
  const fields = element.baseFields();
  for (const name of named) {
    const value = element.fields.get(name);
    if (name === "wants") {
      fields.set("wants", element.wantsJson());
    } else if (isArray(value)) {
      fields.set(name, value);
    } else if (
      specification.definitionOf(map, name) !== undefined &&
      specification.recordsAllowed(map, address)
    ) {
      fields.set(name, []);
    }
  }
  return obj([address, fields]);
}

/** A refusal for an address that holds no element. `map` lists the addresses that exist. */
function notFound(address: string): Refusal {
  return new Refusal(Code.NotFound, `'${address}' does not exist`, obj(["map", obj()]));
}

/**
 * `{".<path>": {}}` is a raw dump (R-5.34): the stored nested JSON at that path. `{".": {}}`
 * dumps the whole project; `{".code.server": {}}` dumps that element and everything beneath it.
 * Names are in the agent's form (R-4.11). The result is keyed by the path that was asked for.
 * Every layer is included, memory too.
 */
export function raw(map: MapModel, path: string): Json {
  let value: Json | undefined = map.toTree();
  if (path !== ROOT) {
    for (const segment of path.slice(1).split(".")) {
      value = get(value, segment);
      if (value === undefined) {
        throw notFound(path.slice(1));
      }
    }
  }
  return obj([path, value]);
}

/**
 * `{"map": {}}` returns the shallow graph (R-5.11): every address beneath the root, each want as
 * an edge from the element that holds it to the element it names, and the one Definitive
 * element. No fields and no layers.
 */
export function shallow(map: MapModel): Json {
  const addresses: Json[] = [];
  const edges: Json[] = [];
  let definitive: string | null = null;
  for (const [address, element] of map.elements()) {
    if (address !== ROOT) {
      addresses.push(address);
    }
    for (const other of element.wants.keys()) {
      edges.push([address, other]);
    }
    if (definitive === null && isProjectDefinitive(address, element.fields.get("role"))) {
      definitive = address;
    }
  }
  return obj(["addresses", addresses], ["edges", edges], ["definitive", definitive]);
}

/**
 * `{"orphaned": {}}` returns a bare dictionary keyed by address: each named element that nothing
 * wants maps to its own fields (R-5.23). Being orphaned does not mean an element should go.
 * Layer definitions are left out: nothing wants them, and the server keeps them (R-6.24), so
 * listing them would invite a delete that is refused.
 */
export function orphaned(map: MapModel): Json {
  const wanted = map.wanted();
  const out: JsonObject = new Map();
  for (const [address, element] of map.elements()) {
    if (
      address !== ROOT &&
      !specification.inLayerScope(address) &&
      element.fields.size > 0 &&
      !wanted.has(address)
    ) {
      out.set(address, element.baseFields());
    }
  }
  return out;
}

/**
 * Fields that are not layers in the summary sheet: `memory` has its own count, and `skills`
 * deliver their frontmatter.
 */
const NON_LAYER_FIELDS = ["memory", "skills"];

/**
 * `{"goto": "<address>"}` returns the summary sheet for the address (R-5.30): the element's own
 * fields and wants, every element that wants it (`wanted_by`) with that element's want, each
 * layer held there with its record count, the frontmatter of the skills at the address (only
 * when it has some), and its memory count. Counts, not records. Delivering it once per context
 * is the job of `Presence` in `tool.ts`, because it knows the connection.
 */
export function goto(map: MapModel, address: string): Json {
  const element = map.element(address);
  if (element === undefined) {
    throw notFound(address);
  }
  const wantedBy: JsonObject = new Map();
  for (const [holder, holderElement] of map.elements()) {
    const record = holder === address ? undefined : holderElement.wants.get(address);
    if (record !== undefined) {
      wantedBy.set(holder, record);
    }
  }
  const layers: JsonObject = new Map();
  for (const [key, value] of element.fields) {
    if (isArray(value) && !NON_LAYER_FIELDS.includes(key)) {
      layers.set(key, obj(["records", value.length]));
    }
  }
  // Every defined layer is listed wherever its records are allowed, even with none yet, so the
  // agent sees where records are due once intake has placed the element (R-6.27).
  const defined = specification.recordsAllowed(map, address) ? specification.definitions(map) : [];
  for (const definition of defined) {
    if (!layers.has(definition.layer)) {
      layers.set(definition.layer, obj(["records", 0]));
    }
  }
  const skills: JsonObject = new Map();
  const held = element.fields.get("skills");
  for (const skill of isArray(held) ? held : []) {
    const front = get(skill, "frontmatter") ?? skill;
    const name = get(front, "name");
    if (typeof name === "string") {
      const entry: JsonObject = new Map();
      for (const key of ["name", "description"]) {
        const value = get(front, key);
        if (value !== undefined) {
          entry.set(key, value);
        }
      }
      const uri = get(skill, "uri");
      if (uri !== undefined) {
        entry.set("uri", uri);
      }
      skills.set(name, entry);
    }
  }
  const memory = element.fields.get("memory");
  const sheet = obj(
    ["at", address],
    ["element", element.baseFields()],
    ["wants", element.wantsJson()],
    ["wanted_by", wantedBy],
    ["layers", layers],
    ["memory", obj(["records", isArray(memory) ? memory.length : 0])],
  );
  if (skills.size > 0) {
    sheet.set("skills", skills);
  }
  // Where the rules for writing each listed layer are. The sheet names the place and does not
  // carry the rules: an agent that arrives here may never write the layer. `Presence` delivers
  // this part once per context (R-6.27).
  if (defined.length > 0) {
    const instructions: JsonObject = new Map();
    for (const d of defined) {
      instructions.set(d.layer, `Before you write ${d.layer}, goto ${d.address} for its rules.`);
    }
    sheet.set("instructions", instructions);
  }
  // At a layer's definition element, the sheet always carries that layer's guidance, so an agent
  // whose context was reset can read it again (R-5.30).
  const here = specification.definitions(map).find((d) => d.address === address);
  if (here !== undefined) {
    sheet.set("guidance", here.guidance());
    // The guidance holds the definition's instruction, so the sheet's `element` part leaves it
    // out: the same text does not arrive twice. An addressed read still returns it.
    (sheet.get("element") as Map<string, unknown>).delete("instruction");
  }
  return sheet;
}
