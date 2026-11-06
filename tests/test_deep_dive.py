"""Deep-dive overlay (spec 007): storyline, overlay, presenter sync, print appendix, handoff, helper."""
import json
import re
import subprocess

import pytest
from playwright.sync_api import expect

from test_editor_e2e import (
    PACKAGE,
    _cli,
    _download,
    _edit,
    _json_script,
    _set_json_script,
    _starter,
    browser_factory as browser_factory,
)
from test_presenter_timing import _presenter

pytestmark = pytest.mark.e2e

DETAIL = 'insights-detail'
SECOND = 'second-detail'
ORPHAN = 'orphan-detail'
# The second deep dive sits between storyline slides and has an empty name ("Deep Dive 1").
SECOND_SLIDE = (
    f'<section class="sf-slide" data-sf-slide="{SECOND}" data-sf-deep-dive="">'
    '<h2 class="headline" data-sf-id="second-title" data-sf-kind="text" '
    'style="position:absolute;left:112px;top:108px;width:1376px;height:70px">Zweiter Vertiefungsinhalt</h2></section>'
)
ORPHAN_SLIDE = (
    f'<section class="sf-slide" data-sf-slide="{ORPHAN}" data-sf-deep-dive="Reserve">'
    '<h2 class="headline" data-sf-id="orphan-title" data-sf-kind="text" '
    'style="position:absolute;left:112px;top:108px;width:1376px;height:70px">Reserveinhalt ohne Verweis</h2></section>'
)
LINK = (
    f'<a class="sf-link" data-sf-id="approach-detail-link" data-sf-kind="text" data-sf-link="" href="#{SECOND}" '
    'style="position:absolute;left:112px;top:800px;width:240px;height:40px">Mehr dazu</a>'
)


def _deck(tmp_path, name='dives.html'):
    """Clean MBB deck: two triggers on the findings slide, a slide link and an unnamed deep dive."""
    source = _starter('mbb.html')
    source = source.replace(
        'data-sf-id="insights-panel-3" data-sf-kind="box"',
        f'data-sf-id="insights-panel-3" data-sf-kind="box" data-sf-deep-dive-target="{SECOND}"', 1)
    source = source.replace('<p class="deck-footer">SLIDEFACTORY · ARBEITSWEISE</p>', LINK + '<p class="deck-footer">SLIDEFACTORY · ARBEITSWEISE</p>', 1)
    source = source.replace('<section class="sf-slide" data-sf-slide="agenda"', SECOND_SLIDE + '\n  <section class="sf-slide" data-sf-slide="agenda"', 1)
    source = source.replace('</main>', ORPHAN_SLIDE + '\n</main>', 1)
    meta = _json_script(source)
    for identity in (SECOND, ORPHAN):
        meta['notes'][identity] = ''
        meta['guidance'][identity] = {'text': '', 'status': 'open'}
    meta['notes'][DETAIL] = 'Detailnotiz zum Deep Dive'
    meta['notes']['insights'] = 'Notiz zum Befund'
    path = tmp_path / name
    path.write_text(_set_json_script(source, meta), encoding='utf-8')
    return path


def _current(page):
    return page.evaluate('document.querySelector("#sf-deck > [data-sf-runtime-visible=\\"true\\"]").dataset.sfSlide')


def _go(page, identity):
    page.locator('#sf-slide-choice').select_option(identity)
    assert _current(page) == identity


def _overlay(page):
    return page.locator('#sf-deep-dive')


def _state(page):
    return page.evaluate('''() => ({deck: document.querySelector('#sf-deck').outerHTML,
      save: document.querySelector('#sf-save-state').dataset.state,
      undo: document.querySelector('[data-action="undo"]').disabled})''')


