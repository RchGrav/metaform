// The Activity panel: what has happened to the map while the person watches, newest first.
// `Activity` holds the panel's own state (pause, filters, the open item, the scroll position).
// `ActivityContent` draws one state and holds none, so each state can be rendered on its own.
// An item that arrives never moves what the person reads, and never changes the selection.

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import { activity as words, statusMarks, statusWords, typeWords } from "../activity/strings";
import { ACTIVITY_TYPES, after, filterItems, hold, isSimulated } from "../activity/stream";
import type { ActivityItem, ActivityType, Pause } from "../activity/stream";
import "../activity/activity.css";

export type { ActivityItem } from "../activity/stream";

/** Whether items can arrive, and from where: the server, sample data, or nowhere. */
export type ActivityConnection = "connected" | "simulated" | "not-connected";

/** The props of `Activity`. */
export interface ActivityProps {
  /** The items as they arrive, newest last. */
  items: ActivityItem[];
  /** Whether the page follows a server, shows sample data, or has lost the server. */
  connection: ActivityConnection;
  /** The address of the selected element, or null when nothing is selected. */
  selected: string | null;
  /** Called with the address of the element an item affects when the user chooses the item. */
  onSelect: (address: string) => void;
  /** Called when the user chooses "Back to where I was". The caller restores the earlier selection. */
  onReturn: () => void;
}

/** The props of `ActivityContent`: one state of the panel, and what to call when the user acts. */
export interface ActivityContentProps {
  /** The items to list, newest first, after the pause and the filters. */
  listed: ActivityItem[];
  /** How many items the filters hide. */
  hidden: number;
  connection: ActivityConnection;
  paused: boolean;
  /** How many items arrived during the pause and are not listed. */
  waiting: number;
  /** The type the list is limited to, or null for every type. */
  type: ActivityType | null;
  /** True when the list is limited to the items that affect the selected element. */
  onlySelected: boolean;
  selected: string | null;
  /** The id of the item whose details show, or null. */
  openId: string | null;
  /** True when the user chose an item that selected an element, and has not gone back. */
  canReturn: boolean;
  /** How many items were added above while the user had scrolled away from the top. */
  newAbove: number;
  onPause: (paused: boolean) => void;
  onType: (type: ActivityType | null) => void;
  onOnlySelected: (on: boolean) => void;
  onChoose: (item: ActivityItem) => void;
  onReturn: () => void;
  onTop: () => void;
  onScroll?: () => void;
  scroller?: RefObject<HTMLDivElement>;
}

const clock = (time: Date) => time.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

