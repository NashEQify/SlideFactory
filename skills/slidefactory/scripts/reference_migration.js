/* Generic conversion-only DOM capture; no private slide/style/function payloads. */
async function captureReference(options) {
  const slides = [...document.querySelectorAll('#stage section.slide')];
  const before = slides.map(s => s.id), originalImages = [];
  await document.fonts?.ready;
  await Promise.all([...document.images].map(async img => { try { await img.decode(); } catch { throw Error('Source image cannot decode'); } }));
  document.documentElement.classList.add('audience-mode');
  document.documentElement.classList.remove('editor-mode','presenter-mode','preview-mode');
  const pixel = value => `${Math.abs(value) < 1e-8 ? 0 : value}px`;
  const numeric = value => Number.parseFloat(value) || 0;
  const offset = value => value === 'auto' || value === 'none' ? '0px' : value;
  const notePlain = template => {
    const box = document.createElement('div'); box.append(template.content.cloneNode(true));
    box.querySelectorAll('br').forEach(e => e.replaceWith(document.createTextNode('\n')));
    box.querySelectorAll('p,li').forEach(e => e.append(document.createTextNode('\n\n')));
    return box.textContent.trim();
  };
  // Embedded saved edits are applied exactly once after admission. The old
  // embedded JSON was removed before rendering, so its permissive loader cannot
  // silently discard malformed values or replay over this materialization.
  const state = options.state;
  if (state) {
    const targets = new Map([...document.querySelectorAll('[data-edit-id]')].map(e => [e.dataset.editId,e]));
    for (const item of state.added) {
      const element=document.createElement('div');element.className='editor-free-text';
      element.dataset.editId=item.id;element.dataset.editKind='text';element.dataset.editAdded='true';
      document.getElementById(item.slideId).querySelector('.body').append(element);targets.set(item.id,element);
    }
    for (const [id,base] of Object.entries(state.baselines)) {
      const element=targets.get(id); element.setAttribute('style',base.style);
      if(base.kind==='text')element.innerHTML=base.html;
    }
    for (const [id,patch] of Object.entries(state.patches)) {
      const element=targets.get(id); const kind=element.dataset.editKind;
      if(kind==='text' && Object.hasOwn(patch,'html'))element.innerHTML=patch.html;
      for(const [name,value] of Object.entries(patch.styles||{}))element.style[name]=value;
      if((patch.styles?.width||patch.styles?.height)&&getComputedStyle(element).display==='inline')element.style.display='inline-block';
      if(patch.x||patch.y) {
        if(getComputedStyle(element).display==='inline'){element.style.position='relative';element.style.left=pixel(patch.x||0);element.style.top=pixel(patch.y||0);}
        else element.style.transform=(element.style.transform?element.style.transform+' ':'')+`translate(${patch.x||0}px,${patch.y||0}px)`;
      }
      if(patch.hidden)element.style.display='none';
    }
  }
  const captures=[], notes={}, notesProvenance={}, targetIds=[];
  let fontFamily='', imageNumber=0;
  for(let index=0;index<slides.length;index++) {
    const slide=slides[index];
    if(window.deck?.show)window.deck.show(index+1);
    else slides.forEach(s=>s.classList.toggle('active',s===slide));
    await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
    const computed=getComputedStyle(slide);fontFamily ||= computed.fontFamily;
    const clone=slide.cloneNode(true);clone.classList.add('active');clone.removeAttribute('aria-hidden');clone.removeAttribute('inert');
    clone.querySelectorAll('.map-lines,.editor-runtime,.presenter-runtime').forEach(e=>e.remove());
    for (const element of slide.querySelectorAll('[data-edit-id]')) {
      const id=element.dataset.editId, copy=clone.querySelector(`[data-edit-id="${CSS.escape(id)}"]`);
      targetIds.push(id);copy.dataset.sfId=id;copy.dataset.sfKind=element.dataset.editKind==='icon'?'box':element.dataset.editKind;
      copy.removeAttribute('contenteditable');copy.removeAttribute('data-editor-selected');
      const css=getComputedStyle(element);
      if(element.tagName!=='IMG' && css.position!=='absolute' && css.position!=='fixed') {
        if(css.display==='inline') {
          copy.dataset.sfLayout='inline';
          if(css.position!=='static'){copy.style.left=offset(css.left);copy.style.top=offset(css.top);}
        } else {
          copy.dataset.sfLayout='flow';
          const translate=css.translate;
          if(translate!=='none' && !/^[-+.\d]+px(?:\s+[-+.\d]+px){0,2}$/.test(translate))throw Error(`Unsupported authored translate on ${id}`);
          if(translate!=='none')copy.style.translate=translate;
        }
      }
    }
    // Keep initial live labels as authored styles. Connector-only private hooks
    // no longer have permission to position labels after this capture.
    for(const element of slide.querySelectorAll('.tom-evidence,.tom-transfer,.tom-improve,.tom-common-label')) {
      const id=element.dataset.editId;if(!id)throw Error('Live diagram label needs an identity');
      const copy=clone.querySelector(`[data-edit-id="${CSS.escape(id)}"]`);
      for(const name of ['left','top','width'])if(element.style[name])copy.style[name]=element.style[name];
    }
    for(const image of slide.querySelectorAll('img')) {
      const css=getComputedStyle(image), parent=image.parentElement, parentCss=getComputedStyle(parent);
      const imageId=image.dataset.editId;
      const directOnly=!imageId && parent.dataset.editId && [...parent.children].length===1;
      const id=imageId || (directOnly?parent.dataset.editId:`image-migrated-${++imageNumber}`);
      const imgIndex=[...slide.querySelectorAll('img')].indexOf(image), copyImg=[...clone.querySelectorAll('img')][imgIndex];
      const copiedParent=copyImg.parentElement;
      const nw=image.naturalWidth,nh=image.naturalHeight;
      if(!nw||!nh)throw Error('Source image has no natural dimensions');
      originalImages.push(image.getAttribute('src'));
      let slot=copiedParent, actualParent=parent;
      if(!directOnly) {
        // An inline/flex image retains a neutral slot of its original measured
        // dimensions. Only its contained native frame becomes absolute.
        const holder=document.createElement(css.display==='inline'?'span':'div');
        holder.className=copyImg.className;holder.dataset.sfImageSlot='';
        holder.style.cssText=copyImg.style.cssText;
        Object.assign(holder.style,{display:css.display==='inline'?'inline-block':css.display,position:css.position==='static'?'relative':css.position,
          width:pixel(image.offsetWidth),height:pixel(image.offsetHeight),maxWidth:'none',maxHeight:'none',boxSizing:'border-box',
          marginTop:css.marginTop,marginRight:css.marginRight,marginBottom:css.marginBottom,marginLeft:css.marginLeft,verticalAlign:css.verticalAlign,
          flex:css.flex,alignSelf:css.alignSelf,transform:css.transform==='none'?'none':css.transform});
        copyImg.replaceWith(holder);holder.append(copyImg);slot=holder;actualParent=image;
      } else {
        copiedParent.removeAttribute('data-sf-id');copiedParent.removeAttribute('data-sf-kind');copiedParent.removeAttribute('data-sf-layout');
        if(parentCss.position==='static')slot.style.position='relative';
      }
      const r=image.getBoundingClientRect(),pr=actualParent.getBoundingClientRect();
      const sx=r.width/image.offsetWidth,sy=r.height/image.offsetHeight;
      if(!sx||!sy)throw Error('Source image is not visibly measurable');
      const pl=numeric(css.paddingLeft)+numeric(css.borderLeftWidth),pt=numeric(css.paddingTop)+numeric(css.borderTopWidth);
      const cw=image.clientWidth-numeric(css.paddingLeft)-numeric(css.paddingRight),ch=image.clientHeight-numeric(css.paddingTop)-numeric(css.paddingBottom);
      let pw=cw,ph=ch;
      if(css.objectFit==='contain'||css.objectFit==='cover') {
        const scale=(css.objectFit==='contain'?Math.min:Math.max)(cw/nw,ch/nh);pw=nw*scale;ph=nh*scale;
      } else if(css.objectFit==='none'){pw=nw;ph=nh;}
      const positions=css.objectPosition.split(/\s+/),anchor=(value,space)=>value?.endsWith('%')?numeric(value)/100*space:numeric(value);
      let left=r.left+(pl+anchor(positions[0],cw-pw))*sx,top=r.top+(pt+anchor(positions[1]||positions[0],ch-ph))*sy;
      const paint={left,top,right:left+pw*sx,bottom:top+ph*sy};
      let visible={...paint};
      if(css.objectFit==='cover')visible={left:Math.max(left,r.left+pl*sx),top:Math.max(top,r.top+pt*sy),right:Math.min(paint.right,r.left+(pl+cw)*sx),bottom:Math.min(paint.bottom,r.top+(pt+ch)*sy)};
      for(let ancestor=parent;ancestor&&ancestor!==slide;ancestor=ancestor.parentElement) {
        const ac=getComputedStyle(ancestor),ar=ancestor.getBoundingClientRect();
        if(['hidden','clip','scroll','auto'].includes(ac.overflowX)){visible.left=Math.max(visible.left,ar.left+ancestor.clientLeft*(ar.width/ancestor.offsetWidth));visible.right=Math.min(visible.right,ar.right-ancestor.clientLeft*(ar.width/ancestor.offsetWidth));}
        if(['hidden','clip','scroll','auto'].includes(ac.overflowY)){visible.top=Math.max(visible.top,ar.top+ancestor.clientTop*(ar.height/ancestor.offsetHeight));visible.bottom=Math.min(visible.bottom,ar.bottom-ancestor.clientTop*(ar.height/ancestor.offsetHeight));}
      }
      const crop={x:(visible.left-paint.left)/(pw*sx),y:(visible.top-paint.top)/(ph*sy),w:(visible.right-visible.left)/(pw*sx),h:(visible.bottom-visible.top)/(ph*sy)};
      for(const key of Object.keys(crop)){crop[key]=Math.max(0,Math.min(1,crop[key]));if(Math.abs(crop[key])<1e-10)crop[key]=0;if(Math.abs(crop[key]-1)<1e-10)crop[key]=1;}
      if(!crop.w||!crop.h)throw Error('Source image has an empty visible crop');
      const psx=pr.width/(actualParent.offsetWidth||actualParent.clientWidth),psy=pr.height/(actualParent.offsetHeight||actualParent.clientHeight);
      const fw=(visible.right-visible.left)/psx,fh=(visible.bottom-visible.top)/psy;
      const canonicalH=fw/(crop.w*nw/(crop.h*nh)),stretch=fh/canonicalH;
      const frame=document.createElement('div');frame.dataset.sfId=id;frame.dataset.sfKind='image';frame.dataset.sfCrop=JSON.stringify(crop);
      Object.assign(frame.style,{position:'absolute',left:pixel((visible.left-pr.left)/psx-(directOnly?actualParent.clientLeft:0)),top:pixel((visible.top-pr.top)/psy-(directOnly?actualParent.clientTop:0)),width:pixel(fw),height:pixel(canonicalH),overflow:'hidden'});
      if(Math.abs(stretch-1)>1e-5){frame.style.transform=`scaleY(${stretch})`;frame.style.transformOrigin='0 0';}
      copyImg.removeAttribute('data-sf-id');copyImg.removeAttribute('data-sf-kind');copyImg.removeAttribute('data-sf-layout');
      copyImg.setAttribute('width',String(nw));copyImg.setAttribute('height',String(nh));
      Object.assign(copyImg.style,{position:'absolute',display:'block',margin:'0',padding:'0',border:'0',boxSizing:'content-box',transform:'none',objectFit:'fill',objectPosition:'0% 0%',maxWidth:'none',maxHeight:'none',
        width:pixel(fw/crop.w),height:pixel(canonicalH/crop.h),left:pixel(-crop.x*fw/crop.w),top:pixel(-crop.y*canonicalH/crop.h),filter:css.filter,maskImage:css.maskImage,maskSize:css.maskSize,maskPosition:css.maskPosition,maskRepeat:css.maskRepeat});
      frame.append(copyImg);slot.append(frame);
    }
    const template=document.getElementById('note-'+slide.id.replace(/^slide-/,''));
    if(!template || template.tagName!=='TEMPLATE')throw Error('Missing slide note template');
    notes[slide.id]=notePlain(template);notesProvenance[slide.id]={html:options.noteHtml[slide.id],text:notes[slide.id]};
    // Remove old navigation attributes and executable event handlers. URLs used
    // solely as private provenance are inert attributes and may be retained.
    for(const node of [clone,...clone.querySelectorAll('*')])for(const attr of [...node.attributes])if(/^on/i.test(attr.name)||['contenteditable','inert','data-editor-selected'].includes(attr.name))node.removeAttribute(attr.name);
    captures.push({id:slide.id,html:clone.outerHTML,duration:slide.getAttribute('data-time'),mainTag:slide.parentElement.tagName.toLowerCase(),mainAttributes:[...slide.parentElement.attributes].filter(a=>a.name!=='id').map(a=>[a.name,a.value])});
  }
  return {slides:captures,notes,notesProvenance,targetIds,originalImages,fontFamily,order:before};
}
