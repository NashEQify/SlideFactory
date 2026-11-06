"""Small empty files: actual offline editing, downloads and presenter lifecycle.

Run this file with SF_BROWSER=chromium|firefox|webkit. Playwright's browser
environments are isolated; no installed personal browser profile is accessed.
"""
import pytest
from playwright.sync_api import Error as PlaywrightError, expect

from test_editor_e2e import _presenter_action
from test_editor_e2e import PACKAGE, _cli, _download, _edit, _meta, browser_factory


# Budget intent: keep the entire reusable editor/template small before any
# content is added; catch accidental embedded demo images/fonts or bundles.
# Rich notes, print, structural history and checked release identity add ~30 KiB;
# the 1.2-1.3 toolbar, shapes, notes pane and slide links bring it to ~180 KiB;
# the three design overview slides add ~9 KiB. Clean MBB embeds its five Latin
# WOFF2 subsets (~77 KiB, ~103 KiB as base64) and nothing else.
BUDGET_KIB = {'consulting-blank.html': 208, 'editorial-blank.html': 208, 'mbb-blank.html': 312}
# A non-default look per template; Clean MBB declares its own looks.
LOOK = {'consulting-blank.html': 'indigo-light', 'editorial-blank.html': 'indigo-light', 'mbb-blank.html': 'paper-marine'}


@pytest.mark.parametrize('template', list(BUDGET_KIB))
def test_empty_template_offline_file_handoff_and_presenter(tmp_path, browser_factory, template):
    source = PACKAGE / 'assets' / template
    assert source.stat().st_size < BUDGET_KIB[template] * 1024
    path = tmp_path / template
    path.write_bytes(source.read_bytes())
    page = browser_factory(path)
    expect(page.locator('#sf-deck [data-sf-slide][data-sf-overview]')).to_have_count(3)
    expect(page.locator('#sf-deck [data-sf-slide]:not([data-sf-overview])')).to_have_count(1)
    expect(page.locator('#sf-deck [data-sf-id],#sf-deck img')).to_have_count(0)
    assert page.locator('#sf-deck [data-sf-slide="intro"]').inner_text().strip() == ''
    faces = path.read_text().count('@font-face')
    assert faces == (5 if template == 'mbb-blank.html' else 0)
    _edit(page)
    page.get_by_label('Farbschema', exact=True).select_option(LOOK[template])
    page.get_by_role('button', name='Kommentare', exact=True).click()
    page.get_by_label('Bearbeitungskommentar', exact=True).fill('Offline file contribution')
    saved = _download(page, tmp_path / 'complete-handoff.html')
    _cli('validate', saved)
    with page.expect_popup() as opened:
        _presenter_action(page)
    popup = opened.value
    expect(popup.locator('#connection')).to_have_text('Mit Präsentation verbunden.')
    try:
        with popup.expect_event('close'):
            popup.get_by_role('button', name='Referentenansicht schließen', exact=True).click()
    except PlaywrightError as error:
        # Firefox may acknowledge window.close before its click protocol reply.
        assert 'closed' in str(error) and popup.is_closed(), 'an automation error must not mask a failed close'
    assert not page.is_closed()
    fresh = browser_factory(saved)
    # The comment lands on the slide shown first: the opening design overview slide.
    assert _meta(fresh)['guidance']['design-type']['text'] == 'Offline file contribution'
    assert _meta(fresh)['colorScheme'] == LOOK[template]
    _edit(fresh)
    expect(fresh.get_by_role('button', name='Fertig', exact=True)).to_be_visible()
