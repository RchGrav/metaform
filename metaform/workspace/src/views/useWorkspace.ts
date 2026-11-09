// Connects the view state to a GraphSource and WorkspaceEvents: loads each project's map and raw
// dump, refetches both on `map-changed` (seam rule 1), and turns events into state actions.

import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import type { Address, GraphSource, ProjectRef, RawDump, ShallowGraph, SummarySheet, WorkspaceEvents } from "../source";
import { RefusalError, TransportError } from "../source";
import { fieldsFromDump, graphAddresses, layerCounts, layerNames } from "../state/structure";
import { initialState, reduce, type Action, type ViewState } from "../state/view";

export interface ProjectData {
  graph: ShallowGraph;
  dump: RawDump;
  fields: Map<Address, Record<string, unknown>>;
  layerCounts: Map<Address, Map<string, number>>;
  layers: string[];
}

export interface AgentState {
  id: string;
  project: string;
  at: Address | null;
  activity: string;
  /** Active when its last event came within the last minute. */
  lastSeen: number;
}

export interface ActivityLine {
  id: number;
  time: Date;
  project: string;
  kind: "map-changed" | "presence";
  agent: string | null;
  at: Address | null;
  activity: string | null;
  simulated: boolean;
}

export const ACTIVE_MS = 60_000;
const ACTIVITY_LIMIT = 50;

/** A refusal (the server answered no) and a transport failure (no answer) are shown differently. */
function failed(error: unknown): Action {
  if (error instanceof RefusalError) return { type: "refused", reason: error.message };
  if (error instanceof TransportError) return { type: "not-connected", reason: error.message };
  return { type: "not-connected", reason: error instanceof Error ? error.message : String(error) };
}

export function useWorkspace(source: GraphSource, events: WorkspaceEvents, simulated: boolean) {
  const [state, dispatchRaw] = useReducer(reduce, undefined, initialState);
  const [projects, setProjects] = useState<ProjectRef[] | null>(null);
  const [data, setData] = useState<Record<string, ProjectData>>({});
  const [agents, setAgents] = useState<Record<string, AgentState>>({});
  const [activity, setActivity] = useState<ActivityLine[]>([]);
  const [activitySeen, setActivitySeen] = useState(0);
  const lineId = useRef(0);
  const stateRef = useRef<ViewState>(state);
  stateRef.current = state;

  const dispatch = useCallback((action: Action) => dispatchRaw(action), []);

  const load = useCallback(
    async (project: string): Promise<ProjectData | null> => {
      try {
        const [graph, dump] = await Promise.all([source.map(project), source.dump(project)]);
        const layers = layerNames(dump);
        const loaded: ProjectData = { graph, dump, fields: fieldsFromDump(dump), layerCounts: layerCounts(dump, layers), layers };
        setData((current) => ({ ...current, [project]: loaded }));
        dispatchRaw({ type: "connected" });
        // Check the view against the loaded map, so a place that no longer exists (or a link to an
        // element the project lacks) falls back to its nearest existing parent, with a notice.
        dispatchRaw({ type: "map-changed", project, addresses: graphAddresses(graph) });
        return loaded;
      } catch (error) {
        dispatchRaw(failed(error));
        return null;
      }
    },
    [source],
  );

  useEffect(() => {
    let live = true;
    source
      .projects()
      .then((list) => {
        if (!live) return;
        setProjects(list);
        const first = list[0];
        if (first) dispatchRaw({ type: "open-project", project: first.id });
      })
      .catch((error: unknown) => {
        if (live) dispatchRaw(failed(error));
      });
    return () => {
      live = false;
    };
  }, [source]);

  // Load each project the first time it opens.
  useEffect(() => {
    if (state.project !== null && data[state.project] === undefined) void load(state.project);
  }, [state.project, data, load]);

  // One subscription per known project, so activity in other projects is counted too.
  useEffect(() => {
    if (!projects) return;
    const stops = projects.map((project) => {
      // Presence the source announces while subscribing is where agents already are: state, not
      // new activity. Only events after that count as activity.
      let announcing = true;
      const stop = events.subscribe(project.id, (event) => {
        const time = new Date();
        lineId.current += 1;
        if (event.kind === "map-changed") {
          setActivity((lines) => [
            { id: lineId.current, time, project: event.project, kind: "map-changed" as const, agent: null, at: null, activity: null, simulated: event.simulated },
            ...lines,
          ].slice(0, ACTIVITY_LIMIT));
          void load(event.project);
        } else {
          setAgents((current) => ({
            ...current,
            [event.agent]: { id: event.agent, project: event.project, at: event.at, activity: event.activity, lastSeen: time.getTime() },
          }));
          if (announcing) return;
          setActivity((lines) => [
            { id: lineId.current, time, project: event.project, kind: "presence" as const, agent: event.agent, at: event.at, activity: event.activity, simulated: true },
            ...lines,
          ].slice(0, ACTIVITY_LIMIT));
          // New activity marks its element unseen; it never moves the viewport or the selection.
          if (event.at !== null) dispatchRaw({ type: "activity", project: event.project, address: event.at });
        }
      });
      announcing = false;
      return stop;
    });
    return () => stops.forEach((stop) => stop());
  }, [projects, events, load]);

  const sheet = useCallback(
    async (address: Address): Promise<SummarySheet | null> => {
      const project = stateRef.current.project;
      if (project === null) return null;
      try {
        return await source.goto(project, address);
      } catch (error) {
        // A NOT_FOUND at the top level means the project's root has no sheet, not a failure.
        if (error instanceof RefusalError && error.refusal.code === "NOT_FOUND") return null;
        dispatchRaw(failed(error));
        return null;
      }
    },
    [source],
  );

  const unseenActivity = activity.length - activitySeen;
  const current = state.project !== null ? data[state.project] ?? null : null;

  return useMemo(
    () => ({
      state,
      dispatch,
      projects,
      current,
      agents: Object.values(agents),
      activity,
      unseenActivity: Math.max(0, unseenActivity),
      markActivitySeen: () => setActivitySeen(activity.length),
      sheet,
      simulated,
    }),
    [state, dispatch, projects, current, agents, activity, unseenActivity, sheet, simulated],
  );
}

export type Workspace = ReturnType<typeof useWorkspace>;
