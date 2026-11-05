"""Bounded conversion RED plan: public CLI + synthetic family, never private content.

Atomic rejects: unknown/already-native/same-path/malformed saved edits. Preservation:
ID-based notes despite reversed template order, inherited typography/global filters,
flow vs inline participation, originals/fonts, contain/cover/anisotropic frame crops,
and native script ownership. The browser is conversion-only optional tooling.
"""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/slidefactory/scripts/migrate_reference.py'
DECK = ROOT / 'skills/slidefactory/scripts/deck.py'
STARTER = ROOT / 'skills/slidefactory/assets/starter.html'
from test_editor_e2e import CHROMIUM


def invoke(source, output, success=True, *extra):
    result = subprocess.run([sys.executable, str(SCRIPT), str(source), '--output', str(output), *(['--chromium', CHROMIUM] if CHROMIUM else []), *extra], capture_output=True, text=True)
    assert (result.returncode == 0) == success, result.stderr
    assert 'Traceback' not in result.stderr
    return result


def fixture_source():
    # Real small PNG and embedded SVG originals are freely generated fixtures.
    import io
    from PIL import Image
    stream = io.BytesIO(); Image.new('RGB', (400, 200), '#4488bb').save(stream, format='PNG')
    image = 'data:image/png;base64,' + base64.b64encode(stream.getvalue()).decode()
    source = '''<!doctype html><html data-edit-document="fixture-doc"><head><meta charset="utf-8"><title>Fixture</title><style>
:root{--bg:#112233;--navy:#123456;--panel:#234567;--cyan:#44eeee;--blue:#5599dd;--teal:#228888;--purple:#bb88dd;--amber:#ddaa44;--muted:#bbccdd;--dim:#99aabb;--line:rgba(99,150,200,.3)}
@font-face{font-family:Fixture;src:url(data:font/woff2;base64,RklYVFVSRSBPTkxZ)}
body{margin:0;font-family:Georgia,serif}#stage{width:1920px;height:1080px;position:absolute;background:var(--bg)}
#stage>main{height:100%}.slide{position:absolute;inset:0;display:none;width:1920px;height:1080px}.slide.active{display:block}.body{padding:40px}
.grid{display:grid;grid-template-columns:200px 200px;gap:25px}.slot{width:200px;height:200px;position:relative;overflow:hidden}.slot img{width:100%;height:100%;object-fit:contain}.cover img{object-fit:cover}.stretch img{position:absolute;width:200%;height:250%;left:-50%;top:-25%;object-fit:fill}
#fixture-label{color:#fff;filter:url(#fixture-filter)}
</style></head><body><div class="theme-lab" id="theme-lab"><select id="theme-select"><option>old</option></select><input id="theme-color" type="color"></div>
<svg width="0" height="0"><defs><filter id="fixture-filter"><feColorMatrix type="saturate" values="1" /></filter></defs></svg>
<div id="stage"><main><section class="slide" id="slide-1" data-time="1.5"><div class="body"><h1 data-edit-id="s1-title" data-edit-kind="text">First <strong>emphasis</strong></h1><div class="grid" data-edit-id="s1-grid" data-edit-kind="box"><div class="slot" data-edit-id="s1-contain" data-edit-kind="box"><img src="IMAGE" alt="contain"></div><div class="slot cover" data-edit-id="s1-cover" data-edit-kind="box"><img src="IMAGE" alt="cover"></div></div><p data-edit-id="s1-flow" data-edit-kind="text">Flow <span id="fixture-label" data-edit-id="s1-inline" data-edit-kind="text">inline</span></p><svg data-edit-id="s1-icon" data-edit-kind="icon" width="20" height="20"><rect width="20" height="20" fill="#44eeee" /></svg></div></section>
<section class="slide" id="slide-2"><div class="body"><h1 data-edit-id="s2-title" data-edit-kind="text">Second</h1><div class="slot stretch" data-edit-id="s2-stretch" data-edit-kind="box"><img src="IMAGE" alt="stretch"></div></div></section></main></div>
<template id="note-2"><p>Second <strong>rich</strong> note.</p></template><template id="note-1"><p>First<br>line.</p><p>Last.</p></template>
<script>const legacyNotesId='synthetic-notes';window.legacyWriter=true;const deckId='synthetic-notes';window.deck={show(n){const slides=[...document.querySelectorAll('.slide')];slides.forEach((s,i)=>s.classList.toggle('active',i===n-1));},count:2};window.deck.show(1);</script></body></html>'''
    return source.replace('IMAGE', image)


