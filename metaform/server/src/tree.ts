/** Convert between the nested JSON document and stored elements. Storage layout never reaches the caller. */
import type { Element, Fields, Store, Want } from './store.ts';

export type Json = Record<string, unknown>;

export function isObject(value: unknown): value is Json {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isWantRecord(value: unknown): boolean {
  return isObject(value) && typeof value.why === 'string' && typeof value.how === 'string';
}

/**
 * Read want records. The contract form is one dictionary keyed by provider address, as the canonical map
 * keeps it; an object is read as wants only when every value is a want record. Any other object named
 * `wants` is a namespace branch. An older list of address-keyed objects is still read.
 */
export function readWants(value: unknown): Want[] | null {
  const groups = Array.isArray(value) ? value : isObject(value) ? [value] : null;
  if (groups === null || !groups.every(isObject)) return null;
  const entries = (groups as Json[]).flatMap((group) => Object.entries(group));
  if (!Array.isArray(value) && (entries.length === 0 || !entries.every(([, record]) => isWantRecord(record)))) {
    return null;
  }
  return entries.map(([provider, record]) => ({ provider, ...(record as Omit<Want, 'provider'>) }));
}

export function writeWants(wants: Want[]): Json {
  return Object.fromEntries(wants.map(({ provider, ...record }) => [provider, record]));
}

/** A wants update: a dictionary keyed by provider address whose values change want fields. */
export function isWantUpdates(value: unknown): value is Record<string, Json> {
  return isObject(value) && Object.keys(value).length > 0 && Object.values(value).every(
    (change) => isObject(change) && ['why', 'how', 'intent'].some((field) => field in change));
}

/** The element as a caller sees it: its own fields and wants, without child elements. */
export function view(element: Element): Json {
  return element.wants.length > 0 ? { ...element.fields, wants: writeWants(element.wants) } : { ...element.fields };
}

export function join(address: string, segment: string): string {
  return address === '' ? segment : `${address}.${segment}`;
}

/** Split a nested object into one stored element per namespace location. */
export function flatten(node: Json, address: string): Element[] {
  const fields: Fields = {};
  const children: Element[] = [];
  let wants: Want[] = [];
  for (const [key, value] of Object.entries(node)) {
    const records = key === 'wants' ? readWants(value) : null;
    if (records !== null) wants = records;
    else if (isObject(value)) children.push(...flatten(value, join(address, key)));
    else fields[key] = value;
  }
  return [{ address, fields, wants }, ...children];
}

export function nest(elements: Element[]): Json {
  const root: Json = {};
  for (const element of elements) {
    let node = root;
    if (element.address !== '') {
      for (const segment of element.address.split('.')) {
        node[segment] ??= {};
        node = node[segment] as Json;
      }
    }
    Object.assign(node, view(element));
  }
  return root;
}

/** A document has one top-level key, the project name, and the project is the object under it. */
export function projectIn(document: Json): [string, Json] {
  const [project, root, ...others] = Object.entries(document).flat();
  if (typeof project !== 'string' || !isObject(root) || others.length > 0) {
    throw new Error('A document must have one top-level key, the project name');
  }
  return [project, root];
}

/** Load a nested document as one transaction. Returns the wants whose provider does not exist, and stores nothing then. */
export async function importProject(store: Store, document: Json): Promise<string[]> {
  const [, root] = projectIn(document);
  const elements = flatten(root, '');
  const known = new Set(elements.map((element) => element.address));
  const missing = elements.flatMap((element) =>
    element.wants.filter((want) => !known.has(want.provider)).map((want) => `${element.address} -> ${want.provider}`));
  if (missing.length > 0) return missing;
  await store.transaction(async () => {
    for (const element of elements) {
      await store.ensure(element.address);
      await store.save(element.address, element.fields);
    }
    for (const element of elements) {
      for (const want of element.wants) await store.setWant(element.address, want);
    }
  });
  return [];
}

/** The project's name comes from the main database, because the store does not hold it. */
export async function exportProject(store: Store, name: string): Promise<Json> {
  return { [name]: nest(await store.transaction(() => store.all())) };
}
