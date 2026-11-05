"""Task003 T1–T10: neutral real file handoffs, UI, and owner transactions."""
import importlib.util
import json
from pathlib import Path

import pytest
from playwright.sync_api import expect
from test_editor_e2e import _click_closing, _presenter_action
from test_editor_e2e import _ready, _edit, _meta, _slide_ids, _download, _cli, _set_json_script, browser_factory, ROOT


def _select(field, start=0, end=None):
    field.evaluate("""(node, positions) => {
      node.focus();const walker=document.createTreeWalker(node,NodeFilter.SHOW_TEXT),nodes=[];
      while(walker.nextNode())nodes.push(walker.currentNode);
      const locate=offset=>{for(const text of nodes){if(offset<=text.length)return [text,offset];offset-=text.length;}return [node,node.childNodes.length];};
      const [a,b]=locate(positions[0]),[c,d]=locate(positions[1]??node.textContent.length),range=document.createRange();range.setStart(a,b);range.setEnd(c,d);getSelection().removeAllRanges();getSelection().addRange(range);
    }""", [start, end])


def _notes(page):
    page.get_by_role('button', name='Referentennotizen', exact=True).click()
    return page.get_by_role('textbox', name='Referentennotizen', exact=True)


def test_shared_note_vectors_and_strict_python_validator(tmp_path, browser_factory):
    page = browser_factory(_ready(tmp_path))
    code = (ROOT / 'src/editor/notes.js').read_text().split('function createNotesEditor')[0]
    vectors = json.loads((ROOT / 'tests/notes_vectors.json').read_text())
    for vector in vectors:
        if vector.get('invalid'):
            result = page.evaluate('(source)=>{' + code + ';try{createNotesCodec(document).validate({version:1,html:source,text:"A"});return false;}catch{return true;}}', vector['html'])
            assert result
            continue
        result = page.evaluate('(source)=>{' + code + ';return createNotesCodec(document).sanitize(source);}', vector['html'])
        assert result == {'version': 1, 'html': vector['canonical'], 'text': vector['text']}
        path = _ready(tmp_path, filename='codec.html'); source = path.read_text(); meta = _meta(page)
        first = next(iter(meta['notes'])); meta['notesFormat'] = {first: result}; meta['notes'][first] = result['text']
        path.write_text(_set_json_script(source, meta)); _cli('validate', path)
    for html in ['<p><ul><li>A</li></ul></p>', '<p onclick="x()">A</p>', '<p><span style="font-size:73pt">A</span></p>']:
        meta['notesFormat'][first] = {'version': 1, 'html': html, 'text': 'A'}
        path.write_text(_set_json_script(source, meta)); _cli('validate', path, success=False)


def test_rich_notes_all_consumers_and_real_handoff(tmp_path, browser_factory):
    page=browser_factory(_ready(tmp_path)); _edit(page); first=_slide_ids(page)[0]
    field=_notes(page); field.fill('Alpha beta gamma'); field.blur()
    _select(field,0,5); page.get_by_role('button',name='Notizen fett',exact=True).click()
    assert '<strong>Alpha</strong>' in _meta(page)['notesFormat'][first]['html']
    _select(field,6,10); page.get_by_role('button',name='Notizen kursiv',exact=True).click()
    _select(field,11,16); page.get_by_label('Notizschriftgröße',exact=True).select_option('24')
    pair=_meta(page)['notesFormat'][first]; assert pair['text']=='Alpha beta gamma'; assert 'font-size:24pt' in pair['html']
    page.get_by_role('button',name='Rückgängig',exact=True).click(); assert '24pt' not in _meta(page)['notesFormat'][first]['html']
    page.keyboard.press('Control+Shift+z')
    with page.expect_popup() as opened: _presenter_action(page)
    popup=opened.value; note=popup.get_by_role('region',name='Referentennotizen',exact=True)
    expect(note).to_have_text('Alpha beta gamma'); expect(note.locator('strong')).to_have_text('Alpha'); _select(field)
    expect(popup.get_by_role('textbox').and_(popup.locator(':not(#end-time)'))).to_have_count(0)  # only the meeting-end time input
    page.locator('#sf-note-tools').get_by_role('button',name='Nummerierte Liste',exact=True).click()
    page.wait_for_function("id=>JSON.parse(document.querySelector('#sf-document').textContent).notesFormat[id].html.includes('<ol>')",arg=first)
    expect(note.locator('ol')).to_have_count(1)
    field.press('Control+z'); page.wait_for_function("id=>!JSON.parse(document.querySelector('#sf-document').textContent).notesFormat[id].html.includes('<ol>')",arg=first)
    with popup.expect_event('close'):
        _click_closing(popup.get_by_role('button',name='Referentenansicht schließen',exact=True))
    saved=_download(page,tmp_path/'rich-saved.html'); _cli('validate',saved)
    _cli('set-text',saved,'--element','qa-text','--text','Next agent edit')
    fresh=browser_factory(saved); assert _meta(fresh)['notesFormat'][first]==pair
    assert json.loads(_cli('inspect',saved,'--slide',first).stdout)['slide']['notesFormat']==pair


