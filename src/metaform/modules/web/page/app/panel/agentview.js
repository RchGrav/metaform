/* What an agent connecting here receives, and provenance. */
import '/page/app/panel/brief.js';  // the part before runs first, so the parts run in the page's order
import {$, h, fill} from '/page/app/core/dom.js';
import {overlay} from '/page/app/core/overlays.js';
import {S, read} from '/page/app/core/reads.js';
import {colorVar} from '/page/app/header/layers.js';
import {noMetaform, noneYet} from '/page/app/header/admin.js';
import {showAgentMenu, refusalBox} from '/page/app/settings/screen.js';
import {counted, briefAddress, briefCopy, budgetMeter} from '/page/app/panel/brief.js';
import {renderPrompt, showTab} from '/page/app/panel/prompts.js';
import {WS} from '/page/app/workspace/workspace.js';

/* ---------- what an agent connecting here receives ----------
 * Read from the project folder's own MCP server over MCP, as the MCP Inspector reads a server, by /api/agent-view:
 * the instructions sent at connect with the capabilities discover gave, metaform://metaform and metaform://tools, every
 * tool, resource, resource template and prompt the lists give, each entry as received and its size, and the selected
 * node's brief; the connect message against the characters Claude Code keeps of a server's instructions, the brief
 * against node_summary_bytes. What is paid before the first call is said both ways a host loads tools: deferred behind
 * tool search, Claude Code's default, where the names come first, or every tool up front. */
const AV = {generation: 0, tab: 'connect', data: null};
const AV_TABS = [['connect', 'Connect'], ['glossary', 'Glossary'], ['tools', 'Tools'], ['resources', 'Resources'],
  ['prompts', 'Prompts'], ['brief', 'Brief']];
export async function openAgentView() {
  showAgentMenu(false);
  if (WS.reveal('agent-view')) return;  // a pane in the workspace: it shows there and reads as it shows
  $('#agentview').hidden = false;
  await readAgentView();
}
export async function readAgentView() {
  const body = $('#agentview .body'), generation = ++AV.generation, address = briefAddress();
  fill(body, h('p', {class: 'loading', role: 'status'},
    'Starting this project\'s MCP server and reading it as an agent does…'));
  let data;
  try { data = await read('agent-view', address ? {address} : {}); } catch (error) {
    if (generation === AV.generation) fill(body, refusalBox(error.body || {error: error.message}));
    return;
  }
  if (generation !== AV.generation) return;
  AV.data = {...data, address};
  drawAgentView();
}
function drawAgentView() {
  const data = AV.data, body = $('#agentview .body');
  const tabs = h('div', {class: 'tabs views', role: 'tablist', 'aria-label': 'What the agent receives'});
  const panel = h('div', {class: 'view', role: 'tabpanel', tabindex: '0'});
  const sizes = {connect: counted(data.connect.chars, 'chars'), glossary: counted(data.glossary.bytes),
    tools: String(data.tools.length), resources: String(data.resources.length + data.templates.length),
    prompts: String(data.prompts.length), brief: data.brief ? counted(data.brief.bytes) : '–'};
  const show = key => {
    AV.tab = key;
    for (const button of tabs.children) {
      const on = button.dataset.tab === key;
      button.setAttribute('aria-selected', String(on));
      button.tabIndex = on ? 0 : -1;
    }
    panel.setAttribute('aria-labelledby', `av-${key}`);
    fill(panel, agentPart(key));
  };
  for (const [key, label] of AV_TABS) {
    tabs.append(h('button', {role: 'tab', type: 'button', id: `av-${key}`, 'data-tab': key,
      'aria-controls': 'av-panel', onclick: () => show(key)}, label, h('small', {}, sizes[key])));
  }
  panel.id = 'av-panel';
  tabs.addEventListener('keydown', event => walkTabs(event, tabs, show));
  fill(body, h('p', {class: 'lead'}, 'Read now from this project\'s MCP server, as an agent connecting to it reads '
    + 'it. Only the connect message is pushed; the rest is read when the agent asks.'),
  paidFacts(data), tabs, panel);
  show(AV.tab);
}
/* The arrows, Home and End move between the tabs and show the one moved to. */
function walkTabs(event, tabs, show) {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
  event.preventDefault();
  const keys = AV_TABS.map(([key]) => key), at = keys.indexOf(AV.tab);
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? keys.length - 1
    : (at + (event.key === 'ArrowRight' ? 1 : -1) + keys.length) % keys.length;
  show(keys[next]);
  tabs.children[next].focus();
}
/* What an agent pays before its first call, each way a host loads tools, then the glossary. */
function paidFacts(data) {
  const paid = data.paid;
  const fact = (term, count, words) => [h('dt', {}, term), h('dd', {}, counted(count), h('small', {}, words))];
  return h('dl', {class: 'paid',
    'aria-label': 'What an agent pays before its first call, in bytes as Claude Code sends them to the model'},
  ...fact('With tool search', paid.deferred, ` connect message, the tool names as mcp__${paid.server}__<tool>, `
      + 'and any tool marked to load up front, as Claude Code loads tools by default'),
  ...fact('Tools loaded as asked', paid.loaded,
    ' the same with every tool loaded, as the connect message asks the agent to make sure of'),
  ...fact('Without it', paid.upfront,
    ' connect message and every tool in full: its name, description and input schema'),
  ...fact('Then the glossary', paid.glossary, ' metaform://metaform, read once, as the connect message asks; '
      + `metaform://tools, ${counted(data.glossary.index.bytes)}, read only where tools are listed by name`));
}
/* One entry of a list as the server gave it: its name, size and first line, opened to the entry as received. */
function entryRow(name, bytes, said, entry, marks = []) {
  return h('li', {}, h('details', {class: 'entry' + (marks.includes('over') ? ' over' : '')},
    h('summary', {}, h('code', {}, name), h('span', {class: 'n'}, counted(bytes)),
      ...marks.filter(Boolean).map(mark => h('span', {class: 'pill'}, mark)), h('span', {class: 'said'}, said)),
    h('pre', {class: 'brieftext raw', tabindex: '0', 'aria-label': `${name} as the server gives it`},
      JSON.stringify(entry, null, 2))));
}
const rawText = (label, value) => h('pre', {class: 'brieftext raw', tabindex: '0', 'aria-label': label}, value);
/* Each tab of what an agent receives; the brief is the tab for any other key. */
const AGENT_PARTS = {connect: connectPart, glossary: glossaryPart, tools: toolsPart, resources: resourcesPart,
  prompts: promptsPart};
