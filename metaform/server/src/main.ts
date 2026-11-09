/**
 * Run the Metaform MCP server on stdio for one project. A project is named by its source folder.
 *
 *   node src/main.ts <folder>                  serve the folder's project, created if it is new
 *   node src/main.ts <folder> --import <file>  load a document; its top-level key names a new project
 *   node src/main.ts <folder> --export
 *   node src/main.ts <folder> --specification [--layers <file>]   render the map as a readable specification
 *   node src/main.ts --projects                list the projects
 *   node src/main.ts --settings                list the global settings
 *   node src/main.ts --set <key>=<value>       store a global setting
 *   node src/main.ts --database <file> --export    read a copy of a project database
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { parseArgs } from 'node:util';
import { StdioServerTransport } from '@modelcontextprotocol/server/stdio';
import { DEFAULT_SIZE, Home, type Project } from './home.ts';
import { createServer } from './server.ts';
import { Store, type DatabaseSize } from './store.ts';
import { renderSpecification, type LayerDefinition } from './specify.ts';
import { exportProject, importProject, projectIn, type Json } from './tree.ts';

const USAGE = 'Usage: node src/main.ts <folder> [--import <file> | --export | --specification [--layers <file>]] | --projects | --settings | --set <key>=<value> | --database <file> --export';

const { positionals, values } = parseArgs({
  allowPositionals: true,
  options: {
    import: { type: 'string' },
    export: { type: 'boolean' },
    specification: { type: 'boolean' },
    layers: { type: 'string' },
    projects: { type: 'boolean' },
    settings: { type: 'boolean' },
    set: { type: 'string' },
    database: { type: 'string' },
  },
});

function fail(message: string, code = 1): never {
  console.error(message);
  process.exit(code);
}

/** Open the main database for one lookup, so a process never holds it while it serves. */
async function withHome<T>(work: (home: Home) => Promise<T>): Promise<T> {
  const home = await Home.open();
  try {
    return await work(home);
  } finally {
    await home.close();
  }
}

async function exportCopy(file: string): Promise<void> {
  const store = await Store.open(file, DEFAULT_SIZE);
  console.log(JSON.stringify(await exportProject(store, 'project'), null, 2));
  await store.close();
}

async function open(project: Project, projectSize: DatabaseSize): Promise<Store> {
  return Store.open(join(project.folder, 'project.lbug'), projectSize);
}

async function importInto(folder: string, file: string): Promise<void> {
  const document = JSON.parse(readFileSync(file, 'utf8')) as Json;
  const [name] = projectIn(document);
  const [project, projectSize] = await withHome(async (home) => [await home.project(folder, name), await home.size()] as const);
  const store = await open(project, projectSize);
  const missing = await importProject(store, document);
  await store.close();
  if (missing.length > 0) fail(`Nothing stored. These wants name a provider that does not exist:\n${missing.join('\n')}`);
}

async function exportFrom(folder: string): Promise<void> {
  const [project, projectSize] = await withHome(async (home) => [await home.find(folder), await home.size()] as const);
  if (project === null) fail(`'${folder}' has no project`);
  const store = await open(project, projectSize);
  console.log(JSON.stringify(await exportProject(store, project.name), null, 2));
  await store.close();
}

/** The map as a readable specification (R-1.2). `layersFile` holds the layer definitions, keyed by layer name. */
async function specificationFrom(folder: string, layersFile?: string): Promise<void> {
  const [project, projectSize] = await withHome(async (home) => [await home.find(folder), await home.size()] as const);
  if (project === null) fail(`'${folder}' has no project`);
  const layers = layersFile === undefined ? {} : (JSON.parse(readFileSync(layersFile, 'utf8')) as Record<string, LayerDefinition>);
  const store = await open(project, projectSize);
  const document = await exportProject(store, project.name);
  await store.close();
  process.stdout.write(renderSpecification(document, layers));
}

async function serve(folder: string): Promise<void> {
  const [project, projectSize] = await withHome(async (home) => [await home.project(folder), await home.size()] as const);
  await createServer(await open(project, projectSize)).connect(new StdioServerTransport());
}

async function setGlobal(assignment: string): Promise<void> {
  const [key, value] = assignment.split('=');
  await withHome((home) => home.set(key, Number(value))).catch((error: Error) => fail(error.message));
}

const [folder] = positionals;
if (values.projects) console.log(JSON.stringify(await withHome((home) => home.projects()), null, 2));
else if (values.settings) console.log(JSON.stringify(await withHome((home) => home.settings()), null, 2));
else if (values.set !== undefined) await setGlobal(values.set);
else if (values.database !== undefined && values.export) await exportCopy(values.database);
else if (folder === undefined) fail(USAGE, 2);
else if (values.import !== undefined) await importInto(folder, values.import);
else if (values.export) await exportFrom(folder);
else if (values.specification) await specificationFrom(folder, values.layers);
else await serve(folder);
