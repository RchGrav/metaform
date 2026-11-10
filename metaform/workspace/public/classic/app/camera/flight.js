/* From the earlier page's camera/flight.js, which flew the 3D map's camera: the three things the 2D map's camera
 * takes from it. */
import '/classic/app/flow/flow.js';  // the part before runs first, so the parts run in the page's order

/* The 2D map's framing, VIEW-041: `free`, the view held where the person left it by the wheel or a drag. `svg` is the
 * drawing the framing is for and `base` whether it is the map's own, `drawing2d`. `labels` holds each drawing's own
 * label size. */
export const MODE = {free: false, svg: null, base: false, note: 0, page: null, labels: new WeakMap()};
export const MARGIN = 40;  // the most screen pixels shown beyond the map's edge where it runs past the pane, VIEW-041
/* A cubic from `from`, leaving at `rate` a second, to rest at `to` after `length` seconds: its value and rate at `s`,
 * the share of the time gone. From rest it eases in and out. */
export function hermite(from, to, rate, length, s) {
  const s2 = s * s, s3 = s2 * s;
  return [(2 * s3 - 3 * s2 + 1) * from + (s3 - 2 * s2 + s) * rate * length + (3 * s2 - 2 * s3) * to,
    ((6 * s2 - 6 * s) * from + (3 * s2 - 4 * s + 1) * rate * length + (6 * s - 6 * s2) * to) / length];
}
