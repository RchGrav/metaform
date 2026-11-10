// The panels the page has. To add a panel: add its title to strings.ts (`panels.title`), add one
// line to PANELS, and add one line to BODIES. To mount a view in a registered panel, replace that
// panel's entry in BODIES; nothing else in the page names a panel's body.

import type { ComponentType } from "react";
import type { Review as ReviewHandle } from "../review/store";
import type { Address } from "../source";
import * as strings from "../strings";
import { Activity, type ActivityProps } from "../views/Activity";
import { Legend } from "../views/Chrome";
import { Findings } from "../views/Findings";
import { Entity, type EntityFolder } from "../views/Entity";
import { Evidence } from "../views/Evidence";
import type { Spec } from "../spec/model";
import { MarkdownPreview } from "../views/MarkdownPreview";
import { Outline } from "../views/Outline";
import { Review } from "../views/Review";
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
  /** The selected element's folder, as the Entity view takes it; null while nothing is selected. */
  entity: EntityFolder | null;
  /** The project's specification as the page shows it now: the saved one with the pending changes. Null before a project is read. */
  spec: Spec | null;
  /** The store that takes edits and holds the proposals, with its state. Null before a project is open. */
  review: ReviewHandle | null;
  /** The activity stream, as the Activity view takes it. */
  activity: ActivityProps;
}

/** The component that renders a panel's body. */
export type PanelBody = ComponentType<PanelBodyProps>;

function EntityBody({ entity, spec, review }: PanelBodyProps) {
  return entity ? <Entity {...entity} spec={spec} review={review} /> : <p className="panel-note">{strings.panels.noSelection}</p>;
}

function LegendBody({ simulated }: PanelBodyProps) {
  return <Legend simulated={simulated} />;
}

function ActivityBody({ activity }: PanelBodyProps) {
  return <Activity {...activity} />;
}

function OutlineBody({ spec, selection, select }: PanelBodyProps) {
  return spec ? <Outline spec={spec} selected={selection} onSelect={select} /> : <p className="panel-note">{strings.panels.noProject}</p>;
}

function MarkdownBody({ spec, selection, review }: PanelBodyProps) {
  // The Markdown shows the proposals that are not accepted only in its one marked section.
  const proposals = review?.state.proposals.filter((proposal) => proposal.state !== "accepted") ?? [];
  return spec ? <MarkdownPreview spec={spec} proposals={proposals} scope={selection} /> : <p className="panel-note">{strings.panels.noProject}</p>;
}

function EvidenceBody({ spec, selection, select }: PanelBodyProps) {
  if (!spec) return <p className="panel-note">{strings.panels.noProject}</p>;
  if (selection === null) return <p className="panel-note">{strings.panels.noSelectionEvidence}</p>;
  return <Evidence spec={spec} address={selection} onSelect={select} />;
}

function ReviewBody({ spec, selection, select, review }: PanelBodyProps) {
  return spec && review ? <Review spec={spec} review={review} selection={selection} onSelect={select} /> : <p className="panel-note">{strings.panels.noProject}</p>;
}

function FindingsBody({ spec, selection, select }: PanelBodyProps) {
  return spec ? <Findings spec={spec} selected={selection} onSelect={select} /> : <p className="panel-note">{strings.panels.noProject}</p>;
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
  evidence: EvidenceBody,
  findings: FindingsBody,
  review: ReviewBody,
};

/** The body component of the panel with this id, or null when no panel has it. */
export function bodyOf(id: string): PanelBody | null {
  return Object.prototype.hasOwnProperty.call(BODIES, id) ? BODIES[id as PanelId] : null;
}
