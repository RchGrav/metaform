/* The server's health, VIEW-002: one status, fed by a light heartbeat of /api/health every BEAT and by every read
 * that fails or runs out of time, said in one banner, `server`. A server that stops answering is said at once, with the
 * reason it last gave and what is being done about it, its watchdog's restart; a read it is slow on is said with what
 * the read waits on; and the moment it answers again the banner says it is back, and what restarted it. */
import '/page/app/core/errors.js';  // the part before runs first, so the parts run in the page's order
import {banner, unbanner, bannered} from '/page/app/core/banner.js';

const BEAT = 2000;  // ms between two asks
const ASK = 3000;  // ms one ask waits for its answer
const SILENT = 20000;  // ms with no healthy answer before the watchdog starts the server again, watchdog.py
const BACK = 8000;  // ms the banner says the server is back
const KEY = 'server';
/* The last answer, when it came, since when there has been none (null while it answers), whether an ask is out, the
 * next ask's timer, the tone the banner shows now, and when the watchdog restarts a server whose read is slow. */
const H = {last: null, heard: Date.now(), since: null, asking: false, timer: null, tone: null, restartAt: null};
const clock = when => new Date(when).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit', second: '2-digit'});

/* Ask now: on the beat, and whenever a read of the page failed or ran out of time, core/reads.js. */
export async function askHealth() {
  if (H.asking) return;
  H.asking = true;
  clearTimeout(H.timer);
  try {
    const response = await fetch('/api/health', {cache: 'no-store', headers: {Accept: 'application/json'},
      signal: AbortSignal.timeout(ASK)});
    answered(await response.json());
  } catch {
    unanswered();
  } finally {
    H.asking = false;
    H.timer = setTimeout(askHealth, BEAT);
  }
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
  if (body.slow) {  // a read still waiting at stuck_after has the watchdog restart the server: said before it comes
    const left = Math.max(0, (body.stuck_after - body.slow.seconds) * 1000);
    H.restartAt = watched ? H.heard + left : null;
    return say('warn', {title: "Metaform's server is slow to answer", closable: false, detail: body.slow.route,
      text: `It is ${body.slow.said}.${watched
        ? ` If that read is still waiting at ${clock(H.heard + left)}, its watchdog restarts it.` : ''}`});
  }
  if (bannered(KEY) && H.tone !== 'ok') unbanner(KEY);
}

function unanswered() {
  H.since ??= H.heard;
  const last = H.last;
  const said = last?.slow?.said || (last?.slowest?.read ? last.slowest.said : null);
  const waited = Date.now() - H.since;
  // its slow read reached the time the watchdog restarts it, or it said it was stuck: the silence is the restart
  const restarting = last?.stuck || (H.restartAt !== null && Date.now() >= H.restartAt);
  const doing = !last?.supervised ? null : !restarting && waited < SILENT
    ? `Its watchdog starts it again at ${clock(H.since + SILENT)} if it has not answered by then.`
    : 'Restarting it now…';
  say('error', {title: `Metaform's server has not answered since ${clock(H.since)}`, closable: false,
    text: [said ? `It last said it was ${said}.` : null, doing].filter(Boolean).join(' ') || null,
    next: last?.supervised ? null : 'Start it again: metaform web start, in a terminal.'});
}

askHealth();
