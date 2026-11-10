// One project's database: its maps as a structure of arrays in SQLite (design document
// `metaform/docs/designs/sqlite-forms.md`, sections 3.2, 3.3 and 4). It takes the place of the
// Rust form's `metaform-store/src/graph.rs` and `writer.rs`.
//
// Each scalar field has its own table `f_<name>` and each layer its own table `l_<name>`, keyed
// by element. No table holds an element as one record. A write stores only the difference
// between the map before the command and the map after it.

import { DatabaseSync } from "node:sqlite";
import type { StatementSync } from "node:sqlite";

import type { Outcome } from "./commands.ts";
import type { Json } from "./json.ts";
import { equal, isArray, parse, stringify } from "./json.ts";
import type { Effect } from "./model.ts";
import { Element, MapModel } from "./model.ts";
import { ROOT, agentName, parent, storedName, toCamel, toSnake } from "./names.ts";
import { Refusal } from "./refusal.ts";
import { Sorted, count } from "./text.ts";

/** How long a connection waits in line for the write lock, in milliseconds. */
const BUSY_TIMEOUT = 5000;

/** A store failure that is not a refusal of the command. */
export class StoreError extends Error {
  /** True when the failure came before any write, so nothing can have been stored. */
  nothingStored: boolean;

  constructor(message: string, nothingStored = false) {
    super(message);
    this.nothingStored = nothingStored;
  }
}

/** Whether an error is SQLite's answer that another connection holds the lock. */
function isBusy(problem: unknown): boolean {
  const code = (problem as { errcode?: number } | null)?.errcode;
  return typeof code === "number" && ((code & 0xff) === 5 || (code & 0xff) === 6);
}

/** A problem as a `StoreError`. A lock that stayed busy stored nothing. */
export function asStoreError(problem: unknown): StoreError {
  if (problem instanceof StoreError) {
    return problem;
  }
  if (isBusy(problem)) {
    return new StoreError("the database was busy for more than five seconds, so the command stored nothing", true);
  }
  const message = problem instanceof Error ? problem.message : String(problem);
  const fromSqlite = (problem as { code?: string } | null)?.code === "ERR_SQLITE_ERROR";
  return new StoreError(`${fromSqlite ? "sqlite" : "i/o"} error: ${message}`);
}

const pause = new Int32Array(new SharedArrayBuffer(4));

/**
 * Perform `action`, and try again while another connection holds the lock, for up to
 * `BUSY_TIMEOUT`. SQLite does not wait by itself in every case: a connection that sets the
 * journal mode of a new file can be refused at once.
 */
function patiently<T>(action: () => T): T {
  const end = Date.now() + BUSY_TIMEOUT;
  for (;;) {
    try {
      return action();
    } catch (problem) {
      if (!isBusy(problem) || Date.now() >= end) {
        throw problem;
      }
      Atomics.wait(pause, 0, 0, 20);
    }
  }
}

/** Open a database file with the settings every connection uses (design document, section 4). */
export function openDatabase(path: string): DatabaseSync {
  const db = new DatabaseSync(path, { timeout: BUSY_TIMEOUT });
  try {
    db.exec(`PRAGMA busy_timeout = ${BUSY_TIMEOUT}`);
    patiently(() => db.exec("PRAGMA journal_mode = WAL"));
    db.exec("PRAGMA synchronous = FULL");
    db.exec("PRAGMA foreign_keys = ON");
  } catch (problem) {
    db.close();
    throw problem;
  }
  return db;
}

/** Whether a table with exactly this name exists. */
export function tableExists(db: DatabaseSync, name: string): boolean {
  return db.prepare("SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = ?").get(name) !== undefined;
}

/** Perform `action` in one write transaction. A failure leaves nothing stored. */
export function transact<T>(db: DatabaseSync, action: () => T): T {
  db.exec("BEGIN IMMEDIATE");
  try {
    const result = action();
    db.exec("COMMIT");
    return result;
  } catch (problem) {
    try {
      db.exec("ROLLBACK");
    } catch {
      // SQLite has already ended the transaction.
    }
    throw problem;
  }
}

const SCHEMA = `
CREATE TABLE IF NOT EXISTS map     (id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS element (key     INTEGER PRIMARY KEY,
                                    map     TEXT    NOT NULL REFERENCES map(id),
                                    address TEXT    NOT NULL,
                                    parent  INTEGER REFERENCES element(key),
                                    UNIQUE (map, address));
CREATE TABLE IF NOT EXISTS wants   (element   INTEGER NOT NULL REFERENCES element(key) ON DELETE CASCADE,
                                    provider  INTEGER NOT NULL REFERENCES element(key),
                                    why       TEXT NOT NULL,
                                    how       TEXT NOT NULL,
                                    direction TEXT NOT NULL,
                                    PRIMARY KEY (element, provider)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS field   (name TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS layer   (name TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS holds   (element INTEGER NOT NULL REFERENCES element(key) ON DELETE CASCADE,
                                    layer   TEXT    NOT NULL REFERENCES layer(name),
                                    PRIMARY KEY (element, layer)) WITHOUT ROWID;
`;

