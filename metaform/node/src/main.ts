// `metaform` in its Node form: the `project-map` tool over stdio MCP, on a SQLite store.
//
//     node metaform/node/src/main.ts mcp  [--home DIR] [--project DIR]
//                                         stdio MCP for an agent harness; DIR defaults to .
//     node metaform/node/src/main.ts call [--home DIR] [--project DIR] '<json command>' | -
//                                         one tool command; `-` reads it from stdin.
//                                         Exit 0 ok, 1 refused, 2 usage error.
//     node metaform/node/src/main.ts projects [--home DIR]
//                                         every registered project: id, name, folder
//
// The home defaults to `METAFORM_HOME`, then `~/.metaform-sqlite`.
//
// The command line follows `metaform-server/src/main.rs`. This form has no `serve`, `gui`,
// `settings` or `specification` command (design document, section 2).

import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

import type { Json } from "./json.ts";
import { get, isObject, obj, parse, pretty } from "./json.ts";
import { Server, serve } from "./mcp.ts";
import { Store } from "./store.ts";
import { MapTool } from "./tool.ts";

function usage(problem: string): number {
  process.stderr.write(
    `metaform: ${problem}\nusage: metaform mcp  [--home DIR] [--project DIR]\n       metaform call [--home DIR] [--project DIR] '<json command>' | -\n       metaform projects [--home DIR]\n`,
  );
  return 2;
}

function fail(problem: unknown, status: number): number {
  process.stderr.write(`metaform: ${problem instanceof Error ? problem.message : String(problem)}\n`);
  return status;
}

/** This form's version, from `package.json`. */
function version(): string {
  const found = get(parse(readFileSync(new URL("../package.json", import.meta.url), "utf8")), "version");
  return typeof found === "string" ? found : "";
}

/** `metaform call`: print the tool's answer; exit 0 ok, 1 refused, 2 usage or store error. */
function call(home: string, project: string, positional: string[]): number {
  if (positional.length !== 1) {
    return usage("call takes one JSON command, or - to read it from stdin");
  }
  let text = positional[0];
  if (text === "-") {
    try {
      text = readFileSync(0, "utf8");
    } catch (problem) {
      return usage(`could not read the command from stdin: ${(problem as Error).message}`);
    }
  }
  let command: Json;
  try {
    command = parse(text);
  } catch {
    command = null;
  }
  if (!isObject(command)) {
    return usage("the command must be one JSON object, such as '{\".\": {}}'");
  }
  let store: Store;
  let tool: MapTool;
  try {
    store = new Store(home);
    tool = new MapTool(store, store.registerProject(project));
  } catch (problem) {
    return fail(problem, 2);
  }
  const answer = tool.call(command);
  store.close();
  // `INTERNAL_ERROR` is a store failure, not a refusal, so the exit status is 2, not 1.
  if (answer.refused && get(parse(answer.text), "code") === "INTERNAL_ERROR") {
    return fail(answer.text, 2);
  }
  process.stdout.write(`${answer.text}\n`);
  return answer.refused ? 1 : 0;
}

/** `metaform projects`: print every project registered in the home. */
function projects(home: string): number {
  try {
    const store = new Store(home);
    const list = store.projects().map((p) => obj(["id", p.id], ["name", p.name], ["folder", p.folder]));
    store.close();
    process.stdout.write(`${pretty(list)}\n`);
    return 0;
  } catch (problem) {
    return fail(problem, 1);
  }
}

/** `metaform mcp`: serve the tool on stdin and stdout until stdin closes. */
function mcp(home: string, project: string): number | null {
  let store: Store;
  let tool: MapTool;
  try {
    store = new Store(home);
    tool = new MapTool(store, store.registerProject(project));
  } catch (problem) {
    return fail(problem, 1);
  }
  serve(new Server(tool, version()), () => store.close());
  return null;
}

function main(args: string[]): number | null {
  let home = process.env.METAFORM_HOME || join(homedir(), ".metaform-sqlite");
  let project = ".";
  const positional: string[] = [];
  for (let at = 1; at < args.length; at += 1) {
    const arg = args[at];
    if (!arg.startsWith("--")) {
      positional.push(arg);
      continue;
    }
    at += 1;
    const value = args[at];
    if (arg === "--home" && value !== undefined) {
      home = value;
    } else if (arg === "--project" && value !== undefined) {
      project = value;
    } else {
      return usage(`unknown or incomplete option ${arg}`);
    }
  }
  const command = args[0];
  if (command === "projects") {
    return positional.length > 0 ? usage("projects takes no arguments") : projects(home);
  }
  if (command === "call") {
    return call(home, project, positional);
  }
  if (positional.length > 0) {
    return usage(`unexpected argument ${positional[0]}`);
  }
  if (command === "mcp") {
    return mcp(home, project);
  }
  return usage("expected mcp, call or projects");
}

const status = main(process.argv.slice(2));
if (status !== null) {
  process.exitCode = status;
}
