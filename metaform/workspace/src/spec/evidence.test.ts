import { describe, expect, it } from "vitest";
import { applyChange } from "./changes";
import type { Proposal } from "./changes";
import { elementEvidence, fieldEvidence, layerEvidence, proposalEvidence, sourcePaths, wantEvidence } from "./evidence";
import { handDump } from "./fixtures/hand-dump";
import { elementAt, fromDump } from "./model";

const spec = fromDump("quake", handDump);
const at = (address: string) => {
  const element = elementAt(spec, address);
  if (!element) throw new Error(`no element at ${address}`);
  return element;
};

describe("element evidence", () => {
  it("is source-backed with the source reference first, then the sources layer, each path once", () => {
    expect(sourcePaths(at("code.engine.game"))).toEqual(["./src/engine.c", "./docs/engine.md", "./docs/loop.md"]);
    expect(elementEvidence(at("code.engine.game")).status).toBe("source-backed");
    expect(elementEvidence(at("data.schema.message"))).toEqual({ status: "source-backed", paths: ["./src/wire.h"] });
  });

  it("is unverified when the element has no source reference", () => {
    expect(elementEvidence(at("code.bus.data.event"))).toEqual({ status: "unverified", paths: [] });
  });

  it("is source-backed from the sources layer alone", () => {
    const next = applyChange(spec, { id: "s", kind: "set-layer", address: "code.bus.data.event", layer: "sources", records: ["./src/bus.c"] });
    const bus = elementAt(next, "code.bus.data.event");
    expect(bus && elementEvidence(bus)).toEqual({ status: "source-backed", paths: ["./src/bus.c"] });
  });
});

describe("want and field evidence", () => {
  it("is inferred for what the map holds, and source-backed for the source reference", () => {
    expect(wantEvidence(spec, "code.engine.game", "code.bus.data.event")).toEqual({ status: "inferred", paths: [] });
    expect(fieldEvidence(spec, "code.engine.game", "name").status).toBe("inferred");
    expect(fieldEvidence(spec, "code.engine.game", "uri")).toEqual({ status: "source-backed", paths: ["./src/engine.c"] });
    expect(fieldEvidence(spec, "code.bus.data.event", "uri").status).toBe("inferred");
    expect(layerEvidence(spec, "code.engine.game", "specification")).toBeNull();
  });

  it("is user-authored after the user's change and accepted after an agent's accepted change", () => {
    const byUser = applyChange(spec, { id: "a", kind: "set-field", address: "code.engine.game", field: "uri", value: "./src/core.c" });
    expect(fieldEvidence(byUser, "code.engine.game", "uri").status).toBe("user-authored");
    const byAgent = applyChange(
      spec,
      { id: "b", kind: "set-want", address: "code.engine.game", to: "code.bus.data.event", part: "how", value: "sends events" },
      "agent",
    );
    expect(wantEvidence(byAgent, "code.engine.game", "code.bus.data.event").status).toBe("accepted");
    expect(wantEvidence(byAgent, "code.engine.game", "upstream.code.engine.physics").status).toBe("inferred");
    const layer = applyChange(spec, { id: "c", kind: "set-layer", address: "code.engine.game", layer: "specification", records: [] });
    expect(layerEvidence(layer, "code.engine.game", "specification")?.status).toBe("user-authored");
  });
});

describe("proposal evidence", () => {
  it("follows the review state and carries the cited paths", () => {
    const proposal: Proposal = {
      change: { id: "p", kind: "remove-want", address: "code.engine.game", to: "code.bus.data.event" },
      rationale: "The engine polls input itself.", evidence: ["./src/input.c"], proposedBy: "Sample agent", simulated: true, state: "proposed",
    };
    expect(proposalEvidence(proposal)).toEqual({ status: "agent-proposed", paths: ["./src/input.c"] });
    expect(proposalEvidence({ ...proposal, state: "accepted" }).status).toBe("accepted");
    expect(proposalEvidence({ ...proposal, state: "rejected" }).status).toBe("rejected");
  });
});
