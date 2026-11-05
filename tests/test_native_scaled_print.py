"""Native print must not fragment a transformed, actually migrated flow layout."""
import os
from pathlib import Path
import re
import subprocess

from PIL import Image
from playwright.sync_api import expect
from test_editor_e2e import _download
from test_editor_e2e import browser_factory as browser_factory
from test_reference_migration import fixture_source, invoke


EVIDENCE = Path(os.environ.get('SF_SCALED_PRINT_EVIDENCE', '/tmp/slidefactory-scaled-print'))


def _migrated_flow_deck(tmp_path):
    source = fixture_source()
    # The migration fixture's deliberately invalid font is unsuitable for printing.
    source = re.sub(r'@font-face\{[^}]+\}', '', source)
    source = re.sub(r'<svg width="0".*?</svg>', '', source)
    image = re.search(r'<img src="([^"]+)"', source)[1]
    slides = ''.join(f'''<section class="slide {layout}" id="slide-{index}">
      <header><h1 data-edit-id="{layout}-header" data-edit-kind="text">{layout.upper()} HEADER</h1></header>
      <div class="flow-body"><p data-edit-id="{layout}-body" data-edit-kind="text">{layout.upper()} BODY</p><div class="flow-image"><img src="{image}" alt="{layout} body witness"></div></div>
      <footer data-edit-id="{layout}-footer" data-edit-kind="text">{layout.upper()} FOOTER</footer>
    </section>''' for index, layout in enumerate(('flex', 'grid'), 1))
    source = re.sub(r'<div id="stage">.*?</main></div>', '<div id="stage"><main>' + slides + '</main></div>', source, flags=re.S)
    source = source.replace('</style>', '''
      .slide{box-sizing:border-box;padding:64px;gap:24px;color:#fff;font:40px Arial}
      .slide.flex.active{display:flex;flex-direction:column}
      .slide.grid.active{display:grid;grid-template-rows:160px 1fr 120px;grid-template-columns:1fr}
      .slide header{height:160px;flex:none;background:crimson}
      .slide h1,.slide p{margin:24px}
      .flow-body{flex:1;min-height:0;display:flex;flex-direction:column;background:seagreen}
      .flow-image{flex:none;margin: auto 0 40px 80px;width:400px;height:200px}
      .flow-image img{width:100%;height:100%;object-fit:contain}
      .slide footer{height:120px;flex:none;background:goldenrod}
    </style>''')
    original = tmp_path / 'flow-reference.html'
    original.write_text(source)
    migrated = tmp_path / 'flow-migrated.html'
    invoke(original, migrated)
    assert original.read_text() == source
    return migrated


def _render(page, name, *, notes=False):
    pdf = EVIDENCE / f'{name}.pdf'
    page.pdf(path=str(pdf), prefer_css_page_size=True, print_background=True)
    info = subprocess.check_output(['pdfinfo', str(pdf)], text=True)
    subprocess.run(['pdftoppm', '-scale-to-x', '1600', '-scale-to-y', '-1', '-png', str(pdf), str(pdf.with_suffix(''))], check=True, capture_output=True)
    assert re.search(r'Pages:\s+2\b', info), info
    width, height = map(float, re.search(r'Page size:\s+([\d.]+) x ([\d.]+)', info).groups())
    expected = (210, 297) if notes else (320, 180)
    assert abs(width * 25.4 / 72 - expected[0]) < .2
    assert abs(height * 25.4 / 72 - expected[1]) < .2
    return subprocess.check_output(['pdftotext', '-layout', str(pdf), '-'], text=True)


def _flow_witnesses(name, text):
    for index, layout in enumerate(('FLEX', 'GRID'), 1):
        with Image.open(EVIDENCE / f'{name}-{index}.png') as image:
            # Original 1920x1080 coordinates mapped to the 1600x900 printed slide.
            for x, y, color in ((1000, 140, (220, 20, 60)), (1000, 600, (46, 139, 87)),
                                (300, 800, (68, 136, 187)), (1000, 960, (218, 165, 32))):
                pixel = image.convert('RGB').getpixel((round(x * 5 / 6), round(y * 5 / 6)))
                assert all(abs(a - b) < 4 for a, b in zip(pixel, color)), (name, layout, x, y, pixel, color)
        for region in ('HEADER', 'BODY', 'FOOTER'):
            assert f'{layout} {region}' in text, (name, layout, region)


def test_native_scaled_flow_survives_saved_handoff(tmp_path, browser_factory):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page = browser_factory(_migrated_flow_deck(tmp_path))
    page.context.set_offline(True)
    saved = _download(page, EVIDENCE / 'saved-flow.html')
    page = browser_factory(saved)
    page.context.set_offline(True)
    stage = page.locator('.sf-reference-stage').first
    assert stage.evaluate('e=>[e.offsetWidth,e.offsetHeight,getComputedStyle(e).transform]') == [1920, 1080, 'matrix(0.833333, 0, 0, 0.833333, 0, 0)']
    before = page.locator('#sf-document').text_content()
    for mode in ('slides', 'notes'):
        page.get_by_role('button', name='Drucken/PDF', exact=True).click()
        page.get_by_label('Inhalt', exact=True).select_option(mode)
        with page.expect_popup() as opened:
            page.get_by_role('button', name='Drucken', exact=True).click()
        popup = opened.value
        expect(popup.locator('html')).to_have_attribute('data-sf-print-ready', 'true', timeout=8000)
        text = _render(popup, f'dialog-{mode}', notes=mode == 'notes')
        if mode == 'slides':
            _flow_witnesses('dialog-slides', text)
        else:
            assert 'First' in text and 'Second rich note.' in text
            assert 'FLEX FOOTER' in text and 'GRID FOOTER' in text
        popup.close()
    assert page.locator('#sf-document').text_content() == before
    _flow_witnesses('native-flow', _render(page, 'native-flow'))
