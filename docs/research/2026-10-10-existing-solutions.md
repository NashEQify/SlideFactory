# Existing solutions and reusable components

Investigated: 2026-10-10. Primary sources only. This is a source-backed comparison,
not a benchmark: products were not installed, migrated or tested end to end.
Documentation and upstream branch observations must be rechecked against pinned
versions before implementation. Independent checks are recorded in the
council consolidation.

## Slidev — the strongest challenger

Slidev combines Markdown with HTML/Vue, custom components, layouts, themes and
addons. Its design vocabulary is extensible rather than limited to a template
catalogue. [Syntax](https://sli.dev/guide/syntax),
[themes and addons](https://sli.dev/guide/theme-addon).

Its built-in MCP interface can read, update, insert, remove and reorder existing
slides. An update changes content, frontmatter or notes at slide granularity;
this is not an arbitrary selected-DOM-element editing tool. Browser source
editing and MCP operations save to the Markdown source.
[MCP](https://sli.dev/features/mcp),
[browser source editor](https://sli.dev/features/side-editor),
[browser save implementation](https://github.com/slidevjs/slidev/blob/main/packages/slidev/node/vite/loaders.ts),
[MCP save implementation](https://github.com/slidevjs/slidev/blob/main/packages/slidev/node/mcp/operations.ts).

Opt-in draggable elements support move, resize and rotation, with saved
positions in frontmatter or source directives. This is useful for the user's
bounded layout adjustments; it does not establish direct text editing for
arbitrary content. Drawings use a separate SVG annotation layer and need
persistence enabled. Semantic instructions to the agent still need a deliberate
representation. [Draggable elements](https://sli.dev/features/draggable),
[drawings](https://sli.dev/features/drawing).

Hosting produces a built web application. Whether the desired complete deck can
be delivered as one offline editable HTML file remains unproven. Current export
documentation includes editable PPTX, with image fallbacks; the old blanket claim
that every PPTX export consists only of screenshots would be incorrect.
[Hosting](https://sli.dev/guide/hosting), [exporting](https://sli.dev/guide/exporting).

**Adoption case:** use its source persistence, development loop and component
ecosystem if the required direct text/layout/guidance interactions can be added
with less lasting complexity than the native route. License: MIT.
[Project](https://github.com/slidevjs/slidev).

## PPTist — a substantial visual editor

PPTist offers broad visual element operations, grouping, alignment, notes,
annotations and presenter facilities. Its editable representation is its own
typed slide/element model. Arbitrary existing HTML authoring is not a documented
import route. New element types affect the model, editor, renderer and exports.
[Project/features](https://github.com/pipipi-pikachu/PPTist),
[element types](https://github.com/pipipi-pikachu/PPTist/blob/master/src/types/slides.ts),
[extension guide](https://github.com/pipipi-pikachu/PPTist/blob/master/doc/CustomElement.md).

JSON export and replacement import provide a concrete sequential handoff route.
Default import can append; the replacement branch must be selected when returning
an edited existing document. Existing updates can target element IDs.
[Export](https://github.com/pipipi-pikachu/PPTist/blob/master/src/hooks/useExport.ts),
[import](https://github.com/pipipi-pikachu/PPTist/blob/master/src/hooks/useImport.ts),
[store operations](https://github.com/pipipi-pikachu/PPTist/blob/master/src/store/slides.ts).

**Adoption case:** attractive if comprehensive human object construction becomes
central and the desired designs translate well to its model. This differs from
the confirmed LLM-led authoring scope. Current license: AGPL-3.0; a commercial
license is offered. Licensing and model migration are real commitments, not a
reason to treat private deck content as automatically public.
[License](https://github.com/pipipi-pikachu/PPTist/blob/master/LICENSE).

## Presenton — generation and editing application

Presenton supports self-hosting, generation, manual editing and custom templates.
Its model includes structured slide data and optional HTML content; describing it
as only a fixed-template generator would understate its scope.
[Project](https://github.com/presenton/presenton),
[slide model](https://github.com/presenton/presenton/blob/main/servers/fastapi/models/sql/slide.py),
[custom templates](https://docs.presenton.ai/v3/get-started/creating-custom-presentation-templates).

The inspected REST implementation can update stored slides and edit an existing
presentation while retaining its presentation ID. The built-in MCP uses a closed
generation/template/upload/status allowlist and excludes the other routes;
Electron disables this MCP server. Thus an external agent editing the user's
existing saved deck needs additional integration. REST editing capability and
built-in agent access are separate facts.
[Presentation endpoints](https://github.com/presenton/presenton/blob/main/servers/fastapi/api/v1/ppt/endpoints/presentation.py),
[MCP implementation](https://github.com/presenton/presenton/blob/main/servers/fastapi/mcp_server.py).

**Adoption case:** stronger if integrated generation and application editing become
the product priority. Today its application/data model and external-agent adapter
would add considerable scope. Local deployment alone does not determine which
configured AI providers receive content. License: Apache-2.0.
[Project/license](https://github.com/presenton/presenton).

## Components, rather than another complete platform

| Component | Useful capability | Boundary |
|---|---|---|
| [reveal.js](https://revealjs.com/markup/) | HTML slide playback, [speaker view](https://revealjs.com/speaker-view/), [print/PDF layout](https://revealjs.com/pdf-export/) | Presentation runtime, not an authored-source save loop; speaker view needs a local server. MIT. |
| [Moveable](https://github.com/daybrush/moveable) | DOM move/resize/rotate interaction | Supplies handles and events, not durable identity, authored-source mapping or diagram semantics. MIT. |
| [GrapesJS storage](https://grapesjs.com/docs/modules/Storage.html) | General visual editing with project persistence | Its own JSON project data is required for reliable reload; HTML/CSS alone are not its complete editable state. |

Recommendation: reuse narrow capabilities only where a demonstrated gap exists.
Do not combine independent editor models merely to collect features. No additional
component was selected, installed or copied during this investigation.
