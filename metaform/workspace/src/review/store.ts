// The one store for the specification (ARCHITECTURE.md section 1). It holds `saved`, the changes
// the server has not confirmed, the proposals with their review states, and the notes that a
// refused write leaves. Every panel reads `spec = current(saved, pending)` from it.
//
// A change is sent as one `project-map` command. When the server stores it, a second command adds
// one record to the `review` layer at the element the change concerns, so the map itself says who
// wrote the part. A rejected proposal adds a record and changes nothing else.

import { useEffect, useMemo, useSyncExternalStore } from "react";
import type { AgentService, ProposalScope } from "../source/agent";
import { RefusalError } from "../source/errors";
import type { Address, GraphSource, WriteCommand } from "../source/types";
import { applyChange, current, toCommand } from "../spec/changes";
import type { Change, Proposal } from "../spec/changes";
import { REVIEW_LAYER, whatOf } from "../spec/evidence";
import type { ReviewRecord } from "../spec/evidence";
import { elementAt, fromDump } from "../spec/model";
import type { Origin, Spec } from "../spec/model";
import { store as words } from "./strings";

/** Where the `review` layer is defined in a map. Its last segment is the layer's field name. */
export const REVIEW_DEFINITION = "layer.record.review";

/** The command that defines the `review` layer. The store sends it once, before the first record. */
export const DEFINE_REVIEW_LAYER: WriteCommand = {
  add: {
    [REVIEW_DEFINITION]: {
      technical_name: "review record layer",
      name: "Review history",
      role: "Supportive",
      instruction: words.layerInstruction,
    },
  },
};

/** A change the server has not confirmed. */
export interface PendingEntry {
  change: Change;
  /** The user, or an agent whose proposal the user accepted without editing it. */
  origin: Origin;
  /** The accepted proposal the change came from, or null for the user's own edit. */
  proposal: Proposal | null;
  /** True when the server stored the change and its review record was sent. The next read of the dump drops the entry. */
  stored: boolean;
}

/** A note shown where an edit was made: a refused write, or a review record that was not stored. */
export interface PartNote {
  /** The part the note concerns, from `partKey`. */
  key: string;
  kind: "refused" | "history";
  /** The server's message, or the reason the host gave. */
  message: string;
  /** The server's code for a refusal, or null. */
  code: string | null;
  /** The server's remediation, when it is a complete write command. Null when it holds a placeholder or is absent. */
  remediation: WriteCommand | null;
}

/** Whether the page can store an edit, and the reason to show when it matters. */
export interface Writable {
  can: boolean;
  /** "sample": edits are kept in the page only. "read-only" and "unreachable": no edit can be stored. Null: no line is needed, or the answer is not known yet. */
  reason: "sample" | "read-only" | "unreachable" | null;
}

/** What the store holds at one moment. A new object replaces it on every change. */
export interface StoreState {
  /** The specification as the server holds it, or null before the first read. */
  saved: Spec | null;
  /** `current(saved, pending)`: the specification every panel shows. */
  spec: Spec | null;
  pending: readonly PendingEntry[];
  /** Every proposal received, with its review state. Only an accepted one is in `spec`. */
  proposals: readonly Proposal[];
  notes: readonly PartNote[];
  writable: Writable;
  /** True while a request for proposals has no answer yet. */
  asking: boolean;
  /** What the last request for proposals returned: a count, or the reason it failed. Null before any request. */
  asked: { added: number; failed: string | null } | null;
}

/** What the store needs from the page. */
export interface StoreOptions {
  source: Pick<GraphSource, "write" | "dump" | "canWrite">;
  agent: AgentService;
  /** The id of the project, as the source takes it. */
  project: string;
  /** The project's name, as the host lists it. */
  projectName: string;
  /** True while the data is sample data. */
  simulated: boolean;
  /** The clock for a review record's time. Tests replace it. */
  now?: () => Date;
}

let made = 0;

/** A new id for a change the user makes in the page. */
export function newChangeId(): string {
  made += 1;
  return `edit-${Date.now().toString(36)}-${made}`;
}

/** The key of the part a change concerns: the element's address and the name a review record gives the part. */
export function partKey(address: Address, what: string): string {
  return `${address}|${what}`;
}

/** The key of the part that a change concerns. */
export function keyOf(change: Change): string {
  return partKey(change.address, whatOf(change));
}

/** True when the value holds a placeholder in angle brackets, such as "<why>", at any depth. */
export function hasPlaceholder(value: unknown): boolean {
  if (typeof value === "string") return /<[^<>]+>/.test(value);
  if (value === null || typeof value !== "object") return false;
  return Object.entries(value).some(([key, held]) => hasPlaceholder(key) || hasPlaceholder(held));
}

