// In-memory stand-in for the OpenRouter HTTP API (no network, no key).
// Serves GET /api/v1/models from a fixed test catalog and answers each
// POST /api/v1/responses with the next scripted turn as a Responses-API SSE stream.

export interface ScriptedToolCall {
  callId: string;
  name: string;
  args: Record<string, unknown>;
}

export interface ScriptedTurn {
  /** Assistant text deltas, streamed in order. */
  text?: string[];
  /** Function calls the model makes in this turn. */
  toolCalls?: ScriptedToolCall[];
  /**
   * If set, the stream stops after the text deltas and waits on this promise
   * (or on the request being aborted) before completing.
   */
  hold?: Promise<void>;
  /** If set, the stream fails with this error after the text deltas. */
  fail?: Error;
  /** Called when the first SSE bytes have been enqueued. */
  onStreaming?: () => void;
}

export interface RecordedRequest {
  url: string;
  method: string;
  headers: Headers;
  body: any;
}

export const CATALOG = {
  data: [
    {
      id: "openrouter/auto",
      name: "Auto Router",
      supported_parameters: ["tools", "tool_choice"],
      endpoints: ["/api/v1/chat/completions", "/api/v1/responses"],
    },
    {
      id: "anthropic/claude-test",
      name: "Anthropic: Claude Test",
      supported_parameters: ["tools", "temperature"],
      endpoints: ["/api/v1/responses"],
    },
    {
      id: "openai/gpt-test",
      name: "OpenAI: GPT Test",
      supported_parameters: ["tools"],
      endpoints: ["/api/v1/chat/completions", "/api/v1/responses"],
    },
    {
      id: "acme/no-tools",
      name: "Acme: No Tools",
      supported_parameters: ["temperature"],
      endpoints: ["/api/v1/responses"],
    },
    {
      id: "acme/chat-only",
      name: "Acme: Chat Only",
      supported_parameters: ["tools"],
      endpoints: ["/api/v1/chat/completions"],
    },
  ],
  links: { next: null },
};

let sequence = 0;

function responseObject(id: string, model: string, status: string, output: unknown[]) {
  return {
    id,
    object: "response",
    created_at: 1_700_000_000,
    completed_at: status === "completed" ? 1_700_000_001 : null,
    status,
    model,
    output,
    error: null,
    incomplete_details: null,
    instructions: null,
    metadata: null,
    frequency_penalty: null,
    presence_penalty: null,
    temperature: null,
    top_p: null,
    parallel_tool_calls: true,
    tool_choice: "auto",
    tools: [],
    usage: {
      input_tokens: 10,
      input_tokens_details: { cached_tokens: 0 },
      output_tokens: 5,
      output_tokens_details: { reasoning_tokens: 0 },
      total_tokens: 15,
    },
  };
}

function sse(event: Record<string, unknown>): string {
  return `data: ${JSON.stringify({ ...event, sequence_number: sequence++ })}\n\n`;
}

function streamTurn(turn: ScriptedTurn, model: string, signal: AbortSignal): Response {
  const id = `resp_${sequence}`;
  const messageId = `msg_${sequence}`;
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    async start(controller) {
      const push = (event: Record<string, unknown>) => controller.enqueue(encoder.encode(sse(event)));
      push({ type: "response.created", response: responseObject(id, model, "in_progress", []) });
      const output: unknown[] = [];
      const text = turn.text ?? [];
      if (text.length > 0) {
        push({
          type: "response.output_item.added",
          output_index: 0,
          item: { type: "message", id: messageId, role: "assistant", status: "in_progress", content: [] },
        });
        for (const delta of text) {
          push({
            type: "response.output_text.delta",
            item_id: messageId,
            output_index: 0,
            content_index: 0,
            delta,
            logprobs: [],
          });
        }
      }
      turn.onStreaming?.();
      if (turn.fail !== undefined) {
        controller.error(turn.fail);
        return;
      }
      if (turn.hold !== undefined) {
        const aborted = new Promise<void>((resolve) => {
          if (signal.aborted) resolve();
          signal.addEventListener("abort", () => resolve(), { once: true });
        });
        await Promise.race([turn.hold, aborted]);
        if (signal.aborted) {
          controller.error(signal.reason);
          return;
        }
      }
      if (text.length > 0) {
        const message = {
          type: "message",
          id: messageId,
          role: "assistant",
          status: "completed",
          content: [{ type: "output_text", text: text.join(""), annotations: [] }],
        };
        push({ type: "response.output_item.done", output_index: 0, item: message });
        output.push(message);
      }
      for (const call of turn.toolCalls ?? []) {
        const item = {
          type: "function_call",
          id: `fc_${call.callId}`,
          call_id: call.callId,
          name: call.name,
          arguments: JSON.stringify(call.args),
          status: "completed",
        };
        push({ type: "response.output_item.added", output_index: output.length, item });
        push({ type: "response.output_item.done", output_index: output.length, item });
        output.push(item);
      }
      push({ type: "response.completed", response: responseObject(id, model, "completed", output) });
      controller.enqueue(encoder.encode("data: [DONE]\n\n"));
      controller.close();
    },
  });
  return new Response(body, { status: 200, headers: { "content-type": "text/event-stream" } });
}

export interface MockOpenRouter {
  fetch: typeof fetch;
  requests: RecordedRequest[];
  /** Bodies of the POST /responses requests, in order. */
  responseRequests(): any[];
  /** Scripted turns not yet consumed. */
  remaining(): number;
}

export function mockOpenRouter(turns: ScriptedTurn[]): MockOpenRouter {
  const queue = [...turns];
  const requests: RecordedRequest[] = [];
  const fetchImpl = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const request = input instanceof Request ? input : new Request(input, init);
    const url = new URL(request.url);
    const body = request.method === "POST" ? await request.json() : undefined;
    requests.push({ url: request.url, method: request.method, headers: request.headers, body });
    if (url.origin !== "https://openrouter.ai") {
      throw new Error(`mock OpenRouter: unexpected host in ${request.url}`);
    }
    if (request.method === "GET" && url.pathname === "/api/v1/models") {
      return Response.json(CATALOG);
    }
    if (request.method === "POST" && url.pathname === "/api/v1/responses") {
      const turn = queue.shift();
      if (turn === undefined) throw new Error("mock OpenRouter: no scripted turn left");
      return streamTurn(turn, body.model, request.signal);
    }
    throw new Error(`mock OpenRouter: unexpected ${request.method} ${request.url}`);
  };
  return {
    fetch: fetchImpl as typeof fetch,
    requests,
    responseRequests: () => requests.filter((r) => r.method === "POST").map((r) => r.body),
    remaining: () => queue.length,
  };
}
