"""Slide-to-slide links in the helper: schema, inspect listing and target validation."""

import json
from pathlib import Path
import subprocess
import sys

import pytest


pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "skills/slidefactory/scripts/deck.py"
BLANK = ROOT / "skills/slidefactory/assets/consulting-blank.html"


def cli(*args):
    return subprocess.run([sys.executable, str(CLI), *map(str, args)], capture_output=True, text=True)


def deck_with(tmp_path, slides):
    """Blank deck whose single slide is replaced by the given section fragments."""
    source = BLANK.read_text(encoding="utf-8")
    blank_slide = '<section class="sf-slide" data-sf-slide="intro" style="width:1600px;height:900px"></section>'
    assert source.count(blank_slide) == 1
    source = source.replace(blank_slide, "\n".join(slides))
    meta_start = source.index('<script id="sf-document" type="application/json">') + len('<script id="sf-document" type="application/json">')
    meta_end = source.index("</script>", meta_start)
    meta = json.loads(source[meta_start:meta_end])
    ids = [fragment.split('data-sf-slide="', 1)[1].split('"', 1)[0] for fragment in slides]
    meta["notes"] = {identity: "" for identity in ids}
    meta["guidance"] = {identity: {"text": "", "status": "open"} for identity in ids}
    source = source[:meta_start] + json.dumps(meta).replace("<", "\\u003c") + source[meta_end:]
    path = tmp_path / "deck.html"
    path.write_text(source, encoding="utf-8")
    return path


def slide(identity, inner=""):
    return f'<section class="sf-slide" data-sf-slide="{identity}" style="width:1600px;height:900px">{inner}</section>'


def link(identity, target, text="Backup"):
    return (f'<a class="sf-link" data-sf-id="{identity}" data-sf-kind="text" data-sf-link="" href="#{target}" '
            f'style="position:absolute;left:10px;top:10px;width:300px;height:56px">{text}</a>')


def test_inspect_lists_links_and_validate_accepts_valid_targets(tmp_path):
    path = deck_with(tmp_path, [slide("main", link("link-a", "backup") + '<a href="#main">self</a>'), slide("backup", link("link-b", "main", "Zurück"))])
    result = cli("validate", path)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["valid"] is True
    info = json.loads(cli("inspect", path, "--slide", "main").stdout)["slide"]
    assert info["links"] == [
        {"id": "link-a", "object": True, "target": "backup", "text": "Backup", "targetNumber": 2},
        {"id": None, "object": False, "target": "main", "text": "self", "targetNumber": 1},
    ]
    assert next(item for item in info["objects"] if item["id"] == "link-a")["link"] == "backup"


def test_validate_reports_missing_targets_with_nonzero_exit(tmp_path):
    path = deck_with(tmp_path, [slide("main", link("link-a", "gone") + '<a href="#also-gone">hand</a>'), slide("backup")])
    result = cli("validate", path)
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["valid"] is False
    assert [(error["slideId"], error["target"], error["object"]) for error in report["linkErrors"]] == [("main", "gone", True), ("main", "also-gone", False)]


def test_write_commands_warn_but_keep_working_with_dangling_links(tmp_path):
    path = deck_with(tmp_path, [slide("main", link("link-a", "gone")), slide("backup")])
    result = cli("reorder", path, "--order", "backup,main", "--output", tmp_path / "out.html")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["linkWarnings"][0]["target"] == "gone"


@pytest.mark.parametrize("markup", [
    '<div data-sf-id="link-x" data-sf-kind="text" data-sf-link="" href="#backup">x</div>',
    '<a data-sf-id="link-x" data-sf-kind="box" data-sf-link="" href="#backup">x</a>',
    '<a data-sf-id="link-x" data-sf-kind="text" data-sf-link="" href="https://example.com">x</a>',
    '<a data-sf-link="" href="#backup">x</a>',
])
def test_malformed_link_objects_are_schema_errors(tmp_path, markup):
    path = deck_with(tmp_path, [slide("main", markup), slide("backup")])
    result = cli("validate", path)
    assert result.returncode == 2
    assert "link" in result.stderr.lower()


def test_in_page_anchors_are_not_slide_links_and_escapes_match_runtime(tmp_path):
    inner = '<p id="fn1">Note</p><a href="#">top</a><a href="#fn1">[1]</a><a href="#50%">bad escape</a>'
    path = deck_with(tmp_path, [slide("main", inner), slide("backup")])
    report = json.loads(cli("validate", path).stdout)
    assert [(error["target"], error["text"]) for error in report["linkErrors"]] == [(None, "bad escape")]
    path = deck_with(tmp_path, [slide("main", '<a href="#fn1">[1]</a><p id="fn1">x</p>' + link("link-a", "r%C3%BCck")), slide("rück")])
    assert cli("validate", path).returncode == 0
