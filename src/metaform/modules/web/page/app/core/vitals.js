/* The page's own vitals, read with `metaform web viewing` as `vitals`, so a slow page can be judged from the page the
 * person has open rather than from another one (2026-10-20: a 6 s stall on the board's picker that no headless page
 * showed). Frame times come from one requestAnimationFrame tick writing into a typed ring, no allocation per frame;
 * long tasks come from a PerformanceObserver, which fires only when one happened. Nothing here polls. */
const RING = 240;  // frames kept, about four seconds at 60 a second
const F = {at: new Float32Array(RING), ms: new Float32Array(RING), n: 0, last: 0, loaded: performance.now()};
const L = {at: new Float32Array(64), ms: new Float32Array(64), n: 0};  // the last long tasks, start and length
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
const SORT = new Float32Array(RING);
const fixed = value => Math.round(value * 10) / 10;
/* Frame times over the ring: median, 95th percentile and the longest, with how many frames took half a second or
 * more, `stalls`; the long tasks of the last minute, their count, their longest and their total; the JS heap when the
 * browser tells it; the DOM's size; and how long the page has been loaded. */
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
  const memory = performance.memory;
  return {
    frames: kept ? {median_ms: fixed(sorted[kept >> 1]), p95_ms: fixed(sorted[Math.floor(kept * 0.95)]),
      max_ms: fixed(sorted[kept - 1]), stalls, span_s: fixed((now - F.at[(F.n - kept) % RING]) / 1000)} : null,
    long_tasks_last_minute: {count: tasks, longest_ms: fixed(longest), total_ms: fixed(total)},
    heap_mb: memory ? Math.round(memory.usedJSHeapSize / 1048576) : null,
    dom_nodes: document.getElementsByTagName('*').length,
    loaded_s_ago: Math.round((now - F.loaded) / 1000),
  };
}
