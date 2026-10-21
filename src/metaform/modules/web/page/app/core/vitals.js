/* The page's own vitals, read with `metaform web viewing` as `vitals`, so a slow page can be judged from the page the
 * person has open rather than from another one (2026-10-20: a 6 s stall on the board's picker that no headless page
 * showed). Frame times come from one requestAnimationFrame tick writing into a typed ring, no allocation per frame;
 * long tasks and the person's own presses come from PerformanceObservers, which fire only when one happened. Nothing
 * here polls. */
const RING = 240;  // frames kept, about four seconds at 60 a second
const F = {at: new Float32Array(RING), ms: new Float32Array(RING), n: 0, last: 0, loaded: performance.now()};
const L = {at: new Float32Array(64), ms: new Float32Array(64), n: 0};  // the last long tasks, start and length
/* The person's presses, by the browser's event timing: for each pointer or key press, how long the main thread kept it
 * waiting before its handlers ran, `delay`, how long the handlers ran, how long until the paint after it, `ms`, and
 * what it was on. The browser reports a press once its paint took INPUT_FROM or longer, the least it offers, so nearly
 * every press is counted; the worst since the page loaded is kept apart from the ring of the last sixty-four. This is
 * the delay the person feels, measured on their own page: a drop-down opens when the main thread has handled the press. */
const INPUT_FROM = 16;
const PRESSES = new Set(['pointerdown', 'keydown']);  // one entry per press; its mousedown, up and click repeat it
const I = {at: new Float32Array(64), delay: new Float32Array(64), handlers: new Float32Array(64),
  ms: new Float32Array(64), on: new Array(64).fill(''), n: 0, count: 0, worstMs: 0, worstDelay: 0, worstOn: ''};
function tick(now) {
  if (F.last) {
    const slot = F.n % RING;
    F.at[slot] = now;
    F.ms[slot] = now - F.last;
    F.n++;
  }
  F.last = now;
  requestAnimationFrame(tick);
}
requestAnimationFrame(tick);
try {
  new PerformanceObserver(list => {
    for (const entry of list.getEntries()) {
      const slot = L.n % 64;
      L.at[slot] = entry.startTime;
      L.ms[slot] = entry.duration;
      L.n++;
    }
  }).observe({entryTypes: ['longtask']});
} catch (error) { /* a browser without long task timing says none */ }
/* What a press was on, for the reader: the control's label, id or title, else its first class or its tag. */
function labelOf(target) {
  if (!target || typeof target.getAttribute !== 'function') return '';
  return target.getAttribute('aria-label') || target.id || target.getAttribute('title')
    || (typeof target.className === 'string' ? target.className.split(' ')[0] : '') || target.tagName.toLowerCase();
}
try {
  new PerformanceObserver(list => {
    for (const entry of list.getEntries()) {
      if (!PRESSES.has(entry.name)) continue;
      const slot = I.n % 64, ms = entry.duration, delay = entry.processingStart - entry.startTime;
      I.at[slot] = entry.startTime;
      I.delay[slot] = delay;
      I.handlers[slot] = entry.processingEnd - entry.processingStart;
      I.ms[slot] = ms;
      I.on[slot] = labelOf(entry.target);
      I.n++;
      I.count++;
      if (delay > I.worstDelay) I.worstDelay = delay;
      if (ms > I.worstMs) { I.worstMs = ms; I.worstOn = I.on[slot]; }
    }
  }).observe({type: 'event', buffered: true, durationThreshold: INPUT_FROM});
} catch (error) { /* a browser without event timing says no presses */ }
const SORT = new Float32Array(RING);
const fixed = value => Math.round(value * 10) / 10;
/* Frame times over the ring: median, 95th percentile and the longest, with how many frames took half a second or
 * more, `stalls`; the long tasks of the last minute, their count, their longest and their total; the presses of the
 * last minute, how many, how many waited 100 ms or more for their paint, `slow`, the longest wait for the main thread
 * and the longest to paint with what it was on, and the same worst since the page loaded; whether the page is in view
 * (out of view, no frame is drawn, so `frames` is null); the JS heap when the browser tells it; the DOM's size; and
 * how long the page has been loaded. */
export function pageVitals() {
  const now = performance.now(), kept = Math.min(F.n, RING);
  let stalls = 0;
  for (let i = 0; i < kept; i++) {
    SORT[i] = F.ms[i];
    if (F.ms[i] >= 500) stalls++;
  }
  const sorted = SORT.subarray(0, kept).sort();
  let tasks = 0, longest = 0, total = 0;
  const seen = Math.min(L.n, 64);
  for (let i = 0; i < seen; i++) {
    if (now - L.at[i] > 60000) continue;
    tasks++;
    total += L.ms[i];
    if (L.ms[i] > longest) longest = L.ms[i];
  }
  let presses = 0, slow = 0, worstMs = 0, worstDelay = 0, worstOn = '';
  const pressed = Math.min(I.n, 64);
  for (let i = 0; i < pressed; i++) {
    if (now - I.at[i] > 60000) continue;
    presses++;
    if (I.ms[i] >= 100) slow++;
    if (I.delay[i] > worstDelay) worstDelay = I.delay[i];
    if (I.ms[i] > worstMs) { worstMs = I.ms[i]; worstOn = I.on[i]; }
  }
  const memory = performance.memory;
  return {
    frames: kept ? {median_ms: fixed(sorted[kept >> 1]), p95_ms: fixed(sorted[Math.floor(kept * 0.95)]),
      max_ms: fixed(sorted[kept - 1]), stalls, span_s: fixed((now - F.at[(F.n - kept) % RING]) / 1000)} : null,
    long_tasks_last_minute: {count: tasks, longest_ms: fixed(longest), total_ms: fixed(total)},
    presses_last_minute: {count: presses, slow, worst_delay_ms: fixed(worstDelay), worst_ms: fixed(worstMs),
      worst_on: worstOn},
    presses_since_load: {count: I.count, worst_delay_ms: fixed(I.worstDelay), worst_ms: fixed(I.worstMs),
      worst_on: I.worstOn},
    visible: !document.hidden,
    heap_mb: memory ? Math.round(memory.usedJSHeapSize / 1048576) : null,
    dom_nodes: document.getElementsByTagName('*').length,
    loaded_s_ago: Math.round((now - F.loaded) / 1000),
  };
}
