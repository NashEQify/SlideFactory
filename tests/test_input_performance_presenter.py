"""Metadata typing must stay local; presenter keyboard and close are real UI paths."""
import pytest
from playwright.sync_api import expect
from test_editor_e2e import _presenter_action
from test_editor_e2e import (
    _ready, _edit, _meta, _download, _cli, _slide_ids, browser_factory,
)


def _count_clones(page):
    page.evaluate("""() => {
      window.qaDeckClones = 0;
      const original = Node.prototype.cloneNode;
      Node.prototype.cloneNode = function(...args) {
        if (this.id === 'sf-deck' && args[0]) window.qaDeckClones++;
        return original.apply(this,args);
      };
    }""")


def test_metadata_typing_avoids_deck_clones_and_preserves_mixed_history(tmp_path, browser_factory):
    path = _ready(tmp_path)
    page = browser_factory(path); _edit(page)
    first, second, *_ = _slide_ids(page)
    page.get_by_role('button', name='Kommentare', exact=True).click()
    field = page.get_by_label('Bearbeitungskommentar', exact=True)
    initial = field.input_value()
    _count_clones(page)
    field.press_sequentially(' direct contribution', delay=10)
    # An initial metadata checkpoint is allowed; each key must not clone the deck.
    assert page.evaluate('qaDeckClones') <= 1
    page.get_by_role('button', name='Nächste Folie', exact=True).click()
    expect(field).to_have_value('')
    field.fill('Second-slide contribution')
    page.get_by_role('button', name='Schließen', exact=True).click()
    page.get_by_label('Folie auswählen', exact=True).select_option(first)
    text = page.locator('[data-sf-id="qa-text"]')
    text.dblclick(); text.fill('Authored text between metadata edits'); text.press('Escape')
    page.get_by_role('button', name='Kommentare', exact=True).click()
    field.fill('Final first-slide contribution')
    page.get_by_role('button', name='Schließen', exact=True).click()
    page.get_by_role('button', name='Rückgängig', exact=True).click()
    assert _meta(page)['guidance'][first]['text'] == initial + ' direct contribution'
    expect(text).to_have_text('Authored text between metadata edits')
    page.get_by_role('button', name='Rückgängig', exact=True).click()
    expect(text).to_have_text('Fixture alpha beta')
    assert _meta(page)['guidance'][second]['text'] == 'Second-slide contribution'
    page.keyboard.press('Control+Shift+z')
    page.keyboard.press('Control+Shift+z')
    expect(text).to_have_text('Authored text between metadata edits')
    assert _meta(page)['guidance'][first]['text'] == 'Final first-slide contribution'
    saved = _download(page, tmp_path / 'metadata-saved.html'); _cli('validate', saved)
    fresh = browser_factory(saved)
    assert _meta(fresh)['guidance'][second]['text'] == 'Second-slide contribution'
    assert _meta(fresh)['guidance'][first]['text'] == 'Final first-slide contribution'


def test_authored_text_typing_avoids_deck_copies_and_keeps_local_undo(tmp_path, browser_factory):
    page = browser_factory(_ready(tmp_path)); _edit(page)
    text = page.locator('[data-sf-id="qa-text"]')
    text.dblclick()
    text.press('End')
    _count_clones(page)
    text.press_sequentially(' added locally', delay=10)
    assert page.evaluate('qaDeckClones') == 0
    text.press('Escape')
    page.get_by_role('button', name='Rückgängig', exact=True).click()
    expect(text).to_have_text('Fixture alpha beta')
    page.keyboard.press('Control+Shift+z')
    expect(text).to_have_text('Fixture alpha beta added locally')


