"""Helper parity for optional schema-1 migration fields (no browser dependency)."""
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
HELPER=ROOT/'skills/slidefactory/scripts/deck.py'
STARTER=ROOT/'skills/slidefactory/assets/consulting.html'


def run(path,command='validate'):
    return subprocess.run([sys.executable,str(HELPER),command,str(path)],capture_output=True,text=True)


def test_layout_notes_provenance_and_duration_parity(tmp_path):
    source=STARTER.read_text()
    # The existing starter text identity is discovered, preserving fixture independence.
    import re
    node=re.search(r'<[^>]+data-sf-kind="text"[^>]*>',source)[0]
    identity=re.search(r'data-sf-id="([^"]+)"',node)[1]
    slide=re.search(r'data-sf-slide="([^"]+)"',source)[1]
    native=tmp_path/'native.html'
    for mode in ('flow','inline'):
        candidate=source.replace(node,node[:-1]+f' data-sf-layout="{mode}" style="translate:5px 6px;left:7px;top:8px;transform:rotate(2deg)">') if 'style=' not in node else source.replace(node,node[:-1]+f' data-sf-layout="{mode}">')
        native.write_text(candidate)
        result=run(native,'inspect'); assert result.returncode==0,result.stderr
        objects={obj['id']:obj for s in json.loads(result.stdout)['slides'] for obj in s['objects']}
        assert objects[identity]['layout']==mode
        assert 'offsets' in objects[identity]
    for marker in ('bogus',''):
        native.write_text(source.replace(node,node[:-1]+f' data-sf-layout="{marker}">'))
        assert run(native).returncode != 0
    raw=re.search(r'<script id="sf-document" type="application/json">(.*?)</script>',source,re.S)[1]
    meta=json.loads(raw)
    for provenance in ({slide:{'html':'<p>Rich</p>','text':'Rich'}},{slide:{'html':3,'text':'Rich'}},{'missing':{'html':'Rich','text':'Rich'}}):
        meta['notesProvenance']=provenance; native.write_text(source.replace(raw,json.dumps(meta)))
        assert (run(native).returncode==0)==(slide in provenance and isinstance(provenance[slide]['html'],str))
    for value in ('NaN','0','-1','.5','1.'):
        native.write_text(source.replace(f'data-sf-slide="{slide}"',f'data-sf-slide="{slide}" data-sf-duration="{value}"'))
        assert run(native).returncode!=0
    image=re.search(r'<[^>]+data-sf-kind="image"[^>]*>',source)[0]
    native.write_text(source.replace(image,image[:-1]+' data-sf-layout="flow">'))
    assert run(native).returncode!=0
