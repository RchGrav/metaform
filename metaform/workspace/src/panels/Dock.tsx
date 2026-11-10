// The zones around the graph and the floating panels over it. Dock draws a layout (layout.ts) and
// turns the pointer and the keyboard into layout actions. It knows a panel only by its id and
// title; the page gives it a function that renders a panel's body.

import { useEffect, useRef, useState } from "react";
import type React from "react";
import * as strings from "../strings";
import { MenuButton } from "./Menu";
import { MIN_FLOATING, ZONES, fitFloating, narrowLayout, type Area, type FloatingPanel, type Layout, type Zone } from "./layout";
import type { LayoutActions } from "./useLayout";

/** How far one press of an arrow key moves a divider or a floating panel, in pixels. */
const KEY_STEP = 16;

/** What Dock needs to know about a panel. */
export interface DockPanel {
  id: string;
  title: string;
}

export interface DockProps {
  layout: Layout;
  actions: LayoutActions;
  panels: readonly DockPanel[];
  /** Renders the body of the panel with this id. Dock calls it only for a panel that shows. */
  renderBody: (id: string) => React.ReactNode;
  /** True in a narrow window: every open panel is in one zone under the graph. */
  narrow: boolean;
  /** False when the page shows the graph area alone, as in Present. */
  shown: boolean;
  /** False while another view takes the place of the graph: the floating panels are then not drawn. */
  graphShown: boolean;
  /** The graph area's content: the graph and what the page draws over it. */
  children: React.ReactNode;
}

/** Follows the pointer from a press until its release, and reports how far it moved from the press. */
function drag(e: React.PointerEvent<HTMLElement>, onMove: (dx: number, dy: number) => void): void {
  if (e.button !== 0) return;
  e.preventDefault();
  const target = e.currentTarget;
  const { clientX, clientY, pointerId } = e;
  target.setPointerCapture(pointerId);
  const move = (ev: PointerEvent) => onMove(ev.clientX - clientX, ev.clientY - clientY);
  const end = () => {
    target.removeEventListener("pointermove", move);
    target.removeEventListener("pointerup", end);
    target.removeEventListener("pointercancel", end);
  };
  target.addEventListener("pointermove", move);
  target.addEventListener("pointerup", end);
  target.addEventListener("pointercancel", end);
}

/** The distance an arrow key asks for, or null for another key. */
function arrowStep(key: string): { dx: number; dy: number } | null {
  if (key === "ArrowLeft") return { dx: -KEY_STEP, dy: 0 };
  if (key === "ArrowRight") return { dx: KEY_STEP, dy: 0 };
  if (key === "ArrowUp") return { dx: 0, dy: -KEY_STEP };
  if (key === "ArrowDown") return { dx: 0, dy: KEY_STEP };
  return null;
}

/** The menu and the close button for one panel, at the right end of its bar. */
function PanelActions(props: {
  panel: DockPanel;
  place: Zone | "floating";
  home: Zone | undefined;
  narrow: boolean;
  actions: LayoutActions;
  area: Area | null;
}) {
  const { panel, place, home, actions, area } = props;
  return (
    <div className="panel-actions">
      {!props.narrow && (
        <MenuButton label={strings.panels.actions(panel.title)} text="⋯" className="panel-button">
          {(close) => {
            const item = (text: string, act: () => void) => (
              <button
                key={text}
                type="button"
                role="menuitem"
                onClick={() => {
                  close();
                  act();
                }}
              >
                {text}
              </button>
            );
            return (
              <>
                {place === "floating" && home !== undefined && item(strings.panels.dock(strings.panels.zone[home]), () => actions.dock(panel.id))}
                {ZONES.filter((zone) => zone !== place && !(place === "floating" && zone === home)).map((zone) =>
                  item(strings.panels.moveTo(strings.panels.zone[zone]), () => actions.move(panel.id, zone)),
                )}
                {place !== "floating" && area !== null && item(strings.panels.float, () => actions.float(panel.id, area))}
                {item(strings.panels.close(panel.title), () => actions.close(panel.id))}
              </>
            );
          }}
        </MenuButton>
      )}
      <button
        type="button"
        className="panel-button"
        aria-label={strings.panels.close(panel.title)}
        title={strings.panels.close(panel.title)}
        onClick={() => actions.close(panel.id)}
      >
        ×
      </button>
    </div>
  );
}

