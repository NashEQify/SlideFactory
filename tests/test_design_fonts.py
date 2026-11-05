"""New text follows the design's text font; embedded design fonts lead the font list."""
import pytest
from playwright.sync_api import expect

from test_editor_e2e import _cli, _download, _edit, _starter, browser_factory


@pytest.mark.parametrize('template,family,listed', [
    ('consulting.html', 'Arial', ['Arial', 'Calibri']),
    ('mbb.html', 'Inter', ['Inter', 'Zain', 'Arial']),
])
def test_inserted_text_uses_design_font(tmp_path, browser_factory, template, family, listed):
    path = tmp_path / template
    path.write_text(_starter(template))
    page = browser_factory(path)
    _edit(page)
    options = page.get_by_label('Schriftart', exact=True).locator('option').all_text_contents()
    assert options[:len(listed)] == listed
    page.get_by_role('button', name='Textfeld einfügen', exact=True).click()
    inserted = page.locator('#sf-deck [data-sf-kind="text"][data-sf-id^="text-"]')
    expect(inserted).to_have_count(1)
    assert inserted.evaluate('n => getComputedStyle(n).fontFamily').split(',')[0].strip('"\' ') == family
    page.keyboard.press('Escape')
    saved = _download(page, tmp_path / 'saved.html')
    _cli('validate', saved)
    fresh = browser_factory(saved)
    text = fresh.locator('#sf-deck [data-sf-kind="text"][data-sf-id^="text-"]')
    assert text.evaluate('n => getComputedStyle(n).fontFamily').split(',')[0].strip('"\' ') == family
