/* The popup is a projection. Only its owning presentation can mutate state. */
function createPresenter(doc, previews, owner) {
  const protocol = 'slidefactory-presenter',
    version = 1;
  const notesCodec = createNotesCodec(document);
  const object = (value) => value && typeof value === 'object' && !Array.isArray(value);
  let active = null,
    ticker = null,
    disposed = false,
    listening = false;
  let elapsed = 0,
    started = null,
    catalog = [],
    target = 0,
    inventoryReady = false;
  // Meeting end (HH:MM) for the wall-clock countdown; presenter-only, never deck content.
  const endKey = () => `slidefactory:presenter-end:${doc.meta.deckId}`;
  let endTime = '';
  try {
    endTime = localStorage.getItem(endKey()) || '';
  } catch {}
  const time = () => elapsed + (started === null ? 0 : (performance.now() - started) / 1000);
  // Per-slide time accumulates over all visits while the timer runs; reset clears it.
  // Scope time: the current part (data-sf-part), or '' for a deck without parts. A
  // slide without part in a deck with parts (backup) keeps the part it was reached from.
  const slideTimes = new Map(),
    scopeTimes = new Map(),
    furthest = new Map();
  let slideId = null,
    slideMark = null,
    scope = null;
  const hasParts = () => catalog.some((entry) => !entry?.hidden && entry?.part);
  const inScope = (entry) =>
    !!entry && !entry.hidden && (hasParts() ? entry.part === scope : scope === '');
  function account() {
    const now = performance.now();
    if (slideMark !== null) {
      const spent = (now - slideMark) / 1000;
      if (slideId !== null) slideTimes.set(slideId, (slideTimes.get(slideId) || 0) + spent);
      if (scope !== null) scopeTimes.set(scope, (scopeTimes.get(scope) || 0) + spent);
    }
    slideMark = started === null ? null : now;
  }
  // The plan follows the furthest slide reached in a scope while the timer runs.
  function advance() {
    const index = owner.index();
    if (started !== null && inScope(catalog[index]))
      furthest.set(scope, Math.max(furthest.get(scope) ?? -1, index));
  }
  function track() {
    const index = owner.index(),
      id = doc.slides()[index]?.dataset.sfSlide ?? null,
      entry = catalog[index];
    if (id !== slideId) {
      account();
      slideId = id;
    }
    if (entry) {
      if (!hasParts()) scope = '';
      else if (!entry.hidden && entry.part) scope = entry.part;
    }
    advance();
  }
  const running = () => (slideMark === null ? 0 : (performance.now() - slideMark) / 1000);
  const timeOf = (id) => (slideTimes.get(id) || 0) + (id === slideId ? running() : 0);
  const slideTime = () => timeOf(slideId);
  // Pace: scope elapsed vs. plan now = durations of scope slides before the furthest
  // one reached + min(time on that slide, its duration). Going back does not lower
  // the plan; time spent there (or on backups) still counts as scope elapsed.
  function pace() {
    if (
      scope === null ||
      !catalog.some((entry) => !entry.hidden && (duration(entry) || entry.partDuration))
    )
      return null;
    const index = owner.index(),
      reached = furthest.get(scope) ?? -1,
      mark = catalog[reached];
    const entries = catalog.filter(inScope),
      sum = (list) => list.reduce((total, entry) => total + (duration(entry) || 0), 0);
    return {
      label: hasParts() ? scope : null,
      elapsed: (scopeTimes.get(scope) || 0) + running(),
      before: sum(catalog.slice(0, Math.max(reached, 0)).filter(inScope)),
      markTime: mark ? timeOf(mark.id) : 0,
      markDuration: duration(mark) || 0,
      onMark: reached === index,
      budget: hasParts()
        ? entries.find((entry) => entry.partDuration)?.partDuration || sum(entries)
        : target,
    };
  }
  const title = (entry, index) => ({
    id: entry.id,
    hidden: entry.hidden,
    title: `${index + 1} · ${String(entry.title || 'Folie')
      .trim()
      .slice(0, 70)}`,
    duration: entry.duration,
    part: entry.part || null,
    partDuration: entry.partDuration || null,
  });
  const duration = (entry) =>
    !entry?.hidden && Number.isFinite(entry?.duration) && entry.duration >= 0
      ? entry.duration
      : null;
  function inventory(event, force) {
    if (inventoryReady && !force && !event?.inventory) return {};
    const entries = doc.inventory(),
      ids = event?.slideIds || [];
    if (
      !inventoryReady ||
      force ||
      entries.length !== catalog.length ||
      !ids.length ||
      ids.some((id) => catalog[doc.slideIndex(id)]?.id !== id)
    ) {
      catalog = entries.map(title);
      target = entries.reduce((sum, entry) => sum + (duration(entry) || 0), 0);
      inventoryReady = true;
      return { inventory: catalog };
    }
    const inventoryUpdates = [];
    for (const id of new Set(ids)) {
      const index = doc.slideIndex(id),
        entry = entries[index];
      if (!entry) continue;
      target += (duration(entry) || 0) - (duration(catalog[index]) || 0);
      catalog[index] = title(entry, index);
      inventoryUpdates.push({ index, entry: catalog[index] });
    }
    return { inventoryUpdates };
  }
  function send(channel, type, fields = {}) {
    if (!channel || channel.window.closed) return false;
    try {
      channel.window.postMessage(
        { protocol, version, deckId: doc.meta.deckId, session: channel.session, type, ...fields },
        '*',
      );
      return true;
    } catch {
      return false;
    }
  }
  function clock() {
    if (!active) return;
    if (active.window.closed) {
      detach(active);
      return;
    }
    track();
    send(active, 'clock', {
      clock: {
        elapsed: time(),
        running: started !== null,
        state: started !== null ? 'running' : elapsed > 0 ? 'paused' : 'stopped',
        endTime,
        target,
        duration: duration(catalog[owner.index()]),
        slide: slideTime(),
        pace: pace(),
      },
    });
  }
  function sync(event = null, force = false) {
    track();
    if (disposed || !active || active.window.closed) return;
    if (event === true) {
      force = true;
      event = null;
    }
    if (event && event.type !== 'change' && event.type !== 'view') return;
    const index = owner.index(),
      entry = doc.inventory()[index];
    if (!entry) return;
    const previous = active.state,
      navigating = force || previous?.slideId !== entry.id || previous?.index !== index;
    const inventoryPatch = inventory(event, force),
      ids = event?.slideIds || [],
      paths = event?.metaPaths || [],
      state = {};
    const previousId = doc.slides()[doc.adjacent(index, -1)]?.dataset.sfSlide || null,
      nextId = doc.slides()[doc.adjacent(index, 1)]?.dataset.sfSlide || null;
    if (navigating || event?.inventory)
      Object.assign(state, {
        slideId: entry.id,
        index,
        previousId,
        nextId,
        duration: duration(entry),
      });
    if (
      navigating ||
      paths.some(
        (path) =>
          ['notes', 'notesProvenance', 'notesFormat'].includes(path[0]) &&
          (path.length === 1 || path[1] === entry.id),
      )
    ) {
      Object.assign(state, { notesHtml: notesCodec.display(doc.meta, entry.id) });
    }
    const viewIds = [entry.id, nextId],
      views = [];
    for (let position = 0; position < 2; position++) {
      const id = viewIds[position],
        revision = id === null ? null : doc.slideVersion(id),
        last = active.views[position];
      if (
        force ||
        navigating ||
        event?.theme ||
        (event?.visual && ids.includes(id)) ||
        last?.id !== id ||
        last?.revision !== revision
      ) {
        const source = id === null ? null : previews.source(doc.slide(id));
        if (force || source !== last?.source) views[position] = source;
        active.views[position] = { id, revision, source };
      }
    }
    active.state = { ...previous, ...state };
    if (
      Object.keys(state).length ||
      Object.keys(inventoryPatch).length ||
      views.some((source) => source !== undefined)
    ) {
      send(active, 'projection', { state, ...inventoryPatch, views });
    }
    if (navigating || event?.inventory || force) clock();
  }
  function detach(channel) {
    if (!channel || channel !== active) return;
    channel.views = [];
    channel.state = null;
    active = null;
    clearInterval(ticker);
    ticker = null;
    if (listening) {
      window.removeEventListener('message', receive);
      listening = false;
    }
  }
  function timer(action) {
    track();
    account();
    if (action === 'start' && started === null) started = performance.now();
    if (action === 'pause' && started !== null) {
      elapsed = time();
      started = null;
    }
    // Stop halts and clears slide, part and furthest marks. 'reset' (no button since 1.3.4,
    // still accepted from older popups) clears the same but keeps a running timer running.
    if (action === 'reset' || action === 'stop') {
      elapsed = 0;
      started = action === 'stop' || started === null ? null : performance.now();
      slideTimes.clear();
      scopeTimes.clear();
      furthest.clear();
    }
    account();
    advance();
    clock();
  }
  function feedback(text, error = false) {
    owner[error ? 'error' : 'message'](text);
  }
  async function fullscreen() {
    try {
      if (!document.documentElement.requestFullscreen)
        throw Error('Vollbild ist in diesem Browser nicht verfügbar.');
      window.focus();
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
      feedback(document.fullscreenElement ? 'Vollbild aktiv.' : 'Vollbild beendet.');
    } catch {
      feedback('Vollbild konnte nicht geöffnet werden. Die Präsentation bleibt verfügbar.', true);
    }
  }
  function receive(event) {
    const command = event.data,
      channel = active;
    if (
      disposed ||
      !channel ||
      event.source !== channel.window ||
      !object(command) ||
      command.protocol !== protocol ||
      command.version !== version ||
      command.session !== channel.session ||
      command.deckId !== doc.meta.deckId ||
      command.type !== 'command' ||
      !object(command.payload)
    )
      return;
    if (command.command === 'close') {
      detach(channel);
      return;
    }
    if (channel.window.closed) {
      detach(channel);
      return;
    }
    const payload = command.payload;
    if (command.command === 'ready') sync(null, true);
    else if (command.command === 'navigate' && typeof payload.slideId === 'string') {
      const index = doc.slideIndex(payload.slideId);
      if (index >= 0) owner.goTo(index);
    } else if (
      command.command === 'timer' &&
      ['start', 'pause', 'reset', 'stop'].includes(payload.action)
    )
      timer(payload.action);
    else if (
      command.command === 'end-time' &&
      typeof payload.value === 'string' &&
      /^(?:(?:[01]\d|2[0-3]):[0-5]\d)?$/.test(payload.value)
    ) {
      endTime = payload.value;
      try {
        if (endTime) localStorage.setItem(endKey(), endTime);
        else localStorage.removeItem(endKey());
      } catch {}
      clock();
    } else if (command.command === 'return-jump') owner.returnJump?.();
  }
  function popupRuntime(config) {
    let state = null,
      connected = true,
      closing = false;
    const get = (id) => document.getElementById(id);
    const send = (command, payload = {}) => {
      if (!connected || !window.opener || window.opener.closed) {
        disconnect();
        return false;
      }
      window.opener.postMessage({ ...config, type: 'command', command, payload }, '*');
      return true;
    };
    function release() {
      clearInterval(connectionTimer);
      for (const id of ['current-preview', 'next-preview']) get(id).removeAttribute('srcdoc');
      window.removeEventListener('message', receive);
      window.removeEventListener('resize', fit);
      state = null;
    }
    function disconnect() {
      if (!connected) return;
      connected = false;
      get('connection').hidden = false;
      get('connection').textContent = 'Verbindung zur Präsentation beendet.';
      document.querySelectorAll('button:not(#close),select').forEach((node) => {
        node.disabled = true;
      });
      release();
    }
    function fit() {
      for (const id of ['current-preview', 'next-preview']) {
        const frame = get(id),
          scale = frame.parentElement.clientWidth / 1600;
        frame.style.transform = `scale(${scale})`;
        frame.parentElement.style.height = `${900 * scale}px`;
      }
    }
    function formatTime(seconds) {
      const whole = Math.floor(seconds);
      return `${String(Math.floor(whole / 60)).padStart(2, '0')}:${String(whole % 60).padStart(2, '0')}`;
    }
    function wallClock() {
      get('wall-clock').textContent = new Date().toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
      });
    }
    // The owner window may be throttled in the background; the visible popup
    // advances the last received base value on its own tick.
    let clockBase = null,
      clockAt = 0;
    function clock(value) {
      clockBase = value;
      clockAt = performance.now();
      get('start').disabled = value.running;
      get('pause').disabled = !value.running;
      get('stop').disabled = value.state === 'stopped';
      get('timer-state').textContent =
        { running: 'läuft', paused: 'pausiert', stopped: 'gestoppt' }[value.state] || '';
      get('timer-state').dataset.state = value.state;
      if (document.activeElement !== get('end-time')) get('end-time').value = value.endTime || '';
      renderClock();
    }
    function hours(seconds) {
      const whole = Math.floor(seconds),
        h = Math.floor(whole / 3600);
      return h ? `${h}:${formatTime(whole % 3600)}` : formatTime(whole);
    }
    // Wall-clock countdown to the meeting end; independent of the presentation timer.
    function renderCountdown() {
      const value = clockBase?.endTime,
        node = get('countdown');
      get('end-clear').hidden = !value;
      node.hidden = !value;
      if (!value) return;
      const now = new Date(),
        [h, m] = value.split(':').map(Number),
        end = new Date(now);
      end.setHours(h, m, 0, 0);
      if (end - now < -6 * 3600 * 1000) end.setDate(end.getDate() + 1);
      const left = (end - now) / 1000;
      node.textContent =
        left >= 0
          ? `noch ${hours(Math.ceil(left))} bis ${value}`
          : `+${hours(-left)} über ${value}`;
      node.dataset.state = left < 0 ? 'over' : left <= 600 ? 'soon' : 'ok';
    }
    function renderClock() {
      renderCountdown();
      const value = clockBase;
      if (!value) return;
      const extra = value.running ? (performance.now() - clockAt) / 1000 : 0,
        elapsed = value.elapsed + extra,
        slide = (value.slide || 0) + extra;
      get('timer').textContent = formatTime(elapsed);
      get('timer').dataset.running = String(value.running);
      get('slide-time').textContent =
        `Folie ${formatTime(slide)}${value.duration ? ` / ${formatTime(value.duration)}` : ''}`;
      get('slide-time').dataset.over = String(!!value.duration && slide > value.duration);
      const pace = value.pace;
      get('pace').hidden = !pace;
      if (!pace) {
        get('target').textContent = '';
        return;
      }
      const done = pace.elapsed + extra,
        plan = pace.before + Math.min(pace.markTime + (pace.onMark ? extra : 0), pace.markDuration),
        delta = done - plan;
      get('target').textContent =
        `${pace.label || 'Gesamt'} ${formatTime(done)} / Plan ${formatTime(plan)}${pace.budget ? ` · ${pace.label ? 'Budget' : 'Ziel'} ${formatTime(pace.budget)}` : ''}`;
      get('pace').textContent =
        Math.abs(delta) < 1
          ? 'im Plan'
          : `${delta > 0 ? '+' : '−'}${formatTime(Math.abs(delta))} ${delta > 0 ? 'hinter' : 'vor'} Plan`;
      get('pace').dataset.state = Math.abs(delta) < 1 ? 'on' : delta > 0 ? 'behind' : 'ahead';
    }
    function option(entry) {
      const node = document.createElement('option');
      node.value = entry.id;
      node.textContent = entry.title;
      node.hidden = entry.hidden;
      return node;
    }
    function receive(event) {
      const message = event.data;
      if (
        event.source !== window.opener ||
        !message ||
        message.protocol !== config.protocol ||
        message.version !== config.version ||
        message.session !== config.session ||
        message.deckId !== config.deckId
      )
        return;
      if (message.type === 'disconnect') {
        disconnect();
        return;
      }
      if (!connected) return;
      if (message.type === 'clock') {
        if (message.clock) clock(message.clock);
        return;
      }
      if (message.type !== 'projection' || !message.state) return;
      const patch = message.state,
        select = get('slide');
      state = { ...state, ...patch };
      get('connection').textContent = 'Mit Präsentation verbunden.';
      get('connection').hidden = true;
      if (message.inventory) {
        state.slides = message.inventory;
        select.replaceChildren(...state.slides.map(option));
      }
      if (message.inventoryUpdates)
        for (const { index, entry } of message.inventoryUpdates) {
          state.slides[index] = entry;
          const existing = select.options[index];
          if (existing) {
            existing.value = entry.id;
            existing.textContent = entry.title;
            existing.hidden = entry.hidden;
          }
        }
      select.value = state.slideId;
      get('previous').disabled = !state.previousId;
      get('next').disabled = !state.nextId;
      if ('notesHtml' in patch) get('notes').innerHTML = state.notesHtml;
      let refit = false;
      (message.views || []).forEach((source, index) => {
        if (source !== undefined) {
          const frame = get(index ? 'next-preview' : 'current-preview');
          frame.hidden = source === null;
          if (source === null) frame.removeAttribute('srcdoc');
          else frame.srcdoc = source;
          refit = true;
        }
      });
      if (refit) fit();
    }
    window.addEventListener('message', receive);
    get('slide').addEventListener('change', (event) =>
      send('navigate', { slideId: event.target.value }),
    );
    get('previous').addEventListener('click', () => {
      if (state?.previousId) send('navigate', { slideId: state.previousId });
    });
    get('next').addEventListener('click', () => {
      if (state?.nextId) send('navigate', { slideId: state.nextId });
    });
    window.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        close();
        window.close();
        return;
      }
      if (
        !connected ||
        !state ||
        event.defaultPrevented ||
        event.isComposing ||
        event.altKey ||
        event.ctrlKey ||
        event.metaKey ||
        event.shiftKey
      )
        return;
      if (event.target instanceof Element && event.target.closest('input,select,textarea')) return;
      if (event.key === 'Backspace') {
        event.preventDefault();
        send('return-jump', {});
        return;
      }
      const step = ['ArrowLeft', 'ArrowUp', 'PageUp'].includes(event.key)
        ? -1
        : ['ArrowRight', 'ArrowDown', 'PageDown'].includes(event.key)
          ? 1
          : 0;
      if (!step) return;
      const slideId = step < 0 ? state.previousId : state.nextId;
      if (slideId && send('navigate', { slideId })) event.preventDefault();
    });
    function close() {
      if (closing) return;
      closing = true;
      send('close');
      release();
    }
    get('close').addEventListener('click', () => {
      close();
      window.close();
    });
    for (const action of ['start', 'pause', 'stop'])
      get(action).addEventListener('click', () => send('timer', { action }));
    get('end-time').addEventListener('change', (event) =>
      send('end-time', { value: event.target.value }),
    );
    get('end-clear').addEventListener('click', () => {
      get('end-time').value = '';
      send('end-time', { value: '' });
    });
    window.addEventListener('resize', fit);
    const connectionTimer = setInterval(() => {
      wallClock();
      renderClock();
      if (!window.opener || window.opener.closed) disconnect();
    }, 250);
    window.addEventListener('pagehide', close, { once: true });
    wallClock();
    send('ready');
  }
  function open() {
    if (disposed) return;
    owner.flush();
    if (active && !active.window.closed) {
      active.window.focus();
      sync(null, true);
      return;
    }
    if (active) detach(active);
    clearInterval(ticker);
    ticker = null;
    const popup = window.open('', '_blank');
    if (!popup) {
      owner.error(
        'Referentenansicht wurde vom Browser blockiert. Bitte Popups für diese Datei erlauben.',
      );
      return;
    }
    const channel = { window: popup, session: doc.freshId(), views: [], state: null };
    active = channel;
    if (!listening) {
      window.addEventListener('message', receive);
      listening = true;
    }
    const config = doc.json({
      protocol,
      version,
      deckId: doc.meta.deckId,
      session: channel.session,
    });
    popup.document.write(
      `<!DOCTYPE html><html lang="de"><head><meta charset="utf-8"><title>SlideFactory · Referentenansicht</title><style>${document.getElementById('sf-editor-styles').textContent}</style><style>
html,body{margin:0;background:#152028;color:#e4ecec;font:14px/1.5 Arial,sans-serif}
body{padding:12px}
*{box-sizing:border-box}
button,select{font:inherit;color:inherit;background:#243841;border:1px solid #53676f;padding:6px}
button{cursor:pointer}
button:disabled{opacity:.45;cursor:default}
button:focus-visible,select:focus-visible,#notes:focus-visible{outline:2px solid #86dbcb;outline-offset:2px}
[hidden]{display:none!important}
#close{position:fixed;top:12px;right:12px;z-index:1;width:36px;height:36px;font-size:24px;line-height:1;padding:0;background:#152028e6}
.previews{display:grid;grid-template-columns:minmax(0,2fr) minmax(0,1fr);gap:12px;align-items:start}
.preview{position:relative;overflow:hidden;width:100%;background:#000}
iframe{position:absolute;left:0;top:0;width:1600px;height:900px;border:0;transform-origin:0 0;pointer-events:none}
.navigation,.timing{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:8px}
.navigation select{min-width:0;max-width:calc(100% - 72px)}
.timing button{min-width:32px}
#timer{font-size:28px;font-variant-numeric:tabular-nums}
#wall-clock{margin-left:auto;font-size:20px;font-variant-numeric:tabular-nums}
#target,#slide-time,#connection{color:#b8c9ca}
#target,#slide-time{flex-basis:100%;font-size:13px;font-variant-numeric:tabular-nums}
#slide-time{color:#e4ecec}
#slide-time[data-over="true"]{color:#ffca3a}
#timer-state{font-size:12px;color:#b8c9ca}
#timer-state[data-state="stopped"]{color:#ffca3a}
.end{flex-basis:100%;display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.end input{font:inherit;color:inherit;background:#243841;border:1px solid #53676f;padding:4px}
#countdown{font-size:20px;font-variant-numeric:tabular-nums}
#countdown[data-state="soon"]{color:#ffca3a}
#countdown[data-state="over"]{color:#ff595e}
#pace{flex-basis:100%;font-size:20px;font-variant-numeric:tabular-nums}
#pace[data-state="ahead"]{color:#8ac926}
#pace[data-state="behind"]{color:#ff595e}
#pace[data-state="on"]{color:#e4ecec}
#notes{margin-top:12px;min-height:120px;max-height:none;border:0;padding:12px;overflow:visible}
#notes:empty::before{content:'Keine Referentennotizen';color:#b8c9ca}
#connection{margin-top:8px}
@media(max-width:650px){.previews{grid-template-columns:minmax(0,3fr) minmax(0,2fr)}
.timing{gap:4px}
#timer{font-size:22px}
#wall-clock{font-size:16px}
}
</style></head><body><button id="close" type="button" aria-label="Referentenansicht schließen" title="Referentenansicht schließen (Esc)">×</button>
<div class="previews"><section aria-label="Aktuelle Folie"><div class="preview"><iframe id="current-preview" title="Aktuelle Folie" sandbox="allow-same-origin" tabindex="-1"></iframe></div><nav class="navigation" aria-label="Foliennavigation"><button id="previous" aria-label="Vorherige Folie">‹</button><select id="slide" aria-label="Folie"></select><button id="next" aria-label="Nächste Folie">›</button></nav></section><section aria-label="Nächste Folie"><div class="preview"><iframe id="next-preview" title="Nächste Folie" sandbox="allow-same-origin" tabindex="-1"></iframe></div><div class="timing"><output id="timer" role="timer" aria-label="Verstrichene Zeit">00:00</output><button id="start" aria-label="Start" title="Timer starten">▶</button><button id="pause" aria-label="Pause" title="Timer pausieren">Ⅱ</button><button id="stop" aria-label="Stopp" title="Timer anhalten und alle Zeiten zurücksetzen">■</button><span id="timer-state"></span><time id="wall-clock" aria-label="Uhrzeit"></time><span class="end"><label for="end-time">Ende</label><input id="end-time" type="time" aria-label="Zieluhrzeit"><button id="end-clear" aria-label="Zieluhrzeit löschen" title="Zieluhrzeit löschen" hidden>×</button><strong id="countdown" hidden></strong></span><strong id="pace" aria-label="Abweichung vom Zeitplan" hidden></strong><span id="slide-time" aria-label="Zeit auf dieser Folie"></span><span id="target" aria-label="Zeit gegenüber Plan"></span></div></section></div>
<div id="notes" class="sf-note-input" role="region" aria-label="Referentennotizen" tabindex="0"></div><div id="connection" role="status">Verbindung wird hergestellt …</div><script>(${popupRuntime.toString()})(${config});</scr` +
        'ipt></body></html>',
    );
    popup.document.close();
    ticker = setInterval(clock, 250);
    sync(null, true);
  }
  function dispose() {
    if (disposed) return;
    disposed = true;
    send(active, 'disconnect');
    detach(active);
    catalog = [];
    window.removeEventListener('message', receive);
    window.removeEventListener('pagehide', dispose);
    listening = false;
  }
  window.addEventListener('pagehide', dispose, { once: true });
  return { open, sync, fullscreen, dispose };
}
