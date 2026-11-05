# Editor usability addendum

Status: delivered Task003 contract plus authorized image/toolbar/highlight/Delete-key follow-ups;
implementation/verification tracked separately.
Version:1.3.2, 2026-10-15. Extends spec001 v1.3.0. Consumers: document, notes,
presenter, preview/print, shell, builder, Python helper, packaged skill and tests.

The product is reusable slide technology. Each saved result remains one complete
offline HTML. Compact controls, arbitrary authored design, independent palettes,
local input cost and existing save notice remain required. No private deck or
content work, new storage platform, required companion files or runtime service.

## Notes contract

Keep schemaVersion1 and `notes[id]` strings. Optional
`notesFormat[id]={version:1,text,html}` pairs bounded markup with its deterministic
plaintext projection. Render it only when `text === notes[id]`; changed plaintext
cannot be overwritten by stale formatting. Canonical allowed markup is p/br,
strong/em, ul/ol/li and spans with numeric font-size in pt bounded8–72. No other
attributes/styles/links/media/executable content. Paragraph/list newline rules
must agree in the shared JS codec and Python validator. Reject malformed formats.
Preserve notesProvenance as historical source, sanitized matching fallback only.

Canonical grammar: root contains p/ul/ol blocks only; p contains inline text,
br/strong/em/span; lists contain li; li contains inline nodes and nested lists.
Inline wrappers contain inline nodes only. Serialize lowercase explicit close
tags (br is void), escape text &, <, >, and use double-quoted numeric pt style.
Normalize CRLF/CR to LF and NBSP to ordinary space in text; preserve other text
whitespace. Paste may normalize/unwrap/flatten invalid markup; persisted formats
must satisfy the grammar and projection, without silent repair.

Plain projection: concatenate decoded inline text; br produces LF. Every p
appends LF, including empty p. Lists concatenate li projections. Inside li,
insert LF before a nested list unless accumulated text is empty or ends in LF;
append LF at the end of li unless already present (empty li produces LF).
After concatenating root blocks, remove exactly one terminal LF if present.
No other trimming. Shared JS/Python vector cases are required before codecs:
empty HTML→empty text; `<p></p>`→empty; `<p>A</p><p></p>`→`A\n`;
`<p>A<br></p>`→`A\n`; `<p>A&nbsp;B</p>`→`A B`;
`<ul><li>A<ul><li>B</li></ul></li><li>C</li></ul>`→`A\nB\nC`;
`<p><strong>A</strong> &amp; B</p>`→`A & B`;
persisted `<p><ul><li>A</li></ul></p>` is rejected, while paste is normalized.
Bound text to200000 and HTML to800000 UTF-16 code units, with explicit parity
for astral characters in the Python validator.

The main-window editor provides B/I, font sizes, lists,
selection retention, sanitized paste, IME and grouped local history. The toolbar
shows B/I, the pt dropdown without a visible size label, and square pictogram
buttons for ordered/unordered lists (retain accessible names). Omit the explanatory
note-storage sentence. Open notes are immediately editable in the main window,
including outside slide edit mode; Bearbeiten gates slide editing only.
Plaintext and format mutate atomically. The user's subsequent
explicit UI correction removes notes import/export and their unused plumbing;
saved notes remain in the complete HTML and printing supplies note-only output.
This supersedes the earlier note-transfer UI in spec002. Helper validates/inspects
and preserves notes formats through edits.

The user's 2026-10-15 correction makes the presenter read-only: exactly one
formatted notes surface, choosing valid current notesFormat, then matching
sanitized notesProvenance, then literal plaintext. No note editor or formatting
controls in the popup. Current/next previews start at the top without a header;
remove its save/fullscreen/audience toolbar. Compact navigation and timer controls
sit below the previews, with wall-clock time near the timer. The top-right X
and Escape close, including after owner disconnect and with a control focused.
Main-window editing remains the only note-writing surface.

Main-window notes occupy a horizontal bottom pane under the slide, without a
heading, slide-label or separate close row. The existing notes button toggles
the pane. Keep compact formatting tools and an accessible input label. Dragging
the top divider upwards increases notes height and reduces the slide's available
height; maintain aspect ratio. Support keyboard resizing, bounds and Escape
cancellation like the thumbnail separator. Pane height is ephemeral UI state;
resizing writes neither document metadata nor undo history. Comments retain
their separate panel layout.

## Print contract

