// Port of the parts of `metaform-store/src/lib.rs` that this form needs: the home and its format
// marker, `execute`, `ensure_defined`, `refusal_json` and `store_failure_json`.
//
// This form has no server and no writer thread. Each process opens the databases itself, and
// SQLite's write lock puts the writers of every process in a line (design document, section 4).

import { linkSync, mkdirSync, readFileSync, readdirSync, realpathSync, unlinkSync, writeFileSync } from "node:fs";
import { basename, join } from "node:path";

import { execute } from "./commands.ts";
import { ProjectDb, StoreError, asStoreError } from "./database.ts";
import type { Json, JsonObject } from "./json.ts";
import { equal, isObject, obj } from "./json.ts";
import type { MapModel } from "./model.ts";
import { Code, Refusal } from "./refusal.ts";
import type { Registered } from "./registry.ts";
import { Registry } from "./registry.ts";
import * as specification from "./specification.ts";

export { StoreError } from "./database.ts";

/** Marks a home this store format made. A home with another marker, or with files and no marker, is refused. */
export const FORMAT_FILE = "store.format";
const FORMAT = "sqlite-soa 1";

/** The id of a project's main map within the project's database. */
const MAIN_MAP = "main";

/** The marker's text without its line end, or `null` when the home has no marker. */
function readMarker(home: string): string | null {
  try {
    return readFileSync(join(home, FORMAT_FILE), "utf8").replace(/\r?\n$/, "");
  } catch (problem) {
    if ((problem as { code?: string }).code === "ENOENT") {
      return null;
    }
    throw problem;
  }
}

/**
 * Make sure the home is in this store's format, and mark a new home. Two engines must never
 * write one home (design document, section 3.1).
 */
function checkFormat(home: string): void {
  mkdirSync(home, { recursive: true });
  let marker = readMarker(home);
  if (marker === null) {
    // Another process that starts on the same new home writes its marker under a temporary
    // name first; that file is not data.
    const data = readdirSync(home).filter((name) => !/^store\.format\.\d+\.tmp$/.test(name));
    if (data.length === 0) {
      // The marker appears complete or not at all: it is written under another name and linked.
      const draft = join(home, `${FORMAT_FILE}.${process.pid}.tmp`);
      writeFileSync(draft, `${FORMAT}\n`);
      try {
        linkSync(draft, join(home, FORMAT_FILE));
      } catch (problem) {
        if ((problem as { code?: string }).code !== "EEXIST") {
          throw problem;
        }
      } finally {
        unlinkSync(draft);
      }
    }
    marker = readMarker(home);
    if (marker === null) {
      throw new StoreError(
        `${home} holds data this store did not write (no ${FORMAT_FILE}). Nothing was changed. Use another home (METAFORM_HOME or --home).`,
        true,
      );
    }
  }
  if (marker !== FORMAT) {
    throw new StoreError(
      `${home} holds a store in another format (${FORMAT_FILE} says "${marker}"); this form reads only "${FORMAT}". Nothing was changed. Use another home (METAFORM_HOME or --home).`,
      true,
    );
  }
}

/** The store for one home: the project registry, and each project's database, opened on first use. */
export class Store {
  private home: string;
  private registry: Registry;
  private open = new Map<string, ProjectDb>();
  /** Main maps whose server-defined layers are current in this process (`ensureDefined`). */
  private defined = new Set<string>();

  /** Open the store for `home`. Throws `StoreError` when the home is in another format. */
  constructor(home: string) {
    try {
      checkFormat(home);
      this.home = realpathSync(home);
      this.registry = new Registry(this.home);
    } catch (problem) {
      throw asStoreError(problem);
    }
  }

  close(): void {
    for (const db of this.open.values()) {
      db.close();
    }
    this.open.clear();
    this.registry.close();
  }

  /**
   * Register a project folder, or return the id it already has. The project's name is the last
   * segment of the folder's canonical path.
   */
  registerProject(folder: string): string {
    let source: string;
    try {
      source = realpathSync(folder);
    } catch (problem) {
      const missing = (problem as { code?: string }).code === "ENOENT";
      const reason = missing ? "No such file or directory (os error 2)" : (problem as Error).message;
      throw new StoreError(`${folder}: ${reason}`, true);
    }
    try {
      return this.registry.register(source, basename(source));
    } catch (problem) {
      throw asStoreError(problem);
    }
  }

