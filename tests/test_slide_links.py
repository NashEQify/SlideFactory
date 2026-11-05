"""Real-browser slide links: insert, retarget, undo, reorder, jump history and saved handoff."""
import pytest
from playwright.sync_api import expect
from test_editor_e2e import browser_factory, PACKAGE, _edit, _drag, _download, _cli

pytestmark = pytest.mark.e2e


def _current(page):
    return page.evaluate('document.querySelector("#sf-deck > [data-sf-runtime-visible=\\"true\\"]").dataset.sfSlide')


def _ids(page):
    return page.evaluate('[...document.querySelectorAll("#sf-deck > [data-sf-slide]")].map(s=>s.dataset.sfSlide)')


def test_slide_link_lifecycle_and_return_jump(tmp_path, browser_factory):
    page = browser_factory(PACKAGE / 'assets/starter.html')
    ids = _ids(page)
    assert len(ids) >= 3
    origin, backup, other = ids[0], ids[-1], ids[1]
    _edit(page)
    page.get_by_role('button', name='Folienlink einfügen', exact=True).click()
    menu = page.locator('#sf-menu')
    expect(menu).to_be_visible()
    assert menu.locator('.sf-slide-targets button').count() == len(ids) - 1, 'current slide is no target'
    menu.locator('.sf-slide-targets button').last.click()
    link = page.locator(f'[data-sf-slide="{origin}"] a[data-sf-link]')
    expect(link).to_have_count(1)
    assert link.get_attribute('href') == f'#{backup}' and link.get_attribute('data-sf-kind') == 'text'
    assert link.evaluate('e=>getComputedStyle(e).borderTopStyle') == 'solid', 'template/editor look applies'
    # Retarget, undo, redo.
    page.get_by_role('button', name='Linkziel ändern', exact=True).click()
    expect(menu.locator(f'.sf-slide-targets button[aria-current="true"]')).to_have_count(1)
    generated = link.inner_text()
    menu.locator('.sf-slide-targets button').nth(0).click()
    assert link.get_attribute('href') == f'#{other}'
    assert link.inner_text() != generated, 'an untouched generated label follows the target'
    page.get_by_role('button', name='Rückgängig', exact=True).click()
    assert link.get_attribute('href') == f'#{backup}' and link.inner_text() == generated
    page.keyboard.press('Control+Shift+Z')
    assert link.get_attribute('href') == f'#{other}'
    page.get_by_role('button', name='Rückgängig', exact=True).click()
    assert link.get_attribute('href') == f'#{backup}'
    # Clicking in edit mode never navigates; dragging moves; label is editable text.
    before = link.evaluate('e=>e.style.left')
    _drag(page, link, -60, -20)
    assert link.evaluate('e=>e.style.left') != before and _current(page) == origin
    link.dblclick(); page.keyboard.press('Control+A'); page.keyboard.insert_text('Zum Backup'); link.press('Escape')
    expect(link).to_have_text('Zum Backup')
    assert _current(page) == origin
    # Delete key on the selected link object, then restore.
    link.click(); page.keyboard.press('Escape')
    link_id = link.get_attribute('data-sf-id')
    page.locator(f'[data-sf-id="{link_id}"]').focus(); page.keyboard.press('Delete')
    expect(link).to_have_count(0)
    page.get_by_role('button', name='Rückgängig', exact=True).click()
    expect(link).to_have_count(1)
    # Reordering the target keeps the link valid by ID.
    page.locator(f'#sf-thumbnail-list button[data-slide="{backup}"]').focus()
    page.keyboard.press('Alt+ArrowUp')
    assert _ids(page).index(backup) == len(ids) - 2
    page.get_by_role('button', name='Fertig', exact=True).click()
    expect(page.locator(f'[data-sf-slide="{origin}"]')).to_be_visible()
    chip = page.locator('#sf-return-jump')
    expect(chip).to_be_hidden()
    # Follow, page around normally, return with Backspace.
    link.click()
    assert _current(page) == backup
    expect(chip).to_be_visible(); expect(chip).to_have_text('↩ Zurück zu Folie 1')
    page.keyboard.press('ArrowRight')
    assert _current(page) == _ids(page)[_ids(page).index(backup) + 1], 'arrow navigation unaffected'
    page.keyboard.press('Backspace')
    assert _current(page) == origin
    expect(chip).to_be_hidden()
    # Follow again, return through the chip.
    link.click(); assert _current(page) == backup
    chip.get_by_role('button').click()
    assert _current(page) == origin
    # Manual return to the origin clears that entry.
    link.click(); page.keyboard.press('Home')
    assert _current(page) == origin
    expect(chip).to_be_hidden()
    # Saved handoff and fresh reopen.
    saved = _download(page, tmp_path / 'links-saved.html')
    report = _cli('validate', saved)
    assert '"valid": true' in report.stdout
    reopened = browser_factory(saved)
    again = reopened.locator(f'[data-sf-slide="{origin}"] a[data-sf-link]')
    expect(again).to_have_text('Zum Backup')
    assert again.get_attribute('href') == f'#{backup}'
    assert again.get_attribute('data-sf-runtime-broken') is None
    again.click()
    assert _current(reopened) == backup
    reopened.keyboard.press('Backspace')
    assert _current(reopened) == origin


def test_deleted_target_is_flagged_in_editor_and_by_validator(tmp_path, browser_factory):
    page = browser_factory(PACKAGE / 'assets/starter.html')
    ids = _ids(page)
    _edit(page)
    page.get_by_role('button', name='Folienlink einfügen', exact=True).click()
    page.locator('#sf-menu .sf-slide-targets button').last.click()
    link = page.locator('a[data-sf-link]')
    page.locator(f'#sf-thumbnail-list button[data-slide="{ids[-1]}"]').locator('xpath=../..').get_by_role('button', name=f'Folie {len(ids)} löschen').click()
    expect(link).to_have_attribute('data-sf-runtime-broken', '')
    saved = _download(page, tmp_path / 'broken.html')
    assert 'data-sf-runtime-broken=' not in saved.read_text()
    report = _cli('validate', saved, success=False)
    assert ids[-1] in report.stdout and '"valid": false' in report.stdout
    page.get_by_role('button', name='Rückgängig', exact=True).click()
    expect(link).not_to_have_attribute('data-sf-runtime-broken', '')