function agentPart(key) {
  return (Object.hasOwn(AGENT_PARTS, key) ? AGENT_PARTS[key] : briefPart)(AV.data);
}
function connectPart(data) {
  const capabilities = Object.entries(data.capabilities).map(([name, held]) =>
    name === 'extensions' && held && typeof held === 'object'
      ? `extensions (${Object.keys(held).join(', ') || 'none'})` : name).join(', ') || 'none';
  const server = data.server ? ` · ${data.server.name} ${data.server.version || ''}` : '';
  return [
    budgetMeter('Connect message', data.connect.chars, data.host_limit, 'characters'),
    h('p', {class: 'hint'}, `Capabilities: ${capabilities} · protocol ${data.protocol.join(', ')}${server}`),
    h('p', {class: 'hint'}, 'The server\'s instructions, sent once as the agent connects. Claude Code keeps the first '
      + `${counted(data.host_limit, 'characters')} of them.`),
    rawText('The connect message', data.connect.text), briefCopy('the connect message', data.connect.text)];
}
function glossaryPart(data) {
  return [
    budgetMeter('metaform://metaform', data.glossary.bytes, 0),
    budgetMeter('metaform://tools, one line per tool, read apart where tools are listed by name',
      data.glossary.index.bytes, 0),
    h('p', {class: 'hint'},
      'The terms and rules, then one line per tool: read once, when the connect message tells the agent to.'),
    rawText('metaform://metaform', data.glossary.text), briefCopy('the glossary', data.glossary.text),
    rawText('metaform://tools', data.glossary.index.text)];
}
function toolsPart(data) {
  const long = data.tools.filter(tool => tool.description.length > data.host_limit);
  const row = tool => entryRow(tool.name, tool.bytes, tool.description.split(/(?<=\.)\s/)[0], tool.entry,
    [tool.description.length > data.host_limit ? 'over' : '', tool.always ? 'up front' : '']);
  return [
    budgetMeter(`${data.tools.length} tools, with their schemas`, data.tool_bytes, 0),
    h('p', {class: 'hint'}, 'Each tool as tools/list gives it, largest first. With tool search an agent is handed the '
      + 'names and loads a tool\'s description and schema when it needs the tool; a tool marked to load up front is '
      + 'handed whole.'),
    long.length ? h('p', {class: 'warnline'},
      `${long.length} description(s) run past the ${counted(data.host_limit, 'characters')} Claude Code keeps.`) : null,
    h('ul', {class: 'entries', 'aria-label': 'Every tool, largest first'}, data.tools.map(row))];
}
function resourcesPart(data) {
  const said = one => one.entry.description || one.entry.name || '';
  return [
    h('p', {class: 'hint'}, 'What an agent can read, as resources/list and resources/templates/list give them. It '
      + 'learns of metaform://metaform, metaform://tools and metaform://<address> here.'),
    h('div', {class: 'eyebrow'}, `Resources · ${data.resources.length}`),
    h('ul', {class: 'entries'}, data.resources.map(one => entryRow(one.entry.uri, one.bytes, said(one), one.entry))),
    h('div', {class: 'eyebrow'}, `Templates · ${data.templates.length}`),
    h('ul', {class: 'entries'},
      data.templates.map(one => entryRow(one.entry.uriTemplate, one.bytes, said(one), one.entry)))];
}
function promptsPart(data) {
  return [
    h('p', {class: 'hint'}, 'The prompts the server offers, as prompts/list gives them: the host shows each as a slash '
      + 'command the person runs.'),
    data.prompts.length ? h('ul', {class: 'entries'},
      data.prompts.map(one => entryRow(one.entry.name, one.bytes, one.entry.description || '', one.entry)))
      : h('p', {class: 'empty'}, 'This server offers no prompts.')];
}
function briefPart(data) {
  if (!data.brief) {
    return h('p', {class: 'empty'},
      'Select an element on the map, then read again, to see the brief an agent working there is handed.');
  }
  return [
    budgetMeter(`metaform://${data.address}`, data.brief.bytes, data.budget),
    h('p', {class: 'hint'}, 'Handed to an agent assigned to this node, and read by any agent at its address.'),
    rawText('The brief', data.brief.text), briefCopy('the brief', data.brief.text)];
}
$('#agentViewBtn').onclick = openAgentView;
$('#agentview .close').onclick = () => { $('#agentview').hidden = true; };
$('#agentview .again').onclick = readAgentView;
overlay($('#agentview'), {kind: 'dialog', close: () => { $('#agentview').hidden = true; },
  focus: () => $('#agentview [role=tab][aria-selected=true]') || $('#agentview .again')});

