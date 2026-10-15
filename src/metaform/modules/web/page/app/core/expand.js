/* Text cut short, ending in an ellipsis, opens in place, wrapped, at a click or Enter on it, and folds again the same
 * way; the cursor says it takes the click. Only text that is cut takes it, and a row opened stays open through its
 * list's redraws, kept by the row's key. Text cut inside a control whose click is the control's own, a button that
 * opens or goes somewhere, keeps that click: its whole words are its tooltip, and they are in the control's name.
 *
 * `expandCut(container, {row, text, key, kept})` watches the rows matching `row` in the container, the container
 * itself included, and the texts matching `text` in each. It marks them after every change to what the container
 * holds and every change of its size, and returns the marking for a surface that wants it at once. Called again on
 * the same container, it returns the same marking. */
const CONTROL = 'button, a[href], summary, select, input, textarea, label';
const MADE = new WeakMap();
export function expandCut(container, {row, text, key = one => one.dataset.key, kept = new Set()}) {
  if (MADE.has(container)) return MADE.get(container);
  const rowsIn = node => [...(node.matches(row) ? [node] : []), ...node.querySelectorAll(row)];
  const inControl = (one, at) => { const control = one.parentElement?.closest(CONTROL); return Boolean(control && at.contains(control)); };
  function mark(rows = rowsIn(container)) {
    for (const at of rows) at.classList.remove('unfolded');  // measured folded, the only way to see what is cut
    // every width read before any write, so the page lays out once
    const cut = rows.map(at => [...at.querySelectorAll(text)].map(one => [one, one.scrollWidth > one.clientWidth + 1]));
    rows.forEach((at, index) => {
      const takes = cut[index].filter(([one, isCut]) => isCut && !inControl(one, at));
      const open = takes.length > 0 && kept.has(key(at));
      at.classList.toggle('unfolded', open);
      for (const [one, isCut] of cut[index]) {
        const clicks = isCut && !inControl(one, at), titled = isCut && !clicks && (!one.title || one.dataset.cutTitle);
        one.classList.toggle('cut', clicks);
        if (clicks) {
          one.tabIndex = 0;
          one.setAttribute('role', 'button');
          one.setAttribute('aria-expanded', String(open));
        } else {
          for (const name of ['tabindex', 'role', 'aria-expanded']) one.removeAttribute(name);
        }
        if (titled) { one.title = one.textContent; one.dataset.cutTitle = '1'; }
        else if (one.dataset.cutTitle) { one.removeAttribute('title'); delete one.dataset.cutTitle; }
      }
    });
  }
  function toggle(event) {
    const one = event.target.closest?.('.cut'), at = one?.closest(row);
    if (!at || !container.contains(one)) return;
    if (event.type === 'keydown' && event.key !== 'Enter' && event.key !== ' ') return;
    if (event.type === 'click' && String(getSelection())) return;  // a drag that chose text to copy is not a click
    event.preventDefault();
    event.stopPropagation();  // the row's own Enter, or its own click, is not this one's
    if (!kept.delete(key(at))) kept.add(key(at));
    mark([at]);
  }
  // first, before the rows' own keys and clicks
  container.addEventListener('click', toggle, true);
  container.addEventListener('keydown', toggle, true);
  new ResizeObserver(() => mark()).observe(container);
  // a redraw marks only the rows it touched, so a thread that streams measures the row that grew, not the thread
  new MutationObserver(records => {
    const rows = new Set();
    for (const record of records) {
      const at = (record.target.nodeType === 1 ? record.target : record.target.parentElement)?.closest(row);
      if (at && container.contains(at)) rows.add(at);
      for (const node of record.addedNodes) if (node.nodeType === 1) for (const one of rowsIn(node)) rows.add(one);
    }
    if (rows.size) mark([...rows]);
  }).observe(container, {childList: true, subtree: true, characterData: true});
  MADE.set(container, mark);
  return mark;
}
