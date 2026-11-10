// The workspace chrome: top bar, rail, bottom strip and keyboard help, and the bodies of the
// Legend and Activity panels. The Entity panel's body is src/views/Entity.tsx (dev/user_agent_interfaces-ux.md sections 2, 3, 7, 8, 9, 11
// and 12; dev/gui_specification.md). Every word comes from strings.ts.

import { useEffect, useRef, useState } from "react";
import type React from "react";
import type { Address, ProjectRef } from "../source";
import * as strings from "../strings";
import { TOP } from "../state/structure";
import { FOCUS_REACH, layerShown, type Mode, type Notice, type ViewState, type Action } from "../state/view";
import type { ActivityLine, AgentState } from "./useWorkspace";

/** The platform the page is on, which decides the names of the modifier keys it shows. */
export const platform: strings.Platform =
  typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform) ? "mac" : "other";

/** The badge that marks simulated data. */
export function SimulatedBadge() {
  return (
    <span className="badge simulated" title={strings.simulated.tooltip}>
      {strings.simulated.badge}
    </span>
  );
}

/** What the top bar says about the data and the specification. */
export interface TopBarStatus {
  connection: "connected" | "simulated" | "not-connected";
  /** How many elements the specification holds, and how many of them have no source reference. */
  elements: number;
  unverified: number;
  /** Edits the server has not confirmed yet. */
  pending: number;
  /** Proposals that wait for a review. */
  proposals: number;
}

/** The top bar: the project, the breadcrumbs, the selection, the status, the Markdown action, the modes, the zoom level and the Panels menu. */
export function TopBar(props: {
  state: ViewState;
  projects: ProjectRef[];
  container: Address;
  zoom: number;
  /** The Panels menu (src/panels/PanelsMenu.tsx). */
  menu: React.ReactNode;
  /** Where the data comes from, and what the specification holds now; null before a project is read. */
  status: TopBarStatus | null;
  /** The name of the selected element, or null. */
  selected: string | null;
  /** Whether the Markdown panel is open, and the action that opens or closes it. */
  markdownOpen: boolean;
  onMarkdown: () => void;
  dispatch: (action: Action) => void;
}) {
  const { state, projects, container, zoom, dispatch, status } = props;
  const segments = container === TOP ? [] : container.split(".");
  const project = projects.find((p) => p.id === state.project);
  const modes: Mode[] = ["graph", "element", "present"];
  return (
    <header className="top-bar">
      <label className="project">
        <span className="visually-hidden">{strings.topBar.projects}</span>
        <select
          value={state.project ?? ""}
          onChange={(e) => dispatch({ type: "open-project", project: e.target.value })}
        >
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </label>
      <nav className="breadcrumbs" aria-label={strings.topBar.address}>
        <button type="button" onClick={() => segments.length > 0 && dispatch({ type: "open", address: TOP, beneath: 1 })}>
          {segments.length === 0 ? strings.topBar.wholeProject : project?.name ?? ""}
        </button>
        {segments.map((segment, i) => {
          const address = segments.slice(0, i + 1).join(".");
          const last = i === segments.length - 1;
          return (
            <span key={address}>
              <span aria-hidden="true"> › </span>
              <button type="button" aria-current={last ? "location" : undefined} onClick={() => !last && dispatch({ type: "open", address, beneath: 1 })}>
                {segment}
              </button>
            </span>
          );
        })}
      </nav>
      {props.selected !== null && <span className="top-selected">{strings.topBar.selected(props.selected)}</span>}
      {status && (
        <span className="top-status" role="status">
          <span className={`top-connection top-${status.connection}`} title={strings.topBar.connectionTip[status.connection]}>
            <span aria-hidden="true">{strings.topBar.connectionMark[status.connection]}</span> {strings.topBar.connection[status.connection]}
          </span>
          <span title={strings.topBar.elementsTip}>{strings.topBar.elements(status.elements)}</span>
          {status.unverified > 0 && <span title={strings.topBar.unverifiedTip}>{strings.topBar.unverified(status.unverified)}</span>}
          {status.pending > 0 && <span title={strings.topBar.pendingTip}>{strings.topBar.pending(status.pending)}</span>}
          {status.proposals > 0 && <span title={strings.topBar.proposalsTip}>{strings.topBar.proposals(status.proposals)}</span>}
        </span>
      )}
      {state.returnTo && (
        <button type="button" className="chip return" onClick={() => dispatch({ type: "back" })}>
          {strings.navigation.backTo(projects.find((p) => p.id === state.returnTo?.project)?.name ?? state.returnTo.project, state.returnTo.container)}
        </button>
      )}
      <button type="button" className="top-markdown" aria-pressed={props.markdownOpen} title={strings.topBar.markdownTip} onClick={props.onMarkdown}>
        {strings.topBar.markdown}
      </button>
      <div className="modes" role="tablist">
        {modes.map((mode, i) => (
          <button key={mode} type="button" role="tab" aria-selected={state.mode === mode} title={`${i + 1}`} onClick={() => dispatch({ type: "mode", mode })}>
            {strings.modes[mode]}
          </button>
        ))}
      </div>
      <span className="zoom" aria-live="off">
        {strings.topBar.zoom(zoom * 100)}
      </span>
      {props.menu}
    </header>
  );
}

