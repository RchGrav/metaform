// Tests on a real dump: the answer of {".": {}} for the project rmcp-3.9.0, read once from a
// metaform-web host on the home ~/.metaform-climb on 2026-11-09 and saved unchanged.

import { describe, expect, it } from "vitest";
import { elementEvidence } from "./evidence";
import dump from "./fixtures/rmcp-3.9.0.dump.json";
import { toMarkdown } from "./markdown";
import { definitiveOf, fromDump } from "./model";
import { functionalGroups } from "./sections";
import type { RawDump } from "../source/types";

const spec = fromDump("rmcp-3.9.0", dump as RawDump);

describe("fromDump on the rmcp-3.9.0 dump", () => {
  it("finds the elements in three bands and keeps the layer definition apart", () => {
    const bands = new Set(spec.elements.map((element) => element.band));
    expect([...bands].sort()).toEqual(["downstream", "project", "upstream"]);
    expect(spec.elements.every((element) => !element.address.startsWith("layer"))).toBe(true);
    expect(spec.layerDefinitions.map((definition) => definition.address)).toEqual(["layer.document.specification"]);
    expect(definitiveOf(spec)?.address).toBe("code.sdk.mcp");
    expect(functionalGroups(spec, null).map((group) => group.segment)).toEqual(["code", "data"]);
  });

  it("resolves every want to an element and reads all three parts", () => {
    const addresses = new Set(spec.elements.map((element) => element.address));
    const wants = spec.elements.flatMap((element) => element.wants);
    expect(wants.length).toBeGreaterThan(0);
    for (const want of wants) {
      expect(addresses.has(want.to)).toBe(true);
      expect(want.why).not.toBe("");
      expect(want.how).not.toBe("");
      expect(["inbound", "outbound", "two-way"]).toContain(want.direction);
    }
  });

  it("reads the not-built element and the specification layer", () => {
    const websocket = spec.elements.find((element) => element.address === "code.transport.websocket");
    expect(websocket?.status).toBe("un_built");
    expect(websocket?.layers.specification?.length).toBeGreaterThan(0);
  });
});

describe("toMarkdown on the rmcp-3.9.0 dump", () => {
  const text = toMarkdown(spec, { scope: null });

  it("has a heading for every element and a row of evidence for every element", () => {
    for (const element of spec.elements) {
      expect(text).toContain(`(\`${element.address}\`)\n\n- Kind: `);
      expect(text).toContain(`| \`${element.address}\` | ${elementEvidence(element).status} |`);
    }
    expect(text).toContain(`This document covers all ${spec.elements.length} elements of the map.`);
  });

  it("carries the specification layer's text and lists the not-built element as open", () => {
    expect(text).toContain("The websocket transport is not built.");
    expect(text.slice(text.indexOf("### Not built"))).toContain("(`code.transport.websocket`)");
  });

  it("is the same text on a second pass, and a scope gives a shorter text", () => {
    expect(toMarkdown(fromDump("rmcp-3.9.0", dump as RawDump), { scope: null })).toBe(text);
    const scoped = toMarkdown(spec, { scope: "code.transport" });
    expect(scoped.length).toBeLessThan(text.length);
    expect(scoped).toContain("(`code.transport.websocket`)");
  });
});
