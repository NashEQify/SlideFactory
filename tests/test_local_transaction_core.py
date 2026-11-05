# INFRA: none
"""Scoped-editor contract, derived before reading the replacement implementation.

Contract: editor-core-rewrite brief and root addendum, 2026-10-14.
The source files expose no spec_version; test_plan_spec_ref is that frozen date.
Only public UI, authored DOM/JSON, real file reloads and browser primitives are
used. Chromium/offline isolation is lifted from test_editor_e2e unchanged.

Producer fidelity: typing, formatting, nudge, crop, pointer streams and reload
use the actual browser/UI. Lost-beforeinput, IME and native-history events are
deliberate browser-boundary fault injections; they do not prove OS IME support.
The presenter-close test keeps note input in the owner editor and closes the
read-only projection before settling that input and checking reload durability.

Execution order: locality -> input baselines/grouping -> durability -> views.
TC-L01: changed-scope cost (4 cases); TC-L02: formatting/geometry/history cost;
TC-L03: missing-beforeinput; TC-L04: composition; TC-L05: native history (2);
TC-L06: cancel/pagehide; TC-L07: native close; TC-L08: bounded views/clock (2).
All contract requirements tested here are clear; this is a scoped matrix, not
sign-off for the complete rewrite, asset recovery or the private handoff.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect

from test_editor_e2e import (
    Elements, _cli, _edit, _frame, _json_script, _meta, _set_json_script,
    _slide_spans, browser_factory,
)
from test_migration_runtime import _asset, _native, _presenter

pytestmark = pytest.mark.e2e


def _fixture(tmp_path, template="consulting.html", *, slides=None):
    """Clone authored template sections, renaming every stable and ordinary ID.

    Three source layouts include nested text, flow/inline geometry and an SVG
    filter reference. An uncompressed synthetic original increases saved bytes
    without depending on private fonts/assets or random image generation.
    """
    path, first, old_asset, _ = _native(tmp_path, template, metadata={
        "notesProvenance": {"intro": {
            "html": "<p><strong>Original normalized</strong> speaker notes</p>",
            "text": "Original normalized speaker notes",
        }}
    })
    if slides is None:
        return path, first, "migration-text", "migration-flow", "migration-image"
    source = path.read_text(encoding="utf-8")
    originals = list(_slide_spans(source).items())
    meta = _json_script(source)
    asset, _ = _asset((128, 128), large=True)
    source = source.replace(old_asset, asset)
    source = source.replace('width="32" height="32"', 'width="128" height="128"')
    originals = list(_slide_spans(source).items())
    fragments, notes, guidance, provenance = [], {}, {}, {}
    for index in range(slides):
        old_id, fragment = originals[index % len(originals)]
        prefix = f"local-{index:04d}-"
        identities = {
            value
            for _, attrs in Elements(fragment).entries
            for name, value in attrs.items()
            if name in {"id", "data-sf-id", "data-sf-slide"}
        }
        for identity in sorted(identities, key=len, reverse=True):
            renamed = prefix + identity
            fragment = re.sub(
                rf'((?<![\w-])(?:id|data-sf-id|data-sf-slide)=["\']){re.escape(identity)}(["\'])',
                lambda match: match[1] + renamed + match[2], fragment,
            )
            fragment = fragment.replace(f"url(#{identity})", f"url(#{renamed})")
            fragment = fragment.replace(f'href="#{identity}"', f'href="#{renamed}"')
            fragment = fragment.replace(f"href='#{identity}'", f"href='#{renamed}'")
        slide_id = prefix + old_id
        notes[slide_id] = meta["notes"].get(old_id, "")
        guidance[slide_id] = meta["guidance"].get(old_id, {"text": "", "status": "open"})
        if old_id in meta.get("notesProvenance", {}):
            provenance[slide_id] = meta["notesProvenance"][old_id]
        fragments.append(fragment)
    source = source.replace(originals[0][1], "\n".join(fragments), 1)
    for _, fragment in originals[1:]:
        source = source.replace(fragment, "", 1)
    meta.update(notes=notes, guidance=guidance, notesProvenance=provenance)
    source = _set_json_script(source, meta)
    path = tmp_path / f"local-{slides}-{template}"
    path.write_text(source, encoding="utf-8")
    _cli("validate", path)
    return path, "local-0000-" + first, "local-0000-migration-text", "local-0000-migration-flow", "local-0000-migration-image"


def _object(page, identity):
    # Exact selectors avoid adding broad deck scans from the test itself.
    return page.locator(f'[data-sf-id="{identity}"]')


def _placement(locator):
    # Flow objects move through CSS translate, which the legacy absolute-frame
    # helper intentionally does not include. Observe the full authored offset.
    return locator.evaluate("""n=>({left:n.style.left,top:n.style.top,
      width:n.style.width,height:n.style.height,translate:n.style.translate,
      transform:n.style.transform,parent:n.parentElement.id})""")


def _probe(page, slide_id):
    """Observe costly platform primitives, with init/export outside the window.

    Exact-ID lookup and capture of the edited object remain allowed. Test reads
    use exact selectors or cached element handles, not a deck-wide inventory.
    """
    page.evaluate(r"""slideId => {
      const deck=document.getElementById('sf-deck');
      const deckId=JSON.parse(document.getElementById('sf-document').textContent).deckId;
      const closest=Element.prototype.closest;
      const state={deckClone:0,unrelatedClone:0,deckQuery:0,broadQuery:0,
        wholeHtml:0,unrelatedHtml:0,wholeMetadata:0};
      window.qaLocalCost=state;
      const unrelated=node=>node instanceof Element &&
        closest.call(node,'[data-sf-slide]')?.getAttribute('data-sf-slide')!==slideId &&
        !!closest.call(node,'[data-sf-slide]');
      const clone=Node.prototype.cloneNode;
      Node.prototype.cloneNode=function(...args){
        if(this===deck || this===document || this===document.documentElement)state.deckClone++;
        else if(unrelated(this))state.unrelatedClone++;
        return clone.apply(this,args);
      };
      for(const method of ['querySelector','querySelectorAll']) {
        const native=Element.prototype[method];
        Element.prototype[method]=function(...args){
          if(this===deck)state.deckQuery++;
          return native.apply(this,args);
        };
        const query=Document.prototype[method];
        Document.prototype[method]=function(selector,...args){
          if(/\[data-sf-(?:id|slide)\]/.test(selector))state.broadQuery++;
          return query.call(this,selector,...args);
        };
      }
      for(const property of ['innerHTML','outerHTML']) {
        const native=Object.getOwnPropertyDescriptor(Element.prototype,property);
        Object.defineProperty(Element.prototype,property,{...native,get:function(){
          if(this===deck || this===document.documentElement)state.wholeHtml++;
          else if(unrelated(this))state.unrelatedHtml++;
          return native.get.call(this);
        }});
      }
      const stringify=JSON.stringify;
      JSON.stringify=function(value,...args){
        if(value?.schemaVersion===1 && value.deckId===deckId && value.notes && value.guidance)
          state.wholeMetadata++;
        return stringify.call(this,value,...args);
      };
    }""", slide_id)


def _assert_local(page):
    costs = page.evaluate("window.qaLocalCost")
    assert costs and all(value == 0 for value in costs.values()), f"unrelated local-path work: {costs}"


def _settled_frames(page):
    page.evaluate("() => new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")


# TC-L01 (changed-scope cost, L3 public integration) | INFRA: none
@pytest.mark.parametrize("template", ["consulting.html", "editorial.html"])
@pytest.mark.parametrize("slides", [40, 400])
def test_authored_typing_cost_is_local_at_both_deck_sizes(tmp_path, browser_factory, template, slides):
    path, first, text_id, _, _ = _fixture(tmp_path, template, slides=slides)
    page = browser_factory(path)
    _edit(page)
    target = _object(page, text_id)
    target.dblclick()
    target.press("Control+A")
    _probe(page, first)
    page.keyboard.insert_text("A bounded local contribution")
    target.press("Escape")
    # Include the real prepared-draft timer, not just synchronous input handlers.
    page.wait_for_function("Object.values(localStorage).some(v=>v.includes('A bounded local contribution'))")
    expect(target).to_have_text("A bounded local contribution")
    _assert_local(page)
    page.reload()
    expect(_object(page, text_id)).to_have_text("A bounded local contribution")


# TC-L02 (precise scopes, L3 public integration) | INFRA: none
def test_font_nudge_crop_and_history_do_not_capture_unrelated_slides(tmp_path, browser_factory):
    path, first, text_id, box_id, image_id = _fixture(tmp_path, slides=40)
    page = browser_factory(path)
    _edit(page)
    text, box, image = (_object(page, identity) for identity in (text_id, box_id, image_id))
    size = "n=>getComputedStyle([...n.querySelectorAll('*')].reverse().find(e=>e.textContent.trim())||n).fontSize"
    font_before = text.evaluate(size)
    frame_before, crop_before = _placement(box), image.get_attribute("data-sf-crop")
    _probe(page, first)
    text.click()
    page.keyboard.press("Escape")
    page.get_by_role("button", name="Schrift vergrößern", exact=True).click()
    font_after = text.evaluate(size)
    assert font_after != font_before
    box.click()
    page.keyboard.press("ArrowRight")
    moved = _placement(box)
    assert moved != frame_before
    image.click()
    page.get_by_role("button", name="Bild zuschneiden", exact=True).click()
    page.get_by_label("Bildausschnitt", exact=True).fill("1.5")
    page.get_by_role("button", name="Übernehmen", exact=True).click()
    crop_after = image.get_attribute("data-sf-crop")
    assert crop_after != crop_before
    undo = page.get_by_role("button", name="Rückgängig", exact=True)
    undo.click()
    assert image.get_attribute("data-sf-crop") == crop_before and _placement(box) == moved
    undo.click()
    assert _placement(box) == frame_before
    undo.click()
    assert text.evaluate(size) == font_before
    for _ in range(3):
        page.keyboard.press("Control+Shift+z")
    assert image.get_attribute("data-sf-crop") == crop_after and _placement(box) == moved
    assert text.evaluate(size) == font_after
    _assert_local(page)


# TC-L03 (focus baseline fallback, L3 fault injection) | INFRA: none
def test_input_without_beforeinput_undo_restores_original_markup(tmp_path, browser_factory):
    path, _, text_id, _, _ = _fixture(tmp_path)
    page = browser_factory(path)
    _edit(page)
    target = _object(page, text_id)
    original = target.inner_html()
    assert "<em>source</em>" in original
    target.dblclick()
    target.evaluate("""n=>{
      n.textContent='Input delivered without its beforeinput event';
      n.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:'event'}));
    }""")
    target.press("Escape")
    page.get_by_role("button", name="Rückgängig", exact=True).click()
    assert target.inner_html() == original, "fallback must use the focus baseline, not already-mutated DOM"
    page.keyboard.press('Control+Shift+z')
    expect(target).to_have_text("Input delivered without its beforeinput event")


# TC-L04 (IME grouping, L3 injected browser event sequence) | INFRA: none
def test_composition_has_no_idle_commit_and_one_undo(tmp_path, browser_factory):
    path, _, text_id, _, _ = _fixture(tmp_path)
    page = browser_factory(path)
    page.clock.install()
    _edit(page)
    target = _object(page, text_id)
    original = target.inner_html()
    target.dblclick()
    target.evaluate("""n=>{
      n.dispatchEvent(new CompositionEvent('compositionstart',{bubbles:true,data:''}));
      n.dispatchEvent(new InputEvent('beforeinput',{bubbles:true,cancelable:true,
        inputType:'insertCompositionText',data:'前',isComposing:true}));
      n.textContent='前';
      n.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertCompositionText',
        data:'前',isComposing:true}));
    }""")
    page.clock.fast_forward(2000)
    expect(target).to_have_text("前")
    expect(page.get_by_role("button", name="Rückgängig", exact=True)).to_be_disabled()
    target.evaluate("""n=>{
      n.dispatchEvent(new InputEvent('beforeinput',{bubbles:true,cancelable:true,
        inputType:'insertCompositionText',data:'前後',isComposing:true}));
      n.textContent='前後';
      n.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertCompositionText',
        data:'前後',isComposing:true}));
      n.dispatchEvent(new CompositionEvent('compositionend',{bubbles:true,data:'前後'}));
    }""")
    target.press("Escape")
    page.get_by_role("button", name="Rückgängig", exact=True).click()
    assert target.inner_html() == original
    expect(page.get_by_role("button", name="Rückgängig", exact=True)).to_be_disabled()
    page.keyboard.press('Control+Shift+z')
    expect(target).to_have_text("前後")


# TC-L05 (single history owner, L3 browser event + native keyboard) | INFRA: none
@pytest.mark.parametrize("surface", ["text", "notes"])
def test_native_history_in_text_and_notes_uses_owner_order(tmp_path, browser_factory, surface):
    path, first, text_id, box_id, _ = _fixture(tmp_path)
    page = browser_factory(path)
    _edit(page)
    if surface == "text":
        target = _object(page, text_id)
        target.dblclick()
        target.press("Control+A")
        page.keyboard.insert_text("First committed owner contribution")
        target.press("Escape")
    else:
        page.get_by_role("button", name="Referentennotizen", exact=True).click()
        target = page.get_by_role("textbox", name="Referentennotizen", exact=True)
        target.fill("First committed owner contribution")
        target.blur()
    box = _object(page, box_id)
    before = _placement(box)
    box.click()
    page.keyboard.press("ArrowRight")
    after = _placement(box)
    assert after != before
    if surface == "text":
        target.dblclick()
    else:
        target.focus()
    prevented = target.evaluate("""n=>{
      const event=new InputEvent('beforeinput',{bubbles:true,cancelable:true,inputType:'historyUndo'});
      n.dispatchEvent(event);return event.defaultPrevented;
    }""")
    assert prevented, "native undo must be intercepted at the editing surface"
    assert _placement(box) == before, "owner undo must reverse the newer nudge before older text/notes"
    target.evaluate("n=>n.dispatchEvent(new InputEvent('beforeinput',{bubbles:true,cancelable:true,inputType:'historyRedo'}))")
    assert _placement(box) == after
    target.press("Control+z")
    assert _placement(box) == before
    target.press("Control+y")
    assert _placement(box) == after
    if surface == "text":
        expect(target).to_have_text("First committed owner contribution")
    else:
        assert _meta(page)["notes"][first] == "First committed owner contribution"


# TC-L06 (accepted vs cancelled durability, L4 actual reload) | INFRA: none
def test_cancelled_crop_never_recovers_but_pagehide_accepts_input_and_gesture(tmp_path, browser_factory):
    path, first, text_id, box_id, image_id = _fixture(tmp_path)
    page = browser_factory(path)
    _edit(page)
    image = _object(page, image_id)
    original_crop, original_frame = image.get_attribute("data-sf-crop"), _frame(image)
    page.get_by_role("button", name="Referentennotizen", exact=True).click()
    notes = page.get_by_role("textbox", name="Referentennotizen", exact=True)
    notes.fill("Accepted note before cancelled crop")
    notes.blur()
    page.get_by_role("button", name="Referentennotizen", exact=True).click()
    image.click()
    page.get_by_role("button", name="Bild zuschneiden", exact=True).click()
    page.get_by_label("Bildausschnitt", exact=True).fill("1.6")
    assert image.get_attribute("data-sf-crop") != original_crop
    page.get_by_role("button", name="Abbrechen", exact=True).click()
    page.wait_for_function("Object.values(localStorage).some(v=>v.includes('Accepted note before cancelled crop'))")
    page.reload()
    assert _meta(page)["notes"][first] == "Accepted note before cancelled crop"
    assert image.get_attribute("data-sf-crop") == original_crop and _frame(image) == original_frame
    _edit(page)
    target = _object(page, text_id)
    target.dblclick()
    target.press("Control+A")
    page.keyboard.insert_text("Accepted ongoing input at pagehide")
    page.reload()
    expect(target).to_have_text("Accepted ongoing input at pagehide")
    _edit(page)
    box = _object(page, box_id)
    before = _placement(box)
    box.click()
    grip = page.get_by_label("Objekt verschieben", exact=True).bounding_box()
    assert grip
    x, y = grip["x"] + grip["width"] / 2, grip["y"] + grip["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 31, y + 17)
    preview = _placement(box)
    assert preview != before
    # Reload drives the actual pagehide producer before pointerup/idle commit.
    page.reload()
    page.mouse.up()
    assert _placement(box) == preview


# TC-L07 (owner notes remain durable across projection close) | INFRA: none
def test_owner_note_input_survives_immediate_presenter_close(tmp_path, browser_factory):
    path, first, _, _, _ = _fixture(tmp_path)
    page = browser_factory(path)
    popup = _presenter(page)
    expect(popup.get_by_role("region", name="Referentennotizen", exact=True)).to_have_text("Original normalized speaker notes")
    page.get_by_role("button", name="Referentennotizen", exact=True).click()
    notes = page.get_by_role("textbox", name="Referentennotizen", exact=True)
    notes.fill("Owner contribution before popup close")
    popup.close()
    notes.blur()
    assert _meta(page)["notes"][first] == "Owner contribution before popup close"
    page.reload()
    assert _meta(page)["notes"][first] == "Owner contribution before popup close"


# TC-L08 (resource lifecycle + clock isolation, L3 public surfaces) | INFRA: none
@pytest.mark.parametrize("surface", ["thumbnails", "clock"])
def test_view_resource_budget_and_clock_projection_isolation(tmp_path, browser_factory, surface):
    path, first, _, _, _ = _fixture(tmp_path, slides=40)
    page = browser_factory(path)
    if surface == "thumbnails":
        _edit(page)
        overview = page.get_by_role("button", name="Folienübersicht", exact=True)
        # Both populated designs start with overview open. Establish its public
        # hidden state instead of assuming that the first toggle opens it.
        if overview.get_attribute("aria-pressed") == "true":
            overview.click()
        for _ in range(2):
            overview.click()
            expect(page.get_by_role("button", name=re.compile(r"^Folie 1$"))).to_be_visible()
            for number in (1, 8, 15, 22, 29, 36, 40):
                page.get_by_role("button", name=re.compile(rf"^Folie {number}$")).scroll_into_view_if_needed()
                _settled_frames(page)
                frames = page.locator('iframe[title^="Vorschau Folie"]')
                from test_thumbnail_coverage import assert_thumbnail_coverage
                assert assert_thumbnail_coverage(page) == frames.count(), "only viewport-demanded thumbnails keep browsing contexts"
            overview.click()
            _settled_frames(page)
            expect(page.locator('iframe[title^="Vorschau Folie"]')).to_have_count(0)
        return
    page.clock.install()
    popup = _presenter(page)
    expect(popup.get_by_role("region", name="Referentennotizen", exact=True)).to_have_text("Original normalized speaker notes")
    expect(popup.locator('iframe')).to_have_count(2)
    _probe(page, first)
    popup.evaluate("""()=>{
      window.qaClockProjection={htmlRead:0,htmlWrite:0,inventory:0,frameSource:0};
      const state=window.qaClockProjection;
      const html=Object.getOwnPropertyDescriptor(Element.prototype,'innerHTML');
      Object.defineProperty(Element.prototype,'innerHTML',{...html,
        get(){state.htmlRead++;return html.get.call(this);},
        set(value){state.htmlWrite++;return html.set.call(this,value);}});
      const append=Node.prototype.appendChild;
      Node.prototype.appendChild=function(node){
        if(this instanceof HTMLSelectElement)state.inventory++;
        return append.call(this,node);
      };
      new MutationObserver(records=>{
        state.frameSource+=records.filter(r=>r.target instanceof HTMLIFrameElement && r.attributeName==='srcdoc').length;
      }).observe(document.body,{subtree:true,attributes:true,attributeFilter:['srcdoc']});
    }""")
    timer = popup.get_by_role("timer")
    initial = timer.text_content()
    popup.get_by_role("button", name="Start", exact=True).click()
    page.clock.fast_forward(3000)
    expect(timer).not_to_have_text(initial)
    costs = popup.evaluate("window.qaClockProjection")
    assert costs and all(value == 0 for value in costs.values()), f"clock projected slide/notes content: {costs}"
    _assert_local(page)
    popup.close()
