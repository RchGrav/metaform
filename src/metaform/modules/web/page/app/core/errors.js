/* The page's one error surface: a read of the server that failed, an exception nothing caught and a promise refused
 * with no one to hear it are each said on screen, in a banner: what happened in plain words, the next step the server
 * sent, and Report a problem, the report `metaform report` makes. The page never stays blank without saying why. Each
 * is also sent to the server, where autoticket files it as a ticket to fix. */
import '/page/app/core/banner.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/page/app/core/dom.js';
import {banner, unbanner, bannered} from '/page/app/core/banner.js';

/* What each read is, said to a person; a read not named here is said by its name. */
const READS = {projects: 'The project list', bases: "The project's bases", graph: 'The map', sequence: 'The map',
  layers: 'The layers', work: 'The tickets', node: 'The selected part', 'dispatch-sessions': 'The agents',
  'dispatch-claims': "The agents' claims", 'dispatch-autostart': 'Full Auto', 'dispatch-agents': 'The agent list',
  notices: "The modules' notices"};
const MAP_READS = new Set(['projects', 'bases', 'graph', 'sequence']);
const FAILING = new Set();  // the reads whose last answer was a failure
/* Whether the map could not be read, so nothing says it is empty when it was never read. */
export const mapUnread = () => [...MAP_READS].some(name => FAILING.has(name));
const readWords = name => READS[name] || (name.startsWith('dispatch-') ? 'The agents' : `The ${name} read`);
/* Each problem said, by its banner's key: how many times it came, since when, and whether the person closed it on the
 * words it has now, so the same words do not come back after a close but new ones do. */
const SEEN = new Map();
const REPORT = {open: null};
/* The window that makes a problem report registers itself here, `header/admin.js`, so a banner can open it with the
 * problem's words filled in. */
export const reportWith = open => { REPORT.open = open; };
const clock = when => when.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});

function say(key, {title, text, next = null, where = null, reload = false}) {
  const now = new Date();
  const seen = SEEN.get(key);
  const same = seen && seen.text === text;
  const entry = {text, first: same ? seen.first : now, count: same ? seen.count + 1 : 1,
    closed: same && seen.closed};
  SEEN.set(key, entry);
  if (entry.closed) return;
  const times = entry.count > 1 ? `${entry.count} times since ${clock(entry.first)}` : `At ${clock(entry.first)}`;
  const words = `${title}: ${text}`;
  const actions = [];
  if (REPORT.open) actions.push({label: 'Report a problem', primary: true, run: () => REPORT.open(words)});
  if (reload) actions.push({label: 'Reload the page', run: () => location.reload()});
  banner(key, {tone: 'error', title, text, detail: [times, where].filter(Boolean).join(' · '),
    // without the report window, which is a later part of the page, the command makes the same report
    next: next || (REPORT.open ? null : `metaform report "${words.slice(0, 120).replace(/"/g, "'")}"`),
    actions, onClose: by => { if (by === 'person') entry.closed = true; }});
}

/* Every error said here goes to the server too, `/api/page-faults`, which publishes each as a fault for autoticket to
 * file: those of one second in one request, each once with how many times it came, so a burst costs one request. */
const SENDING = {project: () => null, faults: new Map(), due: false};
/* The page's project, registered by the part that holds it, `core/reads.js`, so the errors say where they happened. */
export const faultsFrom = project => { SENDING.project = project; };
function sendFault(fault) {
  const key = `${fault.read}\n${fault.message}\n${fault.where}`;
  const had = SENDING.faults.get(key);
  if (had) { had.count += 1; return; }
  SENDING.faults.set(key, {...fault, count: 1});
  if (SENDING.due) return;
  SENDING.due = true;
  setTimeout(flushFaults, 1000);  // the end of the second's batch, a deadline; nothing looks for errors on a clock
}
function flushFaults() {
  SENDING.due = false;
  const faults = [...SENDING.faults.values()];
  SENDING.faults.clear();
  const project = SENDING.project();
  if (!project || !faults.length) return;
  // a send that fails is said nowhere: the banner already says the error, and the server may be the one down;
  // `loaded`, when this page's code was loaded, tells autoticket whether a fault comes from code older than a fix
  fetch('/api/page-faults', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({project, loaded: performance.timeOrigin / 1000, faults})}).catch(() => {});
}
const unorigin = text => String(text || '').split(location.origin).join('');

/* A read of the server that failed, `read` in core/reads.js throws it with the server's {error, next}. A 500 is the
 * server's own fault, which it files itself, so only the others are sent. */
