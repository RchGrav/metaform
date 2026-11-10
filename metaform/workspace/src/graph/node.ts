// Draws one element of the graph: its box, its label, its marks and its chevron.

import type { Address } from "../source/types";
import { graph as text, layers as layerText, legend, presence } from "../strings";
import { type Box, HEADER } from "./layout";
import type { RenderNode } from "./renderer";
import { depth as depthText } from "./strings";
import { el, tip } from "./svg";

/** Layer mark shapes, by style index, so marks do not depend on colour alone. */
const SHAPES = ["square", "circle", "diamond", "triangle"] as const;

/** "<label>, <role>, <N> elements beneath" (renderer rule 3); in the functional graph, the hidden elements it holds. */
function accessibleName(node: RenderNode, functional: boolean): string {
  if (functional) return depthText.nodeName(node.label, node.role, node.collapsed ? node.beneath : 0);
  return text.nodeName(node.label, node.role, node.beneath);
}

/** The address a node sits in: its address without the last segment ("." at the top). */
function containerOf(address: Address): string {
  const cut = address.lastIndexOf(".");
  return cut < 0 ? "." : address.slice(0, cut);
}

/**
 * Draws one element in `parent` and returns its group. `container` is true for an expanded
 * element that holds others in the picture. `functional` is true in the functional graph, where
 * the count is of hidden elements. `onChevron` is called when the chevron is activated.
 */
