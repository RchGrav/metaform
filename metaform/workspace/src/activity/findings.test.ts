// Each kind of finding, on a specification written by hand and on the real rmcp-3.9.0 dump.

import { describe, expect, it } from "vitest";
import { handDump } from "../spec/fixtures/hand-dump";
import dump from "../spec/fixtures/rmcp-3.9.0.dump.json";
import { fromDump } from "../spec/model";
import type { Spec, SpecElement } from "../spec/model";
import type { RawDump } from "../source/types";
import { FINDING_KINDS, findingsOf, groupByKind } from "./findings";
import type { FindingKind } from "./findings";

const element = (address: string, fields: Partial<SpecElement> = {}): SpecElement => ({
  address, band: "project", name: address, role: "Supportive", uri: `./${address}`, wants: [], layers: {}, ...fields,
});
const want = (to: string, why = "a reason", how = "a means") => ({ to, why, how, direction: "inbound" });
const specOf = (elements: SpecElement[]): Spec => ({ project: "hand", elements, layerDefinitions: [], rootLayers: {}, marks: [] });

/** Two elements with every field, joined by one complete want: a specification with no finding. */
const clean = [element("code.a", { wants: [want("code.b")] }), element("code.b")];
const of = (kind: FindingKind, spec: Spec) => findingsOf(spec).filter((finding) => finding.kind === kind);

describe("findingsOf on a specification written by hand", () => {
  it("finds nothing when every field is present and every element is joined", () => {
    expect(findingsOf(specOf(clean))).toEqual([]);
    expect(groupByKind([]).map((group) => group.kind)).toEqual([...FINDING_KINDS]);
  });

  it("finds an element that is not built, and gives the status as evidence", () => {
    const found = findingsOf(specOf([clean[0]!, element("code.b", { status: "un_built" })]));
    expect(found).toEqual([{
      id: "notBuilt:code.b", kind: "notBuilt", address: "code.b",
      sentence: "code.b is not built.", evidence: 'The map holds the status "un_built".',
    }]);
  });

  it("finds a Divergent element", () => {
    const found = findingsOf(specOf([clean[0]!, element("code.b", { role: "Divergent" })]));
    expect(found.map((finding) => [finding.kind, finding.address, finding.sentence])).toEqual([["divergent", "code.b", "code.b has the role Divergent."]]);
  });

  it("finds an element with no role", () => {
    const { role: _role, ...noRole } = element("code.b");
    const found = findingsOf(specOf([clean[0]!, noRole]));
    expect(found.map((finding) => [finding.kind, finding.address, finding.evidence])).toEqual([["noRole", "code.b", "The map holds no role for this element."]]);
  });

  it("finds an element with no source reference, unless its sources layer holds a path", () => {
    const { uri: _uri, ...noUri } = element("code.b");
    expect(findingsOf(specOf([clean[0]!, noUri])).map((finding) => [finding.kind, finding.address])).toEqual([["noSource", "code.b"]]);
    expect(findingsOf(specOf([clean[0]!, { ...noUri, layers: { sources: ["./b.md"] } }]))).toEqual([]);
  });

  it("finds an element that relies on nothing and that nothing relies on", () => {
    const found = findingsOf(specOf([...clean, element("code.c")]));
    expect(found.map((finding) => [finding.kind, finding.address])).toEqual([["isolated", "code.c"]]);
  });

  it("finds a want whose why or how is blank, once for each want, and ignores a blank direction", () => {
    const holder = element("code.a", { wants: [want("code.b", "", "a means"), want("code.c", " ", ""), { ...want("code.d"), direction: "" }] });
    const found = of("blankWant", specOf([holder, element("code.b"), element("code.c"), element("code.d")]));
    expect(found.map((finding) => finding.sentence)).toEqual([
      "The want that code.a holds for code.b has a blank why.",
      "The want that code.a holds for code.c has a blank why and how.",
    ]);
    expect(found.every((finding) => finding.address === "code.a")).toBe(true);
    expect(found[1]?.evidence).toBe("The map holds no why and how for this want.");
  });

  it("finds a want that names an address the map does not hold", () => {
    const found = findingsOf(specOf([element("code.a", { wants: [want("code.b"), want("code.gone")] }), element("code.b")]));
    expect(found).toEqual([{
      id: "unknownAddress:code.a:code.gone", kind: "unknownAddress", address: "code.a",
      sentence: "code.a holds a want for code.gone, and the map holds no element there.",
      evidence: 'The want names "code.gone". No element in the map has that address.',
    }]);
  });

  it("finds each element that shares a name, and compares the technical name when there is no name", () => {
    const { name: _name, ...unnamed } = element("code.c", { technical_name: "Twin", wants: [want("code.a")] });
    const found = findingsOf(specOf([element("code.a", { name: "Twin", wants: [want("code.b")] }), element("code.b", { name: "Twin" }), unnamed]));
    expect(found.map((finding) => [finding.kind, finding.address])).toEqual([["sameName", "code.a"], ["sameName", "code.b"], ["sameName", "code.c"]]);
    expect(found[0]?.sentence).toBe("Twin has the same name as 2 other elements.");
    expect(found[0]?.evidence).toBe('The name "Twin" is also at code.b and code.c.');
  });

  it("orders the findings by kind, then by address, and gives each a different id", () => {
    const found = findingsOf(fromDump("quake", handDump));
    const ranks = found.map((finding) => FINDING_KINDS.indexOf(finding.kind));
    expect(ranks).toEqual([...ranks].sort((a, b) => a - b));
    expect(new Set(found.map((finding) => finding.id)).size).toBe(found.length);
    expect(Object.fromEntries(groupByKind(found).map((group) => [group.kind, group.findings.map((finding) => finding.address)]))).toEqual({
      notBuilt: ["code.queue.dead_letter"],
      divergent: ["data.schema.message"],
      noRole: ["code.queue.dead_letter"],
      noSource: ["code.bus.data.event", "code.queue.dead_letter", "downstream.developer.game"],
      isolated: ["code.queue.dead_letter", "data.schema.message"],
      blankWant: [],
      unknownAddress: [],
      sameName: [],
    });
  });
});

describe("findingsOf on the rmcp-3.9.0 dump", () => {
  const spec = fromDump("rmcp-3.9.0", dump as RawDump);
  const groups = Object.fromEntries(groupByKind(findingsOf(spec)).map((group) => [group.kind, group.findings]));

  it("finds the one element that is not built", () => {
    expect(groups.notBuilt?.map((finding) => finding.address)).toEqual(["code.transport.websocket"]);
    expect(groups.notBuilt?.[0]?.evidence).toBe('The map holds the status "un_built".');
  });

  it("finds what the dump holds of the other kinds, and nothing more", () => {
    const counts = Object.fromEntries(FINDING_KINDS.map((kind) => [kind, groups[kind]?.length]));
    expect(counts).toEqual({ notBuilt: 1, divergent: 1, noRole: 2, noSource: 0, isolated: 1, blankWant: 0, unknownAddress: 0, sameName: 0 });
    expect(groups.isolated?.[0]?.address).toBe("code.transport.websocket");
    const addresses = new Set(spec.elements.map((element) => element.address));
    for (const finding of findingsOf(spec)) expect(addresses.has(finding.address)).toBe(true);
  });
});
