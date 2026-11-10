// The simulated agent: every proposal is marked simulated, and each one follows from the
// specification's own text.

import { describe, expect, it } from "vitest";
import type { RawDump } from "../source/types";
import { handDump } from "../spec/fixtures/hand-dump";
import { elementAt, fromDump } from "../spec/model";
import { MAX_PROPOSALS, SIMULATED_AGENT, SimulatedAgent, baseVerb, rewordHow, rewordWhy } from "./agent";
import { workspace } from "./index";

const dump: RawDump = {
  ".": {
    code: {
      engine: {
        game: {
          technical_name: "game engine", name: "Quake core", role: "Definitive", uri: "./src/engine.c",
          wants: {
            "code.bus.data.event": { why: "to receive player input", how: "it dispatches event streams", direction: "inbound" },
            "upstream.code.engine.physics": { why: "Resolves collisions", how: "Steps rigid bodies", direction: "two-way" },
          },
        },
      },
      bus: { data: { event: { technical_name: "event data bus", name: "Pulsar router", role: "Supportive" } } },
    },
    downstream: {
      developer: { game: { technical_name: "game developer", name: "Studio developer", wants: { "code.engine.game": { why: "Build a playable game", how: "Provides the frame loop", direction: "inbound" } } } },
      player: { game: { technical_name: "game player", name: "Player", role: "Notable" } },
    },
    upstream: { code: { engine: { physics: { technical_name: "physics engine", name: "Bullet" } } } },
  },
};
const spec = fromDump("quake", dump);

describe("rewording", () => {
  it("gives a why that starts with a base verb, from the words the why already holds", () => {
    expect(rewordWhy("to receive player input")?.after).toBe("receive player input");
    expect(rewordWhy("In order to keep frames")?.after).toBe("Keep frames");
    expect(rewordWhy("Resolves collisions")?.after).toBe("Resolve collisions");
    expect(rewordWhy("carries the packets")?.after).toBe("carry the packets");
    expect(rewordWhy("Resolve collisions")).toBeNull();
    expect(rewordWhy("Process frames")).toBeNull();
    expect(rewordWhy("Users can sign in")).toBeNull();
    expect(baseVerb("dispatches")).toBe("dispatch");
    expect(baseVerb("always")).toBeNull();
  });

  it("gives a how that says what the provider does, as the end of the given text", () => {
    expect(rewordHow("it dispatches event streams")?.after).toBe("dispatches event streams");
    expect(rewordHow("The provider steps rigid bodies")?.after).toBe("Steps rigid bodies");
    expect(rewordHow("Steps rigid bodies")).toBeNull();
  });
});

describe("the simulated agent", () => {
  it("marks every proposal simulated, with a rationale and evidence", async () => {
    const proposals = await new SimulatedAgent().propose(spec, { kind: "project" });
    expect(proposals.length).toBeGreaterThan(0);
    for (const proposal of proposals) {
      expect(proposal.simulated).toBe(true);
      expect(proposal.state).toBe("proposed");
      expect(proposal.proposedBy).toBe(SIMULATED_AGENT);
      expect(proposal.rationale).not.toBe("");
      expect(proposal.evidence.length).toBeGreaterThan(0);
    }
    expect(new Set(proposals.map((proposal) => proposal.change.id)).size).toBe(proposals.length);
  });

  it("derives each reworded text from the text the specification holds", async () => {
    const proposals = await new SimulatedAgent().propose(spec, { kind: "project" });
    const rewordings = proposals.flatMap((proposal) => (proposal.change.kind === "set-want" ? [{ proposal, change: proposal.change }] : []));
    expect(rewordings.map(({ change }) => [change.to, change.part, change.value])).toEqual([
      ["code.bus.data.event", "why", "receive player input"],
      ["code.bus.data.event", "how", "dispatches event streams"],
      ["upstream.code.engine.physics", "why", "Resolve collisions"],
    ]);
    for (const { proposal, change } of rewordings) {
      const before = elementAt(spec, change.address)?.wants.find((want) => want.to === change.to)?.[change.part] ?? "";
      // The evidence quotes the text before, and every word after the first is a word of that text.
      expect(proposal.evidence.join(" ")).toContain(`"${before}"`);
      const wordsBefore = before.toLowerCase().split(/\s+/);
      const [first = "", ...rest] = change.value.toLowerCase().split(/\s+/);
      for (const word of rest) expect(wordsBefore).toContain(word);
      expect(wordsBefore.some((word) => word.startsWith(first.replace(/y$/, "")))).toBe(true);
    }
  });

  it("gives an outside party with no role the role the map gives the others, or the role its band implies", async () => {
    const proposals = await new SimulatedAgent().propose(spec, { kind: "project" });
    const roles = proposals.flatMap((proposal) => (proposal.change.kind === "set-field" && proposal.change.field === "role" ? [[proposal.change.address, proposal.change.value]] : []));
    expect(roles).toEqual([["downstream.developer.game", "Notable"], ["upstream.code.engine.physics", "Supportive"]]);
  });

  it("proposes not built only for an element the outline lists with no source reference", async () => {
    const proposals = await new SimulatedAgent().propose(spec, { kind: "project" });
    const marked = proposals.flatMap((proposal) => (proposal.change.kind === "set-field" && proposal.change.field === "status" ? [proposal.change.address] : []));
    expect(marked).toEqual(["code.bus.data.event"]);
  });

  it("keeps to the scope, and to the limit of one request", async () => {
    const agent = new SimulatedAgent();
    const element = await agent.propose(spec, { kind: "element", address: "upstream.code.engine.physics" });
    expect(element.map((proposal) => proposal.change.address)).toEqual(["upstream.code.engine.physics"]);
    const area = await agent.propose(spec, { kind: "area", prefix: "code.engine" });
    expect(area.every((proposal) => proposal.change.address.startsWith("code.engine"))).toBe(true);
    expect(await agent.propose(fromDump("quake", handDump), { kind: "element", address: "code.engine.game" })).toEqual([]);
    const sample = Object.values(workspace.projects)[0];
    const large = await agent.propose(fromDump("sample", { ".": sample?.dump ?? {} }), { kind: "project" });
    expect(large.length).toBeLessThanOrEqual(MAX_PROPOSALS);
    expect(large.every((proposal) => proposal.simulated)).toBe(true);
  });
});
