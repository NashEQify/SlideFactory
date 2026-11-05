#!/usr/bin/env python3
"""Convert the bounded saved v19 stage/slide family into a separate native HTML.

Python/Playwright/Chromium are conversion-only tools. Ready output and deck.py
remain standalone/offline. Private styles/assets/design functions are read from
an explicit source at execution; none are packaged in this generic converter.
"""
import argparse
from collections import Counter
import hashlib
import html
import math
import os
from pathlib import Path
import re
import sys
import uuid

from deck import (Deck, DeckError, SourceParser, atomic_write, image_data, json_source,
                  json_value, number, patched, read_source)
from reference_colors import recognize as recognize_colors, recolor_css, recolor_draw_script, semantic_color, SCHEMES

HERE = Path(__file__).resolve().parent
DEFAULT_TEMPLATE = HERE.parent / 'assets/starter.html'


def digest(source):
    return hashlib.sha256(source.encode('utf-8')).hexdigest()


def recognize(source):
    if re.search(r'\bid\s*=\s*[\'"]sf-document[\'"]', source):
        raise DeckError('Already native SlideFactory input; continue from that saved file with deck.py.')
    family = recognize_colors(source)
    nodes,slides=family['nodes'],family['slides']
    ids=[n.attrs.get('data-edit-id') for n in nodes if n.attrs.get('data-edit-id')]
    targets=[n for n in nodes if n.attrs.get('data-edit-id')]
    if not targets or len(set(ids))!=len(ids) or any(n.attrs.get('data-edit-kind') not in {'text','box','icon'} for n in targets):
        raise DeckError('Unsupported reference family: require unique legacy IDs and text|box|icon kinds.')
    if any(not any(n.inside(slide) for slide in slides) for n in targets):
        raise DeckError('Unsupported reference family: every legacy target must belong to one slide.')
    if any(not re.fullmatch(r'slide-[a-zA-Z0-9-]+',slide.attrs['id']) for slide in slides):
        raise DeckError('Unsupported reference family: expected stable slide-* IDs.')
    notes={}
    for slide in slides:
        wanted='note-'+slide.attrs['id'][6:]
        matches=[n for n in nodes if n.tag=='template' and n.attrs.get('id')==wanted]
        if len(matches)!=1:
            raise DeckError('Unsupported reference family: each slide requires its ID-suffixed note template.')
        notes[slide.attrs['id']]=source[matches[0].open_end:matches[0].close_start]
        if slide.attrs.get('data-time'):
            try: seconds=float(slide.attrs['data-time'])*60
            except (TypeError,ValueError): raise DeckError('Reference duration must be finite nonnegative minutes.')
            number(seconds,'Reference duration')
            if seconds<0: raise DeckError('Reference duration must be nonnegative.')
    scripts='\n'.join(source[n.open_end:n.close_start] for n in nodes if n.tag=='script' and n.attrs.get('type')!='application/json')
    found=re.findall(r'\b(?:const|let)\s+deckId\s*=\s*([\'"])([^\'"\r\n]+)\1',scripts)
    notes_id=found[0][1] if found else None
    family.update(targetIds=ids,noteHtml=notes,script=scripts,legacyNotesDeckId=notes_id)
    return family


PATCH_STYLES={
    'color':r'#[0-9a-fA-F]{6}', 'borderColor':r'#[0-9a-fA-F]{6}',
    'background':r'(?:transparent|#[0-9a-fA-F]{6})', 'backgroundColor':r'(?:transparent|#[0-9a-fA-F]{6})',
    'fontFamily':r'[A-Za-z][A-Za-z0-9 -]*', 'fontSize':r'\d+(?:\.\d+)?px',
    'fontWeight':r'(?:normal|bold|[1-9]00)', 'fontStyle':r'(?:normal|italic)',
    'textDecoration':r'(?:none|underline|line-through)', 'textAlign':r'(?:left|center|right)',
    'lineHeight':r'\d+(?:\.\d+)?', 'width':r'\d+(?:\.\d+)?px', 'height':r'\d+(?:\.\d+)?px',
}


