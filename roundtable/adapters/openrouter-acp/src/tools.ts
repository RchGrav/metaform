// File and shell tools given to the OpenRouter agent loop.
//
// The OpenRouter Agent SDK (@openrouter/agent 1.0.1) ships no file or shell
// tools, so the adapter defines four minimal ones with the SDK's `tool()`
// helper: read_file, list_directory, write_file, run_command. The SDK's loop
// validates their input and dispatches them; each tool reports its lifecycle to
// the ACP client as `tool_call` / `tool_call_update` notifications, and
// write_file and run_command ask the client through
// `session/request_permission` before they act.

import { spawn } from "node:child_process";
import { constants as fsConstants, promises as fs } from "node:fs";
import path from "node:path";
import { tool, type Tool } from "@openrouter/agent";
import { z } from "zod";
import {
  methods,
  type AgentContext,
  type ToolCallContent,
  type ToolCallLocation,
  type ToolKind,
} from "@agentclientprotocol/sdk";

/** What the tools need from their session. */
export interface ToolHost {
  readonly sessionId: string;
  /** Real path of the session working directory; every file path is confined to it. */
  readonly root: string;
  /** Connection to the ACP client, for updates and permission requests. */
  readonly client: AgentContext;
}

/** Environment variables withheld from commands the model runs. */
const WITHHELD_ENV = ["OPENROUTER_API_KEY"];

const ALLOW = "allow";
const REJECT = "reject";

function text(value: string): ToolCallContent {
  return { type: "content", content: { type: "text", text: value } };
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function isInside(root: string, candidate: string): boolean {
  const rel = path.relative(root, candidate);
  return rel === "" || (rel !== ".." && !rel.startsWith(`..${path.sep}`) && !path.isAbsolute(rel));
}

/**
 * Resolves the absolute path `target` as the kernel would when creating it, but
 * without creating anything, and returns a symlink-free path: the real path of
 * the deepest existing ancestor joined with the components that do not exist.
 *
 * `fs.realpath` fails with ENOENT both for an ordinary missing leaf and for a
 * dangling symbolic link (one whose target does not exist). The two differ: the
 * kernel follows the dangling link when the file is opened with O_CREAT and
 * creates its target, wherever that is. So a missing component is examined with
 * readlink, and a dangling link is followed to its target, which is resolved the
 * same way. The link text is resolved against the link's real directory without
 * lexical normalisation, so `..` in it is resolved by the kernel after the
 * preceding components, exactly as when the link is followed.
 *
 * Every step either shortens the path (parent) or follows one link. Symbolic link
 * loops are detected by the OS: realpath fails with ELOOP for them, which is
 * thrown. The bound therefore holds as long as no one rewrites links while the
 * path is being resolved.
 */
async function resolveReal(target: string): Promise<string> {
  try {
    return await fs.realpath(target);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
  }
  const parent = path.dirname(target);
  if (parent === target) throw new Error(`The file system root ${target} does not resolve`);
  const name = path.basename(target);
  const realParent = await resolveReal(parent);
  if (name === "." || name === "..") {
    // Only reachable from link text: the directory before it does not exist, so
    // the kernel cannot resolve the path either.
    throw new Error(`Path ${target} uses "${name}" after a directory that does not exist`);
  }
  const candidate = path.join(realParent, name);
  let link: string;
  try {
    link = await fs.readlink(candidate);
  } catch (error) {
    // ENOENT: an ordinary component that does not exist (yet).
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return candidate;
    // EINVAL here means the entry exists but is not a link although realpath just
    // reported ENOENT: the file system changed during resolution.
    throw error;
  }
  // A dangling symbolic link: resolve where following it leads.
  const separator = realParent.endsWith(path.sep) ? "" : path.sep;
  return resolveReal(path.isAbsolute(link) ? link : `${realParent}${separator}${link}`);
}

/**
 * Resolves `requested` against the session root and proves the result stays
 * inside it, both lexically and after resolving symbolic links, including a
 * dangling link whose target does not exist (so a link inside the root cannot
 * point, or lead a new file, outside it). Returns the resolved symlink-free
 * absolute path; for a file that does not exist yet, the real path of its
 * deepest existing ancestor joined with the remaining components.
 *
 * The result is opened with O_NOFOLLOW (see {@link openResolved}), so the final
 * component cannot be swapped for a symbolic link between this check and use.
 */
export async function resolveInRoot(root: string, requested: string): Promise<string> {
  const lexical = path.resolve(root, requested);
  if (!isInside(root, lexical)) {
    throw new Error(`Path "${requested}" is outside the session working directory ${root}`);
  }
  const resolved = await resolveReal(lexical);
  if (!isInside(root, resolved)) {
    throw new Error(
      `Path "${requested}" resolves through a symbolic link to ${resolved}, outside the session working directory ${root}`,
    );
  }
  return resolved;
}

const READ_FLAGS = fsConstants.O_RDONLY | fsConstants.O_NOFOLLOW;
const WRITE_FLAGS = fsConstants.O_WRONLY | fsConstants.O_CREAT | fsConstants.O_TRUNC | fsConstants.O_NOFOLLOW;

/**
 * Opens a path returned by {@link resolveInRoot}. That path contains no symbolic
 * links, so O_NOFOLLOW refuses (ELOOP) a final component that has been replaced
 * by a link since the check, instead of following it.
 */
async function openResolved(file: string, flags: number): Promise<fs.FileHandle> {
  try {
    return await fs.open(file, flags, 0o666);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ELOOP") {
      throw new Error(`Refusing to open ${file}: a symbolic link appeared on the path after the confinement check`, {
        cause: error,
      });
    }
    throw error;
  }
}

