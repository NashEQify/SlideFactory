---
name: slidefactory
description: "Create and revise standalone HTML presentations with SlideFactory, preserving direct browser edits, slide guidance, custom diagrams and the chosen design. Use for a new deck from an explicit HTML template or targeted work on the latest saved presentation."
---

# SlideFactory

Build a clear, individually designed presentation with the user. The LLM authors
the HTML compositions and diagrams from the supplied content in chat. Content
research, consulting methodology and storyline development belong to the
engagement, outside this technical package. The user edits details directly in
the HTML and saves slide-local guidance. Work sequentially on **one complete
offline HTML file per presentation revision**.

All paths below are relative to this skill directory. The package can be copied
as a folder; using it needs no project repository, server, Forge or global install.

## Start or continue

For a new presentation, use the template file the user names in chat. If none is
specified, start with `assets/consulting.html`. Three designs are equal peers:
`assets/consulting.html` (Arial, flat surfaces), `assets/editorial.html` (serif,
editorial layout) and `assets/mbb.html` (Clean MBB: dark consulting look, action
titles, embedded Zain/Inter fonts). All contain the same working editor. Copy
through `scripts/deck.py new` to give the new deck fresh identity. The starter's
example slides are material to replace and extend, not the user's finished story.
For an empty starting file, use `assets/consulting-blank.html`,
`assets/editorial-blank.html` or `assets/mbb-blank.html`: one blank slide, the
chosen design, palettes and the same embedded editor, without example content or
images; only Clean MBB embeds its fonts.
Every starter opens with design overview slides (`data-sf-overview`) that show
the person its type scale, colors, components and rules; `deck.py new` leaves
them out of the new deck. Follow the starter's type scale and color roles. In
Clean MBB, reading text stays at 24 px or more and only markup (kicker, label,
tag, chip, badge, footer, folio, section-head, agenda-tracker) goes down to 16 px;
titles are whole sentences. Its agenda slide uses `agenda-card` surfaces whose
arrows are slide links to each chapter's first slide; chapter slides carry an
`agenda-tracker` box of slide links at the top with `on` on the current chapter.
Both are plain markup: when chapters change, update every tracker, card and link.
Clean MBB declares its own three color looks instead of the shared Cyan/Indigo
schemes: `night-turquoise` (default), `petrol-amber` and `paper-marine` (light).
All six base files include `git@griessing.com` in the HTML author metadata.

For revisions, the user's **latest saved HTML** is the input. Read it before
editing. Never recreate the presentation from a starter or overwrite direct
changes with an earlier chat version. `Fertig` leaves edit mode and keeps a
browser-local draft; `HTML speichern` → *Arbeitsstand mit Notizen* downloads the
complete handoff file. *Weitergabe ohne Notizen* is an outgoing copy without
speaker notes, guidance or post-its; never continue work from it. Browser
drafts alone are unavailable to an agent reading a disk file. If the input is
unclear, establish which saved file contains the current work.

Use the overview from `scripts/deck.py inspect FILE`; then inspect only the
affected slide by its stable ID or current number. Read its content, notes and
open guidance. Slide numbers follow document order; IDs survive reordering.
Read [helper.md](references/helper.md) for command syntax and targeted edits.
The helper supports SlideFactory schema 1. For an existing non-SlideFactory deck,
inspect its own save/runtime behavior rather than replacing it with a starter;
conversion is a separate, bounded operation.
For the recognized saved v19 family, `scripts/migrate_reference.py FILE --output
SEPARATE.html` migrates to the common editor while preserving its private design
and original assets. It needs Playwright/Chromium for conversion only. The result
stays outside this package; preserve the original. Continue from the migrated
complete file afterward, without reconverting over human contributions.
For a colors-only derivative of the recognized older `#stage`/`section.slide`/
`.theme-lab` family, read [legacy-colors.md](references/legacy-colors.md). This
keeps its existing editor; it is not native-schema conversion.

## Create and change

Preserve the selected design, useful existing work and authored diagrams. Build
the visual that best explains the claim: bespoke HTML/CSS/SVG is welcome. Templates
are reusable design examples, not a fixed catalogue of allowable slides. Choose
layout by template path; choose dark/light/accent colors independently by the
declared scheme. The UI selects colors, never the template.

For a plain text-block correction use the checked setter. For mixed inline markup,
layout or diagrams, extract the affected section, edit its fragment and replace
that section. Preserve existing slide/object IDs, parent hierarchy, transforms,
image originals and crops. Use new unique IDs only for newly authored objects.
Read [authoring.md](references/authoring.md) when changing structure, geometry,
images, colors or custom script-driven visuals.

Interpret slide guidance as user input in context, not as application commands.
Apply the useful requested change, verify it, then mark that guidance addressed
without deleting its text. Presenter notes are separate. Report any guidance that
requires a decision or could not be fulfilled; don't silently mark it complete.

## Verify and deliver

