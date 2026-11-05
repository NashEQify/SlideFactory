"""Task003 T11/T12: trusted old resources and exact outside-span preservation."""
import gzip
import json
from pathlib import Path
import re

import pytest
from playwright.sync_api import expect
from test_editor_e2e import _cli, _json_script, _set_json_script, _download, _edit, browser_factory, ROOT

CURRENT_EDITOR = json.loads((ROOT/'skills/slidefactory/assets/editor-releases.json').read_text())['current']

def _node(source, identity, tag):
    match=re.search(r'<'+tag+r'\b[^>]*\bid="'+identity+r'"[^>]*>([\s\S]*?)</'+tag+r'>',source)
    assert match
    return match[0],match[1]


def _legacy(tmp_path, crlf=False):
    source=gzip.decompress((ROOT/'tests/fixtures/editor-1.0.0.html.gz').read_bytes()).decode()
    meta=_json_script(source);meta['qaExtension']={'value':'preserve this exact whitespace', 'revision':meta['revision']}
    source=_set_json_script(source,meta)
    source=source.replace('</head>','<style id="qa-custom-style">/* keep exactly */ #sf-deck{outline:none}</style></head>',1)
    source='<script id="qa-custom-hook">/* preserve */ window.qaCustomHook=1;</script></body>'.join(source.rsplit('</body>',1))
    if crlf:source=source.replace('\n','\r\n')
    path=tmp_path/'old.html';path.write_bytes(source.encode());return path


def test_upgrade_actual_old_download_exact_preservation(tmp_path,browser_factory):
    original=_legacy(tmp_path,True);old=original.read_bytes();output=tmp_path/'upgraded.html'
    result=json.loads(_cli('upgrade-editor',original,'--output',output).stdout)
    assert original.read_bytes()==old;assert result['editorVersion']==CURRENT_EDITOR
    source=old.decode();upgraded=output.read_bytes().decode();restored=upgraded
    for identity,tag in [('sf-editor-styles','style'),('sf-runtime','script')]:
        restored=restored.replace(_node(upgraded,identity,tag)[1],_node(source,identity,tag)[1],1)
    restored=restored.replace(_node(upgraded,'sf-editor-manifest','script')[0],'',1)
    restored=restored.replace(json.dumps(_json_script(upgraded)['revision']),json.dumps(_json_script(source)['revision']),1)
    assert restored.encode()==old
    _cli('validate',output);page=browser_factory(output)
    expect(page.get_by_role('button',name='Drucken/PDF',exact=True)).to_be_visible()
    assert page.evaluate('qaCustomHook')==1
    page.get_by_role('button',name='Referentennotizen',exact=True).click()
    page.get_by_role('textbox',name='Referentennotizen',exact=True).fill('After upgrade')
    saved=_download(page,tmp_path/'saved.html');_cli('validate',saved);fresh=browser_factory(saved)
    assert _json_script(saved.read_text())['notes']['intro']=='After upgrade'
    expect(fresh.get_by_role('button',name='Drucken/PDF',exact=True)).to_be_visible()


@pytest.mark.parametrize('damage',['css','runtime','mixed','forged','unknown','malformed-version','duplicate','destination','same-source'])
def test_upgrade_rejects_untrusted_or_overwriting_input(tmp_path,damage):
    original=_legacy(tmp_path);source=original.read_text();output=tmp_path/'result.html'
    current=(ROOT/'skills/slidefactory/assets/blank.html').read_text()
    if damage=='css':source=source.replace(_node(source,'sf-editor-styles','style')[1],_node(source,'sf-editor-styles','style')[1]+' ',1)
    elif damage=='runtime':source=source.replace(_node(source,'sf-runtime','script')[1],_node(source,'sf-runtime','script')[1]+' ',1)
    elif damage=='mixed':source=source.replace(_node(source,'sf-runtime','script')[1],_node(current,'sf-runtime','script')[1],1)
    elif damage in {'forged','unknown'}:
        manifest=_node(current,'sf-editor-manifest','script')[0]
        if damage=='unknown':manifest=manifest.replace(CURRENT_EDITOR,'99.0.0')
        source=source.replace('<script id="sf-runtime">',manifest+'<script id="sf-runtime">',1)
    elif damage=='malformed-version':
        source=current.replace(f'\"editorVersion\": \"{CURRENT_EDITOR}\"','\"editorVersion\": []',1)
    elif damage=='duplicate':source=source.replace('</head>','<style id="sf-editor-styles"></style></head>',1)
    elif damage=='destination':output.write_text('Do not overwrite')
    elif damage=='same-source':output=original
    original.write_text(source);before=original.read_bytes();existing=output.read_bytes() if output.exists() else None
    _cli('upgrade-editor',original,'--output',output,success=False)
    assert original.read_bytes()==before
    if existing is None:assert not output.exists()
    else:assert output.read_bytes()==existing
    assert not list(tmp_path.glob('.*.tmp'))
