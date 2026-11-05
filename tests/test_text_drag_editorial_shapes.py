"""Bounded real-pointer regressions for text intent and the editorial shape frames."""
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect
from test_editor_e2e import browser_factory, PACKAGE, _edit, _drag, _download, _cli

pytestmark = pytest.mark.e2e


def _point(node, fraction=.5):
    box = node.bounding_box()
    return box['x'] + box['width'] * fraction, box['y'] + box['height'] / 2


def _style(node):
    return node.evaluate('e=>e.style.cssText')


def test_text_surface_intent_cancel_and_offline_handoff(tmp_path, browser_factory):
    source = (PACKAGE / 'assets/consulting-blank.html').read_text()
    content = '<div data-sf-id="drag-text" data-sf-kind="text" style="position:absolute;left:200px;top:160px;width:500px;height:90px;font:32px/1.3 Arial">Alpha Beta Gamma</div>'
    content += '<div style="position:absolute;left:200px;top:450px;transform:scale(.8);transform-origin:0 0"><div data-sf-id="flow-text" data-sf-kind="text" data-sf-layout="flow" style="width:500px;height:80px;font:32px Arial">Flow text</div></div>'
    path = tmp_path / 'text-intent.html'
    path.write_text(source.replace('</section>', content + '</section>', 1))
    page = browser_factory(path); _edit(page)
    text = page.locator('[data-sf-id="drag-text"]')
    original = _style(text)
    _drag(page, text, 50, 24)
    moved = _style(text)
    assert moved != original and text.get_attribute('contenteditable') == 'false'
    page.get_by_role('button', name='Rückgängig', exact=True).click()
    assert _style(text) == original, 'one drag must be one undo unit'
    # A real click at the start of Beta places the insertion point there.
    point = text.evaluate('''e=>{const r=document.createRange();r.setStart(e.firstChild,6);r.setEnd(e.firstChild,7);const b=r.getBoundingClientRect();return [b.x+.2,b.y+b.height/2]}''')
    page.mouse.click(*point); page.keyboard.insert_text('X')
    expect(text).to_have_text('Alpha XBeta Gamma')
    active_style = _style(text)
    rect = text.bounding_box()
    page.mouse.move(rect['x']+5, rect['y']+15); page.mouse.down(); page.mouse.move(rect['x']+145, rect['y']+15, steps=5); page.mouse.up()
    assert page.evaluate('getSelection().toString().length') > 0
    assert _style(text) == active_style, 'active text selection must not move its frame'
    text.press('Escape')
    # Pending click and active drag both cancel, including their late pointerup.
    page.mouse.move(*_point(text)); page.mouse.down(); page.keyboard.press('Escape'); page.mouse.up()
    assert text.get_attribute('contenteditable') == 'false' and _style(text) == active_style
    x,y = _point(text); page.mouse.move(x,y); page.mouse.down(); page.mouse.move(x+45,y+20,steps=3)
    assert _style(text) != active_style
    page.keyboard.press('Escape'); page.mouse.up()
    assert _style(text) == active_style and text.get_attribute('contenteditable') == 'false'
    # Native capture loss cancels a pending click before a delayed release.
    page.evaluate("document.addEventListener('pointerdown', e=>window.qaPointer=e.pointerId,{once:true})")
    x,y=_point(text); page.mouse.move(x,y); page.mouse.down(); page.mouse.move(x+1,y)
    text.evaluate('(e)=>e.releasePointerCapture(window.qaPointer)')
    page.mouse.move(*_point(text,.51)); page.mouse.up()
    assert text.get_attribute('contenteditable') == 'false'
    flow = page.locator('[data-sf-id="flow-text"]'); before = _style(flow)
    x,y = _point(text); page.mouse.move(x,y); page.mouse.down(); flow.focus()
    page.mouse.move(x+30,y+15); page.mouse.up()
    assert _style(flow)==before and _style(text)==active_style
    assert flow.get_attribute('contenteditable')=='false', 'focus change must cancel the old text press'
    scale = flow.evaluate('e=>e.getBoundingClientRect().width/e.offsetWidth')
    _drag(page, flow, 40, 20)
    dx,dy = flow.evaluate('e=>e.style.translate.split(" ").map(parseFloat)')
    assert abs(dx-40/scale)<.2 and abs(dy-20/scale)<.2
    assert flow.evaluate('e=>e.style.position') == ''
    assert flow.evaluate('e=>e.parentElement.style.transform') == 'scale(0.8)'
    page.get_by_role('button', name='Rückgängig', exact=True).click(); assert _style(flow)==before
    _drag(page, flow, 40, 20)
    committed = _style(flow)
    # Save through a genuine keyboard activation while a text click is pending.
    page.mouse.move(*_point(text)); page.mouse.down()
    save = page.get_by_role('button', name='HTML speichern', exact=True); save.focus()
    saved = tmp_path / 'text-saved.html'
    save.press('Enter')
    with page.expect_download() as download: page.get_by_role('button', name='Arbeitsstand mit Notizen', exact=True).press('Enter')
    download.value.save_as(saved); page.mouse.up()
    assert text.get_attribute('contenteditable') == 'false'
    _cli('validate', saved)
    reopened = browser_factory(saved)
    expect(reopened.locator('[data-sf-id="drag-text"]')).to_have_text('Alpha XBeta Gamma')
    assert _style(reopened.locator('[data-sf-id="flow-text"]')) == committed


