---
name: metaform-cut-text-expand
description: Use when ellipsis-cut text must open on click or Enter.
category: development
---

# Cut text opens through the shared `expandCut` helper, never a surface's own toggle

Any Metaform page text cut with an ellipsis opens through `expandCut(container, {row, text, key, kept})` in `page/app/core/expand.js`. Call it once at module load on a static container; it re-marks itself through a ResizeObserver and a MutationObserver, so no call after each draw.

- Only texts whose `scrollWidth` exceeds `clientWidth` get `.cut`, `tabindex=0`, role button and `aria-expanded`. Uncut text takes no click.
- Its click and keydown listeners run in the capture phase and stop propagation. A row with its own Enter action (Edit Toolbar moves a tool on Enter) needs this, or the bubbling handler acts too.
- Text inside a control (button, a, summary, select, input, label) keeps that control's click; its full text becomes the control's title.
- An ID-scoped nowrap rule beats the generic `.unfolded .cut`; give such a surface its own unfolded rule.
- Prove a new surface with a probe that lists each element with computed `text-overflow: ellipsis` whose text is cut, then run it with `expandCut` made a no-op: every listed text must fail.
