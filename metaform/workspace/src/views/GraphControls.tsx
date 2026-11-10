// The graph controls: the fits, the depth and the categories. The component holds no state. The
// page passes what the view state holds and one callback for each action.

import "../graph/controls.css";
import { categoryState, controls as text } from "../graph/strings";

/** One category as the controls show it. */
export interface CategoryControl {
  /** The first segment of the addresses in the category. */
  category: string;
  /** How many elements the category holds. */
  elements: number;
  state: "shown" | "hidden" | "isolated";
}

/** What the graph controls show, and what each control calls. */
export interface GraphControlsProps {
  /** True when an element is selected; fit selection and fit branch need one. */
  hasSelection: boolean;
  /** The depth on screen; depth 1 is the first level that draws a want. */
  depth: number;
  /** How many depths the graph has. */
  maxDepth: number;
  /** True when a depth action can be undone. */
  canUndo: boolean;
  categories: readonly CategoryControl[];
  onFitGraph: () => void;
  onFitSelection: () => void;
  onFitBranch: () => void;
  onCollapseLevel: () => void;
  onExpandLevel: () => void;
  onExpandAll: () => void;
  onCollapseAll: () => void;
  onUndo: () => void;
  onToggleCategory: (category: string) => void;
  /** Isolates the category; null ends the isolation. */
  onIsolateCategory: (category: string | null) => void;
  onShowAllCategories: () => void;
  onHideAllCategories: () => void;
  onRestoreCategories: () => void;
}

/** A button of the controls: a short label, with a tooltip and an accessible name that say what it does. */
function Control({ label, tip, onClick, disabled, pressed }: { label: string; tip: string; onClick: () => void; disabled?: boolean; pressed?: boolean }) {
  return (
    <button type="button" className="gc-button" title={tip} aria-label={tip} aria-pressed={pressed} disabled={disabled} onClick={onClick}>
      {label}
    </button>
  );
}

/** The graph controls: fit graph, selection and branch; depth and undo; the categories with their states. */
export function GraphControls(props: GraphControlsProps) {
  const { hasSelection, depth, maxDepth, canUndo, categories } = props;
  const needs = (tip: string) => (hasSelection ? tip : `${tip}. ${text.fit.needsSelection}`);
  const changed = categories.some((c) => c.state !== "shown");
  return (
    <div className="graph-controls" role="toolbar" aria-label={text.label}>
      <div className="gc-group" role="group" aria-label={text.fit.group}>
        <span className="gc-title">{text.fit.group}</span>
        <Control label={text.fit.graph.label} tip={text.fit.graph.tip} onClick={props.onFitGraph} />
        <Control label={text.fit.selection.label} tip={needs(text.fit.selection.tip)} onClick={props.onFitSelection} disabled={!hasSelection} />
        <Control label={text.fit.branch.label} tip={needs(text.fit.branch.tip)} onClick={props.onFitBranch} disabled={!hasSelection} />
      </div>
      <div className="gc-group" role="group" aria-label={text.depth.group}>
        <span className="gc-title">{text.depth.group}</span>
        <Control label={text.depth.less.label} tip={text.depth.less.tip} onClick={props.onCollapseLevel} disabled={depth <= 1} />
        <output className="gc-depth" title={text.depth.current(depth, maxDepth)} aria-label={text.depth.current(depth, maxDepth)}>
          {depth}
        </output>
        <Control label={text.depth.more.label} tip={text.depth.more.tip} onClick={props.onExpandLevel} disabled={depth >= maxDepth} />
        <Control label={text.depth.expandAll.label} tip={text.depth.expandAll.tip} onClick={props.onExpandAll} />
        <Control label={text.depth.collapseAll.label} tip={text.depth.collapseAll.tip} onClick={props.onCollapseAll} />
        <Control label={text.depth.undo.label} tip={canUndo ? text.depth.undo.tip : `${text.depth.undo.tip}. ${text.depth.nothingToUndo}`} onClick={props.onUndo} disabled={!canUndo} />
      </div>
      <div className="gc-group" role="group" aria-label={text.categories.group}>
        <span className="gc-title">{text.categories.group}</span>
        {categories.map(({ category, elements, state }) => {
          const name = text.categories.name(category);
          const isolated = state === "isolated";
          return (
            <span key={category} className={`gc-category gc-${state}`}>
              <button
                type="button"
                className="gc-button"
                title={text.categories.toggle(name, elements, state, category)}
                aria-label={text.categories.toggle(name, elements, state, category)}
                aria-pressed={state !== "hidden"}
                onClick={() => props.onToggleCategory(category)}
              >
                <span className="gc-mark" aria-hidden="true">{categoryState[state].mark}</span>
                {name}
                <span className="gc-state">{categoryState[state].word}</span>
              </button>
              <Control
                label={text.categories.isolate.label}
                tip={isolated ? text.categories.endIsolation(name) : text.categories.isolate.tip(name)}
                pressed={isolated}
                onClick={() => props.onIsolateCategory(isolated ? null : category)}
              />
            </span>
          );
        })}
        <Control label={text.categories.showAll.label} tip={text.categories.showAll.tip} onClick={props.onShowAllCategories} />
        <Control label={text.categories.hideAll.label} tip={text.categories.hideAll.tip} onClick={props.onHideAllCategories} />
        <Control label={text.categories.restore.label} tip={text.categories.restore.tip} onClick={props.onRestoreCategories} disabled={!changed} />
      </div>
    </div>
  );
}
