// The workspace chrome: top bar, rail, details, bottom strip and onboarding
// (dev/user_agent_interfaces-ux.md sections 2, 3, 7, 8, 9, 11 and 12). Every word comes from strings.ts.

import { useEffect, useRef, useState } from "react";
import type { Address, ProjectRef, SummarySheet } from "../source";
import * as strings from "../strings";
import { TOP } from "../state/structure";
import { FOCUS_REACH, layerShown, type Mode, type Notice, type ViewState, type Action } from "../state/view";
import type { ActivityLine, AgentState } from "./useWorkspace";

export const platform: strings.Platform =
  typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform) ? "mac" : "other";

export function SimulatedBadge() {
  return (
    <span className="badge simulated" title={strings.simulated.tooltip}>
      {strings.simulated.badge}
    </span>
  );
}

export function TopBar(props: {
  state: ViewState;
  projects: ProjectRef[];
  container: Address;
  zoom: number;
  dispatch: (action: Action) => void;
}) {
  const { state, projects, container, zoom, dispatch } = props;
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
      <nav className="breadcrumbs" aria-label={strings.topBar.projects}>
        <button type="button" onClick={() => segments.length > 0 && dispatch({ type: "open", address: TOP, beneath: 1 })}>
          {project?.name ?? ""}
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
      {state.returnTo && (
        <button type="button" className="chip return" onClick={() => dispatch({ type: "back" })}>
          {strings.navigation.backTo(projects.find((p) => p.id === state.returnTo?.project)?.name ?? state.returnTo.project, state.returnTo.container)}
        </button>
      )}
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
    </header>
  );
}

/** The autohiding rail (UX section 11): hides 3 s after the pointer leaves it, never while it holds focus. */
export function Rail(props: {
  onFit: () => void;
  onZoom: (factor: number) => void;
  onResetZoom: () => void;
  onBack: () => void;
  onCollapseAll: () => void;
  onExpandAll: () => void;
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
          <div className="rail-more" role="menu">
            <button type="button" role="menuitem" onClick={props.onCollapseAll}>{strings.rail.collapseAll}</button>
            <button type="button" role="menuitem" onClick={props.onExpandAll}>{strings.rail.expandAll}</button>
            <button type="button" role="menuitem" onClick={props.onTheme}>{strings.rail.theme}</button>
            <button type="button" role="menuitem" onClick={props.onHelp}>{strings.rail.keyboardHelp}</button>
            <button type="button" role="menuitem" onClick={props.onGettingStarted}>{strings.rail.gettingStarted}</button>
          </div>
        )}
      </nav>
    </>
  );
}

export function Details(props: {
  address: Address;
  sheet: SummarySheet | null;
  opensProject: boolean;
  /** Present when the element is outside the project and its own map can be read (seam gap 4). */
  onOpenMap?: () => void;
  onClose: () => void;
  onFocus: () => void;
  onOpenProject: () => void;
  onSelect: (address: Address) => void;
}) {
  const { address, sheet } = props;
  const wants = Object.entries(sheet?.wants ?? {});
  const wantedBy = Object.entries(sheet?.wanted_by ?? {});
  const layerEntries = Object.entries(sheet?.layers ?? {});
  const fields = Object.entries(sheet?.element ?? {}).filter(([, v]) => typeof v !== "object");
  return (
    <aside className="details" aria-label={address}>
      <header>
        <h2>{address}</h2>
        <button type="button" onClick={props.onClose} aria-label={strings.details.close}>×</button>
      </header>
      <dl className="fields">
        {fields.map(([key, value]) => (
          <div key={key}>
            <dt>{key}</dt>
            <dd>
              {key === "uri" && typeof value === "string" && /^https?:\/\//.test(value) ? (
                // A chained map's uri names its upstream repository (SPEC R-4.15).
                <a href={value} target="_blank" rel="noreferrer noopener">
                  {value}
                </a>
              ) : (
                String(value)
              )}
            </dd>
          </div>
        ))}
      </dl>
      <div className="actions">
        <button type="button" onClick={props.onFocus}>{strings.details.setAsFocus}</button>
        {props.opensProject && (
          <button type="button" onClick={props.onOpenProject}>{strings.details.openProject}</button>
        )}
        {props.onOpenMap && (
          <button type="button" onClick={props.onOpenMap}>{strings.details.openItsMap}</button>
        )}
      </div>
      <h3>{strings.details.wants}</h3>
      {wants.length === 0 ? (
        <p className="empty">{strings.details.noWants}</p>
      ) : (
        <ul>
          {wants.map(([other, want]) => (
            <li key={other}>
              <button type="button" className="link" onClick={() => props.onSelect(other)}>{other}</button>
              <span className="want">{[want.why, want.how, want.direction].filter(Boolean).join(" · ")}</span>
            </li>
          ))}
        </ul>
      )}
      <h3>{strings.details.wantedBy}</h3>
      {wantedBy.length === 0 ? (
        <p className="empty">{strings.details.notWanted}</p>
      ) : (
        <ul>
          {wantedBy.map(([other]) => (
            <li key={other}>
              <button type="button" className="link" onClick={() => props.onSelect(other)}>{other}</button>
            </li>
          ))}
        </ul>
      )}
      {layerEntries.length > 0 && (
        <>
          <h3>{strings.details.layers}</h3>
          <ul>
            {layerEntries.map(([layer, { records }]) => (
              <li key={layer}>
                {layer} · {strings.layers.records(records)}
              </li>
            ))}
          </ul>
        </>
      )}
    </aside>
  );
}

