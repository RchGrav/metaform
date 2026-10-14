/* The chat as an MCP Apps host: each tool call's view in its frame, its messages and context, panels, the gallery
 * and a thread's rows. */
import '/page/app/session/tools.js';  // the part before runs first, so the parts run in the page's order
import {h, fill} from '/page/app/core/dom.js';
import {overlay} from '/page/app/core/overlays.js';
import {confirmAct, toast} from '/page/app/core/controls.js';
import {S, read} from '/page/app/core/reads.js';
import {VIEW} from '/page/app/views/settings.js';
import {DOCK, SEEN} from '/page/app/dock/embody.js';
import {drawHelpdesk, followLog} from '/page/app/dock/helpdesk.js';
import {linked} from '/page/app/board/refs.js';
import {movable} from '/page/app/board/history.js';
import {agentName} from '/page/app/agents/pickers.js';
import {toolRow, permissionCard, elicitationCard, noticeRow, signalWords} from '/page/app/session/tools.js';
import {messageRow, attachmentCard} from '/page/app/session/text.js';
import {posted} from '/page/app/intake/intake.js';

/* ---------- the chat as an MCP Apps host, io.modelcontextprotocol/ui (2026-01-26) ---------- A Metaform tool that
 * declares a view, `_meta.ui.resourceUri`, shows it in the thread under its call: the view's document, `GET
 * /api/mcp-app`, in a frame sandboxed to scripts alone, so its origin is opaque and it reaches nothing of the page's;
 * its content policy is the one it asks for. The page is its host over postMessage, JSON-RPC as the spec has it:
 * ui/initialize answered with what this host offers, the call's input and result sent once the view is ready, its size
 * followed, tools/call taken to the folder's MCP server as the thread's agent session (`POST /api/mcp-call`), a link
 * opened only once the person agrees. A view pops out into a panel of its own, moved and sized as the person likes, and
 * comes back; /apps, or the head's menu, lists every view the enabled modules offer, each opened in a panel. The views
 * and the tools that show them are read from the server, `GET /api/mcp-apps`. */
