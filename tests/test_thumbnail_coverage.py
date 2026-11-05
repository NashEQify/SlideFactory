"""All viewport-demanded thumbnails render and release their browsing contexts."""

import pytest
from playwright.sync_api import expect
from test_editor_e2e import browser_factory as browser_factory
from test_slide_drag import _long_deck

COVERAGE = """() => {
  const panel=document.querySelector('#sf-thumbnails'), view=panel.getBoundingClientRect();
  const entries=[...panel.querySelectorAll('button[data-slide]')];
  return entries.every(entry=>{
    const box=entry.getBoundingClientRect();
    const wanted=box.bottom>=view.top-30 && box.top<=view.bottom+30;
    return !!entry.querySelector('iframe')===wanted;
  });
}"""


def assert_thumbnail_coverage(page):
    page.wait_for_function(COVERAGE)
    return page.locator("#sf-thumbnails iframe").count()


@pytest.mark.parametrize("fallback", [False, True])
def test_complete_thumbnail_viewport_and_scroll_recovery(
    tmp_path, browser_factory, fallback
):
    page = browser_factory(
        _long_deck(tmp_path, 20), viewport={"width": 1280, "height": 1080}
    )
    if fallback:
        page.add_init_script("window.IntersectionObserver=undefined")
        page.reload()
    panel = page.locator("#sf-thumbnails")
    assert assert_thumbnail_coverage(page) > 6
    panel.evaluate("e=>e.scrollTop=e.scrollHeight")
    assert assert_thumbnail_coverage(page) > 6
    panel.evaluate("e=>e.scrollTop=0")
    assert_thumbnail_coverage(page)
    page.locator("#sf-slide-choice").select_option("extra-19")
    assert_thumbnail_coverage(page)
    toggle = page.get_by_role("button", name="Folienübersicht", exact=True)
    toggle.click()
    expect(panel.locator("iframe")).to_have_count(0)
    toggle.click()
    assert_thumbnail_coverage(page)
