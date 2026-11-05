# INFRA: none
"""Task 002 / reference-migration v1: independent native runtime contracts.

Only generated ready files, public DOM/metadata/UI, actual browser storage,
downloaded HTML and the production CLI are driven. All assets are synthetic;
original private decks and newly implemented runtime code are never fixtures.
The existing Task 001 local browser/handoff infrastructure is lifted unchanged.
"""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path
import re

from PIL import Image
import pytest
from playwright.sync_api import expect

from test_editor_e2e import _presenter_action
from test_editor_e2e import (
    Elements, PACKAGE, _cli, _download, _draft_flushed, _drag, _edit, _frame,
    _json_script, _meta, _notes_guidance, _set_json_script, _slide_ids,
    _slide_spans, browser_factory, images,
)

pytestmark = pytest.mark.e2e

TEXT = "migration-text"
FIRST = "intro"
LAYOUT_IDS = {"flow": "migration-flow", "inline": "migration-inline"}


def _asset(size=(32, 32), *, large=False):
    image = Image.new("RGB", size, "#246a82")
    output = io.BytesIO()
    # An uncompressed valid PNG exercises real quota without a network or RNG.
    image.save(output, format="PNG", compress_level=0 if large else 9)
    payload = output.getvalue()
    return "data:image/png;base64," + base64.b64encode(payload).decode(), payload


def _native(tmp_path, name="starter.html", *, large=False, metadata=None):
    source = (PACKAGE / "assets" / name).read_text(encoding="utf-8")
    slides = _slide_spans(source)
    first = next(iter(slides))
    document = _json_script(source)
    document["notes"][first] = "Original normalized speaker notes"
    document["guidance"][first] = {"text": "Original separate guidance", "status": "addressed"}
    document["syntheticMigration"] = {"fixture": True}
    if metadata:
        document.update(metadata)
    source = _set_json_script(source, document)
    data_url, payload = _asset((1240, 1240) if large else (32, 32), large=large)
    authored = (
        '<h1 data-sf-id="migration-text" data-sf-kind="text" '
        'style="position:absolute;left:80px;top:80px;width:650px;height:85px;'
        'font-size:48px">Migration <em>source</em> baseline</h1>'
        '<div id="migration-scaled" style="position:absolute;left:120px;top:280px;'
        'width:1200px;height:580px;transform:scale(0.833333333333);transform-origin:0 0">'
        '<div id="migration-flex" style="display:flex;width:700px;height:80px;gap:20px">'
        '<div data-sf-id="migration-flow" data-sf-kind="box" data-sf-layout="flow" '
        'style="flex:1;min-width:120px;transform:rotate(2deg);background:var(--sf-accent)">'
        '<svg width="50" height="50" viewBox="0 0 50 50"><defs>'
        '<filter id="migration-filter"><feGaussianBlur stdDeviation="0.3"/></filter>'
        '</defs><circle cx="25" cy="25" r="15" filter="url(#migration-filter)" '
        'fill="var(--sf-text)"/></svg></div>'
        '<div id="migration-flow-sibling" style="width:220px;background:var(--sf-surface)">'
        'Flow sibling remains in place</div></div>'
        '<p id="migration-paragraph" style="position:absolute;left:0;top:150px;'
        'width:760px;line-height:45px;font-size:30px">'
        '<span data-sf-id="migration-inline" data-sf-kind="text" data-sf-layout="inline" '
        'style="transform:rotate(0deg);color:var(--sf-accent)">Inline label</span>'
        '<span id="migration-inline-sibling"> unchanged inline sibling</span></p>'
        '<div data-sf-id="migration-absolute" data-sf-kind="box" '
        'style="position:absolute;left:820px;top:130px;width:120px;height:80px;'
        'transform:rotate(3deg);background:var(--sf-accent2)">Absolute control</div>'
        '<div data-sf-id="migration-image" data-sf-kind="image" '
        'data-sf-crop=\'{"x":0,"y":0,"w":1,"h":1}\' '
        'style="position:absolute;left:850px;top:280px;width:170px;height:170px;overflow:hidden">'
        f'<img src="{data_url}" width="{1240 if large else 32}" height="{1240 if large else 32}" '
        'alt="Synthetic original asset" style="position:absolute;left:0;top:0;width:170px;height:170px">'
        '</div></div>'
    )
    # A second authored use must reuse the original source index in compact drafts.
    if large:
        authored += (
            '<div data-sf-id="migration-image-copy" data-sf-kind="image" '
            'data-sf-crop=\'{"x":0,"y":0,"w":1,"h":1}\' '
            'style="position:absolute;left:1300px;top:700px;width:80px;height:80px;overflow:hidden">'
            f'<img src="{data_url}" width="1240" height="1240" alt="Repeated original" '
            'style="position:absolute;left:0;top:0;width:80px;height:80px"></div>'
        )
    original = slides[first]
    opening = re.match(r"<section\b[^>]*>", original)[0]
    source = source.replace(original, opening + authored + "</section>", 1)
    head = '<style id="migration-source-style">/* MIGRATION_HEAD_BASELINE */ '
    head += '.sf-slide[data-sf-slide="' + first + '"]{font-family:system-ui} '
    if large:
        head += "/*" + "synthetic retained head " * 50000 + "*/"
    source = source.replace("</head>", head + "</style></head>", 1)
    path = tmp_path / ("large-native.html" if large else name)
    path.write_text(source, encoding="utf-8")
    return path, first, data_url, payload


