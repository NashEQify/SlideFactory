# HTML contract and design freedom

The whole presentation is a single document. Ordered children of
`<main id="sf-deck">` are `<section class="sf-slide" data-sf-slide="stable-id">`.
Use meaningful permanent IDs, independent of slide number/title. Existing IDs
remain stable during reorder, content changes and handoff. DOM order is the story.

Editable objects carry unique `data-sf-id` and `data-sf-kind="text|box|image"`.
`text` is a text block; `box` can be a panel/group or SVG diagram container;
`image` is the retained original/crop frame. Prefer standard editable shape
objects for simple circles, lines and panels the user may want to change.
Non-editable ornaments are allowed when intentionally part of a fixed design.
Object IDs must not collide with any slide/object ID. Preserve ordinary SVG IDs
and references as well. Use valid, explicitly closed HTML; no external resource
dependencies. The helper checks identity and structure; the browser adds UI.

The text toolbar offers a font family and point-size dropdown plus larger/smaller
buttons (2 pt). Font and color operations retain the selected text range across
toolbar focus; block settings such as alignment and spacing apply to the text
object. Changes retain inline markup and separate undo for pending text edits.
Its yellow highlighter changes the selected text range, or the whole text block
without an active range. Repeating the action removes the marker; other text
formatting is retained. The selected image's trash icon removes its complete
frame, with local Undo retaining its original, crop and authored position.
Delete also removes a selected image or text block in slide edit mode through
local placement history. While typing, Delete retains its normal text behavior;
Escape leaves text editing and focuses the object selection for deletion.

## Inserted objects and feedback

The six shape presets are ordinary `box` objects carrying `data-sf-shape` with
`rectangle`, `rounded-rectangle`, `arrow-left`, `arrow-right`, `oval` or `line`.
Rectangle presets cover squares through equal side lengths. Inline SVG provides
the shape; standard `fill`, `stroke` and `stroke-width` on its frame supply colors.
Keep this structure, its stable ID and authored geometry during agent changes.
Textboxes remain `text` objects with normal background and border styles.
Their whole surface can start a move while not editing text; a click without
dragging enters text editing. Active text editing keeps native range selection;
Escape returns to object selection. Preserve the local geometry/history model.

The editorial starter registers its three approach circles, connector and intro
panel as individual shapes. Keep panel and overlaid text as separate objects.
An editor-only upgrade preserves older authored decoration; it does not convert
arbitrary unregistered SVG or background elements into editable shapes.

Feedback Post-its are `box` wrappers marked `data-sf-postit=""`, containing an
independently identified `text` object. Preserve wrapper and text IDs, position,
size and contents; these are separate from `guidance`. Drag the whole surface,
double-click to edit text and resize via selection controls. Deletion removes
the whole note. Its runtime × is transient and does not belong to saved content.
The writing area fills the note with a small inset; do not add a second visible
field or reserve a header row. The delete × is centered on the upper-right corner.
Keep existing custom padding/layout and typography during unrelated edits.
Post-it text does not supply a slide's title in the inventory.

Optional boolean `postitsVisible` in document metadata defaults to true. It
controls all notes together in editing, presentation and printed projections;
hidden notes remain saved. Preserve this setting during unrelated edits.
The fullscreen icon sits at the slide's bottom-right and disappears in fullscreen.
F toggles fullscreen outside text entry/form fields and dialogs; Escape exits it.

### Slide links and backup slides

A slide link is a `text` object on an `<a>` element, marked `data-sf-link=""`
with class `sf-link`, and `href="#<target data-sf-slide>"` (URI-encoded ID):

```html
<a class="sf-link" data-sf-id="link-backup-costs" data-sf-kind="text" data-sf-link=""
   href="#backup-costs" style="position:absolute;left:610px;top:422px;width:380px;height:56px">→ Cost details</a>
```

The target is the stable slide ID, so links survive reordering. Insert links with
the chain icon in the insertion group and change the target with the crosshair
icon; both list the deck's slides. The label is ordinary editable text; geometry,
Undo and deletion work as for textboxes. In edit mode a link never navigates.
Keep only geometry inline: the look comes from the editor's neutral `.sf-link`
rule (theme tokens) and the design CSS, never deck-local link styling.