def test_presenter_arrows_guard_native_select_and_visible_close(tmp_path, browser_factory):
    page = browser_factory(_ready(tmp_path)); ids = _slide_ids(page)
    page.evaluate("""() => {
      const original=window.open;window.qaOpenArguments=[];
      window.open=function(...args){qaOpenArguments.push(args);return original.apply(this,args)};
    }""")
    with page.expect_popup() as opened:
        _presenter_action(page)
    popup = opened.value
    expect(popup.get_by_label('Folie', exact=True)).to_have_value(ids[0])
    popup.locator('body').click(position={'x':5,'y':5}); popup.keyboard.press('ArrowRight')
    expect(popup.get_by_label('Folie', exact=True)).to_have_value(ids[1])
    expect(page.get_by_label('Folie auswählen', exact=True)).to_have_value(ids[1])
    popup.keyboard.press('ArrowLeft')
    expect(popup.get_by_label('Folie', exact=True)).to_have_value(ids[0])
    popup.keyboard.press('PageDown')
    expect(popup.get_by_label('Folie', exact=True)).to_have_value(ids[1])
    popup.keyboard.press('ArrowDown')
    expect(popup.get_by_label('Folie', exact=True)).to_have_value(ids[2])
    popup.keyboard.press('ArrowUp')
    expect(popup.get_by_label('Folie', exact=True)).to_have_value(ids[1])
    popup.keyboard.press('PageUp')
    expect(popup.get_by_label('Folie', exact=True)).to_have_value(ids[0])
    popup.keyboard.press('ArrowRight')
    expect(popup.get_by_label('Folie', exact=True)).to_have_value(ids[1])
    popup.keyboard.press('Control+ArrowRight')
    expect(popup.get_by_label('Folie', exact=True)).to_have_value(ids[1])
    expect(popup.get_by_role('textbox').and_(popup.locator(':not(#end-time)'))).to_have_count(0)  # only the meeting-end time input
    select = popup.get_by_label('Folie', exact=True)
    select.focus(); select.press('ArrowDown')
    expect(select).to_have_value(ids[2])
    select.select_option(ids[1])
    assert not page.evaluate("qaOpenArguments[0][2] || ''"), 'Presenter must use ordinary browser chrome'
    close = popup.get_by_role('button', name='Referentenansicht schließen', exact=True)
    expect(close).to_be_visible()
    with popup.expect_event('close'):
        close.click()
    assert not page.is_closed()
    with page.expect_popup() as reopened:
        _presenter_action(page)
    expect(reopened.value.get_by_label('Folie', exact=True)).to_have_value(ids[1])


def test_metadata_draft_reuses_deck_but_keeps_later_authored_edits(tmp_path, browser_factory):
    page = browser_factory(_ready(tmp_path)); _edit(page)
    first = _slide_ids(page)[0]
    page.get_by_role('button', name='Kommentare', exact=True).click()
    field = page.get_by_label('Bearbeitungskommentar', exact=True)
    field.fill('Warm draft')
    page.wait_for_function("Object.values(localStorage).some(value => value.includes('Warm draft'))")
    _count_clones(page)
    # Each pause is longer than draft flush, so debouncing alone cannot pass.
    field.press_sequentially('XYZ', delay=300)
    assert page.evaluate('qaDeckClones') == 0
    page.get_by_role('button', name='Schließen', exact=True).click()
    text = page.locator('[data-sf-id="qa-text"]')
    text.dblclick(); text.fill('Later authored edit must survive cached draft'); text.press('Escape')
    page.get_by_role('button', name='Referentennotizen', exact=True).click()
    page.get_by_role('textbox', name='Referentennotizen', exact=True).fill('Fresh metadata with later DOM')
    page.reload()
    expect(page.locator('[data-sf-id="qa-text"]')).to_have_text('Later authored edit must survive cached draft')
    assert _meta(page)['notes'][first] == 'Fresh metadata with later DOM'
    assert _meta(page)['guidance'][first]['text'] == 'Warm draftXYZ'


