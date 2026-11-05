# Bounded legacy colors

`scripts/reference_colors.py` creates a separate color-adaptable copy of the
recognized older family: `#stage`, identified `section.slide` children,
`.theme-lab#theme-lab`, `#theme-select`, `#theme-color` and its complete legacy
color-variable roster. Unknown families, native SlideFactory inputs, repeated
adaptation and the same source/output path are rejected. This is an optional
colors-only operation, not a general HTML importer or editor upgrade.

```bash
python3 /path/to/slidefactory/scripts/reference_colors.py /private/input.html --output /private/colors.html --scheme cyan-dark
```

The palettes come from the packaged complete starter; optionally specify
`--schemes-template /chosen/native-template.html`. The result retains old
navigation/editor/save behavior. Native `deck.py` does not edit it; inspect that
family's actual saved DOM/editor-state behavior before subsequent agent changes.
Never copy private inputs/outputs/assets into this reusable package.

The helper changes palette controls, semantic CSS roles and supported SVG draw
paints while checking unchanged slide bytes, note templates, embedded data URL
references and existing IDs. Raster pixels, fonts and intentional white image
mattes remain unchanged. Stylesheet `fill`/`stroke` literals are conservatively
preserved because arbitrary CSS selectors can paint masks. Variable-based SVG
paints still follow the palette. Check the real file offline in all chosen schemes
and test its own HTML save/reopen path; source witnesses do not prove legibility.

This limited adapter does not establish correct recoloring for every custom SVG.
In particular, masks inheriting `currentColor` or an ancestor's inline paint need
individual visual inspection/explicit fixed mask paints. This is a future-input
boundary, not a promise to convert arbitrary templates. Native SlideFactory
designs should use palette tokens deliberately and explicit black/white mask
paints as described in [authoring.md](authoring.md).
