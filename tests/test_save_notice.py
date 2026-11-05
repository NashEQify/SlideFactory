"""Persistent, honest file-handoff notice through public offline editor flows."""
import pytest
from playwright.sync_api import expect

from test_editor_e2e import _presenter_action
from test_editor_e2e import _download, _edit, _meta, _ready, browser_factory


def _notice(page, state):
    notice = page.locator('#sf-save-state')
    expect(notice).to_be_visible()
    expect(notice).to_have_attribute('data-state', state)
    return notice


def _guidance(page, text):
    page.get_by_role('button', name='Kommentare', exact=True).click()
    field = page.get_by_label('Bearbeitungskommentar', exact=True)
    # Check in the same browser turn: typing has not yet committed its journal.
    immediate = field.evaluate("""(field, text) => {
      field.value = text;
      field.dispatchEvent(new InputEvent('input', {bubbles:true, inputType:'insertText'}));
      return document.getElementById('sf-save-state')?.dataset.state;
    }""", text)
    assert immediate == 'dirty'
    return field


def test_notice_live_edit_done_navigation_and_real_download(tmp_path, browser_factory):
    page = browser_factory(_ready(tmp_path))
    expect(_notice(page, 'file')).to_have_text('Dateistand geöffnet')
    _edit(page)
    _guidance(page, 'Latest offline guidance')
    expect(_notice(page, 'dirty')).to_contain_text('Ungespeicherte Änderungen')
    page.get_by_role('button', name='Fertig', exact=True).click()
    page.get_by_role('button', name='Nächste Folie', exact=True).click()
    _notice(page, 'dirty')
    saved = _download(page, tmp_path / 'notice-handoff.html')
    expect(_notice(page, 'download')).to_have_text('HTML-Download gestartet · Neue Datei verwenden')
    page.get_by_role('button', name='Vorherige Folie', exact=True).click()
    _notice(page, 'download')
    fresh = browser_factory(saved)
    _notice(fresh, 'file')
    assert _meta(fresh)['guidance']['intro']['text'] == 'Latest offline guidance'
    _edit(page)
    _guidance(page, 'Next unsaved contribution')
    page.get_by_role('button', name='Rückgängig', exact=True).click()
    # Conservative notice: Undo does not compare or hash the complete deck.
    _notice(page, 'dirty')


@pytest.mark.parametrize('invalid', [False, True])
def test_recovery_dirty_but_discarded_invalid_draft_is_file_state(tmp_path, browser_factory, invalid):
    page = browser_factory(_ready(tmp_path))
    initial = _meta(page)['guidance']['intro']['text']
    _edit(page)
    _guidance(page, 'Recovered contribution')
    page.get_by_role('button', name='Fertig', exact=True).click()
    page.wait_for_function("""() => {
      const meta = JSON.parse(document.getElementById('sf-document').textContent);
      return !!JSON.parse(localStorage.getItem('slidefactory:' + meta.deckId) || 'null')?.head;
    }""")
    if invalid:
        page.evaluate("""() => {
          const meta = JSON.parse(document.getElementById('sf-document').textContent);
          const key = 'slidefactory:' + meta.deckId, head = JSON.parse(localStorage.getItem(key));
          head.head = 'missing-entry'; localStorage.setItem(key, JSON.stringify(head));
        }""")
    else:
        # Recovery remains unsaved even if later draft persistence fails.
        page.add_init_script("Storage.prototype.setItem = () => {throw new DOMException('quota fault', 'QuotaExceededError')}")
    page.reload()
    _notice(page, 'file' if invalid else 'dirty')
    assert _meta(page)['guidance']['intro']['text'] == (initial if invalid else 'Recovered contribution')
    if not invalid:
        _edit(page)
        page.get_by_label('Farbschema', exact=True).select_option('indigo-light')
        page.get_by_role('button', name='Fertig', exact=True).click()
        expect(page.get_by_role('alert')).to_be_visible()
        _notice(page, 'dirty')


def test_export_failure_keeps_unsaved_notice(tmp_path, browser_factory):
    page = browser_factory(_ready(tmp_path))
    _edit(page)
    _guidance(page, 'Keep unsaved on failure')
    page.evaluate("() => {URL.createObjectURL = () => {throw new Error('Synthetic export failure')};}")
    page.get_by_role('button', name='HTML speichern', exact=True).click()
    page.get_by_role('button', name='Arbeitsstand mit Notizen', exact=True).click()
    _notice(page, 'dirty')
    expect(page.get_by_role('alert')).to_have_text('Synthetic export failure')


def test_owner_notes_and_palette_renew_notice_with_presenter_open(tmp_path, browser_factory):
    page = browser_factory(_ready(tmp_path))
    _edit(page)
    _download(page, tmp_path / 'before-palette.html')
    page.get_by_label('Farbschema', exact=True).select_option('indigo-light')
    _notice(page, 'dirty')
    _download(page, tmp_path / 'before-presenter.html')
    with page.expect_popup() as opened:
        _presenter_action(page)
    popup = opened.value
    expect(popup.locator('#connection')).to_have_text('Mit Präsentation verbunden.')
    _notice(page, 'download')
    expect(popup.get_by_role('textbox').and_(popup.locator(':not(#end-time)'))).to_have_count(0)  # only the meeting-end time input
    page.get_by_role('button', name='Referentennotizen', exact=True).click()
    field = page.get_by_role('textbox', name='Referentennotizen', exact=True)
    field.fill('Owner contribution')
    field.blur()
    expect(popup.get_by_role('region', name='Referentennotizen')).to_have_text('Owner contribution')
    _notice(page, 'dirty')
    popup.close()
    _notice(page, 'dirty')