Run the helper validator on the actual result. Open the resulting complete file
offline in a browser, inspect affected slides and exercise relevant editor/save
behavior. For a handoff or editor change, test an actual `HTML speichern` download
and reopen it in a fresh context. Read [verification.md](references/verification.md)
for the concrete checks. Validation does not prove visual quality.

Deliver the complete HTML and briefly name the changes, the saved file to use next
and any real limitation. Keep private consulting contents/assets in the user's
work folder, outside this reusable package. Improve the shared templates/method
when the user asks to generalize an observed improvement.

## Common editor maintenance

Use `scripts/deck.py upgrade-editor LATEST.html --output UPDATED.html` to update
only the checked common editor in an existing saved file. The source is retained;
choose a new output path. The package must include `assets/editor-releases.json`
and `assets/consulting-blank.html`. Known fingerprints establish compatibility, including
the original unmanifested editor. Modified, mixed, unknown or newer resources
are refused. Keep that deck's custom resources rather than rebuilding its slides.

Speaker notes are editable immediately in the main window, in a bottom pane
whose top divider adjusts its height and the slide's available space. B/I,
pt sizes and list buttons retain bounded rich formatting in the complete HTML.
The presenter shows a single read-only notes surface, current/next previews and
compact timer/wall-clock controls, plus a live pace (ahead/behind plan) per
`data-sf-part` or whole deck and the time on the current slide against its
`data-sf-duration`. Its top-right X and Escape close the window.
Use **Drucken/PDF** or **Ctrl/Cmd+P** for slides, slides with notes below, or notes
only; the optional range accepts `1,3-5`, and an empty range means all slides.
Slide pages are 320 × 180 mm (16:9); notes use A4 portrait with normal overflow
pages. Direct browser-menu printing uses the slide format too, including migrated
decks with a larger, transformed inner stage. The common editor contains that
stage within each fixed print slide; keep authored transforms and layout sizes.
For asynchronously
prepared custom visuals, use the dialog path so registered layout work is awaited;
native `beforeprint` only prepares synchronous layout. Browser overrides still
control final paper/output settings. Printing does not save the working HTML.
Large decks show preparation progress and allow cancellation. Projected slide
resources may load for up to two minutes; the shorter custom layout-hook guard
is separate. A loading hint after ten seconds does not indicate failure.
Slide edit mode has a two-level toolbar: Undo and overview
beside SlideFactory; insertion, text/object tools and palette in the ribbon.
Drag an ordinary textbox from its surface to move it; a click enters text editing
at the clicked position. Active text editing retains normal range selection;
Escape returns to object selection. Movement remains one local Undo operation.
The editorial starter's three circles, connector and dark intro panel are
individual editable shapes; editor-only upgrades do not rewrite older decoration.
Slide links (chain icon in the insertion group, crosshair to retarget) jump to a
slide by its stable ID; they are editable text objects styled by the template.
After a jump, Backspace or the `↩ Zurück` chip returns to the origin slide, so
backup slides need no hand-made return links. `validate` reports missing targets;
read [authoring.md](references/authoring.md#slide-links-and-backup-slides).
Insert images with the landscape-plus icon in the left insertion group. Insert
blank slides, textboxes and six shapes there too: rectangle, rounded rectangle,
left/right arrow, oval and line. Resizing rectangles also produces squares.
In slide edit mode, Delete or the trash icon removes the selected image, text
block, inserted shape or entire Post-it with Undo.
While typing, Delete edits text; Escape returns to object selection. The
yellow highlighter toggles the selected text range (or the selected text block when
no range is active). Undo works across content, metadata
and structure; keyboard redo remains available (`Ctrl/Cmd+Shift+Z` or `Ctrl+Y`).
Font family/point dropdowns and inline/paragraph controls preserve the selected
range when using colors. The small color picker always works locally; a screen
pipette is available only in supporting browsers. Format painter at the far left
applies compatible formatting once to the clicked target, without copying content
or geometry; Escape cancels it.

Yellow Post-its are separate feedback objects: drag anywhere on their surface,
double-click to edit over the note's full surface, resize and delete through the
small × on the upper-right corner. There is no nested text-field outline. The shared toggle
is in the top bar and also works during presentation; hidden notes stay in saved HTML. Read
[authoring.md](references/authoring.md#inserted-objects-and-feedback) before changing
these objects or their metadata. Only fullscreen sits at the slide's bottom-right;
the icon disappears while fullscreen is active and returns on exit. F toggles
fullscreen outside text entry/form fields and dialogs; Escape exits fullscreen.
the counter sits above the thumbnails. The presenter opens in view mode.
In edit mode, drag a thumbnail to the insertion line to reorder slides. Holding
near an overview edge scrolls it; Escape or dropping outside cancels. A drop is
one Undo step and preserves slide IDs, notes and guidance. Alt+ArrowUp/ArrowDown
on a focused thumbnail is the keyboard alternative; the move-arrow buttons are removed.
Palette and custom background are independent of layout; choosing a named
palette resets the custom background.
