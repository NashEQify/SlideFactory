"""Task006: four real offline PDFs and one readiness failure; no broad suite."""
import base64
import io
import os
from pathlib import Path
import re
import subprocess

from PIL import Image, ImageDraw
from playwright.sync_api import expect
from test_editor_e2e import _click_closing
from test_editor_e2e import ROOT, _json_script, _set_json_script, _download, browser_factory


EVIDENCE = Path(os.environ.get('SF_PDF_EVIDENCE', '/tmp/slidefactory-pdf-repair'))


def _fixture(tmp_path):
    source = (ROOT / 'skills/slidefactory/assets/editorial.html').read_text()
    image = Image.new('RGB', (1200, 600)); draw = ImageDraw.Draw(image)
    for box, color in [((0, 0, 599, 299), '#ef3340'), ((600, 0, 1199, 299), '#20bd65'),
                       ((0, 300, 599, 599), '#2864dc'), ((600, 300, 1199, 599), '#ffd43b')]:
        draw.rectangle(box, fill=color)
    data = io.BytesIO(); image.save(data, format='PNG')
    url = 'data:image/png;base64,' + base64.b64encode(data.getvalue()).decode()
    font = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf').read_bytes()
    css = '<style>@font-face{font-family:PDFProof;src:url(data:font/ttf;base64,' + base64.b64encode(font).decode() + ')}.sf-slide .proof-font{font-family:PDFProof}</style>'
    first = f'''<section class="sf-slide" data-sf-slide="proof-one" style="background:#18364a">
      <h1 data-sf-id="proof-title" data-sf-kind="text" class="proof-font" style="position:absolute;left:80px;top:60px;font-size:52px;color:white">OFFLINE PDF PROOF</h1>
      <div data-sf-id="proof-image" data-sf-kind="image" data-sf-crop='{{"x":0,"y":0,"w":1,"h":1}}' style="position:absolute;left:80px;top:240px;width:600px;height:300px;overflow:hidden"><img src="{url}" width="1200" height="600" style="position:absolute;left:0;top:0;width:600px;height:300px"></div>
      <div data-sf-id="proof-crop" data-sf-kind="image" data-sf-crop='{{"x":0.5,"y":0,"w":0.5,"h":1}}' style="position:absolute;left:980px;top:220px;width:480px;height:480px;overflow:hidden"><img src="{url}" width="1200" height="600" style="position:absolute;left:-480px;top:0;width:960px;height:480px"></div>
      <svg viewBox="0 0 600 160" style="position:absolute;left:80px;top:620px;width:600px;height:160px"><path d="M20 80H580" stroke="#ff9933" stroke-width="12"/><circle cx="80" cy="80" r="50" fill="#55ddcc"/><rect x="480" y="30" width="100" height="100" fill="#55ddcc"/></svg>
      <div data-sf-id="proof-background" data-sf-kind="box" style="position:absolute;left:740px;top:760px;width:200px;height:70px;background:linear-gradient(90deg,#ff9933,#ee3399)"></div>
      <p data-sf-id="proof-edge" data-sf-kind="text" style="position:absolute;right:20px;bottom:10px;color:white">BOTTOM RIGHT WITNESS</p>
    </section>'''
    second = '<section class="sf-slide" data-sf-slide="proof-two" style="background:#e4eef2;color:#18364a"><h1 data-sf-id="proof-second" data-sf-kind="text" class="proof-font" style="position:absolute;left:80px;top:80px;font-size:52px">SECOND SLIDE WITNESS</h1></section>'
    source = re.sub(r'<main id="sf-deck"[^>]*>.*?</main>', '<main id="sf-deck">' + first + second + '</main>', source, count=1, flags=re.S)
    meta = _json_script(source)
    long = ('Long notes continue on the following page. ' * 180) + ' LAST_NOTE_WITNESS'
    meta['notes'] = {'proof-one': long, 'proof-two': 'SECOND_NOTE_WITNESS'}
    meta['notesFormat'] = {'proof-one': {'version': 1, 'text': long, 'html': '<ol><li><strong><span style="font-size:18pt">' + long + '</span></strong></li></ol>'}}
    meta['guidance'] = {key: {'text': 'EXCLUDED_GUIDANCE', 'status': 'open'} for key in meta['notes']}
    source = _set_json_script(source, meta).replace('</head>', css + '</head>', 1)
    # Real asynchronous authored layout work: toolbar must await it.
    hook = '''<script>document.addEventListener('sf:layout',event=>{if(window.qaNativeRun && !event.detail.waitUntil && event.target.dataset.sfRuntimePreview==='true' && event.target.offsetWidth===1600){const node=document.createElement('p');node.dataset.sfTransient='';node.style='position:absolute;left:80px;top:200px;color:#ef3340;font-size:24px';node.textContent='NATIVE_HIDDEN_LAYOUT_WITNESS';event.target.append(node);}if(event.detail.waitUntil)event.detail.waitUntil(new Promise(resolve=>setTimeout(()=>{let node=event.target.querySelector('.proof-layout');if(!node){node=document.createElement('p');node.className='proof-layout';node.style='position:absolute;left:80px;top:160px;color:#ef3340;font-size:24px';node.textContent='ASYNC_LAYOUT_WITNESS';event.target.append(node);}resolve();},40)));});</script>'''
    path = tmp_path / 'offline-proof.html'; path.write_text((hook + '</body>').join(source.rsplit('</body>', 1)))
    EVIDENCE.mkdir(exist_ok=True)
    return path