/** The autohiding rail (UX section 11): hides 3 s after the pointer leaves it, never while it holds focus. */
export function Rail(props: {
  onFit: () => void;
  onZoom: (factor: number) => void;
  onResetZoom: () => void;
  onBack: () => void;
  onTheme: () => void;
  onHelp: () => void;
  onGettingStarted: () => void;
  open: boolean;
  setOpen: (open: boolean) => void;
}) {
  const [more, setMore] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const rail = useRef<HTMLElement>(null);
  const { open, setOpen } = props;
  const leave = () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      if (!rail.current?.contains(document.activeElement)) setOpen(false);
    }, 3000);
  };
  const enter = () => {
    if (timer.current) clearTimeout(timer.current);
    setOpen(true);
  };
  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);
  return (
    <>
      <div className="rail-zone" onPointerEnter={enter} aria-hidden="true" />
      {!open && (
        <button type="button" className="rail-handle" aria-label={strings.rail.showMenu} title={`${strings.rail.showMenu} (M)`} onClick={enter}>
          ›
        </button>
      )}
      <nav ref={rail} className={`rail${open ? "" : " hidden"}`} onPointerEnter={enter} onPointerLeave={leave} onFocus={enter} onBlur={leave}>
        <button type="button" title={`${strings.rail.fitToView} (0)`} onClick={props.onFit}>⤢<span className="visually-hidden">{strings.rail.fitToView}</span></button>
        <button type="button" title={`${strings.rail.zoomIn} (+)`} onClick={() => props.onZoom(1.2)}>+<span className="visually-hidden">{strings.rail.zoomIn}</span></button>
        <button type="button" title={`${strings.rail.zoomOut} (−)`} onClick={() => props.onZoom(1 / 1.2)}>−<span className="visually-hidden">{strings.rail.zoomOut}</span></button>
        <button type="button" title={`${strings.rail.resetZoom} (Shift+0)`} onClick={props.onResetZoom}>1:1<span className="visually-hidden">{strings.rail.resetZoom}</span></button>
        <button type="button" title={`${strings.rail.back} (Backspace)`} onClick={props.onBack}>←<span className="visually-hidden">{strings.rail.back}</span></button>
        <button type="button" aria-expanded={more} onClick={() => setMore(!more)}>
          ⋯<span className="visually-hidden">{strings.rail.more}</span>
        </button>
        {more && (
          // Choosing an item closes the menu, so the menu never stays over what the item shows.
          <div className="rail-more" role="menu" onClick={() => setMore(false)}>
            <button type="button" role="menuitem" onClick={props.onTheme}>{strings.rail.theme}</button>
            <button type="button" role="menuitem" onClick={props.onHelp}>{strings.rail.keyboardHelp}</button>
            <button type="button" role="menuitem" onClick={props.onGettingStarted}>{strings.rail.gettingStarted}</button>
          </div>
        )}
      </nav>
    </>
  );
}

/** The bar that reports a refusal, a lost connection, or a container that no longer exists. */
export function NoticeBar({ notice, onDismiss }: { notice: Notice; onDismiss: () => void }) {
  const text =
    notice.kind === "moved"
      ? strings.graph.containerGone(notice.missing, notice.showing)
      : notice.kind === "not-connected"
        ? strings.connection.notConnected(notice.reason)
        : strings.connection.refused(notice.message, notice.code);
  return (
    <div className={`notice ${notice.kind}`} role={notice.kind === "moved" ? "status" : "alert"}>
      <span>{text}</span>
      <button type="button" aria-label={strings.details.close} onClick={onDismiss}>×</button>
    </div>
  );
}

