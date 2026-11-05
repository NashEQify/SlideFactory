# Reference migration — v19 on the common editor

Date 2026-11-04. Version 1.2.1 (original migration 2026-10-14). This extends the
first package for decks of the legacy v19 reference format, not a universal
importer. The original v19 file remains unchanged; real decks stay outside the repo.

## Intent and migration decision

The working deck is a product consumer of reusable human-agent collaboration.
Preserve its individual compositions, direct contributions, images and notes;
swap editing/source handoff, not its story. Input is the explicit saved v19 file.
The optional old browser cache is not available to an agent from disk and is never
silently imported. Saved embedded state, if supplied, is materialized once.

Five migration questions: source still provides unique content/design/presenter
value, retained in output; one consumer40slides; shared editor replacement exists;
conversion needs bounded rendering/tooling; maintaining two active state editors
would undermine reliable handoff. Advisory migration: create a separate native
file, preserve the original. Remove legacy editor/cache/nav scripts in the native
file; retain only live design-render hooks and preserved private assets/styles.

## Conversion and layout

Canonical page remains1600×900. Each ordered native `section.sf-slide` contains
its original1920×1080 canvas scaled5/6. Use the source's clean audience layout as
the presentation baseline; the old editor/navigation topbar is replaced by the
new toolbar. Keep original CSS cascade, typography, masks/filter definitions,
structural HTML, inline emphasis, stable slide IDs and legacy object IDs.

Do not turn every flex/grid/inline object into an absolute frame: that can shift
siblings on its first edit. Add optional `data-sf-layout="flow|inline"` on existing
text/box elements. Flow movement uses authored CSS `translate` pixels and leaves
normal flow/parent hierarchy intact. Inline movement uses relative left/top; a
requested resize can promote it to inline-block. Preserve pre-existing transforms.
Dragging does not freeze width/height merely because geometry was measured.
Default absolute objects keep existing behavior. Helper inspect exposes layout
and authored offsets; invalid layout markers fail explicitly. Images remain
absolute canonical frames, never flow-kind image wrappers.

Map all1389 legacy IDs onto appropriate native text/box/image frames. Icon SVG
roots are boxes; inline SVG remains intact. Any newly necessary frame gets a new
unique ID, without renaming existing ordinary IDs or SVG references. Every original
embedded image and font byte is retained. Contain images keep their actual visible
rectangle and surrounding slot; cover/percentage clips retain originals and
normalized crop. Source's three slight anisotropic screenshot stretches must be
represented by authored frame transform while the canonical crop/frame aspect
remains valid, rather than silently shifting crop or rejecting it.

Two live design producers attach connectors to measured boxes. Capture initial
label positions after source render/fonts; redraw on ready/layout/view/resize/font
readiness, requery after undo. Derived SVG is transient. Preserve a user's manual
label placement; a redraw must not silently overwrite authored contribution.
Only live producer bodies may be carried into the private output, not old stateful
editor/navigation code. No private function/style/body is stored in repo fixtures.

The migrated design supports the four native palettes using the bounded semantic
color bridge. Initial layout comparison uses the equivalent palette-rendered
source audience canvas, so intentional palette differences are distinguished
from geometry/typography regressions. No template selector UI.

## Durable drafts and one authority

