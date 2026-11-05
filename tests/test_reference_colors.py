"""Synthetic production adapter tests: preservation, scheme colors, limited family.

No private reference files or colors/functions are test inputs. The adapter is
an explicitly recognized stage/slide/theme-lab color derivative, not an import.
"""

import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "skills/slidefactory"
HELPER = PACKAGE / "scripts/reference_colors.py"
from test_editor_e2e import CHROMIUM


def invoke(*args, success=True, helper=HELPER):
    result = subprocess.run([sys.executable, str(helper), *map(str, args)], capture_output=True, text=True)
    assert (result.returncode == 0) == success, result.stderr
    assert "Traceback" not in result.stderr
    return result


def synthetic():
    return ('''<!doctype html><html><head><title>Synthetic family</title><style>
:root { --bg:#112233; --navy:#123456; --panel:#234567; --cyan:#44eeee; --blue:#5599dd; --teal:#228888; --purple:#bb88dd; --amber:#ddaa44; --muted:#bbccdd; --dim:#99aabb; --line:rgba(99,150,200,.3); }
@font-face { font-family:FixtureFont; src:url("data:font/woff2;base64,SYNTHETICFONTBYTES"); }
body{margin:0;background:var(--bg);color:#fff}#stage{width:1600px;height:900px;background:var(--bg)}
.slide{width:1600px;height:900px;position:relative}.panel{position:absolute;left:50px;top:80px;width:450px;height:180px;background:rgba(15,40,80,.8);border:1px solid rgba(99,150,200,.3)}
.panel strong{color:#ffffff}.secondary{color:#c0d0e0}.masked{mask-image:linear-gradient(to right,transparent,#000);filter:brightness(0) invert(1)}
</style></head><body><div class="theme-lab" id="theme-lab"><select id="theme-select"><option value="old">Old</option></select><input id="theme-color" type="color" value="#112233"></div>
<div id="stage"><section class="slide" id="fixture-slide"><h1 id="fixture-heading">Synthetic title</h1><div class="panel"><strong>Readable text</strong><p class="secondary">Detail</p></div><svg id="fixture-svg" width="200" height="100"></svg><img id="fixture-image" src="data:image/png;base64,SYNTHETICIMAGEBYTES"><span id="inline-color" style="color:#ffffff">Inline text</span></section></div>
<template id="note-fixture">Synthetic note must remain identical.</template>
<script id="fixture-runtime">window.originalEditorWorking=true;function drawFixture(){document.getElementById('fixture-svg').innerHTML='<path id="fixture-path" d="M0 0 L100 50" stroke="#44eeee" fill="none" /><rect width="10" height="10" fill="#5599dd" stroke="#44eeee" /><defs><mask id="fixture-mask"><rect width="10" height="10" fill="#ffffff" /></mask></defs>';}drawFixture();document.getElementById('theme-select').addEventListener('change',()=>{document.documentElement.style.setProperty('--bg','#000000');});</script>
</body></html>''').replace("\n", "\r\n").encode()


@pytest.fixture
def reference(tmp_path):
    source = tmp_path / "synthetic.html"
    source.write_bytes(synthetic())
    return source


def fragment(data, tag, identity):
    return re.search(rb'<' + tag.encode() + rb'\b[^>]*id="' + identity.encode() + rb'".*?</' + tag.encode() + rb'>', data, re.S)[0]