Drucken/PDF opens a compact accessible dialog: a slide-range field and the three
choices Folien (default), Folien mit Notizen darunter, Nur Notizen. Empty range
means all; accept comma-separated numbers/inclusive ascending ranges, such as
`1, 3-5`. Whitespace is optional; normalize an en dash to a hyphen. Reject malformed,
reversed and out-of-bounds ranges visibly before opening output. Deduplicate and
print in current deck order. Cancel/Escape closes without output; validate against
the current slide inventory when printing. Settle
accepted edits/previews, then capture full rendered slides into disposable
nonexecuting projections: raster originals/crops, HTML/SVG diagrams/definitions,
CSS, root/body context, theme and embedded fonts. Prepare hidden slides using
sf:layout, wait for images/fonts/layout frames, and restore temporary styles.
Capture asynchronous generated SVG without rerunning custom scripts. Preserve
selector and SVG identity contexts.

During print preparation, sf:layout detail adds `waitUntil(promise)`. Handlers
register synchronously during dispatch. Await all registered promises, fonts,
images and two animation frames before capture. A rejection or 10-second
preparation deadline fails visibly and restores temporary live styles in finally;
the deadline prevents an unresponsive renderer from trapping printing. Existing
synchronous handlers remain valid. Unregistered background work is not a supported
readiness signal; document this extension in the authoring skill and test delayed
registered success/rejection/timeout. No custom scripts execute in print output.

Slides only uses one full16:9 slide per page. Notes mode uses A4 portrait, a full
scaled slide followed by flowing formatted notes; next slide starts a new page.
Notes-only uses A4 portrait and flows formatted notes without slide images; show
the original slide number as a small heading and start each selected slide on a
new page. All three modes use the requested selection only.
Long paragraphs and list items can continue onto further pages. Exclude chrome
and guidance. Exact print color adjustment requests faithful colors; browser
settings retain final control. Print/cancel never changes revision/save status or
authored state except settlement of accepted edits. Repeated preparation disposes
old resources; failures are visible. Verify actual browser PDFs and rendered pages.

The print contract above is further specified by the
[offline print repair](006-offline-print-repair.md): native16:9 paper, shared
Ctrl/Cmd+P dialog and resource readiness without animationframe dependency.

## Slide transactions

Thumbnail controls delete/move earlier/later. Reorder records only stable anchors;
delete records only removed slide plus notes/notesFormat/notesProvenance/guidance.
Unknown extensions remain preserved. Dedicated document scopes participate in
validation/capture/apply/indexes/events/assets/history/journal/checkpoints/recovery.
Undo/Redo restores identities, metadata and image originals together. Preserve
unaffected DOM. Keep active slide by ID on move; deletion selects next, or previous
if last. Clear detached selection; protect final slide. Refresh presenter and
thumbnail inventory, reject imports to removed targets, keep Delete text-local.

Task004, authorized2026-10-15: in edit mode, drag thumbnails to reorder with a
visible insertion line and edge scrolling. Ordinary click still selects a slide;
Escape or release outside the list cancels. Resolve the source/target by stable
ID and call the existing move transaction once on a valid drop. A no-op or
cancelled gesture writes no reorder history (settling accepted text edits remains
allowed); pointer/drag motion writes no document state
and takes no deck copies. Preserve active slide, notes and guidance associations.
Clear transient drag state when the overview hides, editing ends, the inventory
changes or the page unloads. The per-thumbnail up/down buttons are removed at
the user's request; Alt+ArrowUp/ArrowDown on a focused thumbnail moves one step.

Checkpoint compaction cannot replay only the most recent anchor per moved ID:
those anchors describe different intermediate inventories. A checkpoint containing
structural changes also stores the final ordered slide-ID vector, derived from the
existing index. After staged content/meta replay, validate it as a unique exact
permutation of the resulting inventory and apply before atomic admission. Account
its bytes and reject corrupt vectors. This is an additive internal draft-v2 field;
ordinary history/journal movements remain local anchor records, with no slide
content copies. Verify a recovered draft can later compact again without drift.

## Sidebar and accessibility

Right-edge pointer/keyboard separator: arrows, Shift faster, Home/End bounds,
Escape cancels drag, accessible value/min/max and visible focus. Width is ephemeral
and constrained by viewport/panels. Keep collapse. Scale thumbnails from actual
interior width after padding/scrollbars: no horizontal overflow. Add two-tone
selection/crop outlines and keyboard resize-handle operation through local history.

## Compact controls and custom background

The approved toolbar increment
supersedes the control placement and size-input layout described below: Undo
and overview follow the brand, insertion belongs to the ribbon, size is a
point dropdown, palette shares that ribbon, count is above thumbnails and
fullscreen sits on the slide. The local history and content-preservation
requirements in this section remain binding.