def _pdf(page, name, *, notes=False, expected_pages=None):
    EVIDENCE.mkdir(exist_ok=True)
    path = EVIDENCE / (name + '.pdf')
    # False deliberately verifies exact-color CSS inside the projected iframes, too.
    page.pdf(path=str(path), prefer_css_page_size=True, print_background=False)
    info = subprocess.check_output(['pdfinfo', str(path)], text=True)
    pages = int(re.search(r'^Pages:\s+(\d+)', info, re.M)[1])
    width, height = map(float, re.search(r'^Page size:\s+([\d.]+) x ([\d.]+)', info, re.M).groups())
    expected = (595.3, 841.9) if notes else (907.1, 510.2)
    assert abs(width - expected[0]) < 1 and abs(height - expected[1]) < 1
    if expected_pages is not None: assert pages == expected_pages
    text = subprocess.check_output(['pdftotext', '-layout', str(path), '-'], text=True)
    assert 'EXCLUDED_GUIDANCE' not in text and 'HTML speichern' not in text
    return path, pages, text


def _image_proof(path):
    subprocess.run(['pdftoppm', '-f', '1', '-singlefile', '-scale-to-x', '1600', '-scale-to-y', '-1', '-png', str(path), str(path.with_suffix(''))], check=True, capture_output=True)
    image = Image.open(path.with_suffix('.png')).convert('RGB')
    for (x, y), expected in [((20, 20), (24, 54, 74)), ((120, 280), (239, 51, 64)),
                             ((500, 280), (32, 189, 101)), ((120, 480), (40, 100, 220)),
                             ((500, 480), (255, 212, 59)), ((1000, 300), (32, 189, 101)),
                             ((1000, 600), (255, 212, 59)), ((160, 700), (85, 221, 204))]:
        assert max(abs(a-b) for a,b in zip(image.getpixel((x,y)), expected)) < 4, (x, y, image.getpixel((x,y)))
    # Empty strips around the title catch native focus rings AND a visible caret,
    # independent of their color; the glyphs themselves begin below the top strip.
    for border in [(70,52,620,65), (70,52,79,130), (70,121,620,129), (610,52,620,129)]:
        assert all(max(abs(a-b) for a,b in zip(pixel, (24,54,74))) < 4 for pixel in image.crop(border).getdata()), border
    fonts = subprocess.check_output(['pdffonts', str(path)], text=True)
    assert 'DejaVuSans' in fonts


