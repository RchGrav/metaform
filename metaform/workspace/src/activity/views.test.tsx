// The Findings panel and the Activity panel, rendered to static HTML in each of their states.
// These tests show what each view puts on the page. They do not perform a click or a scroll.

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { handDump } from "../spec/fixtures/hand-dump";
import { fromDump } from "../spec/model";
import type { Spec } from "../spec/model";
import { Activity, ActivityContent } from "../views/Activity";
import type { ActivityContentProps, ActivityItem } from "../views/Activity";
import { Findings } from "../views/Findings";
import { FINDING_KINDS, findingsOf } from "./findings";
import { kindTitles } from "./strings";
import { diff } from "./stream";

const spec = fromDump("quake", handDump);
const textOf = (html: string) => html.replace(/<[^>]+>/g, "").replace(/&quot;/g, '"').replace(/&#x27;/g, "'");
const ABBREVIATIONS = /\b(RE|PE|OP|EF|IFD|CQU)\b/;

describe("Findings", () => {
  const html = renderToStaticMarkup(<Findings spec={spec} selected="data.schema.message" onSelect={() => {}} />);

  it("says where the findings come from, and does not say that an analysis took place", () => {
    expect(html).toContain("The page reads these findings from the specification as the map holds it.");
    expect(html).toContain("The page performed no analysis of the repository.");
  });

  it("groups the findings by kind with a count, and has a filter for every kind", () => {
    const all = findingsOf(spec);
    expect(html).toContain(`>All kinds (${all.length})</button>`);
    for (const kind of FINDING_KINDS) {
      const n = all.filter((finding) => finding.kind === kind).length;
      expect(html).toContain(`${kindTitles[kind]} (${n})</button>`);
      expect(html.includes(`${kindTitles[kind]} <span class="act-count">`)).toBe(n > 0);
    }
    expect(html.match(/<button[^>]*disabled=""/g)).toHaveLength(3);
    expect(html.match(/class="act-row"/g)).toHaveLength(all.length);
  });

  it("shows each finding's sentence, element and evidence, and marks the selected element's findings", () => {
    const text = textOf(html);
    expect(text).toContain("dead letter queue is not built.");
    expect(text).toContain('Evidence: The map holds the status "un_built".');
    expect(text).toContain("dead letter queue · code.queue.dead_letter");
    const current = html.match(/<button[^>]*aria-current="true"[^>]*>.*?<\/button>/g) ?? [];
    expect(current).toHaveLength(2);
    for (const row of current) expect(row).toContain("data.schema.message");
    expect(text).not.toMatch(ABBREVIATIONS);
  });

  it("says that there is no open finding, and lists the kinds the page checks", () => {
    const clean: Spec = {
      ...spec,
      elements: [
        { address: "code.a", band: "project", name: "A", role: "Definitive", uri: "./a", layers: {}, wants: [{ to: "code.b", why: "w", how: "h", direction: "inbound" }] },
        { address: "code.b", band: "project", name: "B", role: "Supportive", uri: "./b", layers: {}, wants: [] },
      ],
    };
    const empty = renderToStaticMarkup(<Findings spec={clean} selected={null} onSelect={() => {}} />);
    expect(empty).toContain("The specification has no open findings of the kinds this page checks.");
    for (const kind of FINDING_KINDS) expect(empty).toContain(`<strong>${kindTitles[kind]}.</strong>`);
    expect(empty).not.toContain("<button");
  });

  it("says so when the map holds no elements", () => {
    const none = renderToStaticMarkup(<Findings spec={fromDump("empty", {})} selected={null} onSelect={() => {}} />);
    expect(none).toContain("The map holds no elements yet, so there is nothing to check.");
  });
});

const at = new Date("2026-11-10T09:30:00Z");
const changed: Spec = {
  ...spec,
  elements: spec.elements.map((element) => (element.address === "code.engine.game" ? { ...element, name: "Quake heart" } : element)),
  rootLayers: {},
};
const real = diff(spec, changed, at);
const sample: ActivityItem = {
  id: "s1", type: "test-result", time: new Date("2026-11-10T09:31:00Z"), status: "failed", scope: "code.bus.data.event",
  element: "code.bus.data.event", summary: "2 of 14 tests failed.", details: { text: "A sample result." }, simulated: true,
};
const noop = () => {};
const content = (props: Partial<ActivityContentProps>) =>
  renderToStaticMarkup(
    <ActivityContent
      listed={[]} hidden={0} connection="connected" paused={false} waiting={0} type={null} onlySelected={false} selected={null}
      openId={null} canReturn={false} newAbove={0} onPause={noop} onType={noop} onOnlySelected={noop} onChoose={noop} onReturn={noop} onTop={noop}
      {...props}
    />,
  );

describe("Activity", () => {
  it("lists the items newest first when connected, each with its type, status and scope", () => {
    const html = renderToStaticMarkup(<Activity items={[...real, sample]} connection="connected" selected="code.engine.game" onSelect={noop} onReturn={noop} />);
    const text = textOf(html);
    expect(text).toContain("Connected. A change to the map is listed when the server announces it.");
    const order = ["2 of 14 tests failed.", "at the project's root changed.", "The name of Quake heart changed."].map((part) => text.indexOf(part));
    expect(order.every((index) => index >= 0)).toBe(true);
    expect(order).toEqual([...order].sort((a, b) => a - b));
    expect(text).toContain("Field changed");
    expect(text).toContain("●recorded");
    expect(text).toContain("✕failed");
    expect(html).toContain('<span class="act-row-address">the project</span>');
    expect(html.match(/aria-current="true"/g)).toHaveLength(1);
    expect(html.match(/>Simulated</g)).toHaveLength(1);
    expect(html).toContain('aria-pressed="false"');
    expect(text).not.toMatch(ABBREVIATIONS);
  });

  it("labels an item of a type with no source as simulated, even when its flag is not set", () => {
    const html = content({ listed: [{ ...sample, simulated: false }] });
    expect(html.match(/>Simulated</g)).toHaveLength(1);
  });

  it("says that the data is sample data, and labels each item", () => {
    const items = diff(spec, changed, at, true);
    const html = renderToStaticMarkup(<Activity items={items} connection="simulated" selected={null} onSelect={noop} onReturn={noop} />);
    expect(html).toContain("Sample data. Every item is simulated; no server sent it.");
    expect(html.match(/>Simulated</g)).toHaveLength(items.length);
  });

  it("says that it is paused and how many items wait, and does not list them", () => {
    const html = content({ listed: [real[0]!], paused: true, waiting: 3 });
    expect(textOf(html)).toContain("‖Paused. 3 waiting.");
    expect(html).toContain('aria-pressed="true"');
    expect(html).toContain(">Resume</button>");
    expect(html.match(/class="act-item"/g)).toHaveLength(1);
  });

  it("says that there is no activity, in each state that can be empty", () => {
    expect(content({})).toContain("No activity yet.");
    const lost = content({ connection: "not-connected" });
    expect(lost).toContain("Not connected. No new item can arrive until the page reaches the server again.");
    expect(lost).toContain("No activity is listed.");
    expect(content({ paused: true, waiting: 2 })).toContain("No item arrived before the pause.");
    expect(content({ hidden: 4, type: "want-added" })).toContain("No item matches the filters. The filters hide 4 items.");
  });

  it("shows the details of the chosen item, with before and after, and offers the way back", () => {
    const item = real[0]!;
    const html = content({ listed: real, openId: item.id, canReturn: true, selected: item.element });
    expect(html).toContain('aria-expanded="true"');
    expect(html.match(/role="region"/g)).toHaveLength(1);
    expect(html).toContain('<th scope="row">name</th><td>Quake core</td><td>Quake heart</td>');
    expect(html).toContain("<dt>Affected element</dt><dd>code.engine.game</dd>");
    expect(html).toContain(">Back to where I was</button>");
    expect(content({ listed: real, openId: item.id })).not.toContain("Back to where I was");
  });

  it("shows a value the map did not hold as not recorded", () => {
    const html = content({ listed: [{ ...real[0]!, details: { changes: [{ what: "role", before: null, after: "Notable" }] } }], openId: real[0]!.id });
    expect(html).toContain('<th scope="row">role</th><td><em>not recorded</em></td><td>Notable</td>');
  });

  it("says how many items are new above while the user has scrolled away", () => {
    expect(content({ listed: real, newAbove: 2 })).toContain("2 new items above. Go to the top</button>");
    expect(content({ listed: real })).not.toContain("above. Go to the top");
  });
});
