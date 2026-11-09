/**
 * The command grammar of mcp-tools.proposed.json: add, update, delete, orphaned and addressed reads.
 * The form takes what the agent means, and the code does the work behind it. A refusal protects the data.
 * A failed command rolls back, so it leaves no partial change.
 */
import { explain, type Contract } from './contract.ts';
import { prefixes, type Element, type Fields, type Store, type Want } from './store.ts';
import { flatten, isObject, isWantUpdates, join, nest, view, type Json } from './tree.ts';

class CommandError extends Error {
  readonly remediation?: Json;

  constructor(message: string, remediation?: Json) {
    super(message);
    this.remediation = remediation;
  }
}

async function required(store: Store, address: string): Promise<Element> {
  const element = await store.get(address);
  if (element === null) throw new CommandError(`'${address}' does not exist`);
  return element;
}

function check(contract: Contract, element: Element): void {
  const technical = element.fields.technical_name;
  if (typeof technical === 'string') {
    const reversed = element.address.split('.').reverse().join(' ').replaceAll('_', ' ').split(' ').filter(Boolean);
    const words = technical.split(/\s+/).filter(Boolean);
    if (words.length === 0 || words.some((word, index) => word !== reversed[index])) {
      throw new CommandError(`'${element.address}': technical_name "${technical}" is not the leading words of "${reversed.join(' ')}"`);
    }
  }
  if (!contract.validElement(view(element))) {
    throw new CommandError(`'${element.address}': ${explain(contract.validElement.errors)}`);
  }
}

/** Write a want to its path. The remote address is created if it is not there yet. A want needs its three fields. */
async function writeWant(store: Store, address: string, provider: string, change: Partial<Want>): Promise<void> {
  const current = (await required(store, address)).wants.find((candidate) => candidate.provider === provider);
  const want = { ...current, ...change, provider };
  if (!want.why?.trim() || !want.how?.trim() || !want.direction) {
    throw new CommandError(`'${address}' wants '${provider}': a want needs why, how and direction`);
  }
  await store.ensure(provider);
  await store.setWant(address, want as Want);
}

/** `add` keeps what is there: arrays grow, and every other value is written. */
function merged(current: Fields, added: Fields): Fields {
  const fields = { ...current };
  for (const [key, value] of Object.entries(added)) {
    const existing = fields[key];
    fields[key] = Array.isArray(existing) && Array.isArray(value) ? [...existing, ...value] : value;
  }
  return fields;
}

async function add(store: Store, contract: Contract, address: string, supplied: Json): Promise<void> {
  const elements = flatten(supplied, address);
  for (const element of elements) {
    await store.ensure(element.address);
    const current = await required(store, element.address);
    await store.save(element.address, merged(current.fields, element.fields));
  }
  for (const element of elements) {
    for (const { provider, ...change } of element.wants) await writeWant(store, element.address, provider, change);
    check(contract, await required(store, element.address));
  }
}

/** `update` writes to a path. Whatever the path needs is created. `null` removes a field. */
async function update(store: Store, contract: Contract, address: string, supplied: Json): Promise<void> {
  await store.ensure(address);
  const fields = { ...(await required(store, address)).fields };
  for (const [key, value] of Object.entries(supplied)) {
    if (key === 'wants' && isWantUpdates(value)) {
      for (const [provider, change] of Object.entries(value)) await writeWant(store, address, provider, change as Partial<Want>);
    } else if (value === null) delete fields[key];
    else if (isObject(value)) await update(store, contract, join(address, key), value);
    else fields[key] = value;
  }
  await store.save(address, fields);
  check(contract, await required(store, address));
}

/** Remove namespace branches that the deletion left with nothing in them. */
async function prune(store: Store, address: string): Promise<void> {
  for (const prefix of prefixes(address).slice(1, -1).reverse()) {
    const branch = await store.get(prefix);
    const empty = branch !== null && Object.keys(branch.fields).length === 0 && branch.wants.length === 0;
    if (!empty || (await store.hasChildren(prefix)) || (await store.receivers(prefix)).length > 0) return;
    await store.remove(prefix);
  }
}

async function remove(store: Store, address: string, supplied: { wants?: string[] }): Promise<void> {
  if ((await store.get(address)) === null) return;
  if (supplied.wants !== undefined) {
    for (const provider of supplied.wants) await store.removeWant(address, provider);
    return;
  }
  const receivers = await store.receivers(address);
  if (receivers.length > 0) {
    const message =
      receivers.length > 1
        ? `cannot delete '${address}': these elements still want it: ${receivers.map((r) => `'${r}'`).join(", ")}. Remove their wants first.`
        : `cannot delete '${address}': '${receivers[0]}' still wants it. Remove that want first.`;
    throw new CommandError(message, {
      delete: { [receivers[0]]: { wants: [address] } },
    });
  }
  if (await store.hasChildren(address)) throw new CommandError(`cannot delete, '${address}', has elements beneath it`);
  await store.remove(address);
  await prune(store, address);
}

/** Every named element that nothing wants. The result does not mean that any of them should go. */
async function orphaned(store: Store): Promise<Json> {
  const elements = await store.all();
  const wanted = new Set(elements.flatMap((element) => element.wants.map((want) => want.provider)));
  const found: Json = {};
  for (const element of elements) {
    const named = element.address !== '' && Object.keys(element.fields).length > 0;
    if (named && !wanted.has(element.address)) found[element.address] = view(element);
  }
  return found;
}

/** An address and everything beneath it. `.` is the project root. */
async function read(store: Store, key: string): Promise<Json> {
  const address = key === '.' ? '' : key;
  if (address !== '') await required(store, address);
  const beneath = (await store.all()).filter((element) => address === ''
    || element.address === address || element.address.startsWith(`${address}.`));
  const relative = address === '' ? beneath : beneath.map((element) => (
    { ...element, address: element.address.slice(address.length + 1) }));
  return { [key]: nest(relative) };
}

async function execute(store: Store, contract: Contract, command: Json): Promise<Json> {
  const [[key, value]] = Object.entries(command);
  if (key === 'orphaned') return orphaned(store);
  if (key !== 'add' && key !== 'update' && key !== 'delete') return read(store, key);
  const [[selector, supplied]] = Object.entries(value as Record<string, Json>);
  const address = selector === '.' ? '' : selector;
  if (key === 'add') await add(store, contract, address, supplied);
  else if (key === 'update') await update(store, contract, address, supplied);
  else await remove(store, address, supplied as { wants?: string[] });
  return { ...command, status: 'ok' };
}

export interface Outcome {
  result: Json;
  failed: boolean;
}

export async function apply(store: Store, contract: Contract, command: unknown): Promise<Outcome> {
  if (!contract.validInput(command)) {
    const message = explain(contract.validInput.errors);
    return { failed: true, result: { ...(isObject(command) ? command : {}), status: 'error', message } };
  }
  try {
    return { failed: false, result: await store.transaction(() => execute(store, contract, command as Json)) };
  } catch (error) {
    if (!(error instanceof CommandError)) throw error;
    const remediation = error.remediation === undefined ? {} : { remediation: error.remediation };
    return { failed: true, result: { ...(command as Json), status: 'error', message: error.message, ...remediation } };
  }
}
