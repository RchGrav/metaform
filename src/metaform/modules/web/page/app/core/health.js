/* The server's health, VIEW-002: one status, said in one banner, `server`. Nothing asks it on a clock: /api/health is
 * asked once each time something says the server may be gone or slow, the live stream's error, a read that failed, ran
 * out of time or is still waiting at its SLOW deadline, core/reads.js, and once each time something says it may be
 * well again, the stream's open and a read answered while the banner shows. A server that stops answering is said at
 * once, with the reason it last gave and what is being done about it, its watchdog's restart; a read it is slow on is
 * said with what the read waits on; and the moment it answers again the banner says it is back, and what restarted
 * it. */
import '/page/app/core/errors.js';  // the part before runs first, so the parts run in the page's order
import {banner, unbanner, bannered} from '/page/app/core/banner.js';

const ASK = 3000;  // ms one ask waits for its answer
export const SLOW = 3000;  // ms a read waits before the banner asks why, the server's own SLOW, server.py
const BACK = 8000;  // ms the banner says the server is back
const KEY = 'server';
/* The last answer, when it came, since when there has been none (null while it answers), whether an ask is out, the
 * tone the banner shows now, and when the server ends a read that is slow, so its watchdog starts it again. */
const H = {last: null, heard: Date.now(), since: null, asking: false, tone: null, restartAt: null};
const clock = when => new Date(when).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit', second: '2-digit'});

/* Ask now, once: whenever a read of the page failed, ran out of time or is slow, and on the stream's error. */
export async function askHealth() {
  if (H.asking) return;
  H.asking = true;
  try {
    const response = await fetch('/api/health', {cache: 'no-store', headers: {Accept: 'application/json'},
      signal: AbortSignal.timeout(ASK)});
    answered(await response.json());
  } catch {
    unanswered();
  } finally {
    H.asking = false;
  }
}
/* Something says the server may be well: the stream opened, or a read answered. Asked only when nothing has been
 * heard yet, for whether a watchdog keeps it, or while the banner says it is gone or slow. */
export function healthMayBeBack() {
  if (H.last === null || H.since !== null || H.tone === 'warn' || H.tone === 'error') askHealth();
}

function say(tone, spec) {
  H.tone = tone;
  banner(KEY, {tone, ...spec, onClose: () => { H.tone = null; }});
}

function answered(body) {
  const before = H.last, was = H.since;
  H.last = body;
  H.heard = Date.now();
  H.since = null;
  H.restartAt = null;
  const watched = body.supervised;
  if (body.stuck) {
    const slow = body.slow || body.slowest || {};
    return say('error', {title: "Metaform's server is stuck", closable: false, detail: slow.route,
      text: `It is ${slow.said}.${watched ? ' Restarting it now…' : ''}`,
      next: watched ? null : 'Restart it: metaform web stop, then metaform web start, in a terminal.'});
  }
  const restarted = before && before.pid !== body.pid;
  if (was !== null || restarted) {
    const cause = restarted && body.restarted?.cause;
    return say('ok', {title: "Metaform's server is back", ms: BACK,
      text: cause ? `It was restarted at ${clock(body.restarted.at)} because ${cause}.`
        : `It answered again at ${clock(H.heard)}.`});
  }
  if (body.slow) {  // a read still waiting at stuck_after ends the server, and its watchdog starts it again
    const left = Math.max(0, (body.stuck_after - body.slow.seconds) * 1000);
    H.restartAt = watched ? H.heard + left : null;
    return say('warn', {title: "Metaform's server is slow to answer", closable: false, detail: body.slow.route,
      text: `It is ${body.slow.said}.${watched
        ? ` If that read is still waiting at ${clock(H.heard + left)}, its watchdog restarts it.` : ''}`});
  }
  if (bannered(KEY) && H.tone !== 'ok') unbanner(KEY);
  if (H.tone !== 'ok') H.tone = null;
}

function unanswered() {
  H.since ??= H.heard;
  const last = H.last;
  const said = last?.slow?.said || (last?.slowest?.read ? last.slowest.said : null);
  // its slow read reached the time the server ends it, or it said it was stuck: the silence is the restart
  const restarting = last?.stuck || (H.restartAt !== null && Date.now() >= H.restartAt);
  const doing = !last?.supervised ? null : restarting ? 'Restarting it now…'
    : 'Its watchdog starts it again as soon as it ends.';
  say('error', {title: `Metaform's server has not answered since ${clock(H.since)}`, closable: false,
    text: [said ? `It last said it was ${said}.` : null, doing].filter(Boolean).join(' ') || null,
    next: last?.supervised ? null : 'Start it again: metaform web start, in a terminal.'});
}
