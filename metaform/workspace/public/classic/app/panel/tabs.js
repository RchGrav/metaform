/* The side column's tabs, from the tabs part of the earlier page's panel/prompts.js. The Prompt tab and the tabs as
 * a workspace arranges them, which that file also held, are not part of this page. */
import '/classic/app/panel/provenance.js';  // the part before runs first, so the parts run in the page's order
import {$} from '/classic/app/core/dom.js';
import {renderBrief} from '/classic/app/panel/brief.js';
import {renderProv} from '/classic/app/panel/provenance.js';

/* ---------- tabs ---------- */
/* The panel's tabs, as tabs are: the open one is in the Tab order, and Left and Right move between them. */
const TABS = {object: '#p-object', brief: '#p-brief', prov: '#p-prov'};
export const tabNow = () => Object.keys(TABS).find(key => $('#t-' + key).getAttribute('aria-selected') === 'true')
  || 'object';
export function showTab(tab) {
  openPane(tab);
  if (tab === 'prov') renderProv();
  if (tab === 'brief') renderBrief();
}
/* The tab's pane shown and the tab marked open, the others hidden and taken out of the Tab order. */
function openPane(tab) {
  for (const [key, selector] of Object.entries(TABS)) {
    $(selector).hidden = key !== tab;
    $('#t-' + key).setAttribute('aria-selected', String(key === tab));
    $('#t-' + key).tabIndex = key === tab ? 0 : -1;
  }
}
for (const key of Object.keys(TABS)) $('#t-' + key).onclick = () => showTab(key);
function walkPanelTabs(event) {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
  event.preventDefault();
  const keys = [...$('.tabs[role=tablist]').children].filter(tab => !tab.hidden).map(tab => tab.id.slice(2));
  const at = keys.findIndex(key => $('#t-' + key).getAttribute('aria-selected') === 'true');
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? keys.length - 1
    : (at + (event.key === 'ArrowRight' ? 1 : -1) + keys.length) % keys.length;
  showTab(keys[next]);
  $('#t-' + keys[next]).focus();
}
$('.tabs[role=tablist]').addEventListener('keydown', walkPanelTabs);