  /** Every project registered in this home, by name. Registers nothing. */
  projects(): Registered[] {
    try {
      return this.registry.list();
    } catch (problem) {
      throw asStoreError(problem);
    }
  }

  /** A project's database, opened on first use. */
  database(project: string): ProjectDb {
    let db = this.open.get(project);
    if (db === undefined) {
      try {
        db = new ProjectDb(join(this.home, "projects", project, "project.db"));
      } catch (problem) {
        throw asStoreError(problem);
      }
      this.open.set(project, db);
    }
    return db;
  }

  /**
   * Perform one command of the Metaform tool on a project's main map. Returns the result, or
   * throws a `Refusal` or a `StoreError`.
   */
  execute(project: string, command: Json): Json {
    this.ensureDefined(project);
    const db = this.database(project);
    const verb = isObject(command) && command.size > 0 ? (command.keys().next().value as string) : null;
    if (verb !== "add" && verb !== "update" && verb !== "delete") {
      return execute(db.read(MAIN_MAP), command).result;
    }
    return db.write(MAIN_MAP, (map) => execute(map, command));
  }

  /**
   * Make a project's main map hold the server-defined layer definitions exactly as the code
   * defines them (R-6.24): the specification layer at `specification.DEFINITION_ADDRESS`. Runs
   * once for each main map in a process, before its first command, so `goto` always finds the
   * layer and the stored definition follows the code. When the definition is already current it
   * writes nothing.
   */
  ensureDefined(project: string): void {
    if (this.defined.has(project)) {
      return;
    }
    const db = this.database(project);
    if (definitionCommand(db.read(MAIN_MAP)) !== null) {
      try {
        // The map is read again under the write lock: another process may have written the
        // definition since the look above.
        db.write(MAIN_MAP, (map) => {
          const command = definitionCommand(map);
          return command === null ? { result: null } : execute(map, command);
        });
      } catch (problem) {
        if (problem instanceof Refusal) {
          throw new StoreError(
            `the server could not write its layer definition: ${specification.DEFINITION_ADDRESS}: ${problem.code}: ${problem.reason}`,
          );
        }
        throw problem;
      }
    }
    this.defined.add(project);
  }
}

/**
 * The `update` that makes the map's specification layer definition equal to
 * `specification.definition()`, or `null` when it already is. `update` merges fields, so a
 * stored field the definition no longer has is removed with `null` (R-5.5).
 */
function definitionCommand(map: MapModel): Json {
  const wanted = specification.definition();
  const current = map.element(specification.DEFINITION_ADDRESS);
  if (current !== undefined && equal(current.fields, wanted)) {
    return null;
  }
  const fields: JsonObject = new Map(wanted);
  for (const key of current?.fields.keys() ?? []) {
    if (!wanted.has(key)) {
      fields.set(key, null);
    }
  }
  return obj(["update", obj([specification.DEFINITION_ADDRESS, fields])]);
}

/** The JSON an agent receives for a refusal. */
export function refusalJson(command: Json, refusal: Refusal): JsonObject {
  const out: JsonObject = isObject(command) ? new Map(command) : new Map();
  out.set("status", "error");
  for (const [key, value] of refusal.toJson()) {
    out.set(key, value);
  }
  return out;
}

/**
 * A store failure as an agent receives it: the same structure as a refusal, with the code
 * `INTERNAL_ERROR`. The message is the store's own, followed by what to do before a retry: a
 * write may have been stored before the failure, and a repeated `add` can duplicate entries.
 */
export function storeFailureJson(command: Json, problem: unknown): JsonObject {
  const error = asStoreError(problem);
  const sentence = error.message.endsWith(".") ? error.message : `${error.message}.`;
  const message = error.nothingStored
    ? sentence
    : `${sentence} A write may or may not be stored; read the element before you retry it.`;
  return refusalJson(command, new Refusal(Code.InternalError, message, null));
}