const APPS = {project: null, at: 0, tools: {}, views: [], reading: null, panels: 0, gallery: false};
const APPFRAMES = new Map();  // key -> {key, app, scope, frame, holder, panel, mode, ready, fed, note}
const APP_PROTOCOL = '2026-01-26';
// What a view asked the agent be told, ui/update-model-context, by the thread's work and session: the last one of each
// view, sent with the person's next message to that session and never on its own, since it starts no turn.
const MODEL_CONTEXT = new Map();  // `${work}:${session}` -> Map(view name -> text)
const ANSWERS = new Map();  // the id of a request the host sent a view -> what is done with its answer
function readApps(force = false) {
  if (!S.project) return Promise.resolve(APPS);
  if (!force && APPS.project === S.project && Date.now() - APPS.at < 300000) return Promise.resolve(APPS);
  if (APPS.reading) return APPS.reading;
  const project = S.project;
  const keep = found => {
    if (S.project === project) {
      Object.assign(APPS, {project, at: Date.now(), tools: found.tools || {}, views: found.views || []});
    }
  };
  APPS.reading = read('mcp-apps')
    .then(keep)
    .catch(() => Object.assign(APPS, {project, at: Date.now(), tools: {}, views: []}))
    .then(appsRead);
  return APPS.reading;
}
function appsRead() {
  APPS.reading = null;
  if (DOCK.target || APPS.gallery) drawHelpdesk();
  return APPS;
}
/* The view a tool call shows: its tool's, when the runner kept the call's tool, `data.call`. */
function appOf(line) {
  const call = line.data?.call;
  if (!call?.tool) return null;
  if (APPS.project !== S.project) { readApps(); return null; }  // drawn again once the views are known
  const tool = APPS.tools[call.tool];
  return tool?.uri ? {uri: tool.uri, call, tool: call.tool} : null;
}
const appName = uri => APPS.views.find(one => one.uri === uri)?.name || String(uri).replace(/^ui:\/\//, '');
function appRow(key, app, scope) {
  const holder = h('div', {class: 'appholder'});
  const note = h('small', {class: 'appnote', role: 'status', hidden: true});
  const box = h('div', {class: 'mcpapp', 'data-uri': app.uri},
    h('div', {class: 'appbar'}, h('span', {class: 'name'}, appName(app.uri)),
      app.tool ? h('small', {}, app.tool) : null, h('span', {class: 'grow'}),
      h('button', {class: 'btn sm quiet', type: 'button',
        title: 'Show it in a panel of its own, moved and sized as you like', onclick: () => popApp(key)}, 'Pop out')),
    note, holder);
  const had = APPFRAMES.get(key);
  if (had?.panel) {  // shown in its panel: the thread says so, and it comes back here
    had.inline = holder;
    fill(holder, appAway(key));
  } else mountApp(key, holder, app, scope, 'inline').note = note;
  if (had?.said) appNote(APPFRAMES.get(key), had.said);
  return box;
}
/* What the host could not do for a view, or kept for the agent, said in a quiet line over it, so a view that asked for
 * something this chat does not offer is not simply left waiting. */
function appNote(entry, text) {
  if (!entry) return;
  entry.said = text;
  if (entry.note) { entry.note.textContent = text; entry.note.hidden = !text; }
}
const appAway = key => h('p', {class: 'appaway'}, 'Shown in a panel of its own. ',
  h('button', {class: 'btn sm quiet', type: 'button', onclick: () => bringBack(key)}, 'Bring it back'));
function mountApp(key, holder, app, scope, mode) {
  const entry = APPFRAMES.get(key) || {key};
  const meta = APPS.views.find(one => one.uri === app.uri)?.meta?.ui || {};
  const frame = h('iframe', {class: 'appframe', title: `${appName(app.uri)}, a view of the MCP server`,
    sandbox: 'allow-scripts', referrerpolicy: 'no-referrer',
    ...(meta.permissions?.clipboardWrite ? {allow: 'clipboard-write'} : {}),
    src: `/api/mcp-app?project=${encodeURIComponent(S.project)}&uri=${encodeURIComponent(app.uri)}`});
  Object.assign(entry, {app, scope, frame, holder, mode, ready: false, fed: {input: false, result: false}});
  APPFRAMES.set(key, entry);
  fill(holder, frame);
  // the views whose rows have gone from the thread, shown in no panel, are forgotten
  for (const [other, one] of APPFRAMES) {
    if (other !== key && !one.panel && !one.frame?.isConnected) APPFRAMES.delete(other);
  }
  return entry;
}
function appPost(entry, message) { entry.frame?.contentWindow?.postMessage({jsonrpc: '2.0', ...message}, '*'); }
/* The call's input, then its result once there is one, each sent once the view is ready, ui/notifications. */
function appFed(key, call) {
  const entry = APPFRAMES.get(key);
  if (!entry) return;
  entry.app.call = call;
  feedApp(entry);
}
function feedApp(entry) {
  const call = entry.app.call;
  if (!entry.ready || !call) return;
  if (!entry.fed.input) {
    entry.fed.input = true;
    appPost(entry, {method: 'ui/notifications/tool-input', params: {arguments: call.input || {}}});
  }
  if (call.result && !entry.fed.result) {
    entry.fed.result = true;
    appPost(entry, {method: 'ui/notifications/tool-result',
      params: {content: call.result.content || [], isError: Boolean(call.result.isError),
        ...(call.result.structuredContent ? {structuredContent: call.result.structuredContent} : {})}});
  }
}
function appContext(entry) {
  const box = (entry.panel ? entry.holder : entry.frame)?.getBoundingClientRect();
  const ground = getComputedStyle(document.body).backgroundColor.match(/\d+(\.\d+)?/g)?.map(Number) || [0, 0, 0];
  const light = (0.2126 * ground[0] + 0.7152 * ground[1] + 0.0722 * ground[2]) / 255 > 0.5;
  return {theme: light ? 'light' : 'dark', displayMode: entry.mode,
    availableDisplayModes: ['inline', 'fullscreen', 'pip'],
    containerDimensions: entry.panel ? {height: Math.round(box?.height || 400), width: Math.round(box?.width || 560)}
      : {maxHeight: 560, width: Math.round(box?.width || 400)},
    locale: navigator.language, timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone, platform: 'web',
    userAgent: 'Metaform web', deviceCapabilities: {touch: matchMedia('(pointer: coarse)').matches,
      hover: matchMedia('(hover: hover)').matches},
    ...(entry.app.call ? {toolInfo: {tool: {name: entry.app.call.tool, inputSchema: {type: 'object'}}}} : {})};
}
function fromApp(event) {
  const entry = [...APPFRAMES.values()]
    .find(one => one.frame?.contentWindow && one.frame.contentWindow === event.source);
  const message = event.data;
  if (!entry || !message || message.jsonrpc !== '2.0') return;
  if (!message.method) {  // an answer to the host's own request, such as teardown, which waits for it
    ANSWERS.get(message.id)?.();
    ANSWERS.delete(message.id);
    return;
  }
  appMessage(entry, message);
}
addEventListener('message', fromApp);
/* What this host offers a view, ui/initialize: the stable 2026-01-26 capabilities it serves (links, the server's
 * tools, logging), and the two the SDK's hosts declare beside them, `message` and `updateModelContext`, in text, which
 * the stable text describes as methods but lists no capability for. Not offered: the server's resources, a view's own
 * tools called by the host, downloads and sampling, which are the draft's; a view that asks for one is told it is not
 * offered and the chat says so over it. */
const HOST_CAPABILITIES = {openLinks: {}, serverTools: {listChanged: false}, logging: {},
  message: {text: {}}, updateModelContext: {text: {}, structuredContent: {}}};
/* What the host does for each method a view sends, given the entry, the params, and its reply and fail; a method not
 * here is refused. */
const APP_METHODS = {
  'ui/initialize': (entry, params, reply) => reply({protocolVersion: APP_PROTOCOL,
    hostInfo: {name: 'Metaform web', version: '1'}, hostCapabilities: HOST_CAPABILITIES,
    hostContext: appContext(entry)}),
  'ui/notifications/initialized': entry => { entry.ready = true; return feedApp(entry); },
  'ui/notifications/size-changed': (entry, params) => {  // inline it is as tall as it asks, within the thread's reach
    if (!entry.panel && Number(params.height) > 0) {
      entry.frame.style.height = `${Math.round(Math.min(560, Math.max(120, Number(params.height))))}px`;
      if (DOCK.pinned && entry.frame.closest('#helpdesk')) followLog();  // a thread followed stays at its end
    }
  },
  'ping': (entry, params, reply) => reply({}),
  'tools/call': callTool,
  'ui/open-link': openLink,
  'ui/message': appSays,
  'ui/update-model-context': keepContext,
  'ui/request-display-mode': (entry, params, reply) => {
    const mode = params.mode;
    if (mode === 'inline' && entry.panel) { reply({mode: 'inline'}); return bringBack(entry.key); }
    if ((mode === 'fullscreen' || mode === 'pip') && !entry.panel) { reply({mode}); return popApp(entry.key, mode); }
    return reply({mode: entry.mode});
  },
  'notifications/message': () => {},  // the view's own log
};
async function appMessage(entry, message) {
  const reply = result => message.id !== undefined && appPost(entry, {id: message.id, result});
  const fail = (code, text) => message.id !== undefined
    && appPost(entry, {id: message.id, error: {code, message: text}});
  const params = message.params || {};
  if (Object.hasOwn(APP_METHODS, message.method)) return APP_METHODS[message.method](entry, params, reply, fail);
  if (message.id !== undefined) appNote(entry, `It asked for ${message.method}, which this chat does not offer.`);
  return fail(-32601, `${message.method} is not offered by this host.`);
}
/* The text blocks of what a view sends, its other content said by its kind, which this host does not show. */
function textOf(content) {
  const blocks = Array.isArray(content) ? content : content ? [content] : [];
  return blocks.map(block => (block?.type === 'text' ? String(block.text ?? '') : `[${block?.type || 'content'}]`))
    .filter(Boolean).join('\n');
}
const threadOf = entry => (entry.scope?.work ? `${entry.scope.work}:${entry.scope.session || ''}` : null);
/* A message a view writes to the agent as the person, ui/message: sent to the thread's own session once the person
 * agrees, as the spec allows a host to ask; with no agent in the thread it is refused and said. */
async function appSays(entry, params, reply, fail) {
  const text = textOf(params.content).trim();
  if (!text) return fail(-32602, 'The message has no text.');
  if (!entry.scope?.work) {
    appNote(entry, 'It asked to send a message, but no agent is in this chat to send it to.');
    return fail(-32000, 'No agent is in this chat.');
  }
  const agent = agentName(DOCK.chat?.target === entry.scope.work ? DOCK.agent : null);
  const sure = await confirmAct({title: `Send this to ${agent}?`, verb: 'Send it', cancel: 'Do not send', danger: false,
    text: [`${appName(entry.app.uri)} asks to send this as your message:`, h('blockquote', {}, text)]});
  if (!sure) return reply({isError: true});
  const done = await posted('/api/dispatch-message', {work_id: entry.scope.work,
    ...(entry.scope.session ? {session: entry.scope.session} : {}), text: withContext(entry.scope, text)});
  if (!done.ok) {
    appNote(entry, `Its message was not sent: ${done.body?.error || 'the agent did not take it'}.`);
    return fail(-32000, done.body?.error || 'The message was not sent.');
  }
  return reply({});
}
const CONTEXT_SAID = 'What it shows goes to the agent with your next message.';
/* What a view wants the agent to know, ui/update-model-context: each view's last, kept for its thread's session and
 * sent with the person's next message there, said over the view meanwhile. */
function keepContext(entry, params, reply) {
  const thread = threadOf(entry);
  const structured = params.structuredContent === undefined ? '' : JSON.stringify(params.structuredContent);
  const text = [textOf(params.content), structured.length <= 4000 ? structured : ''].filter(Boolean).join('\n');
  if (!thread) {
    appNote(entry, 'With no agent in this chat, what it would tell an agent is kept by no one.');
    return reply({});
  }
  const kept = MODEL_CONTEXT.get(thread) || new Map();
  if (text) kept.set(appName(entry.app.uri), text); else kept.delete(appName(entry.app.uri));
  MODEL_CONTEXT.set(thread, kept);
  appNote(entry, text ? CONTEXT_SAID : '');
  return reply({});
}
/* The person's message to a thread with what its views asked the agent be told before it, each said once. */
export function withContext(scope, text) {
  const thread = scope?.work ? `${scope.work}:${scope.session || ''}` : null;
  const kept = thread && MODEL_CONTEXT.get(thread);
  if (!kept?.size) return text;
  MODEL_CONTEXT.delete(thread);
  for (const one of APPFRAMES.values()) if (threadOf(one) === thread && one.said === CONTEXT_SAID) appNote(one, '');
  return `${[...kept].map(([view, said]) => `[From the ${view}: ${said}]`).join('\n')}\n\n${text}`;
}
/* A view's tools/call, taken to the folder's MCP server as the thread's agent session. */
async function callTool(entry, params, reply, fail) {
  const done = await posted('/api/mcp-call', {tool: params.name, arguments: params.arguments || {},
    ...(entry.scope?.work ? {work_id: entry.scope.work, session: entry.scope.session || null} : {})});
  return done.ok ? reply(done.body) : fail(-32000, done.body?.error || 'The call failed.');
}
/* A link a view asks to open: a web address only, and only once the person agrees. */
async function openLink(entry, params, reply, fail) {
  const url = String(params.url || '');
  if (!/^https?:[/][/]/i.test(url)) return fail(-32602, 'Only a web address is opened.');
  const sure = await confirmAct({title: 'Open this link?', verb: 'Open it', cancel: 'Stay here', danger: false,
    text: [`${appName(entry.app.uri)} asks to open a page in a new tab:`, h('code', {class: 'url'}, url)]});
  if (sure) window.open(url, '_blank', 'noopener,noreferrer');
  return reply(sure ? {} : {isError: true});
}
/* Before a view's frame goes, it is told, ui/resource-teardown, and its answer is waited for, as the spec asks, so
 * what it keeps is kept; a view that does not answer within a moment goes all the same. */
function teardownApp(entry, reason = 'closed') {
  if (!entry.frame?.contentWindow || !entry.ready) return Promise.resolve();
  const id = `teardown-${++APPS.panels}`;
  return new Promise(done => {
    const timer = setTimeout(() => { ANSWERS.delete(id); done(); }, 600);
    ANSWERS.set(id, () => { clearTimeout(timer); done(); });
    appPost(entry, {id, method: 'ui/resource-teardown', params: {reason}});
  });
}
/* A view in a panel of its own: moved by its bar, sized from its corner, kept until put back or closed. */
async function popApp(key, mode = 'pip') {
  const entry = APPFRAMES.get(key);
  if (!entry) return;
  if (entry.panel) { entry.panel.hidden = false; return; }
  if (entry.moving) return;
  entry.moving = true;
  await teardownApp(entry, 'moved to a panel');
  entry.moving = false;
  if (APPFRAMES.get(key) !== entry) return;  // gone meanwhile, with its project
  const inline = entry.holder;
  const body = h('div', {class: 'appholder'});
  const leave = () => (inline ? bringBack(key) : closeApp(key));
  const note = h('small', {class: 'appnote', role: 'status', hidden: true});
  const panel = appPanel(entry, mode, body, inline ? () => bringBack(key) : null, leave, note);
  document.body.append(panel);
  movable(panel);
  overlay(panel, {kind: 'window', close: leave, focus: false});
  mountApp(key, body, entry.app, entry.scope, mode);
  Object.assign(entry, {panel, inline, inlineNote: entry.note, note});
  appNote(entry, '');
  if (inline?.isConnected) fill(inline, appAway(key));
  // the view is told its panel's size as the person sizes it
  const resized = () => {
    if (entry.ready && entry.panel === panel) {
      appPost(entry, {method: 'ui/notifications/host-context-changed',
        params: {containerDimensions: appContext(entry).containerDimensions}});
    }
  };
  new ResizeObserver(resized).observe(body);
}
/* The panel: its bar with the view's name, Back into the chat for a view that came from one, and Close. */
function appPanel(entry, mode, body, back, leave, note) {
  return h('div', {id: `mcpapp${++APPS.panels}`, class: `window movable mcpwin${mode === 'fullscreen' ? ' large' : ''}`,
    role: 'dialog', 'aria-label': appName(entry.app.uri)},
  h('div', {class: 'bar'}, h('span', {class: 'title'}, appName(entry.app.uri)),
    back ? h('button', {class: 'btn sm quiet', type: 'button', onclick: back}, 'Back into the chat') : null,
    h('button', {class: 'close btn icon sm quiet', type: 'button', 'aria-label': 'Close', title: 'Close (Escape)',
      onclick: leave}, h('i', {class: 'i i-close', 'aria-hidden': 'true'}))), note, body);
}
async function closeApp(key) {
  const entry = APPFRAMES.get(key);
  if (!entry) return;
  APPFRAMES.delete(key);
  await teardownApp(entry);
  if (entry.panel) { entry.panel.hidden = true; setTimeout(() => entry.panel.remove(), 0); }
}
async function bringBack(key) {
  const entry = APPFRAMES.get(key);
  if (!entry?.panel || entry.moving) return;
  const {panel, inline} = entry;
  entry.moving = true;
  await teardownApp(entry, 'moved back into the chat');
  entry.moving = false;
  entry.panel = null;
  panel.hidden = true;
  setTimeout(() => panel.remove(), 0);
  entry.note = entry.inlineNote;
  if (inline?.isConnected && APPFRAMES.get(key) === entry) mountApp(key, inline, entry.app, entry.scope, 'inline');
  else APPFRAMES.delete(key);
}
/* Leaving the project: every view, in the thread or a panel, is torn down and goes, with what the views kept for
 * their agents and the views read for it, so none of them acts for the next project. */
export function leaveApps() {
  for (const [key, entry] of APPFRAMES) {
    APPFRAMES.delete(key);
    teardownApp(entry, 'the project was left').then(() => entry.panel?.remove());
    if (entry.panel) entry.panel.hidden = true;
  }
  MODEL_CONTEXT.clear();
  Object.assign(APPS, {project: null, at: 0, tools: {}, views: [], gallery: false});
}
/* The gallery, /apps or the head's menu: every view the enabled modules offer, each opened in a panel of its own,
 * its calls made as the agent of the thread on view, or as the person's page when none is. */
export function showGallery() {
  APPS.gallery = true;
  readApps(true);
  drawHelpdesk().then(() => followLog(true));
}
export function galleryRows() {
  if (!APPS.gallery) return [];
  return [{key: 'gallery', text: JSON.stringify(APPS.views.map(one => one.uri)), make: gallery}];
}
function gallery() {
  const close = () => { APPS.gallery = false; drawHelpdesk(); };
  return h('div', {class: 'appgallery', role: 'group', 'aria-label': 'The views of the MCP server'},
    h('div', {class: 'appbar'}, h('span', {class: 'name'}, 'Apps'),
      h('small', {}, 'The views the enabled modules offer'), h('span', {class: 'grow'}),
      h('button', {class: 'btn sm quiet', type: 'button', onclick: close}, 'Close')),
    APPS.views.length ? h('ul', {}, APPS.views.map(galleryRow))
      : h('p', {class: 'hint'}, APPS.reading ? 'Reading the views…' : 'No enabled module offers a view here.'));
}
const galleryRow = one => h('li', {},
  h('div', {}, h('b', {}, one.name || one.uri), h('small', {}, one.description || ''), h('code', {}, one.uri)),
  h('button', {class: 'btn sm', type: 'button', onclick: () => openView(one)}, 'Open'));
function openView(one) {
  const key = `gallery:${one.uri}:${++APPS.panels}`;
  APPFRAMES.set(key, {key, app: {uri: one.uri, call: null}, scope: {work: DOCK.target, session: DOCK.session}});
  popApp(key);
}
const UNDRAWN = ['plan', 'state', 'tool_detail', 'turn'];  // drawn apart, or not lines of the conversation
const MESSAGES = ['agent_message_chunk', 'person', 'user_message_chunk'];
const SYSTEM_LINES = ['setting', 'approved', 'failed', 'notice'];
/* The agent's work in a thread: its tool calls with their details, the calls its permission prompts approved, and its
 * thinking. A thread shows what the agent says to the person, its messages and the lines it says on the map; its work
 * shows with web_chat_details on, or on this page after W, `toggleWork`, until the page is reloaded. */
const WORK_LINES = ['approved', 'agent_thought_chunk'];
export const CHATWORK = {shown: null};  // W's choice on this page; null follows web_chat_details
export const workShown = () => CHATWORK.shown ?? VIEW.chatDetails === true;
export function toggleWork() {
  CHATWORK.shown = !workShown();
  toast(CHATWORK.shown ? "The chat shows the agent's work on this page; web_chat_details in Settings keeps it shown."
    : 'The chat shows only what the agent says on this page; web_chat_details in Settings keeps it so.');
  drawHelpdesk();
}
/* A line the agent said on the map with web_say, as the chat shows it: its words, or null for any other call, or one
 * that failed. */
export function spokenOf(line) {
  const data = line.data, call = data?.call;
  if ((line.kind !== 'tool_call' && line.kind !== 'tool_call_update') || call?.tool !== 'web_say'
    || data.status === 'failed' || call.result?.isError) return null;
  const said = call.input?.text ?? call.result?.structuredContent?.text;
  return typeof said === 'string' && said.trim() ? said.trim() : null;
}
/* Words as compared for saying the same: case, quotes, spaces and the punctuation at their ends aside. */
export const sameWords = text => String(text ?? '').toLowerCase().replace(/[’‘]/g, "'").replace(/[“”]/g, '"')
  .replace(/\s+/g, ' ').replace(/^[\s"'.,!?…]+|[\s"'.,!?…]+$/g, '');
/* Those words one by one, each word's own punctuation aside, so they compare as whole words. */
const wordsOf = text => sameWords(text).split(' ').map(word => word.replace(/^["'.,!?…:;]+|["'.,!?…:;]+$/g, ''))
  .filter(Boolean);
/* Whether a message's words say all the spoken words, in order, as whole words: 'Look' is not said by 'Looking'. */
function saysAll(words, spoken) {
  for (let at = 0; at + spoken.length <= words.length; at++) {
    if (spoken.every((word, index) => words[at + index] === word)) return true;
  }
  return false;
}
/* Whether a message still being written is on its way to the spoken words: its words begin them, its last word
 * perhaps cut where the stream has got to. */
const growsInto = (words, spoken) => words.length > 0 && words.length <= spoken.length && words.every(
  (word, index) => (index === words.length - 1 ? spoken[index].startsWith(word) : spoken[index] === word));
/* What the agent's messages say in each turn of a thread, by turn, so a line it also said on the map is shown once:
 * each message's place in the lines and its words. */
function messagesByTurn(lines) {
  const said = [[]];
  lines.forEach((line, index) => {
    if (line.kind === 'turn') said.push([]);
    else if (line.kind === 'agent_message_chunk') said.at(-1).push({index, words: wordsOf(line.text)});
  });
  return said;
}
export function threadRows(lines, {work, agent}) {
  const rows = [], shown = workShown(), said = messagesByTurn(lines);
  const growing = new Map();  // a message still being written toward a line said on the map: its place, that line
  let sender = null;  // who wrote the message before, so a run of one sender's messages is named once
  let turn = 0;
  DOCK.heard = new Set();
  for (const [index, line] of lines.entries()) {
    const key = `${line.session_id}:${line.name ?? line.seq}`;
    const kind = line.kind;
    const text = `${kind}\n${line.text}\n${line.data ? JSON.stringify(line.data) : ''}`;
    if (kind === 'turn') turn++;
    if (UNDRAWN.includes(kind) || (!shown && WORK_LINES.includes(kind))) continue;
    const spoken = spokenOf(line);
    // a line said on the map is the agent's words, once: not again when a message of its turn says the same, and
    // not beside the message of its turn still being written toward it, which shows the line in its place until
    // it is written, so the one bubble neither doubles nor moves
    const words = spoken ? wordsOf(spoken) : [], last = turn === said.length - 1 ? said[turn].at(-1) : null;
    const unsaid = spoken && !said[turn].some(one => saysAll(one.words, words));
    if (unsaid && last?.index > index && growsInto(last.words, words)) growing.set(last.index, spoken);
    else if (unsaid) {
      const who = agentName(agent), first = who !== sender, at = seenAt(`said:${key}`, line);
      sender = who;
      rows.push({key: `said:${key}`, text: `said\n${spoken}\n${first}`, make: () => spokenRow(spoken, who, first, at)});
    }
    if (kind === 'tool_call' || kind === 'tool_call_update') toolRows(rows, line, key, text, work, shown);
    else if (kind === 'permission') rows.push({key, text, make: () => permissionCard(line, work, 'div', agent)});
    else if (kind === 'elicitation') rows.push({key, text, make: () => elicitationRow(line, work, agent)});
    else if (kind === 'agent_notice') rows.push({key, text, make: () => noticeRow(line)});
    else if (kind === 'attachment') rows.push({key, text, make: () => attachmentCard(line, agent)});
    else if (kind === 'signal') {
      const words = signalWords(line.text);
      if (words) rows.push({key, text, make: () => h('div', {class: 'system signal'}, words)});
    } else if (MESSAGES.includes(kind)) {
      const mine = kind !== 'agent_message_chunk', who = mine ? 'You' : agentName(agent);
      const first = who !== sender, at = seenAt(key, line);
      sender = who;
      if (mine) DOCK.heard.add(String(line.text).trim());
      const toward = growing.get(index);
      if (toward) rows.push({key, text: `said\n${toward}\n${first}`, make: () => spokenRow(toward, who, first, at)});
      else rows.push({key, text: `${text}\n${first}`, make: () => messageRow(line.text, {mine, who, first, at})});
    } else if (kind === 'agent_thought_chunk') rows.push({key, text, make: () => thoughtRow(line)});
    else if (SYSTEM_LINES.includes(kind)) {
      rows.push({key, text, make: () => h('div', {class: `system ${kind}`}, line.text)});
    }
  }
  for (const line of lines) SEEN.sessions.add(line.session_id);  // a line read later than this one arrived now
  return rows;
}
/* When the page first saw a row: none for those already there when its session was first read, `SEEN`. */
function seenAt(key, line) {
  const at = SEEN.at.get(key) ?? (SEEN.sessions.has(line.session_id) ? Date.now() : 0);
  SEEN.at.set(key, at);
  return at;
}
/* A line the agent said on the map, web_say: its bubble, marked as said there. */
function spokenRow(spoken, who, first, at) {
  const row = messageRow(spoken, {mine: false, who, first, at});
  row.classList.add('spoken');
  row.querySelector('.bubble').title = 'Said on the map';
  return row;
}
/* A tool call's row, shown with the agent's work, and under it the view of a Metaform tool that has one, fed the
 * call's input and its result, which shows either way: the agent shows it to the person. */
function toolRows(rows, line, key, text, work, shown) {
  if (shown) rows.push({key, text, make: () => toolRow(line, 'div', key)});
  const app = appOf(line);
  if (app) {
    rows.push({key: `app:${key}`, text: app.uri,
      make: () => appRow(`app:${key}`, app, {work, session: line.session_id})});
    appFed(`app:${key}`, app.call);
  }
}
/* A question still open as its card; one without a request said in a quiet line, with what became of it. */
function elicitationRow(line, work, agent) {
  if (line.data?.request) return elicitationCard(line, work, 'div', agent);
  return h('div', {class: 'system notice'}, `A question, ${line.data?.state || 'declined'}`
    + `${line.data?.by ? ` by ${line.data.by}` : ''}: ${line.data?.message || ''}`);
}
/* Its thinking, folded to a few quiet lines, opened and folded again by a click that is not on a link or button. */
function thoughtRow(line) {
  const unfold = event => { if (!event.target.closest('a, button')) event.currentTarget.classList.toggle('open'); };
  return h('div', {class: 'thought', title: 'Its thinking: click to read all of it, and again to fold it',
    onclick: unfold}, h('small', {}, 'Thinking'), h('span', {class: 'said'}, ...linked(line.text)));
}
