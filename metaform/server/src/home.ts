/**
 * The Metaform home: one main database, and one folder for each project.
 *
 *   ~/.metaform/                     METAFORM_HOME replaces this
 *     metaform.lbug                  the projects, and the global settings
 *     projects/<path><number>/
 *       source.txt                   the project's real path
 *       project.lbug                 the project's map, the same file name in every project
 *
 * A project is a node here. Its name lives only here, so a project database never says whose it is.
 * Nothing is written into a project's own folder. A folder name can be the same for two paths, so
 * lookups use the real path, and the number keeps the folders apart.
 *
 * A setting is declared in code. A setting at its default has nothing stored, so a new default
 * reaches it. Every setting lookup comes through `setting`, so a project override has one place to go.
 *
 * Step one only: the chassis takes over this database later. Until then a process opens it for a
 * lookup and closes it, because Ladybug allows one read-write process.
 */
import { existsSync, mkdirSync, realpathSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { basename, join } from 'node:path';
import lb from '@ladybugdb/core';
import { connect, query, type DatabaseSize } from './store.ts';

export interface Project {
  path: string;
  name: string;
  folder: string;
}

/**
 * Every setting of the system, with its default. A 64 MB pool could not hold one import of the
 * 40 KB canonical map. A process uses only the memory it needs, so a larger pool costs nothing until then.
 */
const SETTINGS = { 'database.buffer_pool_mb': 256, 'database.max_size_gb': 16 } as const;

export const DEFAULT_SIZE: DatabaseSize = {
  bufferPoolMb: SETTINGS['database.buffer_pool_mb'],
  maxSizeGb: SETTINGS['database.max_size_gb'],
};

export type SettingKey = keyof typeof SETTINGS;

export interface Setting {
  key: string;
  value: number;
  state: 'default' | 'set';
}

const SCHEMA = [
  'CREATE NODE TABLE IF NOT EXISTS Project(path STRING, name STRING, folder STRING, PRIMARY KEY(path))',
  'CREATE NODE TABLE IF NOT EXISTS Setting(key STRING, value STRING, PRIMARY KEY(key))',
];

const isSetting = (key: string): key is SettingKey => key in SETTINGS;

export function homePath(): string {
  return process.env.METAFORM_HOME ?? join(homedir(), '.metaform');
}

/** The full path with each separator replaced. */
function folderName(path: string): string {
  return path.replace(/[^A-Za-z0-9]/g, '-');
}

export class Home {
  private readonly database: lb.Database;
  private readonly connection: lb.Connection;

  private constructor(database: lb.Database, connection: lb.Connection) {
    this.database = database;
    this.connection = connection;
  }

  static async open(): Promise<Home> {
    mkdirSync(join(homePath(), 'projects'), { recursive: true });
    const { database, connection } = connect(join(homePath(), 'metaform.lbug'), DEFAULT_SIZE);
    for (const statement of SCHEMA) await query(connection, statement);
    return new Home(database, connection);
  }

  async close(): Promise<void> {
    await this.connection.close();
    await this.database.close();
  }

  async projects(): Promise<Project[]> {
    const rows = await query(this.connection, 'MATCH (p:Project) RETURN p.path AS path, p.name AS name, p.folder AS folder ORDER BY path');
    return rows as unknown as Project[];
  }

  /** The project of this folder, if it has one. */
  async find(source: string): Promise<Project | null> {
    const path = realpathSync(source);
    return (await this.projects()).find((project) => project.path === path) ?? null;
  }

  /** The project of this folder, created if it is not there yet. */
  async project(source: string, name?: string): Promise<Project> {
    const found = await this.find(source);
    if (found !== null) return found;
    const path = realpathSync(source);
    const project = { path, name: name ?? basename(path).replace(/[.\s]+/g, '-'), folder: this.newFolder(path) };
    mkdirSync(project.folder, { recursive: true });
    writeFileSync(join(project.folder, 'source.txt'), `${path}\n`);
    await query(this.connection, 'CREATE (p:Project {path: $path, name: $name, folder: $folder})', { ...project });
    return project;
  }

  private newFolder(path: string): string {
    for (let number = 1; ; number += 1) {
      const folder = join(homePath(), 'projects', `${folderName(path)}${String(number).padStart(3, '0')}`);
      if (!existsSync(folder)) return folder;
    }
  }

  /** The value of a setting: what is stored globally, or its default. */
  async setting(key: SettingKey): Promise<number> {
    const rows = await query(this.connection, 'MATCH (s:Setting {key: $key}) RETURN s.value AS value', { key });
    return rows.length > 0 ? Number(rows[0].value) : SETTINGS[key];
  }

  async settings(): Promise<Setting[]> {
    const stored = await query(this.connection, 'MATCH (s:Setting) RETURN s.key AS key, s.value AS value');
    const values = new Map(stored.map((row) => [String(row.key), Number(row.value)]));
    return Object.entries(SETTINGS).map(([key, value]) => (
      { key, value: values.get(key) ?? value, state: values.has(key) ? 'set' : 'default' }));
  }

  async set(key: string, value: number): Promise<void> {
    if (!isSetting(key)) throw new Error(`'${key}' is not a setting`);
    if (!Number.isFinite(value) || value <= 0) throw new Error(`'${key}' must be a number above 0`);
    await query(this.connection, 'MERGE (s:Setting {key: $key}) SET s.value = $value', { key, value: String(value) });
  }

  /** How large a project database may be, from the settings. */
  async size(): Promise<DatabaseSize> {
    return { bufferPoolMb: await this.setting('database.buffer_pool_mb'), maxSizeGb: await this.setting('database.max_size_gb') };
  }
}