def _object(page, object_id):
    return page.locator(f'#sf-deck [data-sf-id="{object_id}"]')


def _authored(locator):
    return locator.evaluate("""n => ({
      parent:n.parentElement.id, layout:n.dataset.sfLayout || 'absolute',
      position:n.style.position, left:n.style.left, top:n.style.top,
      translate:n.style.translate, width:n.style.width, height:n.style.height,
      transform:n.style.transform, display:n.style.display,
      flex:n.style.flex
    })""")


def _rect(locator):
    result = locator.bounding_box()
    assert result and result["width"] > 0 and result["height"] > 0
    return result


def _assert_same_rect(before, after):
    assert after == pytest.approx(before, abs=0.6)


def _edit_text(page, value):
    target = _object(page, TEXT)
    target.dblclick()
    target.fill(value)
    target.press("Escape")
    expect(target).to_have_text(value)


def _close_panel(page):
    close = page.get_by_role("button", name="Schließen", exact=True)
    if close.count() and close.is_visible():
        close.click()


def _drafts(page):
    return page.evaluate("() => Object.entries(localStorage).map(([key,value]) => ({key,value}))")


def _draft(page):
    page.wait_for_function(
        "Object.values(localStorage).some(value => value.includes('Migration draft contribution'))",
        timeout=5000,
    )
    deck_id = _meta(page)["deckId"]
    key = "slidefactory:" + deck_id
    head = next(entry for entry in _drafts(page) if entry["key"] == key)
    value = json.loads(head["value"])
    assert value["draftVersion"] == 2
    assert value["base"]["deckId"] == deck_id
    assert value["head"], "a published journal head must identify its immutable entry"
    return key, value


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child)


def _replace_string(value, before, after):
    if isinstance(value, str):
        return value.replace(before, after)
    if isinstance(value, dict):
        return {key: _replace_string(child, before, after) for key, child in value.items()}
    if isinstance(value, list):
        return [_replace_string(child, before, after) for child in value]
    return value


