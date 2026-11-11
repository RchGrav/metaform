// Port of `metaform-core/src/names.rs`. Address rules and the conversion between the agent's
// snake_case and the stored camelCase (R-3.2, R-3.3, R-4.11). Agents see snake_case and full
// addresses; storage sees camelCase.

import type { Json, JsonObject } from "./json.ts";
import { isArray, isObject } from "./json.ts";
import { Code, Refusal } from "./refusal.ts";

/** The address of a map's root (R-5.9). */
export const ROOT = ".";

/** The valid root scopes (R-3.3). */
export const ROOT_SCOPES = ["code", "document", "media", "data", "collection", "upstream", "downstream", "layer"];

/**
 * The root prefixes (R-3.3): what follows them is not located in the project. `upstream` and
 * `downstream` are outside the project being mapped (R-3.7), and `layer` holds layer
 * definitions (R-6.24).
 */
export const ROOT_PREFIXES = ["upstream", "downstream", "layer"];

const UPPERCASE = /\p{Uppercase}/u;
const ALPHABETIC = /^\p{Alphabetic}/u;

/**
 * Whether an address belongs to the project itself: the root, or an element not under a root
 * prefix. The one-Definitive rule (R-3.13) counts only these elements.
 */
export function inProject(address: string): boolean {
  return address === ROOT || !ROOT_PREFIXES.includes(address.split(".")[0]);
}

export function toCamel(snake: string): string {
  let out = "";
  let upper = false;
  for (const c of snake) {
    if (c === "_") {
      upper = true;
    } else if (upper) {
      out += c.toUpperCase();
      upper = false;
    } else {
      out += c;
    }
  }
  return out;
}

export function toSnake(camel: string): string {
  let out = "";
  for (const c of camel) {
    out += UPPERCASE.test(c) ? `_${c.toLowerCase()}` : c;
  }
  return out;
}

/** Convert every segment of an address with `convert`. */
function mapAddress(address: string, convert: (segment: string) => string): string {
  if (address === ROOT) {
    return ROOT;
  }
  return address.split(".").map(convert).join(".");
}

/** Why a name would not survive storage, or `null` if it converts back exactly. */
export function segmentProblem(segment: string): string | null {
  if (UPPERCASE.test(segment)) {
    return "a name in uppercase is refused, not lowercased";
  }
  if (toSnake(toCamel(segment)) === segment) {
    return null;
  }
  if (segment.includes("__")) {
    return "repeated underscores do not survive storage";
  }
  if (segment.endsWith("_")) {
    return "a trailing underscore does not survive storage";
  }
  return "an underscore before a digit or symbol does not survive storage";
}

/**
 * The nearest name that survives storage: lowercased, single underscores, digits joined to the
 * word before them.
 */
export function suggestSegment(segment: string): string {
  let out = "";
  for (const word of segment.toLowerCase().split("_")) {
    if (word === "") {
      continue;
    }
    if (out !== "" && ALPHABETIC.test(word)) {
      out += "_";
    }
    out += word;
  }
  return out;
}

export function join(address: string, segment: string): string {
  return address === ROOT ? segment : `${address}.${segment}`;
}

/** The last segment of an address. */
export function lastSegment(address: string): string {
  return address.slice(address.lastIndexOf(".") + 1);
}

/** The parent of an address; `null` for the root. */
export function parent(address: string): string | null {
  if (address === ROOT) {
    return null;
  }
  const cut = address.lastIndexOf(".");
  return cut === -1 ? ROOT : address.slice(0, cut);
}

/** Every prefix of an address, the root first and the address itself last. */
export function prefixes(address: string): string[] {
  const out = [ROOT];
  if (address === ROOT) {
    return out;
  }
  let current = "";
  for (const segment of address.split(".")) {
    current = current === "" ? segment : `${current}.${segment}`;
    out.push(current);
  }
  return out;
}

/** Whether `child` lies beneath `address`. */
export function isBeneath(child: string, address: string): boolean {
  return (
    (address === ROOT && child !== ROOT) ||
    (child.length > address.length && child.startsWith(address) && child[address.length] === ".")
  );
}

