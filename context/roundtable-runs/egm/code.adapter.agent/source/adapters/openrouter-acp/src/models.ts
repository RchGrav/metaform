// OpenRouter model catalog: the source of the `model` session config option.
//
// The choices are read from OpenRouter's published catalog
// (GET https://openrouter.ai/api/v1/models) every time a session is created;
// there is no built-in list.

import type { SessionConfigSelectOption } from "@agentclientprotocol/sdk";

export const MODELS_URL = "https://openrouter.ai/api/v1/models";

/**
 * The model a new session starts on, as ACP requires every select option to
 * carry a `currentValue` the agent can operate with before the client picks
 * one. `openrouter/auto` is OpenRouter's own router entry in the published
 * catalog; it is used only until the client sends `session/set_config_option`.
 */
export const INITIAL_MODEL = "openrouter/auto";

/** Endpoint the OpenRouter Agent SDK calls (betaResponsesSend -> POST /responses). */
const AGENT_ENDPOINT = "/api/v1/responses";

interface CatalogModel {
  id: string;
  name?: string;
  supported_parameters?: string[];
  endpoints?: string[];
}

interface CatalogPage {
  data: CatalogModel[];
  links?: { next?: string | null };
}

export class CatalogError extends Error {}

/**
 * Fetches the full catalog (following `links.next` when the API paginates) and
 * returns the models this adapter can actually run: those that accept tool
 * definitions (`supported_parameters` contains "tools") and are served on the
 * Responses endpoint the Agent SDK uses. A model lacking either would fail on
 * the first prompt, so advertising it would be a choice that cannot work.
 */
export async function fetchModelOptions(
  fetchImpl: typeof fetch,
  apiKey: string,
): Promise<SessionConfigSelectOption[]> {
  const options: SessionConfigSelectOption[] = [];
  const seen = new Set<string>();
  let url: string | null = MODELS_URL;
  while (url !== null) {
    const response: Response = await fetchImpl(url, {
      headers: { Authorization: `Bearer ${apiKey}` },
    });
    if (!response.ok) {
      const body = await response.text();
      throw new CatalogError(
        `GET ${url} failed with HTTP ${response.status}: ${body}`,
      );
    }
    const page = (await response.json()) as CatalogPage;
    if (!Array.isArray(page.data)) {
      throw new CatalogError(`GET ${url} returned no "data" array`);
    }
    for (const model of page.data) {
      if (typeof model.id !== "string" || seen.has(model.id)) continue;
      const tools = model.supported_parameters?.includes("tools") === true;
      const responses = model.endpoints?.includes(AGENT_ENDPOINT) === true;
      if (!tools || !responses) continue;
      seen.add(model.id);
      options.push({ value: model.id, name: model.name ?? model.id });
    }
    const next: string | null | undefined = page.links?.next;
    url = typeof next === "string" && next.length > 0 ? new URL(next, url).href : null;
  }
  if (options.length === 0) {
    throw new CatalogError(
      `OpenRouter's model catalog (${MODELS_URL}) lists no model that supports tool calling on ${AGENT_ENDPOINT}`,
    );
  }
  return options;
}