def test_storyline_skips_deep_dives_in_view_and_reaches_them_in_edit(tmp_path, browser_factory):
    page = browser_factory(_deck(tmp_path))
    counter = page.locator('#sf-counter')
    expect(counter).to_have_text('Folie 1 / 5')
    page.keyboard.press('ArrowRight')
    assert _current(page) == 'agenda', 'the deep dive between intro and agenda is skipped'
    expect(counter).to_have_text('Folie 2 / 5')
    page.keyboard.press('End')
    assert _current(page) == 'outlook'
    expect(counter).to_have_text('Folie 5 / 5')
    page.keyboard.press('PageDown')
    assert _current(page) == 'outlook'
    expect(page.get_by_role('button', name='Nächste Folie', exact=True)).to_be_disabled()
    page.keyboard.press('Home')
    page.keyboard.press('PageUp')
    assert _current(page) == 'intro'
    _edit(page)
    page.get_by_role('button', name='Nächste Folie', exact=True).click()
    assert _current(page) == SECOND, 'edit mode reaches deep dives like hidden slides'
    expect(counter).to_have_text('Deep Dive · Deep Dive 1')
    page.locator(f'#sf-thumbnail-list button[data-slide="{ORPHAN}"]').click()
    assert _current(page) == ORPHAN
    expect(page.get_by_role('button', name='Nächste Folie', exact=True)).to_be_disabled()
    captions = page.locator('#sf-thumbnail-list .sf-thumbnail-caption').all_inner_texts()
    assert captions[1] == 'Deep Dive · Deep Dive 1'
    assert captions[-2:] == ['Deep Dive · Spitzen im Detail', 'Deep Dive · Reserve']
    assert captions[2].startswith('2 · ') and captions[5].startswith('5 · ')
    expect(page.locator(f'#sf-thumbnail-list button[data-slide="{DETAIL}"]')).to_have_attribute('aria-label', 'Deep Dive · Spitzen im Detail')
    eye = page.locator(f'#sf-thumbnail-list button[data-slide="{DETAIL}"]').locator('xpath=../div/button[1]')
    expect(eye).to_be_disabled()
    # Leaving edit mode on a deep dive returns to the storyline.
    page.get_by_role('button', name='Fertig', exact=True).click()
    assert _current(page) == 'outlook'
    expect(_overlay(page)).to_be_hidden()


def test_overlay_opens_closes_blocks_navigation_and_leaves_no_trace(tmp_path, browser_factory):
    page = browser_factory(_deck(tmp_path))
    _go(page, 'insights')
    trigger = page.locator('[data-sf-id="insights-panel-2"]')
    expect(trigger).to_have_attribute('role', 'button')
    expect(trigger).to_have_attribute('tabindex', '0')
    expect(trigger).to_have_attribute('title', 'Doppelklick für Details')
    expect(page.get_by_role('button', name='Details: Spitzen im Detail', exact=True)).to_have_count(1)
    assert trigger.evaluate('e => getComputedStyle(e).cursor') == 'zoom-in'
    before = _state(page)

    trigger.dblclick()
    overlay = _overlay(page)
    expect(overlay).to_be_visible()
    expect(page.get_by_role('dialog', name='Deep Dive: Spitzen im Detail')).to_be_visible()
    expect(overlay.locator('.sf-deep-dive-name')).to_have_text('Spitzen im Detail')
    frame = overlay.locator('iframe')
    expect(frame).to_have_attribute('srcdoc', re.compile(f'data-sf-slide="{DETAIL}"'))
    assert page.locator('[data-sf-id="insights-detail-title"]').count() == 1, 'no duplicated IDs in the document'
    assert page.evaluate(f'document.querySelector(\'[data-sf-slide="{DETAIL}"]\').parentElement.id') == 'sf-deck'
    box = frame.bounding_box()
    deck = page.locator('#sf-deck').bounding_box()
    assert box['width'] < deck['width'] and abs(box['width'] / box['height'] - 16 / 9) < 0.01
    expect(page.get_by_role('button', name='Deep Dive schließen', exact=True)).to_be_focused()
    for key in ('PageDown', 'ArrowRight', 'ArrowLeft', 'End', 'Home', 'Backspace', 'Control+z'):
        page.keyboard.press(key)
        assert _current(page) == 'insights', key
        expect(overlay).to_be_visible()
    page.keyboard.press('Escape')
    expect(overlay).to_be_hidden()
    expect(trigger).to_be_focused()
    page.keyboard.press('ArrowRight')
    assert _current(page) == 'outlook', 'a focused trigger keeps storyline keys'
    page.keyboard.press('ArrowLeft')

    trigger.focus()
    page.keyboard.press('Enter')
    expect(overlay).to_be_visible()
    page.get_by_role('button', name='Deep Dive schließen', exact=True).click()
    expect(overlay).to_be_hidden()
    expect(trigger).to_be_focused()

    page.keyboard.press('Space')
    expect(overlay).to_be_visible()
    page.wait_for_timeout(200)
    expect(overlay).to_be_visible()
    page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    expect(overlay).to_be_visible()  # a click on the rendered slide keeps it open
    page.mouse.click(4, page.viewport_size['height'] - 4)
    expect(overlay).to_be_hidden()
    assert _state(page) == before, 'overlay changes neither the document, the save state nor undo'
    assert _overlay(page).locator('iframe').count() == 0, 'the projection is released on close'

    # Navigating away closes it; edit mode adds no trigger behavior.
    trigger.dblclick()
    expect(overlay).to_be_visible()
    page.locator('#sf-slide-choice').select_option('outlook')
    expect(overlay).to_be_hidden()
    assert _current(page) == 'outlook'
    _go(page, 'insights')
    _edit(page)
    expect(trigger).not_to_have_attribute('role', 'button')
    trigger.dblclick()
    expect(overlay).to_be_hidden()
    assert _current(page) == 'insights'