def embedded_state(source,family):
    matches=[n for n in family['nodes'] if n.attrs.get('id')=='editor-document-state']
    if not matches:return None
    if len(matches)!=1 or matches[0].tag!='script' or matches[0].attrs.get('type')!='application/json':
        raise DeckError('Malformed embedded state element.')
    state=json_value(source[matches[0].open_end:matches[0].close_start],'Embedded state')
    root=next(n for n in family['nodes'] if n.tag=='html')
    document_id=root.attrs.get('data-edit-document')
    if not isinstance(state,dict) or type(state.get('schema')) is not int or state.get('schema')!=1 or not isinstance(state.get('documentId'),str) or state.get('documentId')!=document_id:
        raise DeckError('Embedded state schema/document identity mismatch.')
    number(state.get('revision'),'Embedded state revision')
    if state['revision']<0:raise DeckError('Embedded state revision must be nonnegative.')
    bases,patches,added=state.get('baselines',{}),state.get('patches',{}),state.get('added',[])
    if not isinstance(bases,dict) or not isinstance(patches,dict) or not isinstance(added,list) or len(added)>100:
        raise DeckError('Malformed embedded state maps or additions.')
    ids=set(family['targetIds']);slides={s.attrs['id'] for s in family['slides']}
    for item in added:
        if not isinstance(item,dict) or not isinstance(item.get('id'),str) or not re.fullmatch(r'add-[a-z0-9-]+',item['id']) or item['id'] in ids or item.get('slideId') not in slides:
            raise DeckError('Embedded state has invalid added object reference.')
        ids.add(item['id'])
    for identity,base in bases.items():
        if identity not in ids or not isinstance(base,dict) or base.get('kind') not in {'text','box','icon'} or not isinstance(base.get('style'),str) or (not isinstance(base.get('html'),str) if base.get('kind')=='text' else base.get('html') is not None):
            raise DeckError('Embedded state has an invalid baseline reference/value.')
        resources=re.findall(r'url\(\s*[\'"]?(.*?)[\'"]?\s*\)',base['style'],re.I)
        if any(not value.startswith(('data:','#')) for value in resources) or re.search(r'@import|expression\(',base['style'],re.I):
            raise DeckError('Embedded baseline has unsupported CSS dependencies.')
    for identity,patch in patches.items():
        if identity not in ids or not isinstance(patch,dict):raise DeckError('Embedded state has an unknown patch reference.')
        for key in ('x','y'):
            if key in patch:number(patch[key],'Embedded patch '+key)
        if abs(patch.get('x',0))>1920 or abs(patch.get('y',0))>1080:raise DeckError('Embedded patch offset exceeds the source canvas bound.')
        if 'hidden' in patch and type(patch['hidden']) is not bool:raise DeckError('Embedded patch hidden must be boolean.')
        styles=patch.get('styles',{})
        if not isinstance(styles,dict) or any(k not in PATCH_STYLES or not isinstance(v,str) or not re.fullmatch(PATCH_STYLES[k],v) for k,v in styles.items()):
            raise DeckError('Embedded patch has unsupported styles.')
        if 'html' in patch:
            if not isinstance(patch['html'],str):raise DeckError('Embedded patch HTML must be a string.')
            parsed=SourceParser(patch['html'])
            if any(n.tag not in {'b','strong','i','em','u','span','br'} or any(a!='style' for a in n.attrs) for n in parsed.nodes):
                raise DeckError('Embedded patch has unsupported text markup.')
    return {**state,'baselines':bases,'patches':patches,'added':added}


def extract_function(script,name):
    """Balanced bounded declaration extraction; literals/comments remain opaque."""
    match=re.search(r'\bfunction\s+'+re.escape(name)+r'\s*\(',script)
    if not match:raise DeckError(f'Live producer {name} is missing.')
    start=script.find('{',match.end());depth=0;quote=None;comment=None;i=start
    while i<len(script):
        char=script[i]
        if comment:
            if comment=='//' and char=='\n':comment=None
            elif comment=='/*' and script.startswith('*/',i):comment=None;i+=1
        elif quote:
            if char=='\\':i+=1
            elif char==quote:quote=None
        elif char in '\'"`':quote=char
        elif script.startswith('//',i):comment='//';i+=1
        elif script.startswith('/*',i):comment='/*';i+=1
        elif char=='{':depth+=1
        elif char=='}':
            depth-=1
            if depth==0:return script[match.start():i+1]
        i+=1
    raise DeckError(f'Unbalanced live producer {name}.')


