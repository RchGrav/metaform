// The workspace chrome: top bar, rail, details, bottom strip and onboarding
// (dev/user_agent_interfaces-ux.md sections 2, 3, 7, 8, 9, 11 and 12). Every word comes from strings.ts.

import { useEffect, useRef, useState } from "react";
import type { Address, ProjectRef, SummarySheet, Want } from "../source";
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

/** The page's address with a control that copies it. The address stays selectable when the copy is refused. */
export function PageAddress({ address }: { address: string }) {
  const [result, setResult] = useState<"copied" | "notCopied" | null>(null);
  const copy = () => {
    const done = (next: "copied" | "notCopied") => {
      setResult(next);
      setTimeout(() => setResult(null), next === "copied" ? 2000 : 6000);
    };
    // The clipboard exists only in a secure context; 127.0.0.1 and localhost are secure contexts.
    if (!navigator.clipboard) return done("notCopied");
    navigator.clipboard.writeText(address).then(() => done("copied"), () => done("notCopied"));
  };
  return (
    <span className="page-address" title={strings.pageAddress.label}>
      <span className="visually-hidden">{strings.pageAddress.label}</span>
      <code>{address}</code>
      <button type="button" onClick={copy}>{strings.pageAddress.copy}</button>
      <span role="status">{result === null ? "" : strings.pageAddress[result]}</span>
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
      <nav className="breadcrumbs" aria-label={strings.topBar.address}>
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

const IFD = ["outbound", "inbound", "two-way"] as const;

/**
 * One want in the intake's terms, as the earlier graph showed it (climb step 2): the receiving
 * element (RE) holds the want, the providing element (PE) is what it names, OP is its `why`, EF
 * its `how`, and IFD its `direction`, relative to the receiving element (R-3.6).
 */
function WantCard(props: { re: Address; pe: Address; want: Want; here: Address; onSelect: (address: Address) => void }) {
  const { re, pe, want, here } = props;
  const direction = IFD.find((d) => d === want.direction);
  const element = (address: Address) =>
    address === here ? <code>{address}</code> : (
      <button type="button" className="link" onClick={() => props.onSelect(address)}>{address}</button>
    );
  return (
    <li className="want-card">
      <dl>
        <div><dt>{strings.intake.re.long}</dt><dd>{element(re)}</dd></div>
        <div><dt>{strings.intake.pe.long}</dt><dd>{element(pe)}</dd></div>
        {typeof want.why === "string" && <div><dt>{strings.intake.op.long}</dt><dd>{want.why}</dd></div>}
        {typeof want.how === "string" && <div><dt>{strings.intake.ef.long}</dt><dd>{want.how}</dd></div>}
        {direction && <div><dt>{strings.intake.ifd.long}</dt><dd>{strings.intake.ifdValue(direction, re, pe)}</dd></div>}
      </dl>
    </li>
  );
}

export function Details(props: {
  address: Address;
  sheet: SummarySheet | null;
  /** The addresses directly beneath this one. */
  beneath: Address[];
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
  // A branch is an address that only groups the elements beneath it: it has no fields and no
  // wants of its own. The arrows the graph draws at it belong to those elements.
  const branch = sheet !== null && props.beneath.length > 0 && fields.length === 0 && wants.length === 0 && wantedBy.length === 0;
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
      {branch && (
        <>
          <p className="empty">{strings.details.branch(props.beneath.length)}</p>
          <ul className="beneath">
            {props.beneath.map((child) => (
              <li key={child}>
                <button type="button" className="link" onClick={() => props.onSelect(child)}>{child}</button>
              </li>
            ))}
          </ul>
        </>
      )}
      {!branch && <h3>{strings.details.wants}</h3>}
      {branch ? null : wants.length === 0 ? (
        <p className="empty">{strings.details.noWants}</p>
      ) : (
        <ul className="wants">
          {wants.map(([other, want]) => (
            <WantCard key={other} re={address} pe={other} want={want} here={address} onSelect={props.onSelect} />
          ))}
        </ul>
      )}
      {!branch && <h3>{strings.details.wantedBy}</h3>}
      {branch ? null : wantedBy.length === 0 ? (
        <p className="empty">{strings.details.notWanted}</p>
      ) : (
        <ul className="wants">
          {wantedBy.map(([other, want]) => (
            <WantCard key={other} re={other} pe={address} want={want} here={address} onSelect={props.onSelect} />
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
        : strings.connection.refused(notice.message, notice.code);
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
  /** The page's origin, shown with a control that copies it. */
  pageAddress: string;
  projectName: (id: string) => string;
  onOpenActivity: () => void;
  dispatch: (action: Action) => void;
  onSelect: (project: string, address: Address) => void;
  legendOpen: boolean;
  onToggleLegend: () => void;
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
        <button type="button" className="link" aria-pressed={props.legendOpen} onClick={props.onToggleLegend}>
          {props.legendOpen ? strings.legend.hide : strings.legend.show}
        </button>
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
        <PageAddress address={props.pageAddress} />
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

/** Every mark the graph draws, with its meaning (climb step 1). The renderer gives each mark the same text as its tooltip. */
const LEGEND_ENTRIES = [
  "roleBar", "definitive", "stack", "chevron", "beneath", "outside", "layerMark",
  "agent", "agentActive", "agentIdle", "unseen", "projectLink", "arrow", "arrowCount", "band",
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
    beneath: <text className="mf-beneath" x={4} y={15}>89</text>,
    outside: <text className="mf-outside" x={4} y={15}>{strings.graph.wantsOutside(2)}</text>,
    layerMark: <g className="mf-layer mf-layer-0" transform="translate(8,11)"><rect x={0} y={-3.5} width={7} height={7} /><text className="mf-layer-count" x={11} y={4}>3</text></g>,
    agent: <g className="mf-agent" transform="translate(20,11)"><circle r={9} /><text textAnchor="middle" y={3.5}>MA</text></g>,
    agentActive: <g className="mf-agent mf-agent-active" transform="translate(20,11)"><circle r={9} /></g>,
    agentIdle: <g className="mf-agent" transform="translate(20,11)"><circle r={9} /></g>,
    unseen: <circle className="mf-unseen" cx={20} cy={11} r={4.5} />,
    projectLink: <g className="mf-project-link" transform="translate(14,5)"><path d="M2,10 L10,2 M5,2 L10,2 L10,7" /></g>,
    arrow: <g className="mf-edge"><path d="M4,11 L30,11" /><path className="mf-arrowhead" d="M30,7 L37,11 L30,15 z" /></g>,
    arrowCount: <g className="mf-edge"><path d="M4,15 L30,15" /><path className="mf-arrowhead" d="M30,11 L37,15 L30,19 z" /><text className="mf-edge-count" x={14} y={10}>3</text></g>,
    band: <line className="mf-separator" x1={20} y1={1} x2={20} y2={21} />,
  };
  // The outside count is words in the graph, so its swatch is as wide as the words.
  const width = entry === "outside" ? 96 : 42;
  return (
    <svg className="mf-graph legend-swatch" width={width} height={22} viewBox={`0 0 ${width} 22`} aria-hidden="true">
      {marks[entry]}
    </svg>
  );
}

/** The marks that only simulated data draws: Metaform has no source of agent presence (seam gap 2). */
const SIMULATED_ENTRIES: readonly string[] = ["agent", "agentActive", "agentIdle"];

export function Legend({ onClose, simulated }: { onClose: () => void; simulated: boolean }) {
  return (
    <aside className="legend" aria-labelledby="legend-title">
      <header>
        <h2 id="legend-title">{strings.legend.title}</h2>
        <button type="button" onClick={onClose} aria-label={strings.legend.hide} title={strings.legend.hide}>×</button>
      </header>
      <ul>
        {LEGEND_ENTRIES.filter((key) => simulated || !SIMULATED_ENTRIES.includes(key)).map((key) => (
          <li key={key}>
            <Swatch entry={key} />
            <span>{strings.legend[key]}</span>
          </li>
        ))}
      </ul>
    </aside>
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
