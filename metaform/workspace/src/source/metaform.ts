// The Metaform adapter: GraphSource and WorkspaceEvents over the host's HTTP routes.
// NOT CONNECTED: the host routes are Proposed (dev/graph_workspace_seam.md, "Host routes") and
// not built. The prototype runs on the mock until the seam's verification checks pass.

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

export const CONNECTED = false;

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
    if (!response.ok || body === undefined) {
      throw new TransportError(`the host answered ${response.status} without a result`);
    }
    return body;
  }

  async projects(): Promise<ProjectRef[]> {
    const response = await fetch(`${this.base}/projects`).catch((error: unknown) => {
      throw new TransportError(`the host did not answer: ${String(error)}`);
    });
    if (!response.ok) throw new TransportError(`the host answered ${response.status}`);
    return (await response.json()) as ProjectRef[];
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