async function readResolved(file: string): Promise<string> {
  const handle = await openResolved(file, READ_FLAGS);
  try {
    return await handle.readFile("utf8");
  } finally {
    await handle.close();
  }
}

interface Prepared<T> {
  /** Locations and content shown to the client (before permission, if any). */
  locations?: ToolCallLocation[];
  content?: ToolCallContent[];
  /** Performs the action; returns the model-facing output and the client-facing content. */
  run: (signal: AbortSignal) => Promise<{ output: T; content: ToolCallContent[] }>;
}

interface ToolSpec<I, T> {
  host: ToolHost;
  callId: string | undefined;
  input: I;
  title: string;
  kind: ToolKind;
  needsPermission: boolean;
  signal: AbortSignal | undefined;
  prepare: () => Promise<Prepared<T>>;
}

/**
 * Runs one tool call through its ACP lifecycle:
 * tool_call(pending) -> [request_permission] -> in_progress -> completed | failed.
 * Errors are reported to the client as `failed` and rethrown so the agent loop
 * hands them to the model as the tool's error output.
 */
async function lifecycle<I, T>(spec: ToolSpec<I, T>): Promise<T> {
  const { host, input, title, kind, signal } = spec;
  if (spec.callId === undefined || signal === undefined) {
    throw new Error("The OpenRouter agent loop invoked a tool without its execution context");
  }
  const toolCallId = spec.callId;
  const update = (fields: Record<string, unknown>) =>
    host.client.notify(methods.client.session.update, {
      sessionId: host.sessionId,
      update: { sessionUpdate: "tool_call_update", toolCallId, ...fields },
    });

  await host.client.notify(methods.client.session.update, {
    sessionId: host.sessionId,
    update: { sessionUpdate: "tool_call", toolCallId, title, kind, status: "pending", rawInput: input },
  });

  try {
    const prepared = await spec.prepare();
    if (prepared.locations !== undefined || prepared.content !== undefined) {
      await update({ locations: prepared.locations, content: prepared.content });
    }
    if (spec.needsPermission) {
      const response = await host.client.request(methods.client.session.requestPermission, {
        sessionId: host.sessionId,
        toolCall: {
          toolCallId,
          title,
          kind,
          status: "pending",
          rawInput: input,
          ...(prepared.locations !== undefined && { locations: prepared.locations }),
          ...(prepared.content !== undefined && { content: prepared.content }),
        },
        options: [
          { optionId: ALLOW, name: "Allow", kind: "allow_once" },
          { optionId: REJECT, name: "Reject", kind: "reject_once" },
        ],
      });
      const outcome = response.outcome;
      if (outcome.outcome !== "selected" || outcome.optionId !== ALLOW) {
        const reason =
          outcome.outcome === "cancelled"
            ? "The permission request was cancelled; the tool did not run."
            : "The client denied permission; the tool did not run.";
        throw new Error(reason);
      }
    }
    signal.throwIfAborted();
    await update({ status: "in_progress" });
    const { output, content } = await prepared.run(signal);
    await update({ status: "completed", content, rawOutput: output });
    return output;
  } catch (error) {
    await update({ status: "failed", content: [text(errorMessage(error))] });
    throw error;
  }
}

