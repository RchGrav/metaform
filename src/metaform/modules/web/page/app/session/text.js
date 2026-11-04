/* A message's rows and Copy, markdown read into the page's own elements, the plan, and the session's own bar. */
import '/page/app/session/apps.js';  // the part before runs first, so the parts run in the page's order
import {h, fill} from '/page/app/core/dom.js';
import {toast, confirmAct} from '/page/app/core/controls.js';
import {overlay} from '/page/app/core/overlays.js';
import {S, reach} from '/page/app/core/reads.js';
import {clockOf, DOCK} from '/page/app/dock/embody.js';
import {followLog} from '/page/app/dock/helpdesk.js';
import {linked} from '/page/app/board/refs.js';
import {wrote, movable} from '/page/app/board/history.js';
import {renderAgents} from '/page/app/agents/dispatch.js';
import {agentName, summonAgent} from '/page/app/agents/pickers.js';
import {skipsPrompts, STATUS_WORDS, countOf} from '/page/app/session/tools.js';
import {SESSIONPOP, sessionSummary, preCallSettings} from '/page/app/session/settings.js';
import {notificationState} from '/page/app/session/tasks.js';

/* A message: who wrote it, named above the first of a run of theirs, its words read as markdown, and on hover or
 * focus the time it arrived and, for the agent's, Copy. The sender is said to a screen reader in the bubble too. The
 * person's message that told their system agent what they clicked shows that as a chip over their words. */
export function messageRow(text, {mine, who, first, at, pending = null}) {
  const [told, words] = mine ? clickedOf(text) : [null, text];
  const bubble = h('div', {class: `bubble ${mine ? 'mine' : 'theirs'}${pending ? ' pending' : ''}`},
    h('span', {class: 'visually-hidden'}, `${who}: `),
    told ? h('span', {class: 'chip clickedchip', title: `Your agent was told: ${told}`},
      told.slice(CLICK_LEAD.length).replace(/^\d+ s before: /, 'Clicked: ').replace(/\.$/, '')) : null,
    ...richText(words));
  const time = at
    ? h('time', {datetime: new Date(at).toISOString(), title: new Date(at).toLocaleString()}, clockOf(at)) : null;
  const tools = h('div', {class: 'tools'}, pending ? h('small', {class: 'pendingnote'}, pending) : time,
    mine ? null : copyButton(() => String(text), 'Copy the message'));
  return h('div', {class: `msg ${mine ? 'mine' : 'theirs'}${first ? ' first' : ''}`},
    first ? h('div', {class: 'who', 'aria-hidden': 'true'}, who) : null, h('div', {class: 'row'}, bubble, tools));
}
/* The line that tells the person's system agent what they last clicked, first in their message, dock/send.js; split
 * from the words they wrote: [the line or null, the words]. */
export const CLICK_LEAD = 'The person clicked, ';
function clickedOf(text) {
  const said = String(text ?? ''), end = said.indexOf('\n\n');
  return said.startsWith(CLICK_LEAD) && end > 0 ? [said.slice(0, end), said.slice(end + 2)] : [null, said];
}
/* A small Copy button: the text given goes to the clipboard, and the button says Copied for a moment. */
function copyButton(text, label = 'Copy') {
  async function copy(event) {
    event.stopPropagation();
    const said = text();
    try { await navigator.clipboard.writeText(said); } catch { copyByHand(said); }
    button.classList.add('done');
    button.setAttribute('aria-label', 'Copied');
    setTimeout(() => { button.classList.remove('done'); button.setAttribute('aria-label', label); }, 1400);
  }
  const button = h('button', {class: 'copy', type: 'button', title: label, 'aria-label': label, onclick: copy},
    h('i', {class: 'i i-copy', 'aria-hidden': 'true'}), h('i', {class: 'i i-check', 'aria-hidden': 'true'}));
  return button;
}
/* Where the browser gives no clipboard: the text selected in a field out of sight and copied the old way. */
function copyByHand(said) {
  const field = h('textarea', {style: {position: 'fixed', opacity: '0'}}, said);
  document.body.append(field); field.select();
  try { document.execCommand('copy'); } catch { /* nothing more to try */ }
  field.remove();
}
/* A message's words as written in markdown, read into the page's own elements and never set as HTML, VIEW-009:
 * paragraphs, headings, lists, quotes and rules; fenced code with its language and Copy; inline code, bold, italic
 * and links to web pages, opened in a new tab. References in the words are linked as everywhere else. */
