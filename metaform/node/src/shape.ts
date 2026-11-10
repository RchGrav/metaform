// Port of `metaform-core/src/shape.rs`, line for line. The shape of a command, checked by hand
// (R-5.24).
//
// `check` refuses a command that does not have the form the `project-map` tool takes. It reads
// only the command, never the map. Each message names a place the way an agent writes it:
// `'code.engine.game'`, `status at 'code.engine.game'`, `the want 'code.bus.data.event' at
// 'code.engine.game'`. This form has no schema check after this one.
//
// # Order of checks
//
// A command can have several problems. `check` reports the first one it finds, in this order:
//
// 1. The number of entries: a command is an object with one entry.
// 2. The command name: `add`, `update`, `delete`, `orphaned`, `goto` and `map` are commands. A
//    key that starts with a period is a raw dump. Any other key is an address to read.
// 3. The address. For `add`, `update` and `delete` the body must first be an object with one
//    entry, because that entry's key is the address.
// 4. The shape of the value at the address.
// 5. Each field, in the order the command gives them. An object value is an element beneath;
//    its fields are checked, in order, before the next field of the element above.
//
// In a want record the order is: the record is an object, the names it does not take, each field
// in the command's order, then the fields that are missing. In `delete`, the items of `wants` are
// checked in the command's order; for each item: it is text, it is not the root, it is an
// address, it is not a repeat.
//
// The rules C1 to W7 that these checks enforce are listed in the Rust file.

import type { Json, JsonObject } from "./json.ts";
import { copy, get, isArray, isObject, obj } from "./json.ts";
import { ROOT, join } from "./names.ts";
import { Code, Refusal } from "./refusal.ts";

const ONE_ENTRY =
  "a command has one entry: add, update, delete, orphaned, goto, map, an address to read, or a path that starts with a period for a raw dump";
const DELETE_FORM = 'delete takes {} to delete the element, or {"wants": ["<address>"]} to remove wants';
/** The fields that hold text (N2 to N5). */
const TEXT_FIELDS = ["technical_name", "name", "role", "status", "project", "uri"];
/** The words that belong to a want, not to an element (N6). `op`, `ef` and `ifd` are older names. */
const WANT_WORDS = ["why", "how", "direction", "op", "ef", "ifd"];
const WANT_FIELDS = ["why", "how", "direction"];
const DIRECTIONS = ["inbound", "outbound", "two-way"];
const LEGACY_STATUS = ["missing", "MISSING", "BKN", "broken", "todo", "TODO"];

/** Where a set of fields sits in the command. */
const Level = {
  /** The fields of the element that `add` names. */
  Add: 0,
  /** The fields of the element that `update` names. */
  Update: 1,
  /** The fields of an element beneath, written as an object value. */
  Beneath: 2,
} as const;
type LevelName = (typeof Level)[keyof typeof Level];

/** Refuse a command that does not have the form the tool takes. See the text above for the order. */
export function check(command: Json): void {
  const entry = oneEntry(command);
  if (entry === null) {
    throw refuse(ONE_ENTRY, null);
  }
  const [key, body] = entry;
  if (key === "map" || key === "orphaned") {
    if (isEmptyObject(body)) {
      return;
    }
    throw refuse(`${key} takes {}`, obj([key, obj()]));
  }
  if (key === "goto") {
    if (typeof body === "string" && (body === ROOT || isAddress(body))) {
      return;
    }
    if (typeof body === "string" && body !== "") {
      throw notAnAddress(body);
    }
    throw refuse('goto takes one address, such as {"goto": "code.engine.game"}', obj(["goto", "<address>"]));
  }
  if (key === "add" || key === "update" || key === "delete") {
    const selected = oneEntry(body);
    if (selected === null) {
      const first = isObject(body) && body.size > 0 ? (body.entries().next().value as [string, Json]) : null;
      throw refuse(
        `${key} takes one address; send one command for each element`,
        first === null ? null : accepted(obj([key, obj([first[0], first[1]])])),
      );
    }
    const [address, value] = selected;
    if (key === "delete") {
      checkDelete(address, value);
      return;
    }
    if (address !== ROOT && !isAddress(address)) {
      throw notAnAddress(address);
    }
    if (!isObject(value)) {
      throw refuse(`${key} takes an object of fields at '${address}'`, null);
    }
    if (value.size === 0) {
      throw refuse(`${key} needs at least one field at '${address}'`, null);
    }
    const level = key === "add" ? Level.Add : Level.Update;
    new Check(command).fields(value, address, [key, address], level);
    return;
  }
  if (key.startsWith(".")) {
    if (key !== ROOT && !isAddress(key.slice(1))) {
      throw notAnAddress(key);
    }
    if (!isEmptyObject(body)) {
      throw refuse("a raw dump takes {}", obj([key, obj()]));
    }
    return;
  }
  read(key, body);
}

/** The command being checked. A remediation is this command with one value corrected. */
class Check {
  command: Json;

  constructor(command: Json) {
    this.command = command;
  }

