// The graph workspace (dev/user_agent_interfaces.md; interaction: dev/user_agent_interfaces-ux.md).

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { GraphRenderer, Viewport } from "./graph/renderer";
import { CAMERA_MS, MAX_ZOOM, MIN_ZOOM } from "./graph/renderer";
import type { Address, GraphSource, ProjectRef, SummarySheet, WorkspaceEvents } from "./source";
import * as strings from "./strings";
import { elementScene, functionalScene, type SceneInput } from "./state/scene";
import { TOP, bandOf, beneathCounts, graphAddresses, outsideAddress, startBudget, startExpansion, visibleIn } from "./state/structure";
import { currentView, type Action } from "./state/view";
import { Canvas } from "./views/Canvas";
import { BottomStrip, Details, FocusBanner, KeyboardHelp, Legend, NoticeBar, Rail, TopBar, platform } from "./views/Chrome";
import { Onboarding } from "./views/Onboarding";
import { ACTIVE_MS, useWorkspace } from "./views/useWorkspace";
import { connected, isArrow, nearestInDirection, nodeCentres } from "./views/navigate";

export interface AppProps {
  source: GraphSource;
  events: WorkspaceEvents;
  renderer: GraphRenderer;
  /** True while the data is simulated; the views then show the Simulated badge. */
  simulated: boolean;
  /** The command that started this page's server, shown in onboarding (UI-U1). */
  startCommand: string;
  /** The page's own address (its origin), shown in the bottom strip with a control that copies it. */
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
  // The legend opens by default until the viewer closes it once (a per-browser convenience).
  const [legendOpen, setLegendOpen] = useState(() => {
    try {
      return localStorage.getItem("mf-legend-closed") !== "1";
    } catch {
      return true;
    }
  });
  const toggleLegend = useCallback(() => {
    setLegendOpen((open) => {
      try {
        localStorage.setItem("mf-legend-closed", open ? "1" : "0");
      } catch {
        // Storage can be unavailable; the toggle still works for this page.
      }
      return !open;
    });
  }, []);
  const [sheet, setSheet] = useState<SummarySheet | null>(null);
  const [zoom, setZoom] = useState(1);
  const [canvasSize, setCanvasSize] = useState<{ width: number; height: number } | null>(null);
  const onCanvasSize = useCallback((width: number, height: number) => {
    setCanvasSize((size) => (size && size.width === width && size.height === height ? size : { width, height }));
  }, []);
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
        .map((agent) => ({
          id: agent.id,
          name: agent.name,
          at: agent.at,
          active: now - agent.lastSeen < ACTIVE_MS,
          doing: agent.activity || null,
        })),
      opensProject: (address) => linkedProject(address) !== null,
    };
  }, [current, state.project, ws.agents, linkedProject]);

  // The project's own name for an element, or the last segment of its address.
  const nameOf = useCallback(
    (address: Address): string => {
      const name = sceneInput?.fields.get(address)?.name;
      return typeof name === "string" && name.trim() !== "" ? name : address.slice(address.lastIndexOf(".") + 1);
    },
    [sceneInput],
  );
  // The records of every layer the selected element holds, read when its sheet arrives.
  const [records, setRecords] = useState<Record<string, unknown[]> | null>(null);
  useEffect(() => {
    let live = true;
    setRecords(null);
    const project = state.project;
    const at = sheet?.at;
    if (!sheet || project === null || at === undefined) return;
    const layers = Object.entries(sheet.layers).filter(([, { records: n }]) => n > 0).map(([layer]) => layer);
    void Promise.all(layers.map(async (layer) => [layer, await source.layerRecords(project, at, layer).catch(() => [])] as const)).then(
      (read) => live && setRecords(Object.fromEntries(read)),
    );
    return () => {
      live = false;
    };
  }, [sheet, state.project, source]);

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

  // A first view of a container expands level by level to fill the canvas, before it is fitted.
  const firstView = current !== null && !view.visited.includes(view.container);
  useEffect(() => {
    if (!firstView || !canvasSize || state.mode === "element") return;
    const budget = startBudget(canvasSize.width, canvasSize.height);
    dispatch({ type: "first-view", container: view.container, expand: startExpansion(addresses, view.container, budget) });
  }, [firstView, canvasSize, state.mode, view.container, addresses, dispatch]);

  const scene = useMemo(() => {
    if (!sceneInput) return { nodes: [], edges: [], top: null };
    if (state.mode === "element" && focusTarget !== null) return elementScene(state, sceneInput, focusTarget);
    return functionalScene(state, sceneInput);
  }, [state, sceneInput, focusTarget]);

  const viewportKey = state.mode === "element" ? `element:${focusTarget ?? ""}` : view.container;
  const storedViewport: Viewport | null = view.viewports[viewportKey] ?? null;

  // The viewport on screen: every zoom control starts from it, and the zoom label follows it.
  const shown = useRef<Viewport | null>(null);
  const [viewTick, setViewTick] = useState(0);
  const onViewport = useCallback((viewport: Viewport) => {
    shown.current = viewport;
    setZoom(viewport.zoom);
    setViewTick((tick) => tick + 1);
  }, []);

  /** Zooms to `target` around the centre of the canvas, from the viewport on screen. */
  const zoomTo = useCallback(
    (target: number) => {
      const base = shown.current ?? { x: 0, y: 0, zoom: 1 };
      const next = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, target));
      const canvas = document.querySelector<HTMLElement>(".canvas");
      const cx = (canvas?.clientWidth ?? 0) / 2;
      const cy = (canvas?.clientHeight ?? 0) / 2;
      const k = next / base.zoom;
      const viewport = { zoom: next, x: cx - (cx - base.x) * k, y: cy - (cy - base.y) * k };
      renderer.setViewport(viewport, true);
      onViewport(viewport);
      dispatch({ type: "viewport", viewport });
    },
    [renderer, onViewport, dispatch],
  );
  const zoomBy = useCallback((factor: number) => zoomTo((shown.current?.zoom ?? 1) * factor), [zoomTo]);
  const fit = useCallback(
    () =>
      void renderer.fit(true).then((v) => {
        onViewport(v);
        dispatch({ type: "viewport", viewport: v });
      }),
    [renderer, onViewport, dispatch],
  );

  // Climb step 6b: elements with new activity outside the view, counted at the canvas edge. The
  // view never moves by itself; activating the chip moves it, because the user asked.
  const [offView, setOffView] = useState<Address[]>([]);
  useEffect(() => {
    const unseen = scene.nodes.filter((node) => node.unseen).map((node) => node.address);
    const measure = () => setOffView(unseen.length > 0 ? renderer.outsideView(unseen) : []);
    // Once now, and again when an eased camera move started by this change has settled.
    const frame = requestAnimationFrame(measure);
    const settled = setTimeout(measure, CAMERA_MS + 60);
    return () => {
      cancelAnimationFrame(frame);
      clearTimeout(settled);
    };
  }, [scene, renderer, viewTick]);
  const offViewArrow = useMemo(() => {
    const canvas = document.querySelector<HTMLElement>(".canvas")?.getBoundingClientRect();
    const centres = nodeCentres();
    const points = offView.flatMap((address) => centres.get(address) ?? []);
    if (!canvas || points.length === 0) return { arrow: "", dx: 0, dy: 0 };
    const dx = points.reduce((sum, p) => sum + p.x, 0) / points.length - (canvas.left + canvas.width / 2);
    const dy = points.reduce((sum, p) => sum + p.y, 0) / points.length - (canvas.top + canvas.height / 2);
    const arrows = ["→", "↘", "↓", "↙", "←", "↖", "↑", "↗"];
    const octant = Math.round(Math.atan2(dy, dx) / (Math.PI / 4));
    return { arrow: arrows[(octant + 8) % 8] ?? "", dx, dy };
  }, [offView]);
  const showOffView = useCallback(() => {
    const base = shown.current;
    const canvas = document.querySelector<HTMLElement>(".canvas")?.getBoundingClientRect();
    if (!base || !canvas) return;
    // Centre the box around every element with new activity, so showing one does not hide another;
    // when they do not all fit, centre the ones outside the view.
    const boxes = (addresses: Address[]) =>
      addresses.flatMap((address) => {
        const node = document.querySelector(`.canvas [data-address="${CSS.escape(address)}"]`);
        return node ? [node.getBoundingClientRect()] : [];
      });
    const all = boxes(scene.nodes.filter((node) => node.unseen).map((node) => node.address));
    const span = (rects: DOMRect[]) => ({
      left: Math.min(...rects.map((r) => r.left)), right: Math.max(...rects.map((r) => r.right)),
      top: Math.min(...rects.map((r) => r.top)), bottom: Math.max(...rects.map((r) => r.bottom)),
    });
    const whole = all.length > 0 ? span(all) : null;
    const fits = whole !== null && whole.right - whole.left < canvas.width - 48 && whole.bottom - whole.top < canvas.height - 48;
    const target = fits ? whole : span(boxes(offView));
    if (!Number.isFinite(target.left)) return;
    const dx = (target.left + target.right) / 2 - (canvas.left + canvas.width / 2);
    const dy = (target.top + target.bottom) / 2 - (canvas.top + canvas.height / 2);
    const viewport = { ...base, x: base.x - dx, y: base.y - dy };
    renderer.setViewport(viewport, true);
    onViewport(viewport);
    dispatch({ type: "viewport", viewport });
  }, [renderer, scene, offView, onViewport, dispatch]);

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

  // "Go up" at a member of an open group closes the group, so the members fold back into one
  // stacked element. Anywhere else it leaves the container, as before.
  const up = useCallback(
    (address: Address): Action => {
      const parent = address.includes(".") ? address.slice(0, address.lastIndexOf(".")) : null;
      return parent !== null && view.expanded.includes(parent) ? { type: "toggle-expanded", address: parent } : { type: "up" };
    },
    [view.expanded],
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
          zoomTo(1);
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
        case isArrow(e.key) && selection !== null: {
          // Along wants, to the connected element most nearly in the arrow's direction; nothing
          // happens when none lies that way. focusNode eases the view only if it is off screen.
          if (!selection || !isArrow(e.key)) break;
          e.preventDefault();
          const next = nearestInDirection(selection, connected(scene, selection), nodeCentres(), e.key);
          if (next) {
            dispatch({ type: "select", address: next });
            renderer.focusNode(next);
          }
          break;
        }
        default:
          return;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dispatch, view, state.mode, state.notice, zoomBy, zoomTo, fit, beneath, open, linkedProject, openLinked, sheet, zoom, showKeys, scene, renderer]);

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
            onResetZoom={() => zoomTo(1)}
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
            simulated={simulated}
            empty={firstRun}
            startCommand={startCommand}
            onCheckAgain={async () => {
              // A project registered after the page loaded: open the first one, as at start-up.
              const list = await ws.reloadProjects();
              const first = list?.[0];
              if (first) dispatch({ type: "open-project", project: first.id });
              return list?.length ?? null;
            }}
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
            up={up}
            onViewport={onViewport}
            ready={!firstView || state.mode === "element"}
            onSize={onCanvasSize}
            dispatch={dispatch}
          />
        )}
        {current && addresses.length === 0 && !firstRun && (
          // A registered project whose map has no element yet: say so, in place of a blank canvas.
          <p className="empty-map">{strings.graph.emptyMap}</p>
        )}
        {offView.length > 0 && !firstRun && (
          <button type="button" className="off-view" aria-label={strings.offView.label(offView.length)} onClick={showOffView}>
            {strings.offView.chip(offView.length, offViewArrow.arrow)}
          </button>
        )}
        {!state.gestureHintDone && view.selection !== null && !present && (
          <p className="gesture-hint" role="note">{strings.hints.openOrGoUp(platform)}</p>
        )}
        {!present && (view.selection !== null || (legendOpen && !firstRun)) && (
          <div className="side">
        {view.selection !== null && (
          <Details
            address={view.selection}
            sheet={sheet}
            records={records}
            nameOf={nameOf}
            beneath={addresses.filter((a) => a.startsWith(`${view.selection}.`) && !a.slice(String(view.selection).length + 1).includes("."))}
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
        {legendOpen && !firstRun && <Legend onClose={toggleLegend} simulated={simulated} />}
          </div>
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
          legendOpen={legendOpen}
          onToggleLegend={toggleLegend}
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