def test_immediate_notes_and_hostile_paste(tmp_path,browser_factory):
    page=browser_factory(_ready(tmp_path));ids=_slide_ids(page);field=_notes(page)
    field.fill('Preserve format');field.blur();_select(field);page.get_by_role('button',name='Notizen fett',exact=True).click()
    field.evaluate('''node=>{node.focus();const clipboardData=new DataTransfer();clipboardData.setData('text/html','<p onclick="alert(1)"><b>Safe</b><img src=x onerror=alert(1)><script>alert(1)</script></p>');node.dispatchEvent(new ClipboardEvent('paste',{bubbles:true,cancelable:true,clipboardData}));}''')
    field.blur();value=_meta(page)['notesFormat'][ids[0]];assert 'script' not in value['html'];assert 'onclick' not in value['html'];assert '<strong>Safe</strong>' in value['html']
    saved=_download(page,tmp_path/'paste.html');_cli('validate',saved)


def _print(page, notes=False):
    page.get_by_role('button',name='Drucken/PDF',exact=True).click()
    page.get_by_label('Inhalt',exact=True).select_option('notes' if notes else 'slides')
    with page.expect_popup() as opened:
        page.get_by_role('button',name='Drucken',exact=True).click()
    popup=opened.value
    expect(popup.locator('html')).to_have_attribute('data-sf-print-ready','true',timeout=20000)
    return popup