@pytest.mark.integration
def test_atomic_rejections_before_output_write(tmp_path):
    output = tmp_path / 'prior.html'; output.write_text('previous work')
    for source in ('<html><head></head><body>unknown</body></html>', STARTER.read_text(), fixture_source().replace('id="stage"', 'id="other"'), fixture_source().replace('</head>', '<script id="editor-document-state" type="application/json">{"schema":1,"patches":{"missing":{"x":5}}}</script></head>')):
        path = tmp_path / 'source.html'; path.write_text(source)
        result = invoke(path, output, False)
        assert output.read_text() == 'previous work'
        assert any(term in result.stderr.lower() for term in ('family', 'native', 'embedded', 'state'))
    path.write_text(fixture_source()); before = path.read_bytes(); invoke(path, path, False)
    assert path.read_bytes() == before
    assert not list(tmp_path.glob('.*.tmp'))


@pytest.mark.integration
def test_conversion_preservation_and_canonical_image_frames(tmp_path):
    path = tmp_path / 'source.html'; path.write_text(fixture_source())
    output = tmp_path / 'native.html'; before = path.read_bytes()
    report = json.loads(invoke(path, output).stdout)
    result = subprocess.run([sys.executable, str(DECK), 'inspect', str(output)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    inspected = json.loads(result.stdout); slides = inspected['slides']
    assert [s['id'] for s in slides] == ['slide-1', 'slide-2']
    assert slides[0]['notes'] == 'First\nline.\n\nLast.'
    assert slides[1]['notes'] == 'Second rich note.'
    assert inspected['metadata']['notesProvenance']['slide-1'] == {'html':'<p>First<br>line.</p><p>Last.</p>', 'text':'First\nline.\n\nLast.'}
    objects = {obj['id']:obj for slide in slides for obj in slide['objects']}
    assert objects['s1-inline']['layout'] == 'inline'
    assert objects['s1-flow']['layout'] == 'flow'
    assert objects['s1-icon']['kind'] == 'box'
    assert objects['s1-contain']['original']['dimensions'] == [400, 200]
    assert objects['s1-contain']['geometry']['width'] == 200
    assert objects['s1-contain']['geometry']['height'] == 100
    assert objects['s1-cover']['crop'] == {'x': .25, 'y': 0, 'w': .5, 'h': 1}
    assert 'scaleY' in objects['s2-stretch']['geometry']['transform']
    assert report['witnesses']['legacyTargetsRetained'] == 9
    assert report['witnesses']['imagesRetained'] == 3
    assert report['witnesses']['notesRetained'] == 2
    assert report['originalSha256'] == hashlib.sha256(before).hexdigest()
    assert path.read_bytes() == before
    html = output.read_text()
    assert 'window.legacyWriter=true' not in html
    assert 'data:font/woff2;base64,RklYVFVSRSBPTkxZ' in html
    assert 'id="fixture-filter"' in html
    assert '<strong>emphasis</strong>' in html
    assert 'font-family:Georgia, serif' in html
    assert 'data-sf-duration="90"' in html


@pytest.mark.integration
def test_valid_embedded_edits_materialize_once_and_unknown_reference_rejects(tmp_path):
    state = {'schema':1,'documentId':'fixture-doc','revision':2,'baselines':{'s1-title':{'kind':'text','html':'Base','style':''},'s1-grid':{'kind':'box','html':None,'style':''}},'patches':{'s1-title':{'html':'Saved <strong>edit</strong>','x':12,'y':9,'styles':{},'hidden':False}},'added':[]}
    path = tmp_path/'saved.html'; output=tmp_path/'native.html'
    path.write_text(fixture_source().replace('</head>', f'<script id="editor-document-state" type="application/json">{json.dumps(state)}</script></head>'))
    invoke(path,output)
    result = subprocess.run([sys.executable,str(DECK),'inspect',str(output)],capture_output=True,text=True)
    assert 'Saved edit' in result.stdout
    assert 'editor-document-state' not in output.read_text()
    state['patches']['missing']={'x':5}; previous=output.read_bytes()
    path.write_text(fixture_source().replace('</head>', f'<script id="editor-document-state" type="application/json">{json.dumps(state)}</script></head>'))
    invoke(path,output,False); assert output.read_bytes()==previous


@pytest.mark.e2e
def test_live_hook_redraw_preserves_labels_and_requeries_restored_nodes(tmp_path):
    from playwright.sync_api import sync_playwright
    labels=''.join(f'<span class="{name}" data-edit-id="label-{index}" data-edit-kind="text" style="position:absolute">L{index}</span>' for index,name in enumerate(('tom-evidence','tom-transfer','tom-improve','tom-common-label')))
    layout='<div class="tom-layout" style="position:absolute;left:800px;top:400px;width:400px;height:200px">'+labels+'</div>'
    # A freely authored synthetic producer with the finite family's connector/
    # initial-placement phases. No private function is used as a fixture.
    producer='''function drawTom(){document.querySelectorAll('.slide.active .tom-layout').forEach(map=>{let svg=map.querySelector('.map-lines');if(!svg){svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.classList.add('map-lines');svg.setAttribute('aria-hidden','true');map.append(svg);}const origin=map.getBoundingClientRect(),scale=origin.width/map.clientWidth;const x=map.querySelector('.tom-evidence').getBoundingClientRect().left-origin.left;svg.innerHTML=`<path d="M0 0 L${x/scale} 40" stroke="#44eeee"/>`;const label=(cls,x,y,w)=>{const e=map.querySelector(cls);e.style.left=x+'px';e.style.top=y+'px';e.style.width=w+'px';};label('.tom-evidence',10,20,60);label('.tom-transfer',90,30,60);label('.tom-improve',170,40,60);label('.tom-common-label',250,50,60);});}drawTom();'''
    path=tmp_path/'live.html';output=tmp_path/'native.html'
    source=fixture_source().replace('<h1 data-edit-id="s1-title"',layout+'<h1 data-edit-id="s1-title"').replace('</body>','<script>'+producer+'</script></body>')
    path.write_text(source);invoke(path,output)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=CHROMIUM,headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1920,'height':1080});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(output.as_uri());page.wait_for_selector('#sf-editor',state='attached')
        page.wait_for_selector('.tom-layout .map-lines path')
        assert page.locator('[data-sf-id="label-0"]').evaluate('(e)=>e.style.left')=='10px'
        page.evaluate('''() => {const e=document.querySelector('[data-sf-id="label-0"]');e.style.left='77px';document.dispatchEvent(new CustomEvent('sf:layout',{detail:{slideId:'slide-1',elementId:'label-0',phase:'commit'}}));}''')
        page.wait_for_function("document.querySelector('.map-lines path').getAttribute('d').includes('77')")
        page.locator('[data-action="next"]').click();page.locator('[data-action="previous"]').click()
        assert page.locator('[data-sf-id="label-0"]').evaluate('(e)=>e.style.left')=='77px'
        page.evaluate('''() => {const map=document.querySelector('.tom-layout'),copy=map.cloneNode(true);copy.querySelector('.map-lines').remove();map.replaceWith(copy);document.dispatchEvent(new CustomEvent('sf:layout',{detail:{slideId:'slide-1',elementId:'label-0',phase:'undo'}}));}''')
        page.wait_for_selector('.tom-layout .map-lines path')
        assert page.locator('[data-sf-id="label-0"]').evaluate('(e)=>e.style.left')=='77px'
        assert not errors
        browser.close()
