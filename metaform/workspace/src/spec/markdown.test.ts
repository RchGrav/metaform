import { describe, expect, it } from "vitest";
import { applyChange, current } from "./changes";
import type { Proposal } from "./changes";
import { handDump } from "./fixtures/hand-dump";
import { fileName, toMarkdown } from "./markdown";
import { fromDump } from "./model";

const spec = fromDump("quake", handDump);
const whole = toMarkdown(spec, { scope: null });

const proposal = (id: string, state: Proposal["state"], value: string): Proposal => ({
  change: { id, kind: "set-field", address: "code.queue.dead_letter", field: "name", value },
  rationale: "The source calls it so.",
  evidence: ["./src/dlq.c"],
  proposedBy: "Sample agent",
  simulated: true,
  state,
});
const proposals = [proposal("p1", "proposed", "Morgue"), proposal("p2", "rejected", "Graveyard"), proposal("p3", "accepted", "Parking lot")];

const headings = (text: string, level: number) =>
  text.split("\n").filter((line) => line.startsWith(`${"#".repeat(level)} `)).map((line) => line.slice(level + 1));

describe("toMarkdown sections", () => {
  it("puts the sections in order and leaves out proposals by default", () => {
    expect(headings(whole, 1)).toEqual(["Functional specification: quake"]);
    expect(headings(whole, 2)).toEqual([
      "Project overview", "Functional elements", "Outside parties and dependencies", "Evidence", "Open items",
    ]);
  });

  it("names the Definitive element, who the project serves and what it relies on in the overview", () => {
    const overview = whole.slice(whole.indexOf("## Project overview"), whole.indexOf("## Functional elements"));
    expect(overview).toContain("### What the project is\n\n- **Quake core** (`code.engine.game`): game engine");
    expect(overview).toContain("### Who the project serves\n\n- **Studio developer** (`downstream.developer.game`): game developer");
    expect(overview).toContain("### What the project relies on\n\n- **Bullet** (`upstream.code.engine.physics`): physics engine");
    expect(overview).toContain("This document covers all 6 elements of the map.");
  });

  it("groups functional elements by first segment and gives each its kind, role, source and wants", () => {
    const elements = whole.slice(whole.indexOf("## Functional elements"), whole.indexOf("## Outside parties"));
    expect(headings(elements, 3)).toEqual(["Code", "Data"]);
    expect(headings(elements, 4)).toEqual([
      "Pulsar router (`code.bus.data.event`)",
      "Quake core (`code.engine.game`)",
      "dead letter queue (`code.queue.dead_letter`)",
      "Wire | format (`data.schema.message`)",
    ]);
    expect(elements).toContain("- Kind: game engine\n- Role: Definitive\n- Source: `./src/engine.c`\n- Evidence: source-backed");
    expect(elements).toContain("- Role: none recorded\n- Status: not built\n- Source: none recorded\n- Evidence: unverified");
    expect(elements).toContain(
      "**Relies on**\n\n- Pulsar router (`code.bus.data.event`)\n  - Why: receive player input\n  - How: dispatches event streams\n  - Direction: inbound",
    );
    expect(elements).toContain("**Relied on by**\n\n- Studio developer (`downstream.developer.game`)\n  - Why: build a playable game");
  });

  it("writes the specification layer beneath the element, with headings below the element's", () => {
    expect(whole).toContain("The engine draws and simulates.\n\n##### Frame loop\n\nOne pass per frame.\n\n###### R-1.2 Timing\n\nA frame takes 16 ms.");
  });

  it("lists source paths by element and the open items by kind", () => {
    expect(whole).toContain("| Quake core | `code.engine.game` | source-backed | `./src/engine.c`, `./docs/engine.md`, `./docs/loop.md` |");
    expect(whole).toContain("| Wire \\| format | `data.schema.message` | source-backed | `./src/wire.h` |");
    expect(whole).toContain("| Pulsar router | `code.bus.data.event` | unverified | none recorded |");
    const open = whole.slice(whole.indexOf("## Open items"));
    expect(open).toContain("### Not built\n\n- dead letter queue (`code.queue.dead_letter`)");
    expect(open).toContain("### Divergent\n\n- Wire | format (`data.schema.message`)");
    expect(open).toContain("### No role\n\n- dead letter queue (`code.queue.dead_letter`)");
    expect(open).toContain("- Studio developer (`downstream.developer.game`)");
  });

  it("includes only the sections the options ask for", () => {
    const text = toMarkdown(spec, { scope: null, sections: { overview: false, evidence: false, open: false } });
    expect(headings(text, 2)).toEqual(["Functional elements", "Outside parties and dependencies"]);
  });

  it("never shows an intake abbreviation", () => {
    expect(whole).not.toMatch(/\b(RE|PE|OP|EF|IFD|CQU|DE|SE|NE|AUE)\b/);
  });
});

