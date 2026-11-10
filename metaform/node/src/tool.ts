// Port of the parts of `metaform-server/src/tool.rs` that an agent's answers depend on: the
// tool's definition, `Presence`, and how one tool call becomes an answer. The definition comes
// from the contract (`metaform/mcp-tools.proposed.json`); this file adds no tool and adjusts no
// schema.
//
// Not ported: the map resource and its subscriptions, because this form has no change
// announcements (design document, section 2).

import { readFileSync } from "node:fs";

import type { Json, JsonObject } from "./json.ts";
import { equal, get, isArray, isObject, obj, parse, stringify } from "./json.ts";
import { Refusal } from "./refusal.ts";
import type { Store } from "./store.ts";
import { refusalJson, storeFailureJson } from "./store.ts";

const CONTRACT = new URL("../../mcp-tools.proposed.json", import.meta.url);

/** The one tool's definition from the contract: `name`, `description` and `inputSchema`. */
export function toolDefinition(): JsonObject {
  const tools = get(parse(readFileSync(CONTRACT, "utf8")), "tools");
  if (!isArray(tools) || tools.length !== 1) {
    throw new Error("the contract must declare exactly one tool");
  }
  const [definition] = tools;
  const text = (key: string): string => {
    const value = get(definition, key);
    return typeof value === "string" ? value : "";
  };
  const schema = get(definition, "inputSchema");
  return obj(
    ["name", text("name")],
    ["description", text("description")],
    ["inputSchema", isObject(schema) ? schema : obj()],
  );
}

/**
 * Sheet parts whose entries are the same wherever they appear, so each entry is delivered once
 * per context: the layer `instructions` (R-6.27).
 */
const ONCE_PER_CONTEXT = ["instructions"];

/**
 * Sheet parts delivered on every arrival, never held back: a layer's `guidance` at its
 * definition element, which is where an agent reads the guidance again after a reset (R-5.30).
 */
const ALWAYS = ["guidance"];

/** Where the agent is, and what `goto` already delivered in this context. */
export class Presence {
  at: string | null = null;
  private delivered = new Map<string, JsonObject>();
  private once: JsonObject = new Map();

  /**
   * Record an arrival and return only the parts of the sheet not yet delivered unchanged in
   * this context (R-5.30). The parts held back are named in `unchanged`, so an agent whose
   * context was reset can tell "nothing here" from "already delivered" and read them again.
   */
  arrive(sheet: Json): Json {
    if (!isObject(sheet)) {
      return sheet;
    }
    const given = sheet.get("at");
    const at = typeof given === "string" ? given : "";
    let seen = this.delivered.get(at);
    if (seen === undefined) {
      seen = new Map();
      this.delivered.set(at, seen);
    }
    const out = obj(["at", at]);
    const unchanged: Json[] = [];
    for (const [part, value] of sheet) {
      if (part === "at") {
        continue;
      }
      if (ALWAYS.includes(part)) {
        out.set(part, value);
        continue;
      }
      if (ONCE_PER_CONTEXT.includes(part)) {
        if (!isObject(value)) {
          continue;
        }
        const fresh: JsonObject = new Map();
        for (const [name, text] of value) {
          if (!equal(this.once.get(name), text)) {
            fresh.set(name, text);
          }
        }
        if (fresh.size === 0) {
          unchanged.push(part);
        } else {
          for (const [name, text] of fresh) {
            this.once.set(name, text);
          }
          out.set(part, fresh);
        }
        continue;
      }
      if (seen.has(part) && equal(seen.get(part), value)) {
        unchanged.push(part);
      } else {
        seen.set(part, value);
        out.set(part, value);
      }
    }
    if (unchanged.length > 0) {
      out.set("unchanged", unchanged);
    }
    this.at = at;
    return out;
  }
}

/** One agent's connection: the project it works on, the store, and its `Presence`. */
export class MapTool {
  definition: JsonObject;
  private store: Store;
  private project: string;
  private presence = new Presence();

  constructor(store: Store, project: string) {
    this.store = store;
    this.project = project;
    this.definition = toolDefinition();
  }

  get name(): string {
    return this.definition.get("name") as string;
  }

  /**
   * Perform one tool command. The answer is the result, a refusal or a store failure as compact
   * JSON text; `refused` is true for the last two.
   */
  call(command: JsonObject): { text: string; refused: boolean } {
    try {
      const result = this.store.execute(this.project, command);
      const answer = command.has("goto") ? this.presence.arrive(result) : result;
      return { text: stringify(answer), refused: false };
    } catch (problem) {
      if (problem instanceof Refusal) {
        return { text: stringify(refusalJson(command, problem)), refused: true };
      }
      return { text: stringify(storeFailureJson(command, problem)), refused: true };
    }
  }
}
