"""Production CLI integration plan, spec 001-working-package v1.

A6 / identity drift: reorder complete permutations, retain supplied insert IDs,
replacement identity, guidance transitions and extensions (clear; integration).
A7 / source collateral change: byte witnesses for untargeted source, CRLF,
SVG/comments/raw script lookalikes and rejected writes (clear; integration).
A9 / unsafe external content: escaped text/JSON and invalid schema, markers,
crop/assets/colors fail before touching output (clear; integration).
Ready-file checks drive builder outputs, not fabricated exported snapshots.
"""

import json
import base64
import io
from itertools import permutations
from pathlib import Path
import re
import subprocess
import sys

import pytest


pytestmark = pytest.mark.integration


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "skills/slidefactory/scripts/deck.py"
PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6WQAAAABJRU5ErkJggg=="
TOKENS = dict(background="#123", text="#ffffff", muted="#bbbbbb", accent="#00ffff", accent2="#7777ff", surface="#222222", border="#44444488")


def cli(*args, success=True):
    result = subprocess.run([sys.executable, str(CLI), *map(str, args)], capture_output=True, text=True)
    if success:
        assert result.returncode == 0, result.stderr
    else:
        assert result.returncode != 0
        assert result.stderr.strip()
    return result


def source():
    metadata = dict(schemaVersion=1, deckId="deck-original", revision="rev-original", title="Original", templateId="synthetic", templateVersion="1.0.0", colorScheme="dark", pageWidth=1600, pageHeight=900, notes={"one":"Speaker", "two":"Other"}, guidance={"one":{"text":"Keep it", "status":"addressed", "extension":17}, "two":{"text":"", "status":"open"}}, extension={"nested":[1, {"human":"preserved"}]})
    scheme = {"dark":{"label":"Dunkel", "tokens":TOKENS}}
    theme = ":root{" + "".join(f"--sf-{key}:{value};" for key,value in TOKENS.items()) + "}"
    return ("<!doctype html>\n<html><head><meta charset=\"utf-8\"><title>Original</title>\n"
        "<style id=\"shared-design\">/* authored */ .custom { color: #abc; }</style>\n"
        f'<script id="sf-color-schemes" type="application/json">{json.dumps(scheme)}</script>\n'
        f'<style id="sf-theme-tokens">{theme}</style>\n'
        f'<script id="sf-document" type="application/json">{json.dumps(metadata)}</script>\n'
        '</head><body><main id="sf-deck">\n'
        '<!-- <section data-sf-slide="fake"><div data-sf-id="fake"> -->\n'
        '<section class="sf-slide custom" data-sf-slide="one"><div style="transform:rotate(2deg)">\n'
        '<h1 data-sf-id="title-one" data-sf-kind="text" style="left:20px;top:30px;width:400px;height:100px">Old <em>headline</em></h1>\n'
        '<svg viewBox="0 0 20 20"><defs><linearGradient id="paint"><stop offset="0" /></linearGradient></defs><g><path d="M0 0" /></g></svg>\n'
        '</div></section>\n\n'
        '<section data-sf-slide="two" class="sf-slide">\n'
        '<p data-sf-id="title-two" data-sf-kind="text">Untouched ü &amp; β</p>\n'
        '<div data-sf-id="image-two" data-sf-kind="image" style="left:0px;top:0px;width:200px;height:200px" data-sf-crop=\'{"x":0,"y":0,"w":1,"h":1}\'>'
        f'<img width="1" height="1" src="data:image/png;base64,{PNG}" alt="original"></div>\n'
        '</section>\n</main>\n'
        '<script id="custom-runtime">const fake = \'<section data-sf-slide="fake"><p data-sf-id="title-one">\'; const ending="</section>";\n</script>\n'
        '</body></html>\n').encode()


@pytest.fixture
def deck(tmp_path):
    path = tmp_path / "authored.html"
    path.write_bytes(source().replace(b"\n", b"\r\n"))
    return path


def metadata(data):
    return json.loads(re.search(rb'<script id="sf-document"[^>]*>(.*?)</script>', data, re.S)[1])


def witness(data, start, end):
    return data[data.index(start):data.index(end, data.index(start)) + len(end)]


def slide(data, identifier):
    # Synthetic source has one nested div and no nested sections.
    return re.search(rb'<section\b[^>]*data-sf-slide="' + identifier.encode() + rb'".*?</section>', data, re.S)[0]


