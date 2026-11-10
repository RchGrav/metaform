// The store with the simulated source: accept, confirm, refusal and reject, and the review record
// that goes with each change. No test here uses React or a server.

import { describe, expect, it } from "vitest";
import { createSimulatedAgent } from "../mock/agent";
import { MockSource } from "../mock/source";
import type { MockWorkspace, Tree } from "../mock/workspace";
import { RefusalError } from "../source/errors";
import type { GraphSource, WriteCommand } from "../source/types";
import type { Proposal } from "../spec/changes";
import { fieldEvidence, reviewRecords, wantEvidence } from "../spec/evidence";
import { handDump } from "../spec/fixtures/hand-dump";
import { elementAt, fromDump } from "../spec/model";
import { DEFINE_REVIEW_LAYER, REVIEW_DEFINITION, SpecStore, hasPlaceholder, keyOf, remediationOf } from "./store";

const ENGINE = "code.engine.game";
const BUS = "code.bus.data.event";
const AT = "2026-11-10T12:00:00.000Z";

/** A simulated source over the hand-written dump. `refuse` names commands the source refuses, with the refusal. */
function sourceOf(options: { canWrite?: boolean; refuse?: (command: WriteCommand) => RefusalError | null } = {}) {
  const workspace: MockWorkspace = {
    simulated: true,
    projects: { quake: { id: "quake", name: "quake", folder: "/quake", dump: structuredClone(handDump["."]) as Tree } },
    outside: {},
    agents: [],
    events: [],
  };
  const mock = new MockSource(workspace, { playEvents: false });
  const sent: WriteCommand[] = [];
  const source: Pick<GraphSource, "write" | "dump" | "canWrite"> = {
    dump: (project) => mock.dump(project),
    canWrite: async () => options.canWrite ?? true,
    write: async (project, command) => {
      sent.push(command);
      const refusal = options.refuse?.(command) ?? null;
      if (refusal) throw refusal;
      await mock.write(project, command);
    },
  };
  return { source, sent, mock };
}

async function storeOf(options: Parameters<typeof sourceOf>[0] = {}) {
  const made = sourceOf(options);
  const store = new SpecStore({ source: made.source, agent: createSimulatedAgent(), project: "quake", projectName: "quake", simulated: true, now: () => new Date(AT) });
  store.setSaved(fromDump("quake", await made.mock.dump("quake")));
  await Promise.resolve();
  return { ...made, store };
}

const refusal = (code: string, message: string, remediation: unknown) => new RefusalError({ status: "error", code, message, remediation });

const proposalOf = (id: string, value: string): Proposal => ({
  change: { id, kind: "set-want", address: ENGINE, to: BUS, part: "why", value },
  rationale: "The why starts with a base verb.",
  evidence: ['The why: "receive player input"'],
  proposedBy: "Simulated generator",
  simulated: true,
  state: "proposed",
});

/** An agent service that returns the given proposals. */
const agentOf = (proposals: Proposal[]) => ({ name: "Simulated generator", simulated: true, propose: async () => proposals });

describe("an accepted edit", () => {
  it("is in the specification at once, is sent as one command, and is followed by the layer's definition and one review record", async () => {
    const { store, sent } = await storeOf();
    const done = store.edit({ id: "e1", kind: "set-want", address: ENGINE, to: BUS, part: "why", value: "Receive input events" });
    // Before the server answers: the edit is in `spec`, marked as the user's, and `saved` is unchanged.
    const before = store.getState();
    expect(elementAt(before.spec!, ENGINE)?.wants.find((want) => want.to === BUS)?.why).toBe("Receive input events");
    expect(elementAt(before.saved!, ENGINE)?.wants.find((want) => want.to === BUS)?.why).toBe("receive player input");
    expect(before.pending.map((entry) => [entry.change.id, entry.origin, entry.stored])).toEqual([["e1", "user", false]]);
    expect(await done).toBe(true);
    expect(sent).toEqual([
      { update: { [ENGINE]: { wants: { [BUS]: { why: "Receive input events" } } } } },
      DEFINE_REVIEW_LAYER,
      { add: { [ENGINE]: { review: [{ what: `want ${BUS}`, by: "user", state: "accepted", at: AT, rationale: "", simulated: false }] } } },
    ]);
  });

  it("is dropped from the pending changes when the next read of the dump confirms it, and stays user-authored", async () => {
    const { store } = await storeOf();
    await store.edit({ id: "e1", kind: "set-field", address: BUS, field: "name", value: "Event router" });
    const state = store.getState();
    expect(state.pending).toEqual([]);
    expect(state.spec?.marks).toEqual([]);
    expect(elementAt(state.saved!, BUS)?.name).toBe("Event router");
    expect(fieldEvidence(state.spec!, BUS, "name").status).toBe("user-authored");
    expect(state.saved?.layerDefinitions.map((definition) => definition.address)).toContain(REVIEW_DEFINITION);
  });

  it("defines the review layer once for two edits", async () => {
    const { store, sent } = await storeOf();
    await Promise.all([
      store.edit({ id: "e1", kind: "set-field", address: BUS, field: "name", value: "Event router" }),
      store.edit({ id: "e2", kind: "set-field", address: ENGINE, field: "name", value: "Quake engine" }),
    ]);
    expect(sent.filter((command) => "add" in command && REVIEW_DEFINITION in command.add)).toHaveLength(1);
    expect(store.getState().pending).toEqual([]);
  });

  it("is not sent when the page cannot write", async () => {
    const { store, sent } = await storeOf({ canWrite: false });
    expect(store.getState().writable).toEqual({ can: false, reason: "read-only" });
    expect(await store.edit({ id: "e1", kind: "set-field", address: BUS, field: "name", value: "Event router" })).toBe(false);
    expect(sent).toEqual([]);
  });
});

