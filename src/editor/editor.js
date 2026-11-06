function startEditor(doc) {
  const chrome = createEditorChrome();
  document.body.append(chrome);
  document.body.dataset.sfRuntimeRunning = 'true';
  const get = (selector) => chrome.querySelector(selector),
    button = (action) => get(`[data-action="${action}"]`);
  const status = get('[role="status"]'),
    alert = get('[role="alert"]');
  const saveState = get('#sf-save-state');
  function fileNotice(state) {
    if (saveState.dataset.state === state) return;
    saveState.dataset.state = state;
    saveState.textContent =
      state === 'dirty'
        ? 'Ungespeicherte Änderungen · HTML speichern'
        : state === 'download'
          ? 'HTML-Download gestartet · Neue Datei verwenden'
          : 'Dateistand geöffnet';
    saveState.title =
      state === 'download'
        ? 'Der Download wurde gestartet; die ursprüngliche Datei wird nicht überschrieben. Für die Weiterarbeit die heruntergeladene HTML verwenden.'
        : state === 'dirty'
          ? 'Änderungen einschließlich eines Browserentwurfs gehören noch nicht zur geöffneten HTML-Datei. HTML speichern lädt den aktuellen Stand herunter.'
          : 'Der Inhalt entspricht dem geöffneten Dateistand.';
  }
  fileNotice(doc.recoveredDraft ? 'dirty' : 'file');
  const message = (text) => {
    status.textContent = text;
    if (!doc.storageWarning) alert.hidden = true;
  };
  const error = (text) => {
    alert.textContent = text;
    alert.hidden = false;
  };
  const panel = get('.sf-panel'),
    notesPanel = get('.sf-notes-panel'),
    thumbnails = get('.sf-thumbnails'),
    palette = get('#sf-palette');
  const player = document.createElement('div');
  player.id = 'sf-player-controls';
  player.dataset.sfTransient = '';
  player.innerHTML = editorTool('fullscreen', 'Vollbild', 'fullscreen');
  document.body.append(player);
  const returnChip = document.createElement('div');
  returnChip.id = 'sf-return-jump';
  returnChip.dataset.sfTransient = '';
  returnChip.hidden = true;
  returnChip.innerHTML =
    '<button type="button" data-action="return-jump" title="Zurück zur Ausgangsfolie (Rücktaste)" aria-keyshortcuts="Backspace"></button>';
  document.body.append(returnChip);
  const jumps = [];
  // Deep-dive overlay: an isolated projection above the current slide; nothing about it is saved.
  const deepDive = document.createElement('div');
  deepDive.id = 'sf-deep-dive';
  deepDive.dataset.sfTransient = '';
  deepDive.hidden = true;
  deepDive.setAttribute('role', 'dialog');
  deepDive.setAttribute('aria-modal', 'true');
  deepDive.innerHTML =
    '<div class="sf-deep-dive-header"><span class="sf-deep-dive-name"></span><button type="button" aria-label="Deep Dive schließen" title="Deep Dive schließen (Esc)">×</button></div><div class="sf-deep-dive-stage"></div>';
  document.body.append(deepDive);
  let openDive = null;
  const viewStyle = document.createElement('style');
  viewStyle.dataset.sfTransient = '';
  document.head.append(viewStyle);
  let index = 0,
    panelMode = null,
    pendingPanel = null,
    panelTimer = null,
    replaceTarget = null,
    wasCompact = false,
    visibleSlide = null,
    panelComposing = false,
    committingPanel = false;
  const notesCodec = createNotesCodec(document);
  const noteEditor = createNotesEditor(
    get('#sf-notes'),
    get('#sf-note-tools'),
    { begin: () => beginPanel(get('#sf-notes')), input: writeNote, settle: flushPanel, history },
    notesCodec,
  );
  let sidebarWidth = 180,
    sidebarDrag = null;
  const separator = get('#sf-sidebar-resize');
  let notesHeight = 200,
    notesDrag = null;
  const notesSeparator = get('#sf-notes-resize');
  const previews = createPreviews(doc);
  const hooks = {
    message,
    error,
    currentSlide: () => doc.slides()[index],
    navigate,
    goToEdge: (last) => {
      const i = doc.adjacent(last ? doc.slides().length : -1, last ? -1 : 1, interaction.editing);
      if (i >= 0) goTo(i);
    },
    selectionChanged,
    cropChanged,
    beforeEdit,
    history,
    deleteSelection: deleteSelectedObject,
  };
  const printer = createPrinter(doc, previews, { error, message });
  const interaction = createInteraction(doc, hooks);
  hooks.interaction = interaction;
  const images = createImages(doc, hooks);
  hooks.images = images;
  hooks.painterChanged = (value) => button('painter').setAttribute('aria-pressed', String(value));
  hooks.postitsChanged = (value) => {
    for (const control of document.querySelectorAll('#sf-editor [data-action="postits"]'))
      control.setAttribute('aria-pressed', String(value));
  };
  const objects = createObjects(doc, hooks);
  hooks.objects = objects;
  const textTools = createTextTools(doc, hooks);
  hooks.textTools = textTools;
  hooks.textStateChanged = syncTextControls;
  const presenter = createPresenter(doc, previews, {
    index: () => index,
    goTo,
    flush: beforeEdit,
    message,
    error,
    returnJump: () => returnJump(),
    deepDive: () => openDive?.id || null,
    closeDeepDive: () => closeDeepDive(),
  });
  previews.onContextChange(() => presenter.sync({ type: 'change', theme: true }));
  let thumbnailOrder = null,
    thumbnailObserver = null;
  let followedEntry = null,
    followedLayout = '';
  const sidebarHeading = get('.sf-sidebar-heading');
  const thumbnailItems = new Map(),
    thumbnailFrames = new Map(),
    visibleThumbnails = new Set();
  let thumbnailDrag = null,
    thumbnailDrop = null,
    thumbnailScroll = null;
  for (const [id, scheme] of Object.entries(doc.schemes)) {
    const option = document.createElement('option');
    option.value = id;
    option.textContent = scheme.label;
    palette.append(option);
  }
  palette.value = doc.meta.colorScheme;
  function fit() {
    const audience = !!document.fullscreenElement && !interaction.editing;
    document.body.dataset.sfRuntimeFullscreen = String(audience);
    if (audience) {
      followedEntry = null;
      updateThumbnailFallback();
      const scale = Math.min(innerWidth / 1600, innerHeight / 900);
      viewStyle.textContent = `body[data-sf-runtime-running] #sf-deck{position:fixed;left:50%;top:50%;transform:translate(-50%,-50%) scale(${scale});transform-origin:center;width:1600px;height:900px;box-shadow:none}`;
      interaction.update();
      positionPlayer();
      positionDeepDive();
      return;
    }
    const compact = innerWidth < 760;
    if (compact && !wasCompact) {
      thumbnails.hidden = true;
      releaseThumbnails();
      button('thumbnails').setAttribute('aria-pressed', 'false');
    }
    wasCompact = compact;
    const toolbar = get('.sf-toolbar').getBoundingClientRect().bottom;
    const footer = Math.max(32, get('.sf-feedback').getBoundingClientRect().height + 4);
    const context = get('.sf-context');
    context.style.top = `${toolbar}px`;
    // In short editing windows, scroll the ribbon before shrinking the notes input.
    context.style.maxHeight = notesPanel.hidden
      ? ''
      : `${Math.max(40, Math.min(innerHeight * 0.45, innerHeight - toolbar - footer - 112 - 132))}px`;
    context.style.minHeight = notesPanel.hidden ? '' : '40px';
    const top = interaction.editing ? context.getBoundingClientRect().bottom : toolbar;
    panel.style.top = compact ? 'auto' : `${top}px`;
    thumbnails.style.top = `${top}px`;
    const right = panel.hidden || compact ? 0 : panel.getBoundingClientRect().width;
    const maximum = Math.max(120, Math.min(480, innerWidth - right - 200));
    sidebarWidth = Math.max(120, Math.min(maximum, sidebarWidth));
    thumbnails.style.width = `${sidebarWidth}px`;
    separator.hidden = thumbnails.hidden;
    separator.style.left = `${sidebarWidth - 4}px`;
    separator.style.top = `${top}px`;
    separator.setAttribute('aria-valuemin', '120');
    separator.setAttribute('aria-valuemax', String(maximum));
    separator.setAttribute('aria-valuenow', String(Math.round(sidebarWidth)));
    scaleThumbnails();
    const left = thumbnails.hidden ? 0 : thumbnails.getBoundingClientRect().width;
    const workspaceHeight = Math.max(0, innerHeight - top - footer);
    const slideReserve = Math.min(132, Math.max(72, workspaceHeight - 112));
    const notesMaximum = Math.max(0, workspaceHeight - slideReserve),
      notesMinimum = Math.min(112, notesMaximum);
    notesHeight = Math.max(notesMinimum, Math.min(notesMaximum, notesHeight));
    notesPanel.style.left = `${left}px`;
    notesPanel.style.bottom = `${footer}px`;
    notesPanel.style.height = `${notesHeight}px`;
    notesSeparator.setAttribute('aria-valuemin', String(Math.round(notesMinimum)));
    notesSeparator.setAttribute('aria-valuemax', String(Math.round(notesMaximum)));
    notesSeparator.setAttribute('aria-valuenow', String(Math.round(notesHeight)));
    notesSeparator.setAttribute('aria-valuetext', `${Math.round(notesHeight)} Pixel`);
    const bottom = !notesPanel.hidden
      ? notesHeight
      : panel.hidden || !compact
        ? 0
        : panel.getBoundingClientRect().height;
    const availableWidth = Math.max(120, innerWidth - left - right - 32),
      availableHeight = Math.max(0, innerHeight - top - bottom - footer - 22);
    const scale = Math.min(availableWidth / 1600, availableHeight / 900);
    viewStyle.textContent = `body[data-sf-runtime-running] #sf-deck{position:fixed;left:${left + (innerWidth - left - right) / 2}px;top:${top + availableHeight / 2 + 16}px;transform:translate(-50%,-50%) scale(${scale});transform-origin:center;width:1600px;height:900px;}`;
    interaction.update();
    positionPlayer();
    positionDeepDive();
    if (!get('#sf-menu').hidden) positionMenu();
    followCurrentThumbnail();
    updateThumbnailFallback();
  }
  function followCurrentThumbnail() {
    if (thumbnails.hidden) {
      followedEntry = null;
      return;
    }
    if (thumbnailDrag) return;
    const entry = thumbnailItems.get(visibleSlide?.dataset.sfSlide)?.parentElement;
    if (!entry) return;
    // The same entry survives ordinary edits. Let a reader scroll freely until
    // navigation, reordering, reopening or a real sidebar size change.
    const layout = `${thumbnails.clientWidth}/${thumbnails.clientHeight}/${interaction.editing}`;
    if (entry === followedEntry && layout === followedLayout) return;
    followedEntry = entry;
    followedLayout = layout;
    const row = entry.getBoundingClientRect(),
      top = sidebarHeading.getBoundingClientRect().bottom + 4;
    const bottom = thumbnails.getBoundingClientRect().bottom - 4;
    if (row.top < top || row.height > bottom - top) thumbnails.scrollTop += row.top - top;
    else if (row.bottom > bottom) thumbnails.scrollTop += row.bottom - bottom;
  }
  function positionPlayer() {
    const rect = doc.deck.getBoundingClientRect();
    if (!returnChip.hidden) {
      returnChip.style.left = `${Math.max(0, Math.min(innerWidth - returnChip.offsetWidth, rect.left + (rect.width - returnChip.offsetWidth) / 2))}px`;
      returnChip.style.top = `${Math.max(0, Math.min(innerHeight - returnChip.offsetHeight, rect.bottom - returnChip.offsetHeight - 8))}px`;
    }
    player.style.left = `${Math.max(0, Math.min(innerWidth - player.offsetWidth, rect.right - player.offsetWidth - 8))}px`;
    player.style.top = `${Math.max(0, Math.min(innerHeight - player.offsetHeight, rect.bottom - player.offsetHeight - 8))}px`;
  }
  function scaleThumbnails() {
    for (const item of thumbnailItems.values()) {
      const canvas = item.querySelector('.sf-thumbnail-canvas'),
        width = canvas.clientWidth;
      canvas.style.height = `${(width * 9) / 16}px`;
      canvas.style.setProperty('--sf-thumbnail-scale', String(width / 1600));
    }
  }
  separator.addEventListener('pointerdown', (event) => {
    if (event.button !== 0) return;
    event.preventDefault();
    sidebarDrag = { x: event.clientX, width: sidebarWidth, pointerId: event.pointerId };
    separator.focus();
    separator.setPointerCapture(event.pointerId);
  });
  separator.addEventListener('pointermove', (event) => {
    if (sidebarDrag) {
      sidebarWidth = sidebarDrag.width + event.clientX - sidebarDrag.x;
      fit();
    }
  });
  function endSidebar(cancel) {
    if (!sidebarDrag) return;
    const drag = sidebarDrag;
    sidebarDrag = null;
    if (cancel) sidebarWidth = drag.width;
    if (separator.hasPointerCapture(drag.pointerId))
      separator.releasePointerCapture(drag.pointerId);
    fit();
  }
  separator.addEventListener('pointerup', () => endSidebar(false));
  separator.addEventListener('pointercancel', () => endSidebar(true));
  separator.addEventListener('lostpointercapture', () => endSidebar(true));
  separator.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && sidebarDrag) {
      event.preventDefault();
      event.stopPropagation();
      endSidebar(true);
      return;
    }
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    event.stopPropagation();
    const step = event.shiftKey ? 20 : 4;
    sidebarWidth =
      event.key === 'Home'
        ? 120
        : event.key === 'End'
          ? Number(separator.getAttribute('aria-valuemax'))
          : sidebarWidth + (event.key === 'ArrowLeft' ? -step : step);
    fit();
  });
  notesSeparator.addEventListener('pointerdown', (event) => {
    if (event.button !== 0 || notesDrag) return;
    event.preventDefault();
    notesDrag = { y: event.clientY, height: notesHeight, pointerId: event.pointerId };
    notesSeparator.focus();
    notesSeparator.setPointerCapture(event.pointerId);
  });
  notesSeparator.addEventListener('pointermove', (event) => {
    if (notesDrag?.pointerId === event.pointerId) {
      notesHeight = notesDrag.height + notesDrag.y - event.clientY;
      fit();
    }
  });
  function endNotesResize(cancel) {
    if (!notesDrag) return;
    const drag = notesDrag;
    notesDrag = null;
    if (cancel) notesHeight = drag.height;
    if (notesSeparator.hasPointerCapture(drag.pointerId))
      notesSeparator.releasePointerCapture(drag.pointerId);
    fit();
  }
  notesSeparator.addEventListener('pointerup', (event) => {
    if (notesDrag?.pointerId === event.pointerId) endNotesResize(false);
  });
  notesSeparator.addEventListener('pointercancel', (event) => {
    if (notesDrag?.pointerId === event.pointerId) endNotesResize(true);
  });
  notesSeparator.addEventListener('lostpointercapture', () => endNotesResize(true));
  notesSeparator.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && notesDrag) {
      event.preventDefault();
      event.stopPropagation();
      endNotesResize(true);
      return;
    }
    if (!['ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    event.stopPropagation();
    const step = event.shiftKey ? 20 : 4;
    notesHeight =
      event.key === 'Home'
        ? Number(notesSeparator.getAttribute('aria-valuemin'))
        : event.key === 'End'
          ? Number(notesSeparator.getAttribute('aria-valuemax'))
          : notesHeight + (event.key === 'ArrowUp' ? step : -step);
    fit();
  });
  window.addEventListener('blur', () => endNotesResize(true));
  function historyButtons() {
    button('undo').disabled = !doc.canUndo;
  }
  function renderSlides() {
    const slides = doc.slides();
    index = Math.min(index, slides.length - 1);
    const current = slides[index];
    if (visibleSlide !== current) {
      if (visibleSlide) visibleSlide.dataset.sfRuntimeVisible = 'false';
      current.dataset.sfRuntimeVisible = 'true';
      visibleSlide = current;
    }
    get('#sf-counter').textContent = doc.isDeepDive(current)
      ? slideLabel(current)
      : `Folie ${doc.slideNumber(current)} / ${storyCount()}`;
    button('previous').disabled = doc.adjacent(index, -1, interaction.editing) < 0;
    button('next').disabled = doc.adjacent(index, 1, interaction.editing) < 0;
    historyButtons();
    palette.value = doc.meta.colorScheme;
    get('#sf-background').value =
      doc.meta.backgroundColor || doc.schemes[doc.meta.colorScheme].tokens.background;
    renderPanel();
    renderThumbnails();
    fit();
    get('#sf-slide-choice').value = current.dataset.sfSlide;
    renderReturn();
    view();
    presenter.sync();
  }
  function view() {
    document.dispatchEvent(
      new CustomEvent('sf:view', {
        detail: {
          deckId: doc.meta.deckId,
          slideId: doc.slides()[index].dataset.sfSlide,
          index,
          count: doc.slides().length,
        },
      }),
    );
  }
  function releaseThumbnail(id) {
    const frame = thumbnailFrames.get(id);
    if (frame) {
      previews.release(frame);
      thumbnailFrames.delete(id);
    }
  }
  function releaseThumbnails() {
    cancelThumbnailDrag();
    for (const id of thumbnailFrames.keys()) releaseThumbnail(id);
  }
  function mountThumbnail(id) {
    if (thumbnails.hidden || thumbnailFrames.has(id) || !visibleThumbnails.has(id)) return;
    const item = thumbnailItems.get(id),
      slide = doc.slide(id);
    if (!item || !slide) return;
    const frame = previews.frame(slide, `Vorschau ${item.getAttribute('aria-label')}`);
    item.querySelector('.sf-thumbnail-canvas').append(frame);
    thumbnailFrames.set(id, frame);
  }
  function updateThumbnailFallback() {
    if (thumbnailObserver || thumbnails.hidden) return;
    const viewport = thumbnails.getBoundingClientRect();
    visibleThumbnails.clear();
    for (const [id, item] of thumbnailItems) {
      const rect = item.getBoundingClientRect();
      if (
        viewport.width > 0 &&
        viewport.height > 0 &&
        rect.bottom >= viewport.top - 30 &&
        rect.top <= viewport.bottom + 30
      )
        visibleThumbnails.add(id);
    }
    for (const id of thumbnailFrames.keys()) if (!visibleThumbnails.has(id)) releaseThumbnail(id);
    for (const id of visibleThumbnails) mountThumbnail(id);
  }
  let thumbnailScrollFrame = null;
  function refreshThumbnailViewport() {
    if (thumbnailObserver || thumbnailScrollFrame !== null) return;
    thumbnailScrollFrame = requestAnimationFrame(() => {
      thumbnailScrollFrame = null;
      updateThumbnailFallback();
    });
  }
  thumbnails.addEventListener('scroll', refreshThumbnailViewport, { passive: true });
  function thumbnailCaption(id) {
    const item = thumbnailItems.get(id),
      position = doc.slideIndex(id),
      entry = doc.inventory()[position];
    if (item && entry)
      item.querySelector('.sf-thumbnail-caption').textContent = entry.deepDive
        ? `Deep Dive · ${entry.deepDive}`.slice(0, 64)
        : `${doc.slideNumber(doc.slide(id))} · ${entry.hidden ? 'Ausgeblendet · ' : ''}${entry.title.slice(0, 52)}`;
  }
  function clearThumbnailDrop() {
    thumbnailDrop?.entry.classList.remove('sf-drop-before', 'sf-drop-after');
    thumbnailDrop = null;
    if (thumbnailScroll !== null) cancelAnimationFrame(thumbnailScroll);
    thumbnailScroll = null;
  }
  function cancelThumbnailDrag() {
    if (thumbnailDrag)
      thumbnailItems.get(thumbnailDrag.id)?.classList.remove('sf-thumbnail-dragging');
    thumbnailDrag = null;
    clearThumbnailDrop();
  }
  function markThumbnailDrop(x, y) {
    clearThumbnailDrop();
    const bounds = thumbnails.getBoundingClientRect();
    if (
      !thumbnailDrag ||
      !interaction.editing ||
      thumbnails.hidden ||
      x < bounds.left ||
      x >= bounds.right ||
      y < bounds.top ||
      y >= bounds.bottom
    )
      return false;
    let position = 0,
      last = null;
    for (const item of thumbnailItems.values()) {
      const entry = item.parentElement,
        box = entry.getBoundingClientRect();
      last = entry;
      if (y < box.top + box.height / 2) {
        thumbnailDrop = { entry, position, after: false };
        break;
      }
      position++;
    }
    if (!thumbnailDrop && last) thumbnailDrop = { entry: last, position, after: true };
    if (!thumbnailDrop) return false;
    thumbnailDrop.entry.classList.add(thumbnailDrop.after ? 'sf-drop-after' : 'sf-drop-before');
    return true;
  }
  function scrollThumbnailDrag(time) {
    thumbnailScroll = null;
    if (!thumbnailDrag || !thumbnailDrop) return;
    const bounds = thumbnails.getBoundingClientRect(),
      edge = Math.min(40, bounds.height / 4),
      y = thumbnailDrag.y;
    const speed = y < bounds.top + edge ? -1 : y > bounds.bottom - edge ? 1 : 0;
    if (!speed) return;
    const elapsed = Math.min(40, time - thumbnailDrag.time),
      previous = thumbnails.scrollTop;
    thumbnailDrag.time = time;
    thumbnails.scrollTop += speed * elapsed * 0.45;
    if (thumbnails.scrollTop !== previous && markThumbnailDrop(thumbnailDrag.x, y))
      thumbnailScroll = requestAnimationFrame(scrollThumbnailDrag);
  }
  thumbnails.addEventListener('dragstart', (event) => {
    const item = event.target.closest('button[data-slide]');
    if (!item || !interaction.editing || thumbnails.hidden || !event.dataTransfer) {
      event.preventDefault();
      return;
    }
    cancelThumbnailDrag();
    thumbnailDrag = {
      id: item.dataset.slide,
      x: event.clientX,
      y: event.clientY,
      time: performance.now(),
    };
    event.dataTransfer.setData('application/x-slidefactory-slide', item.dataset.slide);
    event.dataTransfer.effectAllowed = 'move';
    item.classList.add('sf-thumbnail-dragging');
  });
  function overThumbnailDrag(event) {
    if (!thumbnailDrag) return;
    thumbnailDrag.x = event.clientX;
    thumbnailDrag.y = event.clientY;
    if (!thumbnails.contains(event.target) || !markThumbnailDrop(event.clientX, event.clientY)) {
      clearThumbnailDrop();
      if (event.dataTransfer) event.dataTransfer.dropEffect = 'none';
      return;
    }
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
    thumbnailDrag.time = performance.now();
    thumbnailScroll = requestAnimationFrame(scrollThumbnailDrag);
  }
  document.addEventListener('dragenter', overThumbnailDrag);
  document.addEventListener('dragover', overThumbnailDrag);
  thumbnails.addEventListener('dragleave', (event) => {
    if (thumbnailDrag && !thumbnails.contains(event.relatedTarget)) clearThumbnailDrop();
  });
  document.addEventListener('drop', (event) => {
    if (!thumbnailDrag) return;
    event.preventDefault();
    const id = thumbnailDrag.id,
      from = doc.slideIndex(id);
    const valid =
      thumbnails.contains(event.target) && markThumbnailDrop(event.clientX, event.clientY);
    const target = valid ? thumbnailDrop.position - (thumbnailDrop.position > from ? 1 : 0) : from;
    cancelThumbnailDrag();
    if (valid && from >= 0 && target !== from) {
      beforeEdit();
      doc.moveSlide(id, target - from);
      message(`Folie an Position ${target + 1} verschoben. Rückgängig ist möglich.`);
    }
  });
  document.addEventListener('dragend', cancelThumbnailDrag);
  document.addEventListener(
    'keydown',
    (event) => {
      if (event.key === 'Escape' && thumbnailDrag) {
        event.preventDefault();
        event.stopPropagation();
        cancelThumbnailDrag();
      }
    },
    true,
  );
  thumbnails.addEventListener('keydown', (event) => {
    const item = event.target.closest('button[data-slide]');
    if (
      !interaction.editing ||
      !item ||
      !event.altKey ||
      event.ctrlKey ||
      event.metaKey ||
      event.shiftKey ||
      !['ArrowUp', 'ArrowDown'].includes(event.key)
    )
      return;
    event.preventDefault();
    event.stopPropagation();
    cancelThumbnailDrag();
    beforeEdit();
    const id = item.dataset.slide;
    if (doc.moveSlide(id, event.key === 'ArrowUp' ? -1 : 1)) {
      thumbnailItems.get(id)?.focus();
      message(`Folie an Position ${doc.slideIndex(id) + 1} verschoben. Rückgängig ist möglich.`);
    }
  });
  function renderVisibility() {
    const only = doc.visibleSlides().length === 1,
      reason = 'Mindestens eine Folie muss sichtbar bleiben.';
    for (const [id, item] of thumbnailItems) {
      const i = doc.slideIndex(id),
        slide = doc.slide(id),
        hidden = doc.isHidden(slide),
        dive = doc.isDeepDive(slide),
        locked = !hidden && !dive && only;
      const [eye, remove] = item.nextElementSibling.children;
      const label = slideLabel(slide),
        action = `${label} ${hidden ? 'einblenden' : 'ausblenden'}`,
        outside = 'Deep Dives stehen immer außerhalb der Folienfolge.';
      eye.innerHTML = editorIcon(hidden ? 'eye-off' : 'eye');
      eye.disabled = locked || dive;
      remove.disabled = locked;
      eye.setAttribute('aria-label', locked ? `${action}. ${reason}` : dive ? outside : action);
      eye.title = locked ? reason : dive ? outside : action;
      remove.title = locked ? reason : `${label} löschen`;
      remove.setAttribute('aria-label', `${label} löschen`);
      item.setAttribute('aria-label', label + (hidden ? ' · ausgeblendet' : ''));
      item.classList.toggle('sf-thumbnail-hidden', hidden || dive);
      get('#sf-slide-choice').options[i].textContent = label + (hidden ? ' · ausgeblendet' : '');
    }
  }
  function renderThumbnails() {
    if (!interaction.editing) cancelThumbnailDrag();
    const order = doc.slides();
    if (order !== thumbnailOrder) {
      thumbnailOrder = order;
      thumbnailObserver?.disconnect();
      releaseThumbnails();
      visibleThumbnails.clear();
      thumbnailItems.clear();
      get('#sf-thumbnail-list').replaceChildren();
      const choice = get('#sf-slide-choice');
      choice.replaceChildren();
      if (typeof IntersectionObserver === 'function')
        thumbnailObserver = new IntersectionObserver(
          (entries) => {
            for (const entry of entries) {
              const id = entry.target.dataset.slide;
              if (entry.isIntersecting && !thumbnails.hidden) visibleThumbnails.add(id);
              else {
                visibleThumbnails.delete(id);
                releaseThumbnail(id);
              }
            }
            for (const id of visibleThumbnails) mountThumbnail(id);
          },
          { root: thumbnails, rootMargin: '30px' },
        );
      order.forEach((slide, position) => {
        const id = slide.dataset.sfSlide,
          item = document.createElement('button');
        item.type = 'button';
        item.dataset.slide = id;
        item.setAttribute('aria-label', `Folie ${position + 1}`);
        const canvas = document.createElement('span');
        canvas.className = 'sf-thumbnail-canvas';
        const caption = document.createElement('span');
        caption.className = 'sf-thumbnail-caption';
        item.append(canvas, caption);
        item.addEventListener('click', () => goTo(doc.slideIndex(id)));
        thumbnailItems.set(id, item);
        const wrapper = document.createElement('div');
        wrapper.className = 'sf-thumbnail-entry';
        wrapper.append(item);
        const controls = document.createElement('div');
        controls.className = 'sf-thumbnail-actions sf-edit-controls';
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.setAttribute('aria-label', `Folie ${position + 1} löschen`);
        remove.textContent = '×';
        const eye = document.createElement('button');
        eye.type = 'button';
        eye.className = 'sf-icon-button';
        eye.addEventListener('click', () => {
          beforeEdit();
          doc.toggleSlide(id);
        });
        remove.addEventListener('click', () => {
          beforeEdit();
          doc.deleteSlide(id);
        });
        controls.append(eye, remove);
        wrapper.append(controls);
        get('#sf-thumbnail-list').append(wrapper);
        thumbnailCaption(id);
        thumbnailObserver?.observe(item);
        const option = document.createElement('option');
        option.value = id;
        option.textContent = `Folie ${position + 1}`;
        choice.append(option);
      });
      renderVisibility();
    }
    for (const [id, item] of thumbnailItems) {
      item.setAttribute('aria-current', String(doc.slideIndex(id) === index));
      item.draggable = interaction.editing;
      item.title = interaction.editing
        ? 'Folie ziehen zum Verschieben · Esc bricht ab · Alt+↑/↓ per Tastatur'
        : '';
      if (interaction.editing) item.setAttribute('aria-keyshortcuts', 'Alt+ArrowUp Alt+ArrowDown');
      else item.removeAttribute('aria-keyshortcuts');
    }
    if (thumbnails.hidden) {
      releaseThumbnails();
      return;
    }
    updateThumbnailFallback();
    for (const id of visibleThumbnails) mountThumbnail(id);
  }
  function flushPanel() {
    clearTimeout(panelTimer);
    panelTimer = null;
    if (pendingPanel) {
      const token = pendingPanel.token;
      pendingPanel = null;
      committingPanel = true;
      try {
        doc.commit(token);
      } finally {
        committingPanel = false;
      }
    }
  }
  function beforeEdit() {
    doc.settle('command');
  }
  function deleteSelectedObject() {
    try {
      objects.remove();
    } catch (failure) {
      error(failure.message);
    }
  }
  function history(redo = false) {
    redo ? doc.redo() : doc.undo();
  }
  doc.registerSettler('editor-panel-input', flushPanel);
  function renderPanel() {
    const id = hooks.currentSlide()?.dataset.sfSlide;
    if (!id) return;
    const current = doc.slides()[index];
    get('#sf-panel-slide').textContent = doc.isDeepDive(current)
      ? slideLabel(current)
      : `Folie ${doc.slideNumber(current)} von ${storyCount()}`;
    for (const field of [get('#sf-guidance'), get('#sf-notes')]) {
      if (document.activeElement !== field || field.dataset.slide !== id) {
        if (field.id === 'sf-notes')
          noteEditor.set(doc.meta.notes[id] || '', notesCodec.current(doc.meta, id));
        else field.value = doc.meta.guidance[id]?.text || '';
      }
      field.dataset.slide = id;
    }
    get('#sf-addressed').checked = doc.meta.guidance[id]?.status === 'addressed';
    noteEditor.editable(true);
    get('#sf-guidance').readOnly = !interaction.editing;
  }
  function openPanel(mode) {
    endNotesResize(true);
    beforeEdit();
    panelMode = panelMode === mode ? null : mode;
    panel.hidden = panelMode !== 'guidance';
    notesPanel.hidden = panelMode !== 'notes';
    if (panelMode && innerWidth < 760) {
      thumbnails.hidden = true;
      button('thumbnails').setAttribute('aria-pressed', 'false');
    }
    get('[data-panel="guidance"]').hidden = panelMode !== 'guidance';
    button('guidance').setAttribute('aria-expanded', String(panelMode === 'guidance'));
    button('notes').setAttribute('aria-expanded', String(panelMode === 'notes'));
    renderPanel();
    renderThumbnails();
    fit();
  }
  function goTo(position) {
    const target = doc.slides()[Math.max(0, Math.min(doc.slides().length - 1, position))];
    // Presenting, a deep dive opens above the current slide instead of replacing it.
    if (!interaction.editing && doc.isDeepDive(target)) {
      openDeepDive(target.dataset.sfSlide);
      return;
    }
    closeDeepDive(false);
    closeMenu(false);
    textTools.reset();
    doc.settle('navigation');
    interaction.stopText();
    interaction.select(null);
    index = Math.max(0, Math.min(doc.slides().length - 1, position));
    try {
      window.history.replaceState(
        null,
        '',
        `#${encodeURIComponent(doc.slides()[index].dataset.sfSlide)}`,
      );
    } catch {}
    if (jumps.at(-1) === doc.slides()[index].dataset.sfSlide) jumps.pop();
    renderSlides();
  }
  // Jump history: origins of followed slide links, by stable slide ID (survives reordering).
  function follow(id) {
    const position = doc.slideIndex(id);
    if (position < 0) {
      error('Das Linkziel existiert nicht mehr.');
      return false;
    }
    const origin = doc.slides()[index].dataset.sfSlide;
    if (origin !== id) {
      jumps.push(origin);
      if (jumps.length > 20) jumps.shift();
    }
    goTo(position);
    return true;
  }
  function returnJump() {
    if (interaction.editing) return false;
    while (jumps.length) {
      const id = jumps.pop(),
        position = doc.slideIndex(id);
      if (position >= 0) {
        goTo(position);
        return true;
      }
    }
    renderReturn();
    return false;
  }
  function renderReturn() {
    const origin = [...jumps].reverse().find((id) => doc.slideIndex(id) >= 0),
      control = returnChip.firstElementChild;
    returnChip.hidden = !origin || interaction.editing;
    if (returnChip.hidden) return;
    control.textContent = `↩ Zurück zu Folie ${doc.slideNumber(doc.slide(origin))}`;
    positionPlayer();
  }
  function navigate(delta) {
    const i = doc.adjacent(index, delta, interaction.editing);
    if (i >= 0) goTo(i);
  }
  function slideLabel(slide) {
    return doc.isDeepDive(slide)
      ? `Deep Dive · ${doc.deepDiveName(slide)}`
      : `Folie ${doc.slideNumber(slide)}`;
  }
  const storyCount = () => doc.slides().filter((slide) => !doc.isDeepDive(slide)).length;
  function preferVisible() {
    const current = doc.slides()[index];
    if (!interaction.editing && (doc.isHidden(current) || doc.isDeepDive(current))) {
      const next = doc.adjacent(index, 1),
        i = next >= 0 ? next : doc.adjacent(index, -1);
      if (i >= 0) {
        goTo(i);
        return true;
      }
    }
    return false;
  }
  function syncTextControls() {
    const state = hooks.textTools?.getState();
    if (!state) return;
    for (const [selector, value, label] of [
      [
        '#sf-font-preset',
        state.fontSize === null ? 'mixed' : String(state.fontSize),
        state.fontSize === null ? 'Gemischt' : `${state.fontSize} pt`,
      ],
      ['#sf-font-family', state.fontFamily.split(',')[0].replace(/['"]/g, '').trim(), null],
    ]) {
      const field = get(selector);
      if (selector === '#sf-font-family' && (!state.fontFamily || document.activeElement === field))
        continue;
      field.querySelector('[data-current]')?.remove();
      if (![...field.options].some((option) => option.value === value)) {
        const option = document.createElement('option');
        option.dataset.current = '';
        option.value = value;
        option.textContent = label || value;
        option.disabled = value === 'mixed';
        field.append(option);
      }
      field.value = value;
    }
  }
  function selectionChanged(element) {
    const kind = element?.dataset.sfKind,
      cropping = !!hooks.images?.active;
    const sizeControls = [get('#sf-font-preset'), button('font-larger'), button('font-smaller')];
    const sizeDisabled = cropping || !hooks.textTools?.canSizeText();
    for (const control of chrome.querySelectorAll('[data-needs]'))
      control.disabled = sizeControls.includes(control)
        ? sizeDisabled
        : cropping ||
          (control.dataset.needs === 'text'
            ? kind !== 'text'
            : control.dataset.needs === 'image'
              ? kind !== 'image'
              : control.dataset.needs === 'link'
                ? !element?.hasAttribute('data-sf-link')
                : !hooks.objects?.canRemove(element));
    button('painter').disabled = !element || cropping;
    get('[data-context="crop"]').hidden = !cropping;
    syncTextControls();
  }
  get('#sf-font-preset').addEventListener('change', (event) =>
    textTools.command('fontSize', event.target.value),
  );
  get('#sf-font-family').addEventListener('change', (event) =>
    textTools.command('fontFamily', event.target.value),
  );
  function cropChanged(active) {
    if (active) get('#sf-zoom').value = '1';
    selectionChanged(interaction.selected);
  }
  get('#sf-zoom').addEventListener('input', (event) => images.zoom(event.target.value));
  palette.addEventListener('change', () => {
    beforeEdit();
    doc.run(
      'Farbschema ändern',
      [
        { kind: 'meta', path: ['colorScheme'] },
        { kind: 'meta', path: ['backgroundColor'] },
      ],
      () => {
        doc.meta.colorScheme = palette.value;
        delete doc.meta.backgroundColor;
      },
    );
  });
  let backgroundSession = null;
  function flushBackground() {
    if (backgroundSession) {
      const token = backgroundSession;
      backgroundSession = null;
      doc.commit(token);
    }
  }
  get('#sf-background').addEventListener('input', (event) => {
    if (!backgroundSession) {
      beforeEdit();
      backgroundSession = doc.begin('Hintergrundfarbe ändern', [
        { kind: 'meta', path: ['backgroundColor'] },
      ]);
    }
    doc.update(backgroundSession, () => {
      doc.meta.backgroundColor = event.target.value;
    });
    previews.invalidate();
  });
  get('#sf-background').addEventListener('change', flushBackground);
  get('#sf-background').addEventListener('blur', flushBackground);
  doc.registerSettler('background-input', flushBackground);
  function beginPanel(field) {
    if (!interaction.editing && field.id !== 'sf-notes') return false;
    const id = field.dataset.slide || hooks.currentSlide().dataset.sfSlide,
      key = field.id === 'sf-notes' ? 'notes' : 'guidance';
    if (pendingPanel && (pendingPanel.id !== id || pendingPanel.key !== key)) flushPanel();
    if (!pendingPanel) {
      beforeEdit();
      pendingPanel = {
        id,
        key,
        token: doc.begin('Notizen und Hinweise', [
          { kind: 'meta', path: [key, id] },
          ...(key === 'notes' ? [{ kind: 'meta', path: ['notesFormat', id] }] : []),
        ]),
      };
    }
    return true;
  }
  function writeNote(value, composing) {
    if (!beginPanel(get('#sf-notes'))) return;
    const { id, token } = pendingPanel;
    doc.update(token, () => {
      doc.meta.notes[id] = value.text;
      if (value.format) (doc.meta.notesFormat ||= {})[id] = value.format;
      else if (doc.meta.notesFormat) delete doc.meta.notesFormat[id];
    });
    clearTimeout(panelTimer);
    if (!composing) panelTimer = setTimeout(flushPanel, 450);
  }
  for (const field of [get('#sf-guidance')]) {
    field.addEventListener('beforeinput', (event) => {
      if (['historyUndo', 'historyRedo'].includes(event.inputType)) {
        event.preventDefault();
        history(event.inputType === 'historyRedo');
        return;
      }
      beginPanel(field);
    });
    field.addEventListener('input', () => {
      if (!beginPanel(field)) return;
      const { id, key, token } = pendingPanel;
      doc.update(token, () => {
        if (key === 'notes') doc.meta.notes[id] = field.value;
        else
          doc.meta.guidance[id] = { ...doc.meta.guidance[id], text: field.value, status: 'open' };
      });
      get('#sf-addressed').checked = doc.meta.guidance[id]?.status === 'addressed';
      clearTimeout(panelTimer);
      if (!panelComposing) panelTimer = setTimeout(flushPanel, 450);
    });
    field.addEventListener('compositionstart', () => {
      beginPanel(field);
      panelComposing = true;
      clearTimeout(panelTimer);
    });
    field.addEventListener('compositionend', () => {
      panelComposing = false;
      flushPanel();
    });
    field.addEventListener('blur', () => {
      if (!panelComposing) flushPanel();
    });
  }
  get('#sf-addressed').addEventListener('change', (event) => {
    beforeEdit();
    const id = hooks.currentSlide().dataset.sfSlide;
    doc.run('Hinweisstatus ändern', [{ kind: 'meta', path: ['guidance', id] }], () => {
      doc.meta.guidance[id] = {
        ...doc.meta.guidance[id],
        text: get('#sf-guidance').value,
        status: event.target.checked ? 'addressed' : 'open',
      };
    });
  });
  get('#sf-image-file').addEventListener('change', (event) => {
    const file = event.target.files[0];
    const target = replaceTarget;
    replaceTarget = null;
    event.target.value = '';
    if (file) images.importFile(file, target);
  });
  get('#sf-slide-choice').addEventListener('change', (event) => {
    const position = doc.slideIndex(event.target.value);
    if (position >= 0) goTo(position);
  });
  let menuAnchor = null,
    menuKind = null;
  function positionMenu() {
    if (!menuAnchor) return;
    const menu = get('#sf-menu'),
      rect = menuAnchor.getBoundingClientRect();
    menu.style.left = `${Math.max(8, Math.min(innerWidth - menu.offsetWidth - 8, rect.left))}px`;
    menu.style.top = `${Math.max(8, Math.min(innerHeight - menu.offsetHeight - 8, rect.bottom + 6))}px`;
  }
  function closeMenu(focus = true) {
    const anchor = menuAnchor;
    get('#sf-menu').hidden = true;
    menuAnchor = null;
    menuKind = null;
    anchor?.setAttribute('aria-expanded', 'false');
    hooks.textTools?.finishColor();
    hooks.objects?.finishColor();
    if (focus) anchor?.focus({ preventScroll: true });
  }
  function openMenu(kind) {
    if (menuKind === kind) {
      closeMenu();
      return;
    }
    closeMenu(false);
    textTools.captureSelection();
    beforeEdit();
    menuKind = kind;
    menuAnchor = button(kind);
    menuAnchor.setAttribute('aria-expanded', 'true');
    const menu = get('#sf-menu'),
      body = get('#sf-menu-body');
    body.replaceChildren();
    get('#sf-menu-label').textContent = {
      link: 'Folienlink · Ziel wählen',
      'link-target': 'Linkziel ändern',
      shapes: 'Formen',
      spacing: 'Zeilenabstand',
      vertical: 'Vertikale Ausrichtung',
      columns: 'Textspalten',
      save: 'HTML speichern',
      'text-color': 'Textfarbe',
      fill: 'Füllfarbe',
      border: 'Kantenfarbe',
    }[kind];
    function choice(label, callback, icon = null) {
      const control = document.createElement('button');
      control.type = 'button';
      control.setAttribute('aria-label', label);
      control.title = label;
      if (icon) control.innerHTML = editorIcon(icon);
      else control.textContent = label;
      control.addEventListener('click', () => {
        callback();
        closeMenu();
      });
      return control;
    }
    if (kind === 'link' || kind === 'link-target') {
      const current = hooks.currentSlide().dataset.sfSlide,
        target = kind === 'link-target' ? objects.linkTarget(interaction.selected) : null,
        list = document.createElement('div');
      list.className = 'sf-menu-list sf-slide-targets';
      doc.slides().forEach((slide, position) => {
        const id = slide.dataset.sfSlide;
        if (id === current) return;
        const entry = doc.inventory()[position],
          label = slideLabel(slide);
        const control = choice(
          (entry?.deepDive
            ? label
            : `${doc.slideNumber(slide)} · ${entry?.title || 'Folie'}`
          ).slice(0, 64),
          () => {
            try {
              if (kind === 'link') {
                if (objects.insertLink(id)) message(`Folienlink auf ${label} eingefügt.`);
              } else if (objects.setLinkTarget(id)) message(`Linkziel ist jetzt ${label}.`);
            } catch (failure) {
              error(failure.message);
            }
          },
        );
        if (id === target) control.setAttribute('aria-current', 'true');
        list.append(control);
      });
      if (!list.children.length) {
        const empty = document.createElement('p');
        empty.textContent = 'Keine weitere Folie als Ziel vorhanden.';
        list.append(empty);
      }
      body.append(list);
    } else if (kind === 'save') {
      const list = document.createElement('div');
      list.className = 'sf-menu-list';
      list.append(
        choice('Arbeitsstand mit Notizen', () => download(false)),
        choice('Weitergabe ohne Notizen', () => download(true)),
      );
      const hint = document.createElement('p');
      hint.textContent = 'Ohne Referentennotizen, Kommentare und Post-its.';
      body.append(list, hint);
    } else if (kind === 'shapes') {
      const grid = document.createElement('div');
      grid.className = 'sf-shape-grid';
      for (const [type, label] of [
        ['rectangle', 'Rechteck'],
        ['rounded-rectangle', 'Rechteck mit runden Ecken'],
        ['arrow-left', 'Pfeil links'],
        ['arrow-right', 'Pfeil rechts'],
        ['oval', 'Oval'],
        ['line', 'Linie'],
      ])
        grid.append(choice(label, () => objects.insertShape(type), type));
      body.append(grid);
    } else if (['spacing', 'vertical', 'columns'].includes(kind)) {
      const values =
        kind === 'spacing'
          ? [
              [1, '1,0'],
              [1.15, '1,15'],
              [1.5, '1,5'],
              [2, '2,0'],
            ]
          : kind === 'vertical'
            ? [
                ['start', 'Oben'],
                ['center', 'Mitte'],
                ['end', 'Unten'],
              ]
            : [
                [1, 'Eine Spalte'],
                [2, 'Zwei Spalten'],
                [3, 'Drei Spalten'],
              ];
      const list = document.createElement('div');
      list.className = 'sf-menu-list';
      for (const [value, label] of values)
        list.append(choice(label, () => textTools.command(kind, value)));
      body.append(list);
    } else {
      const apply = (color, preview = false) =>
        kind === 'text-color'
          ? preview
            ? textTools.colorInput(color)
            : textTools.command('color', color)
          : kind === 'fill'
            ? objects.setFill(color, preview)
            : objects.setBorder(color, preview);
      const colors = [
          '#ffffff',
          '#e4ecec',
          '#9ca3af',
          '#111827',
          '#ff595e',
          '#ff924c',
          '#ffca3a',
          '#ffff00',
          '#8ac926',
          '#2ec4b6',
          '#1982c4',
          '#4267ff',
          '#6a4c93',
          '#c77dff',
          '#f15bb5',
          '#795548',
        ],
        grid = document.createElement('div');
      grid.className = 'sf-color-grid';
      for (const color of colors) {
        const swatch = choice(color, () => apply(color));
        swatch.style.background = color;
        grid.append(swatch);
      }
      body.append(grid);
      const row = document.createElement('div');
      row.className = 'sf-color-row';
      const color = document.createElement('input');
      color.type = 'color';
      color.value = '#4267ff';
      color.setAttribute('aria-label', 'Eigene Farbe');
      color.title = 'Eigene Farbe';
      color.addEventListener('input', () => apply(color.value, true));
      for (const name of ['change', 'blur'])
        color.addEventListener(name, () => {
          textTools.finishColor();
          objects.finishColor();
        });
      row.append(color);
      if (kind === 'text-color' && window.isSecureContext && typeof EyeDropper === 'function') {
        const pipette = document.createElement('button');
        pipette.type = 'button';
        pipette.className = 'sf-icon-button';
        pipette.innerHTML = editorIcon('pipette');
        pipette.title = 'Textfarbe aufnehmen';
        pipette.setAttribute('aria-label', 'Textfarbe aufnehmen');
        pipette.addEventListener('click', () => textTools.pickColor());
        row.append(pipette);
      }
      if (kind !== 'text-color')
        row.append(
          choice(kind === 'fill' ? 'Keine Füllung' : 'Keine Kante', () =>
            apply(kind === 'fill' ? 'transparent' : 'none'),
          ),
        );
      body.append(row);
    }
    menu.hidden = false;
    positionMenu();
    body.querySelector('button,input')?.focus({ preventScroll: true });
  }
  document.addEventListener(
    'pointerdown',
    (event) => {
      if (
        menuAnchor &&
        !get('#sf-menu').contains(event.target) &&
        !menuAnchor.contains(event.target)
      )
        closeMenu(false);
    },
    true,
  );
  document.addEventListener(
    'keydown',
    (event) => {
      if (event.key === 'Escape' && !get('#sf-menu').hidden) {
        event.preventDefault();
        event.stopPropagation();
        closeMenu();
      }
    },
    true,
  );
  const actions = {
    previous: () => navigate(-1),
    next: () => navigate(1),
    presenter: () => presenter.open(),
    fullscreen: () => {
      if (!document.fullscreenElement && interaction.editing) actions.edit();
      presenter.fullscreen();
    },
    print: () => {
      get('#sf-print-error').textContent = '';
      get('#sf-print-dialog').showModal();
    },
    'cancel-print': () => get('#sf-print-dialog').close(),
    'confirm-print': () => {
      try {
        const slides = printer.select(get('#sf-print-range').value);
        get('#sf-print-dialog').close();
        printer.print(get('#sf-print-mode').value, slides);
      } catch (error) {
        get('#sf-print-error').textContent = error.message;
      }
    },
    edit: () => {
      closeDeepDive(false);
      closeMenu(false);
      textTools.reset();
      doc.settle(interaction.editing ? 'done' : 'command');
      interaction.setEditing(!interaction.editing);
      configureTriggers();
      button('edit').textContent = interaction.editing ? 'Fertig' : 'Bearbeiten';
      if (!interaction.editing && panelMode === 'guidance') openPanel('guidance');
      if (!preferVisible()) renderSlides();
      message(
        interaction.editing
          ? 'Bearbeitung aktiv. Änderungen bleiben zunächst im Browserentwurf.'
          : 'Ansicht aktiv. HTML speichern lädt den aktuellen Stand als neue Datei herunter.',
      );
    },
    thumbnails: () => {
      thumbnails.hidden = !thumbnails.hidden;
      button('thumbnails').setAttribute('aria-pressed', String(!thumbnails.hidden));
      renderThumbnails();
      fit();
    },
    guidance: () => openPanel('guidance'),
    notes: () => openPanel('notes'),
    'close-panel': () => openPanel(panelMode),
    undo: () => history(),
    insert: () => {
      replaceTarget = null;
      get('#sf-image-file').click();
    },
    replace: () => {
      replaceTarget = interaction.selected;
      get('#sf-image-file').click();
    },
    crop: () => images.start(),
    apply: () => images.apply(),
    cancel: () => images.cancel(),
    'new-slide': () => {
      beforeEdit();
      textTools.reset();
      interaction.stopText();
      const current = hooks.currentSlide(),
        id = `slide-${doc.freshId()}`,
        slide = document.createElement('section');
      slide.className = 'sf-slide';
      slide.dataset.sfSlide = id;
      slide.style.width = '1600px';
      slide.style.height = '900px';
      if (
        doc.run('Leere Folie einfügen', [{ kind: 'slide', id }], () => {
          current.after(slide);
          doc.meta.notes[id] = '';
          doc.meta.guidance[id] = { text: '', status: 'open' };
        })
      )
        goTo(doc.slideIndex(id));
    },
    text: () => objects.insertText(),
    postit: () => objects.insertPostit(),
    postits: () => objects.setPostitsVisible(doc.meta.postitsVisible === false),
    painter: () => textTools.copyFormat(),
    'delete-object': () => deleteSelectedObject(),
    shapes: () => openMenu('shapes'),
    link: () => openMenu('link'),
    'link-target': () => openMenu('link-target'),
    'return-jump': () => returnJump(),
    spacing: () => openMenu('spacing'),
    vertical: () => openMenu('vertical'),
    columns: () => openMenu('columns'),
    'text-color': () => openMenu('text-color'),
    fill: () => openMenu('fill'),
    border: () => openMenu('border'),
    'close-menu': () => closeMenu(),
    bold: () => textTools.command('bold'),
    italic: () => textTools.command('italic'),
    underline: () => textTools.command('underline'),
    strikeThrough: () => textTools.command('strikeThrough'),
    superscript: () => textTools.command('superscript'),
    subscript: () => textTools.command('subscript'),
    highlight: () => textTools.command('highlight'),
    left: () => textTools.command('align', 'left'),
    center: () => textTools.command('align', 'center'),
    right: () => textTools.command('align', 'right'),
    justify: () => textTools.command('align', 'justify'),
    bullets: () => textTools.command('insertUnorderedList'),
    numbering: () => textTools.command('insertOrderedList'),
    'font-larger': () => textTools.stepFontSize(2),
    'font-smaller': () => textTools.stepFontSize(-2),
    save: () => openMenu('save'),
  };
  // The working copy keeps notes and becomes the handoff; a share copy leaves the open state unsaved.
  function download(share) {
    try {
      beforeEdit();
      const html = doc.exportHtml({ share }),
        blob = new Blob([html], { type: 'text/html;charset=utf-8' }),
        url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `${(doc.meta.title || 'Präsentation').replace(/[\\/:*?"<>|]/g, '-').slice(0, 120)}${share ? ' (ohne Notizen)' : ''}.html`;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 15000);
      if (share) {
        message(
          'Weitergabe-Kopie ohne Notizen heruntergeladen. Für die Weiterarbeit den Arbeitsstand mit Notizen speichern.',
        );
        return;
      }
      fileNotice('download');
      message(
        'HTML-Download gestartet. Für die Weiterarbeit die heruntergeladene Datei verwenden.',
      );
    } catch (failure) {
      error(failure.message);
    }
  }
  chrome.addEventListener('pointerdown', (event) => {
    textTools.captureSelection();
    if (event.button === 0 && event.target.closest('.sf-context button,#sf-menu button'))
      event.preventDefault();
  });
  function invoke(event) {
    const target = event.target.closest('[data-action]');
    if (target && !target.disabled) {
      try {
        actions[target.dataset.action]?.();
      } catch (failure) {
        error(failure.message);
      }
    }
  }
  chrome.addEventListener('click', invoke);
  player.addEventListener('click', invoke);
  returnChip.addEventListener('click', invoke);
  // Slide links (and authored #slide anchors) navigate in view mode and record their origin; edit mode never navigates.
  doc.deck.addEventListener(
    'click',
    (event) => {
      const link = event.target.closest?.('a[href^="#"]');
      if (!link || !doc.deck.contains(link)) return;
      let id = null;
      try {
        id = decodeURIComponent(link.getAttribute('href').slice(1));
      } catch {}
      if (interaction.editing) {
        event.preventDefault();
        return;
      }
      if (doc.slideIndex(id) < 0) {
        if (link.hasAttribute('data-sf-link')) {
          event.preventDefault();
          error('Das Linkziel existiert nicht mehr.');
        }
        return;
      }
      event.preventDefault();
      link.blur();
      if (doc.isDeepDive(doc.slide(id))) openDeepDive(id, link);
      else follow(id);
    },
    true,
  );
  // Triggers act only in view and fullscreen mode; edit mode keeps double-click for editing.
  const triggerSelector = '[data-sf-id][data-sf-deep-dive-target]';
  function storyTrigger(node) {
    const trigger = node?.closest?.(triggerSelector);
    return trigger && !interaction.editing && !doc.isDeepDive(trigger.closest('[data-sf-slide]'))
      ? trigger
      : null;
  }
  function openTrigger(trigger) {
    const slide = doc.deepDiveTarget(trigger);
    if (slide) openDeepDive(slide.dataset.sfSlide, trigger);
    else error('Das Deep-Dive-Ziel dieser Fläche existiert nicht mehr.');
  }
  doc.deck.addEventListener('dblclick', (event) => {
    const trigger = storyTrigger(event.target);
    if (!trigger) return;
    event.preventDefault();
    window.getSelection()?.removeAllRanges();
    openTrigger(trigger);
  });
  doc.deck.addEventListener('keydown', (event) => {
    const trigger = storyTrigger(event.target);
    if (
      trigger !== event.target ||
      !['Enter', ' '].includes(event.key) ||
      event.ctrlKey ||
      event.metaKey ||
      event.altKey ||
      event.repeat
    )
      return;
    event.preventDefault();
    event.stopPropagation();
    openTrigger(trigger);
  });
  // Runtime-only button semantics; export and projections restore the authored attributes.
  function runtimeValue(node, name, value) {
    const marker = `data-sf-runtime-original-${name}`;
    if (value !== null) {
      if (!node.hasAttribute(marker))
        node.setAttribute(marker, node.getAttribute(name) ?? '__absent__');
      node.setAttribute(name, value);
    } else if (node.hasAttribute(marker)) {
      const original = node.getAttribute(marker);
      if (original === '__absent__') node.removeAttribute(name);
      else node.setAttribute(name, original);
      node.removeAttribute(marker);
    }
  }
  function configureTriggers(roots = [doc.deck]) {
    const nodes = roots.flatMap((root) => [
      ...(root.matches(triggerSelector) ? [root] : []),
      ...root.querySelectorAll(triggerSelector),
    ]);
    for (const node of nodes) {
      const trigger = storyTrigger(node),
        target = trigger && doc.deepDiveTarget(trigger);
      const name = target ? doc.deepDiveName(target) : null;
      runtimeValue(node, 'role', trigger ? 'button' : null);
      runtimeValue(node, 'aria-label', trigger ? `Details: ${name || 'Ziel fehlt'}` : null);
      runtimeValue(
        node,
        'title',
        trigger ? (name ? 'Doppelklick für Details' : 'Deep-Dive-Ziel fehlt') : null,
      );
      if (trigger) node.setAttribute('tabindex', '0');
      if (trigger) node.dataset.sfRuntimeDeepDive = name ? 'ready' : 'broken';
      else delete node.dataset.sfRuntimeDeepDive;
    }
  }
  function openDeepDive(id, opener = null) {
    const slide = doc.slide(id);
    if (!doc.isDeepDive(slide)) {
      error('Das Deep-Dive-Ziel existiert nicht mehr.');
      return false;
    }
    closeDeepDive(false);
    closeMenu(false);
    const name = doc.deepDiveName(slide),
      frame = previews.frame(slide, `Deep Dive ${name}`);
    deepDive.querySelector('.sf-deep-dive-stage').replaceChildren(frame);
    deepDive.querySelector('.sf-deep-dive-name').textContent = name;
    deepDive.setAttribute('aria-label', `Deep Dive: ${name}`);
    deepDive.hidden = false;
    openDive = { id, frame, opener };
    positionDeepDive();
    deepDive.querySelector('button').focus({ preventScroll: true });
    presenter.sync();
    return true;
  }
  function closeDeepDive(focus = true) {
    if (!openDive) return false;
    const { frame, opener } = openDive;
    openDive = null;
    previews.release(frame);
    deepDive.hidden = true;
    if (focus && opener?.isConnected) opener.focus({ preventScroll: true });
    presenter.sync();
    return true;
  }
  // Scaled to fit the main slide's stage with a visible margin, its name above it.
  function positionDeepDive() {
    if (!openDive) return;
    const rect = doc.deck.getBoundingClientRect(),
      [header, stage] = deepDive.children,
      space = header.offsetHeight + 8;
    const scale = Math.max(
      0.05,
      Math.min((rect.width * 0.88) / 1600, (rect.height * 0.88 - space) / 900),
    );
    const width = 1600 * scale,
      height = 900 * scale,
      left = rect.left + (rect.width - width) / 2,
      top = rect.top + (rect.height - height + space) / 2;
    Object.assign(stage.style, {
      left: `${left}px`,
      top: `${top}px`,
      width: `${width}px`,
      height: `${height}px`,
    });
    Object.assign(header.style, {
      left: `${left}px`,
      top: `${top - space}px`,
      width: `${width}px`,
    });
    openDive.frame.style.transform = `scale(${scale})`;
  }
  deepDive.querySelector('button').addEventListener('click', () => closeDeepDive());
  deepDive.addEventListener('click', (event) => {
    if (!deepDive.lastElementChild.contains(event.target) && !event.target.closest('button'))
      closeDeepDive();
  });
  // While open, storyline and editor keys never reach the slide behind the overlay.
  window.addEventListener(
    'keydown',
    (event) => {
      if (!openDive) return;
      event.stopPropagation();
      if (event.key === 'Escape') {
        event.preventDefault();
        closeDeepDive();
      } else if (event.key === 'Tab') {
        event.preventDefault();
        deepDive.querySelector('button').focus({ preventScroll: true });
      } else if (
        !(deepDive.contains(event.target) && ['Enter', ' '].includes(event.key)) &&
        !event.ctrlKey &&
        !event.metaKey &&
        !event.altKey
      )
        event.preventDefault();
    },
    true,
  );
  doc.onChange((event) => {
    if (event.type === 'update') fileNotice('dirty');
    else if (event.type === 'error') error(event.message);
    else if (event.type === 'storage')
      doc.storageWarning ? error(event.message) : message(event.message);
    else if (event.type === 'change') {
      fileNotice('dirty');
      if (event.theme) {
        palette.value = doc.meta.colorScheme;
        get('#sf-background').value =
          doc.meta.backgroundColor || doc.schemes[doc.meta.colorScheme].tokens.background;
        previews.invalidate();
      } else if (event.visual) for (const id of event.slideIds) previews.invalidate(id);
      if (event.structural) {
        const active = visibleSlide?.dataset.sfSlide,
          position = doc.slideIndex(active);
        index = position >= 0 ? position : Math.min(index, doc.slides().length - 1);
        if (interaction.selected && !interaction.selected.isConnected) interaction.select(null);
        renderSlides();
      }
      if (event.visibility) {
        renderVisibility();
        if (!preferVisible()) renderSlides();
      }
      historyButtons();
      // Edits reconfigure only the changed objects; structural changes recheck the deck.
      if (event.structural) configureTriggers();
      else if (event.objectIds.length)
        configureTriggers(event.objectIds.map((id) => doc.object(id)).filter(Boolean));
      if (event.inventory) for (const id of event.slideIds) thumbnailCaption(id);
      if (event.metaPaths.length) {
        if (event.phase !== 'commit' || !committingPanel)
          for (const field of [get('#sf-guidance'), get('#sf-notes')]) field.dataset.slide = '';
        renderPanel();
      }
      message('Änderungen im Browserentwurf. HTML speichern erstellt die vollständige Datei.');
      presenter.sync(event);
    }
  });
  const pendingLayouts = new Set();
  let layoutFrame = null;
  doc.deck.addEventListener('sf:layout', (event) => {
    if (!['commit', 'undo'].includes(event.detail.phase)) return;
    pendingLayouts.add(event.detail.slideId);
    if (layoutFrame !== null) return;
    layoutFrame = requestAnimationFrame(() => {
      layoutFrame = null;
      const ids = [...pendingLayouts];
      pendingLayouts.clear();
      for (const id of ids) previews.invalidate(id);
      presenter.sync({ type: 'change', visual: true, slideIds: ids });
    });
  });
  window.addEventListener('hashchange', () => {
    const position = doc.slideIndex(decodeURIComponent(location.hash.slice(1)));
    if (position >= 0) goTo(position);
  });
  window.addEventListener('resize', fit);
  window.addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && !event.altKey && event.key.toLowerCase() === 'p') {
      event.preventDefault();
      actions.print();
      return;
    }
    if (
      event.key.toLowerCase() === 'f' &&
      !event.ctrlKey &&
      !event.metaKey &&
      !event.altKey &&
      !event.repeat &&
      !event.isComposing &&
      !event.defaultPrevented &&
      !event.target.isContentEditable &&
      !event.target.closest?.(
        'input,textarea,select,form,[role="textbox"],[role="combobox"],[contenteditable]:not([contenteditable="false"]),dialog,[role="dialog"],[aria-modal="true"]',
      ) &&
      !document.querySelector('dialog[open],[aria-modal="true"]:not([hidden])')
    ) {
      event.preventDefault();
      actions.fullscreen();
      return;
    }
    if (
      event.key === 'Backspace' &&
      !interaction.editing &&
      jumps.length &&
      !event.ctrlKey &&
      !event.metaKey &&
      !event.altKey &&
      !event.shiftKey &&
      !event.isComposing &&
      !event.defaultPrevented &&
      !event.target.isContentEditable &&
      !event.target.closest?.(
        'input,textarea,select,[contenteditable]:not([contenteditable="false"]),dialog,[role="dialog"]',
      ) &&
      !document.querySelector('dialog[open]')
    ) {
      event.preventDefault();
      returnJump();
      return;
    }
    if (event.key === 'Escape' && document.fullscreenElement)
      document.exitFullscreen().catch(() => error('Vollbild konnte nicht beendet werden.'));
  });
  document.addEventListener('fullscreenchange', fit);
  const resizeObserver = new ResizeObserver(fit);
  resizeObserver.observe(thumbnails);
  resizeObserver.observe(get('.sf-toolbar'));
  resizeObserver.observe(get('.sf-context'));
  resizeObserver.observe(get('.sf-feedback'));
  let initial = doc
    .slides()
    .findIndex((slide) => `#${encodeURIComponent(slide.dataset.sfSlide)}` === location.hash);
  // A deep dive's hash opens it above its first trigger's slide, else the first storyline slide.
  const initialDive = doc.isDeepDive(doc.slides()[initial])
    ? doc.slides()[initial].dataset.sfSlide
    : null;
  if (initialDive) {
    const host = [...doc.deck.querySelectorAll(triggerSelector)]
      .filter((node) => node.getAttribute('data-sf-deep-dive-target') === initialDive)
      .map((node) => node.closest('[data-sf-slide]'))
      .find((slide) => !doc.isDeepDive(slide));
    initial = host ? doc.slideIndex(host.dataset.sfSlide) : doc.adjacent(-1, 1);
  }
  if (initial >= 0) index = initial;
  for (const slide of doc.slides()) slide.dataset.sfRuntimeVisible = 'false';
  interaction.setEditing(false);
  configureTriggers();
  if (initial >= 0 || !preferVisible()) renderSlides();
  if (initialDive) openDeepDive(initialDive);
  message(doc.draftMessage || 'Bereit · eine vollständige Präsentation in einer HTML-Datei.');
  if (doc.storageWarning) error(doc.storageWarning);
  document.dispatchEvent(new CustomEvent('sf:ready', { detail: { deckId: doc.meta.deckId } }));
  view();
  requestAnimationFrame(() => previews.invalidate());
  document.fonts?.ready.then(() => {
    previews.invalidate();
    presenter.sync({ type: 'change', theme: true });
  });
  window.addEventListener('pagehide', () => {
    thumbnails.removeEventListener('scroll', refreshThumbnailViewport);
    if (thumbnailScrollFrame !== null) cancelAnimationFrame(thumbnailScrollFrame);
    releaseThumbnails();
    thumbnailObserver?.disconnect();
    resizeObserver.disconnect();
    textTools.dispose();
    objects.dispose();
    presenter.dispose();
    printer.dispose();
    previews.dispose();
  });
}

async function initializeSlideFactory() {
  const sfDocument = await createDocument();
  if (sfDocument.valid) startEditor(sfDocument);
  else {
    const failure = document.createElement('div');
    failure.dataset.sfTransient = '';
    failure.className = 'sf-fatal';
    failure.setAttribute('role', 'alert');
    failure.textContent = `SlideFactory konnte diese Datei nicht öffnen: ${sfDocument.error} Der ursprüngliche Quelltext wurde erhalten.`;
    const save = document.createElement('button');
    save.type = 'button';
    save.textContent = 'HTML speichern';
    save.disabled = true;
    failure.append(document.createElement('br'), save);
    document.body.append(failure);
  }
}
// Wait for the complete parsed file. Authored diagrams initialize on sf:ready.
if (document.readyState === 'loading')
  document.addEventListener('DOMContentLoaded', initializeSlideFactory, { once: true });
else initializeSlideFactory();