def test_offline_pdf_handoff_geometry_images_and_notes(tmp_path, browser_factory):
    page = browser_factory(_fixture(tmp_path)); page.context.set_offline(True)
    saved = _download(page, EVIDENCE / 'saved-offline-proof.html')
    page = browser_factory(saved); page.context.set_offline(True)
    expect(page.locator('meta[name="author"]')).to_have_attribute('content', 'git@griessing.com')
    expect(page.locator('.sf-toolbar [data-action=postits]')).to_have_count(1)
    expect(page.locator('#sf-player-controls [data-action=postits]')).to_have_count(0)
    expect(page.locator('#sf-player-controls button')).to_have_count(1)
    page.get_by_role('button', name='Bearbeiten', exact=True).click()
    page.locator('[data-sf-id=proof-title]').click()
    page.evaluate("window.qaNativeRun=true")
    native, _, text = _pdf(page, 'native-direct', expected_pages=2)
    assert 'BOTTOM RIGHT WITNESS' in text and 'SECOND SLIDE WITNESS' in text and 'NATIVE_HIDDEN_LAYOUT_WITNESS' in text
    expect(page.locator('[data-sf-id=proof-title]')).to_have_attribute('contenteditable', 'true')
    page.evaluate('window.qaNativeRun=false')
    _image_proof(native)
    page.keyboard.press('Control+p'); expect(page.locator('#sf-print-dialog')).to_be_visible()
    page.get_by_role('button', name='Abbrechen', exact=True).click()
    before = page.locator('#sf-document').text_content()
    # Suppress owner animation frames only after initialization; native resources stay real.
    page.evaluate("window.requestAnimationFrame=()=>0;window.print=()=>{}")
    for mode in ['slides', 'notes', 'only-notes']:
        page.get_by_role('button', name='Drucken/PDF', exact=True).click()
        page.get_by_label('Inhalt', exact=True).select_option(mode)
        page.locator('#sf-print-range').fill('1-2' if mode != 'only-notes' else '2')
        with page.expect_popup() as opened: page.get_by_role('button', name='Drucken', exact=True).click()
        popup = opened.value
        expect(popup.locator('html')).to_have_attribute('data-sf-print-ready', 'true', timeout=8000)
        pdf, count, text = _pdf(popup, mode, notes=mode != 'slides', expected_pages=2 if mode == 'slides' else 1 if mode == 'only-notes' else None)
        if mode == 'slides':
            assert 'ASYNC_LAYOUT_WITNESS' in text; _image_proof(pdf)
        elif mode == 'notes':
            assert count > 2 and 'LAST_NOTE_WITNESS' in text and 'SECOND_NOTE_WITNESS' in text
        else:
            assert 'SECOND_NOTE_WITNESS' in text and 'OFFLINE PDF PROOF' not in text and 'LAST_NOTE_WITNESS' not in text
        popup.close()
    assert page.locator('#sf-document').text_content() == before
    assert page.locator('[data-sf-runtime-preview]').count() == 0


def test_failed_image_stops_print_and_restores_owner(tmp_path, browser_factory):
    page = browser_factory(_fixture(tmp_path)); page.context.set_offline(True)
    page.evaluate("document.querySelector('[data-sf-slide=proof-two]').insertAdjacentHTML('beforeend','<img src=\"data:image/png;base64,broken\">')")
    before = page.locator('[data-sf-slide=proof-two]').get_attribute('style')
    page.get_by_role('button', name='Drucken/PDF', exact=True).click()
    with page.expect_popup() as opened: page.get_by_role('button', name='Drucken', exact=True).click()
    popup = opened.value
    expect(popup.get_by_role('alert')).to_contain_text('Bilder der Folie 2')
    assert popup.locator('html').get_attribute('data-sf-print-ready') is None
    assert page.locator('[data-sf-slide=proof-two]').get_attribute('style') == before
    assert page.locator('[data-sf-runtime-preview]').count() == 0


def test_native_print_during_hidden_slide_preparation(tmp_path, browser_factory):
    page = browser_factory(_fixture(tmp_path)); page.context.set_offline(True)
    hidden = page.locator('[data-sf-slide=proof-two]'); original = hidden.get_attribute('style')
    page.evaluate("document.addEventListener('sf:layout',event=>{if(event.detail.waitUntil && event.detail.slideId==='proof-two')event.detail.waitUntil(new Promise(resolve=>window.qaReleaseLayout=resolve));})")
    page.get_by_role('button', name='Drucken/PDF', exact=True).click()
    with page.expect_popup() as opened: page.get_by_role('button', name='Drucken', exact=True).click()
    popup = opened.value
    page.wait_for_function('typeof window.qaReleaseLayout === "function"')
    assert 'left: -100000px' in hidden.get_attribute('style')
    # Actual beforeprint/afterprint from the native renderer during an awaited hook.
    _, _, text = _pdf(page, 'native-during-preparation', expected_pages=2)
    assert 'SECOND SLIDE WITNESS' in text
    assert 'left: -100000px' in hidden.get_attribute('style')
    page.evaluate('window.qaReleaseLayout()')
    expect(popup.locator('html')).to_have_attribute('data-sf-print-ready', 'true', timeout=8000)
    assert hidden.get_attribute('style') == original
    assert page.locator('[data-sf-runtime-preview]').count() == 0
    popup.close()

    # Inject lifecycle boundaries to cover a preparation starting after beforeprint.
    page.evaluate("delete window.qaReleaseLayout;window.dispatchEvent(new Event('beforeprint'))")
    page.get_by_role('button', name='Drucken/PDF', exact=True).click()
    with page.expect_popup() as opened: page.get_by_role('button', name='Drucken', exact=True).click()
    popup = opened.value
    page.wait_for_function('typeof window.qaReleaseLayout === "function"')
    assert 'left: -100000px' not in hidden.get_attribute('style')
    page.evaluate("window.dispatchEvent(new Event('afterprint'))")
    assert 'left: -100000px' in hidden.get_attribute('style')
    page.evaluate('window.qaReleaseLayout()')
    expect(popup.locator('html')).to_have_attribute('data-sf-print-ready', 'true', timeout=8000)
    assert hidden.get_attribute('style') == original
    assert page.locator('[data-sf-runtime-preview]').count() == 0
    popup.close()


