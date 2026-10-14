/* Metaform's web GUI, the viewer: the whole map in 3D and in 2D, kept in sync, and the selected object below.
 * Every piece of data comes from the server's reads, VIEW-004; the page never decides what is visible. Text from the
 * store is always set as text, never as HTML, VIEW-009.
 * The page's script is in parts, page/app/<area>/<part>.js, each one area of the page, in the order the page was
 * written. Each part imports the part before it first, and this file imports the last, so the parts run in that
 * order whatever else they import from each other: what a part does as it loads can rely on every part before it.
 * A new part goes into that chain, imported first by the part after it. */
import {main} from '/page/app/workspace/workspace.js';

main();
