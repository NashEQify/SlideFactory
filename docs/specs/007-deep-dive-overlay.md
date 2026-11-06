# Deep-dive overlay — contract

Task 4, started by the user on 2026-11-06. While presenting, a double-click on a
marked object opens a deep-dive slide as an overlay above the current slide. The
room keeps one storyline; details come on demand without losing the thread. The
pattern comes from a consulting reference deck (one marked panel, zoom-in
cursor, dimmed backdrop, Esc/×/click outside closes); its content is not used.

This extends [Spec 001](001-working-package.md) (markup contract, helper) and
[Spec 003](003-editor-usability.md) (navigation, presenter, print, upgrades). One
complete offline HTML stays the working state; nothing about an open overlay is
saved.

## Markup

- **Deep-dive slide:** an ordinary slide section with `data-sf-deep-dive="<name>"`.
  The value is the name the agent sets when it builds the slide. An empty value
  means the default name `Deep Dive n`, where n counts deep-dive slides in deck
  order starting at 1. A deep-dive slide is never also `data-sf-hidden`.
- **Trigger:** any object (`data-sf-id`) on a storyline slide with
  `data-sf-deep-dive-target="<data-sf-slide of a deep-dive slide>"`. A slide may
  carry several triggers; each names one deep dive. Several triggers may name the
  same deep dive. Triggers on deep-dive slides are invalid (no nesting).
- **Slide links** (`a[data-sf-link]`) whose target is a deep-dive slide open it
  as an overlay instead of navigating.

The editor never generates names or triggers on its own; the agent writes them.
Removing a deep-dive slide leaves its triggers pointing nowhere; validation
reports that (see Helper), and in view mode such a trigger shows an error
instead of opening anything.

## Storyline

Deep-dive slides stay out of the storyline exactly like hidden slides in view
and fullscreen mode: PageDown/PageUp/arrows, Home/End, the pager count
(`Folie x / y`), presenter next-slide preview, parts and timing skip them. In edit
mode they are reachable like hidden slides, so they are edited like any slide.
The slide sidebar marks them `Deep Dive · <name>` instead of a storyline number.
Opening a deck at a deep-dive slide's hash in view mode shows its first trigger's
slide, or the first storyline slide when it has none, with the overlay open.

## Overlay

In view and fullscreen mode each trigger shows a zoom-in cursor and the hint
`Doppelklick für Details` (`title`), is focusable (`tabindex="0"`,
`role="button"`, accessible name `Details: <name>`), and opens its deep dive on
double-click or Enter/Space. Edit mode keeps double-click for text and image
editing and adds no trigger behavior.

The overlay:

- dims and blurs the main slide, which stays visible behind it;
- shows a faithful, non-editable render of the deep-dive slide (design CSS,
  embedded fonts, current color scheme and background) scaled to fit the stage
  with a visible margin, plus a header with the deep dive's name and a close
  button `×` (`Deep Dive schließen`);
- closes on Esc (where the browser delivers it), the close button, or a click
  outside the rendered slide; focus returns to the trigger;
- blocks storyline navigation keys while open, so PageDown never moves the main
  slide behind an open overlay;
- does not duplicate element IDs in the document, move authored nodes, change
  the save state or enter undo history.

Only one overlay is open at a time. Navigating away (slide list, hash, link)
closes it.

## Presenter view

Opening an overlay in the presentation window shows `Deep Dive offen: <name>` in
the presenter view, puts the deep dive in the current-slide preview and its
speaker notes in the notes area. The presenter view offers `Deep Dive schließen`;
closing from either window closes it in both and returns both to the main
slide. Timers keep running against the main slide.

## Print and handoff

The `Folien`, `Folien mit Notizen` and `Nur Notizen` modes print the selected
storyline slides first, then an appendix with the deep dives named by triggers
or slide links on those slides, in deck order, each once. A slide range counts
storyline slides only. Deep dives keep their authored composition; the printed
page adds nothing over the slide. Native browser printing follows the same order.

`HTML speichern` → *Weitergabe ohne Notizen* keeps deep-dive slides and triggers
and strips their notes and comments like any slide.

## Helper

`deck.py validate` rejects a trigger whose target is missing or is not a
deep-dive slide, a trigger on a deep-dive slide, and a slide with both
`data-sf-deep-dive` and `data-sf-hidden`. `deck.py inspect` reports per slide
`deepDive` (resolved name) or the list of trigger targets. `new`,
`extract-slide`, `replace-slide`, `insert-slide`, `reorder` and `upgrade-editor`
preserve both attributes.

## Release and starters

Editor 1.9.0; 1.8.0 joins `releases.json` so `upgrade-editor` lifts older decks.
The Clean MBB starter shows the pattern once: a panel on the findings slide opens
a deep-dive slide placed at the end of the deck. The skill tells the agent how
to mark deep dives and triggers and to name each deep dive with the user.

## Acceptance

Browser tests cover: navigation and pager skip deep dives in view mode and reach
them in edit mode; double-click and keyboard open the overlay, Esc/×/outside
click close it, navigation keys are blocked while open, and the document HTML
and save state are unchanged afterwards; several triggers on one slide open
their own deep dives with resolved names; a slide link to a deep dive opens the
overlay; presenter sync both ways; print order with appendix; handoff keeps deep
dives; save/reopen and helper edits keep the markup; validation rejects the three
invalid cases.
