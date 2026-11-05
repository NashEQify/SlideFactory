# First working SlideFactory package

| Field | Value |
|---|---|
| Layer | L2 implementation contract |
| Status | Implemented |
| Version | v1.4.0 |
| Date | 2026-11-04 |
| Consumers | Editor, builder/designs, Python helper, skill, tests |

One offline HTML is the complete presentation and saved shared working state.
The human edits text/layout/images and guidance; the LLM authors fundamental
changes through the existing chat. Reuse the editor/method while permitting
individual HTML/SVG compositions and multiple designs.

Intent chain: reusable high-quality collaboration → preserve direct contributions
and individual design → editor/ready files/skill/helpers with real handoff proof.

## Bedrock — focused implementation drill

Max depth 5. Root: preserved shared work [uncertainty high/impact high]. Drill
actual saved result → distinct browser/disk stores → older competing replay can
erase work [logic bedrock]. Drill independent design/behavior → layout need not
control crop/save → palettes change appearance, not identity [logic bedrock].
Single-file, LLM-led authorship and no required app/server are user value choices.
Small changes follow addressability; this branch is pruned rather than redrilled.

Given one authority, save authored DOM/layout and metadata rather than a second
text-patch representation in the same file. Q1 PASS: next actor sees current
source; Q2 PASS: bespoke visuals remain possible; Q3 PASS: fresh-open/agent-edit
proves it. Given independent design/behavior, exercise the same editor in two
layouts and multiple palettes. Q1 PASS: common semantics; Q2 PASS: file-based
selection; Q3 PASS: second layout needs no runtime edit. Alternative value: broad
human slide construction would favor a scene editor; it is not today's priority.
Unseen-assumptions prompt for later user review: “Which assumptions seem so
self-evident that they have not been named?” The current explicit choices settle
the required scope; no pending user input blocks autonomous work.

## Shared file/metadata contract

- `<main id="sf-deck">` contains ordered `<section data-sf-slide="ID" class="sf-slide">`.
- Editable objects have unique `data-sf-id` and `data-sf-kind="text|box|image"`.
  IDs survive reorder/rename. Layout and HTML/SVG inside a slide remain free.
- `<script id="sf-document" type="application/json">` has schemaVersion=1,
  deckId, revision (unique saved IDs), title, templateId, templateVersion,
  colorScheme, pageWidth=1600, pageHeight=900, notes and guidance.
- notes maps slide IDs to plain strings, with the optional guarded notesFormat
  extension defined by the Task003 addendum. guidance maps IDs to
  `{text: string, status: "open"|"addressed"}`. Editing text reopens it. Unknown
  metadata extensions are preserved; unsupported schema versions are rejected.
- Movement/resize changes authored inline styles/data. Preserve parent hierarchy
  and authored transforms; document exact attributes in the skill reference.
- Images use an image-kind wrapper with exactly one direct original `<img>` data URL, and
  `data-sf-crop` JSON `{x,y,w,h}` normalized within [0,1]. Width/height are positive
  and contained in the source. Crop and frame geometry change atomically.
- `#sf-color-schemes` JSON maps IDs to `{label, tokens}`. Required token keys are
  `background`, `text`, `muted`, `accent`, `accent2`, `surface`, `border`; values
  are validated CSS colors. Map these to `--sf-background`, `--sf-text`, etc.
  Derive `#sf-theme-tokens` from the
  selected scheme and optional six-digit-hex `backgroundColor` override. Selecting
  a named scheme clears the override; it otherwise survives complete-file handoff.
  Editor chrome has separate scoped styling.

## Source authority, undo and save

Authored slide DOM and schema1 metadata are authoritative. No in-file baseline or
text overlay may replay over agent changes. Document operations declare local
metadata paths, style properties, attributes, image state, object subtrees or
stable placement. Capture before mutation and retain only the reversible local
values. Subtrees exclude transient/generated runtime content and reference
immutable originals. Invalid local changes restore their declared scope.

Undo/redo settles accepted input first, cancels provisional previews, then applies
retained records while preserving unrelated work. The owner tab has one ephemeral
history for authored text, notes and guidance: at most80 commands and64MiB accounted
including distinct referenced assets. Keep an oversized newest command reversible
with a warning. Assets referenced by live objects, active sessions, history,
pending records, projection or admitted journal must remain available.