def fragment(tmp_path, identifier="three", object_id="new-title"):
    path = tmp_path / "fragment.html"
    path.write_text(f'<section class="sf-slide" data-sf-slide="{identifier}"><svg><defs><linearGradient id="fresh-paint"><stop /></linearGradient></defs><path fill="url(#fresh-paint)" /></svg><h2 data-sf-id="{object_id}" data-sf-kind="text">Inserted</h2></section>', encoding="utf-8")
    return path


def test_source_collateral_change_text_and_atomic_failure(deck, tmp_path):
    before = deck.read_bytes()
    output = tmp_path / "next.html"
    hostile = '</script><script>alert("bad")</script> & <b>ü</b>'
    cli("set-text", deck, "--element", "title-one", "--text", hostile, "--output", output)
    after = output.read_bytes()
    assert deck.read_bytes() == before
    assert slide(after, "two") == slide(before, "two")
    assert witness(after,b'<style id="shared-design">',b'</style>') == witness(before,b'<style id="shared-design">',b'</style>')
    assert witness(after,b'<script id="custom-runtime">',b'</script>') == witness(before,b'<script id="custom-runtime">',b'</script>')
    assert b'&lt;/script&gt;&lt;script&gt;alert("bad")&lt;/script&gt; &amp; &lt;b&gt;\xc3\xbc&lt;/b&gt;' in after
    assert b'\r\n' in after and b'\n' not in after.replace(b'\r\n',b'')
    assert metadata(after)["extension"] == metadata(before)["extension"]
    assert metadata(after)["revision"] != "rev-original"
    cli("validate", output)
    saved = output.read_bytes()
    for args in [("--element","missing"), ("--element","image-two")]:
        cli("set-text", deck, *args, "--text", "x", "--output", output, success=False)
        assert output.read_bytes() == saved
    assert not list(tmp_path.glob(".*.tmp"))


def test_identity_drift_reorder_insert_replace_and_guidance(deck, tmp_path):
    before = deck.read_bytes()
    cli("reorder", deck, "--order", "two,one")
    reordered = deck.read_bytes()
    assert reordered.index(slide(reordered, "two")) < reordered.index(slide(reordered, "one"))
    assert slide(reordered, "one") == slide(before, "one")
    assert slide(reordered, "two") == slide(before, "two")
    assert metadata(reordered)["notes"] == metadata(before)["notes"]
    assert metadata(reordered)["guidance"] == metadata(before)["guidance"]
    revision = metadata(reordered)["revision"]
    for order in ("one", "one,one", "one,two,three", "one,missing"):
        cli("reorder", deck, "--order", order, success=False)
        assert deck.read_bytes() == reordered
    new_fragment = fragment(tmp_path)
    cli("insert-slide", deck, "--fragment", new_fragment, "--after", "two")
    inserted = deck.read_bytes()
    assert inserted.index(slide(inserted, "two")) < inserted.index(slide(inserted, "three")) < inserted.index(slide(inserted, "one"))
    assert slide(inserted, "three") == new_fragment.read_bytes()
    assert b'fill="url(#fresh-paint)"' in inserted
    assert metadata(inserted)["revision"] != revision
    assert metadata(inserted)["notes"]["three"] == ""
    assert metadata(inserted)["guidance"]["three"] == {"text":"", "status":"open"}
    preserved = {identity: slide(inserted, identity) for identity in ("one", "two", "three")}
    for order in permutations(preserved):
        cli("reorder", deck, "--order", ",".join(order))
        result = deck.read_bytes()
        assert sorted(order, key=lambda identity: result.index(slide(result, identity))) == list(order)
        assert all(slide(result, identity) == preserved[identity] for identity in preserved)
    cli("reorder", deck, "--order", "two,three,one")
    inserted = deck.read_bytes()
    cli("insert-slide", deck, "--fragment", new_fragment, success=False)
    assert deck.read_bytes() == inserted
    extract = tmp_path / "extracted.html"
    cli("extract-slide", deck, "--slide", "2", "--output", extract)
    assert extract.read_bytes() == new_fragment.read_bytes()
    replacement = fragment(tmp_path, "one", "replacement-title")
    cli("replace-slide", deck, "--slide", "one", "--fragment", replacement)
    replaced = deck.read_bytes()
    assert slide(replaced, "one") == replacement.read_bytes()
    assert metadata(replaced)["notes"]["one"] == "Speaker"
    assert metadata(replaced)["guidance"]["one"]["extension"] == 17
    assert slide(replaced, "two") == slide(before, "two")
    bad = fragment(tmp_path, "one", "title-two")
    cli("replace-slide", deck, "--slide", "one", "--fragment", bad, success=False)
    assert deck.read_bytes() == replaced
    text = '</script><script>danger()</script> ä'
    cli("guidance", deck, "--slide", "one", "--text", text)
    updated = deck.read_bytes()
    assert b"\\u003c/script>" in updated
    assert metadata(updated)["guidance"]["one"] == {"text":text, "status":"open", "extension":17}
    cli("guidance", deck, "--slide", "one", "--status", "addressed")
    assert metadata(deck.read_bytes())["guidance"]["one"]["status"] == "addressed"
    cli("validate", deck)


