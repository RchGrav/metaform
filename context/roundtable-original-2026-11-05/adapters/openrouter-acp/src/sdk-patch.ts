// Workaround for a floating promise in @openrouter/agent 1.0.1.
//
// ModelResult's streaming getters (getTextStream, getFullResponsesStream, ...)
// do:
//
//   const { consumer, executionPromise } = this.startTurnBroadcasterExecution();
//   for await (const event of consumer) yield ...;
//   await executionPromise;
//
// When the first model response stream fails (the turn is aborted by
// session/cancel, or the connection to OpenRouter breaks mid-stream), the
// consumer throws and `executionPromise`, which rejects with the same failure,
// is never awaited. Node treats that as an unhandled rejection and, by default,
// terminates the process, which would take every session of the adapter down
// with it. Reproduced by tests "stops a streaming turn with stopReason
// cancelled" and "reports a broken model stream as a prompt error".
//
// The failure itself is not lost: the consumer rethrows it to the adapter,
// which ends the turn with `cancelled` or a JSON-RPC error. This patch only
// marks the duplicate promise as handled. It wraps the one private method that
// creates the promise, and refuses to start if that method is not there (an
// SDK change must be re-examined, not silently tolerated).

import { ModelResult } from "@openrouter/agent";

type BroadcasterExecution = { consumer: unknown; executionPromise: Promise<unknown> };

let patched = false;

export function patchModelResult(): void {
  if (patched) return;
  patched = true;
  const prototype = ModelResult.prototype as unknown as {
    startTurnBroadcasterExecution?: (this: unknown) => BroadcasterExecution;
  };
  const original = prototype.startTurnBroadcasterExecution;
  if (typeof original !== "function") {
    throw new Error(
      "@openrouter/agent no longer has ModelResult.startTurnBroadcasterExecution; re-examine src/sdk-patch.ts",
    );
  }
  prototype.startTurnBroadcasterExecution = function (this: unknown) {
    const execution = original.call(this);
    execution.executionPromise.catch(() => {
      // Already delivered through the stream consumer; see the file comment.
    });
    return execution;
  };
}