def test_queued_metadata_draft_does_not_capture_later_cancelled_gesture(tmp_path, browser_factory):
    page = browser_factory(_ready(tmp_path)); _edit(page)
    box = page.locator('[data-sf-id="qa-box"]')
    original_left = box.evaluate('node => node.style.left')
    page.get_by_role('button', name='Referentennotizen', exact=True).click()
    page.get_by_role('textbox', name='Referentennotizen', exact=True).fill('Queued metadata checkpoint')
    box.click()
    grip = page.get_by_label('Objekt verschieben', exact=True).bounding_box()
    x, y = grip['x'] + grip['width']/2, grip['y'] + grip['height']/2
    page.mouse.move(x, y); page.mouse.down(); page.mouse.move(x + 30, y + 15)
    assert box.evaluate('node => node.style.left') != original_left
    page.wait_for_timeout(550)
    # Only settled scopes may enter the published journal. A note checkpoint
    # must not sample the unrelated live drag, even after its flush timer runs.
    captured_box = page.evaluate("""() => Object.values(localStorage).some(raw => {
      try {return (JSON.parse(raw).changes || []).some(change => change.descriptor?.id === 'qa-box');}
      catch {return false;}
    })""")
    assert not captured_box
    page.keyboard.press('Escape'); page.mouse.up()
    assert box.evaluate('node => node.style.left') == original_left
    page.reload()
    assert page.locator('[data-sf-id="qa-box"]').evaluate('node => node.style.left') == original_left


def test_presenter_close_remains_available_after_owner_disconnect(tmp_path, browser_factory):
    page = browser_factory(_ready(tmp_path))
    with page.expect_popup() as opened:
        _presenter_action(page)
    popup = opened.value
    expect(popup.locator('#connection')).to_have_text('Mit Präsentation verbunden.')
    page.close()
    expect(popup.locator('#connection')).to_contain_text('beendet')
    close = popup.get_by_role('button', name='Referentenansicht schließen', exact=True)
    expect(close).to_be_enabled()
    # The popup closes during a native click; trigger it detached so the click itself cannot race the close.
    with popup.expect_event('close'):
        close.evaluate('button => setTimeout(() => button.click(), 0)')


@pytest.mark.parametrize('kind', ['notes', 'guidance'])
def test_metadata_literal_asset_markup_survives_draft(tmp_path, browser_factory, kind):
    page = browser_factory(_ready(tmp_path)); _edit(page)
    first = _slide_ids(page)[0]
    literal = 'Die Beschreibung darf data-sf-journal-asset="missing" und {"asset":"missing"} enthalten.'
    name = 'Referentennotizen' if kind == 'notes' else 'Kommentare'
    field = 'Referentennotizen' if kind == 'notes' else 'Bearbeitungskommentar'
    page.get_by_role('button', name=name, exact=True).click()
    page.get_by_role('textbox', name=field, exact=True).fill(literal)
    page.get_by_role('button', name=name, exact=True).click()
    page.wait_for_function("Object.values(localStorage).some(value => value.includes('Die Beschreibung darf'))", timeout=5000)
    page.reload()
    value = _meta(page)[kind][first]
    assert (value if kind == 'notes' else value['text']) == literal


@pytest.mark.parametrize('image', [
    '<img alt="placeholder" data-custom="retained">',
    '<img alt="opaque GIF" src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7">',
])
def test_opaque_text_image_markup_survives_local_undo_and_draft(tmp_path, browser_factory, image):
    path = _ready(tmp_path)
    source = path.read_text().replace('>Fixture alpha beta</p>', '>' + image + 'Fixture alpha beta</p>')
    path.write_text(source)
    # This deliberately probes opaque markup accepted by the browser document
    # validator. The authoring helper has a stricter supported-image boundary.
    page = browser_factory(path); _edit(page)
    target = page.locator('[data-sf-id="qa-text"]'); original = target.inner_html()
    target.dblclick(); target.fill('Replacement text'); target.press('Escape')
    page.get_by_role('button', name='Rückgängig', exact=True).click()
    assert target.inner_html() == original
    page.reload()
    assert page.locator('[data-sf-id="qa-text"]').inner_html() == original
