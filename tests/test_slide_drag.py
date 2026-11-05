"""Task004: two focused real-mouse, offline-file slide ordering scenarios."""

from pathlib import Path

from playwright.sync_api import Page, expect

from test_editor_e2e import (
    _download,
    _edit,
    _json_script,
    _meta,
    _object_ids,
    _ready,
    _set_json_script,
    _slide_ids,
    browser_factory as browser_factory,
)


def _thumbnail(page: Page, slide_id: str):
    return page.locator(f'#sf-thumbnail-list button[data-slide="{slide_id}"]')


def _start_drag(page: Page, slide_id: str) -> None:
    item = _thumbnail(page, slide_id)
    item.scroll_into_view_if_needed()
    box = item.bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 12, y + 12, steps=5)


def _over(page: Page, slide_id: str, *, after: bool) -> None:
    box = _thumbnail(page, slide_id).locator("..").bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + (box["height"] - 8 if after else 8)
    page.mouse.move(x, y, steps=8)
    page.mouse.move(x, y)


def test_mouse_order_undo_and_saved_print_handoff(
    tmp_path: Path, browser_factory
) -> None:
    page = browser_factory(_ready(tmp_path))
    original, objects, metadata = _slide_ids(page), _object_ids(page), _meta(page)
    _edit(page)
    expect(page.locator(".sf-thumbnails")).to_be_visible()
    assert (
        page.get_by_role("button", name="Folie 1 nach vorne", exact=True).count() == 0
    )
    expect(
        page.get_by_role("button", name="Folie 1 löschen", exact=True)
    ).to_be_visible()

    _start_drag(page, original[0])
    _over(page, original[-1], after=True)
    expect(page.locator(".sf-drop-after")).to_have_count(1)
    assert _slide_ids(page) == original  # Preview never mutates the deck.
    page.mouse.up()
    moved = original[1:] + original[:1]
    assert _slide_ids(page) == moved
    expect(_thumbnail(page, original[0])).to_have_attribute("aria-current", "true")
    page.keyboard.press("Control+z")
    assert _slide_ids(page) == original
    expect(page.locator('[data-action="undo"]')).to_be_disabled()
    page.keyboard.press("Control+y")
    assert _slide_ids(page) == moved

    _start_drag(page, original[0])
    _over(page, original[1], after=False)
    page.mouse.up()
    assert _slide_ids(page) == original
    page.keyboard.press("Control+z")
    assert _slide_ids(page) == moved

    saved = _download(page, tmp_path / "mouse-ordered.html")
    fresh = browser_factory(saved)
    assert _slide_ids(fresh) == moved
    assert sorted(_object_ids(fresh)) == sorted(objects)
    for field in ("notes", "guidance", "qaExtension", "deckId"):
        assert _meta(fresh)[field] == metadata[field]
    fresh.get_by_role("button", name="Drucken/PDF", exact=True).click()
    with fresh.expect_popup() as opened:
        fresh.get_by_role("button", name="Drucken", exact=True).click()
    popup = opened.value
    expect(popup.locator("html")).to_have_attribute(
        "data-sf-print-ready", "true", timeout=20000
    )
    assert (
        popup.locator(".sf-print-page").evaluate_all(
            "nodes => nodes.map(n => n.dataset.slide)"
        )
        == moved
    )
    popup.close()


def _long_deck(tmp_path, count=10):
    path = _ready(tmp_path)
    source = path.read_text()
    metadata = _json_script(source)
    additions = []
    for number in range(count):
        slide_id = f"extra-{number}"
        additions.append(
            f'<section class="sf-slide" data-sf-slide="{slide_id}" style="width:1600px;height:900px"><h2>Neutral slide {number}</h2></section>'
        )
        metadata["notes"][slide_id] = f"Note {number}"
        metadata["guidance"][slide_id] = {
            "text": f"Guidance {number}",
            "status": "open",
        }
    source = source.replace("</main>", "".join(additions) + "</main>", 1)
    path.write_text(_set_json_script(source, metadata))
    return path


