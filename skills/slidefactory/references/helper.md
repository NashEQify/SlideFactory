# Focused operations on the saved HTML

Use Python 3; the helper has no third-party dependency. Replace the example
`/path/to/slidefactory` with the directory containing SKILL.md. Run it from any
working directory. Quote paths and text as shell arguments; avoid interpolating
untrusted text into executable shell syntax.

```bash
python3 /path/to/slidefactory/scripts/deck.py new --template /chosen/template.html --output /work/presentation.html --title 'A decision to make'
python3 /path/to/slidefactory/scripts/deck.py inspect /work/presentation.html
python3 /path/to/slidefactory/scripts/deck.py inspect /work/presentation.html --slide approach
python3 /path/to/slidefactory/scripts/deck.py set-text /work/presentation.html --element approach-step-1 --text 'Understand the decision'
python3 /path/to/slidefactory/scripts/deck.py guidance /work/presentation.html --slide approach --status addressed
python3 /path/to/slidefactory/scripts/deck.py scheme /work/presentation.html --id indigo-light
python3 /path/to/slidefactory/scripts/deck.py validate /work/presentation.html
```

`new` preserves the chosen complete template, examples, object IDs and design,
changes the document title and assigns a new deck/revision identity. Revise its
example contents into the new story. Ordinary mutations keep deck identity and
assign a new revision. They operate in place unless `--output /work/next.html`
is supplied. A failed validation leaves the destination untouched; writes use an
atomic sibling temporary file. `new --output` requires an existing parent folder.

`validate` also checks slide links (link objects and authored `href="#..."`
anchors inside slides): a missing target slide yields `"valid": false`, a
`linkErrors` list and exit status 1; schema errors still exit 2. Mutating
commands keep working on such decks and add `linkWarnings` to their result.
`inspect` also reports slide `duration`, `part` and `partDuration`; `validate`
rejects empty part labels, a part duration without part and conflicting budgets.
`inspect` lists each slide's `links` (`id`, `object`, `target`, `targetNumber`,
`text`); link objects also carry `link` with the target ID in `objects`.

`inspect` returns metadata, ordered slides, stable IDs, object text/geometry,
original image MIME/size/dimensions and crop, guidance and presenter notes.
Embedded assets and runtime source are omitted. `inspect --slide` accepts an ID
first, otherwise a one-based position. Mutating `--slide` arguments require IDs.
`scheme` selects a declared scheme; runtime derives its colors when opened, so
unchanged authored CSS does not need rewriting. Available schemes are in inspect.
For flow/inline objects, inspect reports the layout mode and authored movement
offsets separately from absolute geometry. Preserve their layout participation
when editing fragments. Notes provenance remains an immutable source extension;
edit canonical notes without replaying that original markup.

`set-text` replaces the entire inner content of one text-kind object with escaped
plain text. It intentionally removes inline emphasis/line-break markup. For a
partial sentence or mixed markup use a slide fragment instead. It rejects a text
container with nested editable objects. `guidance --text` reopens the entry;
`--status addressed` records completion while retaining text/unknown extensions.

## Structure and custom layouts

```bash
python3 /path/to/slidefactory/scripts/deck.py extract-slide /work/presentation.html --slide approach --output /work/approach.fragment.html
# Edit the fragment; preserve existing identities and useful markup.
python3 /path/to/slidefactory/scripts/deck.py replace-slide /work/presentation.html --slide approach --fragment /work/approach.fragment.html
python3 /path/to/slidefactory/scripts/deck.py insert-slide /work/presentation.html --fragment /work/new.fragment.html --after approach
python3 /path/to/slidefactory/scripts/deck.py reorder /work/presentation.html --order intro,approach,new-slide,outlook
```

A fragment is exactly one `<section class="sf-slide" data-sf-slide="...">` with
optional surrounding whitespace. Replacement keeps its target slide ID and
associated notes/guidance. Insertion requires new unique SF IDs and initializes
only that slide's note/guidance; default is append. IDs are never silently renamed
(ordinary SVG `id`/`url(#...)` references may depend on them). Reorder requires the
complete permutation of current IDs. There is no automatic delete-slide command;
when deleting a section directly, remove its metadata references and validate.

Untouched section, asset, runtime and CSS bytes are retained by the helper. Direct
source edits are possible, but update revision to a fresh UUID and validate before
handoff. Shared design/runtime changes belong to an explicit edit of that source,
not an accidental rebuild during a small deck correction.

## Checked common-editor updates

```bash
python3 /path/to/slidefactory/scripts/deck.py upgrade-editor /work/latest.html --output /work/updated.html
```

The destination must be distinct and must not already exist (including a
symlink). Publication is atomic and refuses clobbering a racing destination. The
original stays byte-for-byte unchanged. Actual CSS/runtime SHA256 pairs are
checked against the packaged trusted registry; input manifest claims alone do
not authorize replacement. Fingerprints normalize CRLF to LF only. Duplicate,
modified, mixed, unknown/newer resources and unsupported legacy files fail
before writing. Keep the original and inspect custom common-resource changes
when an update is refused; there is no force/merge mode.

Only the common CSS/runtime contents, editor manifest and saved revision token
change. All remaining UTF-8 source spans, custom hooks/styles, slides, SVG,
original images, metadata extensions and CRLF survive exactly. The output is a
single complete offline HTML, without companion resources. Validate and reopen
it before using it as the next working file.

`inspect --slide` includes optional `notesFormat` alongside plaintext notes and
historical provenance. Existing edit commands validate and preserve that pair.
`backgroundColor`, when present, is a six-digit hex override of the selected
palette's background. `scheme` clears this override. The browser's thumbnail
controls delete/move slides with shared Undo/Redo and recovery; the helper still
requires explicit source editing for deletion.

Inserted shapes remain `box` objects with a `data-sf-shape` subtype. Feedback
Post-its are `data-sf-postit` boxes with an identified text child; preserve both
IDs and their geometry. Their text is separate from slide guidance and presenter
notes. Optional boolean `postitsVisible` controls their shared visibility and
must survive helper edits and common-editor updates, including when false.
