// The Panels menu in the top bar: every panel with its state, the two text sizes, and the action
// that restores the default layout.

import * as strings from "../strings";
import type { DockPanel } from "./Dock";
import { MenuButton } from "./Menu";
import { TEXT_SIZE, placeOf, type Layout, type TextSize } from "./layout";
import type { LayoutActions } from "./useLayout";

/** One text size with a control: a button that makes it smaller, its value, and a button that makes it larger. */
function TextSizeRow(props: { label: string; which: keyof TextSize; layout: Layout; actions: LayoutActions }) {
  const size = props.layout.text[props.which];
  return (
    <div className="menu-row" role="group" aria-label={props.label}>
      <span>{props.label}</span>
      <button
        type="button"
        role="menuitem"
        className="step"
        aria-label={strings.panels.smaller(props.label)}
        title={strings.panels.smaller(props.label)}
        disabled={size <= TEXT_SIZE.min}
        onClick={() => props.actions.setTextSize(props.which, size - 1)}
      >
        −
      </button>
      <output className="text-size">{strings.panels.pixels(size)}</output>
      <button
        type="button"
        role="menuitem"
        className="step"
        aria-label={strings.panels.larger(props.label)}
        title={strings.panels.larger(props.label)}
        disabled={size >= TEXT_SIZE.max}
        onClick={() => props.actions.setTextSize(props.which, size + 1)}
      >
        +
      </button>
    </div>
  );
}

/**
 * The Panels menu. Each panel is a checkbox item that opens or closes it; the words beside the
 * title say where the panel is. The menu stays open while panels and text sizes are adjusted.
 */
export function PanelsMenu(props: { layout: Layout; actions: LayoutActions; panels: readonly DockPanel[]; narrow: boolean }) {
  const { layout, actions } = props;
  const stateOf = (id: string): string => {
    const place = placeOf(layout, id);
    if (place === null) return strings.panels.closed;
    if (props.narrow) return strings.panels.narrowZone;
    return place === "floating" ? strings.panels.floating : strings.panels.zone[place];
  };
  return (
    <MenuButton label={strings.panels.menu} text={strings.panels.menu} className="panels-menu">
      {(close) => (
        <>
          {props.panels.map((panel) => (
            <button
              key={panel.id}
              type="button"
              role="menuitemcheckbox"
              aria-checked={placeOf(layout, panel.id) !== null}
              onClick={() => actions.toggle(panel.id)}
            >
              <span className="check" aria-hidden="true">{placeOf(layout, panel.id) !== null ? "✓" : ""}</span>
              <span className="menu-title">{panel.title}</span>
              <span className="menu-state">{stateOf(panel.id)}</span>
            </button>
          ))}
          <hr />
          <TextSizeRow label={strings.panels.workspaceText} which="workspace" layout={layout} actions={actions} />
          <TextSizeRow label={strings.panels.panelText} which="panels" layout={layout} actions={actions} />
          <hr />
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              close();
              actions.restore();
            }}
          >
            {strings.panels.restore}
          </button>
        </>
      )}
    </MenuButton>
  );
}