const BLOCK_START = /^\s*(```|~~~|#{1,6}\s|>|[-*+]\s|\d{1,3}[.)]\s|([-*_])(\s*\2){2,}\s*$)/;
const LIST_ITEM = /^(\s*)([-*+]|\d{1,3}[.)])\s+/;
export function richText(text) {
  const lines = String(text ?? '').replace(/\r\n?/g, '\n').split('\n'), out = [];
  let at = 0;
  while (at < lines.length) {
    const line = lines[at];
    const fence = /^\s*(```+|~~~+)\s*([\w+#.-]*)/.exec(line);
    if (fence) { at = fenced(lines, at, fence, out); continue; }
    if (!line.trim()) { at++; continue; }
    const head = /^\s*(#{1,6})\s+(.*)$/.exec(line);
    if (head) { out.push(h('p', {class: `mdh h${head[1].length}`}, ...inlineText(head[2]))); at++; continue; }
    if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) { out.push(h('hr')); at++; continue; }
    if (/^\s*>/.test(line)) at = quoted(lines, at, out);
    else if (LIST_ITEM.test(line)) at = listed(lines, at, out);
    else at = paragraph(lines, at, out);
  }
  return out;
}
/* Each block reader adds its block to `out` and gives the line after it. */
function fenced(lines, at, fence, out) {
  const code = [];
  for (at++; at < lines.length && !lines[at].trim().startsWith(fence[1]); at++) code.push(lines[at]);
  const closed = at < lines.length;  // a block whose closing fence has not come is still being written
  at++;
  out.push(fence[2].toLowerCase() === 'mermaid' ? diagramBlock(code.join('\n'), closed)
    : codeBlock(code.join('\n'), fence[2]));
  return at;
}
function quoted(lines, at, out) {
  const said = [];
  for (; at < lines.length && /^\s*>/.test(lines[at]); at++) said.push(lines[at].replace(/^\s*>\s?/, ''));
  out.push(h('blockquote', {}, ...richText(said.join('\n'))));
  return at;
}
/* A list runs while its lines are items of its kind, or lines indented under the item before. */
function listed(lines, at, out) {
  const line = lines[at];
  const ordered = /\d/.test(LIST_ITEM.exec(line)[2]), items = [];
  for (; at < lines.length && (LIST_ITEM.test(lines[at]) || (/^\s{2,}\S/.test(lines[at]) && items.length)); at++) {
    const found = LIST_ITEM.exec(lines[at]);
    if (found && /\d/.test(found[2]) === ordered) items.push(lines[at].slice(found[0].length));
    else if (found) break;
    else items[items.length - 1] += '\n' + lines[at].trim();
  }
  const start = ordered ? parseInt(LIST_ITEM.exec(line)[2], 10) : 1;
  out.push(h(ordered ? 'ol' : 'ul', ordered && start !== 1 ? {start: String(start)} : {},
    items.map(one => h('li', {}, ...inlineText(one)))));
  return at;
}
function paragraph(lines, at, out) {
  const said = [lines[at]];
  for (at++; at < lines.length && lines[at].trim() && !BLOCK_START.test(lines[at]); at++) said.push(lines[at]);
  out.push(h('p', {}, ...inlineText(said.join('\n'))));
  return at;
}
/* Inline code, bold, italic, a link written [label](address), and a bare web address. */
const INLINE = new RegExp([
  /(`+)([^`]|[^`][\s\S]*?[^`])\1(?!`)/.source,
  /\*\*([^*\n]+?)\*\*/.source,
  /__([^_\n]+?)__/.source,
  /(?<![\w*])\*(?!\s)([^*\n]+?)\*(?![\w*])/.source,
  /(?<![\w_])_(?!\s)([^_\n]+?)_(?![\w_])/.source,
  /\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/.source,
  /(https?:\/\/[^\s<>()]+[^\s<>().,;:!?'"])/.source,
].join('|'), 'g');
function inlineText(text) {
  const parts = [];
  let at = 0;
  for (const found of text.matchAll(INLINE)) {
    parts.push(...linked(text.slice(at, found.index)));
    const [, , code, bold, bold2, em, em2, label, href, bare] = found;
    if (code !== undefined) parts.push(h('code', {}, code));
    else if (bold || bold2) parts.push(h('strong', {}, ...linked(bold || bold2)));
    else if (em || em2) parts.push(h('em', {}, ...linked(em || em2)));
    else {
      parts.push(h('a', {href: href || bare, target: '_blank', rel: 'noopener noreferrer', title: href || bare},
        label || bare));
    }
    at = found.index + found[0].length;
  }
  parts.push(...linked(text.slice(at)));
  return parts;
}
function codeBlock(code, lang) {
  return h('div', {class: 'code'},
    h('div', {class: 'codehead'}, h('span', {}, lang || 'code'), copyButton(() => code, 'Copy the code')),
    h('pre', {tabindex: '0'}, h('code', {}, code)));
}
/* A Mermaid diagram in a fenced block, drawn in place by the bundled Mermaid at its strict security level, its SVG
 * read as a document and never set as HTML. Its source is one click away, with Copy; a block still being written, or
 * one Mermaid cannot read, shows its source and says why, and the rest of the message reads on. Each drawing is kept
 * by its source, so a thread drawn again shows it at once, and Enlarge opens it in a window of its own. */
const DIAGRAMS = new Map();  // source -> {svg} or {error}, the most recent few
const DRAWING = new Map();  // source -> the drawing under way
const SOURCE_SHOWN = new Set();  // the sources the person turned to, kept as the thread is drawn again
let DIAGRAM_ID = 0;
function diagramBlock(code, closed) {
  const figure = h('div', {class: 'figure', role: 'img', 'aria-label': 'Diagram'});
  const source = h('pre', {tabindex: '0'}, h('code', {}, code));
  const note = h('p', {class: 'diagramnote', role: 'status'});
  const flip = () => { if (!SOURCE_SHOWN.delete(code)) SOURCE_SHOWN.add(code); shown(); };
  const toggle = h('button', {class: 'btn sm quiet', type: 'button', onclick: flip}, 'Source');
  const enlarge = h('button', {class: 'copy', type: 'button', title: 'Enlarge the diagram',
    'aria-label': 'Enlarge the diagram', onclick: () => enlargeDiagram(figure)},
  h('i', {class: 'i i-expand', 'aria-hidden': 'true'}));
  const block = h('div', {class: 'code diagram'},
    h('div', {class: 'codehead'}, h('span', {}, 'mermaid diagram'), h('span', {class: 'grow'}), toggle, enlarge,
      copyButton(() => code, 'Copy the diagram source')), figure, note, source);
  function shown() {
    const drawn = DIAGRAMS.get(code);
    const svg = closed && drawn?.svg;
    figure.hidden = !svg;
    if (svg && !figure.firstChild) figure.append(svgOf(svg));
    note.hidden = Boolean(svg);
    note.textContent = !closed ? 'The diagram is still being written; it is drawn once its block is complete.'
      : drawn?.error ? `Mermaid could not read this diagram: ${drawn.error}` : drawn ? '' : 'Drawing the diagram…';
    note.classList.toggle('failed', Boolean(drawn?.error));
    source.hidden = Boolean(svg) && !SOURCE_SHOWN.has(code);
    toggle.hidden = !svg;
    toggle.textContent = source.hidden ? 'Source' : 'Hide source';
    toggle.setAttribute('aria-expanded', String(!source.hidden));
    enlarge.hidden = !svg;
    block.dataset.state = !closed ? 'writing' : drawn?.error ? 'failed' : svg ? 'drawn' : 'drawing';
  }
  shown();
  // drawn after its row is placed, it grows the thread, which stays at its end if it was following it
  const drawnLate = () => { shown(); if (DOCK.pinned && block.closest('#helpdesk')) followLog(); };
  if (closed && !DIAGRAMS.has(code)) drawDiagram(code).then(drawnLate);
  return block;
}
/* One source drawn once, however many rows ask for it while it is drawn; checked first, so a source Mermaid cannot
 * read leaves none of its error drawings in the page. */
function drawDiagram(code) {
  if (DRAWING.has(code)) return DRAWING.get(code);
  const id = `chatdiagram${++DIAGRAM_ID}`;
  const keep = drawn => {
    DIAGRAMS.set(code, drawn);
    if (DIAGRAMS.size > 60) DIAGRAMS.delete(DIAGRAMS.keys().next().value);
    return drawn;
  };
  const drawing = (async () => {
    if (!window.mermaid) return keep({error: 'the diagram library did not load.'});
    try {
      await window.mermaid.parse(code);
      const result = await window.mermaid.render(id, code, document.querySelector('#draw') || undefined);
      return keep({svg: result.svg});
    } catch (error) {
      return keep({error: String(error?.message || error).split('\n').filter(Boolean).slice(0, 3).join(' ')});
    } finally {
      for (const left of document.querySelectorAll(`#${id}, #d${id}`)) left.remove();
      DRAWING.delete(code);
    }
  })();
  DRAWING.set(code, drawing);
  return drawing;
}
/* One diagram's drawing, {svg} or {error}, from the kept drawings or drawn now; a drawing outside a chat row, such as
 * a ticket's graph, shares the cache. */