def test_mouse_cancel_click_edge_scroll_and_keyboard(
    tmp_path: Path, browser_factory
) -> None:
    page = browser_factory(_long_deck(tmp_path))
    original = _slide_ids(page)
    expect(page.locator(".sf-thumbnails")).to_be_visible()
    expect(_thumbnail(page, original[0])).to_have_attribute("draggable", "false")
    _edit(page)
    undo = page.locator('[data-action="undo"]')

    _thumbnail(page, original[1]).click()
    expect(_thumbnail(page, original[1])).to_have_attribute("aria-current", "true")
    _start_drag(page, original[0])
    _over(page, original[0], after=True)
    page.mouse.up()  # Adjacent boundary is a no-op.
    expect(undo).to_be_disabled()

    _start_drag(page, original[0])
    _over(page, original[2], after=True)
    page.keyboard.press("Escape")
    page.mouse.up()
    expect(
        page.locator(".sf-drop-before,.sf-drop-after,.sf-thumbnail-dragging")
    ).to_have_count(0)
    expect(undo).to_be_disabled()
    _start_drag(page, original[0])
    page.mouse.move(600, 450, steps=12)
    page.mouse.up()  # Outside drop cancels.
    assert _slide_ids(page) == original
    expect(undo).to_be_disabled()

    _start_drag(page, original[0])
    box = page.locator(".sf-thumbnails").bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] - 12
    page.mouse.move(x, y, steps=12)
    page.mouse.move(x, y)
    page.wait_for_function("document.querySelector('.sf-thumbnails').scrollTop > 180")
    page.mouse.up()
    assert _slide_ids(page).index(original[0]) > 2
    expect(_thumbnail(page, original[1])).to_have_attribute("aria-current", "true")
    page.keyboard.press("Control+z")
    assert _slide_ids(page) == original
    expect(undo).to_be_disabled()

    item = _thumbnail(page, original[0])
    item.focus()
    page.keyboard.press("Alt+ArrowDown")
    assert _slide_ids(page) == [original[1], original[0], *original[2:]]
    expect(item).to_be_focused()
    page.keyboard.press("Alt+ArrowUp")
    assert _slide_ids(page) == original
    page.get_by_role("button", name="Fertig", exact=True).click()
    expect(item).to_have_attribute("draggable", "false")
    item.focus()
    page.keyboard.press("Alt+ArrowDown")
    assert _slide_ids(page) == original


def test_sidebar_follows_navigation_and_reopen_without_stealing_focus(
    tmp_path, browser_factory
):
    page = browser_factory(_long_deck(tmp_path, 20))
    sidebar = page.locator("#sf-thumbnails")
    choice = page.locator("#sf-slide-choice")
    heading = sidebar.locator(".sf-sidebar-heading")
    ids = _slide_ids(page)

    def assert_visible_entry(slide_id):
        item = _thumbnail(page, slide_id)
        expect(item).to_have_attribute("aria-current", "true")
        port = sidebar.bounding_box()
        row = item.locator("..").bounding_box()
        header = heading.bounding_box()
        assert header["y"] >= port["y"] - 1
        assert row["y"] >= header["y"] + header["height"] - 1
        assert row["y"] + row["height"] <= port["y"] + port["height"] + 1

    for _ in range(12):
        page.keyboard.press("ArrowRight")
    assert_visible_entry(ids[12])
    assert page.evaluate("document.activeElement === document.body")
    previous = page.get_by_role("button", name="Vorherige Folie")
    for _ in range(8):
        previous.click()
    assert_visible_entry(ids[4])
    expect(previous).to_be_focused()
    next_button = page.get_by_role("button", name="Nächste Folie")
    for i in range(5, 16):
        next_button.click()
        assert_visible_entry(ids[i])
    expect(next_button).to_be_focused()
    choice.focus()
    choice.select_option(ids[-1])
    assert_visible_entry(ids[-1])
    expect(choice).to_be_focused()
    toggle = page.locator('[data-action="thumbnails"]')
    toggle.click()
    page.keyboard.press("PageUp")
    page.keyboard.press("PageUp")
    toggle.click()
    expect(toggle).to_be_focused()
    assert_visible_entry(ids[-3])
    _edit(page)
    assert_visible_entry(ids[-3])
    # A fit without any geometry change must respect manual browsing.
    sidebar.evaluate("e=>e.scrollTop=0")
    page.evaluate("window.dispatchEvent(new Event('resize'))")
    assert sidebar.evaluate("e=>e.scrollTop") == 0
