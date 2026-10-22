/* Explicit ticket delivery is local. Request state survives card redraws and is shared with the inspector. */
import {h, fill} from '/page/app/core/dom.js';
import {S, read} from '/page/app/core/reads.js';
import {posted} from '/page/app/intake/intake.js';

const REQUESTS = new Map();
const keyOf = (scope, workId) => JSON.stringify([scope.project, scope.base || '', workId]);

function paint(box, integration, state, scope, workId) {
  box.dataset.head = integration?.head || '';
  const action = integration?.action;
  const busy = state.busy || Boolean(integration?.busy);
  const message = state.error || integration?.reason || '';
  fill(box,
    action === 'merge' || action === 'cleanup' ? h('button', {
      class: `btn sm primary ticket-${action}`, type: 'button', disabled: busy,
      title: action === 'cleanup' ? 'Remove the safely integrated ticket worktree'
        : 'Merge saved ticket changes into the local checkout, clean its worktree, then finish the ticket',
      onclick: event => {
        event.stopPropagation();
        integrate(scope, workId, integration, state);
      },
    }, state.busy ? action === 'cleanup' ? 'Cleaning worktree…' : 'Merging…'
      : action === 'cleanup' ? 'Clean worktree' : 'Merge') : null,
    message ? h('p', {class: 'integration-reason', role: state.error ? 'alert' : 'status'}, message) : null);
}

function repaint(scope, workId, integration, state) {
  const key = keyOf(scope, workId);
  for (const box of document.querySelectorAll('.ticket-integration')) {
    if (box.dataset.integration === key) paint(box, integration, state, scope, workId);
  }
}

async function integrate(scope, workId, integration, state) {
  if (state.busy || integration.busy) return;
  state.busy = true;
  state.error = '';
  repaint(scope, workId, integration, state);
  try {
    const result = await posted('/api/ticket-merge', {...scope, work_id: workId, head: integration.head});
    if (!result.ok) state.error = result.body.why || result.body.error || 'Ticket changes could not be merged.';
    else {
      state.error = result.body.why || '';
      if (result.body.merged) integration = {...integration, merged: true, busy: false,
        action: result.body.cleanup?.state === 'complete' ? null : 'cleanup',
        reason: result.body.cleanup?.reason || result.body.why || '', cleanup: result.body.cleanup || null};
    }
    // Read once after the action. Replace only delivery controls so unsaved ticket text stays intact.
    try {
      const found = await read('ticket-detail', {...scope, work_id: workId});
      integration = found.ticket.integration || null;
      for (const box of document.querySelectorAll('.ticket-integration')) {
        if (box.dataset.integration === keyOf(scope, workId)) {
          box.dispatchEvent(new CustomEvent('integration:refreshed', {detail: found}));
        }
      }
    } catch (error) {
      state.error = [state.error, error.message].filter(Boolean).join(' ');
    }
  } finally {
    state.busy = false;
    repaint(scope, workId, integration, state);
  }
}

export function ticketIntegration(ticket, scope = {project: S.project, base: S.base || ''}, refreshed = null) {
  const key = keyOf(scope, ticket.id);
  let state = REQUESTS.get(key);
  if (!state) {
    state = {busy: false, error: ''};
    REQUESTS.set(key, state);
  }
  const box = h('div', {class: 'ticket-integration', 'data-integration': key,
    onclick: event => event.stopPropagation()});
  if (refreshed) box.addEventListener('integration:refreshed', event => refreshed(event.detail));
  paint(box, ticket.integration, state, scope, ticket.id);
  return box;
}
