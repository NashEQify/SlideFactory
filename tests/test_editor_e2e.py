# INFRA: none
"""Task 001 / spec v1: real file:// browser and production-helper handoff.

Run: python3 -m pytest tests/test_editor_e2e.py -v
Chromium: SF_CHROMIUM_EXECUTABLE overrides the installed default.
Only public UI, authored DOM/JSON contracts, downloaded files and CLI are used.
All content/assets are synthetic. Fresh-agent evidence for TC-010 is root-owned.
"""

from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser

import pytest
from PIL import Image
from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "skills" / "slidefactory"
HELPER = PACKAGE / "scripts" / "deck.py"
def _chromium():
    """Explicit SF_CHROMIUM_EXECUTABLE, else a full Chromium in the Playwright cache, else Playwright's default."""
    if os.environ.get("SF_CHROMIUM_EXECUTABLE"):
        return os.environ["SF_CHROMIUM_EXECUTABLE"]
    cached = sorted(Path.home().glob(".cache/ms-playwright/chromium-*/chrome-linux64/chrome"))
    return str(cached[-1]) if cached else None


CHROMIUM = _chromium()
TEXT_ID = "qa-text"
BOX_ID = "qa-box"
BASE_TEXT = "Fixture alpha beta"
SCHEMES = {"cyan-dark", "cyan-light", "indigo-dark", "indigo-light"}
# Clean MBB brings its own three looks instead of the shared schemes.
MBB_SCHEMES = {"night-turquoise", "petrol-amber", "paper-marine"}
TOKEN_KEYS = {"background", "text", "muted", "accent", "accent2", "surface", "border"}


class Scripts(HTMLParser):
    """Read only public JSON/executable script source from actual file bytes."""

    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.entries = []
        self.current = None
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.current = [dict(attrs), ""]

    def handle_data(self, data):
        if self.current is not None:
            self.current[1] += data

    def handle_endtag(self, tag):
        if tag == "script" and self.current is not None:
            self.entries.append(self.current)
            self.current = None


class Elements(HTMLParser):
    """Inspect actual serialized elements, excluding CSS/JS source text."""

    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.entries = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.entries.append((tag, dict(attrs)))


def _json_script(source, script_id="sf-document"):
    for attrs, content in Scripts(source).entries:
        if attrs.get("id") == script_id:
            return json.loads(content)
    raise AssertionError(f"missing public JSON script #{script_id}")


def _set_json_script(source, value, script_id="sf-document"):
    pattern = rf'(<script\b[^>]*\bid=["\']{re.escape(script_id)}["\'][^>]*>)(.*?)(</script\s*>)'
    payload = json.dumps(value, ensure_ascii=False).replace("<", "\\u003c")
    changed, count = re.subn(pattern, lambda m: m[1] + payload + m[3], source, flags=re.S)
    assert count == 1
    return changed


def _slide_spans(source):
    return dict(
        (m[1], m[0])
        for m in re.finditer(
            r'<section\b[^>]*\bdata-sf-slide=["\']([^"\']+)["\'][^>]*>.*?</section\s*>',
            source,
            re.S,
        )
    )


def _require(path):
    assert path.is_file(), f"RED: production resource missing: {path.relative_to(ROOT)}"
    return path


def _starter(name):
    """A starter as a new deck receives it: without its design overview slides."""
    source = _require(PACKAGE / "assets" / name).read_text(encoding="utf-8")
    overview = re.findall(r'<section class="sf-slide" data-sf-slide="([^"]+)" data-sf-overview', source)
    source = re.sub(r'<section class="sf-slide" data-sf-slide="[^"]+" data-sf-overview.*?</section>\s*', "", source, flags=re.S)
    meta = _json_script(source)
    for identity in overview:
        meta["notes"].pop(identity)
        meta["guidance"].pop(identity)
    return _set_json_script(source, meta)


def _ready(tmp_path, name="consulting.html", filename=None):
    source = _starter(name)
    slides = _slide_spans(source)
    assert len(slides) >= 2, "ready file needs at least two navigable slides"
    first_id = next(iter(slides))
    meta = _json_script(source)
    meta["qaExtension"] = {"retained": "synthetic-only", "sourceGeneration": 0}
    meta["notes"][first_id] = "Initial fixture notes"
    meta["guidance"][first_id] = {"text": "Initial fixture guidance", "status": "addressed"}
    source = _set_json_script(source, meta)
    authored = (
        '<p data-sf-id="qa-text" data-sf-kind="text" '
        'style="position:absolute;left:120px;top:580px;width:520px;height:60px;'
        'font-size:28px;z-index:3">Fixture alpha beta</p>'
        '<div id="qa-parent" style="position:absolute;left:0;top:0;width:1600px;'
        'height:900px;transform:scale(0.8);transform-origin:0 0">'
        '<div data-sf-id="qa-box" data-sf-kind="box" '
        'style="position:absolute;left:1060px;top:670px;width:160px;height:100px;'
        'transform:rotate(3deg);background:var(--sf-accent);z-index:4">'
        '<svg viewBox="0 0 160 100" aria-label="Synthetic token-aware diagram">'
        '<path d="M10 50H150" stroke="var(--sf-text)"/></svg></div></div>'
    )
    original = slides[first_id]
    assert TEXT_ID not in original and BOX_ID not in original
    source = source.replace(original, original.rsplit("</section", 1)[0] + authored + "</section" + original.rsplit("</section", 1)[1], 1)
    source = source.replace("</head>", "<style>/* QA_SOURCE_STYLE_0 */</style></head>", 1)
    path = tmp_path / (filename or name)
    path.write_text(source, encoding="utf-8")
    return path