/** The remediation as a write command the page can send, or null when it is not one or holds a placeholder. */
export function remediationOf(remediation: unknown): WriteCommand | null {
  if (remediation === null || typeof remediation !== "object" || Array.isArray(remediation)) return null;
  const verbs = Object.keys(remediation);
  const verb = verbs[0];
  if (verbs.length !== 1 || verb === undefined || !["add", "update", "delete"].includes(verb)) return null;
  return hasPlaceholder(remediation) ? null : (remediation as WriteCommand);
}

function noteOf(key: string, kind: PartNote["kind"], error: unknown): PartNote {
  if (error instanceof RefusalError) {
    const { message, code, remediation } = error.refusal;
    return { key, kind, message, code, remediation: kind === "refused" ? remediationOf(remediation) : null };
  }
  return { key, kind, message: error instanceof Error ? error.message : String(error), code: null, remediation: null };
}

/** True when the saved specification already holds what the change sets. */
function holds(saved: Spec, change: Change): boolean {
  const after = elementAt(applyChange(saved, change), change.address);
  return JSON.stringify(after) === JSON.stringify(elementAt(saved, change.address));
}

function sameChange(a: Change, b: Change): boolean {
  return JSON.stringify({ ...a, id: "" }) === JSON.stringify({ ...b, id: "" });
}

/** The store. It is plain TypeScript, so a test can use it with no page; `useSpecStore` gives it to React. */
export class SpecStore {
  private state: StoreState = {
    saved: null, spec: null, pending: [], proposals: [], notes: [], writable: { can: false, reason: null }, asking: false, asked: null,
  };
  private readonly listeners = new Set<() => void>();
  private readonly now: () => Date;
  /** True once this store sent the layer's definition, so two records sent together define it once. */
  private defined = false;
  /** The writes of review records, one after the other, so each record follows its definition. */
  private records: Promise<void> = Promise.resolve();

  constructor(private readonly options: StoreOptions) {
    this.now = options.now ?? (() => new Date());
    options.source.canWrite().then(
      (can) => this.set({ writable: can ? { can, reason: options.simulated ? "sample" : null } : { can, reason: "read-only" } }),
      () => this.set({ writable: { can: false, reason: "unreachable" } }),
    );
  }

  /** The state now. The same object is returned until the state changes. */
  getState = (): StoreState => this.state;

  /** Calls `listener` after every change of the state. Returns the function that ends the subscription. */
  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  private set(part: Partial<StoreState>): void {
    const next = { ...this.state, ...part };
    next.spec = next.saved === null ? null : current(next.saved, next.pending.map((entry) => entry.proposal ?? entry.change));
    this.state = next;
    for (const listener of this.listeners) listener();
  }

  /**
   * Takes a specification read from the server. A stored entry is dropped when this specification
   * holds its change. `confirmed` names entries to drop whatever the specification holds: the
   * store's own read uses it for the entries the server stored before that read started.
   */
  setSaved(saved: Spec | null, confirmed: ReadonlySet<string> = new Set()): void {
    const pending = saved === null
      ? this.state.pending
      : this.state.pending.filter((entry) => !(entry.stored && (confirmed.has(entry.change.id) || holds(saved, entry.change))));
    this.set({ saved, pending });
  }

  /** Reads the dump again and drops the entries the server stored before the read started. */
  async refresh(): Promise<void> {
    const stored = new Set(this.state.pending.filter((entry) => entry.stored).map((entry) => entry.change.id));
    try {
      const dump = await this.options.source.dump(this.options.project);
      this.setSaved(fromDump(this.options.projectName, dump), stored);
    } catch {
      // The page reports a failed read where it shows the connection. The entries stay pending.
    }
  }

  private withNote(note: PartNote | null, key: string): PartNote[] {
    const others = this.state.notes.filter((other) => other.key !== key);
    return note ? [...others, note] : others;
  }

  /** Adds one record to the `review` layer at an element, after the layer's definition. It reports a failure as a note. */
  private record(address: Address, record: ReviewRecord): Promise<void> {
    const { source, project } = this.options;
    const send = async () => {
      try {
        if (!this.defined && !this.state.saved?.layerDefinitions.some((definition) => definition.field === REVIEW_LAYER)) {
          await source.write(project, DEFINE_REVIEW_LAYER);
        }
        this.defined = true;
        await source.write(project, { add: { [address]: { [REVIEW_LAYER]: [record] } } });
      } catch (error) {
        const key = partKey(address, record.what);
        this.set({ notes: this.withNote(noteOf(key, "history", error), key) });
      }
    };
    this.records = this.records.then(send);
    return this.records;
  }

  private reviewRecord(change: Change, by: Origin, state: ReviewRecord["state"], proposal: Proposal | null): ReviewRecord {
    return { what: whatOf(change), by, state, at: this.now().toISOString(), rationale: proposal?.rationale ?? "", simulated: proposal?.simulated ?? false };
  }

