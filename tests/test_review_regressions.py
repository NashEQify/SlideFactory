# INFRA: none
"""Real transition regressions discovered in the independent Task001 code review."""
import base64
from PIL import Image
import pytest
from playwright.sync_api import expect
from test_editor_e2e import (browser_factory, _ready, _edit, _box, _frame, _drag,
                            _download, _meta, _cli, PACKAGE)

pytestmark = pytest.mark.e2e


def test_native_keyboard_save_and_cancelled_gesture(tmp_path, browser_factory):
    page = browser_factory(_ready(tmp_path))
    _edit(page)
    box = _box(page)
    box.click()
    original = _frame(box)
    save = page.get_by_role('button', name='HTML speichern', exact=True)
    save.focus()
    save.press('ArrowRight')
    assert _frame(box) == original, 'toolbar focus must own its arrows'
    save.press('Enter')
    with page.expect_download() as download:
        page.get_by_role('button', name='Arbeitsstand mit Notizen', exact=True).press('Enter')
    download.value.save_as(tmp_path/'keyboard-saved.html')
    _cli('validate', tmp_path/'keyboard-saved.html')
    box.click()
    _drag(page, page.get_by_label('Objekt verschieben', exact=True), 25, 12)
    committed = _frame(box)
    assert committed != original
    page.get_by_role('button',name='Rückgängig',exact=True).click()
    assert _frame(box) == original
    box.click()
    grip = page.get_by_label('Objekt verschieben',exact=True).bounding_box()
    x,y=grip['x']+grip['width']/2,grip['y']+grip['height']/2
    page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+65,y+30)
    assert _frame(box)!=original
    page.keyboard.press('Escape');page.mouse.up()
    assert _frame(box)==original
    page.keyboard.press('Control+Shift+z')
    assert _frame(box)==committed, 'cancelled preview must never enter history'


@pytest.mark.parametrize('template,element',[('consulting.html','intro-subtitle'),('editorial.html','intro-title')])
def test_multiline_text_reparsed_in_same_frame(tmp_path,browser_factory,template,element):
    # Use the actual ready layout: the unrelated full-canvas geometry fixture
    # added by _ready would intercept a user's click on its original title.
    source=tmp_path/template
    source.write_bytes((PACKAGE/'assets'/template).read_bytes())
    page=browser_factory(source)
    _edit(page)
    target=page.locator(f'#sf-deck [data-sf-id="{element}"]')
    target.dblclick();target.press('Control+A');page.keyboard.insert_text('First')
    target.press('Enter');page.keyboard.insert_text('Second');target.press('Escape')
    assert target.locator('div,p,h1,h2').count()==0
    assert 'Second' in target.text_content()
    output=_download(page,tmp_path/'multiline.html')
    _cli('validate',output)
    fresh=browser_factory(output)
    assert fresh.locator(f'#sf-deck [data-sf-id="{element}"]').text_content()==target.text_content()
    _edit(fresh)
    pasted=fresh.locator(f'#sf-deck [data-sf-id="{element}"]')
    pasted.dblclick();pasted.press('Control+A')
    pasted.evaluate("n=>{const t=new DataTransfer();t.setData('text/plain','Third\\nFourth');n.dispatchEvent(new ClipboardEvent('paste',{bubbles:true,cancelable:true,clipboardData:t}));}")
    pasted.press('Escape')
    assert pasted.locator('div,p,h1,h2').count()==0
    second=_download(fresh,tmp_path/'pasted.html')
    reopened=browser_factory(second)
    assert reopened.locator(f'#sf-deck [data-sf-id="{element}"]').text_content()==pasted.text_content()
    assert 'Fourth' in pasted.text_content()


