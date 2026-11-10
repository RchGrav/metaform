// The graph workspace (dev/gui_specification.md; dev/user_agent_interfaces.md; interaction:
// dev/user_agent_interfaces-ux.md). The page is the top bar, the graph with the panels around it
// (src/panels), and the bottom strip.

import { diff, type ActivityItem } from "./activity/stream";
import { useSpecStore } from "./review/store";
import type { AgentService } from "./source/agent";
import { definitiveOf, fromDump, labelOf, type Spec } from "./spec/model";
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import type { GraphRenderer, Viewport } from "./graph/renderer";
import { CAMERA_MS, MAX_ZOOM, MIN_ZOOM } from "./graph/renderer";
import type { Address, GraphSource, ProjectRef, SummarySheet, WorkspaceEvents } from "./source";
import * as strings from "./strings";
import { initialDepth, maxDepth, shownDepth, visibleSet } from "./state/depth";
import { categoriesOf, elementScene, functionalElements, functionalLevels, functionalScene, type SceneInput } from "./state/scene";
import { bandOf, beneathCounts, graphAddresses, outsideAddress, startBudget, startExpansion, visibleIn } from "./state/structure";
import { canUndoDepth, categoryShown, currentView, type Action } from "./state/view";
import { Canvas } from "./views/Canvas";
import { GraphControls, type CategoryControl } from "./views/GraphControls";
import { Dock, PANELS, PanelsMenu, bodyOf, placeOf, useLayout, useNarrow, type PanelBodyProps } from "./panels";
import { BottomStrip, FocusBanner, KeyboardHelp, NoticeBar, Rail, TopBar, platform, type TopBarStatus } from "./views/Chrome";
import { elementEvidence } from "./spec/evidence";
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
  /** The service that proposes changes to the specification. The page labels a simulated one. */
  agent: AgentService;
}

/** metaform://map/project/<id>/<map>#<address> (seam gap 3): the project, and the element named after #. */
const PROJECT_LINK = /^metaform:\/\/map\/project\/([^/]+)\/[^#]*(?:#(.+))?$/;

function isTyping(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && (target.isContentEditable || ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName));
}

