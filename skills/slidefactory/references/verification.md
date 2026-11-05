# Check the real saved result

Use the actual output file, not the starter or an invented state. Run
`python3 scripts/deck.py validate FILE` relative to this skill, and inspect affected
IDs/guidance afterward. Validate detects structure/schema/asset/crop errors; it
does not evaluate the story or whether text overflows.

For normal deck changes, open file://, check affected slides at a realistic
presentation size, and verify the claim, hierarchy, spacing and legibility.
Check expected diagrams/images and the chosen palette. A small text change needs
this bounded check; it does not require rebuilding or retesting the whole editor.

For editor, persistence or handoff changes:

- Make representative text/layout changes and leave a note and agent guidance.
- Insert/replace a raster image, crop it, then re-crop or cancel; retain originals.
- Download through **HTML speichern**, reopen the actual download in a fresh
  browser context, and verify text, frames, colors, notes/guidance and image crop.
- Apply an agent change to that saved file and reopen it in a context with the
  old draft. The new file must win. Even a direct CSS/meta edit at the same
  revision must not replay a draft from a different original parsed source.
- Test offline without remote resources. Browser storage may fail; HTML export
  must still work and the user must see a useful storage warning.
- With flow/inline layouts, move a target without displacing its siblings or
  freezing dimensions; test requested resize and undo. Check live connector
  attachments and preserve manually positioned labels through redraw/reopen.
- For timer changes, start the presenter timer and confirm the popup keeps
  counting when no owner clock messages arrive (background throttling); check
  slide time, pace (growing deficit beyond a slide's duration), part scope,
  continuity across back navigation, backup jump and Backspace return, pause
  and reset.
- With Referentenansicht, verify current/next, notes, navigation and timer after
  popup close/reopen. Notes appear once and are read-only; main-window changes
  update that view and survive the actual download. Retained rich notes cannot
  overwrite edited canonical text. X and Escape close even after disconnection.

Use a browser capable of local file previews/downloads. Automated Playwright is
optional development tooling, never required to use a finished presentation.
Avoid claiming a browser/visual check if only source validation ran; name that
limitation. Keep synthetic checks/screenshot evidence outside private client work.

For the common editor's expanded controls:

- Drag a textbox from its interior with the real pointer, then Undo. Click at a
  text position and type; dragging while typing must still select text. Check
  cancellation, transformed/flow coordinates and a saved-file reopen. For the
  editorial starter, verify separate circle/line/panel controls and that deleting
  the panel preserves the overlaid text. Keep these checks scoped to the change.
- Edit notes without entering slide edit mode. Apply mixed B/I, sizes and both
  list types in the main window; test immediate read-only presenter updates and
  Undo/keyboard Redo, then download, validate, edit with the helper and reopen.
  Drag the horizontal divider above the bottom notes pane and check that the
  slide shrinks to fit; keyboard resizing and Escape cancellation preserve
  document state. Check viewport bounds and no extra heading/close row.
- Move/delete active and inactive slides. Check stable IDs, next/previous focus,
  the final-slide guard, restored notes/images and draft recovery. Stress mixed
  moves around a checkpoint; final ID order must survive coalescing and reload.
- For thumbnail dragging, use actual mouse motion to check a drop, one-step
  Undo/Redo, cancel/no-op and edge scrolling. Reopen a real saved HTML and check
  stable order/IDs/notes/guidance; motion must not clone or serialize the deck.
  Keep these checks focused instead of repeating the whole editor suite.
- Resize the overview with pointer and keyboard (arrows/Shift/Home/End); Escape
  cancels a drag. Check no horizontal overflow at narrow widths and browser zoom.
  Resize selected objects with focused handles and keyboard, then Undo/Redo.
- Test custom background preview, save/reopen, print, Undo and named-palette reset.
- Print actual browser PDFs in all three modes with a selected range. Verify
  images/crops, fonts, shared SVG definitions, delayed registered diagrams, full
  edges, long flowing note paragraphs/list items and final text. Inspect rendered
  PDF pages; a screen preview alone does not prove pagination. Invalid ranges
  remain in the dialog with a useful message; print/cancel leaves save status and
  revision unchanged apart from accepted edit settlement.
- For print-engine changes, include direct browser-menu printing at16:9 with
  complete edge content and Ctrl/Cmd+P opening the mode/range dialog. Keep a
  real offline downloaded/reopened file as input. Distinguish a deliberately
  stalled animationframe probe from a naturally reproduced background-tab failure.
  Focus on the affected paths; do not automatically run the full editor suite.
- For migrated scaled stages, use neutral input through the actual migration
  helper. Print native browser PDFs with `prefer_css_page_size=True` and
  `print_background=True`; inspect Flex/Grid bodies, footers and image pixels,
  not extracted text alone. Check the dialog path separately. Preserve the
  authored stage dimensions/transform; fixed print slides use size containment.
- For slide links, insert one through the slide list, retarget, Undo/Redo, drag,
  edit the label and delete/restore it; clicks in edit mode must not navigate.
  Reorder the target, then in view mode follow it, page with the arrows and
  return via Backspace and the chip. Delete a target: the link is outlined and
  `validate` reports it. Save, reopen and follow the link in the fresh file.
- Upgrade an actual saved/downloaded synthetic deck, including CRLF and custom
  resources. Compare all bytes outside the permitted spans, reopen offline, and
  test rejection of modified/mixed/forged resources and existing destinations.
