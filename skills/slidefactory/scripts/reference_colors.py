#!/usr/bin/env python3
"""Colors-only derivative for the explicit #stage/section.slide/theme-lab family.

This is not a SlideFactory schema conversion or a universal HTML importer. It
keeps the source's existing editor, layout, notes, and assets. All code here is
generic; no reference document, palette, CSS, function, or asset is packaged.
"""

import argparse
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import sys

from deck import COLOR, Deck, DeckError, SourceParser, atomic_write, json_source, patched, read_source


SCHEMES = ("cyan-dark", "cyan-light", "indigo-dark", "indigo-light")
LEGACY_VARS = ("bg", "navy", "panel", "cyan", "blue", "teal", "purple", "amber", "muted", "dim", "line")
COLOR_LITERAL = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\(\s*[\d.]+\s*,\s*[\d.]+\s*,\s*[\d.]+(?:\s*,\s*[\d.]+)?\s*\)|\b(?:white|black)\b", re.I)
# A stylesheet paint can reach masks, clip paths, or filters through any class
# selector/inheritance. Its semantic role cannot be inferred from the selector.
# Keep all stylesheet fill/stroke values opaque. Existing variable-based diagram
# paints still follow the bridged palette; SVG attributes/generated paint strings
# are mapped separately with explicit mask/clip/filter ancestry exclusions.
COLOR_PROPERTIES = {"color", "background", "background-color", "background-image", "border", "border-color", "border-top", "border-right", "border-bottom", "border-left", "border-top-color", "border-right-color", "border-bottom-color", "border-left-color", "outline", "outline-color", "text-decoration-color"}
HOOK_IDS = {"sf-reference-color-schemes", "sf-reference-color-state", "sf-reference-color-runtime", "sf-reference-color-style"}


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def rgb(value):
    value = value.strip().lower()
    if value in {"white", "black"}:
        return (255, 255, 255, 1.0) if value == "white" else (0, 0, 0, 1.0)
    if COLOR.fullmatch(value):
        digits = value[1:]
        if len(digits) == 3:
            digits = "".join(char * 2 for char in digits)
        return tuple(int(digits[index:index + 2], 16) for index in (0, 2, 4)) + ((int(digits[6:8], 16) / 255) if len(digits) == 8 else 1.0,)
    match = re.fullmatch(r"rgba?\(([^)]+)\)", value)
    if match:
        values = [float(item.strip()) for item in match[1].split(",")]
        if len(values) in {3, 4} and all(math.isfinite(item) for item in values) and all(0 <= item <= 255 for item in values[:3]):
            alpha = values[3] if len(values) == 4 else 1.0
            if 0 <= alpha <= 1:
                return tuple(values[:3]) + (alpha,)
    return None


def luminance(channels):
    linear = [channel / 255 / 12.92 if channel / 255 <= .04045 else ((channel / 255 + .055) / 1.055) ** 2.4 for channel in channels[:3]]
    return sum(channel * weight for channel, weight in zip(linear, (.2126, .7152, .0722)))


def semantic_color(value, property_name, originals):
    channels = rgb(value)
    if channels is None:
        return value
    color, alpha = channels[:3], channels[3]
    # White image mattes remain white. Pixel/filter/mask properties are excluded.
    if property_name.startswith("background") and min(color) >= 240:
        return value
    exact = next((name for name, original in originals.items() if name != "line" and rgb(original) and rgb(original)[:3] == color), None)
    if exact:
        variable = "--" + exact
    elif property_name.startswith("background"):
        variable = "--sf-ref-surface"
    elif property_name.startswith(("border", "outline")):
        variable = "--sf-ref-border"
    else:
        variable = "--sf-ref-text" if luminance(channels) >= .8 or max(color) < 70 else "--sf-ref-muted"
    if alpha == 1:
        return f"var({variable})"
    return f"color-mix(in srgb,var({variable}) {alpha * 100:g}%,transparent)"


