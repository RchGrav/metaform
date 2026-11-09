/**
 * The LadybugDB store of one project's map. Column names are the field names of metaform-canonical.json.
 *
 * Addresses are project-relative. The root element is stored at `.`, and callers know it as ''.
 * The database never says which project it is. The main database does that, see home.ts.
 *
 * Step one only: this process owns the database because the chassis does not exist yet.
 * Ladybug allows one read-write process, so the chassis takes over this ownership later.
 */
import lb from '@ladybugdb/core';

export type Fields = Record<string, unknown>;

export interface Want {
  provider: string;
  why: string;
  how: string;
  direction: string;
}

export interface Element {
  address: string;
  fields: Fields;
  wants: Want[];
}

/** Fields stored in their own column. Every other field is a native layer, kept whole in `layers`. */
const COLUMNS = ['id', 'name', 'name_length', 'role', 'uri', 'status'] as const;

/** Want columns keep their first names, goal, function and intent, so existing databases still open; they hold why, how and direction (R-3.4, R-3.6). */
const SCHEMA = [
  `CREATE NODE TABLE IF NOT EXISTS Element(
     address STRING, id STRING, name STRING, name_length INT64, role STRING,
     uri STRING, status STRING, layers STRING, PRIMARY KEY(address))`,
  'CREATE REL TABLE IF NOT EXISTS wants(FROM Element TO Element, goal STRING, `function` STRING, intent STRING, ice BOOLEAN)',
];

const ROOT = '.';

const ELEMENT_RETURN = [...COLUMNS, 'layers'].map((column) => `e.${column} AS ${column}`).join(', ');
const WANT_RETURN = 'a.address AS receiver, b.address AS provider, w.goal AS goal, w.`function` AS function, w.intent AS direction, w.ice AS ice';

/** Every prefix of an address, nearest the root first, including the root and the address itself. */
export function prefixes(address: string): string[] {
  if (address === '') return [''];
  const segments = address.split('.');
  return ['', ...segments.map((_, index) => segments.slice(0, index + 1).join('.'))];
}

function toFields(row: Fields): Fields {
  const fields: Fields = JSON.parse(String(row.layers ?? '{}'));
  for (const column of COLUMNS) {
    const value = row[column];
    if (value !== null && value !== undefined) fields[column] = column === 'name_length' ? Number(value) : value;
  }
  return fields;
}

function toWant(row: Fields): Want {
  const want: Want = {
    provider: String(row.provider),
    why: String(row.goal),
    how: String(row.function),
    direction: String(row.direction),
  };
  return want;
}

const stored = (address: string): string => (address === '' ? ROOT : address);
const relative = (address: string): string => (address === ROOT ? '' : address);

export interface DatabaseSize {
  bufferPoolMb: number;
  maxSizeGb: number;
}

/** Open a database with a bounded size. The default reserves 8 TB of address space, and one process fails at about 7 of those. */
export function connect(path: string, size: DatabaseSize): { database: lb.Database; connection: lb.Connection } {
  const database = new lb.Database(path, size.bufferPoolMb * 2 ** 20, true, false, size.maxSizeGb * 2 ** 30);
  return { database, connection: new lb.Connection(database) };
}

/** Run one statement and close its result. An unclosed result keeps its memory. */
export async function query(connection: lb.Connection, statement: string, parameters: Fields = {}): Promise<Fields[]> {
  const prepared = await connection.prepare(statement);
  const result = await connection.execute(prepared, parameters as never);
  const results = Array.isArray(result) ? result : [result];
  const rows = (await results[0].getAll()) as Fields[];
  for (const each of results) each.close();
  return rows;
}

export class Store {
  /** Every operation waits here, because Ladybug refuses a second write transaction instead of queuing it. */
  private queue: Promise<unknown> = Promise.resolve();
  private readonly database: lb.Database;
  private readonly connection: lb.Connection;

  private constructor(database: lb.Database, connection: lb.Connection) {
    this.database = database;
    this.connection = connection;
  }

  static async open(path: string, size: DatabaseSize): Promise<Store> {
    const { database, connection } = connect(path, size);
    const store = new Store(database, connection);
    for (const statement of SCHEMA) await query(connection, statement);
    return store;
  }

  private want(row: Fields): Want {
    return { ...toWant(row), provider: relative(String(row.provider)) };
  }

  async close(): Promise<void> {
    await this.queue.catch(() => undefined);
    await this.connection.close();
    await this.database.close();
  }