def test_editorial_shapes_and_preserved_intro_text(tmp_path, browser_factory):
    path = tmp_path / 'editorial.html'; path.write_text((PACKAGE / 'assets/editorial.html').read_text())
    page = browser_factory(path)
    evidence = Path(os.environ.get('SF_SHAPE_EVIDENCE', tmp_path)); evidence.mkdir(parents=True, exist_ok=True)
    # Capture the authored presentation before edits, with matching viewport/chrome.
    page.locator('#sf-deck').screenshot(path=str(evidence / 'editorial-after-intro.png'))
    page.locator('#sf-slide-choice').select_option('approach')
    page.locator('#sf-deck').screenshot(path=str(evidence / 'editorial-after-approach.png'))
    _edit(page)
    for index in (1,2,3):
        circle=page.locator(f'[data-sf-id="approach-circle-{index}"]')
        circle.click(); assert circle.get_attribute('data-sf-shape') == 'oval'
    circle=page.locator('[data-sf-id="approach-circle-1"]'); original=_style(circle)
    _drag(page,circle,25,15); assert _style(circle)!=original
    _drag(page,page.get_by_role('button',name='Größe ändern unten rechts',exact=True),12,8)
    page.get_by_role('button',name='Füllfarbe',exact=True).click()
    page.get_by_role('button',name='#ff595e',exact=True).click()
    assert circle.evaluate('e=>getComputedStyle(e.querySelector("ellipse")).fill')=='rgb(255, 89, 94)'
    circle.click(); state=_style(circle); page.keyboard.press('Delete'); expect(circle).to_have_count(0)
    page.get_by_role('button',name='Rückgängig',exact=True).click(); assert _style(circle)==state
    line=page.locator('[data-sf-id="approach-connector"]'); x,y=_point(line,.25)
    page.mouse.click(x,y); page.get_by_role('button',name='Kantenfarbe',exact=True).click()
    page.get_by_role('button',name='#1982c4',exact=True).click()
    assert line.evaluate('e=>getComputedStyle(e.querySelector("line")).stroke')=='rgb(25, 130, 196)'
    page.locator('#sf-slide-choice').select_option('intro')
    panel=page.locator('[data-sf-id="intro-panel"]'); panel.click(position={'x':15,'y':15})
    title=page.locator('[data-sf-id="intro-title"]').inner_text()
    page.keyboard.press('Delete'); expect(panel).to_have_count(0)
    assert page.locator('[data-sf-id="intro-title"]').inner_text()==title
    assert page.locator('[data-sf-slide="intro"]>[data-sf-kind="text"]').count()==5
    page.get_by_role('button',name='Rückgängig',exact=True).click(); expect(panel).to_have_count(1)
    saved=_download(page,tmp_path/'editorial-saved.html'); _cli('validate',saved)
    reopened=browser_factory(saved)
    assert reopened.locator('[data-sf-shape]').count()==5
    assert _style(reopened.locator('[data-sf-id="approach-circle-1"]'))==state
    assert reopened.locator('[data-sf-id="intro-title"]').inner_text()==title