The large originals require local drafts. Use the [local transaction authority](001-working-package.md#source-authority-undo-and-save);
saved metadata remains schemaVersion1. SHA256 is computed once from original
parsed documentElement.outerHTML captured before UI/design mutation, then release
the temporary source. Index distinct immutable originals deterministically as
`original:N`; exact introduced sources share `new:<id>` identities and storage.
References come from typed image scopes or actual image aliases; notes/guidance
and their unknown extensions are opaque content, never lexical asset references.

DraftVersion2 head at `slidefactory:<deckId>` is
`{draftVersion:2,base:{deckId,revision,fingerprint},head}`. Namespace immutable
`entry:<id>` and `asset:<newId>` keys by deck/revision/fingerprint. An entry has
`{id,prev,seq,changes:[{descriptor,after}],assetRefs}`. Write introduced assets,
entry, then head. Failure keeps in-memory edits/previous head and removes newly
orphaned writes where possible. Export remains available.

Maintain the coalesced changed-scope projection in causal order with one projector
for live changes and recovery. Replacement/removal prunes scopes owned by previous
and new subtree IDs; recovered removal must not poison a later checkpoint.
At128 entries or2MiB accounted record bytes prepare a checkpoint in idle chunks
of at most64 records, using prepared values, no live DOM scan or synchronous
projection enumeration. New commits invalidate unfinished work. Publish the head
before retiring unreachable records/assets. Record/asset accounting uses twice
the serialized/data-URL string length.

Recovery requires exact v2/base identity; reject legacy-v1/stale heads visibly.
Validate ordering/descriptors/values/exact refs/assets; limit512 entries and128MiB
record text. Replay into a detached full candidate, capture its actual prior
subtree membership for projection reconstruction, validate before atomic install.
Failure retains original file. Recovery restores work without tab undo history.

The journal is optional browser convenience. Complete export has actual originals,
crop/DOM/meta/runtime, fresh revision and no journal aliases. Same-revision source
changes reject old drafts. Missing digest/denied storage/quota warns without weak
digest or whole-source fallback; editing and complete saving remain available.

<!-- DIM journal: completeness ✓; consistency ✓; implementability ✓;
interface contracts ✓; dependencies ✓. As-is sync 2026-10-14. -->

## Notes and presentation

Canonical notes stay plain strings, guidance separate. Task003 adds guarded
`notesFormat` and shared rich input; its current contract supersedes the earlier
plain-note transfer UI. Optional metadata
`notesProvenance` maps existing slide IDs to `{html:string,text:string}` immutable
source provenance; both fields are validated. Preserve source rich note
markup paired with its exact normalized text. Presenter
uses original markup only while canonical text still matches that provenance;
after edits, canonical text wins. Original markup never replays over edited notes.

Add generic presenter/fullscreen behavior to the shared editor: ordinary browser tab
current+next previews, current-slide selection/navigation, read-only notes and
elapsed timer with start/pause/reset and optional durations from authored slides.
Complete HTML saving remains usable through the owning presentation. At the
user's later request, Task003 removes notes JSON import/export controls and their
unused command plumbing, adding notes-only printing. General HTML importing is
outside this scope.
Main window owns mutations/draft/history; presenter is a synchronized projection
and sends commands to that owner. Source-window/session/deck checks prevent
unrelated window commands. Reopening popup rehydrates current state. Offline
source/font/image rendering works; no duplicate active legacy writer is retained.

Open with two-argument window.open; retain native browser chrome and an accessible
visible close-X that remains usable after owner disconnection. Six unmodified
arrow/Page keys navigate; editable focus, composition and modifiers retain native
behavior. Escape closes regardless of focus or owner connection. The compact
layout and bottom main-window notes pane are specified by spec003's
2026-10-15 correction.

Protocol `slidefactory-presenter`, version1, deckId, session and actual source
remain validated for navigation/timer/close. Presenter note-writing, note epochs
and final-note capture are removed with the read-only popup; obsolete note
commands cannot mutate owner data. Closing releases the projection resources.

A public `sf:view` event exposes `{deckId,slideId,index,count}` after navigation
and view restoration (index zero-based) for design redraw. Existing ready and
layout events remain compatible. Preview rendering must preserve per-slide CSS,
SVG/filter references and fonts without inserting duplicate authored IDs into
`#sf-deck`. Presenter notes display the bounded rich/plain format defined in spec003;
preserved original rich markup remains a guarded fallback, never arbitrary
executable HTML. Notes remain immediately editable in the main window without
enabling slide editing.

Inventory/current-next/notes project only relevant dirty fields; note-only edits
do not regenerate visual sources. Sanitize rich-note fallback only on note projection.
Preview sources have a12MiB UTF-8 LRU budget; individual oversized sources remain
uncached. Bound owner-thumbnail frames to the sidebar viewport plus its 30px preload
margin, rendering every intersecting entry; keep2 presenter frames, releasing offscreen,
hidden, disconnected and closed sources. Resources are self-contained; account
common CSS/definition bytes separately. Authored root/body style/class changes
notify the shell through preview.onContextChange; shell invalidates presenter
context explicitly, preserving custom color bridges without a content poll.

Notes transfer validates a bounded native JSON file against native deck identity
before one owner transaction. A migrated deck may explicitly admit legacy-v2
notes through recorded original notes identity and validated existing slide IDs,
never through automatic cache discovery or timestamp merging. Timer is paused
at zero in a fresh owner tab, owner-held and ephemeral, preserved across popup
close/reopen; reset returns to zero paused. Authored `data-sf-duration` is finite
positive seconds (source minutes converted once); untimed dividers omit it.

The250ms clock message carries only elapsed/running/target/current duration.
Clock receive performs no inventory rebuild, rich-note parse, preview lookup or
fit. Disconnect disables editing/commands and releases sources, retaining close.
Import limits are2MiB JSON and200000 JavaScript string units per note. Capture
the document ticket after settlement; recheck after reading and final settlement,
changing only supplied validated notes paths in one transaction.

Migration provenance is `metadata.migration={family:'v19',sourceSha256,
legacyNotesDeckId}`. The converter discovers that original notes identity from
the explicitly supplied source; runtime legacy-v2 import compares it exactly.

Digest unavailable: warn and disable file-bound drafts, retaining complete export.
No weak-digest or whole-source storage fallback. Preview invalidation remains
targeted/lazy; do not regenerate all40 embedded-font documents on note input.

## Modules and scope ownership

| Module | Responsibility |
|---|---|
| document | Authored schema1 authority, indexed local sessions/history/assets, token metadata, journal-v2 recovery/export |
| interaction/images | Local scopes, composition/gestures/crop/cancel and async target validation |
| editor | Main controls/panels/navigation, dirty consumers and bounded thumbnails |
| preview | Nonexecuting sources, visual/context cache and bounded release/dispose lifetime |
| presenter | Authenticated navigation/timer commands, incremental read-only projections and clock |
| bounded converter | Render source, materialize/capture/convert private canvas, notes/assets/identities and live hooks |
| helper/skill | Inspect optional layout and operate on the actual saved migrated file |
| tests | Synthetic preservation/error/lifecycle cases and private real-file QA outside repo |

## Acceptance / verification

| AC | Observable proof | bug class |
|---|---|---|
| M1 | All40 ordered slides,1389 IDs,15 originals/7fonts and40 note contents retained; original SHA unchanged | migration loss |
| M2 | Source audience composition matches converted view; flow/inline edits don't displace unrelated siblings; image crops/filter/mask rendering retain intent | layout destruction |
| M3 | Native text/layout/image/guidance/notes save, actual download/fresh reopen, agent focused edit and source locality pass | incomplete handoff |
| M4 | Both live diagrams remain attached after gestures/undo, manual labels survive, no old editor/cache writer | derived-state overwrite |
| M5 | Local journal does not repeat unchanged originals; stale/corrupt recovery rejects atomically, publication retains earlier head, later checkpoints preserve recovered work; quota fallback exports full file | competing/oversized draft |
| M6 | Ordinary presenter tab, six keys/close, current-next/notes, isolated clock and fullscreen work offline; history/native-close/reopen preserve accepted work with one writer | missing presenter consumer |
| M7 | Both neutral designs retain prior behavior/palettes; malformed fields/messages/notes/source family fail safely | shared regression |
| M8 | Source/derived/exported output and helper validate; all private content/evidence outside repo; generated native file usable standalone | inactive migration/privacy |

Pre-code independent tests use actual UI/download/helper. Synthetic source family
may include grid, inline labels, contained/covered/stretched pictures, rich notes,
saved legacy edits and derived connectors. Private source is a read-only real
acceptance consumer, not a committed fixture. Root renders representative/full
slides and inspects actual private screenshots. Independent code verification
covers draft refs, gesture modes and presenter lifecycle.