@pytest.mark.integration
def test_color_derivative_preserves_slides_assets_notes_and_runtime(reference, tmp_path):
    before = reference.read_bytes()
    output = tmp_path / "colors.html"
    report = json.loads(invoke(reference, "--output", output).stdout)
    after = output.read_bytes()
    assert reference.read_bytes() == before
    assert report["originalSha256"] == hashlib.sha256(before).hexdigest()
    assert fragment(after,"section","fixture-slide") == fragment(before,"section","fixture-slide")
    assert fragment(after,"template","note-fixture") == fragment(before,"template","note-fixture")
    for asset in (b"data:font/woff2;base64,SYNTHETICFONTBYTES",b"data:image/png;base64,SYNTHETICIMAGEBYTES"):
        assert asset in after
    assert b"mask-image:linear-gradient(to right,transparent,#000)" in after
    assert b"filter:brightness(0) invert(1)" in after
    assert b"window.originalEditorWorking=true;" in after
    assert b'stroke="var(--cyan)"' in after
    assert b'fill="var(--blue)" stroke="var(--cyan)"' in after
    assert b'<mask id="fixture-mask"><rect width="10" height="10" fill="#ffffff" /></mask>' in after
    assert b'color:var(--sf-ref-text)' in after
    assert b'background:color-mix(in srgb,var(--sf-ref-surface) 80%,transparent)' in after
    for identity in ("cyan-dark","cyan-light","indigo-dark","indigo-light"):
        assert f'<option value="{identity}">'.encode() in after
    assert b"sf-document" not in after
    assert report["witnesses"]["slidesByteIdentical"]
    assert report["witnesses"]["notesByteIdentical"]
    assert report["witnesses"]["assetsByteIdentical"]
    assert report["witnesses"]["originalIdsRetained"]


@pytest.mark.integration
def test_svg_draw_template_comparisons_do_not_hide_semantic_paint(reference, tmp_path):
    source = reference.read_bytes().replace(b'</body>', b'<script id="generated-fixture">document.getElementById("fixture-svg").innerHTML=`<path d="M${0 < 1 ? 1 : 2},0 L20,20" stroke="#44eeee" fill="#5599dd" />`;</script></body>')
    reference.write_bytes(source)
    output = tmp_path / "generated-path.html"
    invoke(reference,"--output",output)
    result=output.read_bytes()
    assert b'd="M${0 < 1 ? 1 : 2},0 L20,20" stroke="var(--cyan)" fill="var(--blue)"' in result


@pytest.mark.integration
def test_unknown_family_same_output_and_unknown_scheme_fail_atomically(reference, tmp_path):
    output = tmp_path / "existing.html"
    output.write_bytes(b"Prior authored work")
    for data in (b"<html><head></head><body>Unknown</body></html>", synthetic().replace(b'id="stage"',b'id="other"'), synthetic().replace(b'class="slide"',b'class="unknown"'), synthetic().replace(b'class="theme-lab"',b'class="unknown"')):
        invalid = tmp_path / "unsupported.html"
        invalid.write_bytes(data)
        invoke(invalid, "--output", output, success=False)
        assert output.read_bytes() == b"Prior authored work"
        assert invalid.read_bytes() == data
    before = reference.read_bytes()
    invoke(reference, "--output", reference, success=False)
    invoke(reference, "--output", output, "--scheme", "unknown", success=False)
    assert reference.read_bytes() == before
    assert output.read_bytes() == b"Prior authored work"
    assert not list(tmp_path.glob(".*.tmp"))


@pytest.mark.integration
def test_adapter_is_packaged_and_rejects_repeat_application(reference, tmp_path):
    isolated = tmp_path / "unrelated" / "slidefactory"
    shutil.copytree(PACKAGE, isolated)
    helper = isolated / "scripts/reference_colors.py"
    output = tmp_path / "copied-package.html"
    invoke(reference, "--output", output, helper=helper)
    before = output.read_bytes()
    invoke(output, "--output", tmp_path / "twice.html", helper=helper, success=False)
    assert output.read_bytes() == before