export function drawNode(node: RenderNode, box: Box, container: boolean, parent: SVGGElement, functional: boolean, onChevron: (address: Address) => void): SVGGElement {
  const classes = ["mf-node", `mf-band-${node.band}`, `mf-role-${(node.role ?? "none").toLowerCase()}`];
  if (functional) classes.push("mf-flat");
  if (node.status === "un_built") classes.push("mf-unbuilt");
  if (container) classes.push("mf-container");
  if (node.selected) classes.push("mf-selected");
  if (node.focus) classes.push("mf-focus");
  if (node.definitive) classes.push("mf-definitive");
  if (node.dimmed) classes.push("mf-dimmed");
  if (node.beneath > 0 && node.collapsed) classes.push("mf-collapsed");
  const g = el("g", {
    class: classes.join(" "), "data-address": node.address, tabindex: 0, role: "button",
    "aria-label": accessibleName(node, functional), transform: `translate(${box.x},${box.y})`,
  }, parent);
  if (node.selected) g.setAttribute("aria-pressed", "true");
  if (node.beneath > 0 && node.collapsed && !container) {
    tip(el("rect", { class: "mf-stack", x: 5, y: 5, width: box.width, height: box.height, rx: 6 }, g), functional ? depthText.stackTip : legend.stack);
  }
  el("rect", { class: "mf-box", width: box.width, height: box.height, rx: 6 }, g);
  if (node.definitive) tip(el("rect", { class: "mf-definitive-ring", x: 3, y: 3, width: box.width - 6, height: box.height - 6, rx: 4 }, g), legend.definitive);
  tip(el("rect", { class: "mf-role-bar", width: 4, height: container ? HEADER : box.height, rx: 2 }, g), legend.roleBar);
  // Row 1: the label, and the chevron at the right. Row 2: layer marks at the left; the wants
  // that leave the container and the count beneath at the right (nodeWidth sizes both rows).
  const row1 = container ? HEADER / 2 + 5 : 23;
  const row2 = container ? HEADER / 2 + 5 : 43;
  const label = el("text", { class: "mf-label", x: 16, y: row1 }, g);
  // Functionality that is intended and not built yet is drawn faint, with the words on it
  // (the earlier interface drew a missing node ghostly, at 70%).
  if (node.status === "un_built" && !container) {
    el("text", { class: "mf-status", x: box.width - 12, y: 43, "text-anchor": "end" }, g).textContent = text.notBuilt;
  }
  // A name longer than its box is cut with an ellipsis; the whole name is in the tooltip.
  const room = Math.max(4, Math.floor((box.width - 32) / 8.6));
  label.textContent = node.label.length > room ? `${node.label.slice(0, room - 1).trimEnd()}…` : node.label;
  if (node.label.length > room) tip(label, node.label);
  let right = box.width - 16;
  if (node.beneath > 0) {
    const chevron = el("g", {
      class: "mf-chevron", role: "button", tabindex: -1,
      "aria-label": functional ? depthText.chevronLabel(node.label, node.collapsed) : text.beneathLabel(node.beneath, node.address),
      "aria-expanded": String(!node.collapsed),
      transform: `translate(${right - 12},${row1 - 11})`,
    }, g);
    tip(chevron, functional ? (node.collapsed ? depthText.chevronOpen : depthText.chevronClose) : legend.chevron);
    el("rect", { width: 16, height: 16, rx: 3, class: "mf-chevron-hit" }, chevron);
    el("path", { d: node.collapsed ? "M6,4 L11,8 L6,12" : "M4,6 L8,11 L12,6", class: "mf-chevron-mark" }, chevron);
    chevron.addEventListener("click", (event) => {
      event.stopPropagation();
      onChevron(node.address);
    });
    if (container) right -= 24;
  }
  const badgeRight = right + (container || node.beneath === 0 ? 0 : 4);
  // An expanded element shows the elements beneath it, so its header does not also count them.
  // In the functional graph the count is of hidden elements, so an open element shows none.
  const counted = node.beneath > 0 && !container && (!functional || node.collapsed);
  const badgeText = functional ? depthText.hiddenBadge(node.beneath) : text.beneathBadge(node.beneath);
  if (counted) {
    const badge = el("text", { class: "mf-beneath", x: badgeRight, y: row2, "text-anchor": "end", "aria-hidden": "true" }, g);
    badge.textContent = badgeText;
    tip(badge, functional ? depthText.hiddenTip : legend.beneath);
  }
  if (node.outside > 0) {
    const shift = counted ? (badgeText.length * 6.4 + 12) : 0;
    const out = el("text", {
      class: "mf-outside", x: badgeRight - shift, y: row2, "text-anchor": "end",
      "aria-label": text.wantsOutsideLabel(node.outside, containerOf(node.address)),
    }, g);
    out.textContent = text.wantsOutside(node.outside);
    tip(out, legend.outside);
  }
  let x = container ? 16 + node.label.length * 7.8 + 12 : 16;
  for (const mark of node.layers) {
    const shape = SHAPES[mark.style % SHAPES.length] ?? "square";
    const m = el("g", { class: `mf-layer mf-layer-${mark.style % 8}`, transform: `translate(${x},${row2 - 4})` }, g);
    tip(m, layerText.mark(mark.layer, mark.records), legend.layerMark);
    if (shape === "circle") el("circle", { cx: 3.5, cy: 0, r: 4 }, m);
    else if (shape === "diamond") el("path", { d: "M3.5,-4.5 L8,0 L3.5,4.5 L-1,0 z" }, m);
    else if (shape === "triangle") el("path", { d: "M3.5,-4.5 L8,4 L-1,4 z" }, m);
    else el("rect", { x: 0, y: -3.5, width: 7, height: 7 }, m);
    const count = el("text", { class: "mf-layer-count", x: 11, y: 4 }, m);
    count.textContent = String(mark.records);
    x += 18 + String(mark.records).length * 6.4;
  }
  // Agents sit on the top border near the left corner: wants between bands attach at the
  // sides, and wants within a band attach spread along the middle of the top and bottom.
  node.agents.forEach((agent, i) => {
    const a = el("g", { class: `mf-agent${agent.active ? " mf-agent-active" : ""}`, transform: `translate(${22 + i * 20},0)` }, g);
    // Who is here, and doing what, answers "MA?"; the circle's general meaning is in the legend
    // panel (Matthew, climb step 1). Without a name, the general meaning stands in.
    const who = agent.name ? presence.at(agent.name, node.address, agent.doing ?? undefined) : legend.agent;
    tip(a, who, agent.active ? legend.agentActive : legend.agentIdle);
    el("circle", { r: 9 }, a);
    const initials = el("text", { "text-anchor": "middle", y: 3.5 }, a);
    initials.textContent = agent.initials;
  });
  if (node.unseen) tip(el("circle", { class: "mf-unseen", cx: 0, cy: 0, r: 4.5 }, g), legend.unseen);
  if (node.opensProject) {
    const link = el("g", { class: "mf-project-link", transform: `translate(${16 + node.label.length * 7.8 + 6},${row1 - 10})` }, g);
    tip(link, legend.projectLink);
    el("path", { d: "M2,10 L10,2 M5,2 L10,2 L10,7" }, link);
  }
  return g;
}
