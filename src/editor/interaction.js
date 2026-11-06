/* Local geometry is authored on frames; matrices only convert gesture deltas. */
function frameGeometry(element) {
  const style = getComputedStyle(element);
  const pixels = (name) =>
    element.style[name].endsWith('px') ? parseFloat(element.style[name]) : parseFloat(style[name]);
  return {
    x: Number.isFinite(pixels('left')) ? pixels('left') : element.offsetLeft,
    y: Number.isFinite(pixels('top')) ? pixels('top') : element.offsetTop,
    w: pixels('width') || element.offsetWidth,
    h: pixels('height') || element.offsetHeight,
  };
}
function writeGeometry(element, geometry) {
  element.style.position = 'absolute';
  element.style.left = `${geometry.x}px`;
  element.style.top = `${geometry.y}px`;
  element.style.width = `${geometry.w}px`;
  element.style.height = `${geometry.h}px`;
}
function authoredOffsets(element) {
  const finitePixel = (value) => {
    if (!value || value === 'auto' || value === 'none') return 0;
    if (!/^-?(?:\d+(?:\.\d*)?|\.\d+)(?:px)?$/.test(value) || !Number.isFinite(parseFloat(value)))
      throw Error('Dieser Layoutversatz benötigt endliche Pixelwerte.');
    return parseFloat(value);
  };
  const mode = element.dataset.sfLayout;
  if (mode === 'flow') {
    const translate = getComputedStyle(element).translate;
    const parts = translate === 'none' ? [] : translate.trim().split(/\s+/);
    if (parts.length > 2) throw Error('Dreidimensionaler Layoutversatz wird nicht unterstützt.');
    return { x: finitePixel(parts[0]), y: finitePixel(parts[1]) };
  }
  if (mode === 'inline') {
    const style = getComputedStyle(element);
    if (!['static', 'relative'].includes(style.position))
      throw Error('Inline-Bewegung benötigt normale oder relative Position.');
    return {
      x: finitePixel(element.style.left || style.left),
      y: finitePixel(element.style.top || style.top),
    };
  }
  const geometry = frameGeometry(element);
  return { x: geometry.x, y: geometry.y };
}
function moveFrame(element, initial, dx, dy) {
  const mode = element.dataset.sfLayout;
  if (mode === 'flow') element.style.translate = `${initial.x + dx}px ${initial.y + dy}px`;
  else {
    if (mode === 'inline') {
      if (getComputedStyle(element).position === 'static') element.style.position = 'relative';
    } else element.style.position = 'absolute';
    element.style.left = `${initial.x + dx}px`;
    element.style.top = `${initial.y + dy}px`;
  }
}
function resizeFrame(element, geometry, initial, offsets) {
  if (!element.dataset.sfLayout) {
    writeGeometry(element, geometry);
    return;
  }
  if (element.dataset.sfLayout === 'inline') element.style.display = 'inline-block';
  if (
    element.dataset.sfLayout === 'flow' &&
    getComputedStyle(element.parentElement).display.includes('flex')
  )
    element.style.flex = '0 0 auto';
  element.style.width = `${geometry.w}px`;
  element.style.height = `${geometry.h}px`;
  moveFrame(element, offsets, geometry.x - initial.x, geometry.y - initial.y);
}
function localDelta(element, dx, dy, includeSelf = false) {
  let matrix = new DOMMatrix();
  for (let node = includeSelf ? element : element.parentElement; node; node = node.parentElement) {
    // CSS applies rotate, scale, then transform. Origins and translations do not change a delta.
    const { transform, scale, rotate } = getComputedStyle(node);
    if (transform && transform !== 'none') matrix = new DOMMatrix(transform).multiply(matrix);
    if (scale && scale !== 'none') {
      const [x, y = x] = scale
        .split(/\s+/)
        .map((value) => parseFloat(value) / (value.endsWith('%') ? 100 : 1));
      matrix = new DOMMatrix().scale(x, y).multiply(matrix);
    }
    if (rotate && rotate !== 'none') {
      const axis = rotate.split(/\s+/),
        angle = axis.pop();
      const vector = { x: '1,0,0', y: '0,1,0', z: '0,0,1' }[axis.join(' ')] || axis.join(',');
      const rotation = vector ? `rotate3d(${vector},${angle})` : `rotate(${angle})`;
      matrix = new DOMMatrix(rotation).multiply(matrix);
    }
  }
  const inverse = matrix.inverse();
  return { x: inverse.a * dx + inverse.c * dy, y: inverse.b * dx + inverse.d * dy };
}
function geometryScopes(element, resize = false) {
  const properties =
    element.dataset.sfLayout === 'flow' ? ['translate'] : ['position', 'left', 'top'];
  if (resize)
    properties.push(
      'width',
      'height',
      ...(element.dataset.sfLayout === 'inline' ? ['display'] : []),
      ...(element.dataset.sfLayout === 'flow' ? ['flex'] : []),
    );
  return [{ kind: 'style', id: element.dataset.sfId, properties }];
}
function createInteraction(doc, hooks) {
  let selected = null,
    editing = false,
    textElement = null,
    textBaseline = null,
    textToken = null,
    textTimer = null,
    composing = false,
    textMutating = false,
    gesture = null,
    lastNotePress = null,
    pendingText = null,
    blockedTextClick = null;
  let group = [],
    marquee = null,
    keyboardPicking = false;
  const configured = new Map();
  const selectionRect = document.createElement('div');
  selectionRect.id = 'sf-marquee';
  selectionRect.dataset.sfTransient = '';
  selectionRect.hidden = true;
  document.body.append(selectionRect);
  const overlay = document.createElement('div');
  overlay.id = 'sf-selection';
  overlay.dataset.sfTransient = '';
  overlay.hidden = true;
  overlay.tabIndex = 0;
  overlay.setAttribute('aria-label', 'Ausgewähltes Objekt');
  document.body.append(overlay);
  const directions = [
    ['nw', 'oben links'],
    ['n', 'oben'],
    ['ne', 'oben rechts'],
    ['e', 'rechts'],
    ['se', 'unten rechts'],
    ['s', 'unten'],
    ['sw', 'unten'],
    ['w', 'links'],
  ];
  const mover = document.createElement('button');
  mover.className = 'sf-move-grip';
  mover.type = 'button';
  mover.setAttribute('aria-label', 'Objekt verschieben');
  mover.textContent = '↕';
  overlay.append(mover);
  const grips = directions.map(([direction, name]) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `sf-grip sf-${direction}`;
    button.dataset.direction = direction;
    button.setAttribute('aria-label', `Größe ändern ${name}`);
    overlay.append(button);
    return button;
  });
  function runtimeAttribute(element, name, value) {
    const marker = `data-sf-runtime-original-${name}`;
    if (!element.hasAttribute(marker))
      element.setAttribute(
        marker,
        element.hasAttribute(name) ? element.getAttribute(name) : '__absent__',
      );
    element.setAttribute(name, value);
  }
  function update() {
    if (selected && !selected.isConnected) selected = doc.object(selected.dataset.sfId);
    hooks.selectionChanged?.(selected);
    overlay.hidden = !editing || (!selected && !group.length);
    if (overlay.hidden) return;
    const crop = !!hooks.images?.active,
      note = !!selected?.closest('[data-sf-postit]');
    const rects = (group.length ? group : [selected.closest('[data-sf-postit]') || selected]).map(
      (node) => node.getBoundingClientRect(),
    );
    const left = Math.min(...rects.map((r) => r.left)),
      top = Math.min(...rects.map((r) => r.top));
    Object.assign(overlay.style, {
      left: `${left}px`,
      top: `${top}px`,
      width: `${Math.max(...rects.map((r) => r.right)) - left}px`,
      height: `${Math.max(...rects.map((r) => r.bottom)) - top}px`,
    });
    const label = group.length ? `${group.length} Objekte verschieben` : 'Objekt verschieben';
    overlay.setAttribute(
      'aria-label',
      group.length ? `${group.length} Objekte ausgewählt` : 'Ausgewähltes Objekt',
    );
    mover.setAttribute('aria-label', label);
    mover.textContent = group.length ? `↕ ${group.length}` : '↕';
    overlay.dataset.crop = String(crop);
    overlay.dataset.postit = String(note);
    grips.forEach((grip, i) => {
      grip.setAttribute(
        'aria-label',
        `${crop ? 'Ausschnitt' : 'Größe ändern'} ${directions[i][1]}`,
      );
      grip.hidden = !!group.length || (note && directions[i][0] === 'ne');
    });
    mover.hidden = crop || note;
  }
  function refreshTextBaseline(element = textElement) {
    if (!element) return;
    const current = doc.object(element.dataset.sfId);
    if (!current) {
      textElement = null;
      textBaseline = null;
      return;
    }
    textElement = current;
    textBaseline = doc.capture([{ kind: 'subtree', id: current.dataset.sfId }]);
  }
  function flushText() {
    clearTimeout(textTimer);
    textTimer = null;
    if (textToken) {
      const token = textToken;
      textToken = null;
      doc.commit(token);
    }
    refreshTextBaseline();
  }
  function stopText() {
    flushText();
    composing = false;
    if (textElement?.isConnected) {
      runtimeAttribute(textElement, 'contenteditable', 'false');
      delete textElement.dataset.sfRuntimeText;
    }
    textElement = null;
    textBaseline = null;
  }
  function setSelection(nodes, focus = false) {
    const nextSingle = nodes.length === 1 ? nodes[0] : null;
    if (pendingText && pendingText.element !== nextSingle) cancelPendingText();
    if (nextSingle !== selected) {
      stopText();
      if (hooks.images?.active) hooks.images.apply();
    }
    for (const node of group) delete node.dataset.sfRuntimeGroupMember;
    selected = nextSingle;
    group = nodes.length > 1 ? nodes : [];
    for (const node of group) node.dataset.sfRuntimeGroupMember = '';
    update();
    if (focus && nodes.length) overlay.focus({ preventScroll: true });
  }
  function select(element, focus = false) {
    keyboardPicking = false;
    setSelection(element ? [element] : [], focus);
  }
  function members() {
    return selected ? [selected] : group;
  }
  const movableRoot = (node) => node?.closest('[data-sf-postit]') || node;
  function roots(nodes) {
    const candidates = new Set(
      nodes.map(movableRoot).filter((node) => node && hooks.currentSlide().contains(node)),
    );
    return [...candidates].filter((node) => {
      for (let parent = node.parentElement; parent; parent = parent.parentElement)
        if (candidates.has(parent)) return false;
      return true;
    });
  }
  function toggleMember(node, focus = true) {
    const root = movableRoot(node),
      current = roots(members());
    const existing = current.find((member) => member.contains(root));
    setSelection(
      existing ? current.filter((member) => member !== existing) : roots([...current, root]),
      focus,
    );
  }
  function groupOffsets() {
    return group.map((node) => ({ node, offsets: authoredOffsets(node) }));
  }
  function moveGroup(frames, dx, dy) {
    for (const { node, offsets } of frames) {
      const delta = localDelta(node, dx, dy);
      moveFrame(node, offsets, delta.x, delta.y);
    }
  }
  function nudgeGroup(dx, dy) {
    hooks.beforeEdit?.();
    const slide = hooks.currentSlide(),
      scale = slide.getBoundingClientRect().width / slide.offsetWidth;
    try {
      const frames = groupOffsets();
      doc.run(
        'Objekte verschieben',
        group.flatMap((node) => geometryScopes(node)),
        () => moveGroup(frames, dx * scale, dy * scale),
      );
    } catch (error) {
      hooks.error(error.message);
    }
    update();
  }
  function startGroupGesture(event, member = null) {
    hooks.beforeEdit?.();
    event.preventDefault();
    overlay.focus({ preventScroll: true });
    try {
      const frames = groupOffsets(),
        token = doc.begin(
          'Objekte verschieben',
          group.flatMap((node) => geometryScopes(node)),
          { mode: 'preview' },
        );
      gesture = {
        frames,
        token,
        x: event.clientX,
        y: event.clientY,
        pointerId: event.pointerId,
        member,
        moved: false,
      };
      overlay.setPointerCapture(event.pointerId);
    } catch (error) {
      cancelGesture();
      hooks.error(error.message);
    }
  }
  function startMarquee(event) {
    const slide = hooks.currentSlide();
    if (!slide.contains(event.target)) return;
    const base = event.ctrlKey || event.metaKey ? members().slice() : [];
    hooks.beforeEdit?.();
    event.preventDefault();
    setSelection(base);
    marquee = {
      base,
      slide,
      x: event.clientX,
      y: event.clientY,
      pointerId: event.pointerId,
      capture: slide,
    };
    slide.setPointerCapture(event.pointerId);
  }
  function drawMarquee(event) {
    const { x, y } = marquee,
      left = Math.min(x, event.clientX),
      top = Math.min(y, event.clientY);
    if (selectionRect.hidden && Math.hypot(x - event.clientX, y - event.clientY) < 4) return;
    selectionRect.hidden = false;
    Object.assign(selectionRect.style, {
      left: `${left}px`,
      top: `${top}px`,
      width: `${Math.abs(x - event.clientX)}px`,
      height: `${Math.abs(y - event.clientY)}px`,
    });
  }
  function endMarquee(commit) {
    if (!marquee) return;
    const press = marquee;
    marquee = null;
    releasePointer(press);
    if (commit && !selectionRect.hidden) {
      const box = selectionRect.getBoundingClientRect();
      const hits = [...press.slide.querySelectorAll('[data-sf-id]')].filter((node) => {
        if (
          doc.object(node.dataset.sfId) !== node ||
          getComputedStyle(node).visibility !== 'visible'
        )
          return false;
        const r = node.getBoundingClientRect();
        return (
          r.width > 0 &&
          r.height > 0 &&
          r.left < box.right &&
          r.right > box.left &&
          r.top < box.bottom &&
          r.bottom > box.top
        );
      });
      setSelection(roots([...press.base, ...hits]), true);
    }
    selectionRect.hidden = true;
  }
  function beginText(element = selected) {
    if (!editing || element?.dataset.sfKind !== 'text') return;
    hooks.beforeEdit?.();
    select(element);
    textElement = element;
    refreshTextBaseline(element);
    runtimeAttribute(element, 'contenteditable', 'true');
    element.dataset.sfRuntimeText = 'true';
    element.focus({ preventScroll: true });
    update();
  }
  function placeCaret(element, x, y) {
    const point = document.caretPositionFromPoint?.(x, y),
      range = document.createRange();
    if (point && element.contains(point.offsetNode)) {
      range.setStart(point.offsetNode, point.offset);
      range.collapse(true);
    } else {
      const nativeRange = document.caretRangeFromPoint?.(x, y);
      if (!nativeRange || !element.contains(nativeRange.startContainer)) return;
      range.setStart(nativeRange.startContainer, nativeRange.startOffset);
      range.collapse(true);
    }
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
  }
  function configure(element = null) {
    const nodes = element
      ? [element, ...element.querySelectorAll('[data-sf-id]')]
      : [...configured.values()];
    for (const previous of nodes) {
      const id = previous.dataset.sfId,
        node = doc.object(id);
      if (!node) {
        configured.delete(id);
        continue;
      }
      configured.set(id, node);
      runtimeAttribute(node, 'tabindex', editing ? '0' : '-1');
      if (node.dataset.sfKind === 'text' && node !== textElement)
        runtimeAttribute(node, 'contenteditable', 'false');
      hooks.images?.render(node);
    }
  }
  for (const element of doc.deck.querySelectorAll('[data-sf-id]'))
    configured.set(element.dataset.sfId, element);
  function setEditing(value) {
    doc.settle(value ? 'command' : 'done');
    stopText();
    editing = value;
    document.body.dataset.sfRuntimeEditing = String(value);
    select(null);
    configure();
    update();
  }
  function openTextSession(element) {
    if (textToken) return;
    if (textElement !== element) {
      textElement = element;
      refreshTextBaseline(element);
    }
    if (!textBaseline) return;
    textToken = doc.begin('Text bearbeiten', [{ kind: 'subtree', id: element.dataset.sfId }], {
      before: textBaseline,
    });
  }
  function inputElement(event) {
    const element = event.target.closest?.('[data-sf-kind="text"]');
    return element?.isContentEditable ? element : null;
  }
  function scheduleText() {
    clearTimeout(textTimer);
    if (!composing) textTimer = setTimeout(flushText, 450);
  }
  function startGesture(event, direction = '') {
    if (event.button !== 0 || !editing || gesture || pendingText) return;
    if (group.length) {
      if (!direction) startGroupGesture(event);
      return;
    }
    if (!selected) return;
    const note = selected.closest('[data-sf-postit]');
    if (note && note !== selected) select(note);
    if (!hooks.images?.active) hooks.beforeEdit?.();
    event.preventDefault();
    stopText();
    overlay.focus({ preventScroll: true });
    try {
      const crop = !!hooks.images?.active;
      gesture = {
        element: selected,
        token: crop
          ? null
          : doc.begin(
              direction ? 'Größe ändern' : 'Objekt verschieben',
              geometryScopes(selected, !!direction),
              { mode: 'preview' },
            ),
        geometry: frameGeometry(selected),
        offsets: authoredOffsets(selected),
        x: event.clientX,
        y: event.clientY,
        direction,
        pointerId: event.pointerId,
      };
      if (crop) hooks.images.beginGesture(direction);
      try {
        overlay.setPointerCapture(event.pointerId);
      } catch {}
    } catch (error) {
      hooks.error(error.message);
    }
  }
  overlay.addEventListener('keydown', (event) => {
    const handle = event.target.closest('[data-direction],.sf-move-grip'),
      vectors = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
    if (!handle || !vectors[event.key] || !editing) return;
    if (group.length) {
      event.preventDefault();
      event.stopPropagation();
      const step = event.shiftKey ? 10 : 1,
        [dx, dy] = vectors[event.key];
      nudgeGroup(dx * step, dy * step);
      return;
    }
    if (!selected) return;
    const note = selected.closest('[data-sf-postit]');
    if (note && note !== selected) select(note);
    event.preventDefault();
    event.stopPropagation();
    const step = event.shiftKey ? 10 : 1,
      [dx, dy] = vectors[event.key].map((n) => n * step),
      direction = handle.dataset.direction || '';
    if (hooks.images?.active) {
      hooks.images.beginGesture(direction);
      hooks.images.previewGesture({ x: dx, y: dy });
      update();
      return;
    }
    hooks.beforeEdit?.();
    const initial = frameGeometry(selected),
      offsets = authoredOffsets(selected),
      next = { ...initial };
    if (direction) {
      if (direction.includes('e')) next.w = Math.max(24, initial.w + dx);
      if (direction.includes('w')) next.w = Math.max(24, initial.w - dx);
      if (direction.includes('s')) next.h = Math.max(24, initial.h + dy);
      if (direction.includes('n')) next.h = Math.max(24, initial.h - dy);
      if (selected.dataset.sfKind === 'image') {
        const ratio = initial.w / initial.h;
        if (direction === 'n' || direction === 's' || !dx) next.w = next.h * ratio;
        else next.h = next.w / ratio;
      }
      if (direction.includes('w')) next.x = initial.x + initial.w - next.w;
      if (direction.includes('n')) next.y = initial.y + initial.h - next.h;
    }
    doc.run(
      direction ? 'Größe ändern' : 'Objekt verschieben',
      geometryScopes(selected, !!direction),
      () => {
        if (direction) resizeFrame(selected, next, initial, offsets);
        else moveFrame(selected, offsets, dx, dy);
        hooks.images?.render(selected);
      },
    );
    update();
  });
  overlay.addEventListener('pointerdown', (event) =>
    startGesture(event, event.target.closest('[data-direction]')?.dataset.direction || ''),
  );
  doc.deck.addEventListener('pointerdown', (event) => {
    if (
      !editing ||
      event.button !== 0 ||
      pendingText ||
      gesture ||
      marquee ||
      event.target.closest('[data-sf-postit-delete]')
    )
      return;
    keyboardPicking = false;
    blockedTextClick = null;
    let element = event.target.closest('[data-sf-id]');
    if (!element) {
      startMarquee(event);
      return;
    }
    if (!hooks.currentSlide().contains(element) || doc.object(element.dataset.sfId) !== element)
      return;
    if (event.ctrlKey || event.metaKey) {
      event.preventDefault();
      toggleMember(element);
      return;
    }
    if (group.some((node) => node.contains(element))) {
      startGroupGesture(event, movableRoot(element));
      return;
    }
    if (hooks.textTools?.applyCopied(element)) {
      event.preventDefault();
      return;
    }
    if (element.isContentEditable) {
      select(element);
      return;
    }
    const note = element.closest('[data-sf-postit]');
    if (note) {
      const twice =
        lastNotePress?.note === note &&
        event.timeStamp - lastNotePress.time < 400 &&
        Math.hypot(event.clientX - lastNotePress.x, event.clientY - lastNotePress.y) < 5;
      lastNotePress = { note, time: event.timeStamp, x: event.clientX, y: event.clientY };
      if (twice) {
        lastNotePress = null;
        beginText(note.querySelector('[data-sf-kind="text"]'));
        return;
      }
      element = note;
    } else lastNotePress = null;
    select(element);
    if (!note && element.dataset.sfKind === 'text' && !event.altKey) {
      event.preventDefault();
      pendingText = { element, event, pointerId: event.pointerId, capture: element };
      try {
        element.setPointerCapture(event.pointerId);
      } catch {}
      return;
    }
    if (hooks.images?.active || element.dataset.sfKind !== 'text' || event.altKey)
      startGesture(event);
  });
  doc.deck.addEventListener(
    'click',
    (event) => {
      if (blockedTextClick?.contains(event.target)) {
        event.preventDefault();
        event.stopPropagation();
      }
    },
    true,
  );
  doc.deck.addEventListener('dblclick', (event) => {
    if (
      !editing ||
      blockedTextClick?.contains(event.target) ||
      event.target.closest('[data-sf-postit-delete]')
    )
      return;
    let element = event.target.closest('[data-sf-id]');
    const note = element?.closest('[data-sf-postit]');
    if (note) element = note.querySelector('[data-sf-kind="text"]');
    select(element);
    if (element?.dataset.sfKind === 'text') beginText(element);
    if (element?.dataset.sfKind === 'image') hooks.images.start(element);
  });
  doc.deck.addEventListener('focusin', (event) => {
    const element = event.target.closest('[data-sf-id]');
    if (editing && element && !keyboardPicking) {
      select(element);
      if (element.isContentEditable && textElement !== element) {
        textElement = element;
        refreshTextBaseline(element);
      }
    }
  });
  doc.deck.addEventListener('focusout', (event) => {
    if (inputElement(event) && !composing) flushText();
  });
  doc.deck.addEventListener('beforeinput', (event) => {
    const element = inputElement(event);
    if (!element || textMutating) return;
    if (['historyUndo', 'historyRedo'].includes(event.inputType)) {
      event.preventDefault();
      hooks.history?.(event.inputType === 'historyRedo');
      return;
    }
    openTextSession(element);
    const anchor = window.getSelection()?.anchorNode,
      listItem = (anchor?.nodeType === Node.ELEMENT_NODE ? anchor : anchor?.parentElement)?.closest(
        'li',
      );
    if (event.inputType === 'insertParagraph' && !(listItem && element.contains(listItem))) {
      event.preventDefault();
      document.execCommand('insertLineBreak', false);
      doc.update(textToken);
      scheduleText();
    }
  });
  doc.deck.addEventListener('input', (event) => {
    const element = inputElement(event);
    if (!element || textMutating) return;
    openTextSession(element);
    if (textToken) doc.update(textToken);
    scheduleText();
  });
  doc.deck.addEventListener('compositionstart', (event) => {
    const element = inputElement(event);
    if (!element) return;
    openTextSession(element);
    composing = true;
    clearTimeout(textTimer);
  });
  doc.deck.addEventListener('compositionend', (event) => {
    if (!inputElement(event)) return;
    composing = false;
    if (textToken) doc.update(textToken);
    flushText();
  });
  doc.deck.addEventListener('paste', (event) => {
    const element = inputElement(event);
    if (!element) return;
    if ([...(event.clipboardData?.files || [])].some((file) => file.type.startsWith('image/')))
      return;
    event.preventDefault();
    openTextSession(element);
    const text = event.clipboardData.getData('text/plain');
    doc.update(textToken, () => {
      if (/\r|\n/.test(text)) {
        const container = document.createElement('div');
        text
          .replace(/\r\n?/g, '\n')
          .split('\n')
          .forEach((line, i) => {
            if (i) container.append(document.createElement('br'));
            container.append(document.createTextNode(line));
          });
        document.execCommand('insertHTML', false, container.innerHTML);
      } else document.execCommand('insertText', false, text);
    });
    scheduleText();
  });
  window.addEventListener('pointermove', (event) => {
    if (marquee?.pointerId === event.pointerId) {
      drawMarquee(event);
      return;
    }
    if (gesture?.frames && gesture.pointerId === event.pointerId) {
      const dx = event.clientX - gesture.x,
        dy = event.clientY - gesture.y;
      if (!gesture.moved && Math.hypot(dx, dy) < 4) return;
      gesture.moved = true;
      doc.update(gesture.token, () => moveGroup(gesture.frames, dx, dy));
      update();
      return;
    }
    if (
      pendingText?.pointerId === event.pointerId &&
      Math.hypot(
        event.clientX - pendingText.event.clientX,
        event.clientY - pendingText.event.clientY,
      ) >= 5
    ) {
      const press = releasePendingText();
      blockedTextClick = press.element;
      startGesture(press.event);
    }
    if (!gesture || gesture.pointerId !== event.pointerId) return;
    const { element, geometry: initial, direction } = gesture;
    const delta = localDelta(
      element,
      event.clientX - gesture.x,
      event.clientY - gesture.y,
      !!direction,
    );
    if (hooks.images?.active) hooks.images.previewGesture(delta);
    else
      doc.update(gesture.token, () => {
        const next = { ...initial };
        if (!direction) {
          next.x += delta.x;
          next.y += delta.y;
        } else {
          if (direction.includes('e')) next.w = Math.max(24, initial.w + delta.x);
          if (direction.includes('s')) next.h = Math.max(24, initial.h + delta.y);
          if (direction.includes('w')) next.w = Math.max(24, initial.w - delta.x);
          if (direction.includes('n')) next.h = Math.max(24, initial.h - delta.y);
          if (element.dataset.sfKind === 'image') {
            const ratio = initial.w / initial.h;
            if (direction === 'n' || direction === 's') next.w = next.h * ratio;
            else next.h = next.w / ratio;
          }
          if (direction.includes('w')) next.x = initial.x + initial.w - next.w;
          if (direction.includes('n')) next.y = initial.y + initial.h - next.h;
        }
        if (!direction) moveFrame(element, gesture.offsets, delta.x, delta.y);
        else resizeFrame(element, next, initial, gesture.offsets);
        hooks.images?.render(element);
      });
    update();
  });
  function releasePointer(finished) {
    if (finished?.pointerId != null) {
      const target = finished.capture || overlay;
      try {
        if (target.hasPointerCapture(finished.pointerId))
          target.releasePointerCapture(finished.pointerId);
      } catch {}
    }
  }
  function releasePendingText() {
    const press = pendingText;
    pendingText = null;
    releasePointer(press);
    return press;
  }
  function cancelPendingText() {
    const press = releasePendingText();
    if (press) blockedTextClick = press.element;
  }
  function flushGesture() {
    endMarquee(false);
    cancelPendingText();
    if (!gesture) return;
    const finished = gesture;
    gesture = null;
    releasePointer(finished);
    if (finished.token) doc.commit(finished.token);
    update();
  }
  function releaseGesture() {
    cancelPendingText();
    const finished = gesture;
    gesture = null;
    releasePointer(finished);
  }
  function cancelGesture() {
    endMarquee(false);
    cancelPendingText();
    const cancelled = gesture;
    gesture = null;
    releasePointer(cancelled);
    if (hooks.images?.active) hooks.images.cancel();
    else if (cancelled?.token) doc.cancel(cancelled.token);
    update();
  }
  window.addEventListener('pointerup', (event) => {
    if (marquee?.pointerId === event.pointerId) {
      drawMarquee(event);
      endMarquee(true);
      return;
    }
    if (gesture?.frames && gesture.pointerId === event.pointerId) {
      const collapse = !gesture.moved && gesture.member;
      flushGesture();
      if (collapse) select(collapse, true);
      return;
    }
    if (pendingText?.pointerId === event.pointerId) {
      const press = releasePendingText();
      if (editing && press.element.isConnected && selected === press.element) {
        beginText(press.element);
        placeCaret(press.element, event.clientX, event.clientY);
      }
    } else if (gesture?.pointerId === event.pointerId) flushGesture();
  });
  window.addEventListener('pointercancel', (event) => {
    if (
      marquee?.pointerId === event.pointerId ||
      pendingText?.pointerId === event.pointerId ||
      gesture?.pointerId === event.pointerId
    )
      cancelGesture();
  });
  doc.deck.addEventListener('lostpointercapture', (event) => {
    if (marquee?.pointerId === event.pointerId) endMarquee(false);
    if (pendingText?.pointerId === event.pointerId) cancelPendingText();
  });
  overlay.addEventListener('lostpointercapture', (event) => {
    if (gesture?.pointerId === event.pointerId) cancelGesture();
  });
  window.addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && ['z', 'y'].includes(event.key.toLowerCase())) {
      event.preventDefault();
      hooks.history?.(event.key.toLowerCase() === 'y' || event.shiftKey);
      return;
    }
    const typing =
      event.target.isContentEditable ||
      event.target.matches?.(
        'textarea,select,input:not([type="range"]):not([type="checkbox"]):not([type="file"])',
      );
    if (event.key === 'Escape' && (marquee || pendingText || gesture || hooks.images?.active)) {
      event.preventDefault();
      const multi = marquee || gesture?.frames;
      cancelGesture();
      if (multi) select(null);
      return;
    }
    if (typing) {
      if (event.key === 'Escape' && event.target.isContentEditable) {
        event.preventDefault();
        const note = selected?.closest('[data-sf-postit]');
        stopText();
        if (note) select(note);
        overlay.focus();
        update();
      }
      return;
    }
    const focusedObject = event.target.closest?.('[data-sf-id]');
    if (
      editing &&
      event.code === 'Space' &&
      (event.ctrlKey || event.metaKey) &&
      focusedObject &&
      hooks.currentSlide().contains(focusedObject)
    ) {
      event.preventDefault();
      if (!keyboardPicking && focusedObject === selected)
        setSelection([movableRoot(focusedObject)]);
      else toggleMember(focusedObject, false);
      keyboardPicking = true;
      return;
    }
    if (group.length && overlay.contains(event.target) && event.key === 'Escape') {
      event.preventDefault();
      select(null);
      return;
    }
    if (event.key === 'Delete') {
      if (
        !editing ||
        !selected ||
        !hooks.objects?.canRemove(selected) ||
        event.defaultPrevented ||
        event.isComposing ||
        composing ||
        event.ctrlKey ||
        event.metaKey ||
        event.altKey ||
        event.shiftKey ||
        document.querySelector('dialog[open]')
      )
        return;
      const onOverlay = overlay.contains(event.target),
        onObject = selected.contains(event.target);
      if (
        !onOverlay &&
        (!onObject ||
          event.target.closest?.(
            'button,input,textarea,select,a[href]:not([data-sf-id]),[role="button"],[role="textbox"]',
          ))
      )
        return;
      event.preventDefault();
      hooks.deleteSelection?.();
      return;
    }
    // A focused deep-dive trigger is a slide object: storyline keys still navigate.
    if (
      event.target.closest?.(
        'button,input,textarea,select,a[href]:not([data-sf-id]),[role="button"]:not([data-sf-deep-dive-target]),[role="textbox"]',
      ) &&
      !['PageDown', 'PageUp'].includes(event.key)
    )
      return;
    if (event.key === 'Escape') {
      select(null);
      return;
    }
    if (event.key === 'Enter' && editing && selected) {
      event.preventDefault();
      if (hooks.images?.active) hooks.images.apply();
      else if (selected.dataset.sfKind === 'text') beginText();
      else if (selected.hasAttribute('data-sf-postit'))
        beginText(selected.querySelector('[data-sf-kind="text"]'));
      return;
    }
    const vectors = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
    if (vectors[event.key] && editing && group.length) {
      event.preventDefault();
      const [dx, dy] = vectors[event.key],
        step = event.shiftKey ? 10 : 1;
      nudgeGroup(dx * step, dy * step);
      return;
    }
    if (vectors[event.key] && editing && selected) {
      event.preventDefault();
      const note = selected.closest('[data-sf-postit]');
      if (note && note !== selected) select(note);
      const [dx, dy] = vectors[event.key],
        step = event.shiftKey ? 10 : 1;
      if (hooks.images?.active) hooks.images.nudge(dx * step, dy * step);
      else {
        hooks.beforeEdit?.();
        doc.run('Objekt verschieben', geometryScopes(selected), () =>
          moveFrame(selected, authoredOffsets(selected), dx * step, dy * step),
        );
        refreshTextBaseline();
      }
      update();
      return;
    }
    if (['ArrowRight', 'PageDown', 'ArrowLeft', 'PageUp'].includes(event.key)) {
      event.preventDefault();
      hooks.navigate(event.key === 'ArrowRight' || event.key === 'PageDown' ? 1 : -1);
    }
    if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault();
      hooks.goToEdge?.(event.key === 'End');
    }
  });
  doc.registerSettler('interaction-input', () => flushText());
  doc.registerSettler('interaction-preview', ({ preview }) =>
    preview === 'cancel' ? cancelGesture() : flushGesture(),
  );
  doc.onChange((event) => {
    if (event.type !== 'change') return;
    if (group.length && (event.structural || group.some((node) => !node.isConnected)))
      setSelection(roots(group.map((node) => doc.object(node.dataset.sfId))));
    if (event.structural && selected && !selected.isConnected) {
      selected = null;
      textElement = null;
      textBaseline = null;
    }
    // Subtree history recreates clean descendants as well as the named root.
    for (const id of event.objectIds) {
      const element = doc.object(id);
      if (element) configure(element);
    }
    if (
      textElement &&
      (!textElement.isConnected || event.objectIds.includes(textElement.dataset.sfId))
    ) {
      textElement = doc.object(textElement.dataset.sfId);
      if (textElement && editing) {
        runtimeAttribute(textElement, 'contenteditable', 'true');
        textElement.dataset.sfRuntimeText = 'true';
      }
      refreshTextBaseline();
    }
    update();
  });
  window.addEventListener('resize', update);
  return {
    setEditing,
    select,
    beginText,
    flushText,
    stopText,
    update,
    configure,
    releaseGesture,
    cancelGesture,
    flushGesture,
    refreshTextBaseline,
    mutateText(callback) {
      textMutating = true;
      try {
        return callback();
      } finally {
        textMutating = false;
      }
    },
    get selection() {
      return Object.freeze([...members()]);
    },
    get selected() {
      return selected;
    },
    get editing() {
      return editing;
    },
  };
}
