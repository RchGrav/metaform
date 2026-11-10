// The two specification views, rendered to static HTML. These tests show what each view puts on
// the page. They do not perform a click, a copy or a download.

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Proposal } from "../spec/changes";
import { handDump } from "../spec/fixtures/hand-dump";
import { toMarkdown } from "../spec/markdown";
import { fromDump } from "../spec/model";
import { MarkdownPreview } from "./MarkdownPreview";
import { Outline } from "./Outline";

const spec = fromDump("quake", handDump);

/** The text a reader sees: tags removed and the entities React writes turned back into characters. */
const textOf = (html: string) =>
  html.replace(/<[^>]+>/g, "").replace(/&quot;/g, '"').replace(/&#x27;/g, "'").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");

describe("Outline", () => {
  const html = renderToStaticMarkup(<Outline spec={spec} selected="code.engine.game" onSelect={() => {}} />);

  it("shows the sections, a row for each element, and each status as a mark and a word", () => {
    for (const title of ["Project overview", "Functional elements", "Outside parties and dependencies", "Evidence", "Open items"]) {
      expect(html).toContain(`<h3>${title}</h3>`);
    }
    for (const element of spec.elements) expect(html).toContain(`<span class="spec-row-address">${element.address}</span>`);
    expect(html).toContain('<span class="spec-status-word">source-backed</span>');
    expect(html).toContain('<span class="spec-status-word">unverified</span>');
    expect(html).toContain('<span class="spec-status-mark" aria-hidden="true">●</span>');
  });

  it("marks only the selected element's rows as current", () => {
    const current = html.match(/<button[^>]*aria-current="true"[^>]*>/g) ?? [];
    expect(current.length).toBeGreaterThan(0);
    for (const button of current) expect(button).toContain("Quake core, code.engine.game.");
  });

  it("says so when the map holds no elements", () => {
    const empty = renderToStaticMarkup(<Outline spec={fromDump("empty", {})} selected={null} onSelect={() => {}} />);
    expect(empty).toContain("The map holds no elements yet.");
  });
});

describe("MarkdownPreview", () => {
  const proposals: Proposal[] = [{
    change: { id: "p1", kind: "set-field", address: "code.queue.dead_letter", field: "name", value: "Morgue" },
    rationale: "The source calls it so.", evidence: [], proposedBy: "Sample agent", simulated: true, state: "proposed",
  }];

  it("shows the Markdown of the whole project, without proposals, and the two actions", () => {
    const html = renderToStaticMarkup(<MarkdownPreview spec={spec} proposals={proposals} scope={null} />);
    const shown = textOf(html.slice(html.indexOf("<pre"), html.indexOf("</pre>")));
    expect(shown).toBe(toMarkdown(spec, { scope: null }));
    expect(shown).not.toContain("Morgue");
    expect(html.match(/<button/g)).toHaveLength(2);
    expect(html).toContain(">Copy</button>");
    expect(html).toContain(">Download</button>");
    expect(html).toContain("The browser saves the file to its downloads folder.");
    expect(html).not.toContain('type="radio"');
  });

  it("starts at the whole project and offers the scope it is given", () => {
    const html = renderToStaticMarkup(<MarkdownPreview spec={spec} proposals={[]} scope="code.engine" />);
    const shown = textOf(html.slice(html.indexOf("<pre"), html.indexOf("</pre>")));
    expect(shown).toBe(toMarkdown(spec, { scope: null }));
    expect(html.match(/type="radio"/g)).toHaveLength(2);
  });
});
