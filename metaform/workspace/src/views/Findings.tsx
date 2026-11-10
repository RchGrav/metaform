// The Findings panel: what the specification itself shows to be open. Every finding is derived
// from the `spec` prop on each render; the view holds no copy of the specification. The findings
// are read from the map. They are not the result of an analysis, and the panel says so.

import { useState } from "react";
import { FINDING_KINDS, findingsOf, groupByKind } from "../activity/findings";
import type { Finding, FindingKind } from "../activity/findings";
import { findings as words, kindMarks, kindMeanings, kindTitles } from "../activity/strings";
import { labelAt } from "../spec/model";
import type { Spec } from "../spec/model";
import "../activity/activity.css";

/** The props of `Findings`. */
export interface FindingsProps {
  /** The specification the page shows now. */
  spec: Spec;
  /** The address of the selected element, or null when nothing is selected. */
  selected: string | null;
  /** Called with the address of the element a finding concerns when the user chooses the finding. */
  onSelect: (address: string) => void;
}

function Kinds() {
  return (
    <ul className="act-kinds">
      {FINDING_KINDS.map((kind) => (
        <li key={kind}>
          <span className="act-mark" aria-hidden="true">{kindMarks[kind]}</span>
          <strong>{kindTitles[kind]}.</strong> {kindMeanings[kind]}
        </li>
      ))}
    </ul>
  );
}

function Row({ spec, finding, selected, onSelect }: { spec: Spec; finding: Finding; selected: string | null; onSelect: (address: string) => void }) {
  return (
    <li>
      <button
        type="button"
        className="act-row"
        aria-current={finding.address === selected ? "true" : undefined}
        onClick={() => onSelect(finding.address)}
      >
        <span className="act-row-main">{finding.sentence}</span>
        <span className="act-row-address">
          {labelAt(spec, finding.address)} · {finding.address}
        </span>
        <span className="act-row-note">
          {words.evidence}: {finding.evidence}
        </span>
      </button>
    </li>
  );
}

/**
 * The findings of the specification, grouped by kind with a count for each kind. The user can
 * show one kind. Choosing a finding calls `onSelect` with the address of the element it concerns.
 * When there is no finding, the panel says so and lists the kinds the page checks.
 */
export function Findings({ spec, selected, onSelect }: FindingsProps) {
  const [chosen, setChosen] = useState<FindingKind | null>(null);
  const all = findingsOf(spec);
  const groups = groupByKind(all);

  if (all.length === 0) {
    return (
      <section className="act-panel" aria-label={words.label}>
        <p className="act-origin">{words.origin}</p>
        <p className="act-empty">{spec.elements.length === 0 ? words.noElements : words.empty}</p>
        <p className="act-note">{words.emptyKinds}</p>
        <Kinds />
      </section>
    );
  }

  // A kind that the specification no longer has a finding of cannot stay chosen.
  const kind = chosen !== null && groups.some((group) => group.kind === chosen && group.findings.length > 0) ? chosen : null;
  return (
    <section className="act-panel" aria-label={words.label}>
      <p className="act-origin">{words.origin}</p>
      <div className="act-filters" role="group" aria-label={words.filterLabel}>
        <button type="button" className="act-chip" aria-pressed={kind === null} onClick={() => setChosen(null)}>
          {words.withCount(words.all, all.length)}
        </button>
        {groups.map((group) => (
          <button
            key={group.kind}
            type="button"
            className="act-chip"
            aria-pressed={kind === group.kind}
            disabled={group.findings.length === 0}
            title={kindMeanings[group.kind]}
            onClick={() => setChosen(group.kind)}
          >
            <span className="act-mark" aria-hidden="true">{kindMarks[group.kind]}</span>
            {words.withCount(kindTitles[group.kind], group.findings.length)}
          </button>
        ))}
      </div>
      {groups
        .filter((group) => group.findings.length > 0 && (kind === null || group.kind === kind))
        .map((group) => (
          <section key={group.kind} className="act-group">
            <h3>
              <span className="act-mark" aria-hidden="true">{kindMarks[group.kind]}</span>
              {kindTitles[group.kind]} <span className="act-count">{words.total(group.findings.length)}</span>
            </h3>
            <p className="act-note">{kindMeanings[group.kind]}</p>
            <ul className="act-rows">
              {group.findings.map((finding) => (
                <Row key={finding.id} spec={spec} finding={finding} selected={selected} onSelect={onSelect} />
              ))}
            </ul>
          </section>
        ))}
    </section>
  );
}
