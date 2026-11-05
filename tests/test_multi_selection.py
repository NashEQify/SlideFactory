"""Move a transient selection through the real offline editor."""

import pytest
from playwright.sync_api import expect
from test_editor_e2e import (
    PACKAGE,
    _download,
    _edit,
    browser_factory as browser_factory,
)


def _deck(tmp_path):
    source = (PACKAGE / "assets/blank.html").read_text()
    content = """
    <div data-sf-id="outer" data-sf-kind="box" style="position:absolute;left:200px;top:200px;width:150px;height:80px;background:red">
      <div data-sf-id="inner" data-sf-kind="text" style="position:absolute;left:10px;top:10px;width:80px;height:40px">Nested</div>
    </div>
    <div style="position:absolute;left:500px;top:220px;transform:scale(.7);transform-origin:0 0">
      <div data-sf-id="flow" data-sf-kind="box" data-sf-layout="flow" style="width:180px;height:80px;background:blue">Flow</div></div>
    <div data-sf-id="other" data-sf-kind="box" style="position:absolute;left:1000px;top:650px;width:160px;height:80px;background:lime"></div>
    """
    path = tmp_path / "group.html"
    path.write_text(source.replace("</section>", content + "</section>", 1))
    return path


def _objects(page):
    return [
        page.locator(f'[data-sf-id="{key}"]')
        for key in ("outer", "inner", "flow", "other")
    ]


def _styles(nodes):
    return [node.evaluate("e=>e.style.cssText") for node in nodes]


def _pointer(page, node, dx, dy, release=True):
    b = node.bounding_box()
    x, y = b["x"] + b["width"] * 0.9, b["y"] + b["height"] * 0.8
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + dx, y + dy, steps=4)
    if release:
        page.mouse.up()


def test_modified_click_atomic_group_move_and_download(tmp_path, browser_factory):
    page = browser_factory(_deck(tmp_path))
    _edit(page)
    nodes = _objects(page)
    outer, inner, flow, other = nodes
    before = _styles(nodes)
    outer.click(position={"x": 2, "y": 2})
    flow.click(modifiers=["Control"])
    group = page.get_by_role("button", name="2 Objekte verschieben")
    expect(group).to_be_visible()
    expect(page.get_by_role("button", name="Größe ändern unten rechts")).to_be_hidden()
    other.click(modifiers=["Control"])
    expect(page.get_by_role("button", name="3 Objekte verschieben")).to_be_visible()
    other.click(modifiers=["Control"])
    start = [n.bounding_box() for n in [outer, inner, flow]]
    _pointer(page, flow, 34, 16)
    for rect, node in zip(start, [outer, inner, flow]):
        box = node.bounding_box()
        assert abs(box["x"] - rect["x"] - 34) < 1 and abs(box["y"] - rect["y"] - 16) < 1
    moved = _styles(nodes)
    page.keyboard.press("Control+z")
    assert _styles(nodes) == before
    page.keyboard.press("Control+y")
    assert _styles(nodes) == moved
    _pointer(page, outer, -18, 12, release=False)
    page.keyboard.press("Escape")
    page.mouse.up()
    assert _styles(nodes) == moved
    expect(page.locator("#sf-selection")).to_be_hidden()
    outer.click(position={"x": 2, "y": 2})
    flow.click(modifiers=["Control"])
    expect(group).to_be_visible()
    saved = _download(page, tmp_path / "group-saved.html")
    fresh = browser_factory(saved)
    assert _styles(_objects(fresh)) == moved
    expect(fresh.locator("#sf-selection")).to_be_hidden()
    assert not fresh.locator("[data-sf-runtime-group-member]").count()


def test_marquee_normalizes_nested_members_and_nudges_once(tmp_path, browser_factory):
    page = browser_factory(_deck(tmp_path))
    _edit(page)
    outer, inner, flow, other = nodes = _objects(page)
    before = _styles(nodes)
    b, f = outer.bounding_box(), flow.bounding_box()
    page.mouse.move(b["x"] - 10, b["y"] - 8)
    page.mouse.down()
    page.mouse.move(
        f["x"] + f["width"] + 10,
        max(b["y"] + b["height"], f["y"] + f["height"]) + 10,
        steps=4,
    )
    page.mouse.up()
    group = page.get_by_role("button", name="2 Objekte verschieben")
    expect(group).to_be_visible()
    page.keyboard.press("Shift+ArrowRight")
    nudged = _styles(nodes)
    assert nudged[0] != before[0] and nudged[2] != before[2]
    assert nudged[1::2] == before[1::2]
    page.keyboard.press("Delete")
    assert _styles(nodes) == nudged
    page.keyboard.press("Control+z")
    assert _styles(nodes) == before
    # A second marquee adds to the original selection.
    b = other.bounding_box()
    page.keyboard.down("Control")
    page.mouse.move(b["x"] - 8, b["y"] - 8)
    page.mouse.down()
    page.mouse.move(b["x"] + 12, b["y"] + 12, steps=3)
    page.mouse.up()
    page.keyboard.up("Control")
    expect(page.get_by_role("button", name="3 Objekte verschieben")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator("#sf-selection")).to_be_hidden()
    # Pin the focused object, tab to a sibling and toggle it from the keyboard.
    flow.focus()
    page.keyboard.press("Control+Space")
    page.keyboard.press("Tab")
    expect(other).to_be_focused()
    page.keyboard.press("Control+Space")
    expect(group).to_be_visible()
    page.get_by_role("button", name="Fertig", exact=True).click()
    expect(page.locator("#sf-selection")).to_be_hidden()


@pytest.mark.parametrize(
    "css", ["scale:.7", "rotate:25deg;scale:.65 1.15;transform:rotate(-10deg)"]
)
def test_group_spacing_with_individual_transforms(tmp_path, browser_factory, css):
    path = _deck(tmp_path)
    path.write_text(
        path.read_text().replace(
            "transform:scale(.7);transform-origin", f"{css};transform-origin"
        )
    )
    page = browser_factory(path)
    _edit(page)
    outer, _, flow, _ = _objects(page)
    outer.click(position={"x": 2, "y": 2})
    flow.click(modifiers=["Control"])
    group = page.get_by_role("button", name="2 Objekte verschieben")
    expect(group).to_be_visible()
    start = [node.bounding_box() for node in (outer, flow)]
    _pointer(page, outer, 34, 16)
    moved = [node.bounding_box() for node in (outer, flow)]
    for a, b in zip(start, moved):
        assert (b["x"] - a["x"], b["y"] - a["y"]) == pytest.approx((34, 16), abs=0.2)
    group.press("Shift+ArrowRight")
    nudged = [node.bounding_box() for node in (outer, flow)]
    dx = nudged[0]["x"] - moved[0]["x"]
    assert dx > 1
    for a, b in zip(moved, nudged):
        assert (b["x"] - a["x"], b["y"] - a["y"]) == pytest.approx((dx, 0), abs=0.2)