def _identity_fields(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(child, str) and re.search(r"session|deck|token", key, re.I):
                yield key, child
            yield from _identity_fields(child)
    elif isinstance(value, list):
        for child in value:
            yield from _identity_fields(child)


def _assert_complete_original(page, data_url):
    expect(_object(page, TEXT)).to_have_text("Migration source baseline")
    assert _object(page, "migration-image").locator("img").get_attribute("src") == data_url
    assert _meta(page)["notes"][_slide_ids(page)[0]] == "Original normalized speaker notes"
    assert _object(page, "migration-flow").get_attribute("data-sf-layout") == "flow"


def _presenter(page):
    assert page.get_by_role("button", name="Referentenansicht", exact=True).count() == 1, "RED: presenter consumer control missing"
    with page.expect_popup() as opened:
        _presenter_action(page)
    popup = opened.value
    popup.wait_for_load_state()
    return popup


# TC-R01 (M2/M3, L3 regression) | INFRA: none
@pytest.mark.parametrize("layout", ["flow", "inline"])
def test_flow_and_inline_movement(tmp_path, browser_factory, layout):
    path, first, _, _ = _native(tmp_path)
    page = browser_factory(path, viewport={"width": 1100, "height": 820})
    _edit(page)
    target = _object(page, LAYOUT_IDS[layout])
    sibling = page.locator(f"#migration-{layout}-sibling")
    original = _authored(target)
    original_rect = _rect(target)
    sibling_rect = _rect(sibling)
    target.click()
    _drag(page, page.get_by_label("Objekt verschieben", exact=True), 44, 21)
    moved = _authored(target)
    moved_rect = _rect(target)
    assert moved_rect["x"] - original_rect["x"] == pytest.approx(44, abs=2)
    assert moved_rect["y"] - original_rect["y"] == pytest.approx(21, abs=2)
    _assert_same_rect(sibling_rect, _rect(sibling))
    for field in ("parent", "layout", "transform", "width", "height", "flex", "display"):
        assert moved[field] == original[field], f"drag froze or rewrote {field}"
    if layout == "flow":
        assert moved["translate"] != original["translate"]
        assert moved["position"] == original["position"]
        assert moved["left"] == original["left"] and moved["top"] == original["top"]
    else:
        assert moved["position"] == "relative"
        assert moved["left"] != original["left"] and moved["top"] != original["top"]
    target.click()
    if target.get_attribute("contenteditable") == "true":
        page.keyboard.press("Escape")  # a text click places the caret; return to object selection
    page.keyboard.press("ArrowRight")
    assert _rect(target)["x"] > moved_rect["x"]
    page.get_by_role("button", name="Rückgängig", exact=True).click()
    assert _authored(target) == moved
    page.get_by_role("button", name="Rückgängig", exact=True).click()
    assert _authored(target) == original
    page.keyboard.press('Control+Shift+z')
    assert _authored(target) == moved
    saved = _download(page, tmp_path / f"{layout}-saved.html")
    _cli("validate", saved)
    focused = json.loads(_cli("inspect", saved, "--slide", first).stdout)
    inspected = next(item for item in focused["slide"]["objects"] if item["id"] == LAYOUT_IDS[layout])
    assert inspected["layout"] == layout
    assert any(key in inspected for key in ("offsets", "authoredOffsets", "translate", "frame"))
    fresh = browser_factory(saved, viewport={"width": 1100, "height": 820})
    assert _authored(_object(fresh, LAYOUT_IDS[layout])) == moved
    # Standalone reopening intentionally starts in presentation mode. Compare
    # geometry with the same toolbar/view state as the original measurement.
    _edit(fresh)
    _assert_same_rect(sibling_rect, _rect(fresh.locator(f"#migration-{layout}-sibling")))


# TC-R02 (M2/M3, L3 boundary) | INFRA: none
@pytest.mark.parametrize("layout", ["flow", "inline"])
def test_flow_inline_resize_history(tmp_path, browser_factory, layout):
    path, _, _, _ = _native(tmp_path)
    page = browser_factory(path)
    _edit(page)
    target = _object(page, LAYOUT_IDS[layout])
    original = _authored(target)
    rect = _rect(target)
    target.click()
    resize = page.get_by_role("button", name="Größe ändern unten rechts", exact=True)
    _drag(page, resize, 35, 19)
    resized = _authored(target)
    assert _rect(target)["width"] > rect["width"] + 10
    assert resized["parent"] == original["parent"]
    assert resized["transform"] == original["transform"]
    if layout == "inline":
        assert resized["display"] == "inline-block"
    page.get_by_role("button", name="Rückgängig", exact=True).click()
    assert _authored(target) == original
    target.click()
    grip = _rect(page.get_by_label("Objekt verschieben", exact=True))
    x, y = grip["x"] + grip["width"] / 2, grip["y"] + grip["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 70, y + 20)
    assert _authored(target) != original
    page.keyboard.press("Escape")
    page.mouse.up()
    assert _authored(target) == original
    page.keyboard.press('Control+Shift+z')
    assert _authored(target) == resized


# TC-R03 (M5, L4 positive) | INFRA: none
def test_compact_original_source_draft(tmp_path, browser_factory, images):
    path, first, data_url, original_bytes = _native(tmp_path, large=True)
    assert path.stat().st_size > 12_000_000
    page = browser_factory(path)
    _edit(page)
    _edit_text(page, "Migration draft contribution")
    target = _object(page, "migration-image")
    target.click()
    _drag(page, page.get_by_label("Objekt verschieben", exact=True), 31, 16)
    frame = _frame(target)
    image_frames = page.locator(f'#sf-deck [data-sf-slide="{first}"] [data-sf-kind="image"]')
    baseline_count = image_frames.count()
    for count in (baseline_count + 1, baseline_count + 2):
        page.get_by_role("button", name="Bild einfügen", exact=True).click()
        page.get_by_label("Bilddatei auswählen", exact=True).set_input_files(images["png"])
        expect(image_frames).to_have_count(count)
    _notes_guidance(page, "Draft notes remain canonical", "Draft guidance remains separate")
    _close_panel(page)
    _draft_flushed(page)
    key, draft = _draft(page)
    entries = _drafts(page)
    assert sum(len(item["key"]) + len(item["value"]) for item in entries) < 1_000_000
    assert key
    stored = json.dumps(entries)
    assert data_url[100:300] not in stored, "immutable original bytes leaked into draft"
    assert "MIGRATION_HEAD_BASELINE" not in stored, "original head leaked into draft"
    introduced_original = base64.b64encode(images["png"].read_bytes()).decode()
    assert stored.count(introduced_original) == 1, "duplicate imports must share one new original"
    assert any(re.fullmatch(r"[0-9a-f]{64}", value, re.I) for value in _strings(draft)), "draft requires SHA256 source identity"
    page.reload()
    expect(_object(page, TEXT)).to_have_text("Migration draft contribution")
    assert _frame(_object(page, "migration-image")) == frame
    assert _meta(page)["notes"][first] == "Draft notes remain canonical"
    assert _meta(page)["guidance"][first]["text"] == "Draft guidance remains separate"
    restored = _object(page, "migration-image").locator("img").get_attribute("src")
    assert base64.b64decode(restored.split(",", 1)[1]) == original_bytes
    expect(image_frames).to_have_count(baseline_count + 2)


# TC-R04 (M5/M7, L5 negative) | INFRA: none
@pytest.mark.parametrize("change", ["head", "source-text"])
def test_same_revision_source_drift(tmp_path, browser_factory, change):
    path, _, data_url, _ = _native(tmp_path)
    page = browser_factory(path)
    _edit(page)
    _edit_text(page, "Migration draft contribution")
    _draft_flushed(page)
    _draft(page)
    before = path.read_text()
    revision = _json_script(before)["revision"]
    if change == "head":
        after = before.replace("MIGRATION_HEAD_BASELINE", "MIGRATION_HEAD_CHANGED")
        expected_text = "Migration source baseline"
    else:
        after = before.replace("Migration <em>source</em> baseline", "Changed <em>source</em> baseline")
        expected_text = "Changed source baseline"
    assert after != before and _json_script(after)["revision"] == revision
    path.write_text(after)
    page.reload()
    expect(_object(page, TEXT)).to_have_text(expected_text)
    assert _object(page, "migration-image").locator("img").get_attribute("src") == data_url


# TC-R05 (M5/M7, L5 negative) | INFRA: none
def test_corrupt_or_missing_draft_ref(tmp_path, browser_factory):
    path, _, data_url, _ = _native(tmp_path)
    page = browser_factory(path)
    _edit(page)
    _edit_text(page, "Migration draft contribution")
    image = _object(page, "migration-image")
    image.click()
    page.get_by_role("button", name="Bild zuschneiden", exact=True).click()
    page.get_by_role("slider", name="Bildausschnitt", exact=True).press("ArrowRight")
    page.get_by_role("button", name="Übernehmen", exact=True).click()
    _draft_flushed(page)
    _draft(page)
    page.wait_for_function("""() => Object.values(localStorage).some(raw => {
      try{return (JSON.parse(raw).changes||[]).some(change=>change.descriptor.kind==='image'&&change.descriptor.id==='migration-image');}
      catch{return false;}
    })""", timeout=5000)
    candidates = []
    for entry in _drafts(page):
        record = json.loads(entry["value"])
        for change in record.get("changes", []):
            if change["descriptor"] == {"kind": "image", "id": "migration-image"}:
                candidates.append((entry["key"], record, change["after"]["asset"]))
    assert len(candidates) == 1, "a committed crop must produce one local image record"
    key, draft, reference = candidates[0]
    assert reference.startswith("original:"), "the unchanged original must remain an asset reference"
    assert data_url[100:300] not in json.dumps(draft), "local crop must not repeat original bytes"
    corrupt_reference = re.sub(r"\d+$", lambda match: str(int(match[0]) + 100000), reference)
    assert corrupt_reference != reference
    corrupt = _replace_string(draft, reference, corrupt_reference)
    page.evaluate("([key,draft]) => localStorage.setItem(key,JSON.stringify(draft))", [key, corrupt])
    page.reload()
    _assert_complete_original(page, data_url)
    assert _object(page, "migration-image").locator("img").evaluate("img => img.complete && img.naturalWidth>0")


# TC-R06 (M3/M5, L4 degradation) | INFRA: none
def test_new_original_quota_fallback(tmp_path, browser_factory, images):
    path, first, _, _ = _native(tmp_path)
    page = browser_factory(path, storage_fault=True)
    _edit(page)
    _edit_text(page, "Full file remains available after quota")
    page.get_by_role("button", name="Bild einfügen", exact=True).click()
    page.get_by_label("Bilddatei auswählen", exact=True).set_input_files(images["png"])
    inserted = page.locator(f'#sf-deck [data-sf-slide="{first}"] [data-sf-kind="image"]')
    expect(inserted).to_have_count(2)
    _notes_guidance(page, "Quota fallback note", "Quota fallback guidance")
    _close_panel(page)
    expect(page.get_by_role("alert")).to_be_visible()
    saved = _download(page, tmp_path / "quota-full-file.html")
    _cli("validate", saved)
    fresh = browser_factory(saved)
    expect(_object(fresh, TEXT)).to_have_text("Full file remains available after quota")
    assert _meta(fresh)["notes"][first] == "Quota fallback note"
    assert _meta(fresh)["guidance"][first]["text"] == "Quota fallback guidance"
    originals = fresh.locator(f'#sf-deck [data-sf-slide="{first}"] [data-sf-kind="image"] img').evaluate_all("nodes => nodes.map(n => n.getAttribute('src'))")
    assert images["png"].read_bytes() in [base64.b64decode(value.split(",", 1)[1]) for value in originals]


# TC-R07 (M6, L4 positive) | INFRA: none
def test_presenter_lifecycle(tmp_path, browser_factory):
    path, first, _, _ = _native(tmp_path)
    page = browser_factory(path)
    popup = _presenter(page)
    ids = _slide_ids(page)
    current_preview = popup.frame_locator('iframe[title="Aktuelle Folie"]')
    next_preview = popup.frame_locator('iframe[title="Nächste Folie"]')
    expect(current_preview.locator(f'[data-sf-slide="{first}"]')).to_be_visible()
    expect(next_preview.locator(f'[data-sf-slide="{ids[1]}"]')).to_be_visible()
    assert page.locator('#sf-deck [data-sf-id="migration-flow"]').count() == 1
    notes = popup.get_by_role("region", name="Referentennotizen", exact=True)
    expect(notes).to_have_text("Original normalized speaker notes")
    page.get_by_role("button", name="Referentennotizen", exact=True).click()
    owner_notes = page.get_by_role("textbox", name="Referentennotizen", exact=True)
    owner_notes.fill("Presenter canonical contribution")
    owner_notes.blur()
    page.wait_for_function("document.querySelector('#sf-document').textContent.includes('Presenter canonical contribution')")
    popup.get_by_role("button", name="Nächste Folie", exact=True).click()
    expect(page.locator(f'#sf-deck > [data-sf-slide="{ids[1]}"]')).to_be_visible()
    popup.close()
    reopened = _presenter(page)
    expect(reopened.frame_locator('iframe[title="Aktuelle Folie"]').locator(f'[data-sf-slide="{ids[1]}"]')).to_be_visible()
    reopened.get_by_role("button", name="Vorherige Folie", exact=True).click()
    expect(reopened.get_by_role("region", name="Referentennotizen", exact=True)).to_have_text("Presenter canonical contribution")
    timer = reopened.get_by_role("timer")
    page.clock.install()
    reopened.get_by_role("button", name="Start", exact=True).click()
    expect(reopened.get_by_role("button", name="Pause", exact=True)).to_be_enabled()
    initial = timer.text_content()
    page.clock.fast_forward(3000)
    expect(timer).not_to_have_text(initial)
    reopened.get_by_role("button", name="Pause", exact=True).click()
    expect(reopened.get_by_role("button", name="Pause", exact=True)).to_be_disabled()
    paused = timer.text_content()
    page.clock.fast_forward(3000)
    expect(timer).to_have_text(paused)
    reopened.get_by_role("button", name="Stopp", exact=True).click()
    expect(timer).to_have_text(initial)
    # A normal presenter tab leaves its owner in the background. Model the
    # user's tab switch before testing the owner's native fullscreen gesture.
    page.bring_to_front()
    page.get_by_role("button", name="Vollbild", exact=True).click()
    page.wait_for_function("document.fullscreenElement!==null")
    page.keyboard.press("Escape")
    page.wait_for_function("document.fullscreenElement===null")
    saved = _download(page, tmp_path / "presenter-authored.html")
    _cli("validate", saved)
    assert _json_script(saved.read_text())["notes"][first] == "Presenter canonical contribution"


# TC-R08 (M6/M7, L5 negative) | INFRA: none
def test_unrelated_presenter_command_rejection(tmp_path, browser_factory):
    path, first, _, _ = _native(tmp_path)
    page = browser_factory(path)
    page.evaluate("""() => {window.migrationMessages=[];
      addEventListener('message',e=>window.migrationMessages.push(e.data));}""")
    popup = _presenter(page)
    popup.evaluate("""() => {window.migrationStorageWrites=[];
      const set=Storage.prototype.setItem;
      Storage.prototype.setItem=function(key,value){
        window.migrationStorageWrites.push({key,value});return set.call(this,key,value);
      };}""")
    popup.get_by_role("button", name="Nächste Folie", exact=True).click()
    expect(popup.get_by_label("Folie", exact=True)).not_to_have_value(first)
    command = next(value for value in page.evaluate("window.migrationMessages") if value.get('command') == 'navigate')
    popup.get_by_role("button", name="Vorherige Folie", exact=True).click()
    expect(popup.get_by_label("Folie", exact=True)).to_have_value(first)
    protected = _meta(page)
    fields = list(_identity_fields(command))
    assert any(re.search("session|token", key, re.I) for key, _ in fields)
    assert any(re.search("deck", key, re.I) for key, _ in fields)
    with page.expect_popup() as outsider_opened:
        page.evaluate("() => window.open('about:blank','migration-outsider')")
    outsider = outsider_opened.value
    outsider.evaluate("message => opener.postMessage(message,'*')", command)
    page.evaluate("message => dispatchEvent(new MessageEvent('message',{data:message,source:window}))", command)
    for key, identity in fields:
        changed = _replace_string(command, identity, identity + "-unrelated")
        popup.evaluate("message => opener.postMessage(message,'*')", changed)
        page.wait_for_function("identity => window.migrationMessages.some(m=>JSON.stringify(m).includes(identity))", arg=identity + "-unrelated")
    assert _meta(page) == protected
    assert page.locator('#sf-deck > [data-sf-slide]:visible').get_attribute("data-sf-slide") == first
    assert popup.evaluate("window.migrationStorageWrites") == [], "presenter must not write its own browser draft"
    outsider.close()


# TC-R09 (M6/M7, L3 negative) | INFRA: none
def test_rich_note_baseline_guard(tmp_path, browser_factory):
    baseline = "Original normalized speaker notes"
    markup = ('<p><strong>Original normalized</strong> speaker notes</p>'
              '<script>window.migrationExecutableNote=true</script>'
              '<img src="broken-note-image" onerror="window.migrationExecutableNote=true">')
    path, first, _, _ = _native(tmp_path, metadata={
        "notesProvenance": {FIRST: {"html": markup, "text": baseline}}
    })
    assert first == FIRST
    page = browser_factory(path)
    popup = _presenter(page)
    expect(popup.locator("strong").filter(has_text="Original normalized")).to_be_visible()
    assert not popup.evaluate("window.migrationExecutableNote===true")
    assert popup.locator('[onerror],[onclick],img[src="broken-note-image"]').count() == 0
    notes = popup.get_by_role("region", name="Referentennotizen", exact=True)
    expect(notes).to_have_text(baseline)
    page.get_by_role("button", name="Referentennotizen", exact=True).click()
    owner_notes = page.get_by_role("textbox", name="Referentennotizen", exact=True)
    owner_notes.fill("Canonical edited speaker notes")
    owner_notes.blur()
    page.wait_for_function("document.querySelector('#sf-document').textContent.includes('Canonical edited speaker notes')")
    expect(popup.locator("strong").filter(has_text="Original normalized")).to_have_count(0)
    assert _meta(page)["notesProvenance"][first] == {"html": markup, "text": baseline}
    popup.close()
    reopened = _presenter(page)
    expect(reopened.get_by_role("region", name="Referentennotizen", exact=True)).to_have_text("Canonical edited speaker notes")
    expect(reopened.locator("strong").filter(has_text="Original normalized")).to_have_count(0)
    saved = _download(page, tmp_path / "rich-note-edited.html")
    _cli("validate", saved)
    fresh = browser_factory(saved)
    assert _meta(fresh)["notes"][first] == "Canonical edited speaker notes"
    assert _meta(fresh)["notesProvenance"][first] == {"html": markup, "text": baseline}


# TC-R10 (M3/M8, L4 positive) | INFRA: none
@pytest.mark.parametrize("template", ["starter.html", "starter-editorial.html"])
def test_complete_file_handoff(tmp_path, browser_factory, template):
    path, first, data_url, original = _native(tmp_path, template)
    page = browser_factory(path)
    _edit(page)
    _edit_text(page, "Human authored text")
    _notes_guidance(page, "Human authored notes", "Focused next agent change")
    _close_panel(page)
    flow = _object(page, "migration-flow")
    flow.click()
    _drag(page, page.get_by_label("Objekt verschieben", exact=True), 24, 13)
    state = _authored(flow)
    saved = _download(page, tmp_path / f"{template}-human.html")
    serialized = saved.read_text()
    _cli("validate", saved)
    assert data_url in serialized
    for tag, attrs in Elements(serialized).entries:
        for field in ("src", "href"):
            value = attrs.get(field, "")
            if tag in ("img", "image", "link") and value:
                assert value.startswith(("data:", "#")), f"offline export left external/draft reference: {value[:100]}"
    fresh = browser_factory(saved)
    assert _authored(_object(fresh, "migration-flow")) == state
    assert _meta(fresh)["notes"][first] == "Human authored notes"
    before = saved.read_text()
    untouched = {key: value for key, value in _slide_spans(before).items() if key != first}
    _cli("set-text", saved, "--element", TEXT, "--text", "Agent focused text")
    after = saved.read_text()
    assert {key: _slide_spans(after)[key] for key in untouched} == untouched
    second = browser_factory(saved)
    expect(_object(second, TEXT)).to_have_text("Agent focused text")
    assert _authored(_object(second, "migration-flow")) == state
    assert _meta(second)["guidance"][first]["text"] == "Focused next agent change"
    actual = _object(second, "migration-image").locator("img").get_attribute("src")
    assert base64.b64decode(actual.split(",", 1)[1]) == original
    assert second.locator('#sf-deck [contenteditable="true"]').count() == 0


# TC-R11 (M4/M6, L3 public hook) | INFRA: none
def test_view_event_lifecycle(tmp_path, browser_factory):
    path, _, _, _ = _native(tmp_path)
    page = browser_factory(path)
    page.evaluate("""() => {window.migrationViews=[];
      document.addEventListener('sf:view',e=>window.migrationViews.push(e.detail));}""")
    page.get_by_role("button", name="Nächste Folie", exact=True).click()
    details = page.evaluate("window.migrationViews")
    assert details, "navigation must issue public sf:view"
    current = page.locator('#sf-deck > [data-sf-slide]:visible').get_attribute("data-sf-slide")
    assert details[-1] == {"deckId": _meta(page)["deckId"], "slideId": current,
                           "index": 1, "count": len(_slide_ids(page))}
    page.get_by_role("button", name="Vorherige Folie", exact=True).click()
    current = page.locator('#sf-deck > [data-sf-slide]:visible').get_attribute("data-sf-slide")
    assert page.evaluate("window.migrationViews")[-1] == {
        "deckId": _meta(page)["deckId"], "slideId": current,
        "index": 0, "count": len(_slide_ids(page))}