function Details({ item, canReturn, onReturn }: { item: ActivityItem; canReturn: boolean; onReturn: () => void }) {
  const changes = item.details?.changes ?? [];
  const value = (text: string | null) => (text === null ? <em>{words.absent}</em> : text);
  return (
    <div className="act-details" id={`act-details-${item.id}`} role="region" aria-label={words.detailsOf(item.summary)}>
      <dl className="act-facts">
        <div><dt>{words.time}</dt><dd>{item.time.toLocaleString()}</dd></div>
        <div><dt>{words.status}</dt><dd>{statusWords[item.status]}</dd></div>
        <div><dt>{words.scope}</dt><dd>{item.scope ?? words.scopeProject}</dd></div>
        <div><dt>{words.element}</dt><dd>{item.element ?? words.noElement}</dd></div>
      </dl>
      {item.details?.text !== undefined && <p className="act-note">{item.details.text}</p>}
      {changes.length > 0 && (
        <table className="act-changes">
          <thead>
            <tr><th scope="col">{words.what}</th><th scope="col">{words.before}</th><th scope="col">{words.after}</th></tr>
          </thead>
          <tbody>
            {changes.map((change) => (
              <tr key={change.what}>
                <th scope="row">{change.what}</th>
                <td>{value(change.before)}</td>
                <td>{value(change.after)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {canReturn && (
        <button type="button" className="act-button" title={words.backHint} onClick={onReturn}>
          {words.back}
        </button>
      )}
    </div>
  );
}

function Item(props: { item: ActivityItem; open: boolean; current: boolean; canReturn: boolean; onChoose: (item: ActivityItem) => void; onReturn: () => void }) {
  const { item, open } = props;
  return (
    <li className="act-item">
      <button
        type="button"
        className="act-row"
        aria-expanded={open}
        aria-controls={open ? `act-details-${item.id}` : undefined}
        aria-current={props.current ? "true" : undefined}
        onClick={() => props.onChoose(item)}
      >
        <span className="act-item-head">
          <time dateTime={item.time.toISOString()}>{clock(item.time)}</time>
          <span className="act-type">{typeWords[item.type]}</span>
          <span className="act-status">
            <span className="act-mark" aria-hidden="true">{statusMarks[item.status]}</span>
            {statusWords[item.status]}
          </span>
          {isSimulated(item) && <span className="act-simulated" title={words.simulatedHint}>{words.simulatedBadge}</span>}
        </span>
        <span className="act-row-main">{item.summary}</span>
        <span className="act-row-address">{item.scope ?? words.scopeProject}</span>
      </button>
      {open && <Details item={item} canReturn={props.canReturn} onReturn={props.onReturn} />}
    </li>
  );
}

/**
 * One state of the Activity panel: the state of the connection and of the pause in words, the
 * controls, and the list. It holds no state. `Activity` gives it the state and the callbacks.
 */
export function ActivityContent(props: ActivityContentProps) {
  const { listed, connection, paused } = props;
  const emptyWords =
    props.hidden > 0 ? words.noMatch(props.hidden) : paused ? words.emptyPaused : connection === "not-connected" ? words.emptyNotConnected : words.empty;
  const stateWords = connection === "connected" ? words.connected : connection === "simulated" ? words.simulated : words.notConnected;
  return (
    <section className="act-panel act-activity" aria-label={words.label}>
      <div role="status" className="act-states">
        <p className={`act-state act-state-${connection}`}>
          <span className="act-mark" aria-hidden="true">{words.connectionMarks[connection]}</span>
          {stateWords}
        </p>
        {paused && (
          <p className="act-state act-state-paused">
            <span className="act-mark" aria-hidden="true">‖</span>
            {words.paused(props.waiting)}
          </p>
        )}
      </div>
      <div className="act-filters">
        <button type="button" className="act-chip" aria-pressed={paused} title={words.pauseHint} onClick={() => props.onPause(!paused)}>
          {paused ? words.resume : words.pause}
        </button>
        <label className="act-field">
          {words.typeLabel}
          <select value={props.type ?? ""} onChange={(event) => props.onType(event.target.value === "" ? null : (event.target.value as ActivityType))}>
            <option value="">{words.allTypes}</option>
            {ACTIVITY_TYPES.map((type) => (
              <option key={type} value={type}>{typeWords[type]}</option>
            ))}
          </select>
        </label>
        <label className="act-field" title={props.selected === null ? words.noSelection : undefined}>
          <input
            type="checkbox"
            checked={props.onlySelected}
            disabled={props.selected === null && !props.onlySelected}
            onChange={(event) => props.onOnlySelected(event.target.checked)}
          />
          {words.onlySelected}
        </label>
      </div>
      <div className="act-scroller" ref={props.scroller} onScroll={props.onScroll}>
        {props.newAbove > 0 && (
          <button type="button" className="act-new" onClick={props.onTop}>
            <span className="act-mark" aria-hidden="true">↑</span>
            {words.newAbove(props.newAbove)}
          </button>
        )}
        {listed.length === 0 ? (
          <p className="act-empty">{emptyWords}</p>
        ) : (
          <ol className="act-rows" aria-label={words.listLabel}>
            {listed.map((item) => (
              <Item
                key={item.id}
                item={item}
                open={item.id === props.openId}
                current={props.selected !== null && item.element === props.selected}
                canReturn={props.canReturn}
                onChoose={props.onChoose}
                onReturn={props.onReturn}
              />
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}

/** The distance from the top, in pixels, within which the list counts as at the top. */
const AT_TOP = 4;

// The scroll position must move before the browser paints. With no browser, as in a test that
// renders to HTML, there is no scroll position, and a layout effect only gives a warning.
const useBeforePaint = typeof window === "undefined" ? useEffect : useLayoutEffect;

/**
 * The Activity panel. It lists the items newest first, with filters by type and by the selected
 * element. While the pause is on, items that arrive are held and counted, and listed together
 * when the pause ends. While the user has scrolled away from the top, new items are added above
 * without moving the list, and a line at the top says how many. Choosing an item shows its
 * details and calls `onSelect` with the element it affects; "Back to where I was" calls `onReturn`.
 */
export function Activity({ items, connection, selected, onSelect, onReturn }: ActivityProps) {
  const [pause, setPause] = useState<Pause | null>(null);
  const [type, setType] = useState<ActivityType | null>(null);
  const [onlySelected, setOnlySelected] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const [canReturn, setCanReturn] = useState(false);
  // While the user is away from the top: the id of the newest item that was listed when they left it.
  const [away, setAway] = useState<{ fromId: string | null } | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const height = useRef(0);
  const newest = useRef<string | null>(null);

  const held = hold(items, pause);
  // With the filter on and nothing selected, no item passes: no element has an empty address.
  const filter = { type, element: onlySelected ? (selected ?? "") : null };
  const passing = filterItems(held.listed, filter);
  const newestId = held.listed[held.listed.length - 1]?.id ?? null;
  const newAbove = away === null ? 0 : filterItems(after(held.listed, away.fromId), filter).length;

  // When items were added while the user is away from the top, the list grew above what they
  // read. Move the scroll position by the growth, so that the same rows stay in view.
  useBeforePaint(() => {
    const element = scroller.current;
    if (element === null) return;
    if (element.scrollTop > AT_TOP && newestId !== newest.current) element.scrollTop += element.scrollHeight - height.current;
    height.current = element.scrollHeight;
    newest.current = newestId;
  });

  const onScroll = () => {
    const element = scroller.current;
    if (element === null) return;
    const isAway = element.scrollTop > AT_TOP;
    if (isAway && away === null) setAway({ fromId: newestId });
    if (!isAway && away !== null) setAway(null);
  };

  const onChoose = (item: ActivityItem) => {
    if (item.id === openId) {
      setOpenId(null);
      return;
    }
    setOpenId(item.id);
    if (item.element !== null) {
      onSelect(item.element);
      setCanReturn(true);
    }
  };

  return (
    <ActivityContent
      listed={[...passing].reverse()}
      hidden={held.listed.length - passing.length}
      connection={connection}
      paused={pause !== null}
      waiting={held.waiting}
      type={type}
      onlySelected={onlySelected}
      selected={selected}
      openId={openId}
      canReturn={canReturn}
      newAbove={newAbove}
      onPause={(on) => setPause(on ? { lastId: items[items.length - 1]?.id ?? null } : null)}
      onType={setType}
      onOnlySelected={setOnlySelected}
      onChoose={onChoose}
      onReturn={() => {
        setCanReturn(false);
        onReturn();
      }}
      onTop={() => {
        if (scroller.current !== null) scroller.current.scrollTop = 0;
        setAway(null);
      }}
      onScroll={onScroll}
      scroller={scroller}
    />
  );
}
