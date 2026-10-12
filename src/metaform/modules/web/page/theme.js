/* The theme chosen in this browser, applied before the page is drawn, VIEW-023. */
'use strict';
try { document.documentElement.dataset.theme = localStorage.getItem('metaform.theme') || 'space'; }
catch (error) { document.documentElement.dataset.theme = 'space'; }  // storage can be blocked; the page opens in space
/* The text size chosen in this browser, VIEW-023: the factor every size token of the page is drawn at, applied before
 * the page is drawn so it opens at that size. */
try {
  const size = Number(localStorage.getItem('metaform.textSize'));
  if (size >= 0.75 && size <= 1.75) document.documentElement.style.setProperty('--ui', String(size));
} catch (error) { /* storage can be blocked; the page opens at the default size */ }
/* The page stays out of sight until it is laid out as this browser left it, side column, swap, sizes and the map
 * drawn, so a reload never shows another layout first; it fades in once, `revealed` in app.js, or after four seconds
 * whatever happens. */
document.documentElement.classList.add('booting');
setTimeout(() => document.documentElement.classList.remove('booting'), 4000);