/** The page: it joins the workspace state, the graph, the panels and the chrome. */
export function App({ source, events, renderer, simulated, startCommand, agent }: AppProps) {
  const ws = useWorkspace(source, events, simulated);
  const { state, dispatch, current } = ws;
  const view = currentView(state);
  const [railOpen, setRailOpen] = useState(true);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [showGuide, setShowGuide] = useState(false);
  const [showKeys, setShowKeys] = useState(false);
  // Which panels are open and where, the zone sizes and the two text sizes (saved in this browser).
  const { layout, actions: panelActions } = useLayout(PANELS);
  const narrow = useNarrow();
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
  /** Keeps the viewport a fit settled on, as a zoom does. */
  const keepFit = useCallback(
    (viewport: Viewport) => {
      onViewport(viewport);
      dispatch({ type: "viewport", viewport });
    },
    [onViewport, dispatch],
  );
  const fit = useCallback(() => void renderer.fit(true).then(keepFit), [renderer, keepFit]);

  // Depth and categories of the functional graph (state/depth.ts). Every depth action carries the levels.
  const graphMode = state.mode !== "element";
  const levels = useMemo(() => (sceneInput && graphMode ? functionalLevels(state, sceneInput) : null), [state, sceneInput, graphMode]);
  const depthNow = view.depth?.now ?? null;
  const visible = useMemo(() => (levels ? visibleSet(levels, depthNow ?? initialDepth()) : new Set<Address>()), [levels, depthNow]);
  const categories = useMemo(
    (): CategoryControl[] =>
      sceneInput && graphMode
        ? categoriesOf(functionalElements(state, sceneInput)).map(({ category, elements }) => ({
            category,
            elements,
            state: !categoryShown(state, category) ? "hidden" : state.isolatedCategory === category ? "isolated" : "shown",
          }))
        : [],
    [state, sceneInput, graphMode],
  );
  const toggleDepth = useCallback(
    (address: Address): Action => (levels ? { type: "depth-toggle", levels, address } : { type: "select", address }),
    [levels],
  );

  // A depth action or a category the user shows or hides alters what is on screen, so the camera
  // eases to the new scope. A selection, an isolation and a change from an agent never move it.
  const scopeKey = `${JSON.stringify(depthNow)}|${JSON.stringify(state.categories)}`;
  const fittedScope = useRef<{ place: string; scope: string } | null>(null);
  useEffect(() => {
    const place = `${state.project ?? ""}|${view.container}|${state.mode}`;
    const last = fittedScope.current;
    fittedScope.current = { place, scope: scopeKey };
    if (!last || last.place !== place || last.scope === scopeKey) return;
    void renderer.fitScope(true).then(keepFit);
  }, [renderer, keepFit, scopeKey, state.project, view.container, state.mode]);


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
        case e.key === " " && selection !== null:
          e.preventDefault();
          if (selection) dispatch(toggleDepth(selection));
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
  }, [dispatch, view, state.mode, state.notice, zoomBy, zoomTo, fit, toggleDepth, open, linkedProject, openLinked, sheet, zoom, showKeys, scene, renderer]);

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

  // The controls lie over the top of the graph, and the menu over its left edge. Every fit keeps the graph clear of both.
  const controlsShown = !present && !firstRun && !showKeys && !showGuide && levels !== null && graphMode;
  const controlsBox = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const box = controlsBox.current;
    if (!box) return;
    const report = () => renderer.setInsets({ top: box.offsetHeight + 16, left: 56 });
    report();
    const observer = new ResizeObserver(report);
    observer.observe(box);
    return () => {
      observer.disconnect();
      renderer.setInsets({});
    };
  }, [renderer, controlsShown]);

  // What the page hands the body of every panel (src/panels/registry.tsx).
  const selection = view.selection;
  const select = useCallback((address: Address | null) => dispatch({ type: "select", address }), [dispatch]);
  // The one specification every view reads (ARCHITECTURE.md section 1). `saved` is built from the
  // server's dump. The store adds the changes the server has not confirmed (src/review/store.ts).
  const openName = state.project === null ? "" : projectName(state.project);
  const dump = current?.dump ?? null;
  const saved = useMemo(() => (dump && state.project !== null ? fromDump(openName, dump) : null), [dump, state.project, openName]);
  const review = useSpecStore({ source, agent, project: state.project, projectName: openName, simulated }, saved);
  const spec = review?.state.spec ?? saved;

  // The activity stream: what each change the server announced did to the specification. An item
  // is made by comparing the specification before the change with the one after it.
  const [items, setItems] = useState<ActivityItem[]>([]);
  const lastSaved = useRef<{ project: string; spec: Spec } | null>(null);
  useEffect(() => {
    if (!saved || state.project === null) return;
    const last = lastSaved.current;
    lastSaved.current = { project: state.project, spec: saved };
    if (!last || last.spec === saved) return;
    if (last.project !== state.project) {
      setItems([]);
      return;
    }
    const found = diff(last.spec, saved, new Date(), simulated);
    if (found.length > 0) setItems((all) => [...all, ...found].slice(-500));
  }, [saved, state.project, simulated]);
  // Selecting an element brings its details forward when the Entity panel is open behind another tab.
  const entityPlaced = placeOf(layout, "entity");
  const openPanel = panelActions.open;
  useEffect(() => {
    if (selection !== null && entityPlaced !== null && entityPlaced !== "floating") openPanel("entity");
    // Only a new selection brings the tab forward, so the user can go back to another tab.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selection]);
  /** The selection before the user chose an activity item, so "Back to where I was" restores it. */
  const beforeActivity = useRef<Address | null | undefined>(undefined);
  const activityOpen = placeOf(layout, "activity") !== null;
  const { markActivitySeen } = ws;
  useEffect(() => {
    if (activityOpen) markActivitySeen();
  }, [activityOpen, items, markActivitySeen]);
  const topStatus = useMemo(
    (): TopBarStatus | null =>
      spec === null
        ? null
        : {
            connection: state.notice?.kind === "not-connected" ? "not-connected" : simulated ? "simulated" : "connected",
            elements: spec.elements.length,
            unverified: spec.elements.filter((element) => elementEvidence(element).status === "unverified").length,
            pending: review?.state.pending.length ?? 0,
            proposals: review?.state.proposals.filter((proposal) => proposal.state === "proposed").length ?? 0,
          },
    [spec, review, state.notice, simulated],
  );
  const mainElement = useMemo(() => (spec ? definitiveOf(spec) ?? null : null), [spec]);
  const panelBody: PanelBodyProps = {
    spec,
    review,
    project: state.project,
    selection,
    simulated,
    select,
    entity:
      selection === null
        ? null
        : {
            address: selection,
            sheet,
            records,
            nameOf,
            beneath: addresses.filter((a) => a.startsWith(`${selection}.`) && !a.slice(selection.length + 1).includes(".")),
            opensProject: linkedProject(selection) !== null,
            onClose: () => select(null),
            onFocus: () => dispatch({ type: "set-focus", address: selection }),
            onOpenProject: () => openLinked(selection),
            ...(outsideMap
              ? {
                  onOpenMap: () => {
                    ws.addOutside(outsideMap);
                    dispatch({ type: "open-project", project: outsideMap.id, from: "link", at: outsideAddress(selection) });
                  },
                }
              : {}),
            onSelect: select,
          },
    activity: {
      items,
      connection: state.notice?.kind === "not-connected" ? "not-connected" : simulated ? "simulated" : "connected",
      selected: selection,
      onSelect: (address) => {
        if (beforeActivity.current === undefined) beforeActivity.current = selection;
        select(address);
      },
      onReturn: () => {
        if (beforeActivity.current !== undefined) select(beforeActivity.current);
        beforeActivity.current = undefined;
      },
    },
  };
  const renderPanel = (id: string) => {
    const Body = bodyOf(id);
    return Body ? <Body {...panelBody} /> : null;
  };

  return (
    <div
      className={`workspace theme-${theme}${present ? " present" : ""}`}
      data-mode={state.mode}
      style={{ "--text-workspace": `${layout.text.workspace}px`, "--text-panels": `${layout.text.panels}px` } as CSSProperties}
    >
      {!present && (
        <TopBar
          state={state}
          projects={projects}
          container={view.container}
          zoom={zoom}
          menu={<PanelsMenu layout={layout} actions={panelActions} panels={PANELS} narrow={narrow} />}
          status={topStatus}
          selected={selection === null ? null : nameOf(selection)}
          main={mainElement ? { name: labelOf(mainElement), onSelect: () => select(mainElement.address) } : null}
          markdownOpen={placeOf(layout, "markdown") !== null}
          onMarkdown={() => panelActions.toggle("markdown")}
          reviewOpen={placeOf(layout, "review") !== null}
          onReview={() => panelActions.toggle("review")}
          dispatch={dispatch}
        />
      )}
      {state.notice && <NoticeBar notice={state.notice} onDismiss={() => dispatch({ type: "dismiss-notice" })} />}
      {view.focus !== null && state.mode === "graph" && (
        <FocusBanner address={view.focus} onClear={() => dispatch({ type: "clear-focus" })} />
      )}
      {/* The panels show beside the graph, except in Present and before the home has a project. */}
      <Dock
        layout={layout}
        actions={panelActions}
        panels={PANELS}
        renderBody={renderPanel}
        narrow={narrow}
        shown={!present && !firstRun}
        graphShown={!showKeys && !showGuide}
      >
        {!present && (
          <Rail
            open={railOpen}
            setOpen={setRailOpen}
            onFit={fit}
            onZoom={zoomBy}
            onResetZoom={() => zoomTo(1)}
            onBack={() => dispatch({ type: "back" })}
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
            toggle={toggleDepth}
            onViewport={onViewport}
            ready={!firstView || state.mode === "element"}
            onSize={onCanvasSize}
            dispatch={dispatch}
          />
        )}
        {controlsShown && levels && (
          <div className="graph-controls-place" ref={controlsBox}>
            <GraphControls
              hasSelection={selection !== null}
              depth={shownDepth(levels, visible)}
              maxDepth={maxDepth(levels)}
              canUndo={canUndoDepth(state)}
              categories={categories}
              onFitGraph={fit}
              onFitSelection={() => void renderer.fitSelection(true).then(keepFit)}
              onFitBranch={() => void renderer.fitBranch(true).then(keepFit)}
              onCollapseLevel={() => dispatch({ type: "depth-collapse-level", levels })}
              onExpandLevel={() => dispatch({ type: "depth-expand-level", levels })}
              onExpandAll={() => dispatch({ type: "depth-expand-all", levels })}
              onCollapseAll={() => dispatch({ type: "depth-collapse-all", levels })}
              onUndo={() => dispatch({ type: "depth-undo" })}
              onToggleCategory={(category) => dispatch({ type: "category-toggle", category })}
              onIsolateCategory={(category) => dispatch({ type: "category-isolate", category })}
              onShowAllCategories={() => dispatch({ type: "categories-show-all" })}
              onHideAllCategories={() => dispatch({ type: "categories-hide-all", categories: categories.map((c) => c.category) })}
              onRestoreCategories={() => dispatch({ type: "categories-restore" })}
            />
          </div>
        )}
        {present && (
          <button type="button" className="leave-present" onClick={() => dispatch({ type: "mode", mode: "graph" })}>
            {strings.modes.leavePresent}
          </button>
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
      </Dock>
      {!present && (
        <BottomStrip
          state={state}
          layers={current?.layers ?? []}
          counts={layerTotals}
          agents={ws.agents}
          unseen={ws.unseenActivity}
          simulated={simulated}
          legendOpen={placeOf(layout, "legend") !== null}
          onToggleLegend={() => panelActions.toggle("legend")}
          activityOpen={activityOpen}
          onToggleActivity={() => panelActions.toggle("activity")}
          dispatch={dispatch}
        />
      )}
    </div>
  );
}
