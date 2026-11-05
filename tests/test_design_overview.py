"""Design overview slides: every starter shows its design to the person who opens it.

The overview leads each starter, names every sized type role with the size the
design CSS actually sets, and stays out of decks created with deck.py new.
"""

import json
from pathlib import Path
import re
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "skills/slidefactory/assets"
CLI = ROOT / "skills/slidefactory/scripts/deck.py"
STARTERS = {
    "consulting.html": "consulting",
    "consulting-blank.html": "consulting",
    "editorial.html": "editorial",
    "editorial-blank.html": "editorial",
}
OVERVIEW = ["design-type", "design-components", "design-rules"]


def _slides(source):
    return re.findall(r'<section class="sf-slide" data-sf-slide="([^"]+)"( data-sf-overview)?', source)


def _type_roles(design):
    css = (ROOT / "src/designs" / f"{design}.css").read_text()
    roles = {}
    for role, body in re.findall(r"\.sf-slide \.([\w-]+) \{([^}]*)\}", css):
        size = re.search(r"font(?:-size)?:[^;]*?(\d+)px", body)
        if size and role != "sf-link":
            roles[role] = size.group(1)
    return roles


@pytest.mark.parametrize("name,design", STARTERS.items())
def test_starter_opens_with_overview_matching_design_css(name, design):
    source = (ASSETS / name).read_text()
    slides = _slides(source)
    assert [identity for identity, marked in slides if marked] == OVERVIEW
    assert [identity for identity, _ in slides[: len(OVERVIEW)]] == OVERVIEW
    assert "{{" not in source
    roles = _type_roles(design)
    assert {"headline", "body-copy", "step-body", "kicker", "deck-footer"} <= set(roles)
    for role, size in roles.items():
        assert f"<b>{role}</b> · {size} px" in source, role
    meta = json.loads(re.search(r'<script id="sf-document" type="application/json">(.*?)</script>', source, re.S).group(1))
    assert set(meta["notes"]) == {identity for identity, _ in slides}


@pytest.mark.parametrize("name", STARTERS)
def test_new_deck_leaves_overview_out(name, tmp_path):
    output = tmp_path / "deck.html"
    subprocess.run([sys.executable, str(CLI), "new", "--template", str(ASSETS / name), "--output", str(output), "--title", "Neu"], check=True, capture_output=True)
    source = output.read_text()
    slides = _slides(source)
    assert slides and not any(marked for _, marked in slides)
    assert "data-sf-overview" not in source
    meta = json.loads(re.search(r'<script id="sf-document" type="application/json">(.*?)</script>', source, re.S).group(1))
    assert set(meta["notes"]) == set(meta["guidance"]) == {identity for identity, _ in slides}
    subprocess.run([sys.executable, str(CLI), "validate", str(output)], check=True, capture_output=True)