def _cli(*args, helper=HELPER, cwd=None, success=True):
    assert helper.is_file(), f"RED: missing production helper {helper}"
    result = subprocess.run(
        [sys.executable, "-I", str(helper), *map(str, args)],
        cwd=cwd or ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if success:
        assert result.returncode == 0, result.stderr or result.stdout
    else:
        assert result.returncode != 0
        assert (result.stderr or result.stdout).strip(), "rejected CLI input needs a useful error"
    return result


@pytest.fixture
def browser_factory():
    """Lazy local browser: missing assets fail RED before browser launch."""
    with sync_playwright() as playwright:
        browser = None
        opened = []

        def open_file(path, *, viewport=None, storage_fault=False):
            nonlocal browser
            if browser is None:
                engine = os.environ.get("SF_BROWSER", "chromium")
                assert engine in {"chromium", "firefox", "webkit"}, engine
                if engine == "chromium":
                    assert CHROMIUM is None or Path(CHROMIUM).is_file(), f"Chromium not found: {CHROMIUM}"
                    browser = playwright.chromium.launch(executable_path=CHROMIUM, headless=True, args=["--no-sandbox"])
                else:
                    browser = getattr(playwright, engine).launch(headless=True)
            context = browser.new_context(accept_downloads=True, viewport=viewport or {"width": 1280, "height": 900})
            requests = []
            errors = []
            context.route(re.compile(r"^https?://"), lambda route: (requests.append(route.request.url), route.abort()))
            context.add_init_script("window.qaExecuted = false; window.qaLayoutEvents = []; document.addEventListener('sf:layout', e => window.qaLayoutEvents.push(e.detail));")
            if storage_fault:
                context.add_init_script("Storage.prototype.setItem = function () { throw new DOMException('synthetic quota denial', 'QuotaExceededError'); };")
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(path.resolve().as_uri(), wait_until="load")
            opened.append((context, requests, errors))
            return page

        yield open_file
        for context, requests, errors in opened:
            context.close()
            assert requests == [], f"offline file attempted network access: {requests}"
            assert errors == [], f"uncaught browser errors: {errors}"
        if browser is not None:
            browser.close()


def _presenter_action(page):
    """Open the presenter through its view-mode control, then restore test mode."""
    editing = page.get_by_role("button", name="Fertig", exact=True).is_visible()
    if editing:
        page.get_by_role("button", name="Fertig", exact=True).click()
    page.get_by_role("button", name="Referentenansicht", exact=True).click()
    if editing:
        page.get_by_role("button", name="Bearbeiten", exact=True).click()


def _edit(page):
    page.get_by_role("button", name="Bearbeiten", exact=True).click()
    expect(page.get_by_role("button", name="Fertig", exact=True)).to_be_visible()


def _text(page, value):
    target = page.locator(f'[data-sf-id="{TEXT_ID}"]')
    target.dblclick()
    target.fill(value)
    target.press("Escape")
    expect(target).to_have_text(value)


def _draft_flushed(page):
    expect(page.get_by_role("status")).to_contain_text(re.compile("Entwurf|draft", re.I))


def _meta(page):
    return page.locator("#sf-document").evaluate("node => JSON.parse(node.textContent)")


def _slide_ids(page):
    return page.locator("#sf-deck > [data-sf-slide]").evaluate_all("nodes => nodes.map(n => n.dataset.sfSlide)")


def _object_ids(page):
    return page.locator("#sf-deck [data-sf-id]").evaluate_all("nodes => nodes.map(n => n.dataset.sfId)")


def _box(page, object_id=BOX_ID):
    return page.locator(f'[data-sf-id="{object_id}"]')


def _frame(locator):
    return locator.evaluate("n => ({left:n.style.left,top:n.style.top,width:n.style.width,height:n.style.height,transform:n.style.transform,parent:n.parentElement.id})")


def _drag(page, locator, dx, dy):
    rect = locator.bounding_box()
    assert rect and rect["width"] > 0 and rect["height"] > 0
    x, y = rect["x"] + rect["width"] / 2, rect["y"] + rect["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + dx, y + dy, steps=5)
    page.mouse.up()


def _click_closing(locator):
    """Click a control that closes its own window, detached so the click cannot race the close."""
    locator.evaluate("button => setTimeout(() => button.click(), 0)")


def _download(page, destination, choice="Arbeitsstand mit Notizen"):
    page.get_by_role("button", name="HTML speichern", exact=True).click()
    with page.expect_download() as received:
        page.get_by_role("button", name=choice, exact=True).click()
    download = received.value
    assert download.failure() is None
    download.save_as(destination)
    assert destination.stat().st_size > 0
    return destination


def _notes_guidance(page, note, guidance):
    page.get_by_role("button", name="Referentennotizen", exact=True).click()
    page.get_by_role("textbox", name="Referentennotizen", exact=True).fill(note)
    page.get_by_role("button", name="Kommentare", exact=True).click()
    page.get_by_role("textbox", name="Bearbeitungskommentar", exact=True).fill(guidance)
    page.get_by_role("textbox", name="Bearbeitungskommentar", exact=True).blur()


@pytest.fixture
def images(tmp_path):
    result = {}
    for name, fmt, size in [("png", "PNG", (320, 160)), ("jpeg", "JPEG", (160, 320)), ("webp", "WEBP", (320, 160))]:
        image = Image.new("RGB", size, "#2488bb")
        for x in range(size[0] // 2):
            for y in range(size[1]):
                image.putpixel((x, y), (225, 85, 60))
        buffer = io.BytesIO()
        image.save(buffer, format=fmt)
        path = tmp_path / f"synthetic.{name}"
        path.write_bytes(buffer.getvalue())
        result[name] = path
    result["invalid"] = tmp_path / "invalid.png"
    result["invalid"].write_bytes(b"not a decodable image")
    return result


def _import_file(page, path, *, replace=False):
    label = "Bild ersetzen" if replace else "Bild einfügen"
    page.get_by_role("button", name=label, exact=True).click()
    page.get_by_label("Bilddatei auswählen", exact=True).set_input_files(path)


def _file_event(page, event_type, path):
    mime = {".png": "image/png", ".jpeg": "image/jpeg", ".webp": "image/webp"}[path.suffix]
    target = page.locator('#sf-deck > [data-sf-slide]:visible').first
    target.evaluate(
        """(node, args) => {
          const bytes = Uint8Array.from(atob(args.base64), c => c.charCodeAt(0));
          const transfer = new DataTransfer();
          transfer.items.add(new File([bytes], args.name, {type: args.mime}));
          const box = node.getBoundingClientRect();
          const init = {bubbles:true,cancelable:true,clientX:box.x+box.width/3,clientY:box.y+box.height/3};
          const event = args.type === 'paste' ? new ClipboardEvent('paste',{...init,clipboardData:transfer}) : new DragEvent('drop',{...init,dataTransfer:transfer});
          node.dispatchEvent(event);
        }""",
        {"base64": base64.b64encode(path.read_bytes()).decode(), "name": path.name, "mime": mime, "type": event_type},
    )


def _images(page):
    return page.locator('#sf-deck [data-sf-kind="image"]')


def _image_ids(page):
    return set(_images(page).evaluate_all("nodes => nodes.map(n => n.dataset.sfId)"))


def _inserted_image(page, previous_ids):
    """Locate the real producer's new ID, independent of slide/DOM ordering."""
    expect(_images(page)).to_have_count(len(previous_ids) + 1)
    inserted = _image_ids(page) - previous_ids
    assert len(inserted) == 1
    return page.locator(f'#sf-deck [data-sf-kind="image"][data-sf-id="{inserted.pop()}"]')


def _assert_original_bytes(state, path):
    assert state["src"].startswith("data:image/") and ";base64," in state["src"]
    assert base64.b64decode(state["src"].split(",", 1)[1]) == path.read_bytes()


def _image_state(locator):
    return locator.evaluate("n => ({id:n.dataset.sfId,crop:JSON.parse(n.dataset.sfCrop),src:n.querySelector('img').getAttribute('src'),naturalWidth:n.querySelector('img').naturalWidth,naturalHeight:n.querySelector('img').naturalHeight,frame:{left:n.style.left,top:n.style.top,width:n.style.width,height:n.style.height}})")


def _assert_crop(state):
    crop = state["crop"]
    assert 0 <= crop["x"] < 1 and 0 <= crop["y"] < 1
    assert crop["w"] > 0 and crop["h"] > 0
    assert crop["x"] + crop["w"] <= 1 + 1e-8
    assert crop["y"] + crop["h"] <= 1 + 1e-8
    assert state["src"].startswith("data:image/")
    assert state["naturalWidth"] > 0 and state["naturalHeight"] > 0
    width = float(state["frame"]["width"].removesuffix("px"))
    height = float(state["frame"]["height"].removesuffix("px"))
    assert width > 0 and height > 0
    crop_ratio = state["naturalWidth"] * crop["w"] / (state["naturalHeight"] * crop["h"])
    assert crop_ratio == pytest.approx(width / height, rel=1e-5)


# TC-001 (A1, L4 positive) | INFRA: none
@pytest.mark.e2e
def test_offline_dependency(tmp_path, browser_factory):
    for name in ("consulting.html", "editorial.html", "mbb.html"):
        path = _ready(tmp_path, name)
        page = browser_factory(path)
        ids = _slide_ids(page)
        _edit(page)
        _text(page, "Offline direct work")
        page.get_by_role("button", name="Fertig", exact=True).click()
        expect(page.locator(f'[data-sf-id="{TEXT_ID}"]')).to_have_text("Offline direct work")
        page.locator("body").press("PageDown")
        expect(page.locator(f'[data-sf-slide="{ids[1]}"]')).to_be_visible()
        page.locator("body").press("PageUp")
        expect(page.locator(f'[data-sf-slide="{ids[0]}"]')).to_be_visible()


# TC-002 (A2, L4 regression/degradation) | INFRA: none
@pytest.mark.e2e
def test_competing_state_authority(tmp_path, browser_factory):
    path = _ready(tmp_path)
    page = browser_factory(path)
    slide = _slide_ids(page)[0]
    _edit(page)
    _text(page, "Browser draft text")
    _notes_guidance(page, "Browser draft notes", "Browser draft guidance")
    _drag(page, _box(page), 35, 15)
    draft_frame = _frame(_box(page))
    _draft_flushed(page)
    page.reload()
    expect(page.locator(f'[data-sf-id="{TEXT_ID}"]')).to_have_text("Browser draft text")
    assert _meta(page)["notes"][slide] == "Browser draft notes"
    assert _meta(page)["guidance"][slide] == {"text": "Browser draft guidance", "status": "open"}
    assert _frame(_box(page)) == draft_frame
    _cli("set-text", path, "--element", TEXT_ID, "--text", "Agent file text")
    saved_meta = _json_script(path.read_text())
    page.reload()
    expect(page.locator(f'[data-sf-id="{TEXT_ID}"]')).to_have_text("Agent file text")
    assert _meta(page)["notes"][slide] == "Initial fixture notes"
    assert _meta(page)["guidance"][slide] == {"text": "Initial fixture guidance", "status": "addressed"}
    for kind in ("style", "metadata"):
        _edit(page)
        _text(page, f"Stale {kind} draft")
        _draft_flushed(page)
        source = path.read_text()
        if kind == "style":
            assert "QA_SOURCE_STYLE_0" in source
            source = source.replace("QA_SOURCE_STYLE_0", "QA_SOURCE_STYLE_1")
        else:
            meta = _json_script(source)
            meta["qaExtension"]["sourceGeneration"] = 1
            source = _set_json_script(source, meta)
        assert _json_script(source)["revision"] == saved_meta["revision"]
        path.write_text(source)
        page.reload()
        expect(page.locator(f'[data-sf-id="{TEXT_ID}"]')).to_have_text("Agent file text")
    quota_page = browser_factory(path, storage_fault=True)
    _edit(quota_page)
    _text(quota_page, "Save still available")
    expect(quota_page.get_by_role("alert")).to_be_visible()
    saved = _download(quota_page, tmp_path / "quota-save.html")
    _cli("validate", saved)
    reopened = browser_factory(saved)
    expect(reopened.locator(f'[data-sf-id="{TEXT_ID}"]')).to_have_text("Save still available")


# TC-003 (A3, L4 positive) | INFRA: none
@pytest.mark.e2e
def test_incomplete_serialization(tmp_path, browser_factory, images):
    path = _ready(tmp_path)
    original_meta = _json_script(path.read_text())
    page = browser_factory(path)
    ids = _object_ids(page)
    slides = _slide_ids(page)
    _edit(page)
    _text(page, "Exported authored text")
    _drag(page, _box(page), 40, 20)
    expected_frame = _frame(_box(page))
    _notes_guidance(page, "Exported notes", "Exported agent guidance")
    page.get_by_role("combobox", name="Farbschema", exact=True).select_option("indigo-light")
    previous_images = _image_ids(page)
    _import_file(page, images["png"])
    image = _inserted_image(page, previous_images)
    original_image = _image_state(image)["src"]
    _assert_original_bytes(_image_state(image), images["png"])
    image.click()
    page.get_by_role("button", name="Bild zuschneiden", exact=True).click()
    page.get_by_role("slider", name="Bildausschnitt", exact=True).press("ArrowRight")
    # Saving while crop is active must commit the valid crop/frame atomically.
    saved = _download(page, tmp_path / "actual-download.html")
    expected_image = _image_state(image)
    _assert_crop(expected_image)
    _cli("validate", saved)
    source = saved.read_text()
    meta = _json_script(source)
    assert meta["revision"] != original_meta["revision"]
    assert meta["qaExtension"] == original_meta["qaExtension"]
    assert meta["notes"][slides[0]] == "Exported notes"
    assert meta["guidance"][slides[0]] == {"text": "Exported agent guidance", "status": "open"}
    assert meta["colorScheme"] == "indigo-light"
    exported_elements = Elements(source).entries
    assert not any(attrs.get("contenteditable") == "true" for _, attrs in exported_elements)
    assert not any(attrs.get("role") in {"toolbar", "dialog"} for _, attrs in exported_elements)
    fresh = browser_factory(saved)
    expect(fresh.locator(f'[data-sf-id="{TEXT_ID}"]')).to_have_text("Exported authored text")
    assert _frame(_box(fresh)) == expected_frame
    assert _slide_ids(fresh) == slides
    assert [object_id for object_id in _object_ids(fresh) if object_id in ids] == ids
    state = _image_state(fresh.locator(f'#sf-deck [data-sf-id="{expected_image["id"]}"]'))
    assert state["src"] == original_image
    assert state["crop"] == expected_image["crop"]
    assert state["frame"] == expected_image["frame"]
    _assert_original_bytes(state, images["png"])
    _assert_crop(state)
    _edit(fresh)
    _text(fresh, "Reusable editor after fresh open")


# TC-004 (A4, L4 boundary) | INFRA: none
@pytest.mark.e2e
def test_coordinate_focus_ownership(tmp_path, browser_factory):
    page = browser_factory(_ready(tmp_path), viewport={"width": 1050, "height": 780})
    _edit(page)
    frame = _box(page)
    original = _frame(frame)
    rect = frame.bounding_box()
    _drag(page, frame, 40, 24)
    moved = frame.bounding_box()
    assert moved["x"] - rect["x"] == pytest.approx(40, abs=3)
    assert moved["y"] - rect["y"] == pytest.approx(24, abs=3)
    assert _frame(frame)["transform"] == original["transform"]
    assert _frame(frame)["parent"] == original["parent"]
    frame.click()
    x0 = frame.bounding_box()["x"]
    page.keyboard.press("ArrowRight")
    x1 = frame.bounding_box()["x"]
    page.keyboard.press("Shift+ArrowRight")
    x2 = frame.bounding_box()["x"]
    assert x1 > x0 and x2 - x1 > x1 - x0
    width0 = frame.bounding_box()["width"]
    _drag(page, page.get_by_role("button", name="Größe ändern unten rechts", exact=True), 20, 15)
    assert frame.bounding_box()["width"] > width0
    target = page.locator(f'[data-sf-id="{TEXT_ID}"]')
    target.dblclick()
    target.press("Home")
    before = target.evaluate("n => ({offset:getSelection().focusOffset,left:n.style.left,top:n.style.top})")
    target.press("ArrowRight")
    after = target.evaluate("n => ({offset:getSelection().focusOffset,left:n.style.left,top:n.style.top})")
    assert after["offset"] != before["offset"]
    assert (after["left"], after["top"]) == (before["left"], before["top"])
    assert page.get_by_role("spinbutton", name=re.compile(r"^(X|Y|Breite|Höhe|Width|Height)$", re.I)).count() == 0
    assert page.locator('input[type="number"]').count() == 0
    events = page.evaluate("window.qaLayoutEvents")
    assert any(e.get("elementId") == BOX_ID and e.get("phase") == "commit" for e in events)


# TC-005 (A5, L4 positive/negative) | INFRA: none
@pytest.mark.e2e
def test_image_transform_corruption(tmp_path, browser_factory, images):
    page = browser_factory(_ready(tmp_path))
    _edit(page)
    initial_images = _image_ids(page)
    _import_file(page, images["png"])
    image = _inserted_image(page, initial_images)
    before_resize = _image_state(image)
    _assert_original_bytes(before_resize, images["png"])
    image.click()
    _drag(page, page.get_by_role("button", name="Größe ändern unten rechts", exact=True), 25, 15)
    resized = _image_state(image)
    _assert_crop(resized)
    assert resized["frame"] != before_resize["frame"]
    assert float(resized["frame"]["width"].removesuffix("px")) / float(resized["frame"]["height"].removesuffix("px")) == pytest.approx(float(before_resize["frame"]["width"].removesuffix("px")) / float(before_resize["frame"]["height"].removesuffix("px")), rel=1e-5)
    page.get_by_role("button", name="Bild zuschneiden", exact=True).click()
    slider = page.get_by_role("slider", name="Bildausschnitt", exact=True)
    slider.press("ArrowRight")
    slider.press("ArrowRight")
    zoomed = _image_state(image)
    _drag(page, image, 8, 5)
    panned = _image_state(image)
    assert (panned["crop"]["x"], panned["crop"]["y"]) != (zoomed["crop"]["x"], zoomed["crop"]["y"])
    _drag(page, page.get_by_role("button", name="Ausschnitt unten rechts", exact=True), -12, -8)
    handled = _image_state(image)
    _assert_crop(handled)
    assert handled["crop"] != panned["crop"] and handled["frame"] != panned["frame"]
    page.get_by_role("button", name="Abbrechen", exact=True).click()
    cancelled = _image_state(image)
    assert cancelled["crop"] == resized["crop"] and cancelled["frame"] == resized["frame"]
    page.get_by_role("button", name="Bild zuschneiden", exact=True).click()
    page.get_by_role("slider", name="Bildausschnitt", exact=True).press("ArrowRight")
    page.get_by_role("button", name="Übernehmen", exact=True).click()
    applied = _image_state(image)
    _assert_crop(applied)
    assert applied["crop"] != resized["crop"] and applied["src"] == resized["src"]
    page.get_by_role("button", name="Rückgängig", exact=True).click()
    image = page.locator(f'[data-sf-id="{resized["id"]}"]')
    undone = _image_state(image)
    assert undone["crop"] == resized["crop"] and undone["frame"] == resized["frame"]
    image.click()
    page.get_by_role("button", name="Bild zuschneiden", exact=True).click()
    page.get_by_role("slider", name="Bildausschnitt", exact=True).press("ArrowRight")
    page.get_by_role("button", name="Übernehmen", exact=True).click()
    assert _image_state(image)["src"] == resized["src"]
    replacement_frame = _image_state(image)["frame"]
    _import_file(page, images["jpeg"], replace=True)
    expect(image.locator("img")).not_to_have_attribute("src", resized["src"])
    replaced = _image_state(image)
    _assert_crop(replaced)
    _assert_original_bytes(replaced, images["jpeg"])
    assert replaced["id"] == resized["id"] and replaced["frame"] == replacement_frame
    crop = replaced["crop"]
    assert crop["x"] == pytest.approx((1 - crop["w"]) / 2)
    assert crop["y"] == pytest.approx((1 - crop["h"]) / 2)
    _import_file(page, images["invalid"], replace=True)
    expect(page.get_by_role("alert")).to_be_visible()
    assert _image_state(image) == replaced
    # Import routes follow the transform workflow so overlapping new frames
    # cannot intercept the pointer when selecting the first imported image.
    previous_images = _image_ids(page)
    _file_event(page, "drop", images["jpeg"])
    dropped = _image_state(_inserted_image(page, previous_images))
    _assert_crop(dropped)
    _assert_original_bytes(dropped, images["jpeg"])
    previous_images = _image_ids(page)
    _file_event(page, "paste", images["webp"])
    pasted = _image_state(_inserted_image(page, previous_images))
    _assert_crop(pasted)
    _assert_original_bytes(pasted, images["webp"])


# TC-006 (A6, L3 positive) | INFRA: none
@pytest.mark.integration
def test_identity_drift(tmp_path, browser_factory):
    page = browser_factory(_ready(tmp_path))
    _edit(page)
    _notes_guidance(page, "Stable notes", "Stable guidance")
    exported = _download(page, tmp_path / "identity-export.html")
    before = exported.read_text()
    meta = _json_script(before)
    ids = list(_slide_spans(before))
    extracted = tmp_path / "extracted.html"
    _cli("extract-slide", exported, "--slide", ids[0], "--output", extracted)
    fragment = extracted.read_text()
    supplied_slide = "qa-inserted-slide"
    fragment = re.sub(r'(data-sf-slide=["\'])[^"\']+', lambda m: m[1] + supplied_slide, fragment)
    fragment = re.sub(r'(data-sf-id=["\'])([^"\']+)', lambda m: m[1] + "inserted-" + m[2], fragment)
    extracted.write_text(fragment)
    _cli("insert-slide", exported, "--fragment", extracted, "--after", ids[0])
    order = [ids[-1], supplied_slide, *ids[:-1]]
    _cli("reorder", exported, "--order", ",".join(order))
    source = exported.read_text()
    assert list(_slide_spans(source)) == order
    after = _json_script(source)
    for slide_id in ids:
        assert after["notes"].get(slide_id) == meta["notes"].get(slide_id)
        assert after["guidance"].get(slide_id) == meta["guidance"].get(slide_id)
    assert after["notes"][supplied_slide] == ""
    assert after["guidance"][supplied_slide]["status"] == "open"
    fresh = browser_factory(exported)
    all_ids = _object_ids(fresh)
    assert len(all_ids) == len(set(all_ids))
    assert f"inserted-{TEXT_ID}" in all_ids
    expect(fresh.locator(f'[data-sf-slide="{order[0]}"]')).to_be_visible()
    fresh.locator("body").press("PageDown")
    expect(fresh.locator(f'[data-sf-slide="{order[1]}"]')).to_be_visible()
    assert fresh.get_by_role("button", name=re.compile(r"Folie\s+2\b")).count() >= 1


# TC-007 (A7, L3 positive/negative) | INFRA: none
@pytest.mark.integration
def test_source_collateral_change(tmp_path, browser_factory):
    path = _ready(tmp_path)
    page = browser_factory(path)
    _edit(page)
    _text(page, "Human contribution before agent")
    authored = _download(page, tmp_path / "collateral-export.html")
    before = authored.read_text()
    spans = _slide_spans(before)
    first = next(iter(spans))
    untouched = {key: value for key, value in spans.items() if key != first}
    executable = [body for attrs, body in Scripts(before).entries if attrs.get("type") != "application/json"]
    styles = re.findall(r"<style\b[^>]*>.*?</style>", before, re.S)
    _cli("set-text", authored, "--element", TEXT_ID, "--text", "Focused agent contribution")
    _cli("guidance", authored, "--slide", first, "--status", "addressed")
    replacement = tmp_path / "replacement.html"
    replacement.write_text(_slide_spans(authored.read_text())[first].replace("Focused agent contribution", "Replacement contribution"))
    _cli("replace-slide", authored, "--slide", first, "--fragment", replacement)
    after = authored.read_text()
    assert {key: _slide_spans(after)[key] for key in untouched} == untouched
    assert [body for attrs, body in Scripts(after).entries if attrs.get("type") != "application/json"] == executable
    assert re.findall(r"<style\b[^>]*>.*?</style>", after, re.S) == styles
    assert _json_script(after)["qaExtension"] == _json_script(before)["qaExtension"]
    protected = authored.read_bytes()
    existing_output = tmp_path / "existing-output.html"
    existing_output.write_bytes(protected)
    for args in [
        ("set-text", authored, "--element", "missing-id", "--text", "fail", "--output", existing_output),
        ("reorder", authored, "--order", first),
        ("reorder", authored, "--order", ",".join([first] * len(spans))),
    ]:
        _cli(*args, success=False)
        assert authored.read_bytes() == protected
        assert existing_output.read_bytes() == protected
    duplicate = tmp_path / "duplicate-fragment.html"
    duplicate.write_text(_slide_spans(after)[list(spans)[1]])
    _cli("replace-slide", authored, "--slide", first, "--fragment", duplicate, success=False)
    assert authored.read_bytes() == protected
    legacy = tmp_path / "legacy.html"
    legacy.write_text("<!doctype html><html><body><main>Unknown legacy family</main></body></html>")
    _cli("new", "--template", legacy, "--output", existing_output, "--title", "Rejected", success=False)
    assert existing_output.read_bytes() == protected
    assert not list(tmp_path.glob("*.tmp"))


# TC-008 (A8, L4 positive/negative) | INFRA: none
@pytest.mark.e2e
def test_layout_palette_coupling(tmp_path, browser_factory):
    sources = [_require(PACKAGE / "assets" / name).read_text() for name in ("consulting.html", "editorial.html", "mbb.html")]
    runtime = [[body for attrs, body in Scripts(source).entries if attrs.get("type") != "application/json"] for source in sources]
    assert runtime[0] == runtime[1] == runtime[2] and runtime[0]
    assert list(_slide_spans(sources[0]).values()) != list(_slide_spans(sources[1]).values())
    assert list(_slide_spans(sources[0]).values()) != list(_slide_spans(sources[2]).values())
    for index, name in enumerate(("consulting.html", "editorial.html", "mbb.html")):
        page = browser_factory(_ready(tmp_path, name))
        _edit(page)
        schemes = _json_script(sources[index], "sf-color-schemes")
        assert set(schemes) == (MBB_SCHEMES if name == "mbb.html" else SCHEMES)
        ids = _object_ids(page)
        frame = _frame(_box(page))
        selector = page.get_by_role("combobox", name="Farbschema", exact=True)
        expect(selector).to_be_visible()
        assert page.get_by_role("combobox", name=re.compile("Template|Vorlage|Design", re.I)).count() == 0
        assert page.get_by_role("button", name=re.compile("Template|Vorlage", re.I)).count() == 0
        for scheme_id, scheme in schemes.items():
            assert TOKEN_KEYS <= set(scheme["tokens"])
            assert all(re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})", color) for color in scheme["tokens"].values())
            selector.select_option(scheme_id)
            assert _meta(page)["colorScheme"] == scheme_id
            assert _object_ids(page) == ids and _frame(_box(page)) == frame
            assert page.locator(f'[data-sf-id="{TEXT_ID}"]').text_content() == BASE_TEXT
            tokens = page.locator("html").evaluate("n => Object.fromEntries(['background','text','muted','accent','accent2','surface','border'].map(k=>[k,getComputedStyle(n).getPropertyValue('--sf-'+k).trim()]))")
            assert {k: v.lower() for k, v in tokens.items()} == {k: scheme["tokens"][k].lower() for k in TOKEN_KEYS}
            diagram_colors = page.locator('#qa-parent svg path').evaluate("""(node, color) => {
              const probe = document.createElement('span'); probe.style.color = color;
              document.body.append(probe); const expectedColor = getComputedStyle(probe).color;
              probe.remove(); return {actual: getComputedStyle(node).stroke, expected: expectedColor};
            }""", scheme["tokens"]["text"])
            assert diagram_colors["actual"] == diagram_colors["expected"]
        saved = _download(page, tmp_path / f"scheme-{index}.html")
        fresh = browser_factory(saved)
        assert _meta(fresh)["colorScheme"] == scheme_id
        assert _object_ids(fresh) == ids


# TC-009 (A9, L4 adversarial) | INFRA: none
@pytest.mark.e2e
def test_unsafe_external_content(tmp_path, browser_factory):
    path = _ready(tmp_path)
    payload = 'Literal < & "quotes" </script><script>window.qaExecuted=true</script> Unicode Ω'
    first_id = next(iter(_slide_spans(path.read_text())))
    _cli("set-text", path, "--element", TEXT_ID, "--text", payload)
    _cli("guidance", path, "--slide", first_id, "--text", payload)
    page = browser_factory(path)
    expect(page.locator(f'[data-sf-id="{TEXT_ID}"]')).to_have_text(payload)
    assert page.evaluate("window.qaExecuted") is False
    _edit(page)
    target = page.locator(f'[data-sf-id="{TEXT_ID}"]')
    target.dblclick()
    target.press("Control+A")
    target.evaluate("""(node, text) => {
      const data = new DataTransfer();
      data.setData('text/plain', text);
      data.setData('text/html', '<img src="bad:" onerror="window.qaExecuted=true"><script>window.qaExecuted=true</script>');
      node.dispatchEvent(new ClipboardEvent('paste',{bubbles:true,cancelable:true,clipboardData:data}));
    }""", payload)
    target.press("Escape")
    expect(target).to_have_text(payload)
    saved = _download(page, tmp_path / "safe-export.html")
    _cli("validate", saved)
    source = saved.read_text()
    document_raw = next(body for attrs, body in Scripts(source).entries if attrs.get("id") == "sf-document")
    assert "<" not in document_raw
    assert _json_script(source)["guidance"][first_id]["text"] == payload
    fresh = browser_factory(saved)
    assert fresh.evaluate("window.qaExecuted") is False
    expect(fresh.locator(f'[data-sf-id="{TEXT_ID}"]')).to_have_text(payload)
    for kind in ("malformed", "duplicate", "schema"):
        invalid_source = source
        if kind == "malformed":
            invalid_source = re.sub(r'(<script\b[^>]*id=["\']sf-document["\'][^>]*>).*?(</script>)', r'\1{broken\2', source, flags=re.S)
        elif kind == "duplicate":
            invalid_source = source.replace(f'data-sf-id="{BOX_ID}"', f'data-sf-id="{TEXT_ID}"', 1)
        else:
            invalid_meta = _json_script(source)
            invalid_meta["schemaVersion"] = 99
            invalid_source = _set_json_script(source, invalid_meta)
        invalid = tmp_path / f"invalid-{kind}.html"
        invalid.write_text(invalid_source)
        before = invalid.read_bytes()
        _cli("validate", invalid, success=False)
        bad_page = browser_factory(invalid)
        expect(bad_page.get_by_role("alert")).to_be_visible()
        expect(bad_page.get_by_role("button", name="HTML speichern", exact=True)).to_be_disabled()
        assert invalid.read_bytes() == before


# TC-010 (A10, L4 functional forward test) | INFRA: none
@pytest.mark.e2e
def test_inactive_packaging(tmp_path, browser_factory):
    _require(PACKAGE / "SKILL.md")
    _require(HELPER)
    isolated = tmp_path / "unrelated-working-directory"
    isolated.mkdir()
    package = isolated / "slidefactory"
    shutil.copytree(PACKAGE, package)
    helper = package / "scripts" / "deck.py"
    template = package / "assets" / "editorial.html"
    output = isolated / "commissioned.html"
    _cli("new", "--template", template, "--output", output, "--title", "Fresh packaged project", helper=helper, cwd=isolated)
    template_meta = _json_script(template.read_text())
    new_meta = _json_script(output.read_text())
    assert new_meta["deckId"] != template_meta["deckId"] and new_meta["revision"] != template_meta["revision"]
    assert new_meta["templateId"] == template_meta["templateId"]
    overview = _cli("inspect", output, helper=helper, cwd=isolated)
    assert isinstance(json.loads(overview.stdout), dict)
    assert "data:image/" not in overview.stdout and "<script" not in overview.stdout
    page = browser_factory(output)
    text_id = page.locator('#sf-deck [data-sf-kind="text"]').first.get_attribute("data-sf-id")
    _cli("set-text", output, "--element", text_id, "--text", "Packaged actor contribution", helper=helper, cwd=isolated)
    _cli("validate", output, helper=helper, cwd=isolated)
    page.reload()
    expect(page.locator(f'[data-sf-id="{text_id}"]')).to_have_text("Packaged actor contribution")