describe("a refused edit", () => {
  const mismatch = refusal("TECHNICAL_NAME_ALIGNMENT_FAILURE", "technical_name does not match the address", { update: { [BUS]: { technical_name: "event data bus" } } });

  it("is taken back out, and leaves the refusal at the part with the remediation as a command", async () => {
    const { store, sent } = await storeOf({ refuse: (command) => ("update" in command && command.update[BUS]?.technical_name === "router" ? mismatch : null) });
    const change = { id: "e1", kind: "set-field", address: BUS, field: "technical_name", value: "router" } as const;
    expect(await store.edit(change)).toBe(false);
    const state = store.getState();
    expect(state.pending).toEqual([]);
    expect(elementAt(state.spec!, BUS)?.technical_name).toBe("event data bus");
    expect(state.notes).toEqual([
      { key: keyOf(change), kind: "refused", message: "technical_name does not match the address", code: "TECHNICAL_NAME_ALIGNMENT_FAILURE", remediation: { update: { [BUS]: { technical_name: "event data bus" } } } },
    ]);
    // No review record follows a refused change.
    expect(sent).toHaveLength(1);
    // The remediation goes through the same write, and the note is removed.
    await store.remedy(keyOf(change));
    expect(sent[1]).toEqual({ update: { [BUS]: { technical_name: "event data bus" } } });
    expect(store.getState().notes).toEqual([]);
  });

  it("offers no action for a remediation that holds a placeholder", async () => {
    const incomplete = refusal("WANT_INCOMPLETE", "the want has no how", { update: { [ENGINE]: { wants: { [BUS]: { why: "x", how: "<how>" } } } } });
    const { store } = await storeOf({ refuse: (command) => ("update" in command && "wants" in (command.update[ENGINE] ?? {}) ? incomplete : null) });
    await store.edit({ id: "e1", kind: "set-want", address: ENGINE, to: BUS, part: "how", value: "" });
    expect(store.getState().notes[0]?.remediation).toBeNull();
    expect(hasPlaceholder({ a: ["<why>"] })).toBe(true);
    expect(remediationOf({ map: {} })).toBeNull();
    expect(remediationOf({ delete: { a: { wants: ["b"] } } })).toEqual({ delete: { a: { wants: ["b"] } } });
  });

  it("keeps the change and says so when only the review record is refused", async () => {
    const locked = refusal("ELEMENT_NOT_IN_SKELETON", "review records need an element with technical_name, name and role", null);
    const { store } = await storeOf({ refuse: (command) => ("add" in command && "review" in (command.add[BUS] ?? {}) ? locked : null) });
    const change = { id: "e1", kind: "set-field", address: BUS, field: "name", value: "Event router" } as const;
    expect(await store.edit(change)).toBe(true);
    const state = store.getState();
    expect(elementAt(state.saved!, BUS)?.name).toBe("Event router");
    expect(state.notes.map((note) => [note.key, note.kind, note.remediation])).toEqual([[keyOf(change), "history", null]]);
  });
});

