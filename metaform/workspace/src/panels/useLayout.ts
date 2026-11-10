// The layout as React state: read from localStorage once, saved after every adjustment.

import { useEffect, useMemo, useState } from "react";
import {
  closePanel, dockPanel, floatPanel, movePanel, openPanel, placeFloating, placeOf, resizeZone, restoreLayout, setTextSize,
  type Area, type FloatingPanel, type Layout, type PanelSeed, type TextSize, type Zone,
} from "./layout";
import { loadLayout, saveLayout, type LayoutStorage } from "./storage";

/** Every adjustment the page makes to the layout. Each one is saved. */
export interface LayoutActions {
  /** Shows a panel: opens it, makes it the active tab, or brings it to the top. */
  open: (id: string) => void;
  close: (id: string) => void;
  /** Closes an open panel and opens a closed one. */
  toggle: (id: string) => void;
  move: (id: string, zone: Zone) => void;
  /** Floats a panel inside the graph area, whose size is `area`. */
  float: (id: string, area: Area) => void;
  dock: (id: string) => void;
  resizeZone: (zone: Zone, size: number) => void;
  placeFloating: (id: string, rect: Partial<Omit<FloatingPanel, "id">>) => void;
  setTextSize: (which: keyof TextSize, size: number) => void;
  restore: () => void;
}

/** The browser's localStorage, or null when the browser blocks it. */
function browserStorage(): LayoutStorage | null {
  try {
    return typeof localStorage === "undefined" ? null : localStorage;
  } catch {
    return null;
  }
}

/** The layout and the actions that adjust it. `seeds` must be the same list for the life of the page. */
export function useLayout(seeds: readonly PanelSeed[]): { layout: Layout; actions: LayoutActions } {
  const [layout, setLayout] = useState(() => loadLayout(browserStorage(), seeds));
  useEffect(() => {
    saveLayout(browserStorage(), layout);
  }, [layout]);
  const actions = useMemo(
    (): LayoutActions => ({
      open: (id) => setLayout((l) => openPanel(l, id)),
      close: (id) => setLayout((l) => closePanel(l, id)),
      toggle: (id) => setLayout((l) => (placeOf(l, id) === null ? openPanel(l, id) : closePanel(l, id))),
      move: (id, zone) => setLayout((l) => movePanel(l, id, zone)),
      float: (id, area) => setLayout((l) => floatPanel(l, id, area)),
      dock: (id) => setLayout((l) => dockPanel(l, id)),
      resizeZone: (zone, size) => setLayout((l) => resizeZone(l, zone, size)),
      placeFloating: (id, rect) => setLayout((l) => placeFloating(l, id, rect)),
      setTextSize: (which, size) => setLayout((l) => setTextSize(l, which, size)),
      restore: () => setLayout((l) => restoreLayout(l, seeds)),
    }),
    [seeds],
  );
  return { layout, actions };
}

/** True while the window is at most 900 px wide: the page then shows one zone under the graph. */
export function useNarrow(): boolean {
  const query = "(max-width: 900px)";
  const [narrow, setNarrow] = useState(() => typeof matchMedia === "function" && matchMedia(query).matches);
  useEffect(() => {
    if (typeof matchMedia !== "function") return;
    const media = matchMedia(query);
    const update = () => setNarrow(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return narrow;
}