def test_crop_pointer_cancel_redo_and_notes_transaction_order(tmp_path,browser_factory):
    page=browser_factory(_ready(tmp_path))
    _edit(page)
    page.get_by_role('button',name='Nächste Folie').click()
    page.get_by_role('button',name='Nächste Folie').click()
    image=page.locator('#sf-deck [data-sf-id="outlook-image"]')
    original_frame=_frame(image);original_crop=image.get_attribute('data-sf-crop')
    image.click();page.get_by_role('button',name='Bild zuschneiden',exact=True).click()
    # Starting a crop shows its context row and refits the slide; wait until the grip stops moving.
    handle=page.get_by_label('Ausschnitt unten rechts',exact=True);grip=None
    for _ in range(40):
        page.wait_for_timeout(50);box=handle.bounding_box()
        if box==grip:break
        grip=box
    x,y=grip['x']+grip['width']/2,grip['y']+grip['height']/2
    page.mouse.move(x,y);page.mouse.down();page.mouse.move(x-25,y-8)
    expect(image).not_to_have_attribute('data-sf-crop',original_crop)  # preview applies asynchronously
    page.keyboard.press('Escape');page.mouse.up()
    assert _frame(image)==original_frame and image.get_attribute('data-sf-crop')==original_crop
    expect(page.locator('#sf-crop-source')).to_be_hidden()
    assert page.get_by_role('alert').is_hidden()
    image.click();page.get_by_role('button',name='Bild zuschneiden',exact=True).click()
    page.get_by_label('Bildausschnitt',exact=True).fill('1.7')
    zoomed=image.get_attribute('data-sf-crop')
    page.get_by_role('button',name='Referentennotizen',exact=True).click()
    expect(page.get_by_role('button',name='Übernehmen',exact=True)).to_be_hidden()
    note=page.get_by_label('Referentennotizen',exact=True)
    note.fill('Keep this separately committed note');note.blur()
    page.get_by_role('button',name='Referentennotizen',exact=True).click()
    image.click();page.get_by_role('button',name='Bild zuschneiden',exact=True).click()
    page.get_by_label('Bildausschnitt',exact=True).fill('1.3')
    page.get_by_role('button',name='Übernehmen',exact=True).click()
    page.get_by_role('button',name='Rückgängig',exact=True).click()
    assert _meta(page)['notes']['outlook']=='Keep this separately committed note'
    assert image.get_attribute('data-sf-crop')==zoomed
    image.click();page.get_by_role('button',name='Bild zuschneiden',exact=True).click()
    page.get_by_label('Bildausschnitt',exact=True).fill('1.5')
    page.locator('#sf-selection').focus();page.keyboard.press('Control+y')
    expect(page.locator('#sf-crop-source')).to_be_hidden()
    expect(page.get_by_role('button',name='Übernehmen',exact=True)).to_be_hidden()
    assert _meta(page)['notes']['outlook']=='Keep this separately committed note'
    assert page.get_by_role('alert').is_hidden()
    saved=_download(page,tmp_path/'crop-order.html');_cli('validate',saved)