def test_unsafe_external_content_validation_and_atomic_outputs(deck, tmp_path):
    good = deck.read_bytes()
    output = tmp_path / "existing.html"
    output.write_bytes(b"existing work must survive")
    original_output = output.read_bytes()
    invalid = tmp_path / "invalid.html"
    variants = [
        good.replace(b'"schemaVersion": 1', b'"schemaVersion": 99'),
        good.replace(b'data-sf-id="title-two"', b'data-sf-id="title-one"'),
        good.replace(b'data-sf-id="title-two"', b'data-sf-id="one"'),
        good.replace(b'data-sf-id="title-two" ', b''),
        good.replace(b'data-sf-slide="two"', b'data-sf-slide="one"'),
        good.replace(b'data-sf-id="title-two"', b'data-sf-id="title-two" data-sf-id="other"'),
        good.replace(b'"schemaVersion": 1', b'"schemaVersion": 1, "schemaVersion": 1'),
        good.replace(b'"status": "addressed"', b'"status": "bogus"'),
        good.replace(b'"status": "addressed"', b'"status": []'),
        good.replace(b'"notes": {"one": "Speaker", "two": "Other"}', b'"notes": {"missing": "lost"}'),
        good.replace(b'"x":0,"y":0,"w":1,"h":1', b'"x":0.8,"y":0,"w":0.5,"h":1'),
        good.replace(b'"x":0,"y":0,"w":1,"h":1', b'"x":0,"y":0,"w":NaN,"h":1'),
        good.replace(b'width:200px;height:200px', b'width:400px;height:200px'),
        good.replace(b'data:image/png;base64,' + PNG.encode(), b'https://example.invalid/image.png'),
        good.replace(b'data:image/png;base64,' + PNG.encode(), b'data:image/png;base64,ZmFrZQ=='),
        good.replace(b'"#00ffff"', b'"red"'),
        good.replace(b'<script id="custom-runtime">', b'<script src="runtime.js" id="custom-runtime">'),
        good.replace(b'<svg viewBox="0 0 20 20">', b'<svg viewBox="0 0 20 20"><image href="https://example.invalid/image.png" />'),
        good.replace(b'<style id="shared-design">', b'<style id="shared-design">@import "external.css";'),
        good.replace(b'</div></section>', b'</section>'),
        b'<html><head></head><body>Unknown legacy family</body></html>',
    ]
    for data in variants:
        invalid.write_bytes(data)
        checked = cli("validate", invalid, success=False)
        assert "Traceback" not in checked.stderr
        cli("new", "--template", invalid, "--output", output, "--title", "Do not write", success=False)
        assert output.read_bytes() == original_output
        assert invalid.read_bytes() == data
    assert not list(tmp_path.glob(".*.tmp"))


def test_inspect_new_fragment_boundaries_and_redaction(deck, tmp_path):
    original = deck.read_bytes()
    overview = json.loads(cli("inspect", deck).stdout)
    assert overview["slideCount"] == 2
    assert overview["metadata"]["extension"] == {"nested":[1,{"human":"preserved"}]}
    focused = json.loads(cli("inspect", deck, "--slide", "two").stdout)
    assert focused["slide"]["id"] == "two"
    assert focused["slide"]["objects"][1]["crop"] == {"x":0,"y":0,"w":1,"h":1}
    assert PNG not in json.dumps(overview)
    assert "custom-runtime" not in json.dumps(overview)
    assert deck.read_bytes() == original
    new = tmp_path / "new.html"
    title = '</script><script>unsafe()</script> & New'
    cli("new", "--template", deck, "--output", new, "--title", title)
    created = new.read_bytes()
    assert metadata(created)["title"] == title
    assert metadata(created)["deckId"] != "deck-original"
    assert metadata(created)["revision"] != "rev-original"
    assert metadata(created)["templateId"] == "synthetic"
    assert slide(created, "one") == slide(original, "one")
    assert slide(created, "two") == slide(original, "two")
    assert b"&lt;script&gt;unsafe()&lt;/script&gt;" in created
    cli("validate", new)
    replacement = fragment(tmp_path, "different")
    cli("replace-slide", deck, "--slide", "one", "--fragment", replacement, success=False)
    assert deck.read_bytes() == original
    for raw in ('<section data-sf-slide="new" class="sf-slide"><h2 data-sf-id="title-two" data-sf-kind="text">Collision</h2></section>',
                '<section class="sf-slide" data-sf-slide="new" />',
                '<section class="sf-slide" data-sf-slide="new"></section><script>side_effect()</script>'):
        replacement.write_text(raw)
        cli("insert-slide", deck, "--fragment", replacement, success=False)
        assert deck.read_bytes() == original


