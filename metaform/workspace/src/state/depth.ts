// Depth in the functional graph, as the earlier Metaform map counted it. Levels are counted along
// the wants, breadth first, from the elements that nothing relies on. Each element hangs from the
// element that reached it first, and an element whose next level is hidden holds those elements.
// Pure functions: addresses and want pairs in, levels, visible sets and counts out.

import type { Address } from "../source";

/** A map of up to this many elements is shown whole at first. */
export const WHOLE_MAP_LIMIT = 200;
/** How many earlier depth states undo can restore. */
export const UNDO_LIMIT = 50;

/** The levels of one graph, and the element each element hangs from. */
export interface Levels {
  /** Every element, by level and then by address. */
  order: readonly Address[];
  /** The level of each element; 0 for an element that nothing relies on. */
  level: ReadonlyMap<Address, number>;
  /** The element that reached this one first; null at level 0. */
  parent: ReadonlyMap<Address, Address | null>;
  /** The elements that hang from each element. */
  children: ReadonlyMap<Address, readonly Address[]>;
  /** The first level that draws a want: the lowest level at which both ends of some want show. */
  first: number;
  /** The deepest level. */
  deepest: number;
}

/** What the user chose to show: a depth, and the elements opened or closed one by one. */
export interface DepthState {
  /** Depth 1 shows up to the first level that draws a want. Null is the default for the map's size. */
  depth: number | null;
  /** Elements at or beyond the depth whose next level is shown. */
  opened: Address[];
  /** Elements within the depth whose next level is hidden. */
  closed: Address[];
}

/** The depth state of one project, with the earlier states that undo restores. */
export interface DepthRecord {
  now: DepthState;
  undo: DepthState[];
}

/** Every change to the depth state. Each one except undo carries the levels it is computed from. */
export type DepthAction =
  | { type: "depth-collapse-all"; levels: Levels }
  | { type: "depth-expand-all"; levels: Levels }
  | { type: "depth-set"; levels: Levels; depth: number }
  | { type: "depth-expand-level"; levels: Levels }
  | { type: "depth-collapse-level"; levels: Levels }
  | { type: "depth-toggle"; levels: Levels; address: Address }
  | { type: "depth-undo" };

/** The depth state before the user changes anything. */
export function initialDepth(): DepthState {
  return { depth: null, opened: [], closed: [] };
}

/**
 * Counts the levels of a graph. `wants` are [holder, wanted] pairs. A want to itself, and a want
 * with an end that is not in `addresses`, is ignored. Elements that only a cycle reaches have no
 * element that nothing relies on above them; the first of them by address starts at level 0.
 */
export function levelsOf(addresses: readonly Address[], wants: readonly (readonly [Address, Address])[]): Levels {
  const all = [...new Set(addresses)].sort();
  const known = new Set(all);
  const wanted = new Map<Address, Address[]>();
  const reliedOn = new Set<Address>();
  const pairs: [Address, Address][] = [];
  for (const [holder, target] of wants) {
    if (holder === target || !known.has(holder) || !known.has(target)) continue;
    pairs.push([holder, target]);
    wanted.set(holder, [...(wanted.get(holder) ?? []), target]);
    reliedOn.add(target);
  }
  for (const list of wanted.values()) list.sort();

  const level = new Map<Address, number>();
  const parent = new Map<Address, Address | null>();
  const children = new Map<Address, Address[]>();
  const spread = (starts: Address[]): void => {
    let frontier = starts;
    for (const start of starts) {
      level.set(start, 0);
      parent.set(start, null);
    }
    while (frontier.length > 0) {
      const next: Address[] = [];
      for (const from of frontier) {
        for (const to of wanted.get(from) ?? []) {
          if (level.has(to)) continue;
          level.set(to, (level.get(from) ?? 0) + 1);
          parent.set(to, from);
          children.set(from, [...(children.get(from) ?? []), to]);
          next.push(to);
        }
      }
      frontier = next;
    }
  };
  spread(all.filter((address) => !reliedOn.has(address)));
  for (const address of all) if (!level.has(address)) spread([address]);

  const at = (address: Address) => level.get(address) ?? 0;
  const order = [...all].sort((a, b) => at(a) - at(b) || (a < b ? -1 : a > b ? 1 : 0));
  const deepest = order.reduce((max, address) => Math.max(max, at(address)), 0);
  const first = pairs.length === 0 ? 0 : Math.min(...pairs.map(([a, b]) => Math.max(at(a), at(b))));
  return { order, level, parent, children, first, deepest };
}

/** How many depths the graph has: depth 1 is the first level that draws a want. */
export function maxDepth(levels: Levels): number {
  return Math.max(1, levels.deepest - levels.first + 1);
}

/** The depth a map starts at: whole up to WHOLE_MAP_LIMIT elements, otherwise depth 2. */
export function defaultDepth(levels: Levels): number {
  return levels.order.length <= WHOLE_MAP_LIMIT ? maxDepth(levels) : Math.min(2, maxDepth(levels));
}

/** The depth the state asks for, as a number within the graph's depths. */
export function chosenDepth(levels: Levels, state: DepthState): number {
  return Math.min(maxDepth(levels), Math.max(1, state.depth ?? defaultDepth(levels)));
}

/** True when the element's next level shows, by the depth or by the user's own opening or closing. */
function isOpen(levels: Levels, state: DepthState, address: Address, opened: ReadonlySet<Address>, closed: ReadonlySet<Address>): boolean {
  if (closed.has(address)) return false;
  if (opened.has(address)) return true;
  return (levels.level.get(address) ?? 0) < levels.first + chosenDepth(levels, state) - 1;
}