@pytest.mark.e2e
def test_actual_browser_four_schemes_keep_geometry_and_legible_colors(reference, tmp_path):
    from playwright.sync_api import sync_playwright
    output = tmp_path / "browser-colors.html"
    invoke(reference,"--output",output)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=CHROMIUM, headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width":1700,"height":1000})
        page.route("**/*", lambda route: route.abort() if route.request.url.startswith(("http:","https:")) else route.continue_())
        errors=[]
        page.on("pageerror",lambda error: errors.append(str(error)))
        page.goto(output.as_uri())
        initial=page.locator("#fixture-heading").bounding_box()
        states=[]
        for scheme in ("cyan-dark","cyan-light","indigo-dark","indigo-light"):
            page.locator("#theme-select").select_option(scheme)
            state=page.evaluate('''() => ({scheme:document.documentElement.dataset.sfReferenceScheme,background:getComputedStyle(document.getElementById('stage')).backgroundColor,text:getComputedStyle(document.querySelector('.panel strong')).color,inline:getComputedStyle(document.getElementById('inline-color')).color,path:getComputedStyle(document.getElementById('fixture-path')).stroke,panel:getComputedStyle(document.querySelector('.panel')).backgroundColor,editor:window.originalEditorWorking,inputHidden:document.getElementById('theme-color').hidden})''')
            assert state["scheme"] == scheme
            assert state["editor"] and state["inputHidden"]
            assert state["background"] != "rgb(0, 0, 0)"  # Legacy handler blocked.
            assert state["text"] == state["inline"]
            assert state["text"] != state["background"]
            def luminance(css):
                channels=[int(value)/255 for value in re.findall(r"\d+",css)[:3]]
                return sum((value/12.92 if value<=.04045 else ((value+.055)/1.055)**2.4)*weight for value,weight in zip(channels,(.2126,.7152,.0722)))
            a,b=luminance(state["text"]),luminance(state["background"])
            assert (max(a,b)+.05)/(min(a,b)+.05)>=4.5
            assert page.locator("#fixture-mask rect").get_attribute("fill") == "#ffffff"
            assert page.locator("#fixture-heading").bounding_box() == initial
            states.append(state)
        assert states[0]["background"] != states[1]["background"]
        assert states[0]["path"] != states[2]["path"]
        assert not errors
        browser.close()


@pytest.mark.e2e
def test_dom_css_luminance_mask_keeps_white_and_black_paints(reference, tmp_path):
    from PIL import Image
    from playwright.sync_api import sync_playwright
    # Class selectors are deliberately generic: their safety comes from leaving
    # stylesheet SVG paints opaque, not from guessing a mask-related class name.
    css = b'mask rect{fill:#ffffff;stroke:#000000}.paint-dark{fill:black}.paint-light{fill:#ffffff}'
    svg = b'<svg id="css-mask-sample" width="120" height="50" style="position:absolute;left:800px;top:400px"><defs><mask id="css-luminance-mask" maskUnits="userSpaceOnUse" x="0" y="0" width="120" height="50"><rect class="paint-light" width="120" height="50"/><rect class="paint-dark" x="60" width="60" height="50"/></mask><clipPath id="css-clip"><rect class="paint-dark" width="120" height="50"/></clipPath></defs><rect width="120" height="50" fill="red" mask="url(#css-luminance-mask)"/></svg>'
    source = reference.read_bytes().replace(b'</style>',css+b'</style>').replace(b'</section>',svg+b'</section>')
    reference.write_bytes(source)
    output = tmp_path / "css-mask-colors.html"
    invoke(reference,"--output",output)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=CHROMIUM,headless=True,args=["--no-sandbox"])
        page = browser.new_page(viewport={"width":1700,"height":1000})
        page.goto(output.as_uri())
        for scheme in ("cyan-dark","cyan-light","indigo-dark","indigo-light"):
            page.locator("#theme-select").select_option(scheme)
            paints=page.evaluate('''() => ({white:getComputedStyle(document.querySelector('#css-luminance-mask .paint-light')).fill,black:getComputedStyle(document.querySelector('#css-luminance-mask .paint-dark')).fill,stroke:getComputedStyle(document.querySelector('#css-luminance-mask .paint-light')).stroke,clip:getComputedStyle(document.querySelector('#css-clip rect')).fill})''')
            assert paints == {"white":"rgb(255, 255, 255)","black":"rgb(0, 0, 0)","stroke":"rgb(0, 0, 0)","clip":"rgb(0, 0, 0)"}
            screenshot=Image.open(io.BytesIO(page.locator("#css-mask-sample").screenshot())).convert("RGB")
            assert screenshot.getpixel((20,25)) == (255,0,0)
            assert screenshot.getpixel((100,25)) != (255,0,0)
        browser.close()
    assert css in output.read_bytes()
    assert reference.read_bytes() == source
