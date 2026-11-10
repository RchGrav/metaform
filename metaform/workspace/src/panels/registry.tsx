// The panels the page has. To add a panel: add its title to strings.ts (`panels.title`), add one
// line to PANELS, and add one line to BODIES. To mount a view in a registered panel, replace that
// panel's entry in BODIES; nothing else in the page names a panel's body.

import type { ComponentProps, ComponentType } from "react";
import type { Address } from "../source";
import * as strings from "../strings";
import { ActivityList, Details, Legend } from "../views/Chrome";
import type { Spec } from "../spec/model";
import { MarkdownPreview } from "../views/MarkdownPreview";
import { Outline } from "../views/Outline";
import type { Zone } from "./layout";

/** The id of a registered panel. */
export type PanelId = keyof typeof strings.panels.title;

/** A registered panel: its id, the title on its tab, its default zone, and whether it is open at first. */
export interface PanelDefinition {
  id: PanelId;
  title: string;
  zone: Zone;
  open: boolean;
}

/**
 * What the page hands the body of every panel. A body uses the parts it needs. Add a part here,
 * and give it a value in App.tsx, when a new body needs something the page holds.
 */
export interface PanelBodyProps {
  /** The id of the project the page shows, or null before one is open. */
  project: string | null;
  /** The address of the selected element, or null. */
  selection: Address | null;
  /** True while the data is simulated. */
  simulated: boolean;
  /** Selects an element in the graph, or clears the selection with null. */
  select: (address: Address | null) => void;
  /** The selected element's folder, as the Details view takes it; null while nothing is selected. */
  entity: ComponentProps<typeof Details> | null;
  /** The project's specification as the page holds it now, or null before a project is read. */
  spec: Spec | null;
  /** The activity lines, as the ActivityList view takes them. */
  activity: ComponentProps<typeof ActivityList>;
}

/** The component that renders a panel's body. */
export type PanelBody = ComponentType<PanelBodyProps>;

function EntityBody({ entity }: PanelBodyProps) {
  return entity ? <Details {...entity} /> : <p className="panel-note">{strings.panels.noSelection}</p>;
}

function LegendBody({ simulated }: PanelBodyProps) {
  return <Legend simulated={simulated} />;
}

function ActivityBody({ activity }: PanelBodyProps) {
  return <ActivityList {...activity} />;
}

function OutlineBody({ spec, selection, select }: PanelBodyProps) {
  return spec ? <Outline spec={spec} selected={selection} onSelect={select} /> : <p className="panel-note">{strings.panels.noProject}</p>;
}

function MarkdownBody({ spec, selection }: PanelBodyProps) {
  // No proposal exists yet; the review step will pass the ones that are not accepted.
  return spec ? <MarkdownPreview spec={spec} proposals={[]} scope={selection} /> : <p className="panel-note">{strings.panels.noProject}</p>;
}

/** The body of a panel that is registered and not built yet: one sentence that says what it will show. */
function notBuilt(id: keyof typeof strings.panels.notBuilt): PanelBody {
  return function NotBuilt() {
    return <p className="panel-note">{strings.panels.notBuilt[id]}</p>;
  };
}

/** Every panel, in the order the Panels menu lists them. */
export const PANELS: readonly PanelDefinition[] = [
  { id: "entity", title: strings.panels.title.entity, zone: "right", open: true },
  { id: "legend", title: strings.panels.title.legend, zone: "right", open: false },
  { id: "activity", title: strings.panels.title.activity, zone: "bottom", open: false },
  { id: "outline", title: strings.panels.title.outline, zone: "left", open: false },
  { id: "markdown", title: strings.panels.title.markdown, zone: "right", open: false },
  { id: "evidence", title: strings.panels.title.evidence, zone: "right", open: false },
  { id: "findings", title: strings.panels.title.findings, zone: "bottom", open: false },
  { id: "review", title: strings.panels.title.review, zone: "bottom", open: false },
];

/** The component that renders each panel's body. */
export const BODIES: Record<PanelId, PanelBody> = {
  entity: EntityBody,
  legend: LegendBody,
  activity: ActivityBody,
  outline: OutlineBody,
  markdown: MarkdownBody,
  evidence: notBuilt("evidence"),
  findings: notBuilt("findings"),
  review: notBuilt("review"),
};

/** The body component of the panel with this id, or null when no panel has it. */
export function bodyOf(id: string): PanelBody | null {
  return Object.prototype.hasOwnProperty.call(BODIES, id) ? BODIES[id as PanelId] : null;
}