def test_import_keeps_original_slide_and_oriented_jpeg_handoff(tmp_path,browser_factory):
    from test_editor_e2e import _image_state, _assert_crop
    source=_ready(tmp_path)
    file=tmp_path/'oriented.jpeg'
    exif=Image.Exif();exif[274]=6
    Image.new('RGB',(160,320),'#246c91').save(file,format='JPEG',exif=exif)
    page=browser_factory(source);_edit(page)
    page.evaluate("""()=>{
      const decode=Image.prototype.decode;
      window.qaPendingImageDecodes=[];
      Image.prototype.decode=async function(){
        await new Promise(resolve=>window.qaPendingImageDecodes.push(resolve));
        return decode.call(this);
      };
      window.qaReleaseNextImageDecode=()=>{
        const release=window.qaPendingImageDecodes.shift();
        if(!release)throw new Error('No synthetic image decode is pending');
        release();
      };
    }""")
    page.get_by_label('Bilddatei auswählen',exact=True).set_input_files(file)
    page.wait_for_function('window.qaPendingImageDecodes.length===1')
    page.get_by_role('button',name='Nächste Folie').click()
    expect(page.locator('#sf-deck [data-sf-slide="approach"]')).to_be_visible()
    page.evaluate('window.qaReleaseNextImageDecode()')
    imported=page.locator('#sf-deck [data-sf-slide="intro"] [data-sf-kind="image"]')
    expect(imported).to_have_count(1)
    assert page.locator('#sf-deck [data-sf-slide="approach"] [data-sf-kind="image"]').count()==0
    img=imported.locator('img')
    expect(img).to_have_js_property('naturalWidth',320)
    expect(img).to_have_js_property('naturalHeight',160)
    assert (img.get_attribute('width'),img.get_attribute('height'))==('320','160')
    assert base64.b64decode(img.get_attribute('src').split(',',1)[1])==file.read_bytes()
    oriented_state=_image_state(imported)
    _assert_crop(oriented_state)
    # A dropped image also retains the local placement captured before decode,
    # even if navigation hides its original slide meanwhile.
    page.get_by_role('button',name='Vorherige Folie').click()
    png=tmp_path/'drop.png';Image.new('RGB',(320,160),'#eab46b').save(png)
    expected_drop=page.locator('#sf-deck [data-sf-slide="intro"]').evaluate("""(node,b64)=>{
      const bytes=Uint8Array.from(atob(b64),c=>c.charCodeAt(0)),transfer=new DataTransfer();
      transfer.items.add(new File([bytes],'drop.png',{type:'image/png'}));
      const r=node.getBoundingClientRect();
      const event=new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:transfer,clientX:r.x+r.width*.25,clientY:r.y+r.height*.35});
      node.dispatchEvent(event);
      // MouseEvent client coordinates are integer pixels. Use the actual
      // produced event, not its pre-coercion constructor arguments.
      // CSSOM serializes pixel lengths at browser precision. Normalize the
      // independently calculated expected lengths at that public boundary.
      const expected=document.createElement('div');
      expected.style.left=((event.clientX-r.x)/r.width*1600-160)+'px';
      expected.style.top=((event.clientY-r.y)/r.height*900-80)+'px';
      return {left:expected.style.left,top:expected.style.top};
    }""",base64.b64encode(png.read_bytes()).decode())
    page.wait_for_function('window.qaPendingImageDecodes.length===1')
    page.get_by_role('button',name='Nächste Folie').click()
    expect(page.locator('#sf-deck [data-sf-slide="approach"]')).to_be_visible()
    page.evaluate('window.qaReleaseNextImageDecode()')
    expect(imported).to_have_count(2)
    dropped=page.locator('#sf-deck [data-sf-slide="intro"] [data-sf-kind="image"]').filter(has=page.locator('img[src^="data:image/png"]'))
    frame=_frame(dropped)
    assert frame['left']==expected_drop['left']
    assert frame['top']==expected_drop['top']
    expect(dropped.locator('img')).to_have_js_property('naturalWidth',320)
    expect(dropped.locator('img')).to_have_js_property('naturalHeight',160)
    dropped_state=_image_state(dropped)
    _assert_crop(dropped_state)
    assert base64.b64decode(dropped_state['src'].split(',',1)[1])==png.read_bytes()
    saved=_download(page,tmp_path/'oriented-saved.html');_cli('validate',saved)
    _cli('set-text',saved,'--element','intro-title','--text','A local agent change')
    fresh=browser_factory(saved)
    assert fresh.locator('#sf-deck [data-sf-slide="intro"] [data-sf-kind="image"]').count()==2
    for state,asset in ((oriented_state,file),(dropped_state,png)):
        reopened=fresh.locator(f'#sf-deck [data-sf-id="{state["id"]}"]')
        expect(reopened.locator('img')).to_have_js_property('naturalWidth',state['naturalWidth'])
        expect(reopened.locator('img')).to_have_js_property('naturalHeight',state['naturalHeight'])
        assert _image_state(reopened)==state
        assert base64.b64decode(reopened.locator('img').get_attribute('src').split(',',1)[1])==asset.read_bytes()


