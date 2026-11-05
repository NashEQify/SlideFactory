# Editor experience

Date: 2026-10-15. The approved toolbar increment
adds insertion, rich text tools and feedback objects; its
build record distinguishes packaging
and static evidence from older executed browser checks.
Earlier user-confirmed scope: direct text/layout adjustments, image
insertion and cropping, and saved slide-local agent input. The user rejects the
floating editor dock and visible position/element-size number fields. The [implementation contract](../specs/001-working-package.md) governs behavior;
offline browser/download and agent handoff verification passed.

## Where the editor lives

The skill provides the agent's method and points to reusable resources. The starter
HTML is a whole-deck skeleton that already contains the built editor. Reusable
HTML/CSS/JavaScript source implements controls, gestures, image handling and save;
maintenance builds embed it into the ready starter. On creation, the agent uses
that starter to deliver one private presentation HTML. The browser runs its
embedded editor. These are roles, not files the human manually assembles.

Implemented resource boundaries:

- `skills/slidefactory/`: instructions, ready starter, authoring references and helpers.
- `skills/slidefactory/assets/starter.html`: complete whole-deck starter including editor.
- `src/editor/`: maintained shared editor source, embedded into the ready starter.

The [package layout](package-layout.md) explains invocation from a new
engagement chat. These paths exist in the package.

The starter fixes reusable behavior and recognizable structure; it does not fix
the slide count, story, layouts or diagram vocabulary. Editor styling is scoped
separately from the presentation's individual design. Runtime updates are explicit.

## Recommended working surface

The user approved a compact two-level toolbar on 2026-10-14. The top row puts
Undo and overview immediately after SlideFactory, before comments and the global
actions. The ribbon starts with format painter, then insertion, font/paragraph,
object and Post-it tools, followed by palette/background. Tool availability
follows the selection. The counter sits above the thumbnails; fullscreen is a
slide-local bottom-right control. Icon buttons center their contents. The yellow highlighter
acts on a text selection or the whole selected text block and can remove the
highlight again. No always-visible X/Y/width/height fields.

The slide is the main surface. Move objects with the mouse or arrow keys; Shift
uses a larger nudge. Scale via handles, with images proportional by default.
Ordinary textboxes can be dragged from their interior: pointer movement starts
the existing object gesture, while a click without dragging enters text editing.
During active text editing, dragging retains native text selection; Escape leaves
typing so the surface can move again. Cancelled gestures leave no geometry change.
In editable text, arrows navigate the text rather than move the object. In crop
mode they adjust the image/crop rather than change slides. Undo must cover gestures
and cropping. Selection needs visible focus and keyboard-reachable actions.
Delete removes a selected image or text block with Undo when focus belongs to
the object or its selection controls. In text editing, notes and other input
fields it retains normal input behavior. Escape returns from text editing to
the object selection.

An optional narrow thumbnail strip helps navigation and storyline overview.
The **Kommentare** area opens beside the slide on demand and stays associated
with that slide. It does not obscure the working canvas or open live chat. Speaker
notes remain separate and are immediately editable in either mode. The notes
toolbar contains B/I, a pt dropdown and two square list pictograms. Text controls
also offer alignment/list pictograms; redo is a keyboard action. The presenter
launch is visible outside slide editing. The left strip supports edge/keyboard
resize, collapse and slide move/delete with local history. In edit mode,
thumbnail dragging shows an insertion line and scrolls near the list edges.
Drop is one reversible move; Escape or an outside drop cancels. Alt+ArrowUp/Down
on a focused thumbnail replaces the removed move-arrow buttons. A native background
picker beside the palette persists a custom color; named palette selection resets it.

The approved ribbon has no tabs or third toolbar row. Its six-shape palette uses
icons: rectangle and rounded rectangle cover square proportions, alongside left
and right arrows, oval and line. Post-its use whole-surface dragging, double-click
text editing, resize controls and a top-right ×. Their global visibility persists
without deleting content. Its icon is in the top bar in both modes; fullscreen
is the only bottom-right slide control and is hidden while fullscreen is active.
F toggles fullscreen through the existing action, except during text entry,
form-field use or dialogs. Modifier shortcuts, key repeats and composition are
not intercepted; Escape remains available to exit fullscreen.