/** Refuse a top-level element outside the root scopes (R-3.3). */
export function checkScope(address: string): void {
  const scope = address.split(".")[0];
  if (address === ROOT || ROOT_SCOPES.includes(scope)) {
    return;
  }
  throw new Refusal(
    Code.RootScopeNotAllowed,
    `'${address}': the root scope '${scope}' is not one of: ${ROOT_SCOPES.join(", ")}`,
    null,
  );
}

/** Checks every name in a command, building the corrected command as it goes. */
class NameCheck {
  problems: string[] = [];

  segment(segment: string, address: string): string {
    const why = segmentProblem(segment);
    if (why === null) {
      return segment;
    }
    this.problems.push(`'${address}': '${segment}': ${why}`);
    return suggestSegment(segment);
  }

  address(address: string): string {
    if (address === ROOT) {
      return ROOT;
    }
    return address
      .split(".")
      .map((segment) => this.segment(segment, address))
      .join(".");
  }

  fields(fields: JsonObject, address: string): Json {
    const out: JsonObject = new Map();
    for (const [key, value] of fields) {
      let fixed: Json;
      if (isArray(value) && key === "wants") {
        fixed = value.map((group) => this.wantGroup(group));
      } else if (isObject(value)) {
        fixed = this.fields(value, join(address, key));
      } else {
        fixed = value;
      }
      out.set(this.segment(key, address), fixed);
    }
    return out;
  }

  wantGroup(group: Json): Json {
    if (!isObject(group)) {
      return group;
    }
    const out: JsonObject = new Map();
    for (const [provider, record] of group) {
      let fixed = record;
      if (isObject(record)) {
        const renamed: JsonObject = new Map();
        for (const [key, value] of record) {
          renamed.set(this.segment(key, provider), value);
        }
        fixed = renamed;
      }
      out.set(this.address(provider), fixed);
    }
    return out;
  }
}

/**
 * Refuse a command holding a name that would not survive storage (R-4.11). The remediation is
 * the command with each such name corrected. The command has already passed the shape check.
 */
export function checkCommand(command: Json): void {
  if (!isObject(command) || command.size === 0) {
    return;
  }
  const [verb, body] = command.entries().next().value as [string, Json];
  const check = new NameCheck();
  let fixedBody: Json = body;
  if ((verb === "add" || verb === "update") && isObject(body)) {
    const selected: JsonObject = new Map();
    for (const [address, fields] of body) {
      const fixed = isObject(fields) ? check.fields(fields, address) : fields;
      selected.set(check.address(address), fixed);
    }
    fixedBody = selected;
  } else if (verb === "delete" && isObject(body)) {
    const selected: JsonObject = new Map();
    for (const [address, supplied] of body) {
      let fixed = supplied;
      if (isObject(supplied) && isArray(supplied.get("wants"))) {
        const renamed = new Map(supplied);
        const wants = supplied.get("wants") as Json[];
        renamed.set("wants", wants.map((want) => (typeof want === "string" ? check.address(want) : want)));
        fixed = renamed;
      }
      selected.set(check.address(address), fixed);
    }
    fixedBody = selected;
  } else if (verb === "goto" && typeof body === "string") {
    fixedBody = check.address(body);
  }
  let fixedVerb: string;
  if (["add", "update", "delete", "orphaned", "goto", "map", "help"].includes(verb)) {
    fixedVerb = verb;
  } else if (verb === ROOT) {
    fixedVerb = ROOT;
  } else if (verb.startsWith(".")) {
    fixedVerb = `.${check.address(verb.slice(1))}`;
  } else {
    fixedVerb = check.address(verb);
  }
  if (check.problems.length === 0) {
    return;
  }
  throw new Refusal(Code.NameRoundTripFailure, check.problems.join("; "), new Map([[fixedVerb, fixedBody]]));
}

/** An address or key in the stored form: every segment in camelCase (R-4.11). */
export function storedName(agentForm: string): string {
  return mapAddress(agentForm, toCamel);
}

/** An address or key in the agent's form: every segment in snake_case (R-4.11). */
export function agentName(storedForm: string): string {
  return mapAddress(storedForm, toSnake);
}
