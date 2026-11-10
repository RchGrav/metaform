// Port of `metaform-store/src/registry.rs`. The project registry in the core database,
// `metaform.db`. It holds each project's name and source folder. A project's own database never
// stores the project's name (R-4.1).

import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { basename, join } from "node:path";
import type { DatabaseSync } from "node:sqlite";

import { openDatabase, tableExists, transact } from "./database.ts";
import { compare } from "./text.ts";

/** One registered project: its id (the folder under `projects/`), its name and its source folder. */
export type Registered = { id: string; name: string; folder: string };

export class Registry {
  private db: DatabaseSync;
  private home: string;

  constructor(home: string) {
    this.home = home;
    this.db = openDatabase(join(home, "metaform.db"));
    if (!tableExists(this.db, "project")) {
      transact(this.db, () =>
        this.db.exec(
          "CREATE TABLE IF NOT EXISTS project (id TEXT PRIMARY KEY, source TEXT, name TEXT)",
        ),
      );
    }
  }

  close(): void {
    this.db.close();
  }

  private find(source: string): string | null {
    const row = this.db.prepare("SELECT id FROM project WHERE source = ?").get(source) as { id: string } | undefined;
    return row === undefined ? null : row.id;
  }

  /**
   * Register `source`, a canonical folder path, under `name`, or return the id it already has.
   * The id is the path with every character that is not an ASCII letter or digit replaced by
   * `-`, followed by a three-digit number, the first that is free. Nothing is written into the
   * project's own folder.
   */
  register(source: string, name: string): string {
    const found = this.find(source);
    if (found !== null) {
      return found;
    }
    // The write lock is taken before the second look, so two processes that register one folder
    // at the same time give it one id.
    return transact(this.db, () => {
      const again = this.find(source);
      if (again !== null) {
        return again;
      }
      let encoded = "";
      for (const c of source) {
        encoded += /^[A-Za-z0-9]$/.test(c) ? c : "-";
      }
      const projects = join(this.home, "projects");
      let id = "";
      for (let n = 1; ; n += 1) {
        id = `${encoded}${String(n).padStart(3, "0")}`;
        if (!existsSync(join(projects, id))) {
          break;
        }
      }
      const folder = join(projects, id);
      mkdirSync(folder, { recursive: true });
      writeFileSync(join(folder, "source.txt"), `${source}\n`);
      this.db.prepare("INSERT INTO project (id, source, name) VALUES (?, ?, ?)").run(id, source, name);
      return id;
    });
  }

  /** Every registered project, by name and then id. Reads only; registers nothing. */
  list(): Registered[] {
    const rows = this.db.prepare("SELECT id, name, source FROM project").all() as {
      id: string;
      name: string | null;
      source: string;
    }[];
    const projects = rows.map((row) => ({ id: row.id, name: row.name ?? basename(row.source), folder: row.source }));
    return projects.sort((a, b) => compare(a.name, b.name) || compare(a.id, b.id));
  }
}
