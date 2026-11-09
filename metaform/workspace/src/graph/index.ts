// The ELK renderer, with ELK running in a Web Worker so layout never blocks input.

import ELK from "elkjs/lib/elk-api.js";
import elkWorkerUrl from "elkjs/lib/elk-worker.min.js?url";
import type { Elk } from "./layout";
import type { GraphRenderer } from "./renderer";
import { ElkRenderer } from "./svg-renderer";

export { ElkRenderer } from "./svg-renderer";

let shared: Elk | null = null;

/** One ELK worker for the page; layouts queue on it. */
function workerElk(): Elk {
  shared ??= new ELK({ workerFactory: () => new Worker(elkWorkerUrl) }) as unknown as Elk;
  return shared;
}

export function createRenderer(): GraphRenderer {
  return new ElkRenderer(workerElk);
}