  /** The fields of one element (N1 to N10). `path` is the keys from the command to these fields. */
  fields(fields: JsonObject, address: string, path: string[], level: LevelName): void {
    for (const [key, value] of fields) {
      if (!isSegment(key)) {
        throw refuse(
          `'${key}' at '${address}' is not a field name: a name is one segment, with no periods, spaces, '$', '[' or ']'`,
          null,
        );
      }
      const here = [...path, key];
      if (key === "wants") {
        this.wants(value, address, here, level);
        continue;
      }
      if (isObject(value)) {
        this.fields(value, join(address, key), here, Level.Beneath);
      } else if (value === null && level === Level.Update) {
        // `null` removes a field of `update`'s own element (N8).
      } else if (isArray(value) && key !== "uri" && key !== "providers") {
        // A list is a layer's records; `commands` checks that the layer is defined.
      } else if (TEXT_FIELDS.includes(key)) {
        this.text(key, value, address, here);
      } else if (WANT_WORDS.includes(key)) {
        const record = wantPlaceholder();
        if (WANT_FIELDS.includes(key) && typeof value === "string") {
          record.set(key, value);
        }
        throw refuse(
          `${key} at '${address}' is not a field of an element; why, how and direction belong in a want`,
          obj(["update", obj([address, obj(["wants", obj(["<address>", record])])])]),
        );
      } else if (key === "providers") {
        throw refuse(
          `providers at '${address}' can hold only elements beneath it; wants holds what an element wants`,
          null,
        );
      }
    }
  }

  /** A value that is not an object, a list or an accepted `null`, at a field that holds text. */
  text(key: string, value: Json, address: string, path: string[]): void {
    const text = typeof value === "string" && !isBlank(value) ? value : null;
    if (text !== null && key === "status" && LEGACY_STATUS.includes(text)) {
      throw refuse(
        `status at '${address}' cannot be "${text}"; use un_built for functionality that is not built`,
        accepted(replaced(this.command, path, "un_built")),
      );
    }
    if (text !== null) {
      return;
    }
    const placeholder = key === "role" ? "<Definitive, Supportive, Notable or Divergent>" : `<${key}>`;
    throw refuse(`${key} at '${address}' must be text that is not blank`, replaced(this.command, path, placeholder));
  }

  /** The value of `wants` at an element (W1, N10). */
  wants(value: Json, holder: string, path: string[], level: LevelName): void {
    if (!isObject(value)) {
      throw refuse(
        `wants at '${holder}' must be an object of want records keyed by address`,
        replaced(this.command, path, obj(["<address>", wantPlaceholder()])),
      );
    }
    // Beneath the command's own element, `wants` may also be a branch of elements. It holds
    // want records when a value in it gives why, how or direction as a plain value.
    let holdsRecords = false;
    for (const record of value.values()) {
      if (
        WANT_FIELDS.some((field) => {
          const given = get(record, field);
          return given !== undefined && !isObject(given) && !isArray(given);
        })
      ) {
        holdsRecords = true;
        break;
      }
    }
    if (level === Level.Beneath && !holdsRecords) {
      this.fields(value, join(holder, "wants"), path, Level.Beneath);
      return;
    }
    for (const [other, record] of value) {
      if (other === ROOT) {
        throw refuse("the root cannot be wanted", null);
      }
      if (!isAddress(other)) {
        throw notAnAddress(other);
      }
      this.want(record, other, holder, [...path, other], level === Level.Update);
    }
  }

  /**
   * One want record (W2 to W7). `partial` is true at `update`'s own element, where a record
   * holds only the fields to adjust.
   */
  want(record: Json, other: string, holder: string, path: string[], partial: boolean): void {
    const place = `the want '${other}' at '${holder}'`;
    if (!isObject(record)) {
      throw refuse(
        `${place} must be a record with why, how and direction`,
        replaced(this.command, path, wantPlaceholder()),
      );
    }
    const extra = [...record.keys()].filter((name) => !WANT_FIELDS.includes(name));
    if (extra.length > 0) {
      let fixed = this.command;
      for (const name of extra) {
        fixed = replaced(fixed, [...path, name], undefined);
      }
      throw refuse(`${place} does not take: ${extra.join(", ")}`, accepted(fixed));
    }
    for (const [field, value] of record) {
      const here = [...path, field];
      if (field === "direction") {
        if (typeof value !== "string" || !DIRECTIONS.includes(value)) {
          throw refuse(
            `direction at ${place} must be inbound, outbound or two-way`,
            replaced(this.command, here, "<inbound, outbound or two-way>"),
          );
        }
      } else if (typeof value !== "string" || isBlank(value)) {
        throw refuse(`${field} at ${place} must be text that is not blank`, replaced(this.command, here, `<${field}>`));
      }
    }
    const missing = WANT_FIELDS.filter((field) => !record.has(field));
    if (partial && record.size === 0) {
      throw refuse(
        `${place} has no fields; give why, how or direction`,
        replaced(this.command, path, wantPlaceholder()),
      );
    }
    if (!partial && missing.length > 0) {
      // The same code and message as a want that an update leaves incomplete (R-5.6).
      let fixed = this.command;
      for (const field of missing) {
        fixed = replaced(fixed, [...path, field], `<${field}>`);
      }
      throw new Refusal(
        Code.WantIncomplete,
        `'${holder}' wants '${other}': the want has no ${missing.join(", ")}`,
        fixed,
      );
    }
  }
}