def test_append_fragment_and_safe_svg_asset_redaction(deck, tmp_path):
    new_fragment = fragment(tmp_path)
    cli("insert-slide", deck, "--fragment", new_fragment)
    overview = json.loads(cli("inspect", deck).stdout)
    assert [item["id"] for item in overview["slides"]] == ["one", "two", "three"]
    data = deck.read_bytes()
    # Percent-encoded trusted template SVG originals are valid and inspect
    # reports only dimensions/MIME/byte count, including extension data assets.
    svg_url = b'data:image/svg+xml,%3Csvg%20width="1"%20height="1"%20xmlns="http://www.w3.org/2000/svg"%3E%3C/svg%3E'
    safe_src = svg_url.replace(b'"',b'%22')
    data = data.replace(b'data:image/png;base64,' + PNG.encode(), safe_src)
    meta = metadata(data)
    meta["extension"]["asset"] = svg_url.decode()
    data = re.sub(rb'(<script id="sf-document"[^>]*>).*?(</script>)', lambda match: match[1] + json.dumps(meta).encode() + match[2], data, flags=re.S)
    deck.write_bytes(data)
    cli("validate", deck)
    inspection = cli("inspect", deck).stdout
    assert "%3Csvg" not in inspection
    assert "data:image" not in inspection
    assert '"mime": "image/svg+xml"' in inspection


def test_scheme_selection_preserves_all_authored_source(deck, tmp_path):
    data = deck.read_bytes()
    schemes = {"dark":{"label":"Dunkel", "tokens":TOKENS}, "light":{"label":"Hell", "tokens":{**TOKENS,"background":"#ffffff","text":"#123"}}}
    data = re.sub(rb'(<script id="sf-color-schemes"[^>]*>).*?(</script>)', lambda match: match[1] + json.dumps(schemes).encode() + match[2], data, flags=re.S)
    deck.write_bytes(data)
    output = tmp_path / "light.html"
    cli("scheme", deck, "--id", "light", "--output", output)
    changed = output.read_bytes()
    assert metadata(changed)["colorScheme"] == "light"
    assert metadata(changed)["revision"] != metadata(data)["revision"]
    assert metadata(changed)["deckId"] == metadata(data)["deckId"]
    # Runtime derives selected tokens on load: scheme changes only JSON state.
    blank_metadata = lambda raw: re.sub(rb'(<script id="sf-document"[^>]*>).*?(</script>)', rb'\1\2', raw, flags=re.S)
    assert blank_metadata(changed) == blank_metadata(data)
    cli("validate", output)
    cli("scheme", deck, "--id", "unknown", "--output", output, success=False)
    assert output.read_bytes() == changed
    assert deck.read_bytes() == data


@pytest.mark.parametrize("orientation", [1, 5, 6, 7, 8])
def test_jpeg_exif_dimensions_follow_browser_orientation_and_preserve_original(deck, orientation):
    from PIL import Image
    original = io.BytesIO()
    exif = Image.Exif()
    exif[0x0112] = orientation
    Image.new("RGB", (80, 160), "#789abc").save(original, format="JPEG", exif=exif)
    data_url = b"data:image/jpeg;base64," + base64.b64encode(original.getvalue())
    width, height = (160, 80) if orientation in {5, 6, 7, 8} else (80, 160)
    data = deck.read_bytes().replace(b'data:image/png;base64,' + PNG.encode(), data_url)
    data = data.replace(b'<img width="1" height="1"', f'<img width="{width}" height="{height}"'.encode())
    data = data.replace(b'width:200px;height:200px', f'width:{width}px;height:{height}px'.encode())
    deck.write_bytes(data)
    cli("validate", deck)
    info = json.loads(cli("inspect", deck, "--slide", "two").stdout)
    assert info["slide"]["objects"][1]["original"]["dimensions"] == [width,height]
    cli("set-text",deck,"--element","title-one","--text","Unrelated oriented-image revision")
    assert slide(deck.read_bytes(), "two") == slide(data, "two")
    assert data_url in deck.read_bytes()