describe("proposals", () => {
  it("are not part of the specification before they are accepted", async () => {
    const { store } = await storeOf();
    await store.ask({ kind: "project" });
    const state = store.getState();
    expect(state.proposals.length).toBeGreaterThan(0);
    expect(state.proposals.every((proposal) => proposal.simulated && proposal.state === "proposed")).toBe(true);
    expect(state.spec).toEqual(state.saved);
    // A second request does not add the proposals that still wait.
    await store.ask({ kind: "project" });
    expect(store.getState().proposals).toHaveLength(state.proposals.length);
    expect(store.getState().asked).toEqual({ added: 0, failed: null });
  });

  it("an accepted proposal becomes a change with a review record by the agent, and reads accepted after the confirmation", async () => {
    const made = sourceOf();
    const store = new SpecStore({ source: made.source, agent: agentOf([proposalOf("p1", "Receive player input")]), project: "quake", projectName: "quake", simulated: true, now: () => new Date(AT) });
    store.setSaved(fromDump("quake", await made.mock.dump("quake")));
    await Promise.resolve();
    await store.ask({ kind: "element", address: ENGINE });
    expect(await store.accept("p1")).toBe(true);
    const state = store.getState();
    expect(state.proposals.map((proposal) => proposal.state)).toEqual(["accepted"]);
    expect(state.pending).toEqual([]);
    expect(elementAt(state.saved!, ENGINE)?.wants.find((want) => want.to === BUS)?.why).toBe("Receive player input");
    expect(reviewRecords(elementAt(state.saved!, ENGINE)!)).toEqual([
      { what: `want ${BUS}`, by: "agent", state: "accepted", at: AT, rationale: "The why starts with a base verb.", simulated: true },
    ]);
    expect(wantEvidence(state.spec!, ENGINE, BUS).status).toBe("accepted");
  });

  it("a proposal the user edits is recorded as the user's text", async () => {
    const made = sourceOf();
    const proposal = proposalOf("p1", "Receive player input");
    const store = new SpecStore({ source: made.source, agent: agentOf([proposal]), project: "quake", projectName: "quake", simulated: true, now: () => new Date(AT) });
    store.setSaved(fromDump("quake", await made.mock.dump("quake")));
    await Promise.resolve();
    await store.ask({ kind: "project" });
    await store.accept("p1", { ...proposal.change, value: "Receive the player's input" } as Proposal["change"]);
    const state = store.getState();
    expect(elementAt(state.saved!, ENGINE)?.wants.find((want) => want.to === BUS)?.why).toBe("Receive the player's input");
    expect(reviewRecords(elementAt(state.saved!, ENGINE)!).map((record) => record.by)).toEqual(["user"]);
    expect(wantEvidence(state.spec!, ENGINE, BUS).status).toBe("user-authored");
  });

  it("a rejected proposal is recorded and changes nothing else", async () => {
    const made = sourceOf();
    const store = new SpecStore({ source: made.source, agent: agentOf([proposalOf("p1", "Receive player input")]), project: "quake", projectName: "quake", simulated: true, now: () => new Date(AT) });
    store.setSaved(fromDump("quake", await made.mock.dump("quake")));
    await Promise.resolve();
    await store.ask({ kind: "project" });
    await store.reject("p1");
    const state = store.getState();
    expect(state.proposals.map((proposal) => proposal.state)).toEqual(["rejected"]);
    expect(made.sent).toEqual([
      DEFINE_REVIEW_LAYER,
      { add: { [ENGINE]: { review: [{ what: `want ${BUS}`, by: "agent", state: "rejected", at: AT, rationale: "The why starts with a base verb.", simulated: true }] } } },
    ]);
    expect(elementAt(state.saved!, ENGINE)?.wants.find((want) => want.to === BUS)?.why).toBe("receive player input");
    expect(wantEvidence(state.spec!, ENGINE, BUS).status).toBe("inferred");
  });

  it("a refused proposal waits again, with the refusal at its part", async () => {
    const made = sourceOf({ refuse: (command) => ("update" in command ? refusal("SHAPE", "refused for the test", null) : null) });
    const store = new SpecStore({ source: made.source, agent: agentOf([proposalOf("p1", "Receive player input")]), project: "quake", projectName: "quake", simulated: true });
    store.setSaved(fromDump("quake", await made.mock.dump("quake")));
    await Promise.resolve();
    await store.ask({ kind: "project" });
    expect(await store.accept("p1")).toBe(false);
    const state = store.getState();
    expect(state.proposals.map((proposal) => proposal.state)).toEqual(["proposed"]);
    expect(state.notes.map((note) => note.message)).toEqual(["refused for the test"]);
    expect(state.spec).toEqual(state.saved);
  });
});
