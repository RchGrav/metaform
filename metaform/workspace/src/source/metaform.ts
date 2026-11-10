// The Metaform adapter: GraphSource and WorkspaceEvents over the host's HTTP routes
// (dev/graph_workspace_seam.md, "Host routes"; the host is metaform/rust/crates/metaform-web).
// The page uses it when the host serves the page (src/source/choose.ts).

import { RefusalError, TransportError, isRefusal } from "./errors";
import type {
  Address,
  GraphSource,
  ProjectRef,
  RawDump,
  ShallowGraph,
  SummarySheet,
  WorkspaceEvent,
  WorkspaceEvents,
} from "./types";

/** The host's own failure text (`{"error": "<reason>"}`), when its answer carries one. */
function hostReason(body: unknown): string | null {
  const reason = typeof body === "object" && body !== null ? (body as { error?: unknown }).error : undefined;
  return typeof reason === "string" ? reason : null;
}

function hostFailure(status: number, body: unknown): TransportError {
  const reason = hostReason(body);
  return new TransportError(reason === null ? `the host answered ${status} without a result` : `the host answered ${status}: ${reason}`);
}

function projectPath(base: string, project: string): string {
  return `${base}/projects/${encodeURIComponent(project)}`;
}

export class MetaformSource implements GraphSource {
  constructor(private readonly base = "/api") {}

  /** Sends one command of the Metaform tool and returns its result unchanged. */
  private async call(project: string, command: object): Promise<unknown> {
    let response: Response;
    try {
      response = await fetch(`${projectPath(this.base, project)}/call`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(command),
      });
    } catch (error) {
      throw new TransportError(`the host did not answer: ${String(error)}`);
    }
    const body: unknown = await response.json().catch(() => undefined);
    if (isRefusal(body)) throw new RefusalError(body);
    if (!response.ok || body === undefined) throw hostFailure(response.status, body);
    return body;
  }

  async projects(): Promise<ProjectRef[]> {
    const response = await fetch(`${this.base}/projects`).catch((error: unknown) => {
      throw new TransportError(`the host did not answer: ${String(error)}`);
    });
    const body: unknown = await response.json().catch(() => undefined);
    if (!response.ok || !Array.isArray(body)) throw hostFailure(response.status, body);
    return body as ProjectRef[];
  }

  async map(project: string): Promise<ShallowGraph> {
    return (await this.call(project, { map: {} })) as ShallowGraph;
  }

  async dump(project: string): Promise<RawDump> {
    return (await this.call(project, { ".": {} })) as RawDump;
  }

  async goto(project: string, at: Address): Promise<SummarySheet> {
    return (await this.call(project, { goto: at })) as SummarySheet;
  }

  /** Not connected: the server has no request for an outside project's map yet (seam gap 4). */
  async outsideMap(_project: string, _at: Address): Promise<ProjectRef | null> {
    return null;
  }

  async layerRecords(project: string, at: Address, layer: string): Promise<unknown[]> {
    const result = (await this.call(project, { [at]: { [layer]: {} } })) as Record<
      string,
      Record<string, unknown>
    >;
    const records = result[at]?.[layer];
    return Array.isArray(records) ? records : [];
  }
}

/** Relays the host's server-sent events. The browser's EventSource reconnects on its own. */
export class MetaformEvents implements WorkspaceEvents {
  /** Each subscription is one EventSource, and so one connection to the host (see WorkspaceEvents). */
  readonly openProjectOnly = true;

  constructor(private readonly base = "/api") {}

  subscribe(project: string, listener: (event: WorkspaceEvent) => void): () => void {
    const stream = new EventSource(`${projectPath(this.base, project)}/events`);
    const onChange = () => listener({ kind: "map-changed", project, simulated: false });
    stream.addEventListener("map-changed", onChange);
    return () => {
      stream.removeEventListener("map-changed", onChange);
      stream.close();
    };
  }
}