def test_image_frame_positions_require_finite_pixels_and_reject_atomically(deck, tmp_path):
    before=deck.read_bytes()
    output=tmp_path/"existing-revision.html"
    output.write_bytes(b"Existing revision survives rejected image geometry")
    for changed in (before.replace(b'left:0px;top:0px;',b'top:0px;'),before.replace(b'left:0px;top:0px;',b'left:0px;top:10%;')):
        deck.write_bytes(changed)
        cli("validate",deck,success=False)
        cli("set-text",deck,"--element","title-one","--text","Rejected revision","--output",output,success=False)
        assert deck.read_bytes()==changed
        assert output.read_bytes()==b"Existing revision survives rejected image geometry"
    negative=before.replace(b'left:0px;top:0px;',b'left:-20px;top:-30.5px;')
    deck.write_bytes(negative)
    cli("validate",deck)
    info=json.loads(cli("inspect",deck,"--slide","two").stdout)
    assert info["slide"]["objects"][1]["geometry"]["left"]==-20
    assert info["slide"]["objects"][1]["geometry"]["top"]==-30.5
    assert deck.read_bytes()==negative
    assert not list(tmp_path.glob(".*.tmp"))


def test_inspect_keeps_data_labels_and_redacts_only_actual_asset_urls(deck):
    before=deck.read_bytes()
    meta=metadata(before)
    meta["title"]="Metadata: Bitte prüfen; Data: Q1"
    meta["guidance"]["one"]["text"]="Metadata: Bitte erhalten; Data: Q1"
    meta["notes"]["one"]="Data: Q1 bleibt lesbar"
    meta["extension"]["description"]="Metadata: zusätzliche Information; Data: Q1"
    meta["extension"]["asset"]='data:image/svg+xml;charset=utf-8,<svg xmlns="http://www.w3.org/2000/svg"> private asset bytes </svg>'
    updated=re.sub(rb'(<script id="sf-document"[^>]*>).*?(</script>)',lambda match:match[1]+json.dumps(meta).encode()+match[2],before,flags=re.S)
    deck.write_bytes(updated)
    cli("set-text",deck,"--element","title-one","--text","Data: Q1 und Metadata: Text")
    authored=deck.read_bytes()
    result=json.loads(cli("inspect",deck).stdout)
    assert result["metadata"]["title"]==meta["title"]
    assert result["metadata"]["guidance"]["one"]["text"]==meta["guidance"]["one"]["text"]
    assert result["metadata"]["notes"]["one"]==meta["notes"]["one"]
    assert result["metadata"]["extension"]["description"]==meta["extension"]["description"]
    assert result["slides"][0]["objects"][0]["text"]=="Data: Q1 und Metadata: Text"
    assert result["metadata"]["extension"]["asset"]=="[embedded asset omitted]"
    assert "private asset bytes" not in json.dumps(result)
    focused=json.loads(cli("inspect",deck,"--slide","one").stdout)
    assert focused["slide"]["guidance"]["text"]==meta["guidance"]["one"]["text"]
    assert deck.read_bytes()==authored


@pytest.mark.parametrize("name", ["starter.html", "starter-editorial.html"])
def test_ready_builder_output_cli_roundtrip(name, tmp_path):
    ready = ROOT / "skills/slidefactory/assets" / name
    if not ready.exists():
        pytest.skip("Ready asset pending builder publication")
    cli("validate", ready)
    output = tmp_path / name
    cli("new", "--template", ready, "--output", output, "--title", "Packaged handoff")
    initial = output.read_bytes()
    inspected = json.loads(cli("inspect", output).stdout)
    objects = inspected["slides"][0]["objects"]
    element = next(item["id"] for item in objects if item["kind"] == "text")
    cli("set-text", output, "--element", element, "--text", "Actual package revision")
    changed = output.read_bytes()
    assert ready.read_bytes() != initial
    assert metadata(changed)["revision"] != metadata(initial)["revision"]
    # Last slide, design CSS, scheme data, and runtime survive an unrelated edit.
    last = inspected["slides"][-1]["id"]
    extract = tmp_path / "last-fragment.html"
    before = tmp_path / "before.html"
    before.write_bytes(initial)
    cli("extract-slide", before, "--slide", last, "--output", extract)
    last_before = extract.read_bytes()
    cli("extract-slide", output, "--slide", last, "--output", extract)
    assert extract.read_bytes() == last_before
    for match in re.finditer(rb'<(?:style|script)\b[^>]*\bid="([^"]+)"[^>]*>.*?</(?:style|script)>', initial, re.S):
        if match[1] != b"sf-document":
            assert match[0] in changed
    cli("validate", output)