Backup slides need no hard-wired return links. Following any slide link in view
or fullscreen mode records the origin; a `↩ Zurück zu Folie N` chip appears at
the slide's bottom centre and Backspace (outside text entry, also in the presenter
window) returns there. Arrow navigation is unchanged; returning to the origin by
any means clears that entry. Hand-authored `<a href="#slide-id">` anchors inside
slides use the same history and are checked by `validate` but are not editor
objects. A link whose target slide was deleted is outlined in edit mode, still
saves, and is reported by `validate`.

Format painter copies compatible typography, paragraph, fill and edge styles
once to a clicked target; it does not copy content, identifiers, dimensions,
position, transforms or crop. Escape cancels it. The native screen pipette is
offered only when the browser exposes it in the current secure context; the
ordinary color picker does not depend on that API or a network connection.

```html
<section class="sf-slide" data-sf-slide="recommendation" aria-label="Start with a reversible pilot">
  <h2 data-sf-id="recommendation-title" data-sf-kind="text"
      style="position:absolute;left:80px;top:90px;width:1350px;height:150px">Start with a reversible pilot</h2>
  <div data-sf-id="recommendation-diagram" data-sf-kind="box"
       style="position:absolute;left:80px;top:300px;width:1300px;height:430px">
    <svg viewBox="0 0 1300 430" style="width:100%;height:100%" role="img" aria-label="Learn before scaling">
      <path d="M 60 210 H 1200" stroke="var(--sf-accent)" stroke-width="8"/>
      <circle cx="260" cy="210" r="70" fill="var(--sf-surface)" stroke="var(--sf-accent2)" stroke-width="5"/>
      <text x="260" y="220" text-anchor="middle" fill="var(--sf-text)" font-size="30">Learn</text>
    </svg>
  </div>
</section>
```

## Geometry and diagrams

The canvas is 1600×900 design pixels. Default editable frames use authored inline
`position:absolute;left:Xpx;top:Ypx;width:Wpx;height:Hpx`, local to the containing
positioned parent. Text/box objects that participate in flex/grid/block layout
can instead declare `data-sf-layout="flow"`; movement changes CSS `translate` in
pixels while keeping their participation and dimensions. Inline text/boxes use
`data-sf-layout="inline"`; movement uses relative left/top, and an explicit resize
may promote them to inline-block. Images remain absolute canonical frames.
Nesting is allowed. Keep parent layout and authored transforms; don't add a
separate persistence model of offsets/patches or flatten flow objects. Movement
does not freeze measured dimensions. Export serializes authored DOM and styles.

CSS belongs in `#sf-design`, preferably scoped by the design class or to the deck.
Keep editor chrome independent. Text reflows inside its frame; check overflow
after changing copy. A group's box can move without rewriting its child IDs.
For SVG, prefer a viewBox and token-aware fill/stroke. When nested text inside a
diagram is independently editable, give it its own correctly positioned frame.

Geometry-driven diagrams can register an initializer in a custom inline script
**after `#sf-runtime`**, waiting for `document`'s `sf:ready` event. It fires after
validation, original parsed-file capture and initial editor setup. Never mutate
the authored DOM before that capture: it is the stale-draft comparison base.
`sf:layout` bubbles from the changed object with
`{slideId, elementId, phase: 'preview'|'commit'|'undo'}`. Use it to refresh attached
connectors; resize/font readiness may also require redraw. Derived nodes should
be `data-sf-transient` if they should be regenerated rather than exported.
Handlers must tolerate invisible slides and initialize again after a fresh open.
Native browser-menu printing invokes the same synchronous preview contract with
temporary measurable slides. For asynchronous diagram work, register promises
through `detail.waitUntil` when available; the prepared print dialog awaits them.
The synchronous browser `beforeprint` event cannot await arbitrary async work.
`sf:view` on document reports `{deckId,slideId,index,count}` after view setup or
navigation; index is zero-based. Requery nodes after undo/restore. A redraw may
update derived connectors, but must preserve authored label placement.

## Metadata and palettes

`<script id="sf-document" type="application/json">` is the one metadata authority:

