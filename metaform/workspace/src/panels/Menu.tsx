// A button that opens a menu. The menu is placed in the window, not in the button's container, so
// a zone or a floating panel that hides its overflow never clips it. The menu stays inside the window.

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import type React from "react";

/** The space kept between the menu and the edge of the window, in pixels. */
const EDGE = 8;

/** What a menu's content receives: a function that closes the menu and returns focus to its button. */
export type MenuContent = (close: () => void) => React.ReactNode;

/**
 * A button with a menu. `label` is the button's accessible name and tooltip; `text` is what the
 * button shows. The content gives its controls the roles menuitem or menuitemcheckbox. The arrow
 * keys move between the menu's buttons, and Escape or a press outside closes the menu.
 */
export function MenuButton(props: { label: string; text: React.ReactNode; className?: string; children: MenuContent }) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<{ left: number; top: number } | null>(null);
  const button = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);

  const close = useCallback(() => {
    setOpen(false);
    setPosition(null);
    button.current?.focus();
  }, []);

  // Under the button and aligned with its right edge; above the button when there is no room under it.
  const place = useCallback(() => {
    const anchor = button.current?.getBoundingClientRect();
    const own = menu.current?.getBoundingClientRect();
    if (!anchor || !own) return;
    const maxLeft = Math.max(EDGE, window.innerWidth - own.width - EDGE);
    const left = Math.min(maxLeft, Math.max(EDGE, anchor.right - own.width));
    const under = anchor.bottom + 4;
    const fitsUnder = under + own.height <= window.innerHeight - EDGE;
    const top = fitsUnder ? under : Math.max(EDGE, anchor.top - 4 - own.height);
    setPosition((old) => (old && old.left === left && old.top === top ? old : { left, top }));
  }, []);

  useLayoutEffect(() => {
    if (open) place();
  });

  useEffect(() => {
    if (!open) return;
    menu.current?.querySelector<HTMLElement>("button:not(:disabled)")?.focus();
    const outside = (e: PointerEvent) => {
      const target = e.target instanceof Node ? e.target : null;
      if (target && (menu.current?.contains(target) || button.current?.contains(target))) return;
      setOpen(false);
      setPosition(null);
    };
    window.addEventListener("pointerdown", outside, true);
    window.addEventListener("resize", place);
    return () => {
      window.removeEventListener("pointerdown", outside, true);
      window.removeEventListener("resize", place);
    };
  }, [open, place]);

  // Keys pressed in the menu stay in the menu: the page's shortcuts do not also act on them.
  const onKeyDown = (e: React.KeyboardEvent) => {
    e.stopPropagation();
    if (e.key === "Escape") {
      close();
      return;
    }
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp" && e.key !== "Home" && e.key !== "End") return;
    e.preventDefault();
    const items = Array.from(menu.current?.querySelectorAll<HTMLElement>("button:not(:disabled)") ?? []);
    if (items.length === 0) return;
    const at = items.indexOf(document.activeElement as HTMLElement);
    const next =
      e.key === "Home" ? 0 : e.key === "End" ? items.length - 1 : (at + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
    items[next]?.focus();
  };

  return (
    <>
      <button
        ref={button}
        type="button"
        className={props.className}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={props.label}
        title={props.label}
        onClick={() => (open ? close() : setOpen(true))}
      >
        {props.text}
      </button>
      {open && (
        <div
          ref={menu}
          className="menu"
          role="menu"
          aria-label={props.label}
          style={{ left: position?.left ?? 0, top: position?.top ?? 0, opacity: position ? 1 : 0 }}
          onKeyDown={onKeyDown}
        >
          {props.children(close)}
        </div>
      )}
    </>
  );
}
