"""Whole-selection font sizing preserves mixed text, geometry and offline data."""

import pytest
from playwright.sync_api import expect
from test_editor_e2e import (
    PACKAGE,
    _edit,
    _download,
    _meta,
    _object_ids,
    _json_script,
    _set_json_script,
    browser_factory as browser_factory,
)


def test_group_font_size_is_available(tmp_path, browser_factory):
    path = tmp_path / "editorial.html"
    path.write_text((PACKAGE / "assets/editorial.html").read_text())
    page = browser_factory(path)
    _edit(page)
    for key in ["intro-title", "intro-subtitle"]:
        page.locator(f'[data-sf-id="{key}"]').click(modifiers=["Control"])
    expect(page.get_by_role("button", name="2 Objekte verschieben")).to_be_visible()
    expect(
        page.get_by_role("combobox", name="Schriftgröße", exact=True)
    ).to_be_enabled()


def _mixed_deck(tmp_path):
    source = (PACKAGE / "assets/consulting-blank.html").read_text()
    content = """
    <p data-sf-id="words" data-sf-kind="text" style="position:absolute;left:100px;top:130px;width:350px;height:90px;font-size:18pt">Alpha <em style="font-size:24pt">Beta</em></p>
    <div data-sf-id="container" data-sf-kind="box" style="position:absolute;left:600px;top:130px;width:400px;height:160px;background:#223344">
      <p data-sf-id="nested" data-sf-kind="text" style="position:absolute;left:20px;top:20px;width:300px;height:80px;font-size:12pt">Gamma <strong style="font-size:30pt">Delta</strong></p>
    </div>
    <div data-sf-id="raw" data-sf-kind="box" style="position:absolute;left:100px;top:400px;width:300px;height:90px;font-size:22pt;background:#334455">Epsilon</div>
    <div data-sf-id="shape" data-sf-kind="box" data-sf-shape="rectangle" style="position:absolute;left:600px;top:400px;width:180px;height:90px;background:red"><svg viewBox="0 0 180 90"><title>Ignore SVG title</title><rect width="180" height="90"/></svg></div>
    <div data-sf-id="empty" data-sf-kind="box" style="position:absolute;left:1100px;top:400px;width:180px;height:90px;background:blue"></div>
    """
    meta = _json_script(source)
    first = next(iter(meta["notes"]))
    meta["notes"][first] = "Keep speaker notes"
    meta["guidance"][first] = {"text": "Keep guidance", "status": "open"}
    path = tmp_path / "mixed.html"
    path.write_text(
        _set_json_script(source.replace("</section>", content + "</section>", 1), meta)
    )
    return path


def _sizes(page):
    return page.evaluate(
        """()=>['[data-sf-id="words"]','[data-sf-id="words"] em','[data-sf-id="nested"]','[data-sf-id="nested"] strong','[data-sf-id="raw"]'].map(selector=>parseFloat(getComputedStyle(document.querySelector(selector)).fontSize)*.75)"""
    )