```json
{"schemaVersion":1,"deckId":"uuid","revision":"uuid","title":"My deck","templateId":"my-design","templateVersion":"1.0.0","colorScheme":"cyan-dark","pageWidth":1600,"pageHeight":900,"notes":{"recommendation":"Presenter text"},"guidance":{"recommendation":{"text":"Make the trade-off visible","status":"open"}}}
```

Keep unknown extension fields. `notes` maps existing slide IDs to plain strings;
`guidance` maps them to `{text,status:'open'|'addressed'}`. Escape `<` as `\u003c`
in embedded JSON so user text cannot terminate a script tag. Authored slide DOM
plus metadata is the complete saved state; do not add baseline/text-patch replay.
Optional `notesProvenance` maps slide IDs to immutable `{html,text}` source notes.
The presenter shows sanitized original markup only while canonical notes exactly
equal its normalized `text`. Change canonical notes, preserve the provenance.
Optional slide timing attributes on `section.sf-slide`:

- `data-sf-duration="90"`: planned seconds for the slide.
- `data-sf-part="Teil B"`: part label (≤80 characters); slides of a part need not
  be contiguous. Leave backup slides without part and duration.
- `data-sf-part-duration="2400"`: part budget in seconds (incl. discussion), on
  any one slide of the part; conflicting values are rejected. Without it the
  budget is the sum of the part's slide durations.

The presenter shows `Folie 01:12 / 01:30` (time on this slide over all visits vs.
its duration) and a live pace. The plan follows the furthest slide reached in the
scope while the timer runs: plan now = durations of the scope's slides before
that slide + min(time on it, its duration). Delta = elapsed in scope − plan now
(`+00:35 hinter Plan` red, `−00:20 vor Plan` green, `im Plan` within a second).
Staying longer than planned grows the delta continuously; moving forward early
lowers it once at the slide change. Going back does not lower the plan: time
spent on earlier slides counts as elapsed, so the delta grows honestly, and
returning to the furthest slide continues from there. The scope is the current
part (`Teil B 14:05 / Plan 13:30 · Budget 40:00`) or, without parts, the whole
deck (`Gesamt … · Ziel …`). A slide without part in a deck with parts (backup)
belongs to the part it was reached from: its time counts there, the plan holds
still. ■ stops and clears everything, including the furthest-slide mark (state
`gestoppt`); there is no separate reset button since 1.3.4. Navigating while
paused does not move the mark. **Ende** takes a wall-clock time (HH:MM, e.g. the
meeting end) and shows `noch 47:12 bis 12:00`, amber in the last 10 minutes and
`+03:10 über 12:00` in red when overrun; it is independent of the presentation
timer. The value is kept per deck in the browser's localStorage (never in the
saved HTML; without storage it lasts for the open presentation); × clears it. The popup advances the clock on its own tick, so a
throttled background main window does not stall the display. Without any
duration the pace line is hidden.

Editor 1.7.0 splits HTML speichern into a working copy (with notes, the handoff)
and a share copy without speaker notes, guidance and post-its for recipients.

Editor 1.6.0 applies font sizes atomically to text-bearing selections, including
text inside selected containers and ordinary prose in boxes. Exact sizes include
inline runs; A+/A− preserve their differences using 2 pt steps within 1–999 pt.
Mixed sizes appear as “Gemischt”. Thumbnails mount according to the viewport
plus a 30 px overscan and release when outside it or when the overview closes.

Editor 1.5.0 lets users move selected objects together by Ctrl/Command-clicking
objects or dragging a marquee from the slide background. Selection lasts for
the editing session. Each moved object keeps its ID, parent, layout mode and
authored position in the downloaded HTML. A selected parent moves its children
with it.

Editor 1.4.0 stores slide visibility by the presence of `data-sf-hidden` on the
slide section. Preserve that attribute and the slide's content on later edits.
Remove the attribute to show the slide; always leave at least one slide visible.
Hidden slides remain reachable through explicit links and in the editor, but
sequential navigation, the presenter plan and printing skip them. Print ranges
use the original slide numbers.