export const diagramOf = code => DIAGRAMS.has(code) ? Promise.resolve(DIAGRAMS.get(code)) : drawDiagram(code);
export function svgOf(text) {
  const svg = document.importNode(new DOMParser().parseFromString(text, 'image/svg+xml').documentElement, true);
  for (const unsafe of svg.querySelectorAll('script')) unsafe.remove();
  const width = parseFloat(svg.getAttribute('width')) || svg.viewBox?.baseVal?.width || 0;
  svg.removeAttribute('height'); svg.removeAttribute('style');
  svg.setAttribute('width', '100%');
  if (width) svg.style.maxWidth = `${Math.round(width)}px`;
  svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  return svg;
}
/* The diagram in a window of its own, as large as the person makes it, closed with Escape. */
export function enlargeDiagram(figure, title = 'Diagram') {
  const drawn = figure.querySelector('svg');
  if (!drawn) return;
  const svg = drawn.cloneNode(true);
  svg.style.maxWidth = '';
  const close = () => { win.hidden = true; setTimeout(() => win.remove(), 0); };
  const win = h('div', {class: 'window movable diagramwin large', role: 'dialog', 'aria-label': title},
    h('div', {class: 'bar'}, h('span', {class: 'title'}, title),
      h('button', {class: 'close btn icon sm quiet', type: 'button', 'aria-label': 'Close', title: 'Close (Escape)',
        onclick: close}, h('i', {class: 'i i-close', 'aria-hidden': 'true'}))),
    h('div', {class: 'diagrambody'}, svg));
  document.body.append(win);
  movable(win);
  overlay(win, {kind: 'window', close});
}
/* A file the agent attached to its chat, `dispatch attach`: its name, size, type and where it was made, and Download,
 * which asks first whether the file is still kept, so a file gone says so here rather than in the browser's list. */
