// Hosts a GraphRenderer and turns its raw input into state actions (UX sections 4 and 5).

import { useEffect, useRef } from "react";
import type { GraphRenderer, RenderScene, Viewport } from "../graph/renderer";
import type { Action } from "../state/view";

export interface CanvasProps {
  renderer: GraphRenderer;
  scene: RenderScene;
  /** The stored viewport for this project and container, or null to fit on first show. */
  viewport: Viewport | null;
  /** Changes whenever the project or container changes, so the canvas restores or fits once. */
  placeKey: string;
  beneath: (address: string) => number;
  dispatch: (action: Action) => void;
}

export function Canvas({ renderer, scene, viewport, placeKey, beneath, dispatch }: CanvasProps) {
  const host = useRef<HTMLDivElement>(null);
  const latest = useRef({ beneath, dispatch, viewport });
  latest.current = { beneath, dispatch, viewport };
  const restoredFor = useRef<string | null>(null);

  useEffect(() => {
    const element = host.current;
    if (!element) return;
    renderer.mount(element, {
      nodeClick: (address, modifiers) => {
        if (modifiers.up) latest.current.dispatch({ type: "up" });
        else latest.current.dispatch({ type: "select", address });
      },
      nodeDoubleClick: (address) =>
        latest.current.dispatch({ type: "open", address, beneath: latest.current.beneath(address) }),
      chevronClick: (address) => latest.current.dispatch({ type: "toggle-expanded", address }),
      backgroundClick: () => latest.current.dispatch({ type: "select", address: null }),
      viewportChange: (next) => latest.current.dispatch({ type: "viewport", viewport: next }),
    });
    return () => renderer.unmount();
  }, [renderer]);

  useEffect(() => {
    let live = true;
    void renderer.render(scene).then(() => {
      if (!live || restoredFor.current === placeKey) return;
      restoredFor.current = placeKey;
      // A container shown before gets its own viewport back; a new one is fitted (UX section 1).
      const stored = latest.current.viewport;
      if (stored) renderer.setViewport(stored, false);
      else void renderer.fit(false);
    });
    return () => {
      live = false;
    };
  }, [renderer, scene, placeKey]);

  return <div className="canvas" ref={host} />;
}
