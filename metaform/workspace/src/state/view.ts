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
  /** One viewport per container, keyed by container address. */
  viewports: Record<Address, Viewport>;
  /** Elements with activity the user has not seen. */
  unseen: Address[];
}

/** A place in the workspace that Back returns to. */
export interface Place {
  project: string;
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

/** The current project's view; an empty one before any project is open. */
export function currentView(state: ViewState): ProjectView {
  return (state.project !== null ? state.views[state.project] : undefined) ?? emptyView();
}

export function layerShown(state: ViewState, layer: string): boolean {
  if (state.isolated !== null) return layer === state.isolated;
  return state.layers[layer] !== "hidden";
}

function place(state: ViewState): Place | null {
  if (state.project === null) return null;
  const view = currentView(state);
  return { project: state.project, container: view.container, selection: view.selection, focus: view.focus };
}

function pushHistory(state: ViewState): Place[] {
  const here = place(state);
  return here === null ? state.history : [...state.history, here].slice(-HISTORY_LIMIT);
}

function withView(state: ViewState, change: Partial<ProjectView>): ViewState {
  if (state.project === null) return state;
  return { ...state, views: { ...state.views, [state.project]: { ...currentView(state), ...change } } };
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
    case "up": {
      if (view.container === TOP) return state;
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
        returnTo: state.returnTo?.project === last.project ? null : state.returnTo,
      };
      const base = restored.views[last.project] ?? emptyView();
      return {
        ...restored,
        views: {
          ...restored.views,
          [last.project]: { ...base, container: last.container, selection: last.selection, focus: last.focus },
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
      // Refetched map: keep every field, and move any address that disappeared to its nearest parent.
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
        action.project === state.project && container !== stored.container
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
