// Hosts a GraphRenderer and turns its raw input into state actions (UX sections 4 and 5).

import { useEffect, useRef } from "react";
import type React from "react";
import type { GraphRenderer, RenderScene, Viewport } from "../graph/renderer";
import type { Action } from "../state/view";

export interface CanvasProps {
  renderer: GraphRenderer;
  scene: RenderScene;
  /** The stored viewport for this project and container, or null to fit on first show. */
  viewport: Viewport | null;
  /** Changes whenever the project or container changes, so the canvas restores or fits once. */
  placeKey: string;
  /** The action a double-click or Enter on an element performs. */
  open: (address: string) => Action;
  dispatch: (action: Action) => void;
}

export function Canvas({ renderer, scene, viewport, placeKey, open, dispatch }: CanvasProps) {
  const host = useRef<HTMLDivElement>(null);
  const latest = useRef({ open, dispatch, viewport });
  latest.current = { open, dispatch, viewport };
  const restoredFor = useRef<string | null>(null);

  useEffect(() => {
    const element = host.current;
    if (!element) return;
    renderer.mount(element, {
      nodeClick: (address, modifiers) => {
        if (modifiers.up) latest.current.dispatch({ type: "up" });
        else latest.current.dispatch({ type: "select", address });
      },
      nodeDoubleClick: (address) => latest.current.dispatch(latest.current.open(address)),
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
      else void renderer.fit(false).then((fitted) => latest.current.dispatch({ type: "viewport", viewport: fitted }));
    });
    return () => {
      live = false;
    };
  }, [renderer, scene, placeKey]);

  // Keyboard focus on a node selects it; pointer focus does not, so a Ctrl-click is never preceded
  // by a plain select (Jorge's renderer leaves keyboard selection to the shell).
  const onFocus = (e: React.FocusEvent<HTMLDivElement>) => {
    const node = e.target instanceof Element ? e.target.closest("[data-address]") : null;
    const address = node?.getAttribute("data-address");
    if (address && node?.matches(":focus-visible")) latest.current.dispatch({ type: "select", address });
  };
  return <div className="canvas" ref={host} onFocus={onFocus} />;
}