@pytest.mark.parametrize('design,scheme', [('consulting.html','cyan-dark'),('editorial.html','cyan-light')])
def test_actual_pdf_complete_slides_and_flowing_notes(tmp_path,browser_factory,design,scheme):
    import subprocess
    path=_ready(tmp_path,name=design);source=path.read_text();meta=json.loads(_cli('inspect',path).stdout)['metadata'];first=list(meta['notes'])[0]
    meta['colorScheme']=scheme
    long='A long note continues across pages. '*900+' LAST_NOTE_WITNESS'
    meta['notes'][first]=long
    meta['notesFormat']={first:{'version':1,'text':long,'html':'<ul><li><span style="font-size:18pt">'+long+'</span></li></ul>'}}
    source=_set_json_script(source,meta)
    source='''<script>document.addEventListener('sf:layout',event=>{if(event.detail.waitUntil){event.detail.waitUntil(new Promise(resolve=>setTimeout(()=>{const slide=event.target;let marker=slide.querySelector('.qa-async-print');if(!marker){marker=document.createElementNS('http://www.w3.org/2000/svg','svg');marker.classList.add('qa-async-print');marker.setAttribute('style','position:absolute;left:1100px;top:40px;width:450px;height:60px');marker.innerHTML='<text x="5" y="40" font-size="22" fill="red">ASYNC_PRINT_WITNESS</text>';slide.append(marker);}resolve();},100)));}});</script></body>'''.join(source.rsplit('</body>',1))
    path.write_text(source);page=browser_factory(path);_edit(page);revision=_meta(page)['revision'];before=page.locator('#sf-save-state').text_content()
    evidence=Path('/tmp/slidefactory-task003-pdf');evidence.mkdir(exist_ok=True)
    for notes in [False,True]:
        popup=_print(page,notes);mode='notes' if notes else 'slides';pdf=evidence/f'{Path(design).stem}-{mode}.pdf'
        popup.pdf(path=str(pdf),prefer_css_page_size=True,print_background=True)
        info=subprocess.run(['pdfinfo',str(pdf)],capture_output=True,text=True,check=True).stdout
        extracted=subprocess.run(['pdftotext','-layout',str(pdf),'-'],capture_output=True,text=True,check=True).stdout
        pages=int(next(line.split(':')[1] for line in info.splitlines() if line.startswith('Pages:')))
        assert pages==len(_slide_ids(page)) if not notes else pages>len(_slide_ids(page))
        assert 'ASYNC_PRINT_WITNESS' in extracted
        assert 'Initial fixture guidance' not in extracted
        assert 'HTML speichern' not in extracted
        if notes:assert 'LAST_NOTE_WITNESS' in extracted
        subprocess.run(['pdftoppm','-f','1','-singlefile','-scale-to','1600','-png',str(pdf),str(pdf.with_suffix(''))],check=True,capture_output=True)
        popup.close()
        assert _meta(page)['revision']==revision;assert page.locator('#sf-save-state').text_content()==before
    assert page.locator('[data-sf-runtime-preview]').count()==0


def test_print_failure_restores_hidden_slide_and_save_notice(tmp_path,browser_factory):
    page=browser_factory(_ready(tmp_path));_edit(page);ids=_slide_ids(page)
    hidden=page.locator(f'[data-sf-slide="{ids[1]}"]');style=hidden.get_attribute('style');notice=page.locator('#sf-save-state').text_content()
    page.evaluate("""()=>document.addEventListener('sf:layout',event=>{if(event.detail.waitUntil&&event.detail.slideId!==document.querySelector('[data-sf-slide]').dataset.sfSlide)event.detail.waitUntil(Promise.reject(Error('Synthetic rejected layout')));})""")
    page.get_by_role('button',name='Drucken/PDF',exact=True).click()
    with page.expect_popup() as opened:page.get_by_role('button',name='Drucken',exact=True).click()
    popup=opened.value
    expect(page.get_by_role('alert')).to_contain_text('Synthetic rejected layout')
    expect(popup.get_by_role('alert')).to_contain_text('fehlgeschlagen')
    assert hidden.get_attribute('style')==style;assert page.locator('#sf-save-state').text_content()==notice


def test_owner_format_refreshes_read_only_presenter_without_losing_next_input(tmp_path,browser_factory):
    page=browser_factory(_ready(tmp_path));_edit(page);first=_slide_ids(page)[0];field=_notes(page)
    field.fill('Alpha beta');field.blur()
    with page.expect_popup() as opened:_presenter_action(page)
    popup=opened.value;note=popup.get_by_role('region',name='Referentennotizen',exact=True)
    _select(field);page.get_by_role('button',name='Notizen fett',exact=True).click()
    expect(note.locator('strong')).to_have_text('Alpha beta')
    field.press('End');field.press_sequentially('!');field.blur()
    assert '<strong>' in _meta(page)['notesFormat'][first]['html']
    assert _meta(page)['notes'][first]=='Alpha beta!'
    expect(note).to_have_text('Alpha beta!')