interface CommandResult {
  exitCode: number | null;
  signal: string | null;
  stdout: string;
  stderr: string;
}

/**
 * Runs `command` with /bin/sh in `cwd`, stdin closed. The command runs in its
 * own process group so that cancelling the turn kills every process still in
 * that group, including background jobs that outlive the shell.
 * There is no time limit.
 */
function runShell(command: string, cwd: string, signal: AbortSignal): Promise<CommandResult> {
  signal.throwIfAborted();
  const env = { ...process.env };
  for (const name of WITHHELD_ENV) delete env[name];
  return new Promise((resolve, reject) => {
    const child = spawn("/bin/sh", ["-c", command], {
      cwd,
      env,
      stdio: ["ignore", "pipe", "pipe"],
      detached: true,
    });
    const stdout: Buffer[] = [];
    const stderr: Buffer[] = [];
    child.stdout.on("data", (chunk: Buffer) => stdout.push(chunk));
    child.stderr.on("data", (chunk: Buffer) => stderr.push(chunk));
    // The command's process group (its ID is the leader's pid) can outlive the
    // leader: a background job such as `sleep 30 & exit 0` keeps running, and
    // keeps the output pipes open, after /bin/sh has exited. Cancellation
    // therefore signals the whole group whether or not the leader is still
    // running, and the command settles on `close`, once the leader has exited
    // and every holder of the pipes is gone. The kernel does not reuse the
    // group's ID while any member remains, so the signal reaches only this
    // command's processes.
    const kill = () => {
      // No pid: the spawn failed, and the 'error' handler settles the command.
      if (child.pid === undefined) return;
      try {
        process.kill(-child.pid, "SIGKILL");
      } catch (error) {
        // ESRCH: no process is left in the group; it has already stopped.
        if ((error as NodeJS.ErrnoException).code !== "ESRCH") throw error;
      }
    };
    signal.addEventListener("abort", kill, { once: true });
    child.on("error", (error) => {
      signal.removeEventListener("abort", kill);
      reject(error);
    });
    child.on("close", (exitCode, exitSignal) => {
      signal.removeEventListener("abort", kill);
      if (signal.aborted) {
        reject(signal.reason);
        return;
      }
      resolve({
        exitCode,
        signal: exitSignal,
        stdout: Buffer.concat(stdout).toString("utf8"),
        stderr: Buffer.concat(stderr).toString("utf8"),
      });
    });
  });
}

function formatCommandResult(result: CommandResult): string {
  const status =
    result.signal !== null ? `terminated by ${result.signal}` : `exit code ${result.exitCode}`;
  const parts = [status];
  if (result.stdout.length > 0) parts.push(`stdout:\n${result.stdout}`);
  if (result.stderr.length > 0) parts.push(`stderr:\n${result.stderr}`);
  return parts.join("\n");
}

