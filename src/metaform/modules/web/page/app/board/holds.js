/* Every deliberate hold records its own reason, separate from the ticket's general notes. */
import {h} from '/page/app/core/dom.js';
import {toast} from '/page/app/core/controls.js';

export function requestHoldReason() {
  const reason = window.prompt('Please explain why this ticket is on hold. State whether it is unsafe to unhold, and why.');
  if (reason === null) return null;
  if (!reason.trim()) { toast('Enter a reason for this hold.'); return null; }
  return reason.trim();
}

export function holdReason(ticket) {
  const held = ticket.held || ticket.hold || ticket.map?.hold;
  const reason = ticket.hold_reason || ticket.map?.hold_reason;
  if (!held && !reason) return null;
  return h('p', {class: 'hold-reason'}, held
    ? (reason ? `Hold reason: ${reason}` : 'Held: no reason was recorded.')
    : `Last hold reason: ${reason}`);
}
