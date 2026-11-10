// The specification as an outline a user can move through. The sections and their order are those
// of the Markdown, because both read `spec/sections.ts`. The view holds no copy of the
// specification: every row is derived from the `spec` prop on each render.

import type { ReactNode } from "react";
import { elementEvidence, EVIDENCE_STATUSES } from "../spec/evidence";
import type { EvidenceStatus } from "../spec/evidence";
import { labelOf } from "../spec/model";
import type { Spec, SpecElement } from "../spec/model";
import { functionalGroups, openItems, outsideOf, overviewOf } from "../spec/sections";
import {
  common,
  groupTitle,
  OPEN_KINDS,
  openTitles,
  outline as words,
  sectionTitles,
  statusMarks,
  statusMeanings,
  statusWords,
} from "../spec/strings";
import "../spec/spec.css";

/** The props of `Outline`. */
export interface OutlineProps {
  /** The specification the page shows now. */
  spec: Spec;
  /** The address of the selected element, or null when nothing is selected. */
  selected: string | null;
  /** Called with an element's address when the user chooses its row. */
  onSelect: (address: string) => void;
}

interface RowsProps {
  elements: readonly SpecElement[];
  selected: string | null;
  onSelect: (address: string) => void;
}

/** A status as a mark and a word. The mark is decoration; the word carries the meaning. */
function StatusLabel({ status }: { status: EvidenceStatus }) {
  return (
    <span className={`spec-status spec-status-${status}`} title={statusMeanings[status]}>
      <span className="spec-status-mark" aria-hidden="true">
        {statusMarks[status]}
      </span>
      <span className="spec-status-word">{statusWords[status]}</span>
    </span>
  );
}

function Rows({ elements, selected, onSelect }: RowsProps) {
  if (elements.length === 0) return <p className="spec-none">{common.none}</p>;
  return (
    <ul className="spec-rows">
      {elements.map((element) => {
        const status = elementEvidence(element).status;
        return (
          <li key={element.address}>
            <button
              type="button"
              className="spec-row"
              aria-current={element.address === selected ? "true" : undefined}
              aria-label={`${labelOf(element)}, ${element.address}. ${words.statusOf(statusWords[status])}`}
              onClick={() => onSelect(element.address)}
            >
              <span className="spec-row-name">{labelOf(element)}</span>
              <span className="spec-row-address">{element.address}</span>
              <StatusLabel status={status} />
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="spec-section">
      <h3>{title}</h3>
      {children}
    </section>
  );
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="spec-group">
      <h4>{title}</h4>
      {children}
    </div>
  );
}

/**
 * The specification outline: project overview, functional elements, outside parties and
 * dependencies, evidence, and open items. Each element is a row that calls `onSelect` with its
 * address and shows its evidence status as a mark and a word.
 */
export function Outline({ spec, selected, onSelect }: OutlineProps) {
  if (spec.elements.length === 0) {
    return (
      <nav className="spec-outline" aria-label={words.label}>
        <p className="spec-none">{words.empty}</p>
      </nav>
    );
  }
  const overview = overviewOf(spec, null);
  const outside = outsideOf(spec, null);
  const open = openItems(spec.elements);
  const rows = (elements: readonly SpecElement[]) => <Rows elements={elements} selected={selected} onSelect={onSelect} />;
  return (
    <nav className="spec-outline" aria-label={words.label}>
      <Section title={sectionTitles.overview}>
        <Group title={common.whatItIs}>
          {overview.definitive ? rows([overview.definitive]) : <p className="spec-none">{common.noDefinitive}</p>}
        </Group>
        <Group title={common.serves}>{rows(overview.serves)}</Group>
        <Group title={common.reliesOn}>{rows(overview.reliesOn)}</Group>
      </Section>
      <Section title={sectionTitles.elements}>
        {functionalGroups(spec, null).map((group) => (
          <Group key={group.segment} title={groupTitle(group.segment)}>
            {rows(group.elements)}
          </Group>
        ))}
      </Section>
      <Section title={sectionTitles.outside}>
        <Group title={common.serves}>{rows(outside.serves)}</Group>
        <Group title={common.reliesOn}>{rows(outside.reliesOn)}</Group>
      </Section>
      <Section title={sectionTitles.evidence}>
        {EVIDENCE_STATUSES.map((status) => {
          const elements = spec.elements.filter((element) => elementEvidence(element).status === status);
          if (elements.length === 0) return null;
          return (
            <Group key={status} title={statusWords[status]}>
              {rows(elements)}
            </Group>
          );
        })}
      </Section>
      <Section title={sectionTitles.open}>
        {OPEN_KINDS.map((kind) => (
          <Group key={kind} title={openTitles[kind]}>
            {rows(open[kind])}
          </Group>
        ))}
      </Section>
    </nav>
  );
}
