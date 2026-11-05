"""Adversarial cross-window ordering and recovered-journal compaction.

Obsolete popup writer commands and delayed close packets deliberately cross the
browser boundary. Image insertion/nudge/undo/reload use the actual public UI.
"""
import pytest
from playwright.sync_api import expect
from test_editor_e2e import _presenter_action
from test_editor_e2e import _ready, _edit, _meta, _slide_ids, browser_factory, images


@pytest.mark.parametrize('command', ['notes-begin', 'notes', 'notes-settle', 'history'])
def test_removed_presenter_writer_commands_cannot_mutate_owner(tmp_path, browser_factory, command):
    page = browser_factory(_ready(tmp_path)); _edit(page)
    first = _slide_ids(page)[0]; original = _meta(page)
    page.evaluate("""() => {window.qaMessages=[];addEventListener('message',event=>qaMessages.push(event.data));}""")
    with page.expect_popup() as opened:
        _presenter_action(page)
    popup = opened.value
    expect(popup.locator('#connection')).to_have_text('Mit Präsentation verbunden.')
    packet = page.evaluate("qaMessages.find(message=>message.command==='ready')")
    packet.update(command=command, payload={'slideId':first, 'epoch':0, 'text':'Obsolete writer', 'action':'undo'})
    popup.evaluate("packet=>opener.postMessage(packet,'*')", packet)
    page.wait_for_function("command=>qaMessages.some(message=>message.command===command)", arg=command)
    assert _meta(page) == original
    expect(popup.get_by_role('textbox').and_(popup.locator(':not(#end-time)'))).to_have_count(0)  # only the meeting-end time input


def test_recovered_removed_object_does_not_poison_later_checkpoint(tmp_path, browser_factory, images):
    page = browser_factory(_ready(tmp_path)); _edit(page)
    first = _slide_ids(page)[0]
    before = set(page.locator('#sf-deck [data-sf-kind="image"]').evaluate_all('nodes=>nodes.map(n=>n.dataset.sfId)'))
    page.get_by_role('button', name='Bild einfügen', exact=True).click()
    page.get_by_label('Bilddatei auswählen', exact=True).set_input_files(images['png'])
    page.wait_for_function('count=>document.querySelectorAll(\'#sf-deck [data-sf-kind="image"]\').length===count', arg=len(before)+1)
    after = set(page.locator('#sf-deck [data-sf-kind="image"]').evaluate_all('nodes=>nodes.map(n=>n.dataset.sfId)'))
    added = (after-before).pop(); target=page.locator(f'[data-sf-id="{added}"]')
    target.click(); page.keyboard.press('ArrowRight')
    undo=page.get_by_role('button', name='Rückgängig', exact=True)
    undo.click(); undo.click(); expect(target).to_have_count(0)
    page.reload(); expect(target).to_have_count(0); _edit(page)
    page.get_by_role('button', name='Referentennotizen', exact=True).click()
    field=page.get_by_role('textbox', name='Referentennotizen', exact=True)
    field.evaluate("""field => {
      for(let i=0;i<132;i++) {
        field.value='Accepted note '+i;
        field.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText'}));
        field.dispatchEvent(new Event('blur'));
      }
    }""")
    page.wait_for_function("""() => {
      const meta=JSON.parse(document.querySelector('#sf-document').textContent);
      const head=JSON.parse(localStorage.getItem('slidefactory:'+meta.deckId)||'null');
      if(!head)return false;
      return Object.entries(localStorage).some(([key,value])=>key.endsWith('entry:'+head.head)&&JSON.parse(value).checkpoint===true);
    }""", timeout=10000)
    page.reload()
    assert _meta(page)['notes'][first] == 'Accepted note 131'
    expect(target).to_have_count(0)


def test_thumbnail_fallback_releases_frames_outside_current_window(tmp_path, browser_factory):
    from test_local_transaction_core import _fixture
    path, *_ = _fixture(tmp_path, slides=40)
    page = browser_factory(path)
    page.add_init_script('window.IntersectionObserver=undefined')
    page.reload(); _edit(page)
    ids = _slide_ids(page)
    page.get_by_label('Folie auswählen', exact=True).select_option(ids[30])
    frames = page.locator('.sf-thumbnails iframe')
    from test_thumbnail_coverage import assert_thumbnail_coverage
    assert assert_thumbnail_coverage(page) == frames.count()
    page.locator('.sf-thumbnails').evaluate('e=>e.scrollTop=0')
    assert_thumbnail_coverage(page)
    page.get_by_role('button', name='Folienübersicht', exact=True).click()
    expect(frames).to_have_count(0)


def test_old_popup_close_cannot_detach_reopened_presenter(tmp_path, browser_factory):
    page=browser_factory(_ready(tmp_path)); first=_slide_ids(page)[0]
    page.evaluate("""() => {
      const open=window.open;
      window.open=function(...args){window.qaLatest=open.apply(this,args);return qaLatest;};
      window.qaDelayed=[];
      window.addEventListener('message',event=>{
        if(event.source===window.qaOld && event.data?.command==='close') {
          event.stopImmediatePropagation();qaDelayed.push({data:event.data,source:event.source});
        }
      },true);
    }""")
    with page.expect_popup() as opened:
        _presenter_action(page)
    old=opened.value; expect(old.locator('#connection')).to_have_text('Mit Präsentation verbunden.')
    page.evaluate('window.qaOld=window.qaLatest')
    old.close()
    page.wait_for_function("qaDelayed.some(packet=>packet.data.command==='close')")
    with page.expect_popup() as reopened:
        _presenter_action(page)
    new=reopened.value; expect(new.locator('#connection')).to_have_text('Mit Präsentation verbunden.')
    page.evaluate("""() => {
      const packets=qaDelayed.splice(0);qaOld=null;
      for(const packet of packets)window.dispatchEvent(new MessageEvent('message',packet));
    }""")
    new.get_by_role('button',name='Nächste Folie',exact=True).click()
    expect(page.get_by_label('Folie auswählen',exact=True)).not_to_have_value(first)
    new.close()