def declarations(css):
    """Yield value spans without splitting strings, comments, fonts, or URLs."""
    start, colon, quote, parentheses, comment = 0, None, None, 0, False
    index = 0
    while index < len(css):
        char = css[index]
        if comment:
            if css.startswith("*/", index):
                comment = False
                index += 2
                continue
        elif quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
        elif css.startswith("/*", index):
            comment = True
            index += 2
            continue
        elif char in {"'", '"'}:
            quote = char
        elif char == "(":
            parentheses += 1
        elif char == ")":
            parentheses = max(0, parentheses - 1)
        elif not parentheses:
            if char == ":" and colon is None:
                colon = index
            elif char in {";", "}", "{"}:
                if char != "{" and colon is not None:
                    name = re.sub(r"/\*.*?\*/", "", css[start:colon], flags=re.S).strip().lower()
                    if name in COLOR_PROPERTIES:
                        yield name, colon + 1, index
                start, colon = index + 1, None
        index += 1


def protected_ranges(value):
    # A complete url(...) is opaque, including quoted data payloads. Generic
    # strings/comments are opaque too; a color cannot be a CSS quoted string.
    pattern = re.compile(r"/\*.*?\*/|url\(\s*(?:\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|[^)]*)\s*\)|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'", re.I | re.S)
    return [(match.start(), match.end()) for match in pattern.finditer(value)]


def recolor_css(css, originals):
    edits = []
    for name, start, end in declarations(css):
        value = css[start:end]
        protected = protected_ranges(value)
        for match in COLOR_LITERAL.finditer(value):
            if any(left <= match.start() < right for left, right in protected):
                continue
            replacement = semantic_color(match[0], name, originals)
            if replacement != match[0]:
                edits.append((start + match.start(), start + match.end(), replacement))
    return patched(css, edits), len(edits)


def recolor_draw_script(script, originals):
    # Only SVG paint attributes in generated element strings are touched. The
    # containing reference functions, geometry strings, notes, and editor logic
    # remain source-identical. Masks/filters and arbitrary JS colors are opaque.
    paints = re.compile(r"(\b(stroke|fill)\s*=\s*['\"])(#[0-9a-fA-F]{3,8})(['\"])", re.I)
    tag_context = re.compile(r"<(/?)([A-Za-z]+)\b")
    svg_tags = {"path","line","polyline","polygon","circle","ellipse","rect","marker","svg"}
    protected = [(match.start(),match.end()) for match in re.finditer(r"<(mask|clipPath|filter)\b[^>]*>.*?</\1\s*>",script,re.I|re.S)]
    count = 0

    def substitute(match):
        nonlocal count
        value = semantic_color(match[3], match[2].lower(), originals)
        if value != match[3]:
            count += 1
        return match[1] + value + match[4]

    def element(match):
        if any(left<=match.start()<right for left,right in protected):
            return match[0]
        # Generated path data can contain template expressions with < or >
        # comparisons. Their angle characters are not markup boundaries.
        context = list(tag_context.finditer(script[:match.start()]))
        if not context or context[-1][1] or context[-1][2].lower() not in svg_tags:
            return match[0]
        return substitute(match)

    return paints.sub(element, script), count