def test_slide_transactions_history_recovery_and_file_handoff(tmp_path,browser_factory):
    path=_ready(tmp_path);source=path.read_text();meta=json.loads(_cli('inspect',path).stdout)['metadata'];first=list(meta['notes'])[0]
    meta['notesFormat']={first:{'version':1,'text':meta['notes'][first],'html':'<p><strong>'+meta['notes'][first]+'</strong></p>'}}
    meta['notesProvenance']={first:{'text':'Archived','html':'<p>Archived</p>'}}
    path.write_text(_set_json_script(source,meta));page=browser_factory(path);_edit(page);ids=_slide_ids(page)
    page.evaluate("window.qaUntouched=document.querySelectorAll('[data-sf-slide]')[1]")
    with page.expect_popup() as opened:_presenter_action(page)
    popup=opened.value
    page.get_by_role('button',name='Folie 1',exact=True).press('Alt+ArrowDown')
    assert _slide_ids(page)==[ids[1],ids[0],*ids[2:]]
    expect(page.get_by_label('Folie auswählen',exact=True)).to_have_value(first)
    expect(popup.get_by_label('Folie',exact=True)).to_have_value(first)
    page.get_by_role('button',name='Folie 2 löschen',exact=True).click()
    assert first not in _slide_ids(page);assert first not in _meta(page)['notes'];assert first not in _meta(page)['notesFormat']
    expect(popup.get_by_label('Folie',exact=True)).to_have_value(ids[2])
    page.get_by_role('button',name='Rückgängig',exact=True).click()
    assert _meta(page)['notesFormat'][first]==meta['notesFormat'][first]
    assert _meta(page)['notesProvenance'][first]==meta['notesProvenance'][first]
    page.get_by_role('button',name='Rückgängig',exact=True).click();assert _slide_ids(page)==ids
    page.keyboard.press('Control+Shift+z');page.keyboard.press('Control+Shift+z')
    assert page.evaluate("window.qaUntouched===document.querySelector('[data-sf-slide]')")
    page.reload();expect(page.get_by_role('button',name='Bearbeiten',exact=True)).to_be_visible();assert first not in _slide_ids(page)
    saved=_download(page,tmp_path/'slides-saved.html');_cli('validate',saved);fresh=browser_factory(saved)
    assert _slide_ids(fresh)==[ids[1],*ids[2:]];assert _meta(fresh)['qaExtension']==meta['qaExtension']
    _edit(fresh)
    while len(_slide_ids(fresh))>1:fresh.get_by_role('button',name='Folie 1 löschen',exact=True).click()
    expect(fresh.get_by_role('button',name='Folie 1 löschen',exact=True)).to_be_disabled()


def test_reorder_is_anchor_only_and_checkpoint_restores_deleted_contribution(tmp_path,browser_factory):
    page=browser_factory(_ready(tmp_path));_edit(page);ids=_slide_ids(page)
    field=_notes(page);field.fill('Contribution before structure');field.blur()
    page.get_by_role('button',name='Referentennotizen',exact=True).click()
    page.get_by_role('button',name='Folie 1',exact=True).press('Alt+ArrowDown')
    page.wait_for_timeout(350)
    entries=page.evaluate("()=>Object.values(localStorage).map(raw=>{try{return JSON.parse(raw)}catch{return null}}).filter(value=>value?.changes)")
    scopes=[c for entry in entries for c in entry['changes'] if c['descriptor']['kind']=='slide-order']
    assert scopes and all(set(c['after'])=={'beforeId','afterId'} for c in scopes)
    page.get_by_role('button',name='Folie 2 löschen',exact=True).click();assert ids[0] not in _slide_ids(page)
    page.get_by_role('button',name='Rückgängig',exact=True).click();assert _slide_ids(page)==[ids[1],ids[0],*ids[2:]]
    for _ in range(65):
        page.get_by_role('button',name='Folie 1',exact=True).press('Alt+ArrowDown')
        page.get_by_role('button',name='Folie 2',exact=True).press('Alt+ArrowUp')
    # Checkpoints are built in idle-time chunks; wait for the condition, not a fixed delay.
    page.wait_for_function("Object.values(localStorage).some(raw=>{try{return JSON.parse(raw).checkpoint===true}catch{return false}})",timeout=10000)
    Path('/tmp/task003-slide-checkpoint.json').write_text(json.dumps(page.evaluate('Object.fromEntries(Object.entries(localStorage))'),indent=2))
    assert _slide_ids(page)==[ids[1],ids[0],*ids[2:]]
    page.reload();expect(page.get_by_role('button',name='Bearbeiten',exact=True)).to_be_visible()
    assert 'verworfen' not in page.get_by_role('status').text_content()
    assert _meta(page)['notes'][ids[0]]=='Contribution before structure'
    assert _slide_ids(page)==[ids[1],ids[0],*ids[2:]]


