// The graph workspace (dev/user_agent_interfaces.md; interaction: dev/user_agent_interfaces-ux.md).

import { useCallback, useEffect, useMemo, useState } from "react";
import type { GraphRenderer, Viewport } from "./graph/renderer";
import { MAX_ZOOM, MIN_ZOOM } from "./graph/renderer";
import type { Address, GraphSource, ProjectRef, SummarySheet, WorkspaceEvents } from "./source";
import * as strings from "./strings";
import { buildScene, elementScene, type SceneInput } from "./state/scene";
import { TOP, bandOf, beneathCounts, graphAddresses, outsideAddress, visibleIn } from "./state/structure";
import { currentView, type Action } from "./state/view";
import { Canvas } from "./views/Canvas";
import { BottomStrip, Details, FocusBanner, KeyboardHelp, NoticeBar, Onboarding, Rail, TopBar, platform } from "./views/Chrome";
import { ACTIVE_MS, useWorkspace } from "./views/useWorkspace";

export interface AppProps {
  source: GraphSource;
  events: WorkspaceEvents;
  renderer: GraphRenderer;
  /** True while the data is simulated; the views then show the Simulated badge. */
  simulated: boolean;
  /** The command that started this prototype, shown in onboarding (UI-U1). */
  startCommand: string;
}

/** metaform://map/project/<id>/<map>#<address> (seam gap 3): the project, and the element named after #. */
const PROJECT_LINK = /^metaform:\/\/map\/project\/([^/]+)\/[^#]*(?:#(.+))?$/;

function isTyping(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && (target.isContentEditable || ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName));
}

