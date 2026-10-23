/* What the mascot says, or an embodied agent through its figure, `say` in figures/cut.js, drawn by `bubbles3d` in
 * figures/bubble3d.js in the one layer of word bubbles over the maps. `el` is the box the mascot's reply field opens
 * in, figures/ask.js; `since` is when the line was said; `placeBubble` sets, each frame before the bubbles are drawn,
 * where the speaker's head is on the page (`x`, `y`), the map it is drawn in (`left` to `bottom`), whether it was
 * `found`, whether the bubble is `seen` and whether the reply field is open, `asking`. */
// `seconds`: web_bubble_seconds, auto or a number, set from the view as the page reads it
export const BUBBLE = {el: null, text: '', until: 0, click: null, seconds: 'auto', who: null, name: '', since: 0,
  found: false, seen: false, asking: false, x: 0, y: 0, left: 0, top: 0, right: 0, bottom: 0};

/* The person's wait count: vowels, y, digits 1 to 9 and pause marks, minus each listed sequence ("ai" twice)
 * and a terminal silent e. Zero becomes one. Auto visibility is 2 s plus 50 ms per wait. */
const WAITS = 'aeiouy123456789.,;:!?';
const PAIRS = ['ai', 'ee', 'ea', 'ai', 'oa', 'oi', 'oo', 'ou', 'eau', 'ueue', 'cie', 'eo'];
const count = (text, part) => text.split(part).length - 1;
export function waits(text) {
  const lower = String(text || '').toLowerCase();
  let found = 0;
  for (const one of WAITS) found += count(lower, one);
  for (const pair of PAIRS) found -= count(lower, pair);
  if (lower.length >= 3 && lower.at(-1) === 'e' && !'aeiouy'.includes(lower.at(-2))
    && 'aeiouy'.includes(lower.at(-3))) found--;
  return found === 0 ? 1 : found;
}
/* How long a word bubble stays up for `text`, in seconds, by web_bubble_seconds: auto, the default, by its waits;
 * else the seconds chosen. */
export function bubbleSeconds(text, setting) {
  const seconds = Number(setting);
  return setting === 'auto' || !(seconds > 0) ? (2000 + 50 * waits(text)) / 1000 : seconds;
}