export function NoticeBar({ notice, onDismiss }: { notice: Notice; onDismiss: () => void }) {
  const text =
    notice.kind === "moved"
      ? strings.graph.containerGone(notice.missing, notice.showing)
      : notice.kind === "not-connected"
        ? strings.connection.notConnected(notice.reason)
        : notice.reason;
  return (
    <div className={`notice ${notice.kind}`} role={notice.kind === "moved" ? "status" : "alert"}>
      <span>{text}</span>
      <button type="button" aria-label={strings.details.close} onClick={onDismiss}>×</button>
    </div>
  );
}

export function FocusBanner({ address, onClear }: { address: Address; onClear: () => void }) {
  return (
    <div className="focus-banner" role="status">
      <span>{strings.focus.banner(address, FOCUS_REACH)}</span>
      <button type="button" onClick={onClear}>{strings.focus.clear}</button>
    </div>
  );
}

export function BottomStrip(props: {
  state: ViewState;
  layers: string[];
  counts: Record<string, number>;
  activity: ActivityLine[];
  agents: AgentState[];
  unseen: number;
  simulated: boolean;
  projectName: (id: string) => string;
  onOpenActivity: () => void;
  dispatch: (action: Action) => void;
  onSelect: (project: string, address: Address) => void;
}) {
  const [open, setOpen] = useState(false);
  const { state, layers, dispatch } = props;
  return (
    <footer className="bottom-strip">
      <div className="layers" role="group" aria-label={strings.details.layers}>
        {layers.map((layer, style) => {
          const isolated = state.isolated === layer;
          const shown = layerShown(state, layer);
          const hidden = state.isolated === null && !shown;
          return (
            <span key={layer} className={`layer-chip layer-${style % 6}${isolated ? " isolated" : ""}${hidden ? " hidden" : ""}`}>
              <button
                type="button"
                aria-pressed={shown}
                title={shown ? strings.layers.hide(layer) : strings.layers.show(layer)}
                onClick={() => dispatch({ type: "layer", layer, visibility: shown && state.isolated === null ? "hidden" : "visible" })}
              >
                <span className="swatch" aria-hidden="true" />
                {layer} <span className="count">{props.counts[layer] ?? 0}</span>
              </button>
              <button type="button" className="isolate" aria-pressed={isolated} onClick={() => dispatch({ type: "isolate", layer: isolated ? null : layer })}>
                {isolated ? strings.layers.isolated : strings.layers.isolate}
              </button>
            </span>
          );
        })}
        {layers.length > 0 && (
          <>
            <button type="button" className="link" onClick={() => dispatch({ type: "all-layers", layers, visibility: "visible" })}>{strings.layers.showAll}</button>
            <button type="button" className="link" onClick={() => dispatch({ type: "all-layers", layers, visibility: "hidden" })}>{strings.layers.hideAll}</button>
          </>
        )}
      </div>
      <div className="activity">
        <button
          type="button"
          aria-expanded={open}
          onClick={() => {
            setOpen(!open);
            props.onOpenActivity();
          }}
        >
          {strings.activity.summary(props.unseen)}
        </button>
        {props.simulated && <SimulatedBadge />}
        {open && (
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
        )}
      </div>
    </footer>
  );
}

export function Onboarding(props: { onSimulateIntake: () => void; startCommand: string; onClose?: () => void }) {
  const o = strings.onboarding;
  return (
    <section className="onboarding" aria-labelledby="onboarding-title">
      <h2 id="onboarding-title">{o.title}</h2>
      <ol>
        <li>
          <h3>{o.register.title}</h3>
          <p>{o.register.body}</p>
          <code>{o.register.command}</code>
          <p>
            <span className="badge">{o.register.plannedLabel}</span> <code>{o.register.plannedCommand}</code>
          </p>
        </li>
        <li>
          <h3>{o.intake.title}</h3>
          <p>{o.intake.body}</p>
          <button type="button" onClick={props.onSimulateIntake}>{o.intake.button}</button> <SimulatedBadge />
        </li>
        <li>
          <h3>{o.reopen.title}</h3>
          <p>{o.reopen.prototypeCommand(props.startCommand)}</p>
        </li>
      </ol>
      {props.onClose && (
        <button type="button" className="close" onClick={props.onClose} aria-label={strings.details.close}>×</button>
      )}
    </section>
  );
}
