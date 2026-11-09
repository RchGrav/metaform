/** Contract checks through the public interface: a real MCP client talking to the real server over stdio. */
import assert from 'node:assert/strict';
import { copyFileSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { after, before, test } from 'node:test';
import { execFileSync } from 'node:child_process';
import { Client } from '@modelcontextprotocol/client';
import { StdioClientTransport } from '@modelcontextprotocol/client/stdio';
import { renderSpecification } from '../src/specify.ts';

const root = new URL('../../', import.meta.url);
const read = (file: string) => JSON.parse(readFileSync(new URL(file, root), 'utf8'));
const main = new URL('../src/main.ts', import.meta.url).pathname;
const example = read('intake-example.json');
const examples = read('tool-examples.json');
const registry = read('mcp-tools.proposed.json');

let folder: string;
let index = 0;

before(() => {
  folder = mkdtempSync(join(tmpdir(), 'topogee-'));
  process.env.METAFORM_HOME = join(folder, 'home');
});
after(() => { rmSync(folder, { recursive: true, force: true }); });

function source(name = `project-${index++}`): string {
  const path = join(folder, name);
  mkdirSync(path, { recursive: true });
  return path;
}

function database(seed?: string): string {
  const path = source();
  if (seed) execFileSync('node', [main, path, '--import', seed], { stdio: 'pipe' });
  return path;
}

const cli = (...args: string[]) => execFileSync('node', [main, ...args], { encoding: 'utf8', stdio: 'pipe' });

async function connect(path: string) {
  const client = new Client({ name: 'contract-test', version: '0.0.0' });
  await client.connect(new StdioClientTransport({ command: 'node', args: [main, path], env: process.env as Record<string, string> }));
  const call = async (command: unknown) => {
    const result = await client.callTool({ name: registry.tools[0].name, arguments: command as Record<string, unknown> });
    const text = (result.content as { text: string }[])[0].text;
    return { error: Boolean(result.isError), body: JSON.parse(text) };
  };
  return { client, call };
}

const exported = (path: string) => JSON.parse(cli(path, '--export'));
const seed = new URL('intake-example.json', root).pathname;
const canonical = new URL('metaform-canonical.json', root).pathname;

test('tools/list offers exactly the one contract tool, schema unchanged', async () => {
  const { client } = await connect(database(seed));
  const { tools } = await client.listTools();
  assert.equal(tools.length, 1);
  assert.equal(tools[0].name, registry.tools[0].name);
  assert.deepEqual(tools[0].inputSchema, registry.tools[0].inputSchema);
  await client.close();
});

test('the owner sequence gives the documented results', async () => {
  const { client, call } = await connect(database(seed));
  const [, deleteElement, deleteWant, orphaned, removeRole, readElement] = examples.requests;

  const refused = await call(deleteElement);
  assert.equal(refused.error, true);
  assert.deepEqual(refused.body, examples.referenced_delete_error);

  assert.equal((await call(deleteWant)).error, false);
  assert.deepEqual((await call(orphaned)).body, examples.orphan_result_example);
  assert.equal((await call(removeRole)).error, false);
  assert.deepEqual((await call(readElement)).body, examples.read_after_role_removal);
  assert.equal((await call(deleteElement)).error, false);
  assert.equal((await call(readElement)).error, true);
  await client.close();
});

test('each project is a root object that survives import, storage and export', () => {
  const [first, second] = [database(seed), database(canonical)];
  assert.deepEqual(exported(first), example);
  assert.deepEqual(Object.keys(exported(second)), ['metaform']);
  assert.ok(exported(second).metaform.code.framework.plugin);
  assert.deepEqual(exported(first), example);
});

test('a refused command changes nothing, and accepted changes survive a restart', async () => {
  const path = database(seed);
  const first = await connect(path);
  const added = { add: { 'code.relay': { role: 'SE', wants: { 'code.masher.widget': { why: ' ', how: 'f', direction: 'outbound' } } } } };
  assert.equal((await first.call(added)).error, true);
  assert.deepEqual(await first.call({ 'code.relay': {} }).then(({ error }) => error), true);
  assert.equal((await first.call({ add: { 'code.bad': { wants: { 'code.masher.widget': { why: ' ', how: 'f', direction: 'outbound' } } } } })).error, true);
  assert.equal((await first.call({ update: { 'code.masher.widget': { name: 'renamed' } } })).error, false);
  await first.client.close();

  const stored = exported(path);
  assert.equal(stored.mashtrac.code.masher.widget.name, 'renamed');
  assert.equal(stored.mashtrac.code.relay, undefined);
  assert.equal(stored.mashtrac.code.bad, undefined);
});

test('concurrent commands are all applied', async () => {
  const { client, call } = await connect(database(seed));
  const results = await Promise.all(['a', 'b', 'c', 'd'].map((leaf) => call({ add: { [`code.queue.${leaf}`]: { role: 'SE' } } })));
  assert.deepEqual(results.map(({ error }) => error), [false, false, false, false]);
  assert.equal((await call({ 'code.queue.d': {} })).body['code.queue.d'].role, 'SE');
  await client.close();
});

test('the form does the work: one write creates every path it needs, and a read returns everything beneath it', async () => {
  const path = database(seed);
  const { client, call } = await connect(path);
  const want = { why: 'Receive the part.', how: 'Supplies the part.', direction: 'inbound' };
  assert.equal((await call({ update: { 'code.new.part': { name: 'part', wants: { 'code.other.part': want } } } })).error, false);
  assert.equal((await call({ add: { 'code.new.part': { name: 'renamed', wants: { 'code.third.part': want } } } })).error, false);
  assert.equal((await call({ update: { 'code.other.part': { status: 'not_built' } } })).error, false);
  assert.equal((await call({ update: { '.': { layers: ['investigations', 'couplings'] } } })).error, false);
  const { body } = await call({ 'code.new': {} });
  assert.deepEqual(body['code.new'].part.wants, { 'code.other.part': want, 'code.third.part': want });
  const whole = (await call({ '.': {} })).body['.'];
  assert.deepEqual(whole.layers, ['investigations', 'couplings']);
  assert.equal(whole.code.new.part.name, 'renamed');
  assert.ok(whole.code.third.part);
  const refused = await call({ update: { 'code.brand.new': { wants: { 'code.other.part': { direction: 'outbound' } } } } });
  assert.equal(refused.error, true);
  assert.equal((await call({ 'code.brand.new': {} })).error, true);
  assert.equal((await call({ delete: { 'code.gone': {} } })).error, false);
  await client.close();
});

const listed = () => JSON.parse(cli('--projects')) as { path: string; name: string; folder: string }[];

test('each folder is a project in the main database, with its own store and nothing in its own folder', () => {
  const path = database(seed);
  const project = listed().find((each) => each.path === path);
  assert.ok(project);
  assert.equal(project.name, 'mashtrac');
  assert.deepEqual(readdirSync(project.folder).sort(), ['project.lbug', 'source.txt']);
  assert.equal(readFileSync(join(project.folder, 'source.txt'), 'utf8'), `${path}\n`);
  assert.deepEqual(readdirSync(path), []);
});

test('two paths with the same folder name stay two projects', () => {
  const [dashed, nested] = [source('same-name'), source('same/name')];
  for (const path of [dashed, nested]) cli(path, '--import', seed);
  const folders = listed().filter((each) => [dashed, nested].includes(each.path)).map((each) => each.folder);
  assert.equal(new Set(folders).size, 2);
  assert.deepEqual(folders.map((each) => readFileSync(join(each, 'source.txt'), 'utf8').trim()).sort(), [dashed, nested].sort());
  assert.deepEqual(folders.map((each) => each.slice(-3)).sort(), ['001', '002']);
});

test('a project store does not hold the project name', () => {
  const path = database(seed);
  const project = listed().find((each) => each.path === path);
  assert.ok(project);
  const copy = join(folder, 'copy.lbug');
  copyFileSync(join(project.folder, 'project.lbug'), copy);
  const read = JSON.parse(cli('--database', copy, '--export'));
  assert.deepEqual(Object.keys(read), ['project']);
  assert.deepEqual(read.project, example.mashtrac);
});

test('every setting shows as global, and only a changed setting is stored', () => {
  const setting = (key: string) => (JSON.parse(cli('--settings')) as { key: string; value: number; state: string }[]).find((each) => each.key === key);
  assert.deepEqual(setting('database.buffer_pool_mb'), { key: 'database.buffer_pool_mb', value: 256, state: 'default' });
  cli('--set', 'database.buffer_pool_mb=128');
  assert.deepEqual(setting('database.buffer_pool_mb'), { key: 'database.buffer_pool_mb', value: 128, state: 'set' });
  assert.equal(setting('database.max_size_gb')?.state, 'default');
  assert.equal(exported(database(seed)).mashtrac.code.masher.widget.name, example.mashtrac.code.masher.widget.name);
  assert.throws(() => cli('--set', 'no.such.setting=1'));
});

test('the specification export renders each want as one sentence from the wants template, Definitive first', () => {
  const spec = cli(database(seed), '--specification');
  assert.match(spec, /^# Mashtrac Protocol$/m);
  assert.ok(spec.includes('`code.protocol.network.tracker.cs` (mashtrac) requires `code.masher.widget` (mashbox) in order to receive the mash data to relay it, which prepared mash data packets.'));
  assert.ok(spec.indexOf('## Definitive') < spec.indexOf('## Supportive'));
});

test('a layer with a template renders one sentence per record, and one without shows each record as written', () => {
  const document = { demo: { code: { engine: { name: 'loop', role: 'DE', features: [{ feature: 'search' }, { feature: 'save' }], notes: ['kept as written'] } } } };
  const spec = renderSpecification(document, { features: { template: '{this.name} belongs to the {feature} feature.' } });
  assert.ok(spec.includes('- loop belongs to the search feature.'));
  assert.ok(spec.includes('- loop belongs to the save feature.'));
  assert.ok(spec.includes('- kept as written'));
});