def test_mixed_group_font_history_runs_and_saved_handoff(tmp_path, browser_factory):
    page = browser_factory(_mixed_deck(tmp_path))
    _edit(page)
    ids, meta = _object_ids(page), _meta(page)
    original = _sizes(page)
    roots = ["words", "container", "raw", "shape"]
    positions = page.locator("[data-sf-id]").evaluate_all(
        "nodes=>nodes.map(n=>[n.dataset.sfId,n.style.left,n.style.top,n.style.width,n.style.height])"
    )
    markup = page.locator('[data-sf-id="shape"]').inner_html()
    for key in roots:
        page.locator(f'[data-sf-id="{key}"]').click(
            position={"x": 2, "y": 2}, modifiers=["Control"]
        )
    group = page.get_by_role("button", name="4 Objekte verschieben")
    expect(group).to_be_visible()
    size = page.get_by_role("combobox", name="Schriftgröße", exact=True)
    expect(size).to_be_enabled()
    expect(size.locator("option:checked")).to_have_text("Gemischt")
    for label in ["Schriftart", "Objekt löschen", "Bild zuschneiden", "Füllfarbe"]:
        expect(page.get_by_label(label, exact=True)).to_be_disabled()
    page.get_by_role("button", name="Schrift vergrößern", exact=True).click()
    assert _sizes(page) == pytest.approx([n + 2 for n in original], abs=0.01)
    expect(size.locator("option:checked")).to_have_text("Gemischt")
    page.get_by_role("button", name="Schrift verkleinern", exact=True).click()
    assert _sizes(page) == pytest.approx(original, abs=0.01)
    size.focus()
    size.select_option("18")
    expect(size).to_be_focused()
    expect(group).to_be_visible()
    assert _sizes(page) == pytest.approx([18] * 5, abs=0.01)
    page.keyboard.press("Control+z")
    assert _sizes(page) == pytest.approx(original, abs=0.01)
    expect(size.locator("option:checked")).to_have_text("Gemischt")
    page.keyboard.press("Control+y")
    assert _sizes(page) == pytest.approx([18] * 5, abs=0.01)
    expect(page.locator('[data-sf-id="words"] em')).to_have_text("Beta")
    expect(page.locator('[data-sf-id="nested"] strong')).to_have_text("Delta")
    assert page.locator('[data-sf-id="shape"]').inner_html() == markup
    assert (
        page.locator("[data-sf-id]").evaluate_all(
            "nodes=>nodes.map(n=>[n.dataset.sfId,n.style.left,n.style.top,n.style.width,n.style.height])"
        )
        == positions
    )
    saved = _download(page, tmp_path / "font-group.html")
    fresh = browser_factory(saved)
    assert _sizes(fresh) == pytest.approx([18] * 5, abs=0.01)
    assert _object_ids(fresh) == ids
    for field in ["notes", "guidance", "deckId"]:
        assert _meta(fresh)[field] == meta[field]
    _edit(fresh)
    for key in ["shape", "empty"]:
        fresh.locator(f'[data-sf-id="{key}"]').click(modifiers=["Control"])
    expect(fresh.get_by_role("button", name="2 Objekte verschieben")).to_be_visible()
    expect(
        fresh.get_by_role("combobox", name="Schriftgröße", exact=True)
    ).to_be_disabled()
    expect(
        fresh.get_by_role("button", name="Schrift vergrößern", exact=True)
    ).to_be_disabled()
    expect(fresh.get_by_role("button", name="Rückgängig", exact=True)).to_be_disabled()


def test_nested_keyboard_configuration_survives_group_font_history(
    tmp_path, browser_factory
):
    path = _mixed_deck(tmp_path)
    image = '<div data-sf-id="nested-image" data-sf-kind="image" data-sf-crop=\'{"x":0,"y":0,"w":1,"h":1}\' style="position:absolute;left:340px;top:20px;width:40px;height:40px"><img width="40" height="40" alt="" src="data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'40\' height=\'40\'%3E%3C/svg%3E"></div>'
    source = path.read_text().replace(
        "</p>\n    </div>", "</p>" + image + "\n    </div>", 1
    )
    path.write_text(source)
    page = browser_factory(path)
    _edit(page)
    container = page.locator('[data-sf-id="container"]')
    nested = page.locator('[data-sf-id="nested"]')

    def tab_to_nested():
        container.focus()
        page.keyboard.press("Tab")
        expect(nested).to_be_focused()
        expect(nested).to_have_attribute("contenteditable", "false")
        child_image = page.locator('[data-sf-id="nested-image"] img')
        expect(child_image).to_have_attribute("draggable", "false")
        assert child_image.evaluate("e=>e.style.pointerEvents") == "none"

    tab_to_nested()
    page.keyboard.press("Escape")
    for key in ["words", "container", "shape"]:
        page.locator(f'[data-sf-id="{key}"]').click(
            position={"x": 2, "y": 2}, modifiers=["Control"]
        )
    original = nested.inner_html()
    page.get_by_role("button", name="Schrift vergrößern", exact=True).click()
    formatted = nested.inner_html()
    page.keyboard.press("Control+z")
    expect(page.get_by_role("button", name="3 Objekte verschieben")).to_be_visible()
    assert nested.inner_html() == original
    tab_to_nested()
    page.keyboard.press("Control+y")
    assert nested.inner_html() == formatted
    tab_to_nested()