/* ---------- provenance ---------- */
let provLayer = null;
export async function renderProv() {
  const pane = $('#p-prov');
  if (noMetaform()) return fill(pane, h('p', {class: 'empty'}, noneYet()));
  provLayer = provLayer && S.layers.some(layer => layer.name === provLayer) ? provLayer : S.layers[0]?.name;
  const list = h('div', {class: 'layerlist'}, S.layers.map(provButton));
  if (!S.layers.length) return fill(pane, h('p', {class: 'empty'}, 'No layer is recorded in this metaform yet.'));
  fill(pane, h('div', {class: 'eyebrow'}, 'Layers in this metaform'), list);
  if (!provLayer) return;
  const layer = S.layers.find(item => item.name === provLayer);
  // One list of facts for the layer, those its provenance record adds joining it, so every label lines up.
  const facts = h('dl', {class: 'prov'}, ...[['kind', layer.kind], ['module', layer.module], ['created', layer.created],
    ['state', layer.ready ? `ready ${layer.ready}` : 'building'], ['tags', (layer.tags || []).join(', ') || 'none'],
    ['holds', layer.variable]].filter(([, value]) => value !== undefined && value !== null && value !== '')
    .flatMap(([key, value]) => [h('dt', {}, key), h('dd', {}, value)]));
  pane.append(h('div', {class: 'eyebrow'}, 'How it was made'), h('h2', {}, layer.name), facts);
  if (layer.kind === 'memory') {
    return pane.append(h('p', {class: 'empty'}, 'Memory has no provenance. Agents write it freely.'));
  }
  try {
    const record = await read('provenance', {layer: layer.name});
    if (provLayer !== layer.name) return;
    provenanceOf(record, facts, pane);
  } catch (error) { pane.append(h('p', {class: 'failed', role: 'alert'}, error.message)); }
}
/* A layer in the provenance list, chosen to show how it was made. */
const provButton = layer => h('button', {'aria-pressed': String(layer.name === provLayer),
  style: {'--c': `var(${colorVar(layer.name)})`}, onclick: () => { provLayer = layer.name; renderProv(); }},
h('span', {style: {display: 'flex', gap: '8px', 'align-items': 'center'}}, h('i', {class: 'sw'}), layer.name),
h('span', {class: 'pill'}, layer.kind));
/* What the layer's provenance record adds: its facts, its prompt's version to open, and the prompt as delivered. */
function provenanceOf(record, facts, pane) {
  const reports = (record.refs || []).map(ref => `${ref.key}: ${ref.value}`);
  facts.append(...[['workflow', record.workflow], ['model', record.model], ['role', record.role],
    ['blinded', record.blinded === null ? '' : record.blinded ? 'yes' : 'no'],
    ['reports', reports.join(' · ') || 'none']]
    .flatMap(([key, value]) => [h('dt', {}, key), h('dd', {}, value || 'not recorded')]));
  const version = record.prompt_version;
  if (version) {
    pane.append(h('div', {class: 'toolbar'}, h('button', {class: 'btn primary open-prompt', type: 'button',
      onclick: () => { showTab('prompt'); renderPrompt(version.name, version.number); }},
    `Open prompt ${version.name}, version ${version.number}`)));
  }
  if (record.prompt) {
    pane.append(h('details', {}, h('summary', {class: 'eyebrow'}, 'The prompt as it was delivered'),
      h('pre', {class: 'prompt'}, record.prompt)));
  }
}