export function readFailed(error) {
  if (error?.name === 'AbortError') return;  // a read the page itself gave up, for one it needs more
  const name = error?.read || 'server';
  FAILING.add(name);
  if (error?.status !== 500) sendFault({read: name, message: error?.message || String(error), where: '', stack: ''});
  say(`error:read:${name}`, {title: `${readWords(name)} could not be read`, text: error?.message || String(error),
    next: error?.body?.next || null});
  // the object panel waits for the map with "Reading the map…"; a map that cannot be read says so there too
  const waiting = $('#p-object > p.loading');
  if (MAP_READS.has(name) && waiting) fill(waiting.parentElement, h('p', {class: 'empty'},
    'The map could not be read; the notice at the top of the page says why.'));
}
/* A read that answers again takes its problem away. */
export function readBack(name) {
  FAILING.delete(name);
  if (bannered(`error:read:${name}`)) unbanner(`error:read:${name}`);
  SEEN.delete(`error:read:${name}`);
}
/* Authentication is an action for the person, not a page fault. Use the server's recovery command to identify it. */
export function authenticationNeeded(body) {
  const match = /^metaform dispatch login ([a-z][a-z0-9_-]*)$/.exec(body?.next || '');
  if (!match) return;
  const agent = match[1];
  const text = agent === 'antigravity'
    ? 'Google Antigravity needs its own sign-in for this connection. Your agy terminal login is separate.'
    : body.error || 'Your agent needs a sign-in.';
  banner(`authentication:${agent}`, {tone: 'warn', title: 'Agent sign-in required',
    text: `${text} Open a terminal in this project's folder, then run this command to choose a sign-in method. `
      + 'Complete sign-in, then retry.',
    next: h('code', {}, body.next)});
}
export const authenticationRestored = agent => unbanner(`authentication:${agent}`);
/* What a module says needs the person, its status hook's notice, read from /api/notices each time the page's stream
 * opens: one warning a module, its words split at " Next: " into what is wrong and the step that fixes it, and titled by
 * what comes before the first ": ", such as Phone. A notice the person closed does not come back on the same words; one
 * a module no longer gives is taken away. */
const NOTICES = new Map();  // module -> {text, closed}
export function moduleNotices(list) {
  const given = new Set();
  for (const {module, notice} of list || []) {
    given.add(module);
    const had = NOTICES.get(module);
    if (had?.text === notice && had.closed) continue;
    const entry = {text: notice, closed: false};
    NOTICES.set(module, entry);
    const [head, next = null] = notice.split(' Next: ');
    const colon = head.indexOf(': ');
    const titled = colon > 0 && colon <= 40;
    banner(`notice:${module}`, {tone: 'warn', title: titled ? head.slice(0, colon) : module,
      text: titled ? head.slice(colon + 2) : head, next,
      onClose: by => { if (by === 'person') entry.closed = true; }});
  }
  for (const module of [...NOTICES.keys()]) {
    if (given.has(module)) continue;
    NOTICES.delete(module);
    if (bannered(`notice:${module}`)) unbanner(`notice:${module}`);
  }
}
/* An exception or a refusal no part of the page caught. */
export function pageFailed(error, where = null) {
  if (error?.read) return readFailed(error);
  if (error?.name === 'AbortError') return;
  const text = error?.message || String(error ?? 'An unknown error.');
  sendFault({read: '', message: `${error?.name && error.name !== 'Error' ? `${error.name}: ` : ''}${text}`,
    where: unorigin(where), stack: unorigin(error?.stack)});
  say(`error:page:${text}`, {title: 'Part of the page failed', text, where, reload: true});
}

addEventListener('error', event => {
  const target = event.target;
  if (target && target !== window) {  // a file of the page that failed to load; a picture is not a fault
    if (target.tagName === 'SCRIPT' || target.tagName === 'LINK') {
      pageFailed(new Error(`${target.src || target.href} did not load.`));
    }
    return;
  }
  // The browser's own notice that a resize observer had more to say in one frame: not an error, it says so itself.
  if (/^ResizeObserver loop/.test(event.message || '')) return;
  pageFailed(event.error || new Error(event.message), event.filename
    ? `${event.filename.replace(location.origin, '')}:${event.lineno}` : null);
}, true);
addEventListener('unhandledrejection', event => pageFailed(event.reason));
window.METAFORM_SURFACE = true;  // theme.js says a page whose code never ran this far in words of its own