const SIZE_UNITS = ['bytes', 'KB', 'MB', 'GB'];
function sizeOf(bytes) {
  let size = Number(bytes) || 0, unit = 0;
  for (; size >= 1024 && unit < SIZE_UNITS.length - 1; unit++) size /= 1024;
  return unit ? `${size.toFixed(size < 10 ? 1 : 0)} ${SIZE_UNITS[unit]}` : `${size} bytes`;
}
export function attachmentCard(line, agent) {
  const file = line.data || {};
  const query = new URLSearchParams({project: S.project || '', session: line.session_id || '', id: file.id || ''});
  const url = `/api/attachment?${query}`;
  const said = h('small', {class: 'gone', role: 'status'});
  async function download(event) {
    if (link.dataset.checked === 'true') { link.dataset.checked = ''; return; }
    event.preventDefault();
    let kept = null;
    try { kept = await reach(`${url}&check=1`, {headers: {Accept: 'application/json'}}); } catch { kept = null; }
    if (!kept?.ok) {
      card.classList.add('missing');
      said.textContent = kept ? 'This file is no longer kept, so it cannot be downloaded.'
        : 'The server could not be reached; try again in a moment.';
      return toast(said.textContent);
    }
    link.dataset.checked = 'true';
    link.click();
  }
  const link = h('a', {class: 'btn sm', href: url, download: file.name || 'file', onclick: download,
    title: `Download ${file.name || 'the file'}`}, h('i', {class: 'i i-download', 'aria-hidden': 'true'}), 'Download');
  const card = h('div', {class: 'attachment', role: 'group', 'aria-label': `${agentName(agent)} attached ${file.name}`},
    h('i', {class: 'i i-file', 'aria-hidden': 'true'}),
    h('div', {class: 'about'}, h('b', {class: 'name', title: file.name}, file.name || 'file'),
      h('small', {}, [sizeOf(file.size), file.type].filter(Boolean).join(' · ')),
      file.source ? h('small', {class: 'from', title: file.sha256 ? `SHA-256 ${file.sha256}` : ''},
        `${agentName(agent)} attached it from ${file.source}`) : null, said),
    link);
  return h('div', {class: 'msg theirs attached'}, h('div', {class: 'row'}, card));
}
/* The plan, a checklist of its entries as the agent keeps it, drawn again only when it changes. */
export function drawPlan(box, plan) {
  const entries = Array.isArray(plan) ? plan : [];
  const text = JSON.stringify(entries);
  if (box.dataset.drawn === text) return;
  box.dataset.drawn = text;
  box.hidden = !entries.length;
  if (!entries.length) return fill(box);
  const done = entries.filter(entry => entry.status === 'completed').length;
  // open as it was; at first open in a window, folded to its count in the chat, where the conversation needs the room
  const wasOpen = box.querySelector('details') ? box.querySelector('details').open
    : box.dataset.closed ? box.dataset.closed !== 'true' : !box.closest('#helpdesk');
  const details = h('details', {open: wasOpen, ontoggle: event => { box.dataset.closed = String(!event.target.open); }},
    h('summary', {}, h('span', {class: 'eyebrow'}, 'Plan'),
      h('span', {class: 'tally'}, `${done} of ${entries.length} done`),
      h('span', {class: 'meter', 'aria-hidden': 'true'},
        h('span', {style: {width: `${Math.round(100 * done / entries.length)}%`}}))),
    h('ol', {class: 'steps'}, entries.map(planStep)));
  fill(box, details);
}
const planStep = entry => h('li', {class: entry.status || 'pending'},
  h('i', {class: 'mark', 'aria-hidden': 'true'}),
  h('span', {class: 'visually-hidden'}, `${STATUS_WORDS[entry.status] || entry.status}: `),
  h('span', {class: 'what'}, entry.content || ''),
  entry.priority === 'high' ? h('span', {class: 'prio', title: 'High priority'}, 'high') : null);