/** The bar that names the focus element while the graph shows only what is near it. */
export function FocusBanner({ address, onClear }: { address: Address; onClear: () => void }) {
  return (
    <div className="focus-banner" role="status">
      <span>{strings.focus.banner(address, FOCUS_REACH)}</span>
      <button type="button" onClick={onClear}>{strings.focus.clear}</button>
    </div>
  );
}

/** The activity lines, newest first as the workspace keeps them. This is the body of the Activity panel. */
export function ActivityList(props: {
  activity: ActivityLine[];
  projectName: (id: string) => string;
  onSelect: (project: string, address: Address) => void;
  /** Called when the list shows and when a line arrives while it shows: the user has now seen every line. */
  onSeen: () => void;
}) {
  const onSeen = useRef(props.onSeen);
  onSeen.current = props.onSeen;
  const lines = props.activity.length;
  useEffect(() => onSeen.current(), [lines]);
  if (lines === 0) return <p className="panel-note">{strings.panels.noActivity}</p>;
  return (
    <ol className="activity-list">
      {props.activity.map((line) => {
        const time = line.time.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        const text =
          line.kind === "map-changed"
            ? strings.activity.mapChanged(time)
            : strings.presence.at(line.agent ?? "", line.at ?? props.projectName(line.project), line.activity ?? undefined);
        return (
          <li key={line.id}>
            <button type="button" className="link" disabled={line.at === null} onClick={() => line.at !== null && props.onSelect(line.project, line.at)}>
              {text}
            </button>
            {line.simulated && <SimulatedBadge />}
          </li>
        );
      })}
    </ol>
  );
}

/** The bottom strip: the layer controls, and the buttons that show the Legend and Activity panels. */
export function BottomStrip(props: {
  state: ViewState;
  layers: string[];
  counts: Record<string, number>;
  agents: AgentState[];
  unseen: number;
  simulated: boolean;
  dispatch: (action: Action) => void;
  /** Whether the Legend panel and the Activity panel are open, and the actions that open or close each. */
  legendOpen: boolean;
  onToggleLegend: () => void;
  activityOpen: boolean;
  onToggleActivity: () => void;
}) {
  const { state, layers, dispatch } = props;
  return (
    <footer className="bottom-strip">
      <div className="layers" role="group" aria-label={strings.layers.group}>
        {layers.some((layer) => (props.counts[layer] ?? 0) > 0) && <span className="layers-title" title={strings.layers.groupTip}>{strings.layers.group}</span>}
        {layers.map((layer, style) => {
          // A layer with no record draws no mark, so it has nothing to show or hide.
          if ((props.counts[layer] ?? 0) === 0) return null;
          const isolated = state.isolated === layer;
          const shown = layerShown(state, layer);
          const hidden = state.isolated === null && !shown;
          return (
            <span key={layer} className={`layer-chip layer-${style % 6}${isolated ? " isolated" : ""}${hidden ? " hidden" : ""}`}>
              <button
                type="button"
                aria-pressed={shown}
                title={shown ? strings.layers.hide(layer) : strings.layers.show(layer)}
                aria-label={shown ? strings.layers.hide(layer) : strings.layers.show(layer)}
                onClick={() => dispatch({ type: "layer", layer, visibility: shown && state.isolated === null ? "hidden" : "visible" })}
              >
                <span className="swatch" aria-hidden="true" />
                {layer} <span className="count">{props.counts[layer] ?? 0}</span>
              </button>
              <button
                type="button"
                className="isolate"
                aria-pressed={isolated}
                title={isolated ? strings.layers.endOnly(layer) : strings.layers.onlyTip(layer)}
                aria-label={isolated ? strings.layers.endOnly(layer) : strings.layers.onlyTip(layer)}
                onClick={() => dispatch({ type: "isolate", layer: isolated ? null : layer })}
              >
                {strings.layers.only}
              </button>
            </span>
          );
        })}
      </div>
      <div className="activity">
        <button type="button" className="link" aria-pressed={props.legendOpen} onClick={props.onToggleLegend}>
          {props.legendOpen ? strings.legend.hide : strings.legend.show}
        </button>
        <button type="button" aria-pressed={props.activityOpen} onClick={props.onToggleActivity}>
          {strings.activity.summary(props.unseen)}
        </button>
        {props.simulated && <SimulatedBadge />}
      </div>
    </footer>
  );
}