def live_hooks(family):
    declarations=[]
    for selector,name in (('asset-wheel','drawAsset'),('tom-layout','drawTom')):
        if not any(selector in (n.attrs.get('class') or '').split() for n in family['nodes']):continue
        body=extract_function(family['script'],name)
        # This finite source family puts its initial label-placement phase last.
        # Capture has baked that phase; preserve only its measured connector phase.
        if name=='drawTom' and re.search(r'\bconst\s+label\s*=',body):
            beginning=re.search(r'\bconst\s+label\s*=',body).start()
            if not body.rstrip().endswith('});}'):raise DeckError('Unsupported live label producer structure.')
            body=body[:beginning]+'});}'
        body=body.replace('.slide.active .', ':is(.sf-slide[data-sf-runtime-visible="true"],.sf-slide[data-sf-runtime-preview="true"]) .')
        body=body.replace("svg.setAttribute('aria-hidden','true');", "svg.setAttribute('aria-hidden','true');svg.dataset.sfTransient='';")
        if name=='drawTom':
            body=body.replace('const origin=map.getBoundingClientRect()', 'if(!map.clientWidth||!map.clientHeight)return;const origin=map.getBoundingClientRect()')
        body,_=recolor_draw_script(body,family['originals'])
        declarations.append(body)
    if not declarations:return ''
    calls=''.join(name+'();' for name in ('drawAsset','drawTom') if any(re.match(r'function\s+'+name+r'\(',d) for d in declarations))
    return "(() => {'use strict';\n"+'\n'.join(declarations)+"\nlet scheduled=false;function redraw(){scheduled=false;"+calls+"}function schedule(event){if(event?.target?.closest?.('[data-sf-runtime-preview=\"true\"]')){redraw();return;}if(!scheduled){scheduled=true;requestAnimationFrame(redraw);}}for(const event of ['sf:ready','sf:layout','sf:view'])document.addEventListener(event,schedule);addEventListener('resize',schedule);document.fonts?.ready.then(schedule);})();"


def recolor_fragment(fragment, originals):
    """Apply the pure semantic bridge to authored DOM paint, preserving masks."""
    parser=SourceParser(fragment);edits=[]
    for node in parser.nodes:
        if node.tag in {'mask','clippath','filter'} or any(parent.tag in {'mask','clippath','filter'} and node.inside(parent) for parent in parser.nodes):
            continue
        opening=fragment[node.start:node.open_end];replacement=opening
        if 'style' in node.attrs:
            css,_=recolor_css(node.attrs['style'],originals)
            replacement=re.sub(r'\bstyle="[^"]*"',lambda m:'style="'+html.escape(css,quote=True)+'"',replacement,count=1)
        for attribute in ('fill','stroke'):
            if attribute in node.attrs:
                paint=semantic_color(node.attrs[attribute],attribute,originals)
                replacement=re.sub(r'\b'+attribute+r'="[^"]*"',lambda m:attribute+'="'+html.escape(paint,quote=True)+'"',replacement,count=1)
        if opening!=replacement:edits.append((node.start,node.open_end,replacement))
    return patched(fragment,edits)


BRIDGE_RUNTIME = r'''(() => {
'use strict';const originals=JSON.parse(document.getElementById('sf-reference-colors').textContent);
function rgb(v){v=v.trim().toLowerCase();if(/^#[\da-f]{3}$/.test(v))v='#'+[...v.slice(1)].map(c=>c+c).join('');if(/^#[\da-f]{6}([\da-f]{2})?$/.test(v))return[1,3,5].map(i=>parseInt(v.slice(i,i+2),16));const m=v.match(/^rgba?\(([^)]+)\)$/);return m?m[1].split(',').slice(0,3).map(Number):null;}
function lum(v){const c=rgb(v).map(x=>x/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4);return c[0]*.2126+c[1]*.7152+c[2]*.0722;}
function contrast(a,b){const x=lum(a),y=lum(b);return(Math.max(x,y)+.05)/(Math.min(x,y)+.05);}
function readable(v,b,t){if(contrast(v,b)>=4.5)return v;const o=rgb(v),q=rgb(t);for(let w=.05;w<=1.01;w+=.05){const c='#'+o.map((v,i)=>Math.round(v+(q[i]-v)*Math.min(1,w)).toString(16).padStart(2,'0')).join('');if(contrast(c,b)>=4.5)return c;}return t;}
function apply(){const css=getComputedStyle(document.documentElement),token=k=>css.getPropertyValue('--sf-'+k).trim(),b=token('background'),t=token('text');if(!rgb(b)||!rgb(t))return;for(const [k,v]of Object.entries({cyan:readable(token('accent'),b,t),blue:readable(token('accent2'),b,t),teal:readable(token('accent'),b,t),purple:readable(originals.purple,b,t),amber:readable(originals.amber,b,t)}))document.documentElement.style.setProperty('--'+k,v);}
new MutationObserver(apply).observe(document.getElementById('sf-theme-tokens'),{subtree:true,childList:true,characterData:true});document.addEventListener('sf:ready',apply);
})();'''
BRIDGE_CSS = ':root{--bg:var(--sf-background);--navy:var(--sf-surface);--panel:var(--sf-surface);--cyan:var(--sf-accent);--blue:var(--sf-accent2);--teal:var(--sf-accent);--muted:var(--sf-muted);--dim:var(--sf-muted);--line:var(--sf-border);--sf-ref-background:var(--sf-background);--sf-ref-text:var(--sf-text);--sf-ref-muted:var(--sf-muted);--sf-ref-surface:var(--sf-surface);--sf-ref-border:var(--sf-border)}'