def recognize(source):
    parser = SourceParser(source)
    nodes = parser.nodes
    if any(node.attrs.get("id") in HOOK_IDS for node in nodes):
        raise DeckError("This file already has the colors adapter; select its scheme in the browser.")
    if any(node.attrs.get("id") == "sf-document" for node in nodes):
        raise DeckError("Use deck.py scheme for native SlideFactory files.")

    def one(identity, tag=None):
        matches = [node for node in nodes if node.attrs.get("id") == identity and (tag is None or node.tag == tag)]
        if len(matches) != 1:
            raise DeckError("Unsupported reference family: need #stage with section.slide and a .theme-lab picker.")
        return matches[0]

    stage = one("stage")
    lab = one("theme-lab")
    select, custom = one("theme-select", "select"), one("theme-color", "input")
    slides = [node for node in nodes if node.tag == "section" and node.inside(stage) and "slide" in (node.attrs.get("class") or "").split()]
    head = [node for node in nodes if node.tag == "head"]
    body = [node for node in nodes if node.tag == "body"]
    if not slides or "theme-lab" not in (lab.attrs.get("class") or "").split() or not select.inside(lab) or not custom.inside(lab) or len(head) != 1 or len(body) != 1:
        raise DeckError("Unsupported reference family: need #stage with section.slide and a .theme-lab picker.")
    if any(not node.attrs.get("id") for node in slides) or len({node.attrs["id"] for node in slides}) != len(slides):
        raise DeckError("Reference slide IDs must exist and be unique.")
    styles = [node for node in nodes if node.tag == "style"]
    originals = {}
    for style in styles:
        css = source[style.open_end:style.close_start]
        for match in re.finditer(r"--([a-z]+)\s*:\s*(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\))", css):
            if match[1] in LEGACY_VARS:
                originals.setdefault(match[1], match[2])
    if set(LEGACY_VARS) - set(originals):
        raise DeckError("Unsupported reference palette: expected explicit bg/navy/panel/cyan/blue/teal/purple/amber/muted/dim/line variables.")
    return {"parser": parser, "nodes": nodes, "slides": slides, "select": select, "styles": styles, "head": head[0], "body": body[0], "originals": originals}