/** Every mark the graph draws, with its meaning (climb step 1). The renderer gives each mark the same text as its tooltip. */
const LEGEND_ENTRIES = [
  "roleBar", "definitive", "stack", "chevron", "beneath", "outside", "layerMark",
  "agent", "agentActive", "agentIdle", "unseen", "projectLink", "arrow", "arrowCount",
] as const;

/**
 * Each legend line's mark, drawn with the renderer's own classes and colour tokens (src/graph/style.ts),
 * so it matches the graph in both themes (climb step 10).
 */
function Swatch({ entry }: { entry: (typeof LEGEND_ENTRIES)[number] }) {
  const box = <rect className="mf-box" x={2} y={3} width={34} height={16} rx={3} />;
  const marks: Record<(typeof LEGEND_ENTRIES)[number], JSX.Element> = {
    roleBar: <g className="mf-role-supportive">{box}<rect className="mf-role-bar" x={2} y={3} width={4} height={16} rx={2} /></g>,
    definitive: <g>{box}<rect className="mf-definitive-ring" x={4} y={5} width={30} height={12} rx={2} /></g>,
    stack: <g><rect className="mf-stack" x={6} y={6} width={34} height={14} rx={3} />{box}</g>,
    chevron: <path className="mf-chevron-mark" d="M17,6 L23,11 L17,16" />,
    beneath: <text className="mf-beneath" x={4} y={15}>4 hidden</text>,
    outside: <text className="mf-outside" x={4} y={15}>{strings.graph.wantsOutside(2)}</text>,
    layerMark: <g className="mf-layer mf-layer-0" transform="translate(8,11)"><rect x={0} y={-3.5} width={7} height={7} /><text className="mf-layer-count" x={11} y={4}>3</text></g>,
    agent: <g className="mf-agent" transform="translate(20,11)"><circle r={9} /><text textAnchor="middle" y={3.5}>MA</text></g>,
    agentActive: <g className="mf-agent mf-agent-active" transform="translate(20,11)"><circle r={9} /></g>,
    agentIdle: <g className="mf-agent" transform="translate(20,11)"><circle r={9} /></g>,
    unseen: <circle className="mf-unseen" cx={20} cy={11} r={4.5} />,
    projectLink: <g className="mf-project-link" transform="translate(14,5)"><path d="M2,10 L10,2 M5,2 L10,2 L10,7" /></g>,
    arrow: <g className="mf-edge"><path d="M4,11 L30,11" /><path className="mf-arrowhead" d="M30,7 L37,11 L30,15 z" /></g>,
    arrowCount: <g className="mf-edge"><path d="M4,15 L30,15" /><path className="mf-arrowhead" d="M30,11 L37,15 L30,19 z" /><text className="mf-edge-count" x={14} y={10}>3</text></g>,
  };
  // The outside count is words in the graph, so its swatch is as wide as the words.
  const width = entry === "outside" ? 96 : entry === "beneath" ? 56 : 42;
  return (
    <svg className="mf-graph legend-swatch" width={width} height={22} viewBox={`0 0 ${width} 22`} aria-hidden="true">
      {marks[entry]}
    </svg>
  );
}

/** The marks that only simulated data draws: Metaform has no source of agent presence (seam gap 2). */
const SIMULATED_ENTRIES: readonly string[] = ["agent", "agentActive", "agentIdle"];

/** Every mark the graph draws, with its meaning. This is the body of the Legend panel, which gives the title. */
export function Legend({ simulated }: { simulated: boolean }) {
  return (
    <div className="legend">
      <ul>
        {LEGEND_ENTRIES.filter((key) => simulated || !SIMULATED_ENTRIES.includes(key)).map((key) => (
          <li key={key}>
            <Swatch entry={key} />
            <span>{strings.legend[key]}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The keyboard shortcuts panel (UX sections 3 to 11), opened from the rail or with "?". */
export function KeyboardHelp({ onClose }: { onClose: () => void }) {
  return (
    <section className="onboarding keyboard-help" aria-labelledby="keyboard-title">
      <h2 id="keyboard-title">{strings.keyboard.title}</h2>
      <dl className="keys">
        {strings.keyboard.keys(platform).map((row) => (
          <div key={row.keys}>
            <dt>
              <kbd>{row.keys}</kbd>
            </dt>
            <dd>{row.action}</dd>
          </div>
        ))}
      </dl>
      <button type="button" className="close" onClick={onClose} aria-label={strings.details.close}>×</button>
    </section>
  );
}