def test_several_triggers_slide_link_hash_and_missing_target(tmp_path, browser_factory):
    path = _deck(tmp_path)
    page = browser_factory(path)
    _go(page, 'insights')
    overlay = _overlay(page)
    page.get_by_role('button', name='Details: Deep Dive 1', exact=True).dblclick()
    expect(overlay.locator('.sf-deep-dive-name')).to_have_text('Deep Dive 1')
    expect(overlay.locator('iframe')).to_have_attribute('srcdoc', re.compile(f'data-sf-slide="{SECOND}"'))
    page.keyboard.press('Escape')
    page.get_by_role('button', name='Details: Spitzen im Detail', exact=True).dblclick()
    expect(overlay.locator('.sf-deep-dive-name')).to_have_text('Spitzen im Detail')
    page.keyboard.press('Escape')
    # A slide link to a deep dive opens the overlay instead of navigating.
    _go(page, 'approach')
    page.locator('[data-sf-id="approach-detail-link"]').click()
    expect(overlay).to_be_visible()
    expect(overlay.locator('.sf-deep-dive-name')).to_have_text('Deep Dive 1')
    assert _current(page) == 'approach'
    expect(page.locator('#sf-return-jump')).to_be_hidden()
    page.keyboard.press('Escape')
    # Opening at a deep dive's hash: its first trigger's slide, else the first storyline slide.
    fresh = browser_factory(path)
    fresh.goto(path.resolve().as_uri() + f'#{SECOND}')
    fresh.reload()
    expect(_overlay(fresh)).to_be_visible()
    assert _current(fresh) == 'insights'
    expect(_overlay(fresh).locator('.sf-deep-dive-name')).to_have_text('Deep Dive 1')
    fresh.goto(path.resolve().as_uri() + f'#{ORPHAN}')
    fresh.reload()
    assert _current(fresh) == 'intro'
    expect(_overlay(fresh).locator('.sf-deep-dive-name')).to_have_text('Reserve')
    # A trigger whose deep dive is gone reports an error and opens nothing.
    broken = tmp_path / 'broken.html'
    broken.write_text(path.read_text().replace(f'data-sf-deep-dive-target="{SECOND}"', 'data-sf-deep-dive-target="gone"'))
    page = browser_factory(broken)
    _go(page, 'insights')
    page.get_by_role('button', name='Details: Ziel fehlt', exact=True).dblclick()
    expect(_overlay(page)).to_be_hidden()
    expect(page.get_by_role('alert')).to_contain_text('existiert nicht mehr')


def test_presenter_follows_deep_dive_both_ways(tmp_path, browser_factory):
    page = browser_factory(_deck(tmp_path))
    _go(page, 'insights')
    popup = _presenter(page)
    expect(popup.locator('#slide')).to_have_value('insights')
    assert popup.locator('#slide option[hidden]').evaluate_all('o => o.map(n => n.value)') == [SECOND, DETAIL, ORPHAN]
    expect(popup.locator('#next-preview')).to_have_attribute('srcdoc', re.compile('data-sf-slide="outlook"'))
    banner = popup.locator('#deep-dive')
    expect(banner).to_be_hidden()
    page.get_by_role('button', name='Details: Spitzen im Detail', exact=True).dblclick()
    expect(banner).to_be_visible()
    expect(banner).to_contain_text('Deep Dive offen: Spitzen im Detail')
    expect(popup.locator('#current-preview')).to_have_attribute('srcdoc', re.compile(f'data-sf-slide="{DETAIL}"'))
    expect(popup.locator('#notes')).to_have_text('Detailnotiz zum Deep Dive')
    popup.keyboard.press('ArrowRight')
    popup.wait_for_timeout(200)
    assert _current(page) == 'insights'
    expect(_overlay(page)).to_be_visible()
    popup.get_by_role('button', name='Deep Dive schließen', exact=True).click()
    expect(_overlay(page)).to_be_hidden()
    expect(banner).to_be_hidden()
    expect(popup.locator('#current-preview')).to_have_attribute('srcdoc', re.compile('data-sf-slide="insights"'))
    expect(popup.locator('#notes')).to_have_text('Notiz zum Befund')
    # Closing in the main window closes it in the presenter too; Escape there closes the dive first.
    page.get_by_role('button', name='Details: Spitzen im Detail', exact=True).dblclick()
    expect(banner).to_be_visible()
    page.keyboard.press('Escape')
    expect(banner).to_be_hidden()
    page.get_by_role('button', name='Details: Deep Dive 1', exact=True).dblclick()
    expect(banner).to_contain_text('Deep Dive offen: Deep Dive 1')
    popup.keyboard.press('Escape')
    expect(_overlay(page)).to_be_hidden()
    expect(banner).to_be_hidden()
    assert not popup.is_closed()
    popup.keyboard.press('ArrowRight')
    expect(page.locator('#sf-slide-choice')).to_have_value('outlook')