def test_print_dialog_ranges_notes_only_and_immediate_notes(tmp_path,browser_factory):
    page=browser_factory(_ready(tmp_path));ids=_slide_ids(page)
    field=_notes(page);field.fill('FIRST_NOTE_ONLY');field.blur()
    page.get_by_label('Folie auswählen',exact=True).select_option(ids[1]);field.fill('EXCLUDED_SECOND');field.blur()
    page.get_by_label('Folie auswählen',exact=True).select_option(ids[2]);field.fill('THIRD_NOTE_ONLY');field.blur()
    expect(page.get_by_role('button',name='Bearbeiten',exact=True)).to_be_visible()
    assert page.get_by_role('button',name='Notizen exportieren',exact=True).count()==0
    page.get_by_role('button',name='Drucken/PDF',exact=True).click()
    page.get_by_label('Inhalt',exact=True).select_option('only-notes')
    ranges=page.get_by_label('Folien (leer = alle)',exact=True)
    for invalid in ['0','4','2-1','1,x']:
        ranges.fill(invalid);page.get_by_role('button',name='Drucken',exact=True).click();expect(page.locator('#sf-print-error')).not_to_be_empty()
        expect(page.get_by_role('dialog')).to_be_visible()
    ranges.fill('1,3-3')
    with page.expect_popup() as opened:page.get_by_role('button',name='Drucken',exact=True).click()
    popup=opened.value;expect(popup.locator('html')).to_have_attribute('data-sf-print-ready','true')
    expect(popup.locator('iframe,img,svg')).to_have_count(0)
    expect(popup.locator('.sf-print-page')).to_have_count(2)
    expect(popup.locator('body')).to_contain_text('FIRST_NOTE_ONLY');expect(popup.locator('body')).to_contain_text('THIRD_NOTE_ONLY');expect(popup.locator('body')).not_to_contain_text('EXCLUDED_SECOND')
    popup.pdf(path='/tmp/slidefactory-task003-pdf/notes-only-selected.pdf',prefer_css_page_size=True,print_background=True)


def test_print_retains_main_context_and_late_definition_resources(tmp_path,browser_factory):
    path=_ready(tmp_path);source=path.read_text().replace('<main id="sf-deck"','<main class="qa-deck-context" id="sf-deck"',1)
    source=source.replace('</head>','<style>main.qa-deck-context .sf-slide{background:rgb(255,0,255)!important}</style></head>',1)
    hook='''<script>document.addEventListener('sf:layout',event=>{if(event.detail.waitUntil)event.detail.waitUntil(new Promise(resolve=>setTimeout(()=>{if(!document.querySelector('#qa-late-style')){const style=document.createElement('style');style.id='qa-late-style';style.textContent='main.qa-deck-context .qa-late{fill:rgb(0,255,0)}';document.head.append(style);document.body.insertAdjacentHTML('afterbegin','<svg width="0" height="0"><defs><path id="qa-late-path" d="M0 0H100V100H0Z"/></defs></svg>');}event.target.insertAdjacentHTML('beforeend','<svg class="qa-late" style="position:absolute;left:20px;top:20px;width:100px;height:100px"><use href="#qa-late-path"/></svg>');resolve();},30)));});</script></body>'''
    path.write_text(hook.join(source.rsplit('</body>',1)));page=browser_factory(path);popup=_print(page)
    frame=popup.frame_locator('iframe').first
    expect(frame.locator('#sf-deck')).to_have_class('qa-deck-context')
    expect(frame.locator('.sf-slide')).to_have_css('background-color','rgb(255, 0, 255)')
    expect(frame.locator('#qa-late-path')).to_have_count(1)
    expect(frame.locator('.qa-late')).to_have_css('fill','rgb(0, 255, 0)')


