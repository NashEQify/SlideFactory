function createImages(doc, hooks) {
  let cropSession = null, cropGesture = null;
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  const readCrop = element => JSON.parse(element.dataset.sfCrop);
  const setCrop = (element, crop) => { element.dataset.sfCrop = JSON.stringify(crop); render(element); };
  const ghost = document.createElement('div'); ghost.id = 'sf-crop-source'; ghost.dataset.sfTransient = ''; ghost.hidden = true;
  document.body.append(ghost);
  function centeredCrop(nw, nh, width, height) {
    const sourceAspect = nw / nh, targetAspect = width / height;
    let w = 1, h = 1;
    if (sourceAspect > targetAspect) w = targetAspect / sourceAspect;
    else h = sourceAspect / targetAspect;
    return {x: (1 - w) / 2, y: (1 - h) / 2, w, h};
  }
  function render(element) {
    if (element?.dataset.sfKind !== 'image') return;
    const img = element.querySelector(':scope > img'); if (!img) return;
    const crop = readCrop(element), geometry = frameGeometry(element);
    Object.assign(element.style, {overflow: 'hidden'});
    Object.assign(img.style, {position: 'absolute', maxWidth: 'none', maxHeight: 'none', objectFit: 'fill',
      width: `${geometry.w / crop.w}px`, height: `${geometry.h / crop.h}px`,
      left: `${-crop.x * geometry.w / crop.w}px`, top: `${-crop.y * geometry.h / crop.h}px`,
      pointerEvents: 'none', userSelect: 'none'});
    img.draggable = false;
    if (cropSession?.element === element) renderGhost();
  }
  function renderGhost() {
    if (!cropSession) { ghost.hidden = true; return; }
    const element = cropSession.element, rect = element.getBoundingClientRect(), crop = readCrop(element);
    ghost.hidden = false;
    const source = element.querySelector(':scope > img');
    if (!ghost.firstElementChild || ghost.firstElementChild.src !== source.src) {
      ghost.replaceChildren(source.cloneNode(false)); ghost.firstElementChild.removeAttribute('style');
      ghost.firstElementChild.alt = ''; ghost.firstElementChild.draggable = false;
    }
    Object.assign(ghost.style, {left: `${rect.left - crop.x * rect.width / crop.w}px`, top: `${rect.top - crop.y * rect.height / crop.h}px`,
      width: `${rect.width / crop.w}px`, height: `${rect.height / crop.h}px`});
  }
  function renderAll() { doc.deck.querySelectorAll('[data-sf-kind="image"]').forEach(render); }
  async function decodeFile(file) {
    if (!file || !['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) throw Error('Bitte eine PNG-, JPEG- oder WebP-Datei wählen.');
    const src = await new Promise((resolve, reject) => {
      const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = () => reject(Error('Die Bilddatei konnte nicht gelesen werden.')); reader.readAsDataURL(file);
    });
    const image = new Image(); image.src = src;
    try { await image.decode(); } catch { throw Error('Die Bilddatei konnte nicht als Bild geöffnet werden.'); }
    if (!image.naturalWidth || !image.naturalHeight) throw Error('Das Bild hat keine gültige Größe.');
    return {src, width: image.naturalWidth, height: image.naturalHeight, name: file.name || 'Eingefügtes Bild'};
  }
  async function importFile(file, replace = null, point = null) {
    hooks.beforeEdit?.();
    const slide = replace?.closest('[data-sf-slide]') || hooks.currentSlide();
    const slideId = slide?.dataset.sfSlide, replaceId = replace?.dataset.sfId;
    const ticket = doc.ticket({slideId, elementId: replaceId});
    let localPoint = null;
    if (point && slide?.isConnected) {
      const rect = slide.getBoundingClientRect(); localPoint = localDelta(slide, point.x - rect.left, point.y - rect.top, true);
    }
    try {
      hooks.message('Bild wird eingebettet …'); const original = await decodeFile(file);
      if (!hooks.interaction.editing || !doc.accepts(ticket)) throw Error('Bildimport abgebrochen: Das ursprüngliche Ziel wurde geändert oder ist nicht mehr verfügbar.');
      hooks.beforeEdit?.();
      if (!doc.accepts(ticket)) throw Error('Bildimport abgebrochen: Das ursprüngliche Ziel wurde inzwischen geändert.');
      const targetSlide = doc.slide(slideId), target = replaceId ? doc.object(replaceId) : null;
      if (!targetSlide || (replaceId && target?.dataset.sfKind !== 'image')) throw Error('Das ursprüngliche Bildziel fehlt.');
      doc.asset(original.src, original);
      const id = replaceId || `image-${doc.freshId()}`;
      let element = target;
      const scopes = target ? [{kind:'image',id}] : [{kind:'placement',id,slideId,parentId:slideId,beforeId:null}];
      const changed = doc.run(target ? 'Bild ersetzen' : 'Bild einfügen', scopes, () => {
        if (!element) {
          element = document.createElement('div'); element.dataset.sfId = id; element.dataset.sfKind = 'image';
          const factor = Math.min(600 / original.width, 420 / original.height, 1), w = original.width * factor, h = original.height * factor;
          const geometry = {x:800-w/2,y:450-h/2,w,h};
          if (localPoint) {geometry.x=clamp(localPoint.x-w/2,0,1600-w);geometry.y=clamp(localPoint.y-h/2,0,900-h);}
          writeGeometry(element,geometry); targetSlide.append(element);
        }
        const geometry = frameGeometry(element); let img = element.querySelector(':scope > img');
        if (!img) {img=document.createElement('img');element.append(img);}
        img.src=original.src;img.width=original.width;img.height=original.height;img.alt=original.name;
        setCrop(element,centeredCrop(original.width,original.height,geometry.w,geometry.h));
      });
      if (!changed) return;
      hooks.interaction.configure(element); if(hooks.currentSlide()===targetSlide)hooks.interaction.select(element,true);
      hooks.message('Bild eingebettet. Bitte HTML speichern für die gemeinsame Weiterarbeit.');
    } catch(error) {hooks.error(error.message);}
  }
  function start(element = hooks.interaction.selected) {
    if (!element || element.dataset.sfKind !== 'image') return;
    hooks.beforeEdit?.(); hooks.interaction.stopText();
    cropSession = {element, token:doc.begin('Bild zuschneiden',[{kind:'image',id:element.dataset.sfId}],{mode:'preview'}), initialCrop:readCrop(element), initialGeometry:frameGeometry(element)};
    hooks.cropChanged(true); render(element); hooks.interaction.update();
  }
  function apply() {
    if (!cropSession) return;
    hooks.interaction.releaseGesture(); const {element,token}=cropSession;cropSession=null;cropGesture=null;ghost.hidden=true;ghost.replaceChildren();
    doc.commit(token);render(element);hooks.cropChanged(false);hooks.interaction.update();
  }
  function cancel() {
    if (!cropSession) return;
    hooks.interaction.releaseGesture();const {element,token}=cropSession;cropSession=null;cropGesture=null;ghost.hidden=true;ghost.replaceChildren();
    doc.cancel(token);render(element);hooks.cropChanged(false);hooks.interaction.update();
  }
  function beginGesture(direction) {
    if (!cropSession) return;
    cropGesture = {direction, crop: readCrop(cropSession.element), geometry: frameGeometry(cropSession.element)};
  }
  function previewGesture(delta) {
    if (!cropSession || !cropGesture) return;
    const element = cropSession.element, {crop, geometry, direction} = cropGesture;
    const next = {...crop};
    if (!direction) {
      next.x = clamp(crop.x - delta.x / geometry.w * crop.w, 0, 1 - crop.w);
      next.y = clamp(crop.y - delta.y / geometry.h * crop.h, 0, 1 - crop.h);
    } else {
      let left = crop.x, top = crop.y, right = crop.x + crop.w, bottom = crop.y + crop.h;
      const minW = Math.min(crop.w, 24 / geometry.w * crop.w), minH = Math.min(crop.h, 24 / geometry.h * crop.h);
      if (direction.includes('w')) left = clamp(crop.x + delta.x / geometry.w * crop.w, 0, right - minW);
      if (direction.includes('e')) right = clamp(right + delta.x / geometry.w * crop.w, left + minW, 1);
      if (direction.includes('n')) top = clamp(crop.y + delta.y / geometry.h * crop.h, 0, bottom - minH);
      if (direction.includes('s')) bottom = clamp(bottom + delta.y / geometry.h * crop.h, top + minH, 1);
      Object.assign(next, {x: left, y: top, w: right - left, h: bottom - top});
      doc.update(cropSession.token, () => writeGeometry(element, {x: geometry.x + (left - crop.x) / crop.w * geometry.w, y: geometry.y + (top - crop.y) / crop.h * geometry.h,
        w: next.w / crop.w * geometry.w, h: next.h / crop.h * geometry.h}));
    }
    doc.update(cropSession.token, () => setCrop(element, next));
  }
  function zoom(value) {
    if (!cropSession) return;
    const element = cropSession.element, original = cropSession.initialCrop, current = readCrop(element);
    const factor = clamp(Number(value), 1, 4);
    const w = original.w / factor, h = original.h / factor;
    const geometry = frameGeometry(element), image = element.querySelector(':scope > img');
    // Use the current frame aspect, including any crop-handle changes.
    const aspect = geometry.w / geometry.h * Number(image.getAttribute('height')) / Number(image.getAttribute('width'));
    const adjustedW = Math.min(w, h * aspect), adjustedH = adjustedW / aspect;
    const crop = {w: adjustedW, h: adjustedH, x: clamp(current.x + current.w / 2 - adjustedW / 2, 0, 1 - adjustedW), y: clamp(current.y + current.h / 2 - adjustedH / 2, 0, 1 - adjustedH)};
    doc.update(cropSession.token, () => setCrop(element, crop)); hooks.interaction.update();
  }
  function nudge(dx, dy) { beginGesture(''); previewGesture({x: dx, y: dy}); }
  window.addEventListener('resize', renderGhost);
  document.addEventListener('paste', event => {
    if (!hooks.interaction.editing || /^(INPUT|TEXTAREA)$/.test(event.target.tagName)) return;
    const file = [...(event.clipboardData?.files || [])].find(file => file.type.startsWith('image/'));
    if (file) { event.preventDefault(); importFile(file); }
  });
  doc.deck.addEventListener('dragover', event => { if (hooks.interaction.editing && [...event.dataTransfer.types].includes('Files')) event.preventDefault(); });
  doc.deck.addEventListener('drop', event => {
    if (!hooks.interaction.editing) return;
    const file = event.dataTransfer.files[0]; if (!file) return;
    event.preventDefault(); importFile(file, null, {x: event.clientX, y: event.clientY});
  });
  doc.registerSettler('images-preview', ({preview}) => preview === 'cancel' ? cancel() : apply());
  renderAll();
  return {render, renderAll, importFile, start, apply, cancel, beginGesture, previewGesture, zoom, nudge, get active() { return !!cropSession; }};
}