@pytest.mark.parametrize('followup',['alignment','notes'])
def test_rapid_text_followup_keeps_separate_undo_transactions(tmp_path,browser_factory,followup):
    source=tmp_path/'rapid-text.html';source.write_bytes((PACKAGE/'assets'/'consulting.html').read_bytes())
    page=browser_factory(source);_edit(page)
    target=page.locator('#sf-deck [data-sf-id="intro-subtitle"]')
    original_text=target.text_content();original_align=target.evaluate('n=>n.style.textAlign')
    target.dblclick();target.press('Control+A');page.keyboard.insert_text('A separately committed text edit')
    if followup=='alignment':
        page.get_by_role('button',name='Zentriert',exact=True).click()
    else:
        page.get_by_role('button',name='Referentennotizen',exact=True).click()
        note=page.get_by_label('Referentennotizen',exact=True);note.fill('An independent presenter note');note.blur()
    # Production text commit is debounced450ms. Bracket that producer timer;
    # waiting on visible text alone would observe the precommit preview.
    page.wait_for_timeout(650)
    page.get_by_role('button',name='Rückgängig',exact=True).click()
    assert target.text_content()=='A separately committed text edit'
    if followup=='alignment':assert target.evaluate('n=>n.style.textAlign')==original_align
    else:assert _meta(page)['notes']['intro']==''
    page.get_by_role('button',name='Rückgängig',exact=True).click()
    assert target.text_content()==original_text
    page.keyboard.press('Control+Shift+z')
    assert target.text_content()=='A separately committed text edit'
    if followup=='alignment':assert target.evaluate('n=>n.style.textAlign')==original_align
    else:assert _meta(page)['notes']['intro']==''
    page.keyboard.press('Control+Shift+z')
    if followup=='alignment':assert target.evaluate('n=>n.style.textAlign')=='center'
    else:assert _meta(page)['notes']['intro']=='An independent presenter note'


def test_already_open_notes_finalize_pending_text_before_metadata(tmp_path,browser_factory):
    source=tmp_path/'open-panel.html';source.write_bytes((PACKAGE/'assets'/'consulting.html').read_bytes())
    page=browser_factory(source);_edit(page)
    page.get_by_role('button',name='Referentennotizen',exact=True).click()
    target=page.locator('#sf-deck [data-sf-id="intro-subtitle"]');original=target.text_content()
    target.dblclick();target.press('Control+A');page.keyboard.insert_text('Preserve independently typed text')
    note=page.get_by_label('Referentennotizen',exact=True)
    note.fill('A note in the already open panel');note.blur()
    page.wait_for_timeout(650)
    page.get_by_role('button',name='Rückgängig',exact=True).click()
    assert target.text_content()=='Preserve independently typed text'
    assert _meta(page)['notes']['intro']==''
    page.get_by_role('button',name='Rückgängig',exact=True).click()
    assert target.text_content()==original


@pytest.mark.parametrize('defect',['zero-frame','negative-frame','relative-frame','nan-original','multiple-originals','missing-left','relative-top'])
def test_malformed_authored_image_fails_before_browser_mutation(tmp_path,browser_factory,defect):
    source=(PACKAGE/'assets'/'consulting.html').read_text()
    import re
    match=re.search(r'<div data-sf-id="outlook-image".*?</div>',source,re.S)
    assert match
    fragment=match[0]
    if defect=='zero-frame':fragment=fragment.replace('width:720px','width:0px',1)
    elif defect=='negative-frame':fragment=fragment.replace('width:720px','width:-100px',1)
    elif defect=='relative-frame':fragment=fragment.replace('width:720px','width:50%',1)
    elif defect=='nan-original':fragment=fragment.replace('width="1200"','width="NaN"',1)
    elif defect=='missing-left':fragment=fragment.replace('left:740px;','',1)
    elif defect=='relative-top':fragment=fragment.replace('top:366px;','top:20%;',1)
    else:
        original=re.search(r'<img\b[^>]*>',fragment)[0]
        fragment=fragment.replace('</div>',original+'</div>',1)
    broken=source[:match.start()]+fragment+source[match.end():]
    file=tmp_path/f'{defect}.html';file.write_text(broken)
    _cli('validate',file,success=False)
    page=browser_factory(file)
    expect(page.get_by_role('alert')).to_contain_text('SlideFactory konnte diese Datei nicht öffnen')
    expect(page.get_by_role('button',name='HTML speichern',exact=True)).to_be_disabled()
    assert page.locator('#sf-editor').count()==0
    assert file.read_text()==broken