# This runtime is newly authored generic adapter logic; it contains no reference
# editor implementation or reference document content.
RUNTIME = r'''(() => {
  'use strict';
  const root = document.documentElement;
  const schemes = JSON.parse(document.getElementById('sf-reference-color-schemes').textContent);
  const stateNode = document.getElementById('sf-reference-color-state');
  const state = JSON.parse(stateNode.textContent);
  const select = document.getElementById('theme-select');
  const custom = document.getElementById('theme-color');
  const stage = document.getElementById('stage');
  const originals = state.originals;
  const pattern = /#[0-9a-fA-F]{3,8}\b|rgba?\(\s*[\d.]+\s*,\s*[\d.]+\s*,\s*[\d.]+(?:\s*,\s*[\d.]+)?\s*\)|\b(?:white|black)\b/gi;
  function rgb(value) {
    value = String(value).trim().toLowerCase();
    if (value === 'white') return [255,255,255,1];
    if (value === 'black') return [0,0,0,1];
    if (/^#[\da-f]{3}$/.test(value)) value = '#' + [...value.slice(1)].map(c=>c+c).join('');
    if (/^#[\da-f]{6}([\da-f]{2})?$/.test(value)) return [1,3,5].map(i=>parseInt(value.slice(i,i+2),16)).concat(value.length === 9 ? parseInt(value.slice(7,9),16)/255 : 1);
    const match = value.match(/^rgba?\(([^)]+)\)$/);
    if (!match) return null;
    const result = match[1].split(',').map(Number);
    return result.length === 3 ? result.concat(1) : result;
  }
  function lum(value) { const c=rgb(value).slice(0,3).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return c[0]*.2126+c[1]*.7152+c[2]*.0722; }
  function contrast(a,b) { const x=lum(a),y=lum(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05); }
  function readable(value,background,text) {
    if (contrast(value,background)>=4.5) return value;
    const original=rgb(value),target=rgb(text);
    for(let weight=.05;weight<=1.01;weight+=.05){const channels=original.slice(0,3).map((v,i)=>Math.round(v+(target[i]-v)*Math.min(1,weight)));const candidate='#'+channels.map(v=>v.toString(16).padStart(2,'0')).join('');if(contrast(candidate,background)>=4.5)return candidate;}
    return text;
  }
  function paint(value,property) {
    const channels=rgb(value);if(!channels)return value;
    if(property.startsWith('background')&&Math.min(...channels.slice(0,3))>=240)return value;
    const exact=Object.keys(originals).find(key=>key!=='line'&&rgb(originals[key])&&rgb(originals[key]).slice(0,3).every((v,i)=>v===channels[i]));
    let variable=exact?'--'+exact:property.startsWith('background')?'--sf-ref-surface':property.startsWith('border')?'--sf-ref-border':lum(value)>=.8||Math.max(...channels.slice(0,3))<70?'--sf-ref-text':'--sf-ref-muted';
    return channels[3]===1?'var('+variable+')':'color-mix(in srgb,var('+variable+') '+channels[3]*100+'%,transparent)';
  }
  function refreshPaints() {
    for(const node of stage.querySelectorAll('[style]')) {
      if(node.closest('mask,clipPath,filter'))continue;
      for(const property of ['color','background','background-color','border-color','stroke','fill']) {
        const value=node.style.getPropertyValue(property);
        if(value && !/url\(/i.test(value)) {const next=value.replace(pattern,color=>paint(color,property));if(next!==value)node.style.setProperty(property,next,node.style.getPropertyPriority(property));}
      }
    }
    for(const node of stage.querySelectorAll('svg [stroke],svg [fill]')) {
      if(node.closest('mask,clipPath,filter'))continue;
      for(const property of ['stroke','fill']) {const value=node.getAttribute(property);if(value&&rgb(value)){const next=paint(value,property);if(next!==value)node.setAttribute(property,next);}}
    }
  }
  function apply(id) {
    if(!schemes[id])return;
    const t=schemes[id].tokens;
    const values={'sf-ref-background':t.background,'sf-ref-text':t.text,'sf-ref-muted':t.muted,'sf-ref-surface':t.surface,'sf-ref-border':t.border,bg:t.background,navy:t.surface,panel:t.surface,cyan:readable(t.accent,t.background,t.text),blue:readable(t.accent2,t.background,t.text),teal:readable(t.accent,t.background,t.text),purple:readable(originals.purple,t.background,t.text),amber:readable(originals.amber,t.background,t.text),muted:t.muted,dim:t.muted,line:t.border};
    for(const [key,value] of Object.entries(values))root.style.setProperty('--'+key,value);
    root.dataset.sfReferenceScheme=id;
    root.dataset.sfReferenceMode=lum(t.background)>.5?'light':'dark';
    select.value=id;
    state.scheme=id;
    stateNode.textContent=JSON.stringify(state).replace(/</g,'\\u003c');
    refreshPaints();
    document.dispatchEvent(new CustomEvent('sf:reference-colors',{detail:{scheme:id}}));
  }
  select.setAttribute('aria-label','Farbschema');
  const label=document.querySelector('label[for="theme-select"]');
  if(label)label.textContent='Farbschema';
  custom.hidden=true;custom.disabled=true;custom.setAttribute('aria-hidden','true');
  select.addEventListener('change',event=>{event.stopImmediatePropagation();event.preventDefault();apply(select.value);},true);
  const observer=new MutationObserver(()=>refreshPaints());
  observer.observe(stage,{childList:true,subtree:true});
  apply(state.scheme);
})();'''


def assets(source):
    return [digest(match[0]) for match in re.finditer(r"data:[^\s\"'<>)]*", source)]


def outer(source, node):
    return source[node.start:node.end]


def witnesses(before, after, original_family):
    parsed = SourceParser(after)
    after_ids = [node.attrs.get("id") for node in parsed.nodes if node.attrs.get("id")]
    original_ids = [node.attrs.get("id") for node in original_family["nodes"] if node.attrs.get("id")]
    after_map = {node.attrs.get("id"): node for node in parsed.nodes if node.attrs.get("id")}
    slides = original_family["slides"]
    notes = [node for node in original_family["nodes"] if node.tag == "template" and (node.attrs.get("id") or "").startswith("note-")]
    return {"slidesByteIdentical": all(node.attrs["id"] in after_map and outer(before,node)==outer(after,after_map[node.attrs["id"]]) for node in slides), "notesByteIdentical": all(node.attrs["id"] in after_map and outer(before,node)==outer(after,after_map[node.attrs["id"]]) for node in notes), "assetsByteIdentical": assets(before)==assets(after), "originalIdsRetained": [identity for identity in after_ids if identity in set(original_ids)]==original_ids, "slideCount": len(slides), "noteCount": len(notes), "embeddedAssetCount": len(assets(before)), "slideBytesSha256": digest("".join(outer(before,node) for node in slides)), "noteBytesSha256": digest("".join(outer(before,node) for node in notes)), "assetReferencesSha256": digest("".join(assets(before))), "originalIdsSha256": digest(json.dumps(original_ids))}


