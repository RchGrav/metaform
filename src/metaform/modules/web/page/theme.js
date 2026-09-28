/* The theme chosen in this browser, applied before the page is drawn, VIEW-023. */
'use strict';
try { document.documentElement.dataset.theme = localStorage.getItem('metaform.theme') || 'space'; }
catch (error) { document.documentElement.dataset.theme = 'space'; }  // storage can be blocked; the page opens in space