  /** Run `work` alone, in one transaction. Any throw rolls back everything it did. */
  transaction<T>(work: () => Promise<T>): Promise<T> {
    const run = async (): Promise<T> => {
      await query(this.connection, 'BEGIN TRANSACTION');
      try {
        const result = await work();
        await query(this.connection, 'COMMIT');
        return result;
      } catch (error) {
        // Ladybug has already ended a transaction that a failed statement aborted.
        await query(this.connection, 'ROLLBACK').catch(() => undefined);
        throw error;
      }
    };
    const result = this.queue.then(run, run);
    this.queue = result.catch(() => undefined);
    return result;
  }

  private run(statement: string, parameters: Fields = {}): Promise<Fields[]> {
    return query(this.connection, statement, parameters);
  }

  async get(address: string): Promise<Element | null> {
    const key = stored(address);
    const rows = await this.run(`MATCH (e:Element {address: $address}) RETURN ${ELEMENT_RETURN}`, { address: key });
    if (rows.length === 0) return null;
    const wants = await this.run(
      `MATCH (a:Element {address: $address})-[w:wants]->(b:Element) RETURN ${WANT_RETURN} ORDER BY provider`,
      { address: key },
    );
    return { address, fields: toFields(rows[0]), wants: wants.map((row) => this.want(row)) };
  }

  async all(): Promise<Element[]> {
    const rows = await this.run(`MATCH (e:Element) RETURN e.address AS address, ${ELEMENT_RETURN} ORDER BY address`);
    const elements = new Map<string, Element>();
    for (const row of rows) {
      const address = relative(String(row.address));
      elements.set(address, { address, fields: toFields(row), wants: [] });
    }
    const wants = await this.run(`MATCH (a:Element)-[w:wants]->(b:Element) RETURN ${WANT_RETURN} ORDER BY receiver, provider`);
    for (const row of wants) elements.get(relative(String(row.receiver)))?.wants.push(this.want(row));
    return [...elements.values()];
  }

  /** Create the address, the root and any missing namespace branches between them. */
  async ensure(address: string): Promise<void> {
    for (const prefix of prefixes(address)) {
      await this.run('MERGE (e:Element {address: $address})', { address: stored(prefix) });
    }
  }

  /** Replace an element's stored fields. Its wants are unchanged. */
  async save(address: string, fields: Fields): Promise<void> {
    const layers: Fields = { ...fields };
    const values: Fields = { address: stored(address) };
    for (const column of COLUMNS) {
      values[column] = layers[column] ?? null;
      delete layers[column];
    }
    values.layers = JSON.stringify(layers);
    const assignments = [...COLUMNS, 'layers'].map((column) => `e.${column} = $${column}`).join(', ');
    await this.run(`MATCH (e:Element {address: $address}) SET ${assignments}`, values);
  }

  async setWant(receiver: string, want: Want): Promise<void> {
    await this.removeWant(receiver, want.provider);
    await this.run(
      `MATCH (a:Element {address: $receiver}), (b:Element {address: $provider})
       CREATE (a)-[:wants {goal: $goal, \`function\`: $function, intent: $direction, ice: $ice}]->(b)`,
      {
        receiver: stored(receiver),
        provider: stored(want.provider),
        goal: want.why,
        function: want.how,
        direction: want.direction,
        ice: null,
      },
    );
  }

  async removeWant(receiver: string, provider: string): Promise<void> {
    await this.run(
      'MATCH (a:Element {address: $receiver})-[w:wants]->(b:Element {address: $provider}) DELETE w',
      { receiver: stored(receiver), provider: stored(provider) },
    );
  }

  /** The addresses of the elements that want this one. */
  async receivers(address: string): Promise<string[]> {
    const rows = await this.run(
      'MATCH (a:Element)-[:wants]->(b:Element {address: $address}) RETURN a.address AS receiver ORDER BY receiver',
      { address: stored(address) },
    );
    return rows.map((row) => relative(String(row.receiver)));
  }

  async hasChildren(address: string): Promise<boolean> {
    const rows = await this.run(
      'MATCH (e:Element) WHERE e.address STARTS WITH $prefix RETURN count(e) AS total',
      { prefix: `${address}.` },
    );
    return Number(rows[0].total) > 0;
  }

  async remove(address: string): Promise<void> {
    await this.run('MATCH (e:Element {address: $address}) DETACH DELETE e', { address: stored(address) });
  }
}