The main presentation owns edits/history/drafts. Referentenansicht projects its
current/next slide, read-only notes and timer; navigation and timer commands go
through the same owner. Display one notes surface: current valid notesFormat,
otherwise matching sanitized notesProvenance, otherwise literal plaintext.
Browser drafts reference original images from the opened file and match its
complete-source SHA256/revision. Complete HTML downloads contain the actual
originals, not draft aliases. Missing storage/digest still permits HTML saving.

`#sf-color-schemes` contains a map of scheme ID to `{label,tokens}`. Token keys:
`background,text,muted,accent,accent2,surface,border`; values portable CSS hex
(`#RGB`, `#RRGGBB`, `#RRGGBBAA`). `#sf-theme-tokens` defines matching
`--sf-background`, `--sf-text`, etc. The runtime derives the selected scheme on
every load. Use tokens for text, surfaces and SVG. Add schemes in this map without
changing the editor. Layout/design identity and color scheme are independent.

The ready layouts each support cyan/amber and indigo/green in dark/light:
`cyan-dark`, `cyan-light`, `indigo-dark`, `indigo-light`. A palette does not recolor
bitmap pixels, logos, semantic status colors or SVG mask black/white. Keep these
deliberate; review contrast in both modes. Use system fonts or embedded licensed
fonts, never CDN fonts. Additional designs use the same markers/runtime contract.

## Images

An image-kind wrapper contains exactly one direct original `<img>` with embedded
PNG/JPEG/WebP data URL; its `width`/`height` attributes retain original pixel
dimensions after browser decoding, including EXIF orientation. Trusted built-in
SVG assets are also supported; editor upload accepts
raster formats only. Keep original bytes/dimensions when moving or cropping.

The wrapper's `data-sf-crop` is JSON `{x,y,w,h}` in normalized original-image
coordinates, inside [0,1] with positive size. Crop aspect in original pixels
`(w*originalWidth)/(h*originalHeight)` must match frame `width/height` (tolerance
1e-5). Rendering scales/translates the original into the clipped frame. Changing
frame aspect requires a compatible crop; ordinary image resizing is proportional.
Replacing a picture preserves frame/identity and starts a compatible centered
crop. Apply/cancel/undo retain the original so the user can re-crop later.

## Rich notes and asynchronous printing

Optional `notesFormat[id] = {version:1,text,html}` is active only while its `text`
exactly equals `notes[id]`. Retain stale format/provenance when editing plaintext;
neither may overwrite the newer string. Canonical notes allow root `p/ul/ol`,
inline `br/strong/em/span`, and `li` inside lists. List items contain inline text
and nested lists. Spans have only `style="font-size:Npt"` (8–72pt); no other
attributes or executable/media content are valid. Text is normalized from CRLF/CR
to LF and NBSP to space; escape &, < and >. Paragraphs add LF, including empty
paragraphs. List items insert LF before a nested list if necessary and end with
LF. Remove exactly one final LF from the complete projection. Both the JavaScript
and Python validators check this pairing, with text/HTML limits of 200000/800000
UTF-16 code units. Use the UI to author rich notes instead of hand-guessing them.

During print preparation, an `sf:layout` event also offers
`event.detail.waitUntil(promise)`. Register promises synchronously in the event
handler. The print capture waits for registered rendering, fonts, images and two
animation frames; rejected work or a 10-second readiness timeout reports a
visible failure and restores temporary hidden-slide styles. Unregistered
background work has no readiness guarantee. Existing synchronous hooks remain
valid. Keep generated SVG in the realized slide; print projections never rerun
custom scripts and preserve the deck/root/body selector context and shared defs.

`backgroundColor` is an optional `#RRGGBB` metadata override. It changes only
`--sf-background`; all other selected palette tokens and authored layout remain
unchanged. Selecting a named palette clears the override. Browser sidebar width
is ephemeral and never becomes authored deck geometry.

Slide text lists use native numbered/bullet lists. When a paragraph or heading is converted, the editor promotes that text root to a valid `div` while keeping its stable ID, text kind, parent and effective tag-selected typography/box appearance. Undo restores the original root; redo and HTML handoff retain the valid list container. Author new list-bearing editable text in a `div` directly.
