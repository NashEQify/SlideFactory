/* Local authored objects; runtime controls never enter snapshots or projections. */
function createObjects(doc, hooks) {
  const shapes = new Set([
    'rectangle',
    'rounded-rectangle',
    'arrow-left',
    'arrow-right',
    'oval',
    'line',
  ]);
  let colorSession = null;
  const selected = () => hooks.interaction.selected;
  const rootFor = (element) => element?.closest('[data-sf-postit]') || element;
  const deletable = (element) =>
    !!element &&
    (['image', 'text'].includes(element.dataset.sfKind) ||
      element.hasAttribute('data-sf-shape') ||
      element.hasAttribute('data-sf-postit'));
  function insert(label, make) {
    if (!hooks.interaction.editing) return;
    hooks.beforeEdit();
    hooks.interaction.stopText();
    const slide = hooks.currentSlide(),
      element = make(),
      id = element.dataset.sfId;
    if (
      doc.run(
        label,
        [
          {
            kind: 'placement',
            id,
            slideId: slide.dataset.sfSlide,
            parentId: slide.dataset.sfSlide,
            beforeId: null,
          },
        ],
        () => slide.append(element),
      )
    ) {
      hooks.interaction.configure(element);
      hooks.interaction.select(element, true);
    }
    return element;
  }
  function frame(kind, geometry) {
    const element = document.createElement('div');
    element.dataset.sfId = `${kind}-${doc.freshId()}`;
    element.dataset.sfKind = kind;
    writeGeometry(element, geometry);
    element.style.boxSizing = 'border-box';
    return element;
  }
  function insertText() {
    const element = insert('Textfeld einfügen', () => {
      const text = frame('text', { x: 520, y: 350, w: 560, h: 160 });
      Object.assign(text.style, {
        fontFamily: 'Arial, sans-serif',
        fontSize: '32pt',
        lineHeight: '1.2',
        color: 'var(--sf-text)',
        padding: '12px',
        whiteSpace: 'pre-wrap',
        overflowWrap: 'anywhere',
      });
      text.textContent = 'Text';
      return text;
    });
    if (element) {
      hooks.interaction.beginText(element);
      const range = document.createRange();
      range.selectNodeContents(element);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
    }
  }
  function insertShape(type) {
    if (!shapes.has(type)) return;
    return insert('Form einfügen', () => {
      const element = frame('box', { x: 620, y: 340, w: 360, h: type === 'line' ? 80 : 220 });
      element.dataset.sfShape = type;
      Object.assign(element.style, {
        fill: 'var(--sf-accent)',
        stroke: 'var(--sf-text)',
        strokeWidth: '2px',
      });
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('viewBox', '0 0 100 100');
      svg.setAttribute('preserveAspectRatio', 'none');
      svg.setAttribute('aria-hidden', 'true');
      Object.assign(svg.style, {
        display: 'block',
        width: '100%',
        height: '100%',
        overflow: 'visible',
        pointerEvents: 'none',
      });
      const name =
          type === 'oval'
            ? 'ellipse'
            : type === 'line'
              ? 'line'
              : type.startsWith('arrow')
                ? 'polygon'
                : 'rect',
        shape = document.createElementNS(svg.namespaceURI, name);
      const attrs =
        type === 'oval'
          ? { cx: 50, cy: 50, rx: 49, ry: 49 }
          : type === 'line'
            ? { x1: 0, y1: 50, x2: 100, y2: 50, fill: 'none' }
            : type === 'arrow-left'
              ? { points: '1,50 35,1 35,30 99,30 99,70 35,70 35,99' }
              : type === 'arrow-right'
                ? { points: '99,50 65,1 65,30 1,30 1,70 65,70 65,99' }
                : {
                    x: 1,
                    y: 1,
                    width: 98,
                    height: 98,
                    ...(type === 'rounded-rectangle' ? { rx: 10, ry: 15 } : {}),
                  };
      for (const [name, value] of Object.entries(attrs)) shape.setAttribute(name, String(value));
      shape.setAttribute('vector-effect', 'non-scaling-stroke');
      svg.append(shape);
      element.append(svg);
      return element;
    });
  }
  // Slide links: <a data-sf-link> text objects; href holds the stable target slide ID, the look comes from .sf-link.
  const linkHref = (id) => `#${encodeURIComponent(id)}`;
  function linkTarget(element) {
    const href = element?.getAttribute?.('href');
    if (!href || !href.startsWith('#')) return null;
    try {
      return decodeURIComponent(href.slice(1));
    } catch {
      return null;
    }
  }
  function linkLabel(id) {
    const position = doc.slideIndex(id),
      title = doc.inventory()[position]?.title || '';
    return `→ ${title && title !== 'Folie' ? title.slice(0, 48) : `Folie ${position + 1}`}`;
  }
  function insertLink(targetId) {
    if (!doc.slide(targetId)) return;
    return insert('Folienlink einfügen', () => {
      const link = document.createElement('a');
      link.dataset.sfId = `link-${doc.freshId()}`;
      link.dataset.sfKind = 'text';
      link.dataset.sfLink = '';
      link.className = 'sf-link';
      link.setAttribute('href', linkHref(targetId));
      writeGeometry(link, { x: 610, y: 422, w: 380, h: 56 });
      link.style.boxSizing = 'border-box';
      link.textContent = linkLabel(targetId);
      return link;
    });
  }
  function setLinkTarget(targetId, element = selected()) {
    if (
      !hooks.interaction.editing ||
      !element?.hasAttribute('data-sf-link') ||
      !doc.slide(targetId)
    )
      return false;
    hooks.beforeEdit();
    element = doc.object(element.dataset.sfId);
    const previous = linkTarget(element);
    if (!element || previous === targetId) return false;
    // An untouched generated label follows the new target; an authored label stays.
    const relabel =
      !!doc.slide(previous) &&
      element.textContent === linkLabel(previous) &&
      !element.querySelector('*');
    return doc.run(
      'Linkziel ändern',
      [
        {
          kind: relabel ? 'subtree' : 'attrs',
          id: element.dataset.sfId,
          ...(relabel ? {} : { names: ['href'] }),
        },
      ],
      () => {
        element.setAttribute('href', linkHref(targetId));
        if (relabel) element.textContent = linkLabel(targetId);
      },
    );
  }
  // Targets only vanish on structural changes; ordinary edits check just the touched objects.
  function refreshLinks(event = null) {
    const links =
      !event || event.structural
        ? doc.deck.querySelectorAll('[data-sf-link]')
        : event.objectIds
            .map((id) => doc.object(id))
            .filter((node) => node?.hasAttribute('data-sf-link'));
    for (const link of links) {
      const broken = !doc.slide(linkTarget(link));
      if (broken) link.dataset.sfRuntimeBroken = '';
      else delete link.dataset.sfRuntimeBroken;
    }
  }
  function insertPostit() {
    if (doc.meta.postitsVisible === false) setPostitsVisible(true);
    return insert('Post-it einfügen', () => {
      const note = frame('box', { x: 1070, y: 160, w: 300, h: 230 });
      note.dataset.sfPostit = '';
      Object.assign(note.style, {
        backgroundColor: '#ffeb82',
        color: '#352e16',
        padding: '4px',
        boxShadow: '3px 5px 12px #0003',
        zIndex: '20',
      });
      const text = document.createElement('div');
      text.dataset.sfId = `text-${doc.freshId()}`;
      text.dataset.sfKind = 'text';
      Object.assign(text.style, {
        width: '100%',
        height: '100%',
        fontFamily: 'Arial, sans-serif',
        fontSize: '20pt',
        lineHeight: '1.3',
        color: 'inherit',
        whiteSpace: 'pre-wrap',
        overflowWrap: 'anywhere',
        overflow: 'auto',
      });
      text.textContent = 'Feedback';
      note.append(text);
      return note;
    });
  }
  function remove(element = selected()) {
    if (!hooks.interaction.editing) return false;
    element = rootFor(element);
    const id = element?.dataset.sfId;
    if (!id || !deletable(element)) return false;
    hooks.beforeEdit();
    element = doc.object(id);
    const slide = hooks.currentSlide();
    if (!element?.isConnected || element.closest('[data-sf-slide]') !== slide) return false;
    const parent = element.parentElement.closest('[data-sf-id],[data-sf-slide]');
    if (!parent) return false;
    const changed = doc.run(
      'Objekt löschen',
      [
        {
          kind: 'placement',
          id,
          slideId: slide.dataset.sfSlide,
          parentId: parent.dataset.sfId || parent.dataset.sfSlide,
          beforeId: null,
        },
      ],
      () => element.remove(),
    );
    if (changed) {
      hooks.interaction.select(null);
      hooks.message('Objekt gelöscht. Rückgängig stellt es wieder her.');
    }
    return changed;
  }
  function finishColor() {
    if (!colorSession) return;
    const session = colorSession;
    colorSession = null;
    doc.commit(session.token);
    hooks.interaction.refreshTextBaseline();
  }
  function color(kind, value, preview = false) {
    let element = rootFor(selected());
    if (!hooks.interaction.editing || !element || !deletable(element)) return;
    if (value !== 'transparent' && value !== 'none' && !/^#[0-9a-f]{6}$/i.test(value)) return;
    const isShape = element.hasAttribute('data-sf-shape');
    if (kind === 'fill' && element.dataset.sfShape === 'line') return;
    const properties = isShape
      ? [kind === 'fill' ? 'fill' : 'stroke']
      : kind === 'fill'
        ? ['background-color']
        : ['border-color', 'border-width', 'border-style'];
    if (colorSession && (colorSession.id !== element.dataset.sfId || colorSession.kind !== kind))
      finishColor();
    if (!colorSession) {
      hooks.beforeEdit();
      colorSession = {
        id: element.dataset.sfId,
        kind,
        token: doc.begin(kind === 'fill' ? 'Füllfarbe ändern' : 'Kantenfarbe ändern', [
          { kind: 'style', id: element.dataset.sfId, properties },
        ]),
      };
    }
    doc.update(colorSession.token, () => {
      if (isShape)
        element.style.setProperty(properties[0], value === 'transparent' ? 'none' : value);
      else if (kind === 'fill')
        element.style.backgroundColor = value === 'none' ? 'transparent' : value;
      else {
        element.style.borderColor = value === 'none' ? 'transparent' : value;
        element.style.borderWidth = '2px';
        element.style.borderStyle = value === 'none' ? 'none' : 'solid';
      }
    });
    if (!preview) finishColor();
    hooks.interaction.update();
  }
  function setPostitsVisible(value) {
    hooks.beforeEdit();
    doc.run(
      value ? 'Post-its anzeigen' : 'Post-its verbergen',
      [{ kind: 'meta', path: ['postitsVisible'] }],
      () => {
        doc.meta.postitsVisible = !!value;
      },
    );
    if (!value && selected()?.closest('[data-sf-postit]')) hooks.interaction.select(null);
    refresh();
  }
  function refresh(event = null) {
    document.body.dataset.sfRuntimePostits = String(doc.meta.postitsVisible !== false);
    if (doc.meta.postitsVisible === false && selected()?.closest('[data-sf-postit]'))
      hooks.interaction.select(null);
    const candidates = event
      ? event.objectIds.flatMap((id) => {
          const node = doc.object(id);
          if (!node) return [];
          const parent = node.closest('[data-sf-postit]');
          return [...(parent ? [parent] : []), ...node.querySelectorAll('[data-sf-postit]')];
        })
      : doc.deck.querySelectorAll('[data-sf-postit]');
    for (const note of new Set(candidates))
      if (!note.querySelector(':scope > [data-sf-postit-delete]')) {
        const button = document.createElement('button');
        button.type = 'button';
        button.dataset.sfTransient = '';
        button.dataset.sfPostitDelete = '';
        button.className = 'sf-postit-delete';
        button.setAttribute('aria-label', 'Post-it löschen');
        button.title = 'Post-it löschen';
        button.textContent = '×';
        note.append(button);
      }
    hooks.postitsChanged?.(doc.meta.postitsVisible !== false);
  }
  doc.deck.addEventListener('click', (event) => {
    const close = event.target.closest('[data-sf-postit-delete]');
    if (close) {
      event.preventDefault();
      event.stopPropagation();
      remove(close.closest('[data-sf-postit]'));
    }
  });
  const off = doc.onChange((event) => {
    if (event.type === 'change') {
      refresh(event);
      refreshLinks(event);
    }
  });
  doc.registerSettler('object-color', finishColor);
  refresh();
  refreshLinks();
  return {
    insertText,
    insertShape,
    insertPostit,
    insertLink,
    setLinkTarget,
    linkTarget,
    linkLabel,
    remove,
    canRemove: (element) => deletable(rootFor(element)),
    setFill: (value, preview) => color('fill', value, preview),
    setBorder: (value, preview) => color('border', value, preview),
    finishColor,
    setPostitsVisible,
    refresh,
    dispose() {
      finishColor();
      off();
    },
  };
}
