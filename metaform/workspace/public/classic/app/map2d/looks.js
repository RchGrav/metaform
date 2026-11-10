/* An element's shape and colour on the map, from the earlier page's map3d/light.js, which drew the 3D map. */
import {css} from '/classic/app/core/dom.js';
import {layerColor} from '/classic/app/header/layers.js';

/* An element's artifact type, the first segment of its address, where the map draws that type in a shape of its own,
 * `SHAPES2D`. */
const TYPE_ROOTS = ['code', 'document', 'media', 'data', 'collection', 'upstream', 'downstream'];
export const typeOf = node => {
  const root = String(node?.address || '').split('.')[0];
  return TYPE_ROOTS.includes(root) ? root : null;
};
/* An element's own colour, for what flows from it. The earlier map gave the signal colour to those the project serves
 * and a colour of its own to the map's entry; here those are the elements under `downstream` and the Definitive
 * element. Every other element has its layer's colour. */
export function colorOf(element) {
  if (String(element.address).split('.')[0] === 'downstream') return css('--signal');
  return element.role === 'Definitive' ? css('--de') : layerColor(element.layer);
}
