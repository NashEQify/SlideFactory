"""An open guidance panel visibly follows the slide and preserves each contribution."""
import pytest
from playwright.sync_api import expect

from test_editor_e2e import (
    _ready, _edit, _download, _cli, _json_script, _set_json_script,
    _slide_spans, _meta, browser_factory,
)


@pytest.mark.parametrize('template', ['consulting.html', 'editorial.html', 'mbb.html'])
def test_open_guidance_follows_navigation_and_file_handoff(tmp_path, browser_factory, template):
    path = _ready(tmp_path, template)
    source = path.read_text()
    ids = list(_slide_spans(source))
    # The panel counts storyline slides; Clean MBB's deep dive has no number.
    count = sum('data-sf-deep-dive=' not in span for span in _slide_spans(source).values())
    meta = _json_script(source)
    meta['guidance'][ids[0]] = {'text': 'First slide instruction', 'status': 'addressed'}
    meta['guidance'][ids[1]] = {'text': 'Second slide instruction', 'status': 'open'}
    path.write_text(_set_json_script(source, meta))
    page = browser_factory(path)
    _edit(page)
    page.get_by_role('button', name='Kommentare', exact=True).click()
    field = page.get_by_label('Bearbeitungskommentar', exact=True)
    addressed = page.get_by_label('Hinweis erledigt', exact=True)
    context = page.locator('#sf-panel-slide')
    expect(context).to_have_text(f'Folie 1 von {count}')
    expect(field).to_have_attribute('aria-describedby', 'sf-panel-slide')
    expect(field).to_have_value('First slide instruction')
    expect(addressed).to_be_checked()
    field.fill('First human contribution')
    page.get_by_role('button', name='Nächste Folie', exact=True).click()
    expect(context).to_have_text(f'Folie 2 von {count}')
    expect(field).to_have_value('Second slide instruction')
    expect(addressed).not_to_be_checked()
    field.fill('Second human contribution')
    page.get_by_label('Folie auswählen', exact=True).select_option(ids[0])
    expect(context).to_have_text(f'Folie 1 von {count}')
    expect(field).to_have_value('First human contribution')
    field.focus()
    page.evaluate('(id) => {location.hash = encodeURIComponent(id)}', ids[1])
    expect(field).to_have_value('Second human contribution')
    expect(field).to_have_attribute('data-slide', ids[1])
    expect(context).to_have_text(f'Folie 2 von {count}')
    field.fill('Second contribution after focused switch')
    addressed.check()
    page.get_by_role('button', name='Folie 1', exact=True).click()
    expect(field).to_have_value('First human contribution')
    expect(addressed).not_to_be_checked()
    page.get_by_role('button', name='Folie 2', exact=True).click()
    expect(field).to_have_value('Second contribution after focused switch')
    expect(addressed).to_be_checked()
    saved = _download(page, tmp_path / 'guidance-saved.html')
    _cli('validate', saved)
    fresh = browser_factory(saved)
    actual = _meta(fresh)['guidance']
    assert actual[ids[0]] == {'text': 'First human contribution', 'status': 'open'}
    assert actual[ids[1]] == {'text': 'Second contribution after focused switch', 'status': 'addressed'}
    _edit(fresh)
    fresh.get_by_role('button', name='Kommentare', exact=True).click()
    fresh.get_by_label('Folie auswählen', exact=True).select_option(ids[1])
    expect(fresh.locator('#sf-panel-slide')).to_have_text(f'Folie 2 von {count}')
    expect(fresh.get_by_label('Bearbeitungskommentar', exact=True)).to_have_value('Second contribution after focused switch')
