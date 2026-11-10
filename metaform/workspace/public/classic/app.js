/* The earlier Metaform page's 2D map and 3D map, on the new Metaform server. The page's script is in parts, app/<area>/<part>.js,
 * as the earlier page's was. Each part imports the part before it first, and this file imports the last, so the parts
 * run in one order whatever else they import from each other. adapter.js is the one part that reads the server. */
import {main} from '/classic/app/loading/load.js';

window.METAFORM_SURFACE = true;  // the page's code ran, theme.js
main();
