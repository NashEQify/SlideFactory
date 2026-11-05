/* Saved authored HTML/schema1 remain authoritative; edits are bounded local records. */
async function createDocument() {
  let originalBase = document.documentElement.outerHTML;
  const deck = document.getElementById('sf-deck'),
    metadataNode = document.getElementById('sf-document');
  const schemesNode = document.getElementById('sf-color-schemes'),
    themeNode = document.getElementById('sf-theme-tokens');
  const notesCodec = createNotesCodec(document);
  const observers = new Set(),
    settlers = new Map(),
    sessions = new Map(),
    baselines = new WeakMap();
  const past = [],
    future = [],
    pending = [],
    projection = new Map();
  const assets = new Map(),
    assetBySource = new Map(),
    objectAssets = new Map(),
    liveRefs = new Map(),
    historyRefs = new Map(),
    activeRefs = new Map(),
    pendingRefs = new Map(),
    projectionRefs = new Map(),
    projectionKeys = new Map(),
    scopeRefs = new WeakMap(),
    scopeIds = new WeakMap(),
    gcCandidates = new Set();
  const durableRefs = new Set(),
    storedAssets = new Set(),
    durableEntries = new Set();
  const objects = new Map(),
    slideNodes = new Map(),
    slidePositions = new Map(),
    versions = new Map(),
    generations = new Map();
  const requestOwners = new Map(),
    titleNodes = new Map(),
    titleCandidates = new Map();
  let slideOrder = [],
    inventoryEntries = [],
    inventoryView = [],
    meta,
    schemes,
    valid = false,
    recoveredDraft = false,
    storageMessage = '',
    draftMessage = '';
  let sequence = 0,
    lifecycle = 0,
    settling = false,
    draftTimer = null,
    checkpointTimer = null,
    admittedHead = null;
  let recordBytes = 0,
    lastPublishedBytes = 0,
    recordCount = 0,
    historyBytes = 0,
    historyAssetBytes = 0,
    checkpointGeneration = 0,
    assetSequence = 0;
  const historyBudget = 64 * 1024 * 1024,
    journalBudget = 2 * 1024 * 1024;
  const json = (value) => JSON.stringify(value).replace(/</g, '\\u003c');
  // Slide links are text objects on <a>; a missing target is reported, never fatal.
  const validateLink = (element) => {
    if (
      element.hasAttribute('data-sf-link') &&
      (element.tagName !== 'A' ||
        element.dataset.sfKind !== 'text' ||
        !/^#[^#\s]+$/.test(element.getAttribute('href') || ''))
    )
      throw Error('Ein Folienlink benötigt ein Textobjekt <a> mit href="#Folienkennung".');
  };
  // Optional timing: data-sf-duration (s), data-sf-part (label) and data-sf-part-duration (s, part budget).
  const seconds = (value) =>
    /^\d+(?:\.\d+)?$/.test(value) && Number.isFinite(Number(value)) && Number(value) > 0;
  function validateTiming(slide) {
    if (slide.hasAttribute('data-sf-duration') && !seconds(slide.dataset.sfDuration))
      throw Error('Ungültige Foliendauer.');
    if (
      slide.hasAttribute('data-sf-part') &&
      (!slide.dataset.sfPart.trim() || slide.dataset.sfPart.length > 80)
    )
      throw Error('Ungültige Teilbezeichnung.');
    if (
      slide.hasAttribute('data-sf-part-duration') &&
      (!slide.hasAttribute('data-sf-part') || !seconds(slide.dataset.sfPartDuration))
    )
      throw Error('Ungültige Teildauer.');
  }
  const isHidden = (slide) => slide.hasAttribute('data-sf-hidden');
  const timing = (slide) => ({
    duration: Number(slide.dataset.sfDuration) || null,
    part: slide.dataset.sfPart?.trim() || null,
    partDuration: Number(slide.dataset.sfPartDuration) || null,
  });
  const freshId = () =>
    globalThis.crypto?.randomUUID?.() ||
    `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  const tokens = ['background', 'text', 'muted', 'accent', 'accent2', 'surface', 'border'];
  const plainObject = (value) => !!value && typeof value === 'object' && !Array.isArray(value);
  const copyValue = (value) => (value === undefined ? undefined : structuredClone(value));
  const freeze = (value) => {
    if (value && typeof value === 'object' && !Object.isFrozen(value)) {
      for (const item of Object.values(value)) freeze(item);
      Object.freeze(value);
    }
    return value;
  };
  const emit = (type, details = {}) => {
    const event = freeze({ type, ...details });
    for (const listener of observers) listener(event);
  };
  const clean = (root) => {
    root.querySelectorAll('[data-sf-transient]').forEach((node) => node.remove());
    for (const node of [root, ...root.querySelectorAll('*')]) {
      for (const attribute of [...node.attributes])
        if (attribute.name.startsWith('data-sf-runtime-original-')) {
          const name = attribute.name.slice('data-sf-runtime-original-'.length);
          if (attribute.value === '__absent__') node.removeAttribute(name);
          else node.setAttribute(name, attribute.value);
        }
      for (const attribute of [...node.attributes])
        if (attribute.name.startsWith('data-sf-runtime-')) node.removeAttribute(attribute.name);
    }
    return root;
  };
  const applyTheme = () => {
    themeNode.textContent = `:root{${tokens.map((name) => `--sf-${name}:${name === 'background' && meta.backgroundColor ? meta.backgroundColor : schemes[meta.colorScheme].tokens[name]};`).join('')}}`;
  };
  function validate(candidateMeta = meta, candidateDeck = deck) {
    if (!candidateDeck || !metadataNode || !schemesNode || !themeNode)
      throw Error('Diese Datei ist kein vollständiges SlideFactory-Dokument.');
    if (!plainObject(candidateMeta) || candidateMeta.schemaVersion !== 1)
      throw Error('Die Dokumentversion wird nicht unterstützt.');
    for (const key of [
      'deckId',
      'revision',
      'title',
      'templateId',
      'templateVersion',
      'colorScheme',
    ]) {
      if (typeof candidateMeta[key] !== 'string' || (!candidateMeta[key] && key !== 'title'))
        throw Error(`Ungültige Dokumentangabe: ${key}.`);
    }
    if (
      candidateMeta.postitsVisible !== undefined &&
      typeof candidateMeta.postitsVisible !== 'boolean'
    )
      throw Error('Ungültige Post-it-Sichtbarkeit.');
    if (
      candidateMeta.backgroundColor !== undefined &&
      (typeof candidateMeta.backgroundColor !== 'string' ||
        !/^#[0-9a-f]{6}$/i.test(candidateMeta.backgroundColor))
    )
      throw Error('Ungültige Hintergrundfarbe.');
    if (candidateMeta.pageWidth !== 1600 || candidateMeta.pageHeight !== 900)
      throw Error('Ungültiges Folienformat (erwartet: 1600 × 900).');
    if (!plainObject(schemes) || !schemes[candidateMeta.colorScheme])
      throw Error('Das Farbschema fehlt.');
    for (const scheme of Object.values(schemes)) {
      if (!plainObject(scheme) || typeof scheme.label !== 'string' || !plainObject(scheme.tokens))
        throw Error('Ungültiges Farbschema.');
      for (const key of tokens) {
        if (
          typeof scheme.tokens[key] !== 'string' ||
          !/^#(?:[0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})$/i.test(scheme.tokens[key])
        )
          throw Error(`Ungültiger Farbwert: ${key}.`);
      }
    }
    const slideNodes = [...candidateDeck.querySelectorAll('[data-sf-slide]')];
    const ids = new Set(),
      slideIds = new Set();
    if (!slideNodes.length) throw Error('Das Dokument enthält keine Folien.');
    for (const slide of slideNodes) {
      const id = slide.dataset.sfSlide;
      if (
        slide.tagName !== 'SECTION' ||
        !slide.classList.contains('sf-slide') ||
        !id ||
        ids.has(id)
      )
        throw Error('Folienkennungen fehlen oder sind doppelt.');
      ids.add(id);
      slideIds.add(id);
      validateTiming(slide);
    }
    for (const element of candidateDeck.querySelectorAll('[data-sf-id]')) {
      const id = element.dataset.sfId;
      if (
        !id ||
        ids.has(id) ||
        !['text', 'box', 'image'].includes(element.dataset.sfKind) ||
        !element.closest('[data-sf-slide]')
      )
        throw Error('Objektkennungen fehlen, sind doppelt oder haben keinen gültigen Typ.');
      ids.add(id);
      if (
        element.hasAttribute('data-sf-layout') &&
        (!['flow', 'inline'].includes(element.dataset.sfLayout) ||
          element.dataset.sfKind === 'image')
      )
        throw Error('Ungültiger Layoutmodus.');
      validateLink(element);
      if (element.dataset.sfKind === 'image') {
        const originals = element.querySelectorAll('img'),
          img = originals[0];
        if (
          originals.length !== 1 ||
          img.parentElement !== element ||
          !/^data:image\/(?:png|jpeg|webp|svg\+xml)(?:;|,)/i.test(img.getAttribute('src') || '')
        )
          throw Error('Ein Bildrahmen benötigt genau ein direkt eingebettetes Originalbild.');
        const crop = JSON.parse(element.dataset.sfCrop || 'null');
        const nw = Number(img.getAttribute('width')),
          nh = Number(img.getAttribute('height'));
        if (
          !crop ||
          !['x', 'y', 'w', 'h'].every((key) => Number.isFinite(crop[key])) ||
          crop.x < 0 ||
          crop.y < 0 ||
          crop.w <= 0 ||
          crop.h <= 0 ||
          crop.x + crop.w > 1.000001 ||
          crop.y + crop.h > 1.000001 ||
          !Number.isFinite(nw) ||
          !Number.isFinite(nh) ||
          nw <= 0 ||
          nh <= 0
        )
          throw Error('Ungültiger Bildausschnitt oder fehlende Originalgröße.');
        const frame = ['left', 'top', 'width', 'height'].map((name) => {
          const value = element.style[name];
          if (!/^-?(?:\d+(?:\.\d*)?|\.\d+)px$/.test(value) || !Number.isFinite(parseFloat(value)))
            throw Error('Bildrahmen benötigen endliche Position und Größe in Pixeln.');
          return parseFloat(value);
        });
        const fw = frame[2],
          fh = frame[3];
        if (fw <= 0 || fh <= 0) throw Error('Bildrahmen benötigen eine positive Breite und Höhe.');
        if (Math.abs((crop.w * nw) / (crop.h * nh) / (fw / fh) - 1) > 0.00001)
          throw Error('Bildausschnitt und Rahmen haben unterschiedliche Seitenverhältnisse.');
      }
    }
    if (candidateDeck.querySelector('[data-sf-draft-asset],[data-sf-snapshot-asset]'))
      throw Error('Nicht aufgelöster Originalbild-Verweis.');
    for (const key of ['notes', 'guidance']) {
      if (!plainObject(candidateMeta[key])) throw Error(`Ungültige ${key}-Angaben.`);
      for (const [id, value] of Object.entries(candidateMeta[key])) {
        if (!slideIds.has(id)) throw Error(`Verweis auf eine fehlende Folie: ${id}.`);
        if (key === 'notes' && typeof value !== 'string')
          throw Error('Referentennotizen müssen Text sein.');
        if (
          key === 'guidance' &&
          (!plainObject(value) ||
            typeof value.text !== 'string' ||
            !['open', 'addressed'].includes(value.status))
        )
          throw Error('Ungültiger Hinweis für den Agenten.');
      }
    }
    if (candidateMeta.notesFormat !== undefined) {
      if (!plainObject(candidateMeta.notesFormat)) throw Error('Ungültige Notizformate.');
      for (const [id, format] of Object.entries(candidateMeta.notesFormat)) {
        if (!slideIds.has(id)) throw Error('Notizformat ohne Folie.');
        notesCodec.validate(format);
      }
    }
    if (candidateMeta.notesProvenance !== undefined) {
      if (!plainObject(candidateMeta.notesProvenance)) throw Error('Ungültige Notizenherkunft.');
      for (const [id, value] of Object.entries(candidateMeta.notesProvenance)) {
        if (
          !slideIds.has(id) ||
          !plainObject(value) ||
          typeof value.html !== 'string' ||
          typeof value.text !== 'string'
        )
          throw Error('Ungültige Notizenherkunft.');
      }
    }
    if (document.querySelector('script[src],link[rel="stylesheet"][href]'))
      throw Error('Externe Laufzeitdateien sind nicht zulässig.');
    return true;
  }
  try {
    meta = JSON.parse(metadataNode?.textContent || 'null');
    schemes = JSON.parse(schemesNode?.textContent || 'null');
    validate();
    valid = true;
  } catch (error) {
    return { valid: false, error: error.message };
  }
  const base = { deckId: meta.deckId, revision: meta.revision, fingerprint: null },
    storageKey = `slidefactory:${meta.deckId}`;
  try {
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(originalBase));
    base.fingerprint = [...new Uint8Array(digest)]
      .map((byte) => byte.toString(16).padStart(2, '0'))
      .join('');
  } catch {
    storageMessage =
      'Sicherer Browserentwurf nicht verfügbar. Bitte die vollständige HTML-Datei speichern.';
  }
  originalBase = null;
  const namespace = `${storageKey}:${base.revision}:${base.fingerprint}:`;
  const assetSource = (src) =>
    typeof src === 'string' && /^data:image\/[-+.a-z0-9]+(?:;|,)/i.test(src);
  const imageSource = (src) =>
    typeof src === 'string' && /^data:image\/(?:png|jpeg|webp|svg\+xml)(?:;|,)/i.test(src);
  function asset(src, dimensions = {}) {
    if (!assetSource(src)) throw Error('Das Originalbild ist nicht gültig eingebettet.');
    let entry = assetBySource.get(src);
    if (!entry) {
      entry = freeze({
        id: `new:${freshId()}`,
        src,
        width: Number(dimensions.width) || 0,
        height: Number(dimensions.height) || 0,
        bytes: src.length * 2,
      });
      assetBySource.set(src, entry);
      assets.set(entry.id, entry);
      gcCandidates.add(entry.id);
      assetSequence++;
    }
    return entry;
  }
  // Original identities are deterministic and independent of edit/history sequence.
  for (const img of document.querySelectorAll('img[src]')) {
    const src = img.getAttribute('src');
    if (!assetSource(src) || assetBySource.has(src)) continue;
    const entry = freeze({
      id: `original:${assetSequence++}`,
      src,
      width: Number(img.getAttribute('width')) || 0,
      height: Number(img.getAttribute('height')) || 0,
      bytes: src.length * 2,
    });
    assets.set(entry.id, entry);
    assetBySource.set(src, entry);
  }
  function refsFor(descriptor, value) {
    if (!value) return new Set();
    if (descriptor.kind === 'image')
      return new Set(typeof value.asset === 'string' ? [value.asset] : []);
    if (!['subtree', 'placement', 'slide'].includes(descriptor.kind) || !value.html)
      return new Set();
    const cached = scopeRefs.get(value);
    if (cached) return cached;
    const template = document.createElement('template');
    template.innerHTML = value.html;
    const refs = new Set(
      [...template.content.querySelectorAll('img[data-sf-journal-asset]')].map((img) =>
        img.getAttribute('data-sf-journal-asset'),
      ),
    );
    scopeRefs.set(value, refs);
    return refs;
  }
  function refsIn(changes) {
    const refs = new Set();
    for (const change of changes || [])
      if (change?.descriptor)
        for (const key of ['before', 'after', 'value'])
          for (const id of refsFor(change.descriptor, change[key])) refs.add(id);
    return refs;
  }
  function adjustRefs(counter, refs, amount) {
    for (const id of refs) {
      const old = counter.get(id) || 0,
        n = old + amount;
      if (n > 0) counter.set(id, n);
      else counter.delete(id);
      if (counter === historyRefs) {
        if (!old && n > 0) historyAssetBytes += assets.get(id)?.bytes || 0;
        if (old > 0 && n <= 0) historyAssetBytes -= assets.get(id)?.bytes || 0;
      }
      if (amount < 0 && id.startsWith('new:')) gcCandidates.add(id);
    }
  }
  function trackObjectAssets(element) {
    const id = element.dataset.sfId,
      previous = objectAssets.get(id) || new Set(),
      next = new Set();
    if (element.dataset.sfKind === 'image') {
      const img = element.querySelector(':scope > img');
      if (img && imageSource(img.getAttribute('src')))
        next.add(
          asset(img.getAttribute('src'), {
            width: img.getAttribute('width'),
            height: img.getAttribute('height'),
          }).id,
        );
    }
    adjustRefs(liveRefs, previous, -1);
    adjustRefs(liveRefs, next, 1);
    objectAssets.set(id, next);
  }
  const titleCandidate = (node) =>
    node.dataset.sfKind === 'text' &&
    !node.closest('[data-sf-postit]') &&
    !node.hasAttribute('data-sf-link');
  function titleFor(slide) {
    return [...slide.querySelectorAll('[data-sf-kind="text"]')].find(titleCandidate);
  }
  const titleText = (node) => (node?.textContent || 'Folie').trim().slice(0, 160);
  function rebuildIndexes() {
    objects.clear();
    slideNodes.clear();
    slidePositions.clear();
    titleNodes.clear();
    titleCandidates.clear();
    for (const refs of objectAssets.values()) adjustRefs(liveRefs, refs, -1);
    objectAssets.clear();
    slideOrder = [...deck.querySelectorAll('[data-sf-slide]')];
    inventoryEntries = slideOrder.map((slide, position) => {
      const id = slide.dataset.sfSlide;
      slideNodes.set(id, slide);
      slidePositions.set(id, position);
      versions.set(id, versions.get(id) || 0);
      const title = titleFor(slide);
      titleNodes.set(id, title);
      titleCandidates.set(
        id,
        [...slide.querySelectorAll('[data-sf-kind="text"]')]
          .filter(titleCandidate)
          .map((node) => node.dataset.sfId),
      );
      return freeze({ id, title: titleText(title), hidden: isHidden(slide), ...timing(slide) });
    });
    for (const element of deck.querySelectorAll('[data-sf-id]')) {
      objects.set(element.dataset.sfId, element);
      generations.set(element.dataset.sfId, generations.get(element.dataset.sfId) || 0);
      trackObjectAssets(element);
    }
    slideOrder = Object.freeze(slideOrder);
    inventoryView = new Proxy(inventoryEntries, {
      set() {
        throw Error('Die Folienübersicht ist schreibgeschützt.');
      },
      deleteProperty() {
        return false;
      },
      defineProperty() {
        return false;
      },
    });
  }
  rebuildIndexes();
  const nodeFor = (id) => objects.get(id) || slideNodes.get(id);
  function layout(element, phase) {
    if (!element) return;
    element.dispatchEvent(
      new CustomEvent('sf:layout', {
        bubbles: true,
        detail: {
          slideId: element.closest('[data-sf-slide]')?.dataset.sfSlide,
          elementId: element.dataset.sfId,
          phase,
        },
      }),
    );
  }
  // The JSON script is an entry/token tree: touching a note never rewrites its siblings.
  let metadataTree;
  function buildJson(value, fragment) {
    if (!plainObject(value)) {
      const node = document.createTextNode(json(value));
      fragment.append(node);
      return { first: node, last: node, node };
    }
    const first = document.createTextNode('{'),
      last = document.createTextNode('}'),
      entries = new Map();
    fragment.append(first);
    for (const [key, child] of Object.entries(value)) {
      const prefix = document.createTextNode(`${entries.size ? ',' : ''}${json(key)}:`);
      fragment.append(prefix);
      entries.set(key, { prefix, tree: buildJson(child, fragment) });
    }
    fragment.append(last);
    return { first, last, entries };
  }
  function resetJson() {
    const fragment = document.createDocumentFragment();
    metadataTree = buildJson(meta, fragment);
    metadataNode.replaceChildren(fragment);
  }
  function removeRange(first, last) {
    let current = first;
    while (current) {
      const next = current.nextSibling;
      current.remove();
      if (current === last) break;
      current = next;
    }
  }
  function syncPath(path) {
    let tree = metadataTree,
      value = meta;
    for (let i = 0; i < path.length; i++) {
      const key = path[i],
        present = Object.prototype.hasOwnProperty.call(value, key),
        entry = tree.entries?.get(key);
      if (i < path.length - 1 && present && entry?.tree.entries) {
        value = value[key];
        tree = entry.tree;
        continue;
      }
      if (i < path.length - 1) {
        syncPath(path.slice(0, i + 1));
        if (present && plainObject(value[key])) syncPath(path);
        return;
      }
      if (!present) {
        if (entry) {
          removeRange(entry.prefix, entry.tree.last);
          tree.entries.delete(key);
          const first = tree.entries.values().next().value;
          if (first) first.prefix.data = first.prefix.data.replace(/^,/, '');
        }
        return;
      }
      if (entry?.tree.node && !plainObject(value[key])) {
        entry.tree.node.data = json(value[key]);
        return;
      }
      const fragment = document.createDocumentFragment(),
        next = buildJson(value[key], fragment);
      if (entry) {
        const anchor = entry.tree.last.nextSibling;
        removeRange(entry.tree.first, entry.tree.last);
        tree.last.parentNode.insertBefore(fragment, anchor);
        entry.tree = next;
      } else {
        const prefix = document.createTextNode(`${tree.entries.size ? ',' : ''}${json(key)}:`);
        tree.last.parentNode.insertBefore(prefix, tree.last);
        tree.last.parentNode.insertBefore(fragment, tree.last);
        tree.entries.set(key, { prefix, tree: next });
      }
      return;
    }
  }
  resetJson();
  function descriptorKey(d) {
    return json(d);
  }
  function checkDescriptor(d) {
    if (
      !plainObject(d) ||
      !['meta', 'style', 'attrs', 'image', 'subtree', 'placement', 'slide', 'slide-order'].includes(
        d.kind,
      )
    )
      throw Error('Ungültiger Bearbeitungsbereich.');
    const allowed = {
      slide: ['kind', 'id'],
      'slide-order': ['kind', 'id'],
      meta: ['kind', 'path'],
      style: ['kind', 'id', 'properties'],
      attrs: ['kind', 'id', 'names'],
      image: ['kind', 'id'],
      subtree: ['kind', 'id'],
      placement: ['kind', 'id', 'slideId', 'parentId', 'beforeId'],
    }[d.kind];
    if (Object.keys(d).some((key) => !allowed.includes(key)))
      throw Error('Ungültige Bereichsangabe.');
    if (d.kind === 'meta') {
      if (
        !Array.isArray(d.path) ||
        d.path.length < 1 ||
        d.path.length > 8 ||
        d.path.some(
          (key) =>
            typeof key !== 'string' ||
            !key ||
            ['__proto__', 'prototype', 'constructor'].includes(key),
        )
      )
        throw Error('Ungültiger Metadatenpfad.');
      if (
        [
          'schemaVersion',
          'deckId',
          'revision',
          'templateId',
          'templateVersion',
          'pageWidth',
          'pageHeight',
        ].includes(d.path[0])
      )
        throw Error('Die gespeicherte Dokumentidentität ist unveränderlich.');
    } else {
      if (typeof d.id !== 'string' || !d.id) throw Error('Objektkennung fehlt.');
      if (['subtree', 'placement'].includes(d.kind) && slideNodes.has(d.id))
        throw Error('Textänderungen dürfen keine ganze Folie erfassen.');
      if (['style', 'attrs'].includes(d.kind)) {
        const names = d.kind === 'style' ? d.properties : d.names;
        if (
          !Array.isArray(names) ||
          !names.length ||
          names.some((name) => typeof name !== 'string' || !/^[a-zA-Z][-a-zA-Z0-9:]*$/.test(name))
        )
          throw Error('Ungültige lokale Eigenschaft.');
        if (
          d.kind === 'attrs' &&
          names.some(
            (name) =>
              ['data-sf-id', 'data-sf-kind', 'data-sf-slide'].includes(name) ||
              /^on/i.test(name) ||
              name.startsWith('data-sf-runtime-'),
          )
        )
          throw Error('Identitäts- und Laufzeitattribute sind keine editierbaren Werte.');
      }
      if (
        d.kind === 'placement' &&
        (typeof d.slideId !== 'string' ||
          typeof d.parentId !== 'string' ||
          (d.beforeId != null && typeof d.beforeId !== 'string'))
      )
        throw Error('Ungültige Einfügeposition.');
    }
    return d;
  }
  function normalize(scopes) {
    if (!Array.isArray(scopes) || !scopes.length || scopes.length > 1024)
      throw Error('Ein lokaler Bearbeitungsbereich fehlt.');
    const result = [];
    for (const source of scopes) {
      const d = checkDescriptor(copyValue(source));
      if (d.properties) d.properties = [...new Set(d.properties)].sort();
      if (d.names) d.names = [...new Set(d.names)].sort();
      const previous = result.find(
        (item) =>
          item.kind === d.kind &&
          (d.kind === 'meta' ? json(item.path) === json(d.path) : item.id === d.id),
      );
      if (previous && d.properties)
        previous.properties = [...new Set([...previous.properties, ...d.properties])].sort();
      else if (previous && d.names)
        previous.names = [...new Set([...previous.names, ...d.names])].sort();
      else if (!previous) result.push(d);
    }
    return freeze(
      result.filter(
        (d) =>
          !result.some(
            (owner) =>
              owner !== d &&
              ((owner.kind === 'meta' &&
                d.kind === 'meta' &&
                owner.path.length < d.path.length &&
                owner.path.every((key, i) => key === d.path[i])) ||
                (['subtree', 'placement'].includes(owner.kind) &&
                  d.kind !== 'meta' &&
                  (owner.id === d.id ||
                    (nodeFor(owner.id) &&
                      nodeFor(d.id) &&
                      nodeFor(owner.id).contains(nodeFor(d.id)))))),
          ),
      ),
    );
  }
  function readMeta(path, source = meta) {
    let value = source;
    for (let i = 0; i < path.length - 1; i++) {
      value = value?.[path[i]];
      if (!plainObject(value)) return { present: false };
    }
    const present = Object.prototype.hasOwnProperty.call(value, path[path.length - 1]);
    return { present, ...(present ? { value: copyValue(value[path[path.length - 1]]) } : {}) };
  }
  function writeMeta(path, record, source = meta) {
    let parent = source;
    for (let i = 0; i < path.length - 1; i++) {
      if (!plainObject(parent[path[i]])) parent[path[i]] = {};
      parent = parent[path[i]];
    }
    if (record.present) parent[path[path.length - 1]] = copyValue(record.value);
    else delete parent[path[path.length - 1]];
  }
  const frameProperties = ['position', 'left', 'top', 'width', 'height', 'overflow'];
  function readStyles(element, names) {
    return Object.fromEntries(
      names.map((name) => [
        name,
        {
          value: element.style.getPropertyValue(name),
          priority: element.style.getPropertyPriority(name),
        },
      ]),
    );
  }
  function writeStyles(element, values) {
    for (const [name, entry] of Object.entries(values)) {
      if (entry.value) element.style.setProperty(name, entry.value, entry.priority);
      else element.style.removeProperty(name);
    }
    if (!element.style.length) element.removeAttribute('style');
  }
  function authoredState(element) {
    const clone = clean(element.cloneNode(true)),
      refs = new Set();
    for (const img of clone.querySelectorAll('img[src]')) {
      const src = img.getAttribute('src');
      if (!assetSource(src)) continue;
      const original = asset(src, {
        width: img.getAttribute('width'),
        height: img.getAttribute('height'),
      });
      refs.add(original.id);
      img.removeAttribute('src');
      img.setAttribute('data-sf-journal-asset', original.id);
    }
    const state = { html: clone.outerHTML };
    scopeRefs.set(state, refs);
    scopeIds.set(
      state,
      new Set(
        [clone, ...clone.querySelectorAll('[data-sf-id]')]
          .map((node) => node.dataset.sfId)
          .filter(Boolean),
      ),
    );
    return state;
  }
  function idsFor(value) {
    if (!value?.html) return new Set();
    const cached = scopeIds.get(value);
    if (cached) return cached;
    const template = document.createElement('template');
    template.innerHTML = value.html;
    const ids = new Set(
      [...template.content.querySelectorAll('[data-sf-id]')].map((node) => node.dataset.sfId),
    );
    scopeIds.set(value, ids);
    return ids;
  }
  const untrackedChildren = (parent) =>
    [...parent.children].filter(
      (node) => !node.matches('[data-sf-id],[data-sf-slide],[data-sf-transient]'),
    );
  const placementNodes = (parent) =>
    [...parent.childNodes].filter(
      (node) => node.nodeType !== 1 || !node.hasAttribute('data-sf-transient'),
    );
  function placementElement(d, lookup = nodeFor) {
    const anchor = lookup(d.parentId),
      known = lookup(d.id);
    const element =
      known && anchor?.contains(known)
        ? known
        : anchor?.querySelector(`[data-sf-id="${CSS.escape(d.id)}"]`) || null;
    if (element && element.parentElement.closest('[data-sf-id],[data-sf-slide]') !== anchor)
      throw Error('Der stabile Elternanker passt nicht zum Objekt.');
    return element;
  }
  function placementParent(d, value, lookup = nodeFor) {
    let parent = lookup(value.parentId);
    if (
      value.parentId !== d.parentId ||
      !parent ||
      parent.closest('[data-sf-slide]')?.dataset.sfSlide !== d.slideId
    )
      throw Error('Der stabile Elternanker fehlt.');
    for (const index of value.parentPath || []) {
      parent = untrackedChildren(parent)[index];
      if (!parent) throw Error('Der lokale Elternpfad fehlt.');
    }
    return parent;
  }
  function placementPosition(d, element) {
    const parent = element.parentElement,
      anchor = parent.closest('[data-sf-id],[data-sf-slide]'),
      parentId = anchor?.dataset.sfId || anchor?.dataset.sfSlide,
      parentPath = [];
    if (parentId !== d.parentId || anchor.closest('[data-sf-slide]')?.dataset.sfSlide !== d.slideId)
      throw Error('Die Objektposition hat keinen passenden Elternanker.');
    for (let node = parent; node !== anchor; node = node.parentElement) {
      const index = untrackedChildren(node.parentElement).indexOf(node);
      if (index < 0 || parentPath.length >= 128) throw Error('Der lokale Elternpfad ist ungültig.');
      parentPath.unshift(index);
    }
    const siblings = placementNodes(parent),
      following = siblings.slice(siblings.indexOf(element) + 1);
    const offset = following.findIndex(
      (node) => node.nodeType === 1 && node.hasAttribute('data-sf-id'),
    );
    return {
      parentId,
      parentPath,
      beforeId: offset < 0 ? null : following[offset].dataset.sfId,
      beforeOffset: offset < 0 ? following.length : offset,
    };
  }
  function readScope(d, lookup = nodeFor, source = meta) {
    if (d.kind === 'meta') return readMeta(d.path, source);
    if (d.kind === 'slide' || d.kind === 'slide-order') {
      const node = lookup(d.id);
      if (!node || !node.parentElement) return { present: false };
      const placement = {
        beforeId: node.nextElementSibling?.dataset.sfSlide || null,
        afterId: node.previousElementSibling?.dataset.sfSlide || null,
      };
      if (d.kind === 'slide-order') return placement;
      const authored = authoredState(node),
        value = {
          present: true,
          ...placement,
          html: authored.html,
          metadata: Object.fromEntries(
            ['notes', 'notesFormat', 'notesProvenance', 'guidance'].map((key) => [
              key,
              readMeta([key, d.id], source),
            ]),
          ),
        };
      scopeRefs.set(value, scopeRefs.get(authored));
      scopeIds.set(value, scopeIds.get(authored));
      return value;
    }
    const element = d.kind === 'placement' ? placementElement(d, lookup) : lookup(d.id);
    if (d.kind === 'placement') {
      if (!element) return { present: false };
      const authored = authoredState(element),
        state = { present: true, html: authored.html, ...placementPosition(d, element) };
      scopeRefs.set(state, scopeRefs.get(authored));
      scopeIds.set(state, scopeIds.get(authored));
      return state;
    }
    if (!element) throw Error('Das bearbeitete Objekt ist nicht mehr verfügbar.');
    if (d.kind === 'style') return readStyles(element, d.properties);
    if (d.kind === 'attrs')
      return Object.fromEntries(
        d.names.map((name) => [
          name,
          element.hasAttribute(name) ? element.getAttribute(name) : null,
        ]),
      );
    if (d.kind === 'subtree') return authoredState(element);
    if (d.kind === 'image') {
      const img = element.querySelector(':scope > img');
      if (!img) throw Error('Das Originalbild fehlt.');
      return {
        asset: asset(img.getAttribute('src'), {
          width: img.getAttribute('width'),
          height: img.getAttribute('height'),
        }).id,
        attributes: Object.fromEntries(
          [...img.attributes]
            .filter((a) => a.name !== 'src' && !a.name.startsWith('data-sf-runtime-'))
            .map((a) => [a.name, a.value]),
        ),
        crop: element.getAttribute('data-sf-crop'),
        style: readStyles(element, frameProperties),
      };
    }
  }
  function capture(scopes) {
    const descriptors = normalize(scopes),
      values = descriptors.map((descriptor) =>
        freeze({ descriptor, value: freeze(readScope(descriptor)) }),
      );
    const baseline = freeze(values);
    baselines.set(baseline, json(descriptors));
    return baseline;
  }
  function begin(label, scopes, { mode = 'input', before } = {}) {
    const descriptors = normalize(scopes);
    if (!['input', 'preview'].includes(mode)) throw Error('Ungültiger Bearbeitungsmodus.');
    if (before && baselines.get(before) !== json(descriptors))
      throw Error('Die lokale Ausgangslage passt nicht zum Bearbeitungsbereich.');
    const baseline = before || capture(descriptors),
      token = Object.freeze({});
    const roots = new Map();
    for (const d of descriptors)
      if (d.kind !== 'meta') {
        const element = nodeFor(d.id);
        roots.set(
          d.id,
          element
            ? {
                element,
                kind: element.dataset.sfKind,
                parent: element.parentElement,
                next: element.nextSibling,
                nodes: ['subtree', 'placement', 'slide'].includes(d.kind)
                  ? [element, ...element.querySelectorAll('[data-sf-id]')]
                  : [element],
              }
            : null,
        );
      }
    const assetRefs = refsIn(baseline);
    adjustRefs(activeRefs, assetRefs, 1);
    sessions.set(token, {
      label: String(label),
      mode,
      descriptors,
      before: baseline,
      roots,
      assetRefs,
      state: 'input',
    });
    return token;
  }
  function syncScopes(descriptors) {
    for (const d of descriptors)
      if (d.kind === 'slide')
        for (const key of ['notes', 'notesFormat', 'notesProvenance', 'guidance'])
          syncPath([key, d.id]);
    for (const d of descriptors)
      if (d.kind === 'meta') {
        syncPath(d.path);
        if (['colorScheme', 'backgroundColor'].includes(d.path[0]) && schemes[meta.colorScheme])
          applyTheme();
      }
  }
  function update(token, mutate = () => {}) {
    const session = sessions.get(token);
    if (!session) return false;
    try {
      mutate();
      syncScopes(session.descriptors);
      session.state = session.mode === 'preview' ? 'preview' : 'input';
      for (const d of session.descriptors) if (d.kind !== 'meta') layout(nodeFor(d.id), 'preview');
      emit('update');
      return true;
    } catch (error) {
      cancel(token);
      emit('error', { message: error.message });
      return false;
    }
  }
  function inflateHtml(html) {
    if (typeof html !== 'string' || html.length > 64 * 1024 * 1024)
      throw Error('Ungültiger lokaler HTML-Bereich.');
    const template = document.createElement('template');
    template.innerHTML = html;
    if (
      template.content.children.length !== 1 ||
      template.content.querySelector(
        '[data-sf-transient],[data-sf-runtime-text],[data-sf-draft-asset],[data-sf-snapshot-asset]',
      )
    )
      throw Error('Ungültiger lokaler Quelltext.');
    for (const img of template.content.querySelectorAll('img[data-sf-journal-asset]')) {
      const id = img.getAttribute('data-sf-journal-asset'),
        original = assets.get(id);
      if (!original || img.hasAttribute('src'))
        throw Error('Der Originalbild-Verweis fehlt oder ist beschädigt.');
      img.setAttribute('src', original.src);
      img.removeAttribute('data-sf-journal-asset');
    }
    return template.content.firstElementChild;
  }
  function applyScope(
    d,
    value,
    lookup = nodeFor,
    source = meta,
    targetDeck = deck,
    staging = false,
  ) {
    if (d.kind === 'meta') {
      writeMeta(d.path, value, source);
      return;
    }
    if (d.kind === 'slide' || d.kind === 'slide-order') {
      const existing = lookup(d.id);
      if (d.kind === 'slide' && !value.present) {
        existing?.remove();
        for (const key of ['notes', 'notesFormat', 'notesProvenance', 'guidance'])
          writeMeta([key, d.id], { present: false }, source);
        return;
      }
      const before = value.beforeId ? lookup(value.beforeId) : null,
        after = value.afterId ? lookup(value.afterId) : null;
      if (!staging && value.beforeId && !before && value.afterId && !after)
        throw Error('Der Folienanker fehlt.');
      if (
        (before && before.parentElement !== targetDeck) ||
        (after && after.parentElement !== targetDeck) ||
        before === existing ||
        after === existing
      )
        throw Error('Ungültiger Folienanker.');
      const node = d.kind === 'slide' ? inflateHtml(value.html) : existing;
      if (!node || node.dataset.sfSlide !== d.id || node.tagName !== 'SECTION')
        throw Error('Die Folienidentität fehlt.');
      existing?.remove();
      const anchor = before || after?.nextElementSibling || null;
      targetDeck.insertBefore(node, anchor);
      if (d.kind === 'slide')
        for (const key of ['notes', 'notesFormat', 'notesProvenance', 'guidance'])
          writeMeta([key, d.id], value.metadata[key], source);
      return;
    }
    const element = d.kind === 'placement' ? placementElement(d, lookup) : lookup(d.id);
    if (d.kind === 'placement') {
      if (!value.present) {
        element?.remove();
        return;
      }
      const parent = placementParent(d, value, lookup),
        before = value.beforeId ? lookup(value.beforeId) : null;
      if (
        (before && (before.parentElement !== parent || before === element)) ||
        (value.beforeId && !before)
      )
        throw Error('Der stabile Einfügeanker fehlt.');
      const siblings = placementNodes(parent).filter((node) => node !== element),
        anchorIndex = before ? siblings.indexOf(before) : siblings.length,
        offset = value.beforeOffset || 0;
      if (
        anchorIndex < offset ||
        siblings
          .slice(anchorIndex - offset, anchorIndex)
          .some((node) => node.nodeType === 1 && node.hasAttribute('data-sf-id'))
      )
        throw Error('Die lokale Einfügeposition passt nicht zum Anker.');
      const target = siblings[anchorIndex - offset] || null;
      const next = inflateHtml(value.html);
      if (next.dataset.sfId !== d.id)
        throw Error('Die Objektkennung im Einfügebereich stimmt nicht.');
      element?.remove();
      parent.insertBefore(next, target);
      return;
    }
    if (!element) throw Error('Der lokale Zielbereich fehlt.');
    if (d.kind === 'subtree') {
      const next = inflateHtml(value.html);
      if (next.dataset.sfId !== d.id) throw Error('Die Objektkennung wurde verändert.');
      element.replaceWith(next);
    }
    if (d.kind === 'style') writeStyles(element, value);
    if (d.kind === 'attrs')
      for (const [name, entry] of Object.entries(value)) {
        if (entry === null) element.removeAttribute(name);
        else element.setAttribute(name, entry);
      }
    if (d.kind === 'image') {
      const original = assets.get(value.asset);
      if (!original) throw Error('Das Originalbild fehlt.');
      let img = element.querySelector(':scope > img');
      if (!img) {
        img = document.createElement('img');
        element.append(img);
      }
      for (const attr of [...img.attributes]) img.removeAttribute(attr.name);
      for (const [name, entry] of Object.entries(value.attributes)) img.setAttribute(name, entry);
      img.setAttribute('src', original.src);
      if (value.crop === null) element.removeAttribute('data-sf-crop');
      else element.setAttribute('data-sf-crop', value.crop);
      writeStyles(element, value.style);
    }
  }
  function validateMetaScope(d) {
    const value = readMeta(d.path),
      [key, id] = d.path;
    if (
      key === 'postitsVisible' &&
      (d.path.length !== 1 || (value.present && typeof value.value !== 'boolean'))
    )
      throw Error('Ungültige Post-it-Sichtbarkeit.');
    if (
      key === 'backgroundColor' &&
      (d.path.length !== 1 || (value.present && !/^#[0-9a-f]{6}$/i.test(value.value)))
    )
      throw Error('Ungültige Hintergrundfarbe.');
    if (key === 'colorScheme' && (d.path.length !== 1 || !schemes[meta.colorScheme]))
      throw Error('Das Farbschema fehlt.');
    if (['notes', 'guidance', 'notesProvenance', 'notesFormat'].includes(key)) {
      if (d.path.length !== 2 || !slideNodes.has(id))
        throw Error('Notizen und Hinweise benötigen eine gültige Folie.');
      if (!value.present) return;
      const entry = value.value;
      if (key === 'notesFormat') notesCodec.validate(entry);
      if (key === 'notes' && typeof entry !== 'string')
        throw Error('Referentennotizen müssen Text sein.');
      if (
        key === 'guidance' &&
        (!plainObject(entry) ||
          typeof entry.text !== 'string' ||
          !['open', 'addressed'].includes(entry.status))
      )
        throw Error('Ungültiger Hinweis für den Agenten.');
      if (
        key === 'notesProvenance' &&
        (!plainObject(entry) || typeof entry.html !== 'string' || typeof entry.text !== 'string')
      )
        throw Error('Ungültige Notizenherkunft.');
    }
  }
  function validateImage(element) {
    const imgs = element.querySelectorAll('img'),
      img = imgs[0],
      crop = JSON.parse(element.dataset.sfCrop || 'null');
    const nw = Number(img?.getAttribute('width')),
      nh = Number(img?.getAttribute('height'));
    if (
      imgs.length !== 1 ||
      img.parentElement !== element ||
      !imageSource(img.getAttribute('src')) ||
      !Number.isFinite(nw) ||
      !Number.isFinite(nh) ||
      nw <= 0 ||
      nh <= 0
    )
      throw Error('Ein Bildrahmen benötigt genau ein direktes Original mit gültiger Größe.');
    if (
      !crop ||
      !['x', 'y', 'w', 'h'].every((k) => Number.isFinite(crop[k])) ||
      crop.x < 0 ||
      crop.y < 0 ||
      crop.w <= 0 ||
      crop.h <= 0 ||
      crop.x + crop.w > 1.000001 ||
      crop.y + crop.h > 1.000001
    )
      throw Error('Ungültiger Bildausschnitt.');
    const geometry = ['left', 'top', 'width', 'height'].map((name) => {
      const value = element.style[name];
      if (!/^-?(?:\d+(?:\.\d*)?|\.\d+)px$/.test(value) || !Number.isFinite(parseFloat(value)))
        throw Error('Bildrahmen benötigen endliche Pixelwerte.');
      return parseFloat(value);
    });
    if (
      geometry[2] <= 0 ||
      geometry[3] <= 0 ||
      Math.abs((crop.w * nw) / (crop.h * nh) / (geometry[2] / geometry[3]) - 1) > 0.00001
    )
      throw Error('Bildausschnitt und Rahmen müssen dasselbe Seitenverhältnis haben.');
  }
  function validateScopes(session) {
    if (session.descriptors.some((d) => ['slide', 'slide-order'].includes(d.kind))) {
      validate();
      for (const d of session.descriptors) {
        if (
          d.kind === 'slide-order' &&
          (nodeFor(d.id) !== session.roots.get(d.id)?.element ||
            nodeFor(d.id)?.parentElement !== deck)
        )
          throw Error('Ungültige Folienverschiebung.');
      }
      return;
    }
    const removed = new Set(),
      added = new Map();
    for (const root of session.roots.values())
      for (const node of root?.nodes || []) removed.add(node.dataset.sfId);
    for (const d of session.descriptors) {
      if (d.kind === 'meta') {
        validateMetaScope(d);
        continue;
      }
      const old = session.roots.get(d.id),
        known = nodeFor(d.id);
      const element =
        d.kind === 'placement'
          ? placementElement(d)
          : known?.isConnected
            ? known
            : d.kind === 'subtree'
              ? [...(old?.parent?.children || [])].find((node) => node.dataset.sfId === d.id)
              : known;
      if (!element) {
        if (d.kind === 'placement') continue;
        throw Error('Das bearbeitete Objekt fehlt.');
      }
      if (
        d.kind === 'placement' &&
        (element.closest('[data-sf-slide]')?.dataset.sfSlide !== d.slideId ||
          element.parentElement.closest('[data-sf-id],[data-sf-slide]') !== nodeFor(d.parentId))
      )
        throw Error('Die Einfügeposition wurde verändert.');
      const promoted =
        d.kind === 'subtree' &&
        old?.kind === 'text' &&
        /^(P|H[1-6])$/.test(old.element.tagName) &&
        element.tagName === 'DIV' &&
        !old.element.isConnected;
      if (
        d.kind !== 'placement' &&
        ((!promoted && element !== old?.element) ||
          (slideNodes.has(d.id) ? element.dataset.sfSlide : element.dataset.sfId) !== d.id ||
          element.dataset.sfKind !== old.kind ||
          element.parentElement !== old.parent)
      )
        throw Error('Eine lokale Bearbeitung darf Identität und Elternanker nicht verändern.');
      if (slideNodes.get(d.id) === element) {
        if (
          !['style', 'attrs'].includes(d.kind) ||
          element.dataset.sfSlide !== d.id ||
          element.hasAttribute('data-sf-id') ||
          !element.classList.contains('sf-slide')
        )
          throw Error('Die Folienidentität wurde verändert.');
        validateTiming(element);
        continue;
      }
      const nodes = ['subtree', 'placement'].includes(d.kind)
        ? [element, ...element.querySelectorAll('[data-sf-id]')]
        : [element];
      for (const node of nodes) {
        const id = node.dataset.sfId;
        if (
          !id ||
          (added.has(id) && added.get(id) !== node) ||
          slideNodes.has(id) ||
          (objects.has(id) && !removed.has(id)) ||
          !['text', 'box', 'image'].includes(node.dataset.sfKind) ||
          !node.closest('[data-sf-slide]')
        )
          throw Error('Objektkennungen fehlen, sind doppelt oder haben einen ungültigen Typ.');
        added.set(id, node);
        if (
          node.hasAttribute('data-sf-layout') &&
          (!['flow', 'inline'].includes(node.dataset.sfLayout) || node.dataset.sfKind === 'image')
        )
          throw Error('Ungültiger Layoutmodus.');
        validateLink(node);
        if (node.dataset.sfKind === 'image') validateImage(node);
      }
    }
  }
  function refreshLocal(descriptors, roots = null) {
    if (descriptors.some((d) => ['slide', 'slide-order'].includes(d.kind))) {
      rebuildIndexes();
      return;
    }
    // Capture root membership before removal; updating indexes is proportional to changed subtrees.
    for (const d of descriptors)
      if (['subtree', 'placement'].includes(d.kind)) {
        const old =
          roots?.get(d.id)?.nodes ||
          (objects.get(d.id)
            ? [objects.get(d.id), ...objects.get(d.id).querySelectorAll('[data-sf-id]')]
            : []);
        for (const node of old) {
          const id = node.dataset.sfId;
          objects.delete(id);
          adjustRefs(liveRefs, objectAssets.get(id) || [], -1);
          objectAssets.delete(id);
        }
        const parent = d.kind === 'placement' ? nodeFor(d.parentId) : roots?.get(d.id)?.parent;
        const known = roots?.get(d.id)?.element;
        const element =
          d.kind === 'placement'
            ? placementElement(d)
            : known?.isConnected && known.dataset.sfId === d.id
              ? known
              : [...(parent?.children || [])].find((node) => node.dataset.sfId === d.id);
        const nextNodes = element ? [element, ...element.querySelectorAll('[data-sf-id]')] : [];
        for (const node of nextNodes) {
          objects.set(node.dataset.sfId, node);
          trackObjectAssets(node);
        }
        const sid =
          element?.closest('[data-sf-slide]')?.dataset.sfSlide ||
          roots?.get(d.id)?.parent?.closest('[data-sf-slide]')?.dataset.sfSlide ||
          d.slideId;
        const beforeTitles = old.filter(titleCandidate).map((node) => node.dataset.sfId),
          afterTitles = nextNodes.filter(titleCandidate).map((node) => node.dataset.sfId);
        if (sid && json(beforeTitles) !== json(afterTitles)) {
          const removedTitles = new Set(beforeTitles),
            candidates = (titleCandidates.get(sid) || []).filter((id) => !removedTitles.has(id));
          candidates.push(...afterTitles);
          candidates.sort((a, b) => {
            const first = objects.get(a),
              second = objects.get(b);
            return first === second
              ? 0
              : first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING
                ? -1
                : 1;
          });
          titleCandidates.set(sid, candidates);
        }
      }
    for (const d of descriptors)
      if (d.kind === 'image') {
        const element = objects.get(d.id);
        if (element) trackObjectAssets(element);
      }
  }
  function rootsFor(descriptors) {
    return new Map(
      descriptors
        .filter((d) => d.kind !== 'meta')
        .map((d) => {
          const element = nodeFor(d.id);
          return [
            d.id,
            element
              ? {
                  element,
                  parent: element.parentElement,
                  next: element.nextSibling,
                  nodes: ['subtree', 'placement', 'slide'].includes(d.kind)
                    ? [element, ...element.querySelectorAll('[data-sf-id]')]
                    : [element],
                }
              : null,
          ];
        }),
    );
  }
  function applyChanges(changes, direction, phase) {
    const ordered = direction === 'before' ? [...changes].reverse() : changes;
    for (const change of ordered) {
      const roots = rootsFor([change.descriptor]);
      applyScope(change.descriptor, change[direction]);
      refreshLocal([change.descriptor], roots);
      if (change.descriptor.kind === 'meta') syncPath(change.descriptor.path);
      else if (change.descriptor.kind === 'slide') {
        syncScopes([change.descriptor]);
        layout(nodeFor(change.descriptor.id), phase);
      } else layout(nodeFor(change.descriptor.id), phase);
    }
    if (
      changes.some(
        (c) =>
          c.descriptor.kind === 'meta' &&
          ['colorScheme', 'backgroundColor'].includes(c.descriptor.path[0]),
      )
    )
      applyTheme();
  }
  function cancel(token) {
    const session = sessions.get(token);
    if (!session) return false;
    sessions.delete(token);
    adjustRefs(activeRefs, session.assetRefs, -1);
    session.state = 'cancelled';
    for (const d of session.descriptors) {
      const root = session.roots.get(d.id);
      if (!root || ['placement', 'slide', 'slide-order'].includes(d.kind)) continue;
      const element = root.element;
      if (!element.dataset.sfSlide) element.dataset.sfId = d.id;
      if (root.kind) element.dataset.sfKind = root.kind;
      if (element.parentElement !== root.parent) {
        if (d.kind === 'subtree')
          for (const replacement of [...root.parent.children])
            if (replacement !== element && replacement.dataset.sfId === d.id) replacement.remove();
        root.parent.insertBefore(element, root.next?.parentNode === root.parent ? root.next : null);
      }
    }
    const changes = session.before.map((entry) => ({
      descriptor: entry.descriptor,
      before: entry.value,
    }));
    applyChanges(changes, 'before', 'preview');
    scheduleCheckpoint();
    return true;
  }
  function affected(changes) {
    if (changes.some((c) => ['slide', 'slide-order'].includes(c.descriptor.kind))) {
      const ids = new Set(slideOrder.map((s) => s.dataset.sfSlide)),
        objectIds = new Set(),
        metaPaths = [];
      for (const c of changes) {
        ids.add(c.descriptor.id);
        if (c.descriptor.kind === 'slide') {
          for (const value of [c.before, c.after])
            for (const id of idsFor(value)) objectIds.add(id);
          for (const key of ['notes', 'notesFormat', 'notesProvenance', 'guidance'])
            metaPaths.push([key, c.descriptor.id]);
        }
      }
      return {
        slideIds: [...ids],
        objectIds: [...objectIds],
        metaPaths,
        visual: true,
        theme: false,
        inventory: true,
        structural: true,
      };
    }
    const slideIds = new Set(),
      objectIds = new Set(),
      metaPaths = [],
      visualIds = new Set();
    let theme = false,
      inventory = false;
    for (const change of changes) {
      const d = change.descriptor;
      if (d.kind === 'meta') {
        metaPaths.push([...d.path]);
        if (d.path[1] && slideNodes.has(d.path[1])) slideIds.add(d.path[1]);
        theme ||= ['colorScheme', 'backgroundColor'].includes(d.path[0]);
        if (d.path[0] === 'postitsVisible')
          for (const slide of slideOrder) {
            slideIds.add(slide.dataset.sfSlide);
            visualIds.add(slide.dataset.sfSlide);
          }
      } else {
        objectIds.add(d.id);
        const element = nodeFor(d.id),
          sid = element?.closest('[data-sf-slide]')?.dataset.sfSlide || d.slideId;
        if (sid) {
          slideIds.add(sid);
          visualIds.add(sid);
        }
        if (sid) {
          const slide = slideNodes.get(sid),
            oldTitle = titleNodes.get(sid);
          if (['subtree', 'placement'].includes(d.kind))
            titleNodes.set(sid, objects.get((titleCandidates.get(sid) || [])[0]) || null);
          const position = slidePositions.get(sid),
            title = titleText(titleNodes.get(sid)),
            times = timing(slide),
            old = inventoryEntries[position];
          if (
            old.hidden !== isHidden(slide) ||
            old.title !== title ||
            ['duration', 'part', 'partDuration'].some((key) => old[key] !== times[key])
          ) {
            inventoryEntries[position] = freeze({
              id: sid,
              title,
              hidden: isHidden(slide),
              ...times,
            });
            inventory = true;
          }
        }
      }
    }
    for (const id of visualIds) versions.set(id, (versions.get(id) || 0) + 1);
    for (const id of objectIds) generations.set(id, (generations.get(id) || 0) + 1);
    return {
      slideIds: [...slideIds],
      objectIds: [...objectIds],
      metaPaths,
      visual: visualIds.size > 0,
      theme,
      inventory,
      visibility: changes.some(
        ({ descriptor: d }) => d.kind === 'attrs' && d.names.includes('data-sf-hidden'),
      ),
    };
  }
  function gcAssets() {
    for (const id of gcCandidates) {
      gcCandidates.delete(id);
      if (
        liveRefs.has(id) ||
        historyRefs.has(id) ||
        activeRefs.has(id) ||
        pendingRefs.has(id) ||
        projectionRefs.has(id) ||
        durableRefs.has(id)
      )
        continue;
      const original = assets.get(id);
      if (original) {
        assets.delete(id);
        assetBySource.delete(original.src);
      }
    }
  }
  function deleteProjection(key) {
    const entry = projection.get(key);
    if (entry) {
      adjustRefs(projectionRefs, refsFor(entry.descriptor, entry.after), -1);
      projection.delete(key);
      if (entry.descriptor.kind !== 'meta') {
        const keys = projectionKeys.get(entry.descriptor.id);
        keys?.delete(key);
        if (!keys?.size) projectionKeys.delete(entry.descriptor.id);
      }
    }
  }
  // Delete/reinsert preserves last-write causal order, including journal recovery.
  function setProjection(key, entry) {
    deleteProjection(key);
    projection.set(key, entry);
    adjustRefs(projectionRefs, refsFor(entry.descriptor, entry.after), 1);
    if (entry.descriptor.kind !== 'meta') {
      if (!projectionKeys.has(entry.descriptor.id))
        projectionKeys.set(entry.descriptor.id, new Set());
      projectionKeys.get(entry.descriptor.id).add(key);
    }
  }
  function removeHistory(entry) {
    historyBytes -= entry.bytes;
    adjustRefs(historyRefs, entry.assetRefs, -1);
  }
  function addHistory(entry) {
    historyBytes += entry.bytes;
    adjustRefs(historyRefs, entry.assetRefs, 1);
  }
  function trimHistory() {
    const bytes = () => historyBytes + historyAssetBytes;
    while (past.length + future.length > 80 || bytes() > historyBudget) {
      if (past.length > 1) removeHistory(past.shift());
      else if (future.length) removeHistory(future.shift());
      else break;
    }
    const excess = bytes() - historyBudget;
    if (excess > 0)
      emit('storage', {
        message: `Die letzte Änderung überschreitet das Verlaufslimit um ${Math.ceil(excess / 1024 / 1024)} MiB und bleibt rückgängig machbar. Bitte HTML speichern.`,
      });
    gcAssets();
  }
  function projectChange(change, seq, previousState = null, previousIds = []) {
    if (['placement', 'subtree', 'slide'].includes(change.descriptor.kind)) {
      const owned = new Set([change.descriptor.id, ...previousIds]);
      for (const state of [previousState, change.after])
        for (const id of idsFor(state)) owned.add(id);
      for (const id of owned)
        for (const key of [...(projectionKeys.get(id) || [])]) deleteProjection(key);
    }
    if (change.descriptor.kind === 'slide')
      for (const key of ['notes', 'notesFormat', 'notesProvenance', 'guidance'])
        deleteProjection(descriptorKey({ kind: 'meta', path: [key, change.descriptor.id] }));
    setProjection(descriptorKey(change.descriptor), {
      descriptor: change.descriptor,
      after: change.after,
      seq,
    });
  }
  function prepareJournal(changes, direction) {
    const prepared = [];
    for (const original of changes) {
      const change = freeze({ descriptor: original.descriptor, after: original[direction] });
      prepared.push(change);
      projectChange(change, sequence, original.before, idsFor(original.after));
    }
    const entry = freeze({
      id: freshId(),
      seq: sequence,
      changes: prepared,
      assetRefs: [...refsIn(prepared)],
    });
    pending.push(entry);
    adjustRefs(pendingRefs, entry.assetRefs, 1);
    checkpointGeneration++;
    clearTimeout(draftTimer);
    draftTimer = setTimeout(flushDraft, 250);
  }
  function commit(token) {
    const session = sessions.get(token);
    if (!session) return false;
    try {
      validateScopes(session);
      // Newly inserted objects enter the indexes before their after-state is captured.
      refreshLocal(session.descriptors, session.roots);
      const changes = session.before.map((entry) =>
        freeze({
          descriptor: entry.descriptor,
          before: entry.value,
          after: freeze(readScope(entry.descriptor)),
        }),
      );
      syncScopes(session.descriptors);
      sessions.delete(token);
      adjustRefs(activeRefs, session.assetRefs, -1);
      session.state = 'committed';
      if (changes.every((c) => json(c.before) === json(c.after))) {
        gcAssets();
        scheduleCheckpoint();
        return false;
      }
      sequence++;
      const entry = freeze({
        seq: sequence,
        label: session.label,
        changes,
        assetRefs: [...refsIn(changes)],
        bytes: json(changes).length * 2,
      });
      for (const previous of future) removeHistory(previous);
      future.length = 0;
      past.push(entry);
      addHistory(entry);
      const detail = affected(changes);
      for (const d of session.descriptors) if (d.kind !== 'meta') layout(nodeFor(d.id), 'commit');
      prepareJournal(changes, 'after');
      trimHistory();
      emit('change', { seq: sequence, label: session.label, phase: 'commit', ...detail });
      return true;
    } catch (error) {
      cancel(token);
      emit('error', { message: error.message });
      return false;
    }
  }
  function run(label, scopes, mutate) {
    const token = begin(label, scopes);
    return update(token, mutate) && commit(token);
  }
  function registerSettler(name, callback) {
    if (typeof callback !== 'function') throw Error('Ungültiger Abschlussmechanismus.');
    settlers.set(name, callback);
    return () => settlers.delete(name);
  }
  function settle(reason = 'command') {
    if (settling) return;
    settling = true;
    const preview = ['undo', 'redo'].includes(reason) ? 'cancel' : 'commit';
    if (['undo', 'redo', 'done', 'pagehide', 'dispose'].includes(reason)) lifecycle++;
    try {
      const callbacks = [...settlers.entries()].sort(
        ([a], [b]) => Number(a.includes('preview')) - Number(b.includes('preview')),
      );
      for (const [, callback] of callbacks) callback({ reason, preview });
      for (const [token, session] of [...sessions]) {
        if (session.mode === 'preview' && preview === 'cancel') cancel(token);
        else commit(token);
      }
    } finally {
      settling = false;
    }
  }
  function undo() {
    settle('undo');
    const entry = past.pop();
    if (!entry) return false;
    applyChanges(entry.changes, 'before', 'undo');
    future.push(entry);
    sequence++;
    const detail = affected(entry.changes);
    prepareJournal(entry.changes, 'before');
    emit('change', { seq: sequence, label: 'Rückgängig', phase: 'undo', ...detail });
    return true;
  }
  function redo() {
    settle('redo');
    const entry = future.pop();
    if (!entry) return false;
    applyChanges(entry.changes, 'after', 'undo');
    past.push(entry);
    sequence++;
    const detail = affected(entry.changes);
    prepareJournal(entry.changes, 'after');
    emit('change', { seq: sequence, label: 'Wiederholen', phase: 'redo', ...detail });
    return true;
  }
  function ticket({ slideId, elementId } = {}) {
    const key = elementId || slideId || 'document',
      request = freshId();
    requestOwners.set(key, request);
    return Object.freeze({
      slideId: slideId || null,
      elementId: elementId || null,
      slide: slideId ? slideNodes.get(slideId) : null,
      element: elementId ? objects.get(elementId) : null,
      sequence,
      slideGeneration: slideId ? versions.get(slideId) : null,
      elementGeneration: elementId ? generations.get(elementId) : null,
      lifecycle,
      request,
      key,
    });
  }
  function accepts(value) {
    return (
      !!value &&
      value.lifecycle === lifecycle &&
      (value.slideId || value.elementId || value.sequence === sequence) &&
      requestOwners.get(value.key) === value.request &&
      (!value.slideId ||
        (slideNodes.get(value.slideId) === value.slide &&
          value.slide?.isConnected &&
          versions.get(value.slideId) === value.slideGeneration)) &&
      (!value.elementId ||
        (objects.get(value.elementId) === value.element &&
          value.element?.isConnected &&
          generations.get(value.elementId) === value.elementGeneration))
    );
  }
  function storageFailure() {
    if (!storageMessage) {
      storageMessage =
        'Browserentwurf nicht verfügbar. Bitte die vollständige HTML-Datei speichern.';
      emit('storage', { message: storageMessage });
    }
  }
  function publish(entry, preparedText = null) {
    const writes = [],
      recordKey = `${namespace}entry:${entry.id}`;
    try {
      for (const id of entry.assetRefs) {
        const original = assets.get(id);
        if (!original) throw Error('Das Originalbild fehlt.');
        if (!id.startsWith('new:') || storedAssets.has(id)) continue;
        const assetKey = `${namespace}asset:${id}`;
        localStorage.setItem(
          assetKey,
          json({ id, src: original.src, width: original.width, height: original.height }),
        );
        writes.push(assetKey);
      }
      const record = { ...entry, prev: entry.checkpoint ? null : admittedHead };
      const text = preparedText || json(record);
      localStorage.setItem(recordKey, text);
      writes.push(recordKey);
      localStorage.setItem(storageKey, json({ draftVersion: 2, base, head: entry.id }));
      admittedHead = entry.id;
      durableEntries.add(entry.id);
      recordCount++;
      recordBytes += text.length * 2;
      lastPublishedBytes = text.length * 2;
      for (const id of entry.assetRefs) {
        durableRefs.add(id);
        if (id.startsWith('new:')) storedAssets.add(id);
      }
      if (storageMessage) {
        storageMessage = '';
        emit('storage', { message: 'Browserentwurf wieder verfügbar.' });
      }
      return true;
    } catch {
      for (const key of writes) {
        try {
          localStorage.removeItem(key);
        } catch {}
      }
      storageFailure();
      return false;
    }
  }
  function scheduleCheckpoint() {
    if (
      checkpointTimer !== null ||
      sessions.size ||
      pending.length ||
      !recordCount ||
      (recordCount < 128 && recordBytes < journalBudget)
    )
      return;
    const generation = checkpointGeneration,
      iterator = projection.values(),
      changes = [],
      fragments = new Map(),
      checkpointRefs = new Set();
    let complete = false;
    const idle = (callback) =>
      typeof requestIdleCallback === 'function'
        ? requestIdleCallback(callback, { timeout: 1000 })
        : setTimeout(() => callback({ timeRemaining: () => 4 }), 16);
    function chunk(deadline) {
      checkpointTimer = null;
      if (generation !== checkpointGeneration || pending.length || sessions.size)
        return scheduleCheckpoint();
      let n = 0;
      while (n < 64 && (!n || deadline.timeRemaining() > 1)) {
        const next = iterator.next();
        if (next.done) {
          complete = true;
          break;
        }
        n++;
        const item = next.value,
          change = { descriptor: item.descriptor, after: item.after };
        try {
          if (item.descriptor.kind === 'placement' && item.after.present) {
            const element = placementElement(item.descriptor);
            if (!element) {
              storageFailure();
              return;
            }
            change.after = { ...item.after, ...placementPosition(item.descriptor, element) };
          }
        } catch {
          storageFailure();
          return;
        }
        changes.push(change);
        fragments.set(change, json(change));
        for (const id of refsFor(item.descriptor, item.after)) checkpointRefs.add(id);
      }
      if (!complete) {
        checkpointTimer = idle(chunk);
        return;
      }
      // Final sibling anchors may themselves be new objects. Admit those placements
      // first, while retaining every later style/image edit after its own placement.
      const placements = new Map(
          changes
            .filter((change) => change.descriptor.kind === 'placement' && change.after.present)
            .map((change) => [change.descriptor.id, change]),
        ),
        removals = new Map(),
        ordered = [],
        admitted = new Set(),
        visiting = new Set();
      for (const change of changes)
        if (change.descriptor.kind === 'placement' && !change.after.present) {
          const key = change.descriptor.parentId;
          if (!removals.has(key)) removals.set(key, []);
          removals.get(key).push(change);
        }
      function admit(change) {
        if (admitted.has(change)) return;
        if (visiting.has(change)) throw Error('Zyklische lokale Einfügeanker.');
        visiting.add(change);
        if (change.descriptor.kind === 'placement') {
          const parent = placements.get(change.descriptor.parentId);
          if (parent) admit(parent);
          if (change.after.present) {
            for (const removal of removals.get(change.descriptor.parentId) || []) admit(removal);
            const before = placements.get(change.after.beforeId);
            if (before) admit(before);
          }
        }
        visiting.delete(change);
        admitted.add(change);
        ordered.push(change);
      }
      try {
        for (const change of changes) admit(change);
      } catch {
        storageFailure();
        return;
      }
      const slideIds = ordered.some((change) =>
        ['slide', 'slide-order'].includes(change.descriptor.kind),
      )
        ? slideOrder.map((slide) => slide.dataset.sfSlide)
        : null;
      const oldEntries = [...durableEntries],
        oldAssets = [...durableRefs],
        entry = freeze({
          id: freshId(),
          seq: sequence,
          checkpoint: true,
          changes: ordered,
          assetRefs: [...checkpointRefs],
          ...(slideIds ? { slideOrder: slideIds } : {}),
        });
      const preparedText = `{"id":${json(entry.id)},"prev":null,"seq":${entry.seq},"checkpoint":true,${slideIds ? `"slideOrder":${json(slideIds)},` : ''}"changes":[${ordered.map((change) => fragments.get(change)).join(',')}],"assetRefs":${json(entry.assetRefs)}}`;
      if (generation !== checkpointGeneration || !publish(entry, preparedText)) return;
      durableEntries.clear();
      durableEntries.add(entry.id);
      durableRefs.clear();
      for (const id of entry.assetRefs) durableRefs.add(id);
      for (const id of oldEntries) {
        try {
          localStorage.removeItem(`${namespace}entry:${id}`);
        } catch {}
      }
      for (const id of oldAssets)
        if (id.startsWith('new:') && !durableRefs.has(id)) {
          try {
            localStorage.removeItem(`${namespace}asset:${id}`);
            storedAssets.delete(id);
            gcCandidates.add(id);
          } catch {}
        }
      recordCount = 1;
      recordBytes = lastPublishedBytes;
      gcAssets();
    }
    checkpointTimer = idle(chunk);
  }
  function flushDraft() {
    clearTimeout(draftTimer);
    draftTimer = null;
    if (!pending.length) return;
    if (!base.fingerprint) {
      emit('storage', { message: storageMessage });
      return;
    }
    while (pending.length) {
      const entry = pending[0];
      if (!publish(entry)) break;
      pending.shift();
      adjustRefs(pendingRefs, entry.assetRefs, -1);
    }
    scheduleCheckpoint();
  }
  function checkRecordValue(d, value) {
    if (!plainObject(value)) throw Error('Ungültiger Bereichswert im Browserentwurf.');
    if (
      d.kind === 'meta' &&
      (typeof value.present !== 'boolean' ||
        (value.present && !Object.prototype.hasOwnProperty.call(value, 'value')))
    )
      throw Error('Ungültiger Metadatenwert.');
    if (['slide', 'slide-order'].includes(d.kind)) {
      if (d.kind === 'slide' && typeof value.present !== 'boolean')
        throw Error('Ungültiger Folienwert.');
      if (d.kind === 'slide-order' || value.present) {
        if (
          ![value.beforeId, value.afterId].every(
            (id) => id === null || (typeof id === 'string' && id !== d.id),
          )
        )
          throw Error('Ungültiger Folienanker.');
      }
      if (d.kind === 'slide' && value.present) {
        if (
          typeof value.html !== 'string' ||
          !plainObject(value.metadata) ||
          Object.keys(value.metadata).sort().join(',') !==
            'guidance,notes,notesFormat,notesProvenance'
        )
          throw Error('Ungültige gespeicherte Folie.');
        for (const entry of Object.values(value.metadata))
          checkRecordValue({ kind: 'meta' }, entry);
      }
    }
    if (
      ['subtree', 'placement'].includes(d.kind) &&
      (d.kind === 'subtree' || value.present) &&
      typeof value.html !== 'string'
    )
      throw Error('Ungültiger Quelltextbereich.');
    if (
      d.kind === 'placement' &&
      (typeof value.present !== 'boolean' ||
        (value.present &&
          (typeof value.parentId !== 'string' ||
            (value.beforeId !== null && typeof value.beforeId !== 'string'))))
    )
      throw Error('Ungültiger Platzierungswert.');
    if (
      d.kind === 'placement' &&
      ((value.parentPath !== undefined &&
        (!Array.isArray(value.parentPath) ||
          value.parentPath.length > 128 ||
          value.parentPath.some((index) => !Number.isSafeInteger(index) || index < 0))) ||
        (value.beforeOffset !== undefined &&
          (!Number.isSafeInteger(value.beforeOffset) || value.beforeOffset < 0)))
    )
      throw Error('Ungültiger lokaler Platzierungsanker.');
    if (d.kind === 'style' || d.kind === 'attrs') {
      const names = d.kind === 'style' ? d.properties : d.names;
      if (
        Object.keys(value).length !== names.length ||
        names.some((n) => !Object.prototype.hasOwnProperty.call(value, n))
      )
        throw Error('Eigenschaftsliste stimmt nicht überein.');
      for (const entry of Object.values(value)) {
        if (d.kind === 'attrs' && entry !== null && typeof entry !== 'string')
          throw Error('Ungültiger Attributwert.');
        if (
          d.kind === 'style' &&
          (!plainObject(entry) ||
            typeof entry.value !== 'string' ||
            !['', 'important'].includes(entry.priority))
        )
          throw Error('Ungültiger Stilwert.');
      }
    }
    if (
      d.kind === 'image' &&
      (typeof value.asset !== 'string' ||
        !plainObject(value.attributes) ||
        typeof value.crop !== 'string' ||
        !plainObject(value.style))
    )
      throw Error('Ungültiger Originalbildbereich.');
  }
  try {
    const raw = localStorage.getItem(storageKey);
    if (raw && base.fingerprint) {
      const head = JSON.parse(raw);
      if (head.draftVersion !== 2 || json(head.base) !== json(base)) {
        localStorage.removeItem(storageKey);
        draftMessage = 'Älterer Browserentwurf verworfen; diese Datei ist der aktuelle Stand.';
      } else {
        if (typeof head.head !== 'string' || !head.head) throw Error('Der Entwurfskopf fehlt.');
        const chain = [],
          seen = new Set();
        let id = head.head,
          total = 0,
          previousSeq = Infinity;
        while (id) {
          if (seen.has(id) || chain.length >= 512) throw Error('Ungültige Entwurfskette.');
          seen.add(id);
          const entryRaw = localStorage.getItem(`${namespace}entry:${id}`);
          if (!entryRaw) throw Error('Ein Entwurfseintrag fehlt.');
          total += entryRaw.length * 2;
          if (total > 128 * 1024 * 1024)
            throw Error('Der Entwurf überschreitet das Wiederherstellungslimit.');
          const entry = JSON.parse(entryRaw);
          if (
            !plainObject(entry) ||
            entry.id !== id ||
            !Number.isInteger(entry.seq) ||
            entry.seq < 0 ||
            entry.seq > previousSeq ||
            !Array.isArray(entry.changes) ||
            !entry.changes.length ||
            !Array.isArray(entry.assetRefs) ||
            (entry.prev !== null && typeof entry.prev !== 'string')
          )
            throw Error('Ungültiger Entwurfseintrag.');
          if (entry.seq === previousSeq && !entry.checkpoint)
            throw Error('Ungültige Entwurfsreihenfolge.');
          previousSeq = entry.seq;
          if (
            entry.slideOrder !== undefined &&
            (!entry.checkpoint ||
              !Array.isArray(entry.slideOrder) ||
              !entry.slideOrder.length ||
              entry.slideOrder.some((id) => typeof id !== 'string' || !id) ||
              new Set(entry.slideOrder).size !== entry.slideOrder.length)
          )
            throw Error('Ungültige Folienreihenfolge im Kontrollpunkt.');
          for (const change of entry.changes) {
            checkDescriptor(change.descriptor);
            checkRecordValue(change.descriptor, change.after);
          }
          const refs = [...refsIn(entry.changes)].sort();
          if (
            json(refs) !== json([...new Set(entry.assetRefs)].sort()) ||
            refs.length !== entry.assetRefs.length
          )
            throw Error('Ungültige Originalbild-Verweise.');
          for (const reference of refs)
            if (!assets.has(reference)) {
              if (!/^new:[a-zA-Z0-9-]+$/.test(reference))
                throw Error('Ein Originalbild-Verweis fehlt.');
              const assetRaw = localStorage.getItem(`${namespace}asset:${reference}`);
              if (!assetRaw) throw Error('Ein neues Originalbild fehlt.');
              const original = JSON.parse(assetRaw);
              if (
                original.id !== reference ||
                !assetSource(original.src) ||
                assetBySource.has(original.src) ||
                !Number.isFinite(original.width) ||
                !Number.isFinite(original.height) ||
                original.width <= 0 ||
                original.height <= 0
              )
                throw Error('Ungültiges neues Originalbild.');
              const stored = freeze({ ...original, bytes: original.src.length * 2 });
              assets.set(reference, stored);
              assetBySource.set(original.src, stored);
            }
          chain.push(entry);
          id = entry.prev;
          if (entry.checkpoint && id !== null) throw Error('Ungültiger Entwurfskontrollpunkt.');
        }
        // Recovery alone materializes a detached complete candidate, then admits atomically.
        const candidate = deck.cloneNode(true),
          candidateMeta = copyValue(meta),
          candidateIndex = new Map(),
          replayed = [];
        const indexCandidate = () => {
          candidateIndex.clear();
          for (const node of candidate.querySelectorAll('[data-sf-slide],[data-sf-id]'))
            candidateIndex.set(node.dataset.sfId || node.dataset.sfSlide, node);
        };
        indexCandidate();
        for (const entry of [...chain].reverse()) {
          for (const change of entry.changes) {
            const lookup = (target) => candidateIndex.get(target),
              d = change.descriptor,
              existing = lookup(d.id);
            if (d.kind === 'subtree' && (existing?.dataset.sfSlide || !existing))
              throw Error('Der lokale Wiederherstellungsbereich fehlt.');
            const previousIds =
              ['subtree', 'placement', 'slide'].includes(d.kind) && existing
                ? [existing, ...existing.querySelectorAll('[data-sf-id]')]
                    .map((node) => node.dataset.sfId)
                    .filter(Boolean)
                : [];
            applyScope(d, change.after, lookup, candidateMeta, candidate, !!entry.slideOrder);
            if (['subtree', 'placement', 'slide', 'slide-order'].includes(d.kind)) indexCandidate();
            replayed.push({ change, seq: entry.seq, previousIds });
          }
          if (entry.slideOrder) {
            const slides = [...candidate.children];
            if (
              slides.length !== entry.slideOrder.length ||
              entry.slideOrder.some(
                (id) =>
                  !candidateIndex.get(id)?.hasAttribute('data-sf-slide') ||
                  candidateIndex.get(id).parentElement !== candidate,
              )
            )
              throw Error('Die Folienreihenfolge passt nicht zum Kontrollpunkt.');
            for (const id of entry.slideOrder) candidate.append(candidateIndex.get(id));
          }
        }
        validate(candidateMeta, candidate);
        deck.replaceChildren(...candidate.childNodes);
        meta = candidateMeta;
        rebuildIndexes();
        resetJson();
        admittedHead = head.head;
        sequence = chain[0].seq;
        recordCount = chain.length;
        recordBytes = total;
        for (const entry of [...chain].reverse()) {
          durableEntries.add(entry.id);
          for (const ref of entry.assetRefs) {
            durableRefs.add(ref);
            if (ref.startsWith('new:')) storedAssets.add(ref);
          }
        }
        for (const { change, seq, previousIds } of replayed)
          projectChange(change, seq, null, previousIds);
        recoveredDraft = true;
        draftMessage = 'Passender Browserentwurf wiederhergestellt.';
      }
    }
  } catch (error) {
    draftMessage = `Browserentwurf verworfen: ${error.message} Die Datei bleibt unverändert.`;
  }
  applyTheme();
  function moveSlide(id, delta) {
    settle('command');
    const slide = slideNodes.get(id),
      position = slidePositions.get(id),
      target = slideOrder[position + delta];
    if (!slide || !target) return false;
    return run('Folie verschieben', [{ kind: 'slide-order', id }], () =>
      deck.insertBefore(slide, delta < 0 ? target : target.nextElementSibling),
    );
  }
  function adjacent(position, step, includeHidden = false) {
    for (let i = position + step; i >= 0 && i < slideOrder.length; i += step)
      if (includeHidden || !isHidden(slideOrder[i])) return i;
    return -1;
  }
  const visibleSlides = () => slideOrder.filter((slide) => !isHidden(slide));
  function toggleSlide(id) {
    settle('command');
    const slide = slideNodes.get(id);
    if (!slide || (!isHidden(slide) && visibleSlides().length === 1)) return false;
    return run(
      isHidden(slide) ? 'Folie einblenden' : 'Folie ausblenden',
      [{ kind: 'attrs', id, names: ['data-sf-hidden'] }],
      () => slide.toggleAttribute('data-sf-hidden'),
    );
  }
  function deleteSlide(id) {
    settle('command');
    const slide = slideNodes.get(id);
    if (!slide || slideOrder.length === 1 || (!isHidden(slide) && visibleSlides().length === 1))
      return false;
    return run('Folie löschen', [{ kind: 'slide', id }], () => {
      slide.remove();
      for (const key of ['notes', 'notesFormat', 'notesProvenance', 'guidance'])
        if (meta[key]) delete meta[key][id];
    });
  }
  // A share copy drops everything addressed to the owner or the agent: speaker notes, guidance and post-its.
  function exportHtml({ share = false } = {}) {
    settle('save');
    flushDraft();
    validate();
    const clone = clean(document.documentElement.cloneNode(true)),
      savedMeta = copyValue(meta);
    savedMeta.revision = freshId();
    if (share) {
      for (const id of Object.keys(savedMeta.notes)) savedMeta.notes[id] = '';
      for (const id of Object.keys(savedMeta.guidance))
        savedMeta.guidance[id] = { text: '', status: 'open' };
      delete savedMeta.notesFormat;
      delete savedMeta.notesProvenance;
      clone.querySelectorAll('#sf-deck [data-sf-postit]').forEach((node) => node.remove());
    }
    clone.querySelector('#sf-document').textContent = json(savedMeta);
    clone.querySelector('title').textContent = meta.title || 'Präsentation';
    validate(savedMeta, clone.querySelector('#sf-deck'));
    return '<!DOCTYPE html>\n' + clone.outerHTML;
  }
  window.addEventListener('pagehide', () => {
    settle('pagehide');
    flushDraft();
  });
  return {
    valid,
    deck,
    schemes,
    json,
    freshId,
    clean,
    layout,
    validate,
    capture,
    begin,
    update,
    commit,
    cancel,
    run,
    registerSettler,
    settle,
    undo,
    redo,
    flushDraft,
    exportHtml,
    asset,
    ticket,
    accepts,
    moveSlide,
    deleteSlide,
    toggleSlide,
    isHidden,
    visibleSlides,
    adjacent,
    slide: (id) => slideNodes.get(id) || null,
    object: (id) => objects.get(id) || null,
    slideIndex: (id) => slidePositions.get(id) ?? -1,
    slides: () => slideOrder,
    inventory: () => inventoryView,
    slideVersion: (id) => versions.get(id) || 0,
    get meta() {
      return meta;
    },
    get canUndo() {
      return !!past.length;
    },
    get canRedo() {
      return !!future.length;
    },
    get recoveredDraft() {
      return recoveredDraft;
    },
    get draftMessage() {
      return storageMessage || draftMessage;
    },
    get storageWarning() {
      return storageMessage;
    },
    onChange(listener) {
      observers.add(listener);
      return () => observers.delete(listener);
    },
  };
}
