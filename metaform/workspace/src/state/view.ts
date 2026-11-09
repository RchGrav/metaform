// The view state and every change to it (dev/user_agent_interfaces-ux.md, section 1).
// One reducer: modes, gestures, project switches and incoming activity all go through `reduce`,
// so nothing is lost when the view changes. Words shown to the user live in src/strings.ts;
// the state holds structured notices only.

import type { Address } from "../source";
import type { Viewport } from "../graph/renderer";
import { TOP, isBeneath, parentOf } from "./structure";

export type Mode = "graph" | "element" | "present";
export type LayerVisibility = "visible" | "hidden";

/** How far the pivot layout reaches along wants (UX section 10). */
export const FOCUS_REACH = 2;

/** The state kept for each project, so switching projects and back restores it (UX section 7). */
export interface ProjectView {
  /** The address whose elements fill the graph; TOP for the project's top level. */
  container: Address;
  selection: Address | null;
  /** The pivot element, or null. */
  focus: Address | null;
  /** Elements whose elements beneath are shown. Everything else with elements beneath is collapsed. */
  expanded: Address[];
  /** One viewport per container, keyed by container address. Each map has its own ProjectView. */
  viewports: Record<Address, Viewport>;
  /** Elements with activity the user has not seen. */
  unseen: Address[];
}

/** A place in the workspace that Back returns to. */
export interface Place {
  project: string;
  /** The chained maps entered from the project's main map (R-4.15); [] is the main map. */
  chain: Address[];
  container: Address;
  selection: Address | null;
  focus: Address | null;
}

export type Notice =
  | { kind: "moved"; missing: Address; showing: Address }
  | { kind: "not-connected"; reason: string }
  | { kind: "refused"; reason: string };

export interface ViewState {
  project: string | null;
  /**
   * The chained maps entered from the project's main map, outermost first: each address is the
   * element, in the map before it, that holds the next map (R-4.15). [] is the main map.
   */
  chain: Address[];
  mode: Mode;
  views: Record<string, ProjectView>;
  /** Visibility by layer name, shared by every project (UX section 8). Unknown layers are visible. */
  layers: Record<string, LayerVisibility>;
  /** The isolated layer, or null. Isolation keeps `layers` so leaving it restores the visible set. */
  isolated: string | null;
  history: Place[];
  /** The project and place a cross-project move came from, for the return chip (UX section 7). */
  returnTo: Place | null;
  notice: Notice | null;
  /** The gesture hint shows until the user opens or goes up once (terms sheet rule 3). */
  gestureHintDone: boolean;
}

export type Action =
  | { type: "open-project"; project: string; from?: "link" }
  | { type: "select"; address: Address | null }
  | { type: "open"; address: Address; beneath: number }
  /** Opens the chained map an element holds (owner, 2026-11-09: a nested graph is the element's own map). */
  | { type: "open-map"; address: Address }
  | { type: "up" }
  | { type: "back" }
  | { type: "mode"; mode: Mode }
  | { type: "set-focus"; address: Address }
  | { type: "clear-focus" }
  | { type: "toggle-expanded"; address: Address }
  | { type: "expand-all"; addresses: Address[] }
  | { type: "collapse-all" }
  | { type: "layer"; layer: string; visibility: LayerVisibility }
  | { type: "isolate"; layer: string | null }
  | { type: "all-layers"; layers: string[]; visibility: LayerVisibility }
  | { type: "viewport"; viewport: Viewport }
  | { type: "map-changed"; project: string; addresses: Address[] }
  | { type: "activity"; project: string; address: Address }
  | { type: "seen"; address: Address }
  | { type: "not-connected"; reason: string }
  | { type: "refused"; reason: string }
  | { type: "connected" }
  | { type: "dismiss-notice" };

export const HISTORY_LIMIT = 100;

export function initialState(): ViewState {
  return {
    project: null,
    chain: [],
    mode: "graph",
    views: {},
    layers: {},
    isolated: null,
    history: [],
    returnTo: null,
    notice: null,
    gestureHintDone: false,
  };
}

export function emptyView(): ProjectView {
  return { container: TOP, selection: null, focus: null, expanded: [], viewports: {}, unseen: [] };
}

/** The key of one map's view: the project, and the chain of elements to the map. */
export function viewKey(project: string, chain: readonly Address[]): string {
  return chain.length === 0 ? project : `${project}>${chain.join(">")}`;
}

/** The current map's view; an empty one before any project is open. */
export function currentView(state: ViewState): ProjectView {
  return (state.project !== null ? state.views[viewKey(state.project, state.chain)] : undefined) ?? emptyView();
}

export function layerShown(state: ViewState, layer: string): boolean {
  if (state.isolated !== null) return layer === state.isolated;
  return state.layers[layer] !== "hidden";
}

function place(state: ViewState): Place | null {
  if (state.project === null) return null;
  const view = currentView(state);
  return { project: state.project, chain: state.chain, container: view.container, selection: view.selection, focus: view.focus };
}

function pushHistory(state: ViewState): Place[] {
  const here = place(state);
  return here === null ? state.history : [...state.history, here].slice(-HISTORY_LIMIT);
}

function withView(state: ViewState, change: Partial<ProjectView>): ViewState {
  if (state.project === null) return state;
  return { ...state, views: { ...state.views, [viewKey(state.project, state.chain)]: { ...currentView(state), ...change } } };
}

/** The nearest address that still exists, walking up; TOP when none does. */
function survivor(address: Address, exists: ReadonlySet<Address>): Address {
  let at = address;
  while (at !== TOP && !exists.has(at)) at = parentOf(at);
  return at;
}