def capture(source,family,state,chromium):
    try:from playwright.sync_api import sync_playwright, Error as BrowserError
    except ImportError as error:raise DeckError('Conversion requires optional Python Playwright and Chromium; ready HTML/deck.py do not. Install development tooling separately or supply an environment with Playwright.') from error
    removed=[(n.start,n.end,'') for n in family['nodes'] if n.attrs.get('id')=='editor-document-state']
    rendered=patched(source,removed)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=chromium or None,headless=True,args=['--no-sandbox'])
            context=browser.new_context(viewport={'width':1920,'height':1080})
            context.route('**/*',lambda route: route.abort() if route.request.url.startswith(('http:','https:')) else route.continue_())
            page=context.new_page();page.set_content(rendered,wait_until='load',timeout=60000)
            result=page.evaluate((HERE/'reference_migration.js').read_text()+'\ncaptureReference',{'state':state,'noteHtml':family['noteHtml']})
            browser.close();return result
    except BrowserError as error:
        raise DeckError('Conversion browser failed; verify optional Chromium/Playwright and --chromium path. '+str(error).splitlines()[0]) from error


def migrate(file,output,template=DEFAULT_TEMPLATE,scheme='cyan-dark',chromium=None):
    path,target=Path(file),Path(output)
    if path.resolve()==target.resolve() or target.exists() and os.path.samefile(path,target):
        raise DeckError('--output must be a separate derivative file; the original is never mutated.')
    source=read_source(path);family=recognize(source);state=embedded_state(source,family)
    native=Deck(read_source(template))
    if scheme not in SCHEMES or any(s not in native.schemes for s in SCHEMES):raise DeckError('Need the packaged four schemes and a known --scheme.')
    result=capture(source,family,state,chromium)
    original_sha=digest(source)
    metadata={'schemaVersion':1,'deckId':str(uuid.uuid4()),'revision':str(uuid.uuid4()),'title':re.sub(r'\s+',' ',html.unescape(next((source[n.open_end:n.close_start] for n in family['nodes'] if n.tag=='title'),'Migrated presentation'))).strip(),'templateId':'reference-v19','templateVersion':'1','colorScheme':scheme,'pageWidth':1600,'pageHeight':900,'notes':result['notes'],'notesProvenance':result['notesProvenance'],'guidance':{s['id']:{'text':'','status':'open'} for s in result['slides']},'migration':{'family':'v19','sourceSha256':original_sha}}
    if family['legacyNotesDeckId']:metadata['migration']['legacyNotesDeckId']=family['legacyNotesDeckId']
    styles=[]
    for n in family['styles']:
        css,_=recolor_css(source[n.open_end:n.close_start],family['originals'])
        # Only the finite source stage selector changes names; its background
        # paints at the retained 1920 canvas, rather than the 1600 native frame.
        styles.append('<style>'+css.replace('#stage','.sf-reference-stage')+'</style>')
    font=html.escape(result['fontFamily'],quote=False)
    override=f'''<style id="sf-reference-layout">{BRIDGE_CSS}
#sf-deck{{width:1600px;height:900px;position:absolute;transform-origin:0 0}}#sf-deck>.sf-slide{{position:relative;width:1600px;height:900px;overflow:hidden;display:block;padding:0;background:var(--bg)}}
.sf-reference-stage{{position:absolute!important;left:0!important;top:0!important;width:1920px!important;height:1080px!important;transform:scale(.8333333333333334)!important;transform-origin:0 0!important;font-family:{font};color:var(--sf-ref-text)}}
.sf-reference-stage .slide{{inset:0;padding-top:65px}}
</style>'''
    tokens=native.schemes[scheme]['tokens'];theme='<style id="sf-theme-tokens">:root{'+''.join('--sf-'+key+':'+value+';' for key,value in tokens.items())+'}</style>'
    slide_html=[]
    for item in result['slides']:
        attrs=''.join(' '+key+'="'+html.escape(value,quote=True)+'"' for key,value in item['mainAttributes'])
        seconds=float(item['duration'])*60 if item['duration'] else 0
        duration='' if seconds==0 else ' data-sf-duration="'+format(seconds,'.12f').rstrip('0').rstrip('.')+'"'
        content=recolor_fragment(item['html'],family['originals'])
        slide_html.append(f'<section class="sf-slide" data-sf-slide="{html.escape(item["id"],quote=True)}"{duration}><div class="sf-reference-stage"><{item["mainTag"]}{attrs}>{content}</{item["mainTag"]}></div></section>')
    # Retain shared global SVG definitions outside slides; remove all UI/scripts.
    definitions=[]
    for n in family['nodes']:
        if n.tag=='svg' and not any(n.inside(s) for s in family['slides']) and not any(parent.tag=='svg' and n.inside(parent) for parent in family['nodes']):
            raw=source[n.start:n.end];raw=raw.replace('<svg','<svg data-sf-definitions=""',1);definitions.append(raw)
    editor=native.outer(native.unique('sf-editor-styles','style'))
    runtime=native.outer(native.unique('sf-runtime','script'))
    private_hooks=live_hooks(family)
    assembled='<!DOCTYPE html>\n<html lang="de" class="audience-mode"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(metadata['title'])+'</title>\n'+theme+'\n'+'\n'.join(styles)+'\n'+override+'\n'+editor+'\n</head><body>\n'+'\n'.join(definitions)+'\n<main id="sf-deck">'+''.join(slide_html)+'</main>\n<script id="sf-document" type="application/json">'+json_source(metadata)+'</script>\n<script id="sf-color-schemes" type="application/json">'+json_source({s:native.schemes[s] for s in SCHEMES})+'</script>\n<script id="sf-reference-colors" type="application/json">'+json_source(family['originals'])+'</script>\n<script id="sf-reference-color-bridge">'+BRIDGE_RUNTIME+'</script>\n'+('<script id="sf-reference-design-hooks">'+private_hooks+'</script>\n' if private_hooks else '')+runtime+'\n</body></html>\n'
    checked=Deck(assembled)
    expected=set(family['targetIds']) | {i['id'] for i in state['added']} if state else set(family['targetIds'])
    if expected-set(checked.objects):raise DeckError('Preservation witness: legacy targets missing; output was not written.')
    image_before=Counter(n.attrs['src'] for n in family['nodes'] if n.tag=='img')
    image_after=Counter(n.attrs['src'] for n in checked.nodes if n.tag=='img')
    fonts_before=re.findall(r'data:font/[^\s\'"<>)]*',source)
    fonts_after=re.findall(r'data:font/[^\s\'"<>)]*',assembled)
    if image_before!=image_after or fonts_before!=fonts_after or list(checked.slides)!=result['order'] or len(checked.meta['notes'])!=len(family['slides']):
        raise DeckError('Preservation witness: originals/fonts/order/notes mismatch; output was not written.')
    if digest(read_source(path))!=original_sha:raise DeckError('Original changed during conversion; output was not written.')
    atomic_write(target,assembled,path)
    return {'output':str(target.resolve()),'family':'v19','originalSha256':original_sha,'derivativeSha256':digest(assembled),'scheme':scheme,'embeddedStateMaterialized':state is not None,'witnesses':{'slidesRetained':len(checked.slides),'legacyTargetsRetained':len(family['targetIds']),'nativeObjects':len(checked.objects),'imagesRetained':sum(image_after.values()),'uniqueImages':len(image_after),'fontFacesRetained':len(fonts_after),'notesRetained':len(checked.meta['notes']),'durationSeconds':sum(float(s.attrs.get('data-sf-duration',0)) for s in checked.slides.values()),'originalUnchanged':True,'standaloneValid':True}}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('file');parser.add_argument('--output',required=True);parser.add_argument('--runtime-template',default=str(DEFAULT_TEMPLATE));parser.add_argument('--scheme',default='cyan-dark');parser.add_argument('--chromium',default=os.environ.get('SF_CHROMIUM_EXECUTABLE'));args=parser.parse_args()
    try:
        import json
        print(json.dumps(migrate(args.file,args.output,args.runtime_template,args.scheme,args.chromium),indent=2));return 0
    except (DeckError,OSError,UnicodeError,ValueError) as error:
        print('SlideFactory reference migration: '+str(error),file=sys.stderr);return 2


if __name__=='__main__':sys.exit(main())