def _print_pages(page, mode, value=''):
    page.get_by_role('button', name='Drucken/PDF').click()
    page.locator('#sf-print-mode').select_option(mode)
    page.locator('#sf-print-range').fill(value)
    with page.expect_popup() as opened:
        page.get_by_role('button', name='Drucken', exact=True).click()
    popup = opened.value
    popup.wait_for_function('document.documentElement.dataset.sfPrintReady === "true"', timeout=30000)
    pages = popup.locator('.sf-print-page').evaluate_all('p => p.map(n => n.dataset.slide)')
    headings = popup.locator('.sf-print-page h1').all_inner_texts()
    popup.close()
    return pages, headings


def test_print_appends_named_deep_dives_and_native_print_follows(tmp_path, browser_factory):
    page = browser_factory(_deck(tmp_path))
    page.evaluate('window.print = () => {}')
    pages, _ = _print_pages(page, 'slides')
    assert pages == ['intro', 'agenda', 'approach', 'insights', 'outlook', SECOND, DETAIL]
    pages, _ = _print_pages(page, 'slides', '4')
    assert pages == ['insights', SECOND, DETAIL]
    pages, _ = _print_pages(page, 'notes', '3')
    assert pages == ['approach', SECOND]
    pages, headings = _print_pages(page, 'only-notes', '3-4')
    assert pages == ['approach', 'insights', SECOND, DETAIL]
    assert headings == ['Folie 3', 'Folie 4', 'Deep Dive · Deep Dive 1', 'Deep Dive · Spitzen im Detail']
    page.get_by_role('button', name='Drucken/PDF').click()
    page.locator('#sf-print-range').fill('6')
    page.get_by_role('button', name='Drucken', exact=True).click()
    expect(page.locator('#sf-print-error')).to_contain_text('zwischen 1 und 5')
    page.get_by_role('button', name='Abbrechen').click()
    # Native printing: storyline in order, then named deep dives; the unnamed reserve is left out.
    page.evaluate('window.dispatchEvent(new Event("beforeprint"))')
    page.emulate_media(media='print')
    pdf = tmp_path / 'native.pdf'
    page.pdf(path=str(pdf), prefer_css_page_size=True, print_background=True)
    page.evaluate('window.dispatchEvent(new Event("afterprint"))')
    page.emulate_media(media='screen')
    sheets = [sheet for sheet in subprocess.check_output(['pdftotext', str(pdf), '-'], text=True).split('\f') if sheet.strip()]
    assert len(sheets) == 7
    assert 'Wenige Themen' in sheets[3] and 'Zweiter Vertiefungsinhalt' in sheets[5]
    assert 'feste Spitzen' in sheets[6]
    assert not any('Reserveinhalt' in sheet for sheet in sheets)
    assert page.locator('[data-sf-runtime-print],[data-sf-runtime-print-last]').count() == 0