def test_slow_projected_frame_progress_cancel_and_error(tmp_path, browser_factory):
    """Inject 31s child load-event delivery; this does not reproduce private assets."""
    page = browser_factory(_fixture(tmp_path)); page.context.set_offline(True)
    before = page.locator('#sf-document').text_content()
    page.evaluate('''() => {
      window.qaFrameMode='slow';window.qaHeld=[];window.qaPrintCalls=0;window.qaLongTimers=new Set();
      const timeout=window.setTimeout,clear=window.clearTimeout,open=window.open;
      window.setTimeout=(callback,delay,...args)=>{let id;id=timeout(()=>{qaLongTimers.delete(id);callback(...args);},delay);if(delay===120000)qaLongTimers.add(id);return id;};
      window.clearTimeout=id=>{qaLongTimers.delete(id);clear(id);};
      window.open=(...args)=>{
        const popup=open(...args),mode=qaFrameMode,add=popup.EventTarget.prototype.addEventListener;let index=0;
        popup.print=()=>{qaPrintCalls++;};
        popup.HTMLIFrameElement.prototype.addEventListener=function(type,callback,options){
          if(type!=='load')return add.call(this,type,callback,options);
          const number=++index,frame=this;
          return add.call(this,type,event=>{
            const run=()=>callback.call(frame,event);
            if(mode==='slow'&&number===2){setTimeout(run,31000);return;}
            if((mode==='cancel'&&number===2)||(mode==='error'&&number===1)){qaHeld.push(run);return;}
            if(mode==='error'&&number===2){
              const img=frame.contentDocument.createElement('img');
              img.decode=()=>Promise.reject(Error('Injected projection decode failure'));
              frame.contentDocument.body.append(img);
            }
            run();
          },options);
        };
        return popup;
      };
    }''')

    def begin(mode):
        page.evaluate("mode=>{qaFrameMode=mode;qaHeld=[];}", mode)
        page.get_by_role('button', name='Drucken/PDF', exact=True).click()
        with page.expect_popup() as opened: page.get_by_role('button', name='Drucken', exact=True).click()
        return opened.value

    popup = begin('slow')
    expect(popup.get_by_role('status')).to_contain_text('1 / 2 Folien bereit.')
    expect(popup.get_by_role('status')).to_contain_text('Das Laden dauert länger', timeout=15000)
    assert popup.locator('iframe').count() == 2
    assert popup.locator('html').get_attribute('data-sf-print-ready') is None
    expect(popup.locator('html')).to_have_attribute('data-sf-print-ready', 'true', timeout=35000)
    assert page.evaluate('qaPrintCalls') == 1
    assert page.evaluate('qaLongTimers.size') == 0
    expect(popup.locator('.sf-print-progress')).to_have_count(0)
    popup.close()

    popup = begin('cancel')
    page.wait_for_function('qaHeld.length===1')
    _click_closing(popup.get_by_role('button', name='Abbrechen', exact=True))
    page.wait_for_function('qaLongTimers.size===0')
    assert popup.is_closed()
    page.evaluate('qaHeld.forEach(run=>run())')
    assert page.evaluate('qaPrintCalls') == 1
    expect(page.get_by_role('alert')).to_be_hidden()

    popup = begin('error')
    expect(popup.get_by_role('alert')).to_contain_text('Bilder der Folie 2: Injected projection decode failure')
    assert page.evaluate('qaLongTimers.size') == 0
    assert popup.locator('html').get_attribute('data-sf-print-ready') is None
    page.evaluate('qaHeld.forEach(run=>run())')
    assert page.evaluate('qaPrintCalls') == 1
    with popup.expect_event('close'):
        _click_closing(popup.get_by_role('button', name='Schließen', exact=True))
    assert page.locator('#sf-document').text_content() == before
    assert page.locator('[data-sf-runtime-preview]').count() == 0