/** `delete` (D2 to D5). */
function checkDelete(address: string, value: Json): void {
  if (address === ROOT) {
    throw refuse("the root cannot be deleted", null);
  }
  if (!isAddress(address)) {
    throw notAnAddress(address);
  }
  if (!isObject(value)) {
    throw refuse(DELETE_FORM, null);
  }
  if (value.size === 0) {
    return;
  }
  const wants = value.get("wants");
  if (wants === undefined || value.size !== 1) {
    throw refuse(DELETE_FORM, null);
  }
  const remove = (wanted: string[]): Json => obj(["delete", obj([address, obj(["wants", wanted])])]);
  if (!isArray(wants) || wants.length === 0) {
    if (typeof wants === "string" && isAddress(wants)) {
      throw refuse(DELETE_FORM, remove([wants]));
    }
    throw refuse(DELETE_FORM, remove(["<address>"]));
  }
  const seen: string[] = [];
  for (const item of wants) {
    if (typeof item !== "string") {
      throw refuse(DELETE_FORM, remove(["<address>"]));
    }
    if (item === ROOT) {
      throw refuse("the root cannot be wanted", null);
    }
    if (!isAddress(item)) {
      throw notAnAddress(item);
    }
    if (seen.includes(item)) {
      const once: string[] = [];
      for (const other of wants) {
        if (typeof other === "string" && !once.includes(other)) {
          once.push(other);
        }
      }
      throw refuse(`delete names the want '${item}' more than once`, accepted(remove(once)));
    }
    seen.push(item);
  }
}

/** An addressed read (L1 to L4). */
function read(address: string, body: Json): void {
  if (!isAddress(address)) {
    throw notAnAddress(address);
  }
  const form = `a read names each layer with {} as its value, such as {"${address}": {"wants": {}}}`;
  if (!isObject(body)) {
    throw refuse(form, obj([address, obj()]));
  }
  for (const [name, value] of body) {
    if (!isSegment(name)) {
      throw refuse(
        `'${name}' is not a layer name: a layer name is one segment, with no periods, spaces, '$', '[' or ']'`,
        null,
      );
    }
    if (!isEmptyObject(value)) {
      const named: JsonObject = new Map();
      for (const layer of body.keys()) {
        named.set(layer, obj());
      }
      throw refuse(form, accepted(obj([address, named])));
    }
  }
}

function refuse(message: string, remediation: Json): Refusal {
  return new Refusal(Code.FieldMismatch, message, remediation);
}

function notAnAddress(text: string): Refusal {
  return refuse(`'${text}' is not an address: segments are joined by periods, with no spaces, '$', '[' or ']'`, null);
}

/** A corrected command, if this check accepts it. A remediation must not be refused in turn. */
function accepted(command: Json): Json {
  try {
    check(command);
    return command;
  } catch (problem) {
    if (problem instanceof Refusal) {
      return null;
    }
    throw problem;
  }
}

/** A want record with a placeholder for each value only the agent can supply. */
function wantPlaceholder(): JsonObject {
  return obj(["why", "<why>"], ["how", "<how>"], ["direction", "<direction>"]);
}

/** The single entry of an object, or `null` if the value is not an object with one entry. */
function oneEntry(value: Json): [string, Json] | null {
  if (!isObject(value) || value.size !== 1) {
    return null;
  }
  return value.entries().next().value as [string, Json];
}

function isEmptyObject(value: Json): boolean {
  return isObject(value) && value.size === 0;
}

/**
 * The command with the value at `path` replaced, or removed when `value` is `undefined`. Every
 * key of `path` but the last names an object in the command.
 */
function replaced(command: Json, path: string[], value: Json | undefined): Json {
  const out = copy(command);
  if (path.length === 0) {
    return out;
  }
  let at: Json | undefined = out;
  for (const key of path.slice(0, -1)) {
    at = get(at, key);
  }
  if (isObject(at)) {
    const last = path[path.length - 1];
    if (value === undefined) {
      at.delete(last);
    } else {
      at.set(last, value);
    }
  }
  return out;
}

/** One address segment: at least one character, and no period, `$`, `[`, `]` or space. */
function isSegment(text: string): boolean {
  return text !== "" && !NOT_IN_SEGMENT.test(text);
}

/** An address beneath the root: segments joined by periods. The root `.` is not one. */
function isAddress(text: string): boolean {
  return text.split(".").every(isSegment);
}

function isBlank(text: string): boolean {
  return ONLY_SPACE.test(text);
}

// The characters with the Unicode property White_Space, which the schemas' `\s` matches. They
// are listed, as in the Rust file, so that every form of Metaform uses the same set.
const SPACE = "\\u0009-\\u000d \\u0085\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000";
const NOT_IN_SEGMENT = new RegExp(`[.$\\[\\]${SPACE}]`);
const ONLY_SPACE = new RegExp(`^[${SPACE}]*$`);