def test_handoff_reopen_and_helper_edits_keep_the_markup(tmp_path, browser_factory):
    path = _deck(tmp_path)
    page = browser_factory(path)
    _go(page, 'insights')
    working = _download(page, tmp_path / 'working.html')
    shared = _download(page, tmp_path / 'shared.html', choice='Weitergabe ohne Notizen')
    for saved in (working, shared):
        text = saved.read_text()
        deck = text.split('id="sf-deck"', 1)[1].split('id="sf-document"', 1)[0]
        assert f'data-sf-slide="{DETAIL}" data-sf-deep-dive="Spitzen im Detail"' in deck
        assert f'data-sf-deep-dive-target="{DETAIL}"' in deck and f'data-sf-deep-dive-target="{SECOND}"' in deck
        assert 'role="button"' not in deck and 'data-sf-runtime' not in deck and 'Doppelklick' not in deck
        _cli('validate', saved)
    assert _json_script(working.read_text())['notes'][DETAIL] == 'Detailnotiz zum Deep Dive'
    assert _json_script(shared.read_text())['notes'][DETAIL] == ''
    reopened = browser_factory(shared)
    _go(reopened, 'insights')
    reopened.get_by_role('button', name='Details: Spitzen im Detail', exact=True).dblclick()
    expect(_overlay(reopened)).to_be_visible()

    # Helper: inspect, extract/replace, insert, reorder and new keep both attributes.
    report = json.loads(_cli('inspect', working).stdout)
    slides = {slide['id']: slide for slide in report['slides']}
    assert slides[DETAIL]['deepDive'] == 'Spitzen im Detail' and slides[SECOND]['deepDive'] == 'Deep Dive 1'
    assert slides['insights']['deepDiveTargets'] == [
        {'id': 'insights-panel-2', 'target': DETAIL}, {'id': 'insights-panel-3', 'target': SECOND}]
    assert 'deepDive' not in slides['insights'] and 'deepDiveTargets' not in slides['outlook']
    fragment = tmp_path / 'detail.html'
    _cli('extract-slide', working, '--slide', DETAIL, '--output', fragment)
    edited = tmp_path / 'edited.html'
    _cli('replace-slide', working, '--slide', DETAIL, '--fragment', fragment, '--output', edited)
    extra = tmp_path / 'extra.html'
    extra.write_text('<section class="sf-slide" data-sf-slide="third-detail" data-sf-deep-dive="Drittes Detail"></section>')
    _cli('insert-slide', edited, '--fragment', extra, '--output', edited)
    order = [slide['id'] for slide in json.loads(_cli('inspect', edited).stdout)['slides']]
    _cli('reorder', edited, '--order', ','.join(reversed(order)), '--output', edited)
    report = json.loads(_cli('inspect', edited).stdout)
    names = {slide['id']: slide.get('deepDive') for slide in report['slides']}
    assert names[DETAIL] == 'Spitzen im Detail' and names['third-detail'] == 'Drittes Detail'
    assert names[SECOND] == 'Deep Dive 4', 'default names count deep dives in the new order'
    assert '"valid": true' in _cli('validate', edited).stdout
    fresh = tmp_path / 'fresh.html'
    _cli('new', '--template', PACKAGE / 'assets/mbb.html', '--output', fresh, '--title', 'Neu')
    report = json.loads(_cli('inspect', fresh).stdout)
    assert [slide['id'] for slide in report['slides']][-1] == DETAIL
    assert report['slides'][-1]['deepDive'] == 'Spitzen im Detail'


@pytest.mark.parametrize('case', ['missing', 'not-deep-dive', 'nested', 'hidden'])
def test_validate_rejects_invalid_deep_dive_markup(tmp_path, case):
    source = _deck(tmp_path).read_text()
    if case == 'missing':
        source = source.replace(f'data-sf-deep-dive-target="{SECOND}"', 'data-sf-deep-dive-target="nowhere"', 1)
    elif case == 'not-deep-dive':
        source = source.replace(f'data-sf-deep-dive-target="{SECOND}"', 'data-sf-deep-dive-target="outlook"', 1)
    elif case == 'nested':
        source = source.replace('data-sf-id="orphan-title"', f'data-sf-id="orphan-title" data-sf-deep-dive-target="{DETAIL}"', 1)
    else:
        source = source.replace('data-sf-deep-dive="Reserve"', 'data-sf-deep-dive="Reserve" data-sf-hidden', 1)
    path = tmp_path / f'{case}.html'
    path.write_text(source)
    result = _cli('validate', path, success=False)
    report = json.loads(result.stdout)
    assert result.returncode == 1 and report['valid'] is False
    assert len(report['deepDiveErrors']) == 1
    error = report['deepDiveErrors'][0]['error']
    assert {'missing': 'missing', 'not-deep-dive': 'not a deep-dive', 'nested': 'no nesting', 'hidden': 'data-sf-hidden'}[case] in error
