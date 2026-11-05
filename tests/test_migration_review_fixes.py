"""Focused regressions for live preview context and cold derived diagrams."""
import pytest
from playwright.sync_api import expect

from test_editor_e2e import _presenter_action
from test_editor_e2e import (
    PACKAGE, _download, _edit, _json_script, _meta, _set_json_script,
    _slide_spans, browser_factory,
)

pytestmark = pytest.mark.e2e


def _fixture(tmp_path, *, diagram=False):
    source = (PACKAGE / "assets" / "starter.html").read_text()
    spans = _slide_spans(source)
    ids = list(spans)
    metadata = _json_script(source)
    metadata["notes"][ids[0]] = "First original notes"
    metadata["notes"][ids[1]] = "Second original notes"
    source = _set_json_script(source, metadata)
    source = source.replace('<html lang="de">', '<html lang="de" style="--preview-color:#112233">', 1)
    source = source.replace('<body class="', '<body style="--preview-text:#334455" class="', 1)
    for index, (slide_id, span) in enumerate(spans.items()):
        probe = '<div class="palette-probe" style="position:absolute;left:30px;top:30px;width:100px;height:50px;background:var(--preview-color);color:var(--preview-text)">Palette</div>'
        if diagram and index == 1:
            probe += '<div id="cold-diagram" style="position:absolute;left:220px;top:220px;width:300px;height:180px"><div id="cold-node" style="position:absolute;left:20px;top:30px;width:100px;height:50px">Node</div></div>'
        source = source.replace(span, span.replace('>', '>' + probe, 1), 1)
    if diagram:
        hook = """document.addEventListener('sf:layout',event=>{
          const slide=event.target.closest('[data-sf-runtime-preview="true"]');
          const diagram=slide?.querySelector('#cold-diagram');if(!diagram)return;
          const rect=diagram.getBoundingClientRect();if(!rect.width||!rect.height)return;
          diagram.querySelector('svg')?.remove();
          const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
          svg.dataset.sfTransient='';svg.setAttribute('width','300');svg.setAttribute('height','180');
          const path=document.createElementNS(svg.namespaceURI,'path');path.id='cold-connector';
          path.setAttribute('d','M20 30 L220 130');path.setAttribute('stroke','#ff8800');
          svg.append(path);diagram.append(svg);
        });"""
    else:
        hook = """function syncReviewPalette(){
          const scheme=JSON.parse(document.getElementById('sf-document').textContent).colorScheme;
          document.documentElement.style.setProperty('--preview-color',scheme.endsWith('light')?'#ddee11':'#112233');
          document.body.style.setProperty('--preview-text',scheme.startsWith('indigo')?'#ff5566':'#334455');
        }
        document.addEventListener('sf:ready',syncReviewPalette);
        new MutationObserver(syncReviewPalette).observe(document.getElementById('sf-theme-tokens'),{childList:true,subtree:true,characterData:true});"""
    prefix, suffix = source.rsplit('</body>', 1)
    source = prefix + '<script>' + hook + '</script></body>' + suffix
    path = tmp_path / 'review-fix.html'
    path.write_text(source)
    return path, ids


def _popup(page):
    with page.expect_popup() as opened:
        _presenter_action(page)
    return opened.value


def test_live_palette_preview_and_owner_note_binding(tmp_path, browser_factory):
    path, ids = _fixture(tmp_path)
    page = browser_factory(path)
    _edit(page)
    page.get_by_role('button', name='Referentennotizen', exact=True).click()
    notes = page.get_by_role('textbox', name='Referentennotizen', exact=True)
    notes.fill('First direct contribution')
    popup = _popup(page)
    current = popup.frame_locator('#current-preview')
    following = popup.frame_locator('#next-preview')
    expect(current.locator('.palette-probe')).to_have_css('background-color', 'rgb(17, 34, 51)')
    expect(following.locator('.palette-probe')).to_have_css('color', 'rgb(51, 68, 85)')
    popup.get_by_role('button', name='Nächste Folie', exact=True).click()
    expect(notes).to_have_text('Second original notes')
    assert _meta(page)['notes'][ids[0]] == 'First direct contribution'
    notes.fill('Second owner contribution')
    expect(popup.get_by_role('region', name='Referentennotizen')).to_have_text('Second owner contribution')
    page.wait_for_function("document.querySelector('#sf-document').textContent.includes('Second owner contribution')")
    page.get_by_label('Farbschema', exact=True).select_option('indigo-light')
    expect(current.locator('.palette-probe')).to_have_css('background-color', 'rgb(221, 238, 17)')
    expect(following.locator('.palette-probe')).to_have_css('color', 'rgb(255, 85, 102)')
    saved = _download(page, tmp_path / 'review-saved.html')
    preserved = _json_script(saved.read_text())
    assert preserved['notes'][ids[0]] == 'First direct contribution'
    assert preserved['notes'][ids[1]] == 'Second owner contribution'


def test_cold_next_preview_prepares_transient_connectors(tmp_path, browser_factory):
    path, ids = _fixture(tmp_path, diagram=True)
    page = browser_factory(path)
    hidden = page.locator(f'#sf-deck > [data-sf-slide="{ids[1]}"]')
    original_style = hidden.get_attribute('style')
    popup = _popup(page)
    preview = popup.frame_locator('#next-preview')
    expect(preview.locator('#cold-connector')).to_be_visible()
    expect(hidden).to_be_hidden()
    assert hidden.get_attribute('style') == original_style
    assert hidden.get_attribute('data-sf-runtime-preview') is None
    assert hidden.get_attribute('data-sf-runtime-original-style') is None
    assert preview.locator(f'[data-sf-slide="{ids[1]}"]').get_attribute('style') == original_style
    _edit(page)
    expect(page.get_by_role('button', name='Rückgängig', exact=True)).to_be_disabled()
    saved = _download(page, tmp_path / 'cold-saved.html')
    html = saved.read_text()
    assert 'id="cold-connector"' not in html
    assert 'data-sf-runtime-preview="true"' not in _slide_spans(html)[ids[1]]
    assert _json_script(html)['notes'] == _json_script(path.read_text())['notes']


def test_source_read_before_context_observer_refreshes_both_presenter_views(tmp_path, browser_factory):
    path, ids = _fixture(tmp_path)
    source = path.read_text().replace('class="palette-probe"',
        'class="palette-probe" data-sf-id="context-probe" data-sf-kind="box"', 1)
    path.write_text(source)
    page = browser_factory(path)
    _edit(page)
    popup = _popup(page)
    current = popup.frame_locator('#current-preview').locator('.palette-probe')
    following = popup.frame_locator('#next-preview').locator('.palette-probe')
    expect(current).to_have_css('background-color', 'rgb(17, 34, 51)')
    expect(following).to_have_css('background-color', 'rgb(17, 34, 51)')
    # A synchronous authored layout hook runs before the shell's source read;
    # the MutationObserver notification is delivered only afterward.
    page.evaluate("""() => document.addEventListener('sf:layout', event => {
      if (event.detail.phase !== 'commit') return;
      document.documentElement.style.setProperty('--preview-color', '#aa2211');
      document.body.style.setProperty('--preview-text', '#117733');
    })""")
    page.locator('[data-sf-id="context-probe"]').click()
    page.keyboard.press('ArrowRight')
    expect(current).to_have_css('background-color', 'rgb(170, 34, 17)')
    expect(following).to_have_css('background-color', 'rgb(170, 34, 17)')
    expect(following).to_have_css('color', 'rgb(17, 119, 51)')