/** One zone: its divider, the tabs of its panels, and the body of the active panel. */
function ZoneView(props: {
  zone: Zone;
  layout: Layout;
  titles: Map<string, string>;
  narrow: boolean;
  area: Area | null;
  actions: LayoutActions;
  renderBody: (id: string) => React.ReactNode;
  onActivate: (id: string) => void;
}) {
  const { zone, layout, titles, actions } = props;
  const state = layout.zones[zone];
  const section = useRef<HTMLElement>(null);
  const zoneName = props.narrow ? strings.panels.narrowZone : strings.panels.zone[zone];
  const active = state.active;
  const horizontal = zone === "bottom";
  // A zone with many tabs scrolls its tabs; the active tab is always brought into view.
  useEffect(() => {
    section.current?.querySelector('[role="tab"][aria-selected="true"]')?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [active, state.panels.length]);

  /** The zone's size on screen, which a small window can hold below the saved size. */
  const measured = () => {
    const rect = section.current?.getBoundingClientRect();
    return rect ? (horizontal ? rect.height : rect.width) : state.size;
  };
  // Dragging toward the graph makes the zone larger.
  const grow = (dx: number, dy: number) => (zone === "left" ? dx : zone === "right" ? -dx : -dy);
  const onDividerDown = (e: React.PointerEvent<HTMLElement>) => {
    const start = measured();
    drag(e, (dx, dy) => actions.resizeZone(zone, start + grow(dx, dy)));
  };
  const onDividerKey = (e: React.KeyboardEvent) => {
    const step = arrowStep(e.key);
    if (!step) return;
    e.preventDefault();
    e.stopPropagation();
    const by = grow(step.dx, step.dy);
    if (by !== 0) actions.resizeZone(zone, measured() + by);
  };
  // The left and right arrow keys move between the tabs of one zone.
  const onTabKey = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    e.stopPropagation();
    const tabs = Array.from(e.currentTarget.querySelectorAll<HTMLElement>('[role="tab"]'));
    const at = tabs.indexOf(document.activeElement as HTMLElement);
    tabs[(at + (e.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length]?.focus();
  };

  return (
    <section
      ref={section}
      className={`zone zone-${zone}`}
      style={horizontal ? { height: state.size } : { width: state.size }}
      aria-label={zoneName}
    >
      <div
        className="divider"
        role="separator"
        tabIndex={0}
        aria-orientation={horizontal ? "horizontal" : "vertical"}
        aria-valuenow={state.size}
        aria-label={strings.panels.resizeZone(zoneName)}
        title={strings.panels.resizeZone(zoneName)}
        onPointerDown={onDividerDown}
        onKeyDown={onDividerKey}
      />
      <div className="panel-stack">
        <div className="panel-bar">
          <div className="panel-tabs" role="tablist" aria-label={strings.panels.tabs(zoneName)} onKeyDown={onTabKey}>
            {state.panels.map((id) => (
              <button key={id} type="button" role="tab" aria-selected={id === active} tabIndex={id === active ? 0 : -1} onClick={() => props.onActivate(id)}>
                {titles.get(id) ?? id}
              </button>
            ))}
          </div>
          {active !== null && (
            <PanelActions
              panel={{ id: active, title: titles.get(active) ?? active }}
              place={zone}
              home={layout.home[active]}
              narrow={props.narrow}
              actions={actions}
              area={props.area}
            />
          )}
        </div>
        {active !== null && (
          <div className="panel-body" role="tabpanel" aria-label={titles.get(active) ?? active} key={active}>
            {props.renderBody(active)}
          </div>
        )}
      </div>
    </section>
  );
}

/** One floating panel: a bar to drag it by, its body, and a corner to resize it by. */
function FloatingView(props: {
  panel: FloatingPanel;
  title: string;
  order: number;
  home: Zone | undefined;
  area: Area;
  actions: LayoutActions;
  body: React.ReactNode;
}) {
  const { panel, title, area, actions } = props;
  const shown = fitFloating(panel, area);
  /** Keeps the panel inside the graph area while it moves. */
  const moveTo = (x: number, y: number) =>
    actions.placeFloating(panel.id, {
      x: Math.min(Math.max(0, x), Math.max(0, area.width - shown.width)),
      y: Math.min(Math.max(0, y), Math.max(0, area.height - shown.height)),
      width: shown.width,
      height: shown.height,
    });
  /** Keeps the panel's far corner inside the graph area while it is resized. */
  const sizeTo = (width: number, height: number) =>
    actions.placeFloating(panel.id, {
      x: shown.x,
      y: shown.y,
      width: Math.min(Math.max(MIN_FLOATING.width, width), Math.max(MIN_FLOATING.width, area.width - shown.x)),
      height: Math.min(Math.max(MIN_FLOATING.height, height), Math.max(MIN_FLOATING.height, area.height - shown.y)),
    });
  const onKey = (act: (dx: number, dy: number) => void) => (e: React.KeyboardEvent) => {
    const step = arrowStep(e.key);
    if (!step) return;
    e.preventDefault();
    e.stopPropagation();
    act(step.dx, step.dy);
  };
  return (
    <section
      className="floating-panel"
      style={{ left: shown.x, top: shown.y, width: shown.width, height: shown.height, zIndex: 5 + props.order }}
      aria-label={title}
      onPointerDownCapture={() => actions.open(panel.id)}
      onFocusCapture={() => actions.open(panel.id)}
    >
      <div className="panel-bar">
        <div
          className="float-handle"
          role="button"
          tabIndex={0}
          aria-label={strings.panels.moveFloating(title)}
          title={strings.panels.moveFloating(title)}
          onPointerDown={(e) => drag(e, (dx, dy) => moveTo(shown.x + dx, shown.y + dy))}
          onKeyDown={onKey((dx, dy) => moveTo(shown.x + dx, shown.y + dy))}
        >
          {title}
        </div>
        <PanelActions panel={{ id: panel.id, title }} place="floating" home={props.home} narrow={false} actions={actions} area={area} />
      </div>
      <div className="panel-body" role="region" aria-label={title}>
        {props.body}
      </div>
      <div
        className="float-resize"
        role="button"
        tabIndex={0}
        aria-label={strings.panels.resizeFloating(title)}
        title={strings.panels.resizeFloating(title)}
        onPointerDown={(e) => drag(e, (dx, dy) => sizeTo(shown.width + dx, shown.height + dy))}
        onKeyDown={onKey((dx, dy) => sizeTo(shown.width + dx, shown.height + dy))}
      />
    </section>
  );
}

/**
 * The page's body: the graph area, with the left and right zones beside it, the bottom zone under
 * it, and the floating panels over it. A zone with no open panel is not drawn and takes no room.
 * The graph area's element stays the same whatever opens or closes, so the graph is never rebuilt.
 */
export function Dock(props: DockProps) {
  const { actions, shown } = props;
  const graphArea = useRef<HTMLDivElement>(null);
  const [area, setArea] = useState<Area | null>(null);
  // The tab the user last chose in a narrow window, where one zone holds every panel.
  const [narrowActive, setNarrowActive] = useState<string | null>(null);

  useEffect(() => {
    const element = graphArea.current;
    if (!element) return;
    const measure = () =>
      setArea((old) => {
        const next = { width: element.clientWidth, height: element.clientHeight };
        return old && old.width === next.width && old.height === next.height ? old : next;
      });
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const layout = props.narrow ? narrowLayout(props.layout, narrowActive) : props.layout;
  const titles = new Map(props.panels.map((panel) => [panel.id, panel.title]));
  const has = (zone: Zone) => shown && layout.zones[zone].panels.length > 0;
  const zone = (name: Zone) => (
    <ZoneView
      zone={name}
      layout={layout}
      titles={titles}
      narrow={props.narrow}
      area={area}
      actions={actions}
      renderBody={props.renderBody}
      onActivate={(id) => {
        setNarrowActive(id);
        actions.open(id);
      }}
    />
  );
  // The floating panels keep one order in the document; the layout's order sets which is on top.
  const floating = [...layout.floating].sort((a, b) => a.id.localeCompare(b.id));

  return (
    <main className={`body${props.narrow ? " narrow" : ""}`}>
      <div className="dock-row">
        {has("left") && zone("left")}
        <div className="graph-area" ref={graphArea}>
          {props.children}
          {shown &&
            props.graphShown &&
            area !== null &&
            floating.map((panel) => (
              <FloatingView
                key={panel.id}
                panel={panel}
                title={titles.get(panel.id) ?? panel.id}
                order={layout.floating.indexOf(panel)}
                home={layout.home[panel.id]}
                area={area}
                actions={actions}
                body={props.renderBody(panel.id)}
              />
            ))}
        </div>
        {has("right") && zone("right")}
      </div>
      {has("bottom") && zone("bottom")}
    </main>
  );
}
