# Offline print repair — bounded contract

Task006, user-authorized2026-10-15. This delta refines the print section of
[Spec003](003-editor-usability.md), preserving one complete offline HTML and
arbitrary authored slide composition. No editor architecture redesign.

## Outcome

Slides use16:9 paper,320×180mm with zero margins. Scale the1600×900 CSS-pixel
composition as a complete unit, including images/crops, SVG, embedded fonts,
foreground/background colors and authored layout. One selected slide per page,
no added final blank page. Browser settings retain final control of paper,
scale, headers/footers and backgrounds; the document requests correct defaults.

The compact dialog retains slide ranges and three modes: slides, slides with
notes below, only notes. Notes use A4 portrait with12mm margins; long paragraphs
and lists can continue across pages. Each selected slide/notes block starts a
new page. Notes-only must not require slide images or diagram readiness.

Ctrl/Cmd+P from the owner opens the same preparation dialog. Native browser-menu
printing also has correct slide page CSS and excludes editor chrome. beforeprint
is synchronous; do not pretend it awaits arbitrary async hooks. Fully awaited
custom layout preparation uses the dialog/toolbar path. Never open a nested print
window from beforeprint. Printing is not saving the deck.

Native print must also retain normal-flow content inside a larger transformed
stage, such as migrated 1920×1080 reference layouts scaled to 1600×900. Apply size
containment to the fixed print slide so the stage is not fragmented across page
boundaries. Keep its authored transform/layout dimensions; changing the stage to
zoom can alter diagram measurement. This is shared editor print behavior, also
available through checked editor updates, with a separate dialog-path check.

## Readiness and ownership

Prepared projections wait for registered sf:layout.waitUntil promises, embedded
fonts and decodable images, without depending on owner/popup animationframes.
Use browser layout/resource APIs, not a screenshot canvas or external PDF engine.
Keep isolated nonexecuting slide documents, their ID namespaces, custom CSS and
prepared transient diagram visuals.

Resource/layout failures must not silently produce incomplete slides. Keep bounded
waits with useful stage-specific errors; restore temporary hidden-slide styles
in finally. Closed/replaced requests cannot print over newer requests; retain
serialized preparation ownership. Print/cancel does not change revision, save
notice, content or selection except settlement of accepted edits. Native temporary
presentation state is ephemeral and cleaned up after printing.

Projected frames may need substantially longer than10s on large decks. Allow up
to120s per child resource-readiness request, show prepared/total progress, and
offer cancellation. After10s show that loading is continuing. Cancel, popup
close, replacement, failure and success dispose request timers/listeners. Keep
the separate10s owner custom-layout-hook guard; this is not a rendering rewrite.

## Package

All four complete starters contain one standard head element:
`<meta name="author" content="git@griessing.com">`.
The first repair shipped editor1.2.1; the readiness follow-up ships1.2.2 while
retaining trusted1.2.1 and earlier fingerprints. No new runtime dependency,
required helper, server, cloud API or companion file. Do not inject this author
into unrelated existing decks during editor-only upgrade.

Editor 1.2.4 adds native-print size containment for transformed inner stages and
retains trusted 1.2.3 fingerprints. This bounded CSS repair does not change stage
geometry, migration behavior, print readiness or the separate dialog path.

## Bounded evidence

Reproduce old native-paper behavior; distinguish natural background behavior from
injected stalled-animationframe evidence. Generate a small set of PDFs from a
neutral offline file: native print, prepared slides, notes with overflow, and
notes-only/ranges. Check paper dimensions, images/crops, edge content, text/fonts,
SVG and rendered appearance. Exercise one HTML download and fresh offline reopen.
Keep fault/error/cancellation checks scoped to print; no full suite/browser matrix.

One independent focused code verification covers print entry points, readiness,
cleanup and authored-state preservation. Root reviews decisive claims and rendered
output before delivery. User authorizes implementation and bounded verification.

## Registration

User steering during delivery: move the existing shared Post-it visibility icon
into the top bar in both modes. The slide's bottom-right overlay contains only
fullscreen. Visibility semantics and saved metadata remain unchanged.

This contract refines [Spec 003](003-editor-usability.md); README and skill guidance follow it.