def test_sidebar_pointer_keyboard_overflow_and_resize_handles(tmp_path,browser_factory):
    page=browser_factory(_ready(tmp_path));_edit(page)
    separator=page.get_by_role('separator',name='Breite der Folienübersicht',exact=True)
    expect(separator).to_have_attribute('aria-valuenow','180');separator.focus();separator.press('Shift+ArrowRight');expect(separator).to_have_attribute('aria-valuenow','200')
    box=separator.bounding_box();page.mouse.move(box['x']+4,box['y']+20);page.mouse.down();page.mouse.move(box['x']+70,box['y']+20);separator.press('Escape');page.mouse.up();expect(separator).to_have_attribute('aria-valuenow','200')
    for width in [480,768,1280]:
        page.set_viewport_size({'width':width,'height':900})
        # The compact layout collapses the sidebar in the resize handler; let it run first.
        page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
        if page.locator('.sf-thumbnails').is_hidden():page.get_by_role('button',name='Folienübersicht',exact=True).click()
        separator.focus();separator.press('End')
        assert page.locator('.sf-thumbnails').evaluate('node=>node.scrollWidth<=node.clientWidth')
        for canvas in page.locator('.sf-thumbnail-canvas').all():
            assert canvas.evaluate('node=>node.offsetWidth<=node.parentElement.clientWidth')
    page.set_viewport_size({'width':1280,'height':900});separator.press('Home')
    target=page.locator('[data-sf-id="qa-box"]');target.click();before=target.evaluate('node=>parseFloat(node.style.width)')
    handle=page.get_by_role('button',name='Größe ändern rechts',exact=True);handle.focus();handle.press('Shift+ArrowRight')
    assert target.evaluate('node=>parseFloat(node.style.width)')==before+10
    page.get_by_role('button',name='Rückgängig',exact=True).click();assert target.evaluate('node=>parseFloat(node.style.width)')==before
    page.keyboard.press('Control+Shift+z');assert target.evaluate('node=>parseFloat(node.style.width)')==before+10



def test_checkpoint_preserves_causal_order_and_rejects_corrupt_vector(tmp_path,browser_factory):
    page=browser_factory(_ready(tmp_path));_edit(page);ids=_slide_ids(page)
    page.get_by_role('button',name='Folie 1',exact=True).press('Alt+ArrowDown')
    page.get_by_role('button',name='Folie 3',exact=True).press('Alt+ArrowUp')
    page.get_by_role('button',name='Folie 3',exact=True).press('Alt+ArrowUp')
    order=[ids[1],ids[0],ids[2]];assert _slide_ids(page)==order
    field=_notes(page)
    for index in range(126):field.fill(f'Checkpoint note {index}');field.blur()
    page.wait_for_timeout(850)
    checkpoint=page.evaluate("()=>Object.values(localStorage).map(raw=>{try{return JSON.parse(raw)}catch{return {}}}).find(entry=>entry.checkpoint)")
    assert checkpoint['slideOrder']==order
    page.reload();expect(page.get_by_role('button',name='Bearbeiten',exact=True)).to_be_visible();assert _slide_ids(page)==order
    page.evaluate("""()=>{for(const [key,raw] of Object.entries(localStorage)){let entry;try{entry=JSON.parse(raw)}catch{continue}if(entry.checkpoint){entry.slideOrder=[entry.slideOrder[0],entry.slideOrder[0],entry.slideOrder[2]];localStorage.setItem(key,JSON.stringify(entry));}}}""")
    page.reload();expect(page.get_by_role('status')).to_contain_text('verworfen');assert _slide_ids(page)==ids


