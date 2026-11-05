# Package layout and use in a new engagement

Date: 2026-10-14. Implemented package and shared editor rewrite; user-level installation complete.
See the [solution](solution-sketch.md) and [editor behavior](editor-experience.md).

## One central repository

```text
SlideFactory/
  skills/slidefactory/
    SKILL.md
    agents/openai.yaml
    assets/consulting.html            complete consulting deck INCLUDING editor
    assets/editorial.html  independent editorial design, same editor
    assets/consulting-blank.html              empty consulting design, same editor
    assets/editorial-blank.html    empty editorial design, same editor
    assets/editor-releases.json    trusted helper-side resource fingerprints
    references/                   HTML contract, focused operations, checks
    scripts/deck.py                stdlib-only checked file helper
  src/editor/                     shared document/interaction/image/UI source
  src/designs/                    independent styles and four token palettes
  src/templates/                  neutral whole-deck layout examples
  scripts/build-starter.mjs        one-file assembly; optional build-only minifier
  tests/                          real browser/download + source-edit checks
  docs/                           contracts, decisions and evidence
```

The skill folder is self-contained and can be copied as a unit. A new engagement
needs a ready template, not a runtime build or a repository clone with developer
dependencies. Maintaining editor source requires the repo; authoring a deck does
not. `npm ci` installs the build-only minifier; `npm run build` embeds the shared
runtime/styles/assets into the ready HTMLs. An isolated package build without
the minifier produces readable, larger files. Opening or using a deck needs
neither Node nor these development dependencies.
A deck keeps its embedded editor version; `deck.py upgrade-editor` updates known
common resources into a new complete HTML while retaining the source. The registry
is helper-side tooling; the resulting presentation needs no companion file.

## Invocation in a new local chat

The user requested installation after the first package was delivered. The
installed entry `~/.agents/skills/slidefactory` links to this package, so
`$slidefactory` is available across local projects and follows source updates.
Explicit-path invocation below remains useful without installing the package.

Start the chat in the private engagement's work folder and say:

> Read `<repo>/skills/slidefactory/SKILL.md`.
> Use `/path/to/the/chosen/template.html` as the design starting point.
> Create `presentation.html` here for this audience, objective and content.

The agent gives a new deck fresh identity, authors the story and individual
compositions, and returns **one complete HTML**. No app or new repository is
required. The user opens it, edits, selects a color scheme, leaves guidance and
uses `HTML speichern`. Next chat turn names that downloaded current file.
Ordinary revision works directly on it; the starter is not applied again.

## Authority and responsibilities

- Skill: reusable method and resource entry point; individual visual reasoning.
- Ready template: whole-deck starting file with examples, styles and editor embedded.
- Shared source: maintenance of browser interaction/save and neutral design examples.
- Private engagement HTML: current saved content, layout, assets, notes and guidance.

Browser drafts are a convenience guarded by original source/revision. Saved
HTML is the shared authority. The agent helper inspects/extracts only affected
sections and makes validated atomic edits, preserving other source bytes. A
fragment is temporary agent tooling, never a file the user opens per slide.

Additional designs can adopt the same markers/runtime with their own CSS/layouts;
color tokens remain independent. There is no template-selection UI. Private older
HTML families require a deliberate bounded adaptation; arbitrary import is not
promised by the schema-1 helper.
