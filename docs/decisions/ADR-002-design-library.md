# ADR-002 — Design library and two kinds of design change

Status: proposed technical direction; the two-operation distinction and the name
Clean MBB follow the user's clarification on 2026-11-04. This is a solve result,
not an implemented library or a locked low-level implementation contract.
Update 2026-11-05: the content-free Clean MBB starter (`mbb.html`,
`mbb-blank.html`) is delivered; catalogue, style-role contracts and procedural
apply remain open.

## Problem and current state

The shared skill ships Consulting and Editorial as neutral starter designs,
introduced with the first package (commit3d59f0b). They already have independent
CSS/layout sources and four common palettes, but do not form a managed design
library. Editor insertion still hard-codes Arial/32pt. Each saved deck embeds its
own design resources and shared editor; its latest HTML is authoritative.

A real native deck of the author has a custom reference design, now named **Clean
MBB** for the future library. It is neither Consulting nor Editorial. Preserve
its source, content, embedded fonts/assets and additional styles outside the
reusable repository. Its current templateId is legacy provenance, not a new
library identifier, and its sf-design block is only part of its visual resources.

## Chosen direction

Keep one self-contained offline HTML per saved deck. Separate maintained source
packages and independently version them; embed the selected versions/snapshots
when creating or changing a deck. Opening a deck never needs the library, a
server, an account or an external font request.

The library contains three distinct kinds of reusable material:

1. **Style packs:** palette roles, typography roles/defaults, fills, lines,
   corners and other declared styling of existing elements.
2. **Layout/diagram recipes:** slide compositions, object groups and diagram
   structures. An agent can use them for creating or rebuilding selected slides.
3. **Complete starters:** generated offline HTMLs that combine a design/style,
   neutral layout examples and the common editor for immediate use.

A catalogue records names, versions, examples and compatibility. Initial entries
are Consulting, Editorial and Clean MBB. Selection remains through paths/chat;
a graphical template chooser is not needed for this scope. A catalogue entry
does not itself prove that a private design has been extracted into a reusable,
content-free pack. Clean MBB extraction is future implementation work.

## Two explicit operations

**Decision 2026-11-05 (user): style packs change through the skill only.** A
saved HTML embeds exactly one design; it does not carry alternative style packs
or an in-browser pack switcher, to keep the file free of that overhead (decks are
built with an LLM anyway). Palettes and per-object formatting stay selectable in
the HTML as today. A style-pack change is a request to the agent: the skill
applies the pack procedurally, runs the checks below and writes a new file. An
in-HTML pack switcher remains a possible later extension, not part of this scope.

**Apply style, procedurally:** change only declared style roles/tokens of a known
compatible design family/adapter. Preserve slide/object identities, content,
hierarchy, notes/guidance, images/crops and authored frame geometry. Typography
can change rendered bounds/wrapping, and a declared style may intentionally move
CSS-positioned decoration; do not promise pixel identity after restyling.
Colors, font families and other supported properties switch without LLM work.

First analyze coverage and local overrides. Produce compatible, partial or
unsupported results with concrete reasons. Preserve explicit local overrides by
default; do not silently erase them to force an apparently successful switch.
Check every affected slide for new overflow/clipping and resource availability.
Write a distinct output only after the checked operation is acceptable; retain
the original. A partial result needs explicit acceptance before delivery as a
converted deck. Do not silently invoke an LLM or a different layout.

**Rebuild layout/diagram, with the agent:** use a recipe to deliberately change
compositions, grouping or diagram structure. This is separately requested work,
with visual/preservation checks and an explicit plan for retained versus replaced
objects. Existing IDs remain where objects survive; new IDs belong to new
objects. Registered diagram renderers may later automate specific structures,
but a universal automatic redesign engine is outside this simple library.

The operation boundary concerns structure/compatibility, not the file extension:
CSS can change layouts too, and diagram colors/lines can be ordinary style edits.

## Existing-deck adoption

| Input | Approach and promise |
|---|---|
| Native deck with known editor and unchanged look | Retain all actual design resources as an embedded snapshot; add optional provenance without rebuilding slides |
| Native deck with a supported style adapter | Procedural style application, coverage/override report and all-slide visual checks |
| Native custom reference design such as Clean MBB | Preserve first; extract content-free reusable styling/recipes and a tested adapter once, then reuse them |
| Modified/unknown editor or incompatible native schema | Keep existing refusal/inspection boundaries; do not assume the editor upgrader can convert it |
| Non-native HTML or another presentation format | Separate inspected conversion; no universal-import promise |

Shared source updates never overwrite a saved deck's pinned resources merely
because the catalogue has a newer version. Editor updates and style updates are
separate, explicit operations. Reuse the existing guarded editor upgrade and
source-span preservation. Do not make metadata origin labels authoritative over
the actual embedded CSS, fonts or local overrides.

## Evidence and limits

The reproducible synthetic probe is
the solve experiment.
Both stock designs survived metadata-only snapshot registration, real HTML
download/reopen and a subsequent checked CLI edit: 16 pixel comparisons matched
in the same Chromium environment; IDs, non-target object state and design CSS
were preserved. Trusted legacy editor upgrade retained source outside its
permitted spans; modified editor resources were refused without output.

A direct Consulting-to-Editorial CSS/palette swap changed computed typography and
colors but introduced two text overflows on the intro slide. The reverse switch
introduced none on the three probed slides. These are compatibility examples,
not blanket guarantees for either template family or arbitrary content.

A read-only browser dry run on that native deck changed font
families for 612/1801 registered text objects through its existing variables;
adding the known reference-stage font bridge reached 1801/1801. No source file
was changed or private output saved. This proves a procedural font-family route,
not whole-deck typography fit, complete size/color coverage or full redesign.

## Implementation handoff

1. Freeze and classify current embedded resource ownership; preserve backward
   compatibility with existing complete HTML and templateId/templateVersion.
2. Package the stock styles and layouts separately; extract a neutral Clean MBB
   design without private content or unapproved assets/fonts.
3. Define versioned style-role/adapter contracts and pinned-resource ownership;
   keep local overrides distinct and make editor insertion use design defaults.
4. Add catalogue discovery and guarded procedural application with actual
   coverage/overflow checks and real save/reopen/next-edit tests.
5. Keep recipe-driven rebuilds an explicit, separately authorized agent operation.
6. Later: one generated showcase HTML presenting each catalogued style pack on
   the same neutral example slides, so a pack can be chosen by looking at it.

Detailed manifest/metadata field schemas, CLI names, compatibility rules and
font/asset distribution must be specified and reviewed before product coding.
No production library, Clean MBB starter or procedural apply command is delivered
by this solve. Editor1.6.0 work from the previous request remains untouched.
