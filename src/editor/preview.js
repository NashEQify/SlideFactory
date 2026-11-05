/* Isolated, non-executing projections preserve the presentation's ID namespace. */
function createPreviews(doc) {
  const cache = new Map(),
    mounted = new Map(),
    contextListeners = new Set(),
    budget = 12 * 1024 * 1024;
  const encoder = new TextEncoder(),
    preparing = new WeakMap(),
    exposures = new WeakMap(),
    nativeRestores = new Map();
  let nativePrinting = false;
  // Content-only counterpart of editor.css; projections exclude all editor chrome.
  const contentStyle =
    '<style>.sf-slide [data-sf-highlight],.sf-slide [data-sf-highlight] *{color:#172a2c!important}:where(.sf-slide [data-sf-postit][style*="padding: 28px 18px 18px;"]:has(> [data-sf-kind="text"][style*="width: 100%;"][style*="height: 100%;"])){padding:4px!important}:where(.sf-slide a[data-sf-link]){display:flex;align-items:center;justify-content:center;padding:0 18px;border:2px solid var(--sf-accent);border-radius:999px;background:var(--sf-surface);color:var(--sf-accent);font:700 20px/1.2 Arial,Helvetica,sans-serif;text-decoration:none;white-space:nowrap;overflow:hidden;cursor:pointer}</style>';
  let cacheBytes = 0,
    generation = 0,
    disposed = false,
    builds = 0,
    hits = 0,
    contextPending = false;
  const resourceNodes = [...document.head.querySelectorAll('style')].filter(
    (node) =>
      node.id !== 'sf-editor-styles' &&
      node.id !== 'sf-theme-tokens' &&
      !node.hasAttribute('data-sf-transient'),
  );
  let resources = resourceNodes.map((node) => node.outerHTML).join('');
  let definitions = [...document.querySelectorAll('body > svg,body > [data-sf-definitions]')]
    .map((node) => node.outerHTML)
    .join('');
  let resourceBytes = encoder.encode(resources + definitions).byteLength;
  const attributes = (node) =>
    [...node.attributes]
      .filter(
        (attribute) =>
          !attribute.name.startsWith('data-sf-runtime-') && !attribute.name.startsWith('on'),
      )
      .map(
        (attribute) =>
          ` ${attribute.name}="${attribute.value.replace(/&/g, '&amp;').replace(/"/g, '&quot;')}"`,
      )
      .join('');
  let bodyAttributes = attributes(document.body),
    rootAttributes = attributes(document.documentElement),
    deckAttributes = attributes(doc.deck);
  function refreshContext() {
    const body = attributes(document.body),
      root = attributes(document.documentElement),
      deck = attributes(doc.deck);
    if (body === bodyAttributes && root === rootAttributes && deck === deckAttributes) return false;
    bodyAttributes = body;
    rootAttributes = root;
    deckAttributes = deck;
    clear();
    generation++;
    contextPending = true;
    return true;
  }
  function clear(id = null) {
    if (id === null) {
      cache.clear();
      cacheBytes = 0;
    } else if (cache.has(id)) {
      cacheBytes -= cache.get(id).bytes;
      cache.delete(id);
    }
  }
  function safeCopy(slide) {
    const copy = slide.cloneNode(true);
    copy
      .querySelectorAll('script,iframe,object,embed,[data-sf-postit-delete]')
      .forEach((node) => node.remove());
    for (const node of [copy, ...copy.querySelectorAll('*')]) {
      for (const attribute of [...node.attributes]) {
        if (attribute.name.startsWith('data-sf-runtime-original-')) {
          const name = attribute.name.slice('data-sf-runtime-original-'.length);
          if (attribute.value === '__absent__') node.removeAttribute(name);
          else node.setAttribute(name, attribute.value);
        }
      }
      for (const attribute of [...node.attributes]) {
        if (
          attribute.name.startsWith('on') ||
          attribute.name.startsWith('data-sf-runtime-') ||
          ['contenteditable', 'tabindex'].includes(attribute.name)
        )
          node.removeAttribute(attribute.name);
      }
    }
    return copy;
  }
  function source(slide, prepared = false) {
    if (disposed || !slide) return '';
    refreshContext();
    const id = slide.dataset.sfSlide,
      revision = doc.slideVersion(id);
    const cached = cache.get(id);
    if (cached && cached.revision === revision && cached.generation === generation) {
      cache.delete(id);
      cache.set(id, cached);
      hits++;
      return cached.source;
    }
    clear(id);
    {
      const hidden = !prepared && slide.dataset.sfRuntimeVisible === 'false';
      const style = slide.getAttribute('style'),
        originalStyle = slide.getAttribute('data-sf-runtime-original-style'),
        previousPreview = slide.getAttribute('data-sf-runtime-preview');
      let copy;
      try {
        if (hidden) {
          if (originalStyle === null)
            slide.setAttribute(
              'data-sf-runtime-original-style',
              style === null ? '__absent__' : style,
            );
          slide.dataset.sfRuntimePreview = 'true';
          for (const [name, value] of Object.entries({
            display: 'block',
            position: 'absolute',
            left: '-100000px',
            top: '0px',
            visibility: 'hidden',
            pointerEvents: 'none',
          }))
            slide.style.setProperty(
              name.replace(/[A-Z]/g, (char) => `-${char.toLowerCase()}`),
              value,
              'important',
            );
          slide.dispatchEvent(
            new CustomEvent('sf:layout', {
              bubbles: true,
              detail: {
                slideId: id,
                elementId: slide.querySelector('[data-sf-id]')?.dataset.sfId || id,
                phase: 'preview',
              },
            }),
          );
        }
        copy = safeCopy(slide);
      } finally {
        if (hidden) {
          if (style === null) slide.removeAttribute('style');
          else slide.setAttribute('style', style);
          if (originalStyle === null) slide.removeAttribute('data-sf-runtime-original-style');
          else slide.setAttribute('data-sf-runtime-original-style', originalStyle);
          if (previousPreview === null) slide.removeAttribute('data-sf-runtime-preview');
          else slide.setAttribute('data-sf-runtime-preview', previousPreview);
        }
      }
      const theme =
        (document.getElementById('sf-theme-tokens')?.outerHTML || '') +
        contentStyle +
        (doc.meta.postitsVisible === false
          ? '<style>[data-sf-postit]{display:none!important}</style>'
          : '');
      const html = `<!DOCTYPE html><html${rootAttributes}><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; font-src data:; style-src 'unsafe-inline';"><meta name="viewport" content="width=1600">${resources}${theme}<style>*{-webkit-print-color-adjust:exact;print-color-adjust:exact}html,body{margin:0!important;padding:0!important;width:1600px;height:900px;overflow:hidden!important}#sf-deck{position:relative!important;left:0!important;top:0!important;width:1600px!important;height:900px!important;transform:none!important}#sf-deck>.sf-slide{display:block!important;position:relative!important;left:0!important;top:0!important;width:1600px;height:900px}</style></head><body${bodyAttributes}>${definitions}<main${deckAttributes}>${copy.outerHTML}</main></body></html>`;
      const bytes = encoder.encode(html).byteLength;
      builds++;
      if (bytes <= budget) {
        while (cacheBytes + bytes > budget) clear(cache.keys().next().value);
        cache.set(id, { source: html, bytes, revision, generation });
        cacheBytes += bytes;
      }
      return html;
    }
  }
  const presentationState = (slide) =>
    ['style', 'data-sf-runtime-original-style', 'data-sf-runtime-preview'].map((name) => [
      name,
      slide.getAttribute(name),
    ]);
  const restorePresentation = (slide, saved) => {
    for (const [name, value] of saved) {
      if (value === null) slide.removeAttribute(name);
      else slide.setAttribute(name, value);
    }
  };
  const positionPreview = (slide) => {
    for (const [name, value] of Object.entries({
      display: 'block',
      position: 'absolute',
      left: '-100000px',
      top: '0px',
      visibility: 'hidden',
      'pointer-events': 'none',
    }))
      slide.style.setProperty(name, value, 'important');
  };
  function expose(slide) {
    const saved = presentationState(slide),
      previous = exposures.get(slide),
      token = { saved };
    exposures.set(slide, token);
    if (nativePrinting && !previous) nativeRestores.set(slide, { token, saved: null });
    if (slide.dataset.sfRuntimeVisible === 'false') {
      if (!slide.hasAttribute('data-sf-runtime-original-style'))
        slide.setAttribute(
          'data-sf-runtime-original-style',
          slide.getAttribute('style') ?? '__absent__',
        );
      slide.dataset.sfRuntimePreview = 'true';
      if (nativePrinting) slide.style.setProperty('display', 'block', 'important');
      else positionPreview(slide);
    }
    return () => {
      restorePresentation(slide, saved);
      if (previous) exposures.set(slide, previous);
      else exposures.delete(slide);
    };
  }
  function beginNativePrint() {
    if (nativePrinting) return;
    nativePrinting = true;
    // Temporarily reveal in-flight preparations without stealing their finally owner.
    for (const slide of doc.slides()) {
      const token = exposures.get(slide);
      if (!token) continue;
      nativeRestores.set(slide, { token, saved: presentationState(slide) });
      restorePresentation(slide, token.saved);
    }
  }
  function finishNativePrint() {
    nativePrinting = false;
    for (const [slide, { token, saved }] of nativeRestores)
      if (exposures.get(slide) === token) {
        if (saved) restorePresentation(slide, saved);
        else if (slide.dataset.sfRuntimeVisible === 'false') positionPreview(slide);
      }
    nativeRestores.clear();
  }
  function prepareNative(slide) {
    const restore = expose(slide);
    try {
      slide.dispatchEvent(
        new CustomEvent('sf:layout', {
          bubbles: true,
          detail: {
            slideId: slide.dataset.sfSlide,
            elementId: slide.querySelector('[data-sf-id]')?.dataset.sfId || slide.dataset.sfSlide,
            phase: 'preview',
          },
        }),
      );
      slide.getBoundingClientRect();
    } finally {
      restore();
    }
  }
  function prepare(slide, isCurrent = () => true) {
    // A slide has exactly one temporary-style owner, including superseded requests.
    const task = (preparing.get(slide) || Promise.resolve()).then(() => {
      if (!isCurrent()) return null;
      return prepareSlide(slide);
    });
    const settled = task.catch(() => {});
    preparing.set(slide, settled);
    settled.then(() => {
      if (preparing.get(slide) === settled) preparing.delete(slide);
    });
    return task;
  }
  async function prepareSlide(slide) {
    if (disposed || !slide?.isConnected) throw Error('Die Druckfolie ist nicht mehr verfügbar.');
    const restore = expose(slide);
    let timeout,
      stage = 'Layout';
    try {
      const promises = [];
      let registering = true;
      const detail = {
        slideId: slide.dataset.sfSlide,
        elementId: slide.querySelector('[data-sf-id]')?.dataset.sfId || slide.dataset.sfSlide,
        phase: 'preview',
        waitUntil(promise) {
          if (!registering) throw Error('waitUntil muss während sf:layout registriert werden.');
          promises.push(Promise.resolve(promise));
        },
      };
      slide.dispatchEvent(new CustomEvent('sf:layout', { bubbles: true, detail }));
      registering = false;
      // Readiness is resource/layout completion, not a paint in a foreground tab.
      const ready = async () => {
        await Promise.all(promises);
        stage = 'Schriften';
        await document.fonts?.ready;
        if ([...document.fonts].some((font) => font.status === 'error'))
          throw Error('Eine Schrift konnte nicht geladen werden.');
        stage = 'Bilder';
        await Promise.all([...slide.querySelectorAll('img')].map((img) => img.decode()));
        slide.getBoundingClientRect();
      };
      await Promise.race([
        ready(),
        new Promise((_, reject) => {
          timeout = setTimeout(
            () => reject(Error('Druckvorbereitung nach 10 Sekunden abgebrochen.')),
            10000,
          );
        }),
      ]);
      if (disposed || !slide.isConnected) throw Error('Die Druckfolie wurde entfernt.');
      resources = [...document.querySelectorAll('style')]
        .filter(
          (node) =>
            node.id !== 'sf-editor-styles' &&
            node.id !== 'sf-theme-tokens' &&
            !node.closest('[data-sf-transient],#sf-deck'),
        )
        .map((node) => node.outerHTML)
        .join('');
      definitions = [...document.querySelectorAll('body > svg,body > [data-sf-definitions]')]
        .map((node) => safeCopy(node).outerHTML)
        .join('');
      resourceBytes = encoder.encode(resources + definitions).byteLength;
      generation++;
      refreshContext();
      clear(slide.dataset.sfSlide);
      return source(slide, true);
    } catch (error) {
      throw Error(
        `${stage} der Folie ${doc.slideIndex(slide.dataset.sfSlide) + 1}: ${error.message}`,
      );
    } finally {
      clearTimeout(timeout);
      restore();
    }
  }
  function frame(slide, title) {
    if (disposed) throw Error('Die Vorschauen wurden beendet.');
    const iframe = document.createElement('iframe');
    iframe.title = title;
    iframe.className = 'sf-preview-frame';
    iframe.setAttribute('sandbox', 'allow-same-origin');
    iframe.setAttribute('aria-hidden', 'true');
    iframe.tabIndex = -1;
    iframe.dataset.sfPreview = slide.dataset.sfSlide;
    iframe.srcdoc = source(slide);
    mounted.set(iframe, slide.dataset.sfSlide);
    return iframe;
  }
  function release(iframe) {
    if (!iframe) return;
    mounted.delete(iframe);
    iframe.removeAttribute('srcdoc');
    iframe.removeAttribute('src');
    iframe.remove();
  }
  function invalidate(id = null) {
    if (disposed) return;
    clear(id);
    if (id === null) generation++;
    for (const [iframe, slideId] of mounted) {
      if (!iframe.isConnected) {
        release(iframe);
        continue;
      }
      if (!id || id === slideId) {
        const slide = doc.slide(slideId);
        if (slide) iframe.srcdoc = source(slide);
        else release(iframe);
      }
    }
  }
  const contextObserver = new MutationObserver(() => {
    refreshContext();
    // Reading the source updates its cache, but does not acknowledge delivery.
    if (contextPending) {
      contextPending = false;
      invalidate();
      for (const listener of contextListeners) listener();
    }
  });
  for (const node of [document.documentElement, document.body, doc.deck])
    contextObserver.observe(node, { attributes: true, attributeFilter: ['style', 'class'] });
  function dispose() {
    if (disposed) return;
    disposed = true;
    contextPending = false;
    contextObserver.disconnect();
    window.removeEventListener('pagehide', dispose);
    for (const iframe of mounted.keys()) release(iframe);
    clear();
    contextListeners.clear();
    resources = '';
    definitions = '';
    resourceBytes = 0;
  }
  window.addEventListener('pagehide', dispose, { once: true });
  return {
    source,
    prepare,
    prepareNative,
    beginNativePrint,
    finishNativePrint,
    frame,
    invalidate,
    release,
    dispose,
    onContextChange(listener) {
      contextListeners.add(listener);
      return () => contextListeners.delete(listener);
    },
    get stats() {
      return Object.freeze({
        sourceBytes: cacheBytes,
        sourceBudget: budget,
        sources: cache.size,
        frames: mounted.size,
        resourceBytes,
        builds,
        hits,
        disposed,
      });
    },
  };
}