/** Builds the tool set for one session. */
export function createTools(host: ToolHost): readonly Tool[] {
  const relative = (absolute: string) => path.relative(host.root, absolute) || ".";

  const readFile = tool({
    name: "read_file",
    description:
      "Read a UTF-8 text file. The path is relative to the session working directory (absolute paths must lie inside it).",
    inputSchema: z.object({ path: z.string().describe("File path") }),
    execute: (input, ctx) =>
      lifecycle({
        host,
        callId: ctx?.callId,
        input,
        title: `Read ${input.path}`,
        kind: "read",
        needsPermission: false,
        signal: ctx?.signal,
        prepare: async () => {
          const file = await resolveInRoot(host.root, input.path);
          return {
            locations: [{ path: file }],
            run: async () => {
              const content = await readResolved(file);
              return { output: { path: relative(file), content }, content: [text(content)] };
            },
          };
        },
      }),
  });

  const listDirectory = tool({
    name: "list_directory",
    description:
      "List the entries of a directory (directories end with '/'). The path is relative to the session working directory; omit it for the working directory itself.",
    inputSchema: z.object({ path: z.string().optional().describe("Directory path; default '.'") }),
    execute: (input, ctx) =>
      lifecycle({
        host,
        callId: ctx?.callId,
        input,
        title: `List ${input.path ?? "."}`,
        kind: "read",
        needsPermission: false,
        signal: ctx?.signal,
        prepare: async () => {
          const dir = await resolveInRoot(host.root, input.path ?? ".");
          return {
            locations: [{ path: dir }],
            run: async () => {
              const entries = await fs.readdir(dir, { withFileTypes: true });
              const names = entries
                .map((entry) => (entry.isDirectory() ? `${entry.name}/` : entry.name))
                .sort();
              return {
                output: { path: relative(dir), entries: names },
                content: [text(names.join("\n"))],
              };
            },
          };
        },
      }),
  });

  const writeFile = tool({
    name: "write_file",
    description:
      "Create or overwrite a UTF-8 text file with the given content, creating missing parent directories. The path is relative to the session working directory. Requires the client's permission.",
    inputSchema: z.object({
      path: z.string().describe("File path"),
      content: z.string().describe("Complete new file content"),
    }),
    execute: (input, ctx) =>
      lifecycle({
        host,
        callId: ctx?.callId,
        input,
        title: `Write ${input.path}`,
        kind: "edit",
        needsPermission: true,
        signal: ctx?.signal,
        prepare: async () => {
          const file = await resolveInRoot(host.root, input.path);
          let oldText: string | null = null;
          try {
            oldText = await readResolved(file);
          } catch (error) {
            if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
          }
          const diff: ToolCallContent = { type: "diff", path: file, oldText, newText: input.content };
          return {
            locations: [{ path: file }],
            content: [diff],
            run: async () => {
              // Re-check confinement: a directory could have been swapped for a
              // symlink while the permission request was open.
              const target = await resolveInRoot(host.root, input.path);
              await fs.mkdir(path.dirname(target), { recursive: true });
              const handle = await openResolved(target, WRITE_FLAGS);
              try {
                await handle.writeFile(input.content, "utf8");
              } finally {
                await handle.close();
              }
              return {
                output: { path: relative(target), bytesWritten: Buffer.byteLength(input.content, "utf8") },
                content: [diff],
              };
            },
          };
        },
      }),
  });

  const runCommand = tool({
    name: "run_command",
    description:
      "Run a shell command with /bin/sh -c in the session working directory and return its exit status, stdout and stderr. Stdin is closed. Requires the client's permission.",
    inputSchema: z.object({ command: z.string().describe("Shell command line") }),
    execute: (input, ctx) =>
      lifecycle({
        host,
        callId: ctx?.callId,
        input,
        title: input.command,
        kind: "execute",
        needsPermission: true,
        signal: ctx?.signal,
        prepare: async () => ({
          locations: [{ path: host.root }],
          run: async (signal) => {
            const result = await runShell(input.command, host.root, signal);
            return { output: result, content: [text(formatCommandResult(result))] };
          },
        }),
      }),
  });

  return [readFile, listDirectory, writeFile, runCommand];
}