Slide links (1.3.0) are text objects on `<a data-sf-link href="#slide-id">`; the
target is the stable slide ID, chosen from a slide list (chain icon) and changed
with the crosshair icon via an `attrs` history step. Their look is the neutral
token-based `.sf-link` rule (mirrored into projections) refined by design CSS.
Editing never navigates. In view/fullscreen, following any `#slide` anchor in a
slide pushes the origin ID on a small in-memory jump stack (20 entries); the
transient bottom-centre chip and Backspace (outside text entry; forwarded from the
presenter) pop it. Landing on the top origin by other navigation pops it too.
The stack is not saved. Missing targets get a transient edit-mode outline.

The editorial starter's three circles, their connector and the dark intro panel
are individual standard shape objects. They retain the design's palette colors
and can be moved, resized, recolored or deleted with Undo. The panel is separate
from its overlaid text. This changes the starter's authored objects; upgrading
only the common editor of an existing saved file does not rewrite its decoration.

## Image core

Insertion: a visible image action/file picker, plus drag/drop and image paste as
supported convenient routes. Imported pictures become embedded deck assets rather
than depend on a linked local path. Replacing a picture can preserve its frame
where useful. The file picker accepts PNG, JPEG and WebP; original bytes remain embedded.

Crop sequence:

1. Select the picture; use Crop or double-click.
2. Show the retained frame and a subdued view of excluded areas, with crop handles.
3. Drag handles to change the frame, move the picture within it, and zoom if needed.
4. Apply with Enter/a visible action; cancel with Escape/a visible action.

Retain the original picture and editable crop information. Undo/re-crop must not
require recovering an image that was destructively overwritten. The complete
saved HTML carries the asset, crop, geometry and identity so the next agent can
preserve or intentionally change the effective result. This extends the
editing vocabulary with images; it does not require a general visual slide builder.

Interaction precedent: [Google Slides image cropping](https://support.google.com/docs/answer/4600160?co=GENIE.Platform%3DDesktop&hl=en)
uses selected-image crop handles and confirmation by Enter or clicking elsewhere,
and offers image reset. This informed the interaction choice. Actual SlideFactory behavior is covered
by real download/reopen and crop/undo tests.

## Save feedback

Keep complete-file saving visible, with language that distinguishes browser-local
changes from the saved handoff file. **Fertig** leaves editing; **HTML speichern**
creates the complete current file. A note or inserted image must be included in
the same save. The user's existing browser/file/chat handoff remains the workflow.

The download action honestly reports `HTML-Download gestartet`; it cannot
confirm final disk placement. A separate persistent footer notice now distinguishes
opened-file state, unsaved browser changes (including accepted recovery) and
download started. Done, navigation and other messages do not erase it. Further
edits renew the unsaved notice. Undo or cancelled previews conservatively keep
the notice; no complete-deck comparison is performed for this UI.
The user explicitly chose this small notice and the existing HTML-download path;
no direct-file adapter, helper or extra working files are required.
The [editor addendum](../specs/003-editor-usability.md) specifies the implemented
notes, printing, slide actions and draggable thumbnail width. A compact print
dialog accepts slide numbers/ranges and selects slides, slides with notes below,
or notes only. Whole-slide output retains raster crops and backgrounds; long notes
continue onto later pages. Notes import/export controls are removed. Printing
does not mark the working HTML as saved.
The [offline print repair](../specs/006-offline-print-repair.md) adds the same
16:9 geometry to direct browser printing and Ctrl/Cmd+P access to the dialog.
Notes use A4 portrait. Prepared printing awaits resources and custom layout
promises without waiting for a screen paint; native printing runs synchronous
layout only. Bounded PDF evidence records
actual offline output, long-note flow and saved-file reopen.

## Verification and retained prototype history

The implemented starter is verified for image insertion, proportional resize, crop,
undo and repeated crop adjustment as well as text/layout/guidance. Save, reopen
offline in a fresh browser, give that file to the agent for a small unrelated
change, then confirm image/crop/notes preservation. Test gestures at different
preview scales. Avoid treating a purely visual mockup as proof of persistence.

The neutral UI mockup was checked for crop-handle interaction/application/cancel,
proportional image resize, selection-dependent tools, opening guidance, both
toolbar variants, light/dark appearance and horizontal fit at 1024/760/320px.
It is response content outside the product repository. Its file-save action is
disabled; it does not implement the actual deck save loop. No private deck was
modified by that earlier UI mockup. Production editor source was added later
under `src/editor/`, and is checked using real files/downloads rather than the mockup.
