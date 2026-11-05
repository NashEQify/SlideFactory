/* Saved local ranges survive toolbar focus; transactions stay within one text object. */
function createTextTools(doc, hooks) {
  let saved = null,
    copied = null,
    colorSession = null,
    pipette = null;
  const inlineProperties = [
    'font-family',
    'font-size',
    'font-weight',
    'font-style',
    'text-decoration',
    'vertical-align',
    'color',
    'background-color',
  ];
  const blockProperties = [
    'text-align',
    'line-height',
    'align-content',
    'column-count',
    'column-gap',
  ];
  const surfaceProperties = [
    'background-color',
    'border-top-color',
    'border-right-color',
    'border-bottom-color',
    'border-left-color',
    'border-top-width',
    'border-right-width',
    'border-bottom-width',
    'border-left-width',
    'border-top-style',
    'border-right-style',
    'border-bottom-style',
    'border-left-style',
  ];
  const current = () =>
    hooks.interaction.selected?.dataset.sfKind === 'text' ? hooks.interaction.selected : null;
  const fontPoints = (element) =>
    Math.round(parseFloat(getComputedStyle(element).fontSize) * 75) / 100;
  const clampFont = (value) => Math.max(1, Math.min(999, value));
  function batchFontPlan() {
    const selection = hooks.interaction.selection;
    if (selection.length === 1 && current()) return null;
    const roots = selection.filter(
      (root) => !selection.some((other) => other !== root && other.contains(root)),
    );
    const scopes = [],
      sizes = [],
      fonts = new Map();
    for (const root of roots) {
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      let hasText = false;
      while (walker.nextNode()) {
        const text = walker.currentNode,
          parent = text.parentElement;
        if (
          !text.textContent.trim() ||
          parent.closest('svg,math,script,style,[data-sf-transient],[data-sf-kind="image"]')
        )
          continue;
        const owner = parent.closest('[data-sf-id]');
        if (!owner || !['text', 'box'].includes(owner.dataset.sfKind)) continue;
        hasText = true;
        const size = fontPoints(parent);
        sizes.push(size);
        fonts.set(parent, size);
        if (!fonts.has(owner)) fonts.set(owner, fontPoints(owner));
      }
      for (const text of [root, ...root.querySelectorAll('[data-sf-kind="text"]')]) {
        if (text.dataset.sfKind === 'text' && !text.textContent.trim()) {
          hasText = true;
          const size = fontPoints(text);
          sizes.push(size);
          fonts.set(text, size);
        }
      }
      if (hasText) scopes.push({ kind: 'subtree', id: root.dataset.sfId });
    }
    return { scopes, sizes, fonts };
  }
  function batchFontSize(value, delta = false) {
    if (!hooks.interaction.editing) return false;
    hooks.beforeEdit();
    const plan = batchFontPlan();
    if (!plan?.scopes.length) return false;
    const amount = Number(value);
    if (!Number.isFinite(amount)) return false;
    doc.run('Schriftgrößen ändern', plan.scopes, () => {
      for (const [element, size] of plan.fonts)
        element.style.fontSize = `${clampFont(delta ? size + amount : amount)}pt`;
    });
    hooks.interaction.update();
    return true;
  }
  function stepFontSize(delta) {
    if (!current()) {
      batchFontSize(delta, true);
      return;
    }
    command('fontSize', (getState()?.fontSize || 24) + delta);
  }
  function canSizeText() {
    return !!current() || !!batchFontPlan()?.scopes.length;
  }
  function valid(range, element) {
    return (
      !!range &&
      element?.isConnected &&
      element.contains(range.startContainer) &&
      element.contains(range.endContainer)
    );
  }
  function captureSelection() {
    const element = current(),
      selection = window.getSelection();
    if (!element || !selection?.rangeCount) return;
    const range = selection.getRangeAt(0);
    if (valid(range, element)) saved = { id: element.dataset.sfId, range: range.cloneRange() };
  }
  function restore(element, range = saved?.id === element.dataset.sfId ? saved.range : null) {
    const selection = window.getSelection();
    if (!valid(range, element) || range.collapsed) {
      range = document.createRange();
      range.selectNodeContents(element);
    }
    selection.removeAllRanges();
    selection.addRange(range);
    return selection;
  }
  function rangeStyles(element, styles) {
    const selection = window.getSelection(),
      range = selection.getRangeAt(0);
    if (!element.textContent) {
      for (const [property, value] of Object.entries(styles))
        element.style.setProperty(property, value);
      return [];
    }
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT),
      parts = [];
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (!range.intersectsNode(node)) continue;
      const start = node === range.startContainer ? range.startOffset : 0,
        end = node === range.endContainer ? range.endOffset : node.length;
      if (end > start) parts.push({ node, start, end });
    }
    const spans = [];
    for (const { node, start, end } of parts) {
      // A plain span already wrapping exactly this text is restyled instead of nested again.
      const parent = node.parentElement;
      if (
        !start &&
        end === node.length &&
        parent !== element &&
        parent.localName === 'span' &&
        parent.childNodes.length === 1 &&
        [...parent.attributes].every((attribute) => attribute.name === 'style')
      ) {
        for (const [property, value] of Object.entries(styles))
          parent.style.setProperty(property, value);
        spans.push(parent);
        continue;
      }
      if (end < node.length) node.splitText(end);
      const text = start ? node.splitText(start) : node;
      const span = document.createElement('span');
      for (const [property, value] of Object.entries(styles))
        span.style.setProperty(property, value);
      text.replaceWith(span);
      span.append(text);
      spans.push(span);
    }
    if (spans.length) {
      const next = document.createRange();
      next.setStart(spans[0].firstChild, 0);
      const last = spans.at(-1).firstChild;
      next.setEnd(last, last.length);
      selection.removeAllRanges();
      selection.addRange(next);
    }
    return spans;
  }
  function rangeStyle(element, property, value) {
    return rangeStyles(element, { [property]: value });
  }
  function promoteListRoot(element) {
    if (!/^(P|H[1-6])$/.test(element.tagName) || !element.querySelector('ul,ol')) return;
    const properties = [
      'font-family',
      'font-size',
      'font-weight',
      'font-style',
      'font-variant',
      'font-stretch',
      'line-height',
      'letter-spacing',
      'word-spacing',
      'text-transform',
      'text-decoration',
      'text-align',
      'text-indent',
      'white-space',
      'color',
      'display',
      'position',
      'box-sizing',
      'margin-top',
      'margin-right',
      'margin-bottom',
      'margin-left',
      'padding-top',
      'padding-right',
      'padding-bottom',
      'padding-left',
      'border-top',
      'border-right',
      'border-bottom',
      'border-left',
      'background-color',
      'width',
      'height',
      'min-width',
      'max-width',
      'min-height',
      'max-height',
      'left',
      'right',
      'top',
      'bottom',
      'transform',
      'transform-origin',
      'translate',
      'rotate',
      'scale',
      'flex',
      'align-self',
      'order',
      'grid-area',
    ];
    const original = getComputedStyle(element),
      values = properties.map((name) => [name, original.getPropertyValue(name)]),
      replacement = document.createElement('div');
    const selection = window.getSelection(),
      anchor = selection.anchorNode,
      focus = selection.focusNode,
      anchorOffset = selection.anchorOffset,
      focusOffset = selection.focusOffset;
    for (const attribute of element.attributes)
      replacement.setAttribute(attribute.name, attribute.value);
    replacement.append(...element.childNodes);
    element.replaceWith(replacement);
    for (const [name, value] of values)
      if (
        getComputedStyle(replacement).getPropertyValue(name) !== value &&
        !replacement.style.getPropertyValue(name)
      )
        replacement.style.setProperty(name, value);
    replacement.focus({ preventScroll: true });
    const nextAnchor = anchor === element ? replacement : anchor,
      nextFocus = focus === element ? replacement : focus;
    if (nextAnchor?.isConnected && nextFocus?.isConnected)
      selection.setBaseAndExtent(nextAnchor, anchorOffset, nextFocus, focusOffset);
    return replacement;
  }
  function highlightText(element) {
    const selection = window.getSelection(),
      range = selection.getRangeAt(0),
      walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT),
      texts = [];
    while (walker.nextNode()) {
      const node = walker.currentNode,
        start = node === range.startContainer ? range.startOffset : 0,
        end = node === range.endContainer ? range.endOffset : node.length;
      if (end > start && range.intersectsNode(node)) texts.push(node);
    }
    if (!texts.length) return;
    const remove = texts.every((node) => {
      const marker = node.parentElement.closest('[data-sf-highlight]');
      return marker && element.contains(marker);
    });
    const backgrounds = new Set(
      [...element.querySelectorAll('[style]')].map((node) => node.style.backgroundColor),
    );
    backgrounds.add(element.style.backgroundColor);
    const probe = document.createElement('span');
    let value;
    for (let blue = 1; blue < 256; blue++) {
      probe.style.backgroundColor = `rgb(255,255,${blue})`;
      if (!backgrounds.has(probe.style.backgroundColor)) {
        value = probe.style.backgroundColor;
        break;
      }
    }
    if (!remove && !value) throw Error('Der Textmarker kann hier nicht eindeutig gesetzt werden.');
    document.execCommand('hiliteColor', false, remove ? 'transparent' : value);
    if (!remove)
      for (const node of element.querySelectorAll('[style]'))
        if (node.style.backgroundColor === value) {
          node.dataset.sfHighlight = '';
          node.style.backgroundColor = '#ffff00';
        }
    for (const node of element.querySelectorAll('[data-sf-highlight]'))
      if (node.style.backgroundColor !== 'rgb(255, 255, 0)') delete node.dataset.sfHighlight;
  }
  function command(name, value) {
    if (name === 'fontSize' && !current()) {
      batchFontSize(value);
      return;
    }
    let element = current();
    if (!hooks.interaction.editing || !element) return;
    captureSelection();
    const range = saved?.id === element.dataset.sfId ? saved.range.cloneRange() : null;
    hooks.beforeEdit();
    hooks.interaction.beginText(element);
    restore(element, range);
    const blocks = {
      align: 'text-align',
      spacing: 'line-height',
      vertical: 'align-content',
      columns: 'column-count',
    };
    if (blocks[name]) {
      const property = blocks[name];
      doc.run(
        'Absatz formatieren',
        [{ kind: 'style', id: element.dataset.sfId, properties: [property] }],
        () => element.style.setProperty(property, String(value)),
      );
    } else {
      doc.run('Text formatieren', [{ kind: 'subtree', id: element.dataset.sfId }], () =>
        hooks.interaction.mutateText(() => {
          if (name === 'fontSize')
            rangeStyle(
              element,
              'font-size',
              `${Math.max(1, Math.min(999, Number(value) || 24))}pt`,
            );
          else if (name === 'fontFamily') rangeStyle(element, 'font-family', value);
          else if (name === 'color') rangeStyle(element, 'color', value);
          else if (name === 'highlight') highlightText(element);
          else {
            document.execCommand(name, false, value ?? null);
            if (['insertUnorderedList', 'insertOrderedList'].includes(name))
              element = promoteListRoot(element) || element;
          }
        }),
      );
    }
    hooks.interaction.refreshTextBaseline(element);
    captureSelection();
    hooks.interaction.update();
  }
  function finishColor() {
    if (!colorSession) return;
    const session = colorSession;
    colorSession = null;
    doc.commit(session.token);
    hooks.interaction.refreshTextBaseline();
    captureSelection();
  }
  function colorInput(value) {
    let element = current();
    if (!hooks.interaction.editing || !element || !/^#[0-9a-f]{6}$/i.test(value)) return;
    if (colorSession && colorSession.id !== element.dataset.sfId) finishColor();
    if (!colorSession) {
      captureSelection();
      const range = saved?.id === element.dataset.sfId ? saved.range.cloneRange() : null;
      hooks.beforeEdit();
      hooks.interaction.beginText(element);
      restore(element, range);
      colorSession = {
        id: element.dataset.sfId,
        token: doc.begin('Textfarbe ändern', [{ kind: 'subtree', id: element.dataset.sfId }]),
        spans: null,
      };
    }
    doc.update(colorSession.token, () =>
      hooks.interaction.mutateText(() => {
        if (colorSession.spans?.length && colorSession.spans.every((span) => span.isConnected))
          for (const span of colorSession.spans) span.style.color = value;
        else colorSession.spans = rangeStyle(element, 'color', value);
      }),
    );
  }
  function cancelAsync() {
    pipette?.abort();
    pipette = null;
  }
  function pickColor() {
    if (
      !window.isSecureContext ||
      typeof EyeDropper !== 'function' ||
      !current() ||
      !hooks.interaction.editing
    )
      return;
    captureSelection();
    hooks.beforeEdit();
    cancelAsync();
    const element = current(),
      slide = hooks.currentSlide(),
      range = saved?.id === element.dataset.sfId ? saved.range.cloneRange() : null;
    const ticket = doc.ticket({ slideId: slide.dataset.sfSlide, elementId: element.dataset.sfId }),
      controller = new AbortController();
    pipette = controller;
    // open stays in the click's user activation; no awaited preparation before it.
    new EyeDropper()
      .open({ signal: controller.signal })
      .then((result) => {
        if (
          controller !== pipette ||
          !hooks.interaction.editing ||
          hooks.currentSlide() !== slide ||
          current() !== element ||
          !doc.accepts(ticket)
        )
          return;
        if (range && valid(range, element)) {
          saved = { id: element.dataset.sfId, range };
          restore(element, range);
        }
        command('color', result.sRGBHex);
      })
      .catch((failure) => {
        if (failure.name !== 'AbortError')
          hooks.error('Die Pipette ist hier nicht verfügbar. Bitte das Farbrad verwenden.');
      })
      .finally(() => {
        if (pipette === controller) pipette = null;
      });
  }
  function getState() {
    const element = current();
    if (!element) {
      const sizes = batchFontPlan()?.sizes;
      if (!sizes?.length) return null;
      return {
        fontSize: sizes.every((size) => size === sizes[0]) ? sizes[0] : null,
        fontFamily: '',
      };
    }
    const node =
      saved?.id === element.dataset.sfId && valid(saved.range, element)
        ? saved.range.startContainer
        : null;
    const style = getComputedStyle(
        node ? (node.nodeType === 1 ? node : node.parentElement) : element,
      ),
      block = getComputedStyle(element);
    return {
      fontFamily: style.fontFamily,
      fontSize: Math.round(parseFloat(style.fontSize) * 75) / 100,
      color: style.color,
      align: block.textAlign,
    };
  }
  function cancelCopied() {
    copied = null;
    hooks.painterChanged?.(false);
  }
  function copyFormat() {
    const element = hooks.interaction.selected;
    if (!hooks.interaction.editing || !element) return;
    if (copied) {
      cancelCopied();
      return;
    }
    captureSelection();
    hooks.beforeEdit();
    const text = element.dataset.sfKind === 'text',
      root = element.closest('[data-sf-postit]') || element,
      style = getComputedStyle(element),
      surface = getComputedStyle(root);
    const node =
        text && saved?.id === element.dataset.sfId && valid(saved.range, element)
          ? saved.range.startContainer
          : null,
      inline = getComputedStyle(node ? (node.nodeType === 1 ? node : node.parentElement) : element);
    const inlineNode = node?.nodeType === 1 ? node : node?.parentElement,
      highlight = !!inlineNode?.closest('[data-sf-highlight]');
    copied = {
      text,
      inline: Object.fromEntries(
        inlineProperties.map((name) => [name, inline.getPropertyValue(name)]),
      ),
      block: Object.fromEntries(
        blockProperties.map((name) => [name, style.getPropertyValue(name)]),
      ),
      surface: Object.fromEntries(
        surfaceProperties.map((name) => [name, surface.getPropertyValue(name)]),
      ),
      shape: root.hasAttribute('data-sf-shape')
        ? { fill: surface.fill, stroke: surface.stroke, 'stroke-width': surface.strokeWidth }
        : null,
      highlight,
      list: inlineNode?.closest('ul,ol')?.tagName.toLowerCase() || null,
    };
    copied.inline['background-color'] = highlight
      ? '#ffff00'
      : inlineNode && inlineNode !== element
        ? inline.backgroundColor
        : 'transparent';
    const script = inlineNode?.closest('sup,sub');
    if (script && element.contains(script) && copied.inline['vertical-align'] === 'baseline')
      copied.inline['vertical-align'] = getComputedStyle(script).verticalAlign;
    hooks.painterChanged?.(true);
    hooks.message('Format aufgenommen. Ziel anklicken; Escape bricht ab.');
  }
  function applyCopied(target) {
    if (!copied || !target || !hooks.interaction.editing) return false;
    const format = copied;
    cancelCopied();
    hooks.beforeEdit();
    hooks.interaction.stopText();
    hooks.interaction.select(target);
    const root = target.closest('[data-sf-postit]') || target,
      isText = target.dataset.sfKind === 'text',
      isShape = root.hasAttribute('data-sf-shape');
    const properties = isShape
        ? format.shape || {
            fill: format.surface['background-color'],
            stroke:
              format.surface['border-top-style'] === 'none'
                ? 'none'
                : format.surface['border-top-color'],
            'stroke-width': format.surface['border-top-width'],
          }
        : {
            ...format.surface,
            ...(format.shape
              ? {
                  'background-color':
                    format.shape.fill === 'none' ? 'transparent' : format.shape.fill,
                  'border-top-color': format.shape.stroke,
                  'border-right-color': format.shape.stroke,
                  'border-bottom-color': format.shape.stroke,
                  'border-left-color': format.shape.stroke,
                  'border-top-style': format.shape.stroke === 'none' ? 'none' : 'solid',
                  'border-right-style': format.shape.stroke === 'none' ? 'none' : 'solid',
                  'border-bottom-style': format.shape.stroke === 'none' ? 'none' : 'solid',
                  'border-left-style': format.shape.stroke === 'none' ? 'none' : 'solid',
                  'border-top-width': format.shape['stroke-width'],
                  'border-right-width': format.shape['stroke-width'],
                  'border-bottom-width': format.shape['stroke-width'],
                  'border-left-width': format.shape['stroke-width'],
                }
              : {}),
          },
      scopes = [];
    if (isText && format.text) scopes.push({ kind: 'subtree', id: target.dataset.sfId });
    if ((properties && root !== target) || (properties && !(isText && format.text)))
      scopes.push({ kind: 'style', id: root.dataset.sfId, properties: Object.keys(properties) });
    if (!scopes.length) return true;
    if (isText && format.text) hooks.interaction.beginText(target);
    doc.run('Format übertragen', scopes, () => {
      if (properties)
        for (const [name, value] of Object.entries(properties)) root.style.setProperty(name, value);
      if (isText && format.text) {
        for (const node of [target, ...target.querySelectorAll('*')]) {
          for (const property of inlineProperties)
            if (property !== 'background-color' || node !== root)
              node.style?.removeProperty(property);
          node.removeAttribute?.('data-sf-highlight');
          if (/^(U|S|STRIKE|DEL)$/.test(node.tagName)) node.style.textDecoration = 'none';
          if (/^(SUP|SUB)$/.test(node.tagName)) {
            node.style.verticalAlign = 'baseline';
            node.style.fontSize = 'inherit';
          }
        }
        for (const [name, value] of Object.entries(format.block))
          target.style.setProperty(name, value);
        restore(target, null);
        const spans = rangeStyles(target, format.inline);
        if (format.highlight) for (const span of spans) span.dataset.sfHighlight = '';
        restore(target, null);
        const existing = target.querySelector('ul,ol');
        if (format.list ? !existing || existing.tagName.toLowerCase() !== format.list : !!existing)
          hooks.interaction.mutateText(() => {
            document.execCommand(
              (format.list || existing.tagName.toLowerCase()) === 'ol'
                ? 'insertOrderedList'
                : 'insertUnorderedList',
              false,
            );
            target = promoteListRoot(target) || target;
          });
      }
    });
    hooks.interaction.select(target, true);
    return true;
  }
  const selectionListener = () => {
    captureSelection();
    hooks.textStateChanged?.();
  };
  document.addEventListener('selectionchange', selectionListener);
  const keyListener = (event) => {
    if (event.key === 'Escape') {
      cancelCopied();
      cancelAsync();
    }
  };
  window.addEventListener('keydown', keyListener, true);
  doc.registerSettler('text-tools', ({ reason }) => {
    finishColor();
    if (['navigation', 'done', 'undo', 'redo', 'pagehide'].includes(reason)) {
      cancelCopied();
      cancelAsync();
      saved = null;
    }
  });
  return {
    captureSelection,
    command,
    stepFontSize,
    canSizeText,
    colorInput,
    finishColor,
    pickColor,
    copyFormat,
    applyCopied,
    cancelCopied,
    getState,
    reset() {
      saved = null;
      cancelCopied();
      cancelAsync();
    },
    get copying() {
      return !!copied;
    },
    dispose() {
      finishColor();
      cancelAsync();
      document.removeEventListener('selectionchange', selectionListener);
      window.removeEventListener('keydown', keyListener, true);
    },
  };
}