Build identity/order/title indexes and a metadata JSON token tree at load. Local
changes update affected entries/leaves; the metadata script remains current
parseable JSON, with `<` escaped and unknown extensions preserved. Local input,
formatting, geometry, history and background persistence must not capture, scan
or serialize the complete deck. Load, checked recovery and complete export may.

Browser draftVersion2 is independent of saved schemaVersion1. Bind drafts to
deckId, revision and SHA256 of original parsed documentElement.outerHTML captured
before UI/design mutation; release the temporary source after hashing. Persist
settled changed scopes and separate deduplicated introduced originals. Publish
assets and immutable records before the head. Reject stale/legacy drafts visibly;
validate a detached complete recovery candidate before atomic admission. See
[journal protocol](002-reference-migration.md#durable-drafts-and-one-authority).

Fertig settles edits and leaves editing. HTML speichern offers a working copy
and a share copy. The working copy settles input and valid
previews, flushes prepared records where possible and downloads one checked HTML
with actual originals/crops/theme/notes/guidance/editor. The share copy is the
same export with empty notes/guidance, no notesFormat/notesProvenance and no
post-its; it keeps the file notice dirty and is not a handoff. Strip transient UI and
runtime attributes; assign a fresh revision and escape `<` in JSON. Invalid
metadata/identity fails explicitly. Missing digest, denied storage or quota warns
while retaining editing and full HTML export; no weak-digest/whole-source fallback.

<!-- DIM source/history/save: completeness ✓; consistency ✓; implementability ✓;
interface contracts ✓; dependencies ✓. As-is sync 2026-10-14. -->

## Editor behavior

Fixed compact top toolbar, contextual selected-object controls, optional thumbnail
navigation, on-demand right guidance and separate notes. No floating inspector
or X/Y/width/height fields. Mouse/handles/arrows manipulate; Shift nudges more.
Separate persistent footer notice distinguishes opened-file state, unsaved local
changes (including admitted recovery), and HTML-download started. Live update and
history notifications mark changes without whole-deck comparison; Done/navigation
and temporary messages do not clear the notice. A download never claims to have
overwritten the opened file. Undo/cancel may conservatively retain the notice.
No extra presentation files or new storage adapter are required by this notice.
Text arrows move the caret. Images import via file picker/drop/paste (PNG/JPEG/WebP),
embed originals, resize proportionally, replace, crop handles/pan/zoom, apply/cancel
and undo. Re-crop preserves the original; replacement preserves identity/frame
with a valid centered crop. Custom diagrams initialize on `sf:ready` after original parsed-source capture,
and can update on `sf:layout`. Task003 adds registered asynchronous print readiness,
formatted immediately editable notes, three-mode/range printing, thumbnail slide
actions, pane resize and checked common-resource updates; see spec003 for details.

Text uses a cached pre-input object baseline, including missing-beforeinput
fallback. Ordinary text/notes/guidance group until450ms idle or blur; composition
settles at completion. Native and keyboard undo/redo use owner history. Formatting
captures the affected text objects; alignment/nudge capture their style properties.
Mixed multiple selections allow one atomic font-size change across their text
targets, including text inside selected containers, while skipping textless
objects. Explicit sizes apply to all target text; size stepping adds/subtracts
two points to each run, and differing sizes display as mixed. Preserve inline
emphasis, identifiers, nontext content and the selection through formatting,
undo/redo and the complete-file handoff.
Geometry commits on pointerup; Escape, pointercancel and lost capture cancel.
Crop remains one preview across pan/handles/zoom until apply/valid settlement.

Central settlement runs input before previews. Editing commands, navigation,
Save, Fertig and owner pagehide commit accepted input and valid previews; history
commits input and cancels previews. Pagehide flushes prepared records synchronously
without waiting for imports or constructing a deck snapshot. Closing the read-only
presenter releases its projection without contributing document edits.

Async image tickets bind original slide/object identity, generation, lifecycle
and request ownership; recheck after decode and settlement. Navigation alone does
not redirect/reject a still-valid original target. Changed/detached/replaced targets,
history, Fertig/pagehide and superseding requests reject before atomic mutation.
Render every thumbnail intersecting the sidebar viewport plus its 30px preload
margin; bound live frames to that demand and release offscreen/hidden frames,
including the no-observer fallback. Update affected captions/visuals rather than every entry.

<!-- DIM editor: completeness ✓; consistency ✓; implementability ✓;
interface contracts ✓; dependencies ✓. -->

## Design, palettes and packaging

Two neutral independent layouts from the outset: reference-inspired consulting
and editorial. No private content/fonts/assets are copied. The first design is
one peer, not special-cased in runtime. Each supports at least dark/light and two
accent combinations. Farbschema UI selects colors only; **no template UI picker**.
Templates are chosen by their file paths in chat.

Ready assets: `consulting.html`, `editorial.html`, `consulting-blank.html` and
`editorial-blank.html` in `skills/slidefactory/assets/`. Each blank file has one
empty1600×900 slide, empty notes/guidance and no authored text/image/font assets.
Sources: src/editor/, src/designs/, src/templates/. Builder embeds the same eight
classic JS modules, editor CSS, selected design and schemes. Terser is build-only;
without it a warning accompanies readable larger output. Minification must retain
serialized popupRuntime behavior; reject a literal runtime script-end tag.
Using a ready file needs only a browser, no runtime package/network/app/server.
The skill is self-contained; helper uses stdlib. No global install/public release.
Private originals remain intact; reject unknown legacy families explicitly.

<!-- DIM packaging: completeness ✓; consistency ✓; implementability ✓;
interface contracts ✓; dependencies ✓. -->

## Python helper commands

skills/slidefactory/scripts/deck.py:

- `new --template FILE --output FILE --title TEXT`: compatible explicit source,
  fresh deck/revision IDs, chosen design preserved.
- `inspect FILE [--slide ID_OR_NUMBER]`: JSON overview or relevant slide/objects,
  crop/geometry/guidance. Redact embedded asset bytes and runtime.
- `set-text FILE --element ID --text TEXT [--output FILE]`: escape plain text,
  focused inner-content replacement, new revision.
- `guidance FILE --slide ID [--text TEXT] [--status open|addressed] [--output FILE]`.
- `scheme FILE --id SCHEME [--output FILE]`: choose declared colors; derive tokens on load.
- `extract-slide FILE --slide ID_OR_NUMBER --output FILE`: raw authored fragment.
- `replace-slide FILE --slide ID --fragment FILE [--output FILE]`: retain slide ID,
  metadata; reject duplicate cross-deck object IDs.
- `insert-slide FILE --fragment FILE [--after ID] [--output FILE]`: new unique IDs,
  initialize only new notes/guidance.
- `reorder FILE --order ID,ID,... [--output FILE]`: complete permutation.
- `validate FILE`: schema, identities, images/crop, metadata refs and standalone
  structure; nonzero on error.
- `upgrade-editor FILE --output FILE`: recognize trusted common CSS/runtime,
  replace them and manifest/revision only, validate preservation, exclusively
  publish a distinct new HTML; source retained. See spec003 for rejection rules.

Focused review clarified: preserve supplied new unique IDs on insertion; reject
collisions, do not silently regenerate ordinary DOM/SVG references. Text setters
target text-kind objects only. Read source bytes without newline normalization.
Crop render uses original dimensions and enforces crop aspect = frame aspect;
saving during crop commits a valid crop, cancel restores previous geometry/crop.
`sf:layout` bubbles with `{slideId,elementId,phase:preview|commit|undo}`. Four schemes
are cyan-dark, cyan-light, indigo-dark, indigo-light; portable hex color grammar.

Validate before atomic sibling-temp/replace writes. Preserve untouched slide bytes,
assets/shared styles/runtime using source spans; only touched fragments may be
parsed/serialized. No silent rebuild from starter on revision. Never automatically
mutate private reference inputs. Unsupported non-SF files get a useful error.

## §Module-Decomposition

| Module | Deep responsibility / relationship |
|---|---|
| Document/state/export | Authored authority, indexes, tokenized metadata, scoped sessions/history/assets, journal/recovery/export and structured changes |
| Interaction/images | Declare local scopes; selection/gestures/composition/crop/cancel and target-bound decoded imports |
| Editor shell | Toolbar/panels/navigation; affected-entry updates and bounded thumbnails |
| Preview | Isolated sources, visual/context cache, bounded frames and disposal; notify shell of authored context changes |
| Notes | Shared bounded rich/plain codec and compact main-window input controls |
| Print | Validated selection, awaited complete projections, flowing notes and disposable output |
| Presenter | Authenticated navigation/timer commands, read-only incremental projection and separate ephemeral clock |
| Design/builder | Independent layouts/palettes, populated/blank one-file assembly and build-only minification |
| Python helper | Focused checked authored-source edits; same markers/meta, unrelated byte preservation |
| Skill | Create/revise/verify method, individual visuals and current saved input |

Implementation surface: src/editor/, src/designs/, src/templates/, scripts/,
skills/slidefactory/, tests/, package.json and docs. JS may combine operations
where doing so keeps state ownership deep and avoids pass-through modules.

## Acceptance and §Test-Strategy

| AC | Observable requirement | bug_class | Level |
|---|---|---|---|
| A1 | All four ready files open file:// with network blocked and edit/present/navigation work | offline dependency | E2E |
| A2 | Journal reload/pagehide preserves settled direct work; stale/legacy drafts cannot override saved file/agent revision | competing state authority | integration/E2E |
| A3 | Real exported file/fresh reopen keeps text, geometry, notes, guidance, originals/crop and colors | incomplete serialization | E2E |
| A4 | Scaled mouse/keys, caret arrows and grouped owner history preserve local state; no geometry-number UI | coordinate/focus ownership | E2E |
| A5 | Import/paste/drop/resize/crop/undo retain originals; delayed imports use valid original targets and reject stale targets | image transform corruption | unit/E2E |
| A6 | Reorder/insert preserve IDs/guidance; labels track DOM order | identity drift | CLI/integration |
| A7 | Focused mutations preserve untouched slide bytes/assets; invalid targets/orders fail atomically | source collateral change | unit/integration |
| A8 | Both populated/blank layouts share runtime/palettes; minification preserves popup execution; no template selector | layout/palette coupling | build/E2E |
| A9 | Paste/JSON edge text cannot execute/corrupt export; invalid inputs preserve previous work | unsafe external content | integration/E2E |
| A10 | A fresh agent can create/revise using packaged skill/resources/helper | inactive packaging | functional forward test |

Test the actual browser download and production helper, not fabricated snapshots.
Use compact meaningful cases per defect class; no mechanical test-count goal.
Installed Playwright/Chromium may serve development tests, never runtime use.
Instrument input/history/flush for absence of complete-deck capture/scans/metadata
serialization. Exercise missing-beforeinput/composition, cancellation, stale
imports, corrupt/failed journal publication and repeated bounded preview/presenter
lifecycle. Clock ticks must not project content. Record execution and timing
evidence separately; these requirements are not test-success claims.

## Failure modes / stops

Stale/legacy/corrupt drafts reject before candidate admission; retain file source.
Digest unavailable disables guarded drafts visibly. Failed storage/publication
keeps in-memory work and the previous head, cleans new orphan writes where possible
and retains full export. Invalid local metadata/identity/image/geometry restores
its scope. Cancel/lost capture/history cannot persist provisional previews.
Stale imports retain previous valid state. Oversized newest history remains
reversible with a warning. Focus owns arrows. Palette changes preserve content,
geometry and readable diagrams, including inherited authored color variables.
No required live provider, server or platform API is introduced.

<!-- DIM modules/AC/failures: completeness ✓; consistency ✓; implementability ✓;
interface contracts ✓; dependencies ✓. -->

## Review and registration

[Task003 editor usability](003-editor-usability.md) is the additive contract for
formatted notes, printing, slide transactions, sidebar and checked resource
updates. It extends the original package rather than reopening its delivery.

Verification: an independent contract/buildability review, a pre-code test plan
and independent correctness/UI review. Preservation and actual handoff checks
remain mandatory.
