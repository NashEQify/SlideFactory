"""Hidden slides survive offline handoff and leave the audience/print sequence."""

import re
import subprocess

from playwright.sync_api import expect

from test_editor_e2e import (
    _download,
    _edit,
    _meta,
    _object_ids,
    _ready,
    _slide_ids,
    browser_factory as browser_factory,
)
from test_presenter_timing import _deck, _presenter


def _eye(page, position, action):
    return page.get_by_role("button", name=f"Folie {position} {action}", exact=True)


def test_visibility_edit_history_guard_and_saved_handoff(tmp_path, browser_factory):
    page = browser_factory(_ready(tmp_path))
    ids, objects, metadata = _slide_ids(page), _object_ids(page), _meta(page)
    _edit(page)
    _eye(page, 1, "ausblenden").focus()
    page.keyboard.press("Enter")
    expect(_eye(page, 1, "einblenden")).to_be_focused()
    expect(page.get_by_role("button", name="Folie 1 · ausgeblendet")).to_have_attribute(
        "aria-current", "true"
    )
    page.keyboard.press("Control+z")
    expect(_eye(page, 1, "ausblenden")).to_be_focused()
    page.keyboard.press("Control+y")
    expect(_eye(page, 1, "einblenden")).to_be_focused()
    _eye(page, 2, "ausblenden").click()
    expect(
        page.get_by_role("button", name=re.compile("^Folie 3 ausblenden"))
    ).to_be_disabled()
    expect(page.get_by_role("button", name="Folie 3 löschen")).to_be_disabled()
    fresh = browser_factory(_download(page, tmp_path / "hidden.html"))
    expect(fresh.locator("#sf-slide-choice")).to_have_value(ids[2])
    expect(fresh.get_by_role("button", name="Vorherige Folie")).to_be_disabled()
    _edit(fresh)
    fresh.get_by_role("button", name="Folie 1 · ausgeblendet").click()
    expect(fresh.locator('[data-sf-id="qa-text"]')).to_be_visible()
    _eye(fresh, 1, "einblenden").click()
    recovered = browser_factory(_download(fresh, tmp_path / "restored.html"))
    assert (_slide_ids(recovered), _object_ids(recovered)) == (ids, objects)
    for field in ("notes", "guidance", "deckId", "qaExtension"):
        assert _meta(recovered)[field] == metadata[field]
    expect(recovered.locator("#sf-slide-choice")).to_have_value(ids[0])
    recovered.keyboard.press("ArrowRight")
    expect(recovered.locator("#sf-slide-choice")).to_have_value(ids[2])
    recovered.keyboard.press("Home")
    expect(recovered.locator("#sf-slide-choice")).to_have_value(ids[0])


def test_hidden_middle_presenter_and_print(tmp_path, browser_factory):
    page = browser_factory(
        _deck(
            tmp_path,
            approach='data-sf-duration="900" data-sf-hidden',
            outlook='data-sf-duration="30"',
        )
    )
    popup = _presenter(page)
    expect(popup.locator("#target")).to_contain_text("Ziel 01:30")
    expect(popup.locator("#next-preview")).to_have_attribute(
        "srcdoc", re.compile('data-sf-slide="outlook"')
    )
    popup.get_by_role("button", name="Nächste Folie").click()
    expect(page.locator("#sf-slide-choice")).to_have_value("outlook")
    popup.keyboard.press("ArrowLeft")
    expect(page.locator("#sf-slide-choice")).to_have_value("intro")
    popup.close()
    page.keyboard.press("f")
    page.wait_for_function("!!document.fullscreenElement")
    page.keyboard.press("ArrowRight")
    expect(page.locator("#sf-slide-choice")).to_have_value("outlook")
    page.evaluate("document.exitFullscreen()")
    page.emulate_media(media="print")
    expect(page.locator('[data-sf-slide="approach"]')).to_be_hidden()
    expect(page.locator('[data-sf-slide="intro"]')).to_be_visible()
    native_pdf = tmp_path / "visible.pdf"
    page.pdf(path=str(native_pdf), prefer_css_page_size=True, print_background=True)
    extracted = subprocess.check_output(["pdftotext", str(native_pdf), "-"], text=True)
    sheets = [sheet for sheet in extracted.split("\f") if sheet.strip()]
    assert len(sheets) == 2
    assert "Gemeinsam" in sheets[0] and "Perspektive" in sheets[1]
    page.emulate_media(media="screen")
    page.get_by_role("button", name="Drucken/PDF").click()
    page.locator("#sf-print-range").fill("2")
    page.get_by_role("button", name="Drucken", exact=True).click()
    expect(page.locator("#sf-print-error")).to_contain_text("nur ausgeblendete")
    page.locator("#sf-print-range").fill("1-3")
    with page.expect_popup() as opened:
        page.get_by_role("button", name="Drucken", exact=True).click()
    pages = opened.value.locator(".sf-print-page")
    expect(pages).to_have_count(2)
    assert pages.evaluate_all("(pages)=>pages.map(p=>p.dataset.slide)") == [
        "intro",
        "outlook",
    ]
