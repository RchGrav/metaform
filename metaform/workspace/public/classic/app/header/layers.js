/* Layers: each layer's colour by its position, from the earlier page's header/layers.js. The Layers checklist and
 * the choice of which edges of the project show are not part of this page, so every element is drawn. */
import '/classic/app/adapter.js';  // the part before runs first, so the parts run in the page's order
import {css} from '/classic/app/core/dom.js';
import {S} from '/classic/app/core/reads.js';

/* ---------- layers: color by position ---------- */
const KNOWLEDGE = ['--k1', '--k2', '--k3', '--k4', '--k5', '--k6'];
export function colorVar(layerName) {
  const layer = S.layers.find(item => item.name === layerName);
  if (!layer) return '--intake';
  if (layer.kind === 'base') return '--intake';  // the base layer, kind base, keeps the intake color
  if (layer.kind === 'memory') return '--memory';
  const knowledge = S.layers.filter(item => !['base', 'memory'].includes(item.kind));
  return KNOWLEDGE[knowledge.indexOf(layer) % KNOWLEDGE.length];
}
export const layerColor = name => css(colorVar(name));
/* No edge of the project is hidden on this page. */
export const underHiddenRoot = () => false;