def test_compact_toolbar_lists_alignment_and_background_handoff(tmp_path,browser_factory):
    page=browser_factory(_ready(tmp_path));_edit(page)
    expect(page.get_by_role('button',name='Referentenansicht',exact=True)).to_be_hidden()
    assert page.get_by_role('button',name='Wiederholen',exact=True).count()==0
    assert page.get_by_role('button',name='Text bearbeiten',exact=True).count()==0
    assert page.get_by_role('button',name='Bild einfügen',exact=True).locator('svg').count()==1
    expect(page.get_by_role('button',name='Kommentare',exact=True)).to_be_visible()
    text=page.locator('[data-sf-id="qa-text"]');text.click()
    page.get_by_role('button',name='Rechtsbündig',exact=True).click();expect(text).to_have_css('text-align','right')
    page.get_by_role('button',name='Aufzählung',exact=True).click();expect(text.locator('ul')).to_have_count(1)
    page.keyboard.press('Control+z');expect(text.locator('ul')).to_have_count(0)
    page.keyboard.press('Control+Shift+z');expect(text.locator('ul')).to_have_count(1)
    color=page.get_by_label('Hintergrundfarbe',exact=True)
    color.evaluate("node=>{node.value='#13579b';node.dispatchEvent(new Event('input',{bubbles:true}));node.dispatchEvent(new Event('change',{bubbles:true}));}")
    assert _meta(page)['backgroundColor']=='#13579b'
    popup=_print(page);expect(popup.frame_locator('iframe').first.locator('.sf-slide')).to_have_css('background-color','rgb(19, 87, 155)');popup.close()
    saved=_download(page,tmp_path/'custom-background.html');_cli('validate',saved);fresh=browser_factory(saved);assert _meta(fresh)['backgroundColor']=='#13579b'
    _edit(fresh);fresh.get_by_label('Farbschema',exact=True).select_option('indigo-light');assert 'backgroundColor' not in _meta(fresh)
    fresh.get_by_role('button',name='Rückgängig',exact=True).click();assert _meta(fresh)['backgroundColor']=='#13579b'
    _cli('scheme',saved,'--id','indigo-light');assert 'backgroundColor' not in _json_script_for_test(saved)


def _json_script_for_test(path):
    return json.loads(_cli('inspect',path).stdout)['metadata']


@pytest.mark.parametrize('tag', ['p', 'h1'])
def test_text_lists_promote_valid_root_preserve_tag_styles_and_handoff(tmp_path, browser_factory, tag):
    import re
    path = _ready(tmp_path)
    source = path.read_text()
    source = re.sub(r'<p data-sf-id="qa-text".*?</p>', f'<{tag} class="qa-list-root" data-sf-id="qa-text" data-sf-kind="text" style="position:absolute;left:120px;top:560px;transform:rotate(1deg);z-index:3">Fixture alpha beta</{tag}>', source)
    style = f'<style>#sf-deck {tag}.qa-list-root{{font:italic 600 26px/1.6 Georgia;letter-spacing:1.2px;color:rgb(123,45,67);margin:7px 9px;padding:3px 5px;width:520px;height:140px;box-sizing:border-box}}</style>'
    source = source.replace('</head>', style + '</head>', 1)
    path.write_text(source)
    page = browser_factory(path)
    baseline = _download(page, tmp_path / 'before-list.html').read_text()
    sibling = baseline.split('<div id="qa-parent"', 1)[1].split('</section>', 1)[0]
    _edit(page)
    text = page.locator('[data-sf-id="qa-text"]')
    appearance = "node=>{const s=getComputedStyle(node),r=node.getBoundingClientRect();return {font:s.fontFamily,size:s.fontSize,weight:s.fontWeight,line:s.lineHeight,color:s.color,margin:s.margin,padding:s.padding,transform:s.transform,rect:[r.x,r.y,r.width,r.height]};}"
    before = text.evaluate(appearance)
    text.click(); page.get_by_role('button', name='Aufzählung', exact=True).click()
    expect(text.locator('ul > li')).to_have_count(1)
    assert text.evaluate('node=>node.tagName') == 'DIV'
    assert text.evaluate(appearance) == before
    page.keyboard.press('Control+z'); assert text.evaluate('node=>node.tagName') == tag.upper()
    page.keyboard.press('Control+Shift+z'); assert text.evaluate('node=>node.tagName') == 'DIV'
    _select(text, len('Fixture alpha beta'))
    text.press('Enter'); text.press_sequentially('Second item'); text.blur()
    expect(text.locator('li')).to_have_count(2)
    page.keyboard.press('Control+z'); expect(text.locator('li')).to_have_count(1)
    page.keyboard.press('Control+Shift+z'); expect(text.locator('li')).to_have_count(2)
    _select(text); page.get_by_role('button', name='Nummerierte Liste', exact=True).click()
    expect(text.locator('ol > li')).to_have_count(2)
    page.get_by_role('button', name='Nummerierte Liste', exact=True).click(); expect(text.locator('ol')).to_have_count(0)
    page.keyboard.press('Control+z'); expect(text.locator('ol > li')).to_have_count(2)
    saved = _download(page, tmp_path / f'list-{tag}.html'); _cli('validate', saved)
    assert '<div id="qa-parent"' + sibling in saved.read_text()
    fresh = browser_factory(saved); _edit(fresh)
    expect(fresh.locator('[data-sf-id="qa-text"]')).to_have_count(1)
    expect(fresh.locator('[data-sf-id="qa-text"] > ol > li')).to_have_count(2)
    assert fresh.locator('[data-sf-id="qa-text"]').evaluate(appearance) == before