/** A map as last read or written by this connection. */
type Snapshot = {
  /** `PRAGMA data_version` when the map was current. */
  version: number;
  map: MapModel;
  /** Each element's key in the `element` table, by address in the agent's form. */
  keys: Map<string, number>;
};

type Kind = "f" | "l";

export class ProjectDb {
  private db: DatabaseSync;
  private statements = new Map<string, StatementSync>();
  /** The quoted table of each field (`f`) and layer (`l`), by kind and stored name. */
  private tables = new Map<string, string>();
  private snapshots = new Map<string, Snapshot>();
  /** True while the open transaction has made a table, so a rollback must forget what is kept. */
  private madeTable = false;

  constructor(path: string) {
    this.db = openDatabase(path);
    if (!tableExists(this.db, "holds")) {
      transact(this.db, () => this.db.exec(SCHEMA));
    }
  }

  close(): void {
    this.statements.clear();
    this.db.close();
  }

  /** A statement, prepared the first time its text is used and kept. */
  private statement(sql: string): StatementSync {
    let found = this.statements.get(sql);
    if (found === undefined) {
      found = this.db.prepare(sql);
      this.statements.set(sql, found);
    }
    return found;
  }

  private dataVersion(): number {
    const row = this.statement("PRAGMA data_version").get() as { data_version: number };
    return row.data_version;
  }

  /**
   * The map as last committed. SQLite gives a new `data_version` when another connection
   * commits, so the kept map is loaded again only when the map may have been adjusted.
   */
  private current(mapId: string): Snapshot {
    const version = this.dataVersion();
    const kept = this.snapshots.get(mapId);
    if (kept !== undefined && kept.version === version) {
      return kept;
    }
    const loaded = this.load(mapId, version);
    this.snapshots.set(mapId, loaded);
    return loaded;
  }

  /** One read: the map in one committed state. */
  read(mapId: string): MapModel {
    try {
      const kept = this.snapshots.get(mapId);
      if (kept !== undefined && kept.version === this.dataVersion()) {
        return kept.map;
      }
      this.db.exec("BEGIN");
      try {
        return this.current(mapId).map;
      } finally {
        this.db.exec("COMMIT");
      }
    } catch (problem) {
      throw asStoreError(problem);
    }
  }

  /**
   * One write, as one transaction (design document, section 4). `perform` gets the map as last
   * committed and returns the command's outcome, or throws a `Refusal`. The lock is taken
   * before the map is read, so no other process writes between the read and the write. The
   * result is returned only after the commit (R-4.7).
   */
  write(mapId: string, perform: (map: MapModel) => Outcome): Json {
    try {
      this.db.exec("BEGIN IMMEDIATE");
    } catch (problem) {
      throw asStoreError(problem);
    }
    this.madeTable = false;
    try {
      const before = this.current(mapId);
      const outcome = perform(before.map);
      if (outcome.write === undefined || outcome.write.effect.size === 0) {
        this.db.exec("ROLLBACK");
        return outcome.result;
      }
      const keys = new Map(before.keys);
      this.persist(mapId, before.map, outcome.write.effect, keys);
      this.db.exec("COMMIT");
      this.snapshots.set(mapId, { version: before.version, map: outcome.write.map, keys });
      return outcome.result;
    } catch (problem) {
      try {
        this.db.exec("ROLLBACK");
      } catch {
        // SQLite has already ended the transaction.
      }
      if (this.madeTable) {
        this.tables.clear();
        this.statements.clear();
      }
      if (problem instanceof Refusal) {
        throw problem;
      }
      this.snapshots.delete(mapId);
      throw asStoreError(problem);
    }
  }