/**
 * The elements that show. An element at level 0 always shows. Any other element shows when the
 * element it hangs from shows and is open.
 */
export function visibleSet(levels: Levels, state: DepthState): Set<Address> {
  const opened = new Set(state.opened);
  const closed = new Set(state.closed);
  const visible = new Set<Address>();
  for (const address of levels.order) {
    const from = levels.parent.get(address) ?? null;
    if (from === null || (visible.has(from) && isOpen(levels, state, from, opened, closed))) visible.add(address);
  }
  return visible;
}

/**
 * For each visible element, how many hidden elements it holds: the hidden elements whose nearest
 * visible element, along the elements they hang from, is this one. `counted` leaves elements out
 * of the count, such as those in a hidden category.
 */
export function hiddenCounts(levels: Levels, visible: ReadonlySet<Address>, counted: (address: Address) => boolean = () => true): Map<Address, number> {
  const counts = new Map<Address, number>();
  for (const address of levels.order) {
    if (visible.has(address) || !counted(address)) continue;
    let at = levels.parent.get(address) ?? null;
    while (at !== null && !visible.has(at)) at = levels.parent.get(at) ?? null;
    if (at !== null) counts.set(at, (counts.get(at) ?? 0) + 1);
  }
  return counts;
}

/** The depth on screen: the deepest visible level, counted from the first level that draws a want. */
export function shownDepth(levels: Levels, visible: ReadonlySet<Address>): number {
  let deepest = 0;
  for (const address of visible) deepest = Math.max(deepest, levels.level.get(address) ?? 0);
  return Math.max(1, deepest - levels.first + 1);
}

/** Shows `depth` levels from the first level that draws a want, and forgets single openings. */
export function setDepth(levels: Levels, depth: number): DepthState {
  return { depth: Math.min(maxDepth(levels), Math.max(1, Math.round(depth))), opened: [], closed: [] };
}

/** Opens or closes elements one by one, keeping `opened` and `closed` to what differs from the depth. */
function withOpen(levels: Levels, state: DepthState, addresses: readonly Address[], open: boolean): DepthState {
  const depth = chosenDepth(levels, state);
  const opened = new Set(state.opened);
  const closed = new Set(state.closed);
  for (const address of addresses) {
    const byDepth = (levels.level.get(address) ?? 0) < levels.first + depth - 1;
    opened.delete(address);
    closed.delete(address);
    if (open && !byDepth) opened.add(address);
    if (!open && byDepth) closed.add(address);
  }
  return { depth: state.depth === null && opened.size === 0 && closed.size === 0 ? null : depth, opened: [...opened].sort(), closed: [...closed].sort() };
}

/** Shows the next level of every visible element that holds hidden elements. */
export function expandLevel(levels: Levels, state: DepthState): DepthState {
  if (state.opened.length === 0 && state.closed.length === 0) return setDepth(levels, chosenDepth(levels, state) + 1);
  const visible = visibleSet(levels, state);
  const holders = [...visible].filter((address) => (levels.children.get(address) ?? []).some((child) => !visible.has(child)));
  return withOpen(levels, state, holders, true);
}

/** Hides the deepest visible level. The first level that draws a want always stays. */
export function collapseLevel(levels: Levels, state: DepthState): DepthState {
  if (state.opened.length === 0 && state.closed.length === 0) return setDepth(levels, chosenDepth(levels, state) - 1);
  const visible = visibleSet(levels, state);
  const deepest = shownDepth(levels, visible) + levels.first - 1;
  if (deepest <= levels.first) return state;
  const holders = [...visible].filter((address) => levels.level.get(address) === deepest - 1 && (levels.children.get(address) ?? []).length > 0);
  return withOpen(levels, state, holders, false);
}

/** Opens an element whose next level is hidden, or closes one whose next level shows. */
export function toggleElement(levels: Levels, state: DepthState, address: Address): DepthState {
  const held = levels.children.get(address) ?? [];
  const visible = visibleSet(levels, state);
  if (held.length === 0 || !visible.has(address)) return state;
  return withOpen(levels, state, [address], held.some((child) => !visible.has(child)));
}

function same(a: DepthState, b: DepthState): boolean {
  return a.depth === b.depth && a.opened.join("\n") === b.opened.join("\n") && a.closed.join("\n") === b.closed.join("\n");
}

/**
 * Applies one depth action to a project's depth record. Every action that alters the state puts
 * the earlier state on the undo list; undo takes the last one back. An action that alters nothing
 * leaves the record, and the undo list, as they are.
 */
export function applyDepth(record: DepthRecord | null, action: DepthAction): DepthRecord {
  const base = record ?? { now: initialDepth(), undo: [] };
  if (action.type === "depth-undo") {
    const last = base.undo[base.undo.length - 1];
    return last === undefined ? base : { now: last, undo: base.undo.slice(0, -1) };
  }
  const { levels } = action;
  let next: DepthState;
  switch (action.type) {
    case "depth-collapse-all": next = setDepth(levels, 1); break;
    case "depth-expand-all": next = setDepth(levels, maxDepth(levels)); break;
    case "depth-set": next = setDepth(levels, action.depth); break;
    case "depth-expand-level": next = expandLevel(levels, base.now); break;
    case "depth-collapse-level": next = collapseLevel(levels, base.now); break;
    case "depth-toggle": next = toggleElement(levels, base.now, action.address); break;
  }
  // The same elements on screen is no change, so undo never restores a state that looks the same.
  const before = visibleSet(levels, base.now);
  const after = visibleSet(levels, next);
  if (same(base.now, next) || (before.size === after.size && [...before].every((address) => after.has(address)))) return base;
  return { now: next, undo: [...base.undo, base.now].slice(-UNDO_LIMIT) };
}