The user's subsequent UI correction removes the visible Wiederholen and Text
bearbeiten buttons; retain keyboard redo and the established direct text editing.
Ordinary textboxes also move by dragging their surface while not editing text.
A click without dragging enters text editing at the clicked position; active
text editing retains native range selection. Escape leaves typing. Reuse local
geometry Undo and clear pending presses on cancellation or command settlement.
Bild einfügen uses a landscape-plus SVG directly after the overview control,
before the flexible toolbar spacer. Undo uses an arrow icon in the right action
group. Square icon buttons center their contents on both axes. Rename Für den
Agenten to Kommentare. Hide the
Referentenansicht launch button while slide editing. Text tools use B/I, left/center/
right alignment and numbered/bullet-list pictograms, with accessible labels and
titles. These actions participate in the existing local object history.
The yellow highlighter acts on the selected slide-text range, or the entire
selected text object when no noncollapsed local range exists. Applying it to
already highlighted text removes the highlight without discarding other text
formatting. A persistent `data-sf-highlight` marker supplies dark displayed text
on the yellow background without overwriting original authored foreground
colors. Owner and isolated projections include that content-only contrast rule.
The action is a local text transaction and survives saved HTML.
When list formatting would put a block list inside a paragraph/heading text root,
promote that root to a div with the same ID/kind/parent and preserve its effective
typography/box appearance, including tag-selector styling. Undo restores the
original root; redo and saved HTML must parse validly. Other objects are untouched.

Selected image tools include a trash icon with title/accessible name Bild löschen.
Remove the entire image frame through local reversible placement state; Undo
restores identity, original image, crop, geometry and authored sibling position.
The trash control is available only while editing a selected image, outside the
crop preview. Clear the detached selection. Keep image history/assets and local draft
projection coherent; no whole-slide/deck copies or required confirmation dialog.
Untracked layout wrappers and decorative siblings must retain their order.
Unmodified Delete removes a selected image or text block in slide edit mode,
through the same local placement history. Focus must belong to that object or
its selection overlay/handles. Do not intercept text editing, IME composition,
notes/comments, other inputs or unrelated UI, nor already-handled key events.
Escape leaves text editing and focuses the object overlay; a following Delete
then removes the text block. Backspace retains its prior behavior. Settle pending
gestures/crops before deletion and re-resolve the ID in the current slide.
Placement values may carry an optional `parentPath` through untracked child
elements from the stable parent anchor and `beforeOffset` counting untracked
child nodes before a stable next sibling, or from the parent's end. These
additive draft values accept older records without the fields. Validate
integer bounds and reject missing or inconsistent anchors rather than silently
moving an image. Saved schema/template identity is unchanged.
At idle checkpoint construction, refresh only current placement anchors, order
same-parent removals before surviving placements, and admit a referenced inserted
parent/following sibling before its dependent. Retain later style/image/subtree
changes after their placement; do not sample uncommitted input sessions. This
keeps coalesced final placements independent of removed intermediate anchors.

Place a native color picker beside Farbschema for a chosen background. Optional
`backgroundColor` metadata is a validated six-digit-hex override of the selected palette's
background token; other tokens and design remain independent. Its absence means
the palette background. Color edits are local and undoable, survive complete
HTML save/reopen/helper/update, and appear in all visual projections/print.
Choosing a named palette clears the override in the same transaction. Canceled
native selection without an input/change does not modify authored state.

## Checked common-editor upgrades

`deck.py upgrade-editor FILE --output FILE` requires distinct new output; source
is retained unchanged. Builder embeds an editor version/manifest independent of
layout/templateVersion. Trusted packaged registry recognizes actual CSS/runtime
fingerprints, including the current known unmanifested release. Self-declared
input hashes are insufficient. Fingerprint normalization is CRLF→LF only.

Reject modified/mixed/duplicate/unknown/newer resources and unknown legacy formats
before writing. No force overwrite. Replace only common CSS/runtime, manifest
and saved revision. Preserve all other source spans byte-for-byte, including
custom CSS/scripts/hooks, slides, SVG, images, design and metadata extensions.
Validate complete result and preservation comparison before atomic write. Refuse
existing output. Output needs no companion file. Publish all four rebuilt starters
and updated portable skill/reference docs; record measured empty-file size.

## Acceptance and test strategy

The twelve pre-code cases T1–T12 in the
implementation brief
are the acceptance catalog: note consumer/compatibility/order/locality; actual
PDF fidelity/pagination/lifecycle; structural history/focus; sidebar access;
upgrade preservation/rejection. Use neutral fixtures and actual download→fresh
offline reopen→helper edit→fresh reopen. Retain existing performance and owner
race regressions. Run focused tests per increment and one final full suite.

That catalog describes the original Task003 verification plan. The subsequent
image/toolbar/highlighter delivery retains the user's test stop; its separate
record reports build/static inspection
only, without claiming new browser or file-handoff verification. Post-its were
subsequently delivered under the Task005 toolbar contract.
The later [Task006 print repair](006-offline-print-repair.md) has its own limited
actual PDF and offline-handoff evidence; it does not repeat the original full suite.

Sources checked for printing behavior: [MDN printing](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Media_queries/Printing),
[page size](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/%40page),
[print color adjustment](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/print-color-adjust).