export function reduce(state: ViewState, action: Action): ViewState {
  const view = currentView(state);
  switch (action.type) {
    case "open-project": {
      if (action.project === state.project) return state;
      const here = place(state);
      return {
        ...state,
        history: pushHistory(state),
        project: action.project,
        chain: [],
        views: { ...state.views, [action.project]: state.views[action.project] ?? emptyView() },
        // The return chip shows after a move through a link, and stays until a third project opens.
        returnTo: action.from === "link" ? here : state.returnTo?.project === action.project ? null : state.returnTo,
      };
    }
    case "select":
      return withView(state, {
        selection: action.address,
        unseen: action.address === null ? view.unseen : view.unseen.filter((a) => a !== action.address),
      });
    case "open":
      if (action.beneath > 0) {
        return {
          ...withView({ ...state, history: pushHistory(state) }, { container: action.address, selection: null }),
          gestureHintDone: true,
        };
      }
      // A leaf opens in Element mode (UX section 5).
      return { ...withView(state, { selection: action.address }), mode: "element", gestureHintDone: true };
    case "open-map": {
      if (state.project === null) return state;
      const chain = [...state.chain, action.address];
      const key = viewKey(state.project, chain);
      return {
        ...state,
        history: pushHistory(state),
        chain,
        views: { ...state.views, [key]: state.views[key] ?? emptyView() },
        gestureHintDone: true,
      };
    }
    case "up": {
      if (view.container === TOP) {
        // At the top of a chained map, going up returns to the map that holds it, with the holding element selected.
        const holder = state.chain[state.chain.length - 1];
        if (holder === undefined) return state;
        const outer: ViewState = { ...state, history: pushHistory(state), chain: state.chain.slice(0, -1), gestureHintDone: true };
        return withView(outer, { selection: holder });
      }
      return {
        ...withView({ ...state, history: pushHistory(state) }, {
          container: parentOf(view.container),
          selection: view.container,
        }),
        gestureHintDone: true,
      };
    }
    case "back": {
      const last = state.history[state.history.length - 1];
      if (last === undefined) return state;
      const restored: ViewState = {
        ...state,
        history: state.history.slice(0, -1),
        project: last.project,
        chain: last.chain,
        returnTo: state.returnTo?.project === last.project ? null : state.returnTo,
      };
      const key = viewKey(last.project, last.chain);
      const base = restored.views[key] ?? emptyView();
      return {
        ...restored,
        views: {
          ...restored.views,
          [key]: { ...base, container: last.container, selection: last.selection, focus: last.focus },
        },
      };
    }
    case "mode":
      return { ...state, mode: action.mode };
    case "set-focus":
      return withView({ ...state, history: pushHistory(state) }, { focus: action.address, selection: action.address });
    case "clear-focus":
      return view.focus === null ? state : withView({ ...state, history: pushHistory(state) }, { focus: null });
    case "toggle-expanded":
      return withView(state, {
        expanded: view.expanded.includes(action.address)
          ? view.expanded.filter((a) => a !== action.address && !isBeneath(a, action.address))
          : [...view.expanded, action.address],
      });
    case "expand-all":
      return withView(state, { expanded: [...action.addresses] });
    case "collapse-all":
      return withView(state, { expanded: [] });
    case "layer":
      return { ...state, layers: { ...state.layers, [action.layer]: action.visibility }, isolated: null };
    case "isolate":
      return { ...state, isolated: action.layer };
    case "all-layers":
      return {
        ...state,
        isolated: null,
        layers: Object.fromEntries(action.layers.map((layer) => [layer, action.visibility])),
      };
    case "viewport":
      return withView(state, { viewports: { ...view.viewports, [view.container]: action.viewport } });
    case "map-changed": {
      // A project's main map changed (the event names no chained map). Refetched map: keep every field, and move any address that disappeared to its nearest parent.
      const stored = state.views[action.project];
      if (stored === undefined) return state;
      const exists = new Set(action.addresses);
      const keep = (address: Address | null): Address | null =>
        address === null ? null : exists.has(address) ? address : survivor(address, exists);
      const container = stored.container === TOP ? TOP : survivor(stored.container, exists);
      const next: ProjectView = {
        ...stored,
        container,
        selection: keep(stored.selection),
        focus: stored.focus !== null && exists.has(stored.focus) ? stored.focus : null,
        expanded: stored.expanded.filter((a) => exists.has(a)),
        unseen: stored.unseen.filter((a) => exists.has(a)),
      };
      const notice: Notice | null =
        action.project === state.project && state.chain.length === 0 && container !== stored.container
          ? { kind: "moved", missing: stored.container, showing: container }
          : state.notice;
      return { ...state, views: { ...state.views, [action.project]: next }, notice };
    }
    case "activity": {
      // Never moves the viewport or the selection (UX section 9): it only marks the element unseen.
      const stored = state.views[action.project] ?? emptyView();
      if (stored.selection === action.address || stored.unseen.includes(action.address)) return state;
      return { ...state, views: { ...state.views, [action.project]: { ...stored, unseen: [...stored.unseen, action.address] } } };
    }
    case "seen":
      return withView(state, { unseen: view.unseen.filter((a) => a !== action.address) });
    case "not-connected":
      return { ...state, notice: { kind: "not-connected", reason: action.reason } };
    case "refused":
      return { ...state, notice: { kind: "refused", reason: action.reason } };
    case "connected":
      return state.notice?.kind === "not-connected" || state.notice?.kind === "refused" ? { ...state, notice: null } : state;
    case "dismiss-notice":
      return { ...state, notice: null };
  }
}