  /**
   * The quoted name of the table for a field or a layer, or `null` when it does not exist and
   * `create` is false. `name` is in the stored form.
   *
   * The table is `f_<name>` or `l_<name>`. SQLite ignores the case of ASCII letters in a table
   * name, so the stored names `fooBar` and `foobar` cannot both have such a table. The second
   * of two such names gets the table `f__<snake_case name>`: a stored name holds no underscore
   * and a snake_case name holds no uppercase letter, so that name is free. A table name cannot
   * hold the character U+0000; a period, which no name holds, takes its place.
   */
  private table(kind: Kind, name: string, create: boolean): string | null {
    const kept = this.tables.get(kind + name);
    if (kept !== undefined) {
      return kept;
    }
    const quote = (table: string): string => `"${table.replaceAll("\0", ".").replaceAll('"', '""')}"`;
    const bare = (table: string): string => table.replaceAll("\0", ".");
    const plain = `${kind}_${name}`;
    const second = `${kind}__${toSnake(name)}`;
    const exact = this.statement("SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = ?");
    for (const candidate of [plain, second]) {
      if (exact.get(bare(candidate)) !== undefined) {
        this.tables.set(kind + name, quote(candidate));
        return quote(candidate);
      }
    }
    if (!create) {
      return null;
    }
    const taken = this.statement(
      "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = ? COLLATE NOCASE",
    ).get(bare(plain));
    const table = quote(taken === undefined ? plain : second);
    this.madeTable = true;
    if (kind === "f") {
      this.db.exec(
        `CREATE TABLE ${table} (element INTEGER PRIMARY KEY REFERENCES element(key) ON DELETE CASCADE, value TEXT NOT NULL)`,
      );
      this.statement("INSERT OR IGNORE INTO field (name) VALUES (?)").run(name);
    } else {
      this.db.exec(
        `CREATE TABLE ${table} (element INTEGER NOT NULL REFERENCES element(key) ON DELETE CASCADE, ordinal INTEGER NOT NULL, data TEXT NOT NULL, PRIMARY KEY (element, ordinal)) WITHOUT ROWID`,
      );
      this.statement("INSERT OR IGNORE INTO layer (name) VALUES (?)").run(name);
    }
    this.tables.set(kind + name, table);
    return table;
  }

  /** The table of a field or layer that the catalog names. */
  private catalogued(kind: Kind, name: string): string {
    const table = this.table(kind, name, false);
    if (table === null) {
      throw new StoreError(`stored data is not in the expected form: the catalog names ${name}, which has no table`);
    }
    return table;
  }

  /** Read a map back as the flat map of elements that the commands work on (section 3.3). */
  private load(mapId: string, version: number): Snapshot {
    const elements = new Sorted<Element>();
    const keys = new Map<string, number>();
    const byKey = new Map<number, Element>();
    const addressOf = new Map<number, string>();
    type Row = Record<string, string | number>;
    for (const row of this.statement("SELECT key, address FROM element WHERE map = ?").all(mapId) as Row[]) {
      const address = agentName(row.address as string);
      const element = new Element();
      elements.set(address, element);
      keys.set(address, row.key as number);
      byKey.set(row.key as number, element);
      addressOf.set(row.key as number, address);
    }
    for (const { name } of this.statement("SELECT name FROM field").all() as Row[]) {
      const field = toSnake(name as string);
      const table = this.catalogued("f", name as string);
      for (const row of this.statement(`SELECT element, value FROM ${table}`).all() as Row[]) {
        byKey.get(row.element as number)?.fields.set(field, parse(row.value as string));
      }
    }
    // `holds` names every layer an element has, so a layer with no records is still a field.
    for (const row of this.statement("SELECT element, layer FROM holds").all() as Row[]) {
      byKey.get(row.element as number)?.fields.set(toSnake(row.layer as string), []);
    }
    for (const { name } of this.statement("SELECT name FROM layer").all() as Row[]) {
      const field = toSnake(name as string);
      const table = this.catalogued("l", name as string);
      const rows = this.statement(`SELECT element, data FROM ${table} ORDER BY element, ordinal`).all() as Row[];
      for (const row of rows) {
        const element = byKey.get(row.element as number);
        if (element === undefined) {
          continue;
        }
        let records = element.fields.get(field);
        if (!isArray(records)) {
          records = [];
          element.fields.set(field, records);
        }
        records.push(parse(row.data as string));
      }
    }
    const wants = this.statement(
      "SELECT w.element, w.provider, w.why, w.how, w.direction FROM wants w JOIN element e ON e.key = w.element WHERE e.map = ?",
    ).all(mapId) as Row[];
    for (const row of wants) {
      const holder = byKey.get(row.element as number);
      const other = addressOf.get(row.provider as number);
      if (holder !== undefined && other !== undefined) {
        holder.wants.set(other, new Map([["why", row.why], ["how", row.how], ["direction", row.direction]]));
      }
    }
    return { version, map: MapModel.fromElements(elements), keys };
  }