/* The session's own bar: its settings as the agent offers them, a mode that skips the agent's own permission prompts
 * said as such, its usage, and Resume for a session that ended when its agent can resume it. Drawn again only when
 * what it shows changed, and never while one of its selects is in the person's hand. */
export function drawSession(box, {work, session, state}) {
  if (notificationState(state)) {
    box.hidden = true;
    box.dataset.drawn = '';
    if (SESSIONPOP.el) SESSIONPOP.el.hidden = true;
    return;
  }
  const settings = state?.settings || [];
  const usage = state?.usage || null;
  const caps = state?.capabilities || {};
  const ended = session && session.state !== 'running';
  /* Every ended session can be called back: resumed in place where its agent offers load or resume, else as a new
   * context of the same agent reading its thread; the answer says which. */
  const resumable = ended, inPlace = Boolean(caps.load || caps.resume);
  const text = JSON.stringify([work, session?.session_id, session?.state, settings, usage, resumable,
    state?.tokens || null]);
  if (box.dataset.drawn === text + (session ? '' : summonAgent()) || (box.contains(document.activeElement)
    || SESSIONPOP.el?.contains(document.activeElement)) && box.dataset.work === work) return;
  box.dataset.drawn = text + (session ? '' : summonAgent());
  box.dataset.work = work || '';
  const agent = agentName(session?.agent);
  const controls = ended ? [] : settings.map(setting => setting.type === 'boolean'
    ? switchSetting(setting, work) : selectSetting(setting, work, agent));
  const used = usage && usage.used !== null && usage.used !== undefined ? usageLine(usage) : null;
  const resume = resumable ? resumeButton(work, session, agent, inPlace) : null;
  if (!session && !ended) { preCallSettings(box); return; }  // before Call: the agent's known options, chosen first
  sessionSummary(box, {agent, settings, usage, controls, used, resume});
}
/* A setting that is on or off, written as it is switched and put back when the write fails. */
function switchSetting(setting, work) {
  const flip = async () => {
    input.disabled = true;
    const done = await wrote('/api/dispatch-configure', {work_id: work, setting: setting.id, value: input.checked});
    input.disabled = false;
    if (!done) input.checked = !input.checked;
  };
  const input = h('input', {type: 'checkbox', role: 'switch', checked: Boolean(setting.current), onchange: flip});
  return h('label', {class: 'switch setting', title: setting.description || setting.name}, input, setting.name);
}
/* A setting chosen among the agent's options; a mode that skips its permission prompts is confirmed first and marked
 * Approve all while it holds. */