export function App({ source, events, renderer, simulated, startCommand }: AppProps) {
  const ws = useWorkspace(source, events, simulated);
  const { state, dispatch, current } = ws;
  const view = currentView(state);
  const [railOpen, setRailOpen] = useState(true);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [showGuide, setShowGuide] = useState(false);
  const [showKeys, setShowKeys] = useState(false);
  const [sheet, setSheet] = useState<SummarySheet | null>(null);
  const [zoom, setZoom] = useState(1);
  /** The selected outside element's own map, when the source can read it (seam gap 4). */
  const [outsideMap, setOutsideMap] = useState<ProjectRef | null>(null);

  // The renderer's tokens follow :root[data-theme] (src/graph/style.ts).
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  const addresses = useMemo(() => (current ? graphAddresses(current.graph) : []), [current]);
  const counts = useMemo(() => beneathCounts(addresses), [addresses]);
  const beneath = useCallback((address: Address) => counts.get(address) ?? 0, [counts]);

  // The project an element's `uri` names, if any (seam gap 3, proposed form).
  const linkTarget = useCallback(
    (address: Address): { project: string; at: Address | null } | null => {
      const uri = current?.fields.get(address)?.uri;
      const match = typeof uri === "string" ? PROJECT_LINK.exec(uri) : null;
      const id = match?.[1];
      if (id === undefined || !ws.projects?.some((p) => p.id === id)) return null;
      return { project: id, at: match?.[2] ?? null };
    },
    [current, ws.projects],
  );
  const linkedProject = useCallback((address: Address) => linkTarget(address)?.project ?? null, [linkTarget]);
  /** The action that follows a link: open the project, at the linked element when the link names one. */
  const followLink = useCallback(
    (address: Address): Action | null => {
      const target = linkTarget(address);
      if (!target) return null;
      return target.at === null
        ? { type: "open-project", project: target.project, from: "link" }
        : { type: "open-project", project: target.project, from: "link", at: target.at };
    },
    [linkTarget],
  );

  const sceneInput = useMemo((): SceneInput | null => {
    if (!current || state.project === null) return null;
    const now = Date.now();
    return {
      graph: current.graph,
      fields: current.fields,
      wants: current.wants,
      layerCounts: current.layerCounts,
      layers: current.layers,
      agents: ws.agents
        .filter((agent) => agent.project === state.project)
        .map((agent) => ({ id: agent.id, name: agent.name, at: agent.at, active: now - agent.lastSeen < ACTIVE_MS })),
      opensProject: (address) => linkedProject(address) !== null,
    };
  }, [current, state.project, ws.agents, linkedProject]);

  // The selected element's sheet, for Details and Element mode.
  const focusTarget = state.mode === "element" ? view.selection ?? current?.graph.definitive ?? null : view.selection;
  useEffect(() => {
    let live = true;
    setSheet(null);
    if (focusTarget !== null) void ws.sheet(focusTarget).then((s) => live && setSheet(s));
    return () => {
      live = false;
    };
  }, [focusTarget, ws.sheet, current]);

  useEffect(() => {
    let live = true;
    setOutsideMap(null);
    const at = view.selection;
    if (at !== null && state.project !== null && bandOf(at) !== "project" && source.outsideMap) {
      source.outsideMap(state.project, at).then(
        (ref) => live && setOutsideMap(ref),
        () => live && setOutsideMap(null),
      );
    }
    return () => {
      live = false;
    };
  }, [source, state.project, view.selection]);

  const scene = useMemo(() => {
    if (!sceneInput) return { nodes: [], edges: [], top: null };
    if (state.mode === "element" && focusTarget !== null) return elementScene(state, sceneInput, focusTarget);
    return buildScene(state, sceneInput);
  }, [state, sceneInput, focusTarget]);

  const viewportKey = state.mode === "element" ? `element:${focusTarget ?? ""}` : view.container;
  const storedViewport: Viewport | null = view.viewports[viewportKey] ?? null;

  useEffect(() => {
    const stored = view.viewports[view.container];
    if (stored) setZoom(stored.zoom);
  }, [view.viewports, view.container]);

  const zoomBy = useCallback(
    (factor: number) => {
      const base = view.viewports[view.container] ?? { x: 0, y: 0, zoom };
      const next = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, base.zoom * factor));
      renderer.setViewport({ ...base, zoom: next }, true);
      setZoom(next);
    },
    [renderer, view.viewports, view.container, zoom],
  );
  const fit = useCallback(
    () =>
      void renderer.fit(true).then((v) => {
        setZoom(v.zoom);
        dispatch({ type: "viewport", viewport: v });
      }),
    [renderer, dispatch],
  );

  const openLinked = useCallback(
    (address: Address) => {
      const action = followLink(address);
      if (action) dispatch(action);
    },
    [followLink, dispatch],
  );

  // Double-click and Enter: a link to another project opens that project (UX section 7); anything
  // else opens its own address subgraph (UX section 5). An outside element's own map opens from
  // Details ("Open its map") once the seam can read it (gap 4).
  const open = useCallback(
    (address: Address): Action => followLink(address) ?? { type: "open", address, beneath: beneath(address) },
    [followLink, beneath],
  );

  // The keyboard map (UX sections 3 to 11). Every action also has a pointer route.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isTyping(e.target)) return;
      // A focused graph node handles Enter, Shift+Enter and Space itself (the renderer's keyboard map).
      const onNode = e.target instanceof Element && e.target.closest("[data-address]") !== null;
      if (onNode && (e.key === "Enter" || e.key === " ")) return;
      const selection = view.selection;
      switch (true) {
        case e.key === "1" || e.key === "2" || e.key === "3":
          dispatch({ type: "mode", mode: (["graph", "element", "present"] as const)[Number(e.key) - 1] ?? "graph" });
          break;
        case e.key === "+" || e.key === "=":
          zoomBy(1.2);
          break;
        case e.key === "-":
          zoomBy(1 / 1.2);
          break;
        case e.key === "0" && !e.shiftKey:
          fit();
          break;
        case e.key === ")" || (e.key === "0" && e.shiftKey):
          zoomBy(1 / (view.viewports[view.container]?.zoom ?? zoom));
          break;
        case e.key === "Backspace" || (e.key === "ArrowLeft" && e.altKey):
          dispatch({ type: "back" });
          break;
        case e.key === "Escape":
          if (showKeys) setShowKeys(false);
          else if (state.mode === "present") dispatch({ type: "mode", mode: "graph" });
          else if (state.notice) dispatch({ type: "dismiss-notice" });
          else dispatch({ type: "select", address: null });
          break;
        case e.key === "Enter" && selection !== null && !e.shiftKey:
          if (selection) dispatch(open(selection));
          break;
        case e.key === "Enter" && e.shiftKey:
          dispatch({ type: "up" });
          break;
        case e.key === " " && selection !== null && beneath(selection ?? "") > 0:
          e.preventDefault();
          if (selection) dispatch({ type: "toggle-expanded", address: selection });
          break;
        case (e.key === "f" || e.key === "F") && selection !== null:
          if (selection) dispatch({ type: "set-focus", address: selection });
          break;
        case e.key === "?":
          setShowKeys((open) => !open);
          break;
        case e.key === "m" || e.key === "M":
          setRailOpen(true);
          break;
        case state.mode === "present" && ["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"].includes(e.key) && sheet !== null: {
          const forward = e.key === "ArrowRight" || e.key === "ArrowDown";
          const next = Object.keys(forward ? sheet?.wants ?? {} : sheet?.wanted_by ?? {})[0];
          if (next) dispatch({ type: "select", address: next });
          break;
        }
        default:
          return;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dispatch, view, state.mode, state.notice, zoomBy, fit, beneath, open, linkedProject, openLinked, sheet, zoom, showKeys]);

  useEffect(() => {
    if (view.selection) renderer.focusNode(view.selection);
  }, [renderer, view.selection]);

  const layerTotals = useMemo(() => {
    const totals: Record<string, number> = {};
    for (const perLayer of current?.layerCounts.values() ?? []) {
      for (const [layer, n] of perLayer) totals[layer] = (totals[layer] ?? 0) + n;
    }
    return totals;
  }, [current]);

  const projects = ws.projects ?? [];
  const firstRun = ws.projects !== null && projects.length === 0;
  const present = state.mode === "present";
  const projectName = (id: string) => projects.find((p) => p.id === id)?.name ?? id;
  const visibleCount = current ? visibleIn(addresses, view.container, new Set(view.expanded)).size : 0;

  return (
    <div className={`workspace theme-${theme}${present ? " present" : ""}`} data-mode={state.mode}>
      {!present && (
        <TopBar state={state} projects={projects} container={view.container} zoom={zoom} dispatch={dispatch} />
      )}
      {state.notice && <NoticeBar notice={state.notice} onDismiss={() => dispatch({ type: "dismiss-notice" })} />}
      {view.focus !== null && state.mode === "graph" && (
        <FocusBanner address={view.focus} onClear={() => dispatch({ type: "clear-focus" })} />
      )}
      <main className="body">
        {!present && (
          <Rail
            open={railOpen}
            setOpen={setRailOpen}
            onFit={fit}
            onZoom={zoomBy}
            onResetZoom={() => zoomBy(1 / zoom)}
            onBack={() => dispatch({ type: "back" })}
            onCollapseAll={() => dispatch({ type: "collapse-all" })}
            onExpandAll={() => dispatch({ type: "expand-all", addresses: addresses.filter((a) => (counts.get(a) ?? 0) > 0 && (view.container === TOP || a.startsWith(`${view.container}.`))) })}
            onTheme={() => setTheme(theme === "dark" ? "light" : "dark")}
            onHelp={() => setShowKeys(true)}
            onGettingStarted={() => setShowGuide(true)}
          />
        )}
        {showKeys && !firstRun ? (
          <KeyboardHelp onClose={() => setShowKeys(false)} />
        ) : firstRun || showGuide ? (
          <Onboarding
            startCommand={startCommand}
            onSimulateIntake={() => {
              setShowGuide(false);
              // The mock can register a sample project and fill it while the user watches. It is
              // not part of GraphSource, because a real intake is run by an agent (Intake.md).
              const intake = (source as Partial<{ simulateIntake: () => Promise<ProjectRef> }>).simulateIntake;
              if (intake) {
                void intake.call(source).then(async (project) => {
                  await ws.reloadProjects();
                  dispatch({ type: "open-project", project: project.id });
                });
              } else {
                const first = projects[0];
                if (first) dispatch({ type: "open-project", project: first.id });
              }
            }}
            {...(firstRun ? {} : { onClose: () => setShowGuide(false) })}
          />
        ) : (
          <Canvas
            renderer={renderer}
            scene={scene}
            viewport={storedViewport}
            placeKey={`${state.project ?? ""}|${viewportKey}|${visibleCount > 0 ? "ready" : "empty"}`}
            open={open}
            dispatch={dispatch}
          />
        )}
        {!state.gestureHintDone && view.selection !== null && !present && (
          <p className="gesture-hint" role="note">{strings.hints.openOrGoUp(platform)}</p>
        )}
        {!present && view.selection !== null && (
          <Details
            address={view.selection}
            sheet={sheet}
            opensProject={linkedProject(view.selection) !== null}
            onClose={() => dispatch({ type: "select", address: null })}
            onFocus={() => view.selection && dispatch({ type: "set-focus", address: view.selection })}
            onOpenProject={() => view.selection && openLinked(view.selection)}
            {...(outsideMap && view.selection !== null
              ? {
                  onOpenMap: () => {
                    if (view.selection === null) return;
                    ws.addOutside(outsideMap);
                    dispatch({ type: "open-project", project: outsideMap.id, from: "link", at: outsideAddress(view.selection) });
                  },
                }
              : {})}
            onSelect={(address) => dispatch({ type: "select", address })}
          />
        )}
      </main>
      {!present && (
        <BottomStrip
          state={state}
          layers={current?.layers ?? []}
          counts={layerTotals}
          activity={ws.activity}
          agents={ws.agents}
          unseen={ws.unseenActivity}
          simulated={simulated}
          projectName={projectName}
          onOpenActivity={ws.markActivitySeen}
          dispatch={dispatch}
          onSelect={(project, address) => {
            if (project !== state.project) dispatch({ type: "open-project", project });
            dispatch({ type: "select", address });
          }}
        />
      )}
    </div>
  );
}