describe("toMarkdown scope", () => {
  const scoped = toMarkdown(spec, { scope: "code.engine" });

  it("holds the scope's elements and the outside elements related to them", () => {
    expect(scoped).toContain("Scope: `code.engine` and every element beneath that address.");
    expect(scoped).toContain("This document covers 3 of the 6 elements of the map.");
    expect(headings(scoped, 4)).toEqual([
      "Quake core (`code.engine.game`)", "Studio developer (`downstream.developer.game`)", "Bullet (`upstream.code.engine.physics`)",
    ]);
    expect(scoped).not.toContain("| Pulsar router |");
  });

  it("says so when the scope holds nothing", () => {
    const empty = toMarkdown(spec, { scope: "media" });
    expect(empty).toContain("The scope holds no functional elements.");
    expect(empty).toContain("The scope has no outside parties and no dependencies.");
  });

  it("names the file after the project and the scope", () => {
    expect(fileName(spec, null)).toBe("quake-specification.md");
    expect(fileName(spec, "code.engine")).toBe("quake-code.engine-specification.md");
    expect(fileName({ ...spec, project: "my project/1" }, null)).toBe("my-project-1-specification.md");
  });
});

describe("toMarkdown and proposals", () => {
  it("leaves every proposal out unless the option asks, even when proposals are given", () => {
    const text = toMarkdown(spec, { scope: null, proposals });
    expect(text).toBe(whole);
    for (const word of ["Morgue", "Graveyard", "Parking lot", "Sample agent"]) expect(text).not.toContain(word);
  });

  it("puts proposed and rejected proposals in one marked section, and nowhere else", () => {
    const text = toMarkdown(spec, { scope: null, proposals, sections: { proposals: true } });
    const at = text.indexOf("## Proposals that are not accepted");
    expect(at).toBeGreaterThan(text.indexOf("## Open items"));
    expect(`${text.slice(0, at).trimEnd()}\n`).toBe(whole);
    const section = text.slice(at);
    expect(section).toContain("> The proposals in this section are not part of the specification.");
    expect(section).toContain('### 1. Set the field `name` of `code.queue.dead_letter` to "Morgue"');
    expect(section).toContain("- State: agent-proposed");
    expect(section).toContain('### 2. Set the field `name` of `code.queue.dead_letter` to "Graveyard"');
    expect(section).toContain("- State: rejected");
    expect(section).toContain("- Proposed by: Sample agent (simulated; no agent service made this proposal)");
    expect(section).toContain("- Evidence cited: `./src/dlq.c`");
    expect(section).not.toContain("Parking lot");
  });

  it("limits the proposals section to the scope", () => {
    const text = toMarkdown(spec, { scope: "code.engine", proposals, sections: { proposals: true } });
    expect(text).toContain("There are no proposals in this scope that are not accepted.");
  });

  it("shows an accepted change in the specification and lists it as not confirmed", () => {
    const text = toMarkdown(current(spec, proposals), { scope: null });
    expect(text).toContain("#### Parking lot (`code.queue.dead_letter`)");
    expect(text).toContain("### Changes the server has not confirmed\n\n- `code.queue.dead_letter`, the field `name`: accepted");
    expect(text).not.toContain("Morgue");
    const edited = applyChange(spec, { id: "u", kind: "set-field", address: "code.bus.data.event", field: "uri", value: "./src/bus.c" });
    expect(toMarkdown(edited, { scope: null })).toContain("- `code.bus.data.event`, the field `uri`: user-authored");
  });
});

describe("toMarkdown determinism", () => {
  it("gives the same text for the same specification and options", () => {
    const options = { scope: "code", proposals, sections: { proposals: true } };
    expect(toMarkdown(spec, options)).toBe(toMarkdown(fromDump("quake", handDump), options));
  });

  it("does not depend on the order of the keys in the dump", () => {
    const tree = handDump["."] as Record<string, unknown>;
    const reversed = { ".": Object.fromEntries(Object.entries(tree).reverse()) };
    expect(toMarkdown(fromDump("quake", reversed), { scope: null })).toBe(whole);
  });

  it("ends with one line break", () => {
    expect(whole.endsWith("\n")).toBe(true);
    expect(whole.endsWith("\n\n")).toBe(false);
  });
});