function selectSetting(setting, work, agent) {
  const current = (setting.options || []).find(option => option.value === setting.current);
  const pick = h('select', {'aria-label': setting.name, title: setting.description || setting.name,
    onchange: () => chooseSetting(setting, work, agent, pick)},
  (setting.options || []).map(option => h('option', {value: option.value, selected: option.value === setting.current},
    skipsPrompts(option) ? `${option.name} · skips its permission prompts` : option.name)));
  const isMode = setting.source === 'mode' || setting.category === 'mode';
  return h('label', {class: 'setting'}, h('span', {}, setting.name), pick,
    isMode ? (skipsPrompts(current)
      ? h('span', {class: 'badge danger', title: `${agent} can run commands and edit files without permission dialogs. Instructions still apply.`}, 'Approve all') : null) : null);
}
async function chooseSetting(setting, work, agent, pick) {
  const option = (setting.options || []).find(one => one.value === pick.value);
  if (skipsPrompts(option) && !await confirmAct({title: `Let ${agent} act without asking?`,
    text: [`${option.name}: in this mode ${agent} skips its own permission prompts. It edits files and runs commands `
      + 'without asking you first.', 'You can choose another mode at any time.'],
    verb: `Use ${option.name}`, cancel: 'Keep asking', danger: true})) {
    pick.value = setting.current; return;
  }
  pick.disabled = true;
  const done = await wrote('/api/dispatch-configure', {work_id: work, setting: setting.id, value: pick.value});
  pick.disabled = false;
  if (!done) pick.value = setting.current;
  else toast(`${setting.name}: ${option?.name || pick.value}.`);
}
/* The context the session has used of its model's window, and what it cost when the agent says. */
function usageLine(usage) {
  const cost = usage.cost && usage.cost.amount !== undefined
    ? ` · ${usage.cost.currency === 'USD' || !usage.cost.currency ? '$' : usage.cost.currency + ' '}`
      + `${Number(usage.cost.amount).toFixed(2)}` : '';
  return h('span', {class: 'usage', title: 'The context the session has used of its model\'s window'},
    usage.size ? `${countOf(usage.used)} / ${countOf(usage.size)} tokens` : `${countOf(usage.used)} tokens`, cost);
}
function resumeButton(work, session, agent, inPlace) {
  async function resume(event) {
    const button = event.currentTarget;  // read before the await, after which the event has no currentTarget
    button.disabled = true;
    const done = await wrote('/api/dispatch-resume', {work_id: work, session: session.session_id});
    if (!done) { button.disabled = false; return; }
    toast(done.state === 'running' ? `${agent} is running already; talk to it here.`
      : done.notice || `${agent} is resuming its session; it waits for your next message.`);
    await renderAgents();
  }
  return h('button', {class: 'btn sm resume', type: 'button',
    title: inPlace ? `${agent} offers to resume its sessions: it goes on where it ended, with its own memory of the work`
      : `${agent} cannot resume this session: a new context of the same agent starts and reads its thread`,
    onclick: resume}, h('i', {class: 'i i-play', 'aria-hidden': 'true'}), 'Resume');
}
