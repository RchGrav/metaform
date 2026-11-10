// Small helpers that make SVG elements for the renderer.

export const SVG = "http://www.w3.org/2000/svg";

/** Gives an SVG element its hover meaning: every mark is explained. */
export function tip<T extends Element>(element: T, ...lines: string[]): T {
  const title = document.createElementNS(SVG, "title");
  title.textContent = lines.join("\n");
  element.insertBefore(title, element.firstChild);
  return element;
}

/** Makes an SVG element with these attributes and appends it to `parent`. */
export function el<K extends keyof SVGElementTagNameMap>(
  name: K,
  attrs: Record<string, string | number> = {},
  parent?: Element,
): SVGElementTagNameMap[K] {
  const node = document.createElementNS(SVG, name);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
  parent?.appendChild(node);
  return node;
}