  /** Sends one accepted change, then its review record, then reads the dump. False when the change was refused. */
  private async send(change: Change, origin: Origin, proposal: Proposal | null): Promise<boolean> {
    const key = keyOf(change);
    const entry: PendingEntry = { change, origin, proposal: origin === "agent" ? proposal : null, stored: false };
    this.set({ pending: [...this.state.pending.filter((other) => other.change.id !== change.id), entry], notes: this.withNote(null, key) });
    try {
      await this.options.source.write(this.options.project, toCommand(change));
    } catch (error) {
      // The server did not store the change: take it back out and say why, where the edit was made.
      this.set({
        pending: this.state.pending.filter((other) => other.change.id !== change.id),
        proposals: this.state.proposals.map((other) => (other.change.id === change.id ? { ...other, state: "proposed" as const } : other)),
        notes: this.withNote(noteOf(key, "refused", error), key),
      });
      return false;
    }
    await this.record(change.address, this.reviewRecord(change, origin, "accepted", proposal));
    this.set({ pending: this.state.pending.map((other) => (other.change.id === change.id ? { ...other, stored: true } : other)) });
    await this.refresh();
    return true;
  }

  /** Stores the user's own edit. It resolves to false when the page cannot write or the server refused the edit. */
  async edit(change: Change): Promise<boolean> {
    if (!this.state.writable.can) return false;
    return this.send(change, "user", null);
  }

  /**
   * Accepts a proposal, as proposed or as the user edited it. The proposal becomes a change with
   * a review record. An edited proposal is recorded as the user's text, because the user wrote it.
   */
  async accept(id: string, edited?: Change): Promise<boolean> {
    const proposal = this.state.proposals.find((other) => other.change.id === id);
    if (!proposal || proposal.state !== "proposed" || !this.state.writable.can) return false;
    const change = edited ? { ...edited, id } : proposal.change;
    const origin: Origin = edited && !sameChange(edited, proposal.change) ? "user" : "agent";
    const accepted: Proposal = { ...proposal, change, state: "accepted" };
    this.set({ proposals: this.state.proposals.map((other) => (other.change.id === id ? accepted : other)) });
    return this.send(change, origin, accepted);
  }

  /** Rejects a proposal: its state changes and a review record is added. The specification does not change. */
  async reject(id: string): Promise<void> {
    const proposal = this.state.proposals.find((other) => other.change.id === id);
    if (!proposal || proposal.state !== "proposed" || !this.state.writable.can) return;
    this.set({ proposals: this.state.proposals.map((other) => (other.change.id === id ? { ...other, state: "rejected" as const } : other)) });
    await this.record(proposal.change.address, this.reviewRecord(proposal.change, "agent", "rejected", proposal));
    await this.refresh();
  }

  /** Asks the agent service for proposals in a scope. A proposal equal to one that still waits is not added again. */
  async ask(scope: ProposalScope): Promise<void> {
    const spec = this.state.spec;
    if (spec === null || this.state.asking) return;
    this.set({ asking: true });
    try {
      const received = await this.options.agent.propose(spec, scope);
      const waiting = this.state.proposals.filter((other) => other.state === "proposed");
      const fresh = received.filter((proposal) => !waiting.some((other) => sameChange(other.change, proposal.change)));
      this.set({ asking: false, asked: { added: fresh.length, failed: null }, proposals: [...this.state.proposals, ...fresh] });
    } catch (error) {
      this.set({ asking: false, asked: { added: 0, failed: error instanceof Error ? error.message : String(error) } });
    }
  }

  /** Sends the remediation of a refusal through the same write, then reads the dump again. */
  async remedy(key: string): Promise<void> {
    const note = this.state.notes.find((other) => other.key === key);
    if (!note?.remediation || !this.state.writable.can) return;
    try {
      await this.options.source.write(this.options.project, note.remediation);
      this.set({ notes: this.withNote(null, key) });
    } catch (error) {
      this.set({ notes: this.withNote(noteOf(key, "refused", error), key) });
    }
    await this.refresh();
  }

  /** Removes the note at a part. */
  dismiss(key: string): void {
    this.set({ notes: this.withNote(null, key) });
  }
}

/** The store with its state, as a panel takes it. */
export interface Review {
  store: SpecStore;
  state: StoreState;
}

/**
 * The store for the open project, for React. A new store is made when the project or the source
 * changes, so pending changes and proposals never move from one project to another. `saved` is
 * the specification built from the dump the page already reads.
 */
export function useSpecStore(options: Omit<StoreOptions, "project" | "projectName"> & { project: string | null; projectName: string }, saved: Spec | null): Review | null {
  const { source, agent, project, projectName, simulated } = options;
  const store = useMemo(
    () => (project === null ? null : new SpecStore({ source, agent, project, projectName, simulated })),
    // The project's name is read when the store is made; a store is not remade for a new name.
    [source, agent, project, simulated],
  );
  useEffect(() => {
    store?.setSaved(saved);
  }, [store, saved]);
  const state = useSyncExternalStore(store?.subscribe ?? noSubscription, store?.getState ?? noState);
  return store && state ? { store, state } : null;
}

const noSubscription = () => () => {};
const noState = () => null;
