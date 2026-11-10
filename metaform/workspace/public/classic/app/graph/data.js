/* What the map code asks of the graph's data, from the earlier page's graph/data.js. The nodes and links that file
 * built were the 3D map's, which is not part of this page. */
import '/classic/app/header/menus.js';  // the part before runs first, so the parts run in the page's order
import {S} from '/classic/app/core/reads.js';

/* A node's name with the count of the parts it holds beneath it, VIEW-051. */
export const heldName = (name, held) => held ? `${name} +${held}` : name;
/* Each element's open work as the map shows it: its own, then that of the joins it receives, which have no node of
 * their own to show it on; worked out once for a whole drawing. */
export function workShown() {
  const shown = new Map();
  for (const {element} of S.elements.values()) shown.set(element.id, element.open_work || []);
  for (const join of S.joins) {
    const own = shown.get(join.receiver), work = join.open_work;
    if (!own || !work?.length) continue;
    shown.set(join.receiver, [...new Set([...own, ...work])]);
  }
  return shown;
}
/* A selection is an element's id or a join as 'p:<id>'. */
/* A join as the map code holds it: `providers` are the ids of every element it holds, each a provider;
 * `provider` and `provider_address` name the first, the one that names the join beside its receiver. */
export const withProviders = join => ({...join, providers: (join.elements || []).map(each => each.element_id),
  provider: join.elements?.[0]?.element_id, provider_address: join.elements?.[0]?.address});
export const joinOf = key => S.joins.find(join => 'p:' + join.id === key);
/* The Address a selection stands for: an element's own, or for a join its receiving element's. */
export const addressOf = id => {
  const join = id.startsWith('p:') ? joinOf(id) : null;
  return join ? join.receiver_address : S.elements.get(id)?.element.address;
};
