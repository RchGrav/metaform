# Source attribution

`src/metaform/modules/_imagegen.py` is the unmodified `imagegen.py` from
`imagegen.zip` in RchGrav/tempo at commit
`1bf06068d1d7baf435555b0b0b2e59817850c61b`.
SHA-256: `c425491dd64399eef74db429b32fa877bd8158ee248320e8fb8d70cadafdbd65`. The new module wrapper uses its validation, prompt construction,
capability probing, and generation implementation.

The imported intake and core documents use this repository's Metaform naming in
`src/metaform/data/semantics/*.source.md`. The former name's etymology paragraph
was removed. The C++ namespace examples were corrected to `code.cpp`, with the
intervening `language` level retained as an explicitly bad inference. Local paths, original source
commits and hashes, and authority notes are recorded in `sources.json`.
Active definitions select current user statements over conflicting historical
entries. The active EN/ED glossary now uses the established rulebook sentences
verbatim. `aliases.md` is the exact Aliases section from
`docs/semantics/inference_metaform_rules.md`. Rule seed provenance is recorded in
`docs/rulebook/seed-sources.md`.

All new chassis code is specific to this repository. No license grant or
publication to a package index is added on the owner's behalf.

## Solid Glass

The Glass and Tinted Glass themes of the web page (`src/metaform/modules/web/page/app.css`, their token blocks and
"The glass material") are adapted from Solid Glass by deeplethe, https://github.com/deeplethe/solid-glass: its light
and dark colors, converted from OKLCH to the page's tokens, and its rules for the material (the rim, the hairline and
the shadow at a pane's edge, thickness by elevation, one state). It is used under the MIT License:

> MIT License
>
> Copyright (c) 2026 DeepLethe
>
> Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
> documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
> rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
> permit persons to whom the Software is furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all copies or substantial portions of
> the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
> WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
> COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
> OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
