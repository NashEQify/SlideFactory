"""Share copy: the save menu can drop owner/agent annotations without touching the working state."""
import json
import re

from playwright.sync_api import expect

from test_editor_e2e import _cli, _download, _edit, _notes_guidance, _ready, browser_factory


def _saved_meta(path):
    source = path.read_text(encoding='utf-8')
    return json.loads(re.search(r'<script id="sf-document" type="application/json">(.*?)</script>', source, re.S).group(1))


def test_share_copy_drops_notes_guidance_and_postits(tmp_path, browser_factory):
    page = browser_factory(_ready(tmp_path))
    _edit(page)
    _notes_guidance(page, 'PRIVATE_SPEAKER_NOTE', 'PRIVATE_AGENT_GUIDANCE')
    page.get_by_role('button', name='Post-it einfügen', exact=True).click()
    expect(page.locator('#sf-deck [data-sf-postit]')).to_have_count(1)

    shared = _download(page, tmp_path / 'shared.html', choice='Weitergabe ohne Notizen')
    expect(page.locator('#sf-save-state')).to_have_attribute('data-state', 'dirty')
    working = _download(page, tmp_path / 'working.html')

    text = shared.read_text(encoding='utf-8')
    for private in ['PRIVATE_SPEAKER_NOTE', 'PRIVATE_AGENT_GUIDANCE', 'Initial fixture notes', 'Initial fixture guidance']:
        assert private not in text
    meta = _saved_meta(shared)
    assert set(meta['notes'].values()) == {''}
    assert all(entry == {'text': '', 'status': 'open'} for entry in meta['guidance'].values())
    assert 'notesFormat' not in meta and 'notesProvenance' not in meta
    assert 'data-sf-postit=' not in text.split('id="sf-deck"', 1)[1].split('id="sf-document"', 1)[0]
    _cli('validate', shared)

    kept = _saved_meta(working)
    assert 'PRIVATE_SPEAKER_NOTE' in kept['notes'].values()
    assert any(entry['text'] == 'PRIVATE_AGENT_GUIDANCE' for entry in kept['guidance'].values())
    assert list(meta['notes']) == list(kept['notes'])

    reopened = browser_factory(shared)
    expect(reopened.locator('#sf-deck > [data-sf-slide]')).to_have_count(len(kept['notes']))
    expect(reopened.locator('#sf-deck [data-sf-id="qa-text"]')).to_have_text('Fixture alpha beta')
    _edit(reopened)
    reopened.get_by_role('button', name='Referentennotizen', exact=True).click()
    expect(reopened.get_by_role('textbox', name='Referentennotizen', exact=True)).to_have_text('')
