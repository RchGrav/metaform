#!/usr/bin/env node
// Entry point: ACP agent over stdio (newline-delimited JSON-RPC).
// stdout carries only protocol messages; diagnostics go to stderr.

import { Readable, Writable } from "node:stream";
import { ndJsonStream } from "@agentclientprotocol/sdk";
import { createAdapter } from "./adapter.js";

const adapter = createAdapter({ env: process.env, fetch: globalThis.fetch });
const connection = adapter.app.connect(
  ndJsonStream(
    Writable.toWeb(process.stdout) as WritableStream<Uint8Array>,
    Readable.toWeb(process.stdin) as ReadableStream<Uint8Array>,
  ),
);

// When the client goes away, stop running turns (killing their commands) before exiting.
connection.closed.then(
  () => {
    adapter.abortAll("client connection closed");
    process.exit(0);
  },
  (error: unknown) => {
    adapter.abortAll("client connection failed");
    process.stderr.write(`openrouter-acp: connection failed: ${error instanceof Error ? error.stack : String(error)}\n`);
    process.exit(1);
  },
);
