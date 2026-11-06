/* Disposable, non-executing full-slide projections; printing never exports/saves. */
function createPrinter(doc, previews, owner) {
  const codec = createNotesCodec(document);
  let output = null,
    request = 0,
    active = null;
  // Native printing keeps DOM order; runtime marks move named deep dives behind the storyline.
  function clearMarks() {
    for (const slide of doc.slides()) {
      delete slide.dataset.sfRuntimePrint;
      delete slide.dataset.sfRuntimePrintLast;
    }
  }
  function nativePrint() {
    doc.settle('print');
    previews.beginNativePrint();
    clearMarks();
    const story = doc.visibleSlides(),
      appendix = doc.appendix(story);
    for (const slide of doc.slides())
      if (doc.isDeepDive(slide))
        slide.dataset.sfRuntimePrint = appendix.includes(slide) ? 'appendix' : 'omit';
    const last = appendix.at(-1) || story.at(-1);
    if (last) last.dataset.sfRuntimePrintLast = '';
    // Browser-menu printing is synchronous; awaited hooks belong to print().
    for (const slide of [...story, ...appendix]) previews.prepareNative(slide);
  }
  function finishNativePrint() {
    clearMarks();
    previews.finishNativePrint();
  }
  window.addEventListener('beforeprint', nativePrint);
  window.addEventListener('afterprint', finishNativePrint);
  function closeOutput() {
    request++;
    active?.stop();
    active = null;
    if (output && !output.closed) output.close();
    output = null;
  }
  function dispose() {
    closeOutput();
    finishNativePrint();
    window.removeEventListener('beforeprint', nativePrint);
    window.removeEventListener('afterprint', finishNativePrint);
  }
  // A range counts storyline numbers; deep dives follow as the appendix of print().
  function select(value) {
    if (!value.trim()) return doc.visibleSlides();
    const numbered = doc.slides().filter((slide) => !doc.isDeepDive(slide)),
      positions = new Set();
    for (const part of value.replace(/–/g, '-').split(',')) {
      const match = part.trim().match(/^(\d+)(?:\s*-\s*(\d+))?$/);
      if (!match) throw Error('Bitte Folien als 1,3-5 eingeben oder das Feld leer lassen.');
      const start = Number(match[1]),
        end = Number(match[2] || match[1]);
      if (start < 1 || end < start || end > numbered.length)
        throw Error(`Bitte Folien zwischen 1 und ${numbered.length} auswählen.`);
      for (let i = start; i <= end; i++) positions.add(i - 1);
    }
    const selected = [...positions]
      .sort((a, b) => a - b)
      .map((index) => numbered[index])
      .filter((slide) => !doc.isHidden(slide));
    if (!selected.length) throw Error('Der gewählte Bereich enthält nur ausgeblendete Folien.');
    return selected;
  }
  async function print(mode = 'slides', selected = doc.visibleSlides()) {
    const withNotes = mode !== 'slides',
      onlyNotes = mode === 'only-notes';
    closeOutput();
    doc.settle('print');
    const generation = request;
    const popup = window.open('', '_blank');
    output = popup;
    if (!popup) {
      owner.error('Druckansicht wurde blockiert. Bitte Popups für diese Datei erlauben.');
      return;
    }
    const controller = new AbortController(),
      story = selected.filter((slide) => !doc.isDeepDive(slide)),
      slides = [...story, ...doc.appendix(story)];
    const label = (slide) =>
      doc.isDeepDive(slide)
        ? `Deep Dive · ${doc.deepDiveName(slide)}`
        : `Folie ${doc.slideNumber(slide)}`;
    let phase = 'Folien vorbereiten',
      completed = 0,
      phaseStart = Date.now(),
      status = null,
      progress = null,
      controls = null,
      failed = false,
      ticker;
    const job = {
      stop() {
        clearInterval(ticker);
        controller.abort();
      },
    };
    active = job;
    const current = () => generation === request && !popup.closed && !controller.signal.aborted;
    const statusStyle =
      '.sf-print-progress{position:fixed;top:12px;left:12px;right:12px;max-width:520px;z-index:1000;padding:14px;border:1px solid #53676f;border-radius:6px;background:#1c2b34;color:#e4ecec;font:14px/1.4 Arial,sans-serif;box-shadow:0 4px 20px #0005}.sf-print-progress p{margin:0 0 8px}.sf-print-progress progress{width:100%;height:8px}.sf-print-progress button{display:block;margin-top:8px;padding:6px 12px;border:1px solid #86dbcb;border-radius:4px;background:transparent;color:inherit;cursor:pointer}@media print{.sf-print-progress{display:none!important}}';
    function cancel() {
      if (generation !== request) return;
      closeOutput();
      if (!failed) owner.message('Druckvorbereitung abgebrochen.');
    }
    function update() {
      if (!status || failed) return;
      const slow = Date.now() - phaseStart >= 10000;
      const text = `${phase}: ${completed} / ${slides.length} Folien bereit.${slow ? ' Das Laden dauert länger. Bitte warten oder abbrechen.' : ' Bitte warten …'}`;
      if (status.textContent !== text) status.textContent = text;
      progress.value = completed;
    }
    function showProgress() {
      controls = popup.document.createElement('aside');
      controls.className = 'sf-print-progress';
      status = popup.document.createElement('p');
      status.setAttribute('role', 'status');
      status.setAttribute('aria-live', 'polite');
      progress = popup.document.createElement('progress');
      progress.max = slides.length;
      progress.setAttribute('aria-label', 'Vorbereitete Folien');
      const button = popup.document.createElement('button');
      button.type = 'button';
      button.textContent = 'Abbrechen';
      button.addEventListener('click', cancel);
      controls.append(status, progress, button);
      popup.document.body.append(controls);
      update();
    }
    function frameReady(frame, number) {
      return new Promise((resolve, reject) => {
        let stage = 'Druckvorschau',
          settled = false;
        const finish = (error) => {
          if (settled) return;
          settled = true;
          clearTimeout(timeout);
          frame.removeEventListener('load', loaded);
          controller.signal.removeEventListener('abort', aborted);
          if (error) reject(error);
          else {
            completed++;
            update();
            resolve();
          }
        };
        const aborted = () =>
          finish(new DOMException('Druckvorbereitung abgebrochen.', 'AbortError'));
        const timeout = setTimeout(
          () =>
            finish(
              Error(
                `${stage} der ${number} nach 120 Sekunden nicht bereit. Bitte erneut versuchen oder diese Folie prüfen.`,
              ),
            ),
          120000,
        );
        async function loaded() {
          if (settled) return;
          try {
            stage = 'Schriften';
            await frame.contentDocument.fonts?.ready;
            if (settled) return;
            if ([...frame.contentDocument.fonts].some((font) => font.status === 'error'))
              throw Error('Eine Schrift konnte nicht geladen werden.');
            stage = 'Bilder';
            await Promise.all([...frame.contentDocument.images].map((img) => img.decode()));
            if (settled) return;
            frame.contentDocument.body.getBoundingClientRect();
            finish();
          } catch (error) {
            finish(Error(`${stage} der ${number}: ${error.message}`));
          }
        }
        controller.signal.addEventListener('abort', aborted, { once: true });
        frame.addEventListener('load', loaded, { once: true });
      });
    }
    popup.document.write(
      `<!DOCTYPE html><html lang="de"><head><title>Druckvorbereitung</title><style>${statusStyle}</style></head><body></body></html>`,
    );
    popup.document.close();
    showProgress();
    ticker = setInterval(() => {
      if (popup.closed) {
        cancel();
        return;
      }
      update();
    }, 1000);
    try {
      const sources = [],
        notes = slides.map((slide) => codec.display(doc.meta, slide.dataset.sfSlide));
      const ticket = doc.ticket({});
      if (!onlyNotes)
        for (const slide of slides) {
          sources.push(await previews.prepare(slide, current));
          if (!current()) return;
          completed++;
          update();
        }
      if (!doc.accepts(ticket))
        throw Error(
          'Die Präsentation wurde während der Druckvorbereitung geändert. Bitte erneut drucken.',
        );
      const scale = withNotes ? (186 * 96) / 25.4 / 1600 : (320 * 96) / 25.4 / 1600;
      popup.document.open();
      popup.document
        .write(`<!DOCTYPE html><html lang="de"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; frame-src about:; img-src data:; font-src data:; style-src 'unsafe-inline'"><title>${onlyNotes ? 'Nur Notizen' : withNotes ? 'Folien mit Notizen darunter' : 'Folien'}</title><style>
      @page{size:${withNotes ? 'A4 portrait' : '320mm 180mm'};margin:${withNotes ? '12mm' : '0'}}
      *{box-sizing:border-box;-webkit-print-color-adjust:exact;print-color-adjust:exact}html,body{margin:0;padding:0;background:white;color:black;font:14pt/1.45 Arial,sans-serif}body{width:${withNotes ? '186mm' : '320mm'}}
      .sf-print-page{break-before:page;page-break-before:always;margin:0;padding:0}.sf-print-page:first-of-type{break-before:auto;page-break-before:auto}
      .sf-print-slide{position:relative;width:100%;height:${withNotes ? '104.625mm' : '180mm'};overflow:hidden;break-inside:avoid;page-break-inside:avoid}
      iframe{position:absolute;left:0;top:0;width:1600px;height:900px;border:0;transform:scale(${scale});transform-origin:0 0}
      .sf-print-notes{margin-top:8mm;white-space:pre-wrap;overflow-wrap:anywhere}.sf-print-notes p,.sf-print-notes li{break-inside:auto;page-break-inside:auto;orphans:2;widows:2}.sf-print-notes p{margin:0 0 .6em}.sf-print-notes ul,.sf-print-notes ol{padding-left:1.8em}
      ${statusStyle}</style></head><body></body></html>`);
      popup.document.close();
      phase = 'Druckvorschauen laden';
      completed = 0;
      phaseStart = Date.now();
      showProgress();
      const ready = [];
      for (let i = 0; i < slides.length; i++) {
        const page = popup.document.createElement('section');
        page.className = 'sf-print-page';
        page.dataset.slide = slides[i].dataset.sfSlide;
        if (!onlyNotes) {
          const box = popup.document.createElement('div');
          box.className = 'sf-print-slide';
          const frame = popup.document.createElement('iframe');
          frame.title = label(slides[i]);
          frame.setAttribute('sandbox', 'allow-same-origin');
          ready.push(frameReady(frame, label(slides[i])));
          frame.srcdoc = sources[i];
          box.append(frame);
          page.append(box);
        } else {
          const heading = popup.document.createElement('h1');
          heading.style.fontSize = '14pt';
          heading.textContent = label(slides[i]);
          page.append(heading);
        }
        if (withNotes) {
          const note = popup.document.createElement('div');
          note.className = 'sf-print-notes';
          note.innerHTML = notes[i];
          page.append(note);
        }
        popup.document.body.append(page);
      }
      await Promise.all(ready);
      popup.document.body.getBoundingClientRect();
      if (!current()) return;
      if (!doc.accepts(ticket))
        throw Error(
          'Die Präsentation wurde während der Druckvorbereitung geändert. Bitte erneut drucken.',
        );
      controls.remove();
      status = null;
      popup.document.documentElement.dataset.sfPrintReady = 'true';
      job.stop();
      if (active === job) active = null;
      popup.focus();
      popup.print();
    } catch (error) {
      if (current()) {
        failed = true;
        owner.error(`Druckvorbereitung fehlgeschlagen: ${error.message}`);
        status.setAttribute('role', 'alert');
        status.textContent = `Druckvorbereitung fehlgeschlagen: ${error.message}`;
        progress.remove();
        controls.querySelector('button').textContent = 'Schließen';
      }
    } finally {
      job.stop();
      if (active === job) active = null;
    }
  }
  return { print, dispose, select };
}