  /**
   * Store an effect as a difference (section 4, step 4): only the elements the command touched,
   * and for each one only the fields, wants and layer rows that are not as they were. `keys` is
   * the caller's copy, and gains and loses the keys of the elements made and removed.
   */
  private persist(mapId: string, before: MapModel, effect: Effect, keys: Map<string, number>): void {
    const insert = this.statement("INSERT INTO element (map, address, parent) VALUES (?, ?, ?)");
    if (!keys.has(ROOT)) {
      this.statement("INSERT OR IGNORE INTO map (id) VALUES (?)").run(mapId);
      keys.set(ROOT, insert.run(mapId, ROOT, null).lastInsertRowid as number);
    }
    // New elements first, in the order of their addresses, so that a parent has its key before
    // an element beneath it, and a want's provider has its key before the want is written.
    const made = new Set<string>();
    for (const [address, after] of effect.entries()) {
      if (after !== null && !keys.has(address)) {
        const above = keys.get(parent(address) as string) as number;
        keys.set(address, insert.run(mapId, storedName(address), above).lastInsertRowid as number);
        made.add(address);
      }
    }
    const removed: string[] = [];
    for (const [address, after] of effect.entries()) {
      if (after === null) {
        removed.push(address);
      } else {
        const old = made.has(address) ? undefined : before.element(address);
        this.writeElement(keys.get(address) as number, old, after, keys);
      }
    }
    // The deepest first, so that no element is removed before the elements beneath it.
    removed.sort((a, b) => count(b, ".") - count(a, "."));
    const remove = this.statement("DELETE FROM element WHERE key = ?");
    for (const address of removed) {
      const key = keys.get(address);
      if (key !== undefined) {
        remove.run(key);
        keys.delete(address);
      }
    }
  }

  /** Write the fields and wants of one element that differ from `old`. */
  private writeElement(key: number, old: Element | undefined, now: Element, keys: Map<string, number>): void {
    for (const [name, value] of now.fields) {
      const was = old?.fields.get(name);
      if (was !== undefined && equal(was, value)) {
        continue;
      }
      const stored = toCamel(name);
      if (was !== undefined && isArray(was) !== isArray(value)) {
        this.removeField(key, stored, was);
      }
      if (isArray(value)) {
        this.writeLayer(key, stored, isArray(was) ? was : null, value);
      } else {
        const table = this.table("f", stored, true);
        this.statement(
          `INSERT INTO ${table} (element, value) VALUES (?, ?) ON CONFLICT (element) DO UPDATE SET value = excluded.value`,
        ).run(key, stringify(value));
      }
    }
    for (const [name, was] of old?.fields ?? []) {
      if (!now.fields.has(name)) {
        this.removeField(key, toCamel(name), was);
      }
    }
    for (const [other, record] of now.wants.entries()) {
      const was = old?.wants.get(other);
      if (was !== undefined && equal(was, record)) {
        continue;
      }
      const [why, how, direction] = ["why", "how", "direction"].map((field) => record.get(field));
      if (typeof why !== "string" || typeof how !== "string" || typeof direction !== "string") {
        throw new StoreError(`the want '${other}' does not hold why, how and direction as text`);
      }
      this.statement(
        "INSERT INTO wants (element, provider, why, how, direction) VALUES (?, ?, ?, ?, ?) ON CONFLICT (element, provider) DO UPDATE SET why = excluded.why, how = excluded.how, direction = excluded.direction",
      ).run(key, keys.get(other) as number, why, how, direction);
    }
    for (const other of old?.wants.keys() ?? []) {
      if (!now.wants.has(other)) {
        this.statement("DELETE FROM wants WHERE element = ? AND provider = ?").run(key, keys.get(other) as number);
      }
    }
  }

  /**
   * Write a layer's records as rows in order. The rows that `was` and `now` share at the start
   * stay as they are, so appending a record writes one row.
   */
  private writeLayer(key: number, stored: string, was: Json[] | null, now: Json[]): void {
    const table = this.table("l", stored, true);
    if (was === null) {
      this.statement("INSERT INTO holds (element, layer) VALUES (?, ?)").run(key, stored);
    }
    let same = 0;
    while (was !== null && same < was.length && same < now.length && equal(was[same], now[same])) {
      same += 1;
    }
    if (was !== null && was.length > same) {
      this.statement(`DELETE FROM ${table} WHERE element = ? AND ordinal >= ?`).run(key, same);
    }
    const insert = this.statement(`INSERT INTO ${table} (element, ordinal, data) VALUES (?, ?, ?)`);
    for (let ordinal = same; ordinal < now.length; ordinal += 1) {
      insert.run(key, ordinal, stringify(now[ordinal]));
    }
  }

  /** Remove one field of an element: its scalar row, or its layer rows and its `holds` row. */
  private removeField(key: number, stored: string, was: Json): void {
    if (isArray(was)) {
      this.statement(`DELETE FROM ${this.catalogued("l", stored)} WHERE element = ?`).run(key);
      this.statement("DELETE FROM holds WHERE element = ? AND layer = ?").run(key, stored);
    } else {
      this.statement(`DELETE FROM ${this.catalogued("f", stored)} WHERE element = ?`).run(key);
    }
  }
}