def adapt(file, output, template, scheme):
    source_path, target = Path(file), Path(output)
    if source_path.resolve() == target.resolve() or target.exists() and os.path.samefile(source_path,target):
        raise DeckError("--output must be a separate derivative file; the original is never mutated.")
    source = read_source(source_path)
    family = recognize(source)
    schemes = Deck(read_source(template)).schemes
    if any(identity not in schemes for identity in SCHEMES) or scheme not in SCHEMES:
        raise DeckError("Need packaged cyan-dark/cyan-light/indigo-dark/indigo-light schemes and a known --scheme.")
    selected = {identity: schemes[identity] for identity in SCHEMES}
    edits, css_count, draw_count = [], 0, 0
    for style in family["styles"]:
        css = source[style.open_end:style.close_start]
        replacement, count = recolor_css(css,family["originals"])
        if count:
            edits.append((style.open_end,style.close_start,replacement))
            css_count += count
    for script in family["nodes"]:
        if script.tag == "script" and script.attrs.get("type") != "application/json":
            replacement, count = recolor_draw_script(source[script.open_end:script.close_start],family["originals"])
            if count:
                edits.append((script.open_end,script.close_start,replacement))
                draw_count += count
    options = "".join(f'<option value="{identity}">{html.escape(selected[identity]["label"])}</option>' for identity in SCHEMES)
    select = family["select"]
    edits.append((select.open_end,select.close_start,options))
    newline = "\r\n" if "\r\n" in source else "\n"
    style = '<style id="sf-reference-color-style">html,body{color:var(--sf-ref-text)}.theme-lab select{color:var(--sf-ref-text);background:var(--sf-ref-surface);border-color:var(--sf-ref-border)}</style>'
    edits.append((family["head"].close_start,family["head"].close_start,newline+style+newline))
    extension = (f'<script id="sf-reference-color-schemes" type="application/json">{json_source(selected)}</script>' + newline + f'<script id="sf-reference-color-state" type="application/json">{json_source({"scheme":scheme,"originals":family["originals"]})}</script>' + newline + '<script id="sf-reference-color-runtime">' + RUNTIME.replace("\n",newline) + '</script>')
    edits.append((family["body"].close_start,family["body"].close_start,newline+extension+newline))
    result = patched(source,edits)
    proof = witnesses(source,result,family)
    if not all(proof[key] for key in ("slidesByteIdentical","notesByteIdentical","assetsByteIdentical","originalIdsRetained")):
        raise DeckError("Preservation witness failed; derivative was not written.")
    atomic_write(target,result,source_path)
    return {"output":str(target.resolve()),"family":"stage-slide-theme-lab","scope":"colors-only; existing editor unchanged","scheme":scheme,"schemes":list(selected),"originalSha256":digest(source),"derivativeSha256":digest(result),"cssColorReplacements":css_count,"svgDrawColorReplacements":draw_count,"witnesses":proof}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file")
    parser.add_argument("--output",required=True)
    parser.add_argument("--scheme",default="cyan-dark")
    parser.add_argument("--schemes-template",default=str(Path(__file__).resolve().parents[1]/"assets"/"starter.html"))
    args = parser.parse_args()
    try:
        print(json.dumps(adapt(args.file,args.output,args.schemes_template,args.scheme),indent=2))
        return 0
    except (DeckError,OSError,UnicodeError) as error:
        print(f"SlideFactory reference colors: {error}",file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
