"""Public font-size UI, independent undo and complete-file handoff."""
import pytest
from playwright.sync_api import expect
from test_editor_e2e import _ready, _edit, _download, _cli, browser_factory

# Size applies to the text range (inline spans); measure the first rendered text.
TEXT_SIZE="n=>{const w=document.createTreeWalker(n,NodeFilter.SHOW_TEXT);while(w.nextNode())if(w.currentNode.textContent.trim())return getComputedStyle(w.currentNode.parentElement).fontSize;return getComputedStyle(n).fontSize}"

@pytest.mark.parametrize('template',['consulting.html','editorial.html','mbb.html'])
def test_font_size_entry_buttons_history_and_handoff(tmp_path,browser_factory,template):
    path=_ready(tmp_path,template)
    source=path.read_text().replace('>Fixture alpha beta</p>','>Fixture <em>alpha</em> beta</p>')
    path.write_text(source)
    page=browser_factory(path);_edit(page)
    target=page.locator('[data-sf-id="qa-text"]');target.click()
    size=page.get_by_role('combobox',name='Schriftgröße',exact=True)
    # Point sizes are a preset dropdown with stepping buttons (no free entry).
    # CSSOM property edits normalize spacing; compare all authored declarations,
    # including priorities and ordering, rather than attribute whitespace.
    expect(size).to_be_visible();original=target.evaluate('n=>n.style.cssText');markup=target.inner_html()
    page.keyboard.press('Escape');size.select_option('24');assert target.evaluate(TEXT_SIZE)=='32px'
    page.get_by_role('button',name='Schrift vergrößern',exact=True).click();expect(size).to_have_value('26')
    page.get_by_role('button',name='Schrift verkleinern',exact=True).click();expect(size).to_have_value('24')
    assert target.locator('em').inner_text()=='alpha' and target.inner_text()=='Fixture alpha beta', 'range sizing keeps content and emphasis'
    page.get_by_role('button',name='Rückgängig',exact=True).click();assert target.evaluate(TEXT_SIZE)=='34.6667px'
    page.get_by_role('button',name='Rückgängig',exact=True).click();assert target.evaluate(TEXT_SIZE)=='32px'
    page.get_by_role('button',name='Rückgängig',exact=True).click();assert target.evaluate('n=>n.style.cssText')==original
    target.click();page.keyboard.press('Escape');size.select_option('18');assert target.evaluate(TEXT_SIZE)=='24px'
    saved=_download(page,tmp_path/'font-saved.html');_cli('validate',saved)
    fresh=browser_factory(saved);assert fresh.locator('[data-sf-id="qa-text"]').evaluate(TEXT_SIZE)=='24px'
    assert fresh.locator('[data-sf-id="qa-text"] em').inner_text()=='alpha'