def test_overlapping_prints_restore_hidden_slide_and_accept_en_dash(tmp_path, browser_factory):
    page = browser_factory(_ready(tmp_path)); ids = _slide_ids(page)
    hidden = page.locator(f'[data-sf-slide="{ids[1]}"]')
    attributes = "node=>['style','data-sf-runtime-original-style','data-sf-runtime-preview'].map(name=>node.getAttribute(name))"
    original = hidden.evaluate(attributes)
    page.evaluate("""()=>{window.qaPreparations=0;document.addEventListener('sf:layout',event=>{if(event.detail.waitUntil){const call=++window.qaPreparations;event.detail.waitUntil(new Promise(resolve=>setTimeout(resolve,call===1?350:600)));}});}""")
    page.get_by_role('button', name='Drucken/PDF', exact=True).click()
    page.get_by_label('Folien (leer = alle)', exact=True).fill('2')
    with page.expect_popup() as first: page.get_by_role('button', name='Drucken', exact=True).click()
    page.wait_for_function('window.qaPreparations===1')
    page.get_by_role('button', name='Drucken/PDF', exact=True).click()
    page.get_by_label('Folien (leer = alle)', exact=True).fill('2–3')
    with page.expect_popup() as second: page.get_by_role('button', name='Drucken', exact=True).click()
    popup = second.value
    expect(popup.locator('html')).to_have_attribute('data-sf-print-ready', 'true', timeout=15000)
    assert first.value.is_closed()
    assert hidden.evaluate(attributes) == original
    page.get_by_label('Folie auswählen', exact=True).select_option(ids[1])
    expect(hidden).to_be_visible(); expect(hidden).to_have_css('visibility', 'visible')
    assert popup.locator('.sf-print-page').count() == 2


def test_print_timeout_restores_hidden_slide(tmp_path, browser_factory):
    page = browser_factory(_ready(tmp_path)); ids = _slide_ids(page)
    hidden = page.locator(f'[data-sf-slide="{ids[1]}"]'); original = hidden.get_attribute('style')
    page.evaluate("""()=>document.addEventListener('sf:layout',event=>{if(event.detail.waitUntil)event.detail.waitUntil(new Promise(()=>{}));})""")
    page.get_by_role('button', name='Drucken/PDF', exact=True).click()
    page.get_by_label('Folien (leer = alle)', exact=True).fill('2')
    with page.expect_popup() as opened: page.get_by_role('button', name='Drucken', exact=True).click()
    expect(opened.value.get_by_role('alert')).to_contain_text('10 Sekunden', timeout=15000)
    expect(page.get_by_role('alert')).to_contain_text('10 Sekunden')
    assert hidden.get_attribute('style') == original
    assert hidden.get_attribute('data-sf-runtime-preview') is None
