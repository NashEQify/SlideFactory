/* Shared compact chrome; inline SVG needs no external icon/font resource. */
function editorIcon(name) {
  const paths = {
    undo: 'M8 4 3 9l5 5M3 9h11a6 6 0 0 1 0 12',
    overview: 'M3 4h18v16H3zM8 4v16',
    painter: 'M4 3h16v7H4zM7 10v4h5v7h3v-9h5v-2',
    slide: 'M3 4h18v13H3zM12 14v8M8 18h8',
    text: 'M4 5V3h16v2M12 3v18M8 21h8',
    image: 'M20 13v7H4V4h9M4 16l5-5 8 9M18 3v6m-3-3h6M8 8h.01',
    shapes: 'M3 3h7v7H3zM16 3l5 7H11zM7 15a4 4 0 1 0 0 .01M14 15h7v6h-7z',
    replace: 'M3 5h12l-3-3m3 3-3 3M21 19H9l3 3m-3-3 3-3M3 9v9h3M21 15V6h-3',
    bold: 'M6 3h7a4.5 4.5 0 0 1 0 9H6zm0 9h8a4.5 4.5 0 0 1 0 9H6z',
    italic: 'M10 3h10M4 21h10M15 3 9 21',
    underline: 'M6 3v8a6 6 0 0 0 12 0V3M4 21h16',
    strike: 'M18 5c-2-3-12-3-12 2 0 3 4 4 7 5s6 2 5 5c-1 5-12 5-13 1M3 12h18',
    highlight: 'm9 15 7-11 5 4-9 9-3-2Zm0 0-3 4h5l1-2M3 22h18',
    color: 'm5 18 7-15 7 15M8 12h8M3 22h18',
    fill: 'm4 12 8-8 8 8-8 8zM8 2l8 8M21 16v4M3 23h18',
    border: 'M4 4h16v16H4z',
    crop: 'M6 2v16h16M2 6h16v16',
    trash: 'M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7',
    postit: 'M3 3h18v12l-6 6H3zM15 21v-6h6M7 8h10M7 12h6',
    eye: 'M2 12c5-9 15-9 20 0-5 9-15 9-20 0Zm10-3a3 3 0 1 0 0 6 3 3 0 0 0 0-6',
    'eye-off':
      'M3 3l18 18M10 6c5-1 9 2 12 6l-3 4M6 7c-2 1-3 3-4 5 5 8 12 9 17 5M10 10a3 3 0 0 0 4 4',
    fullscreen: 'M3 9V3h6M15 3h6v6M21 15v6h-6M9 21H3v-6',
    pipette: 'm14 5 5 5M3 18l10-10 3 3L6 21H3zM13 4l3-3 7 7-3 3z',
    spacing: 'M3 3v18m-2-16 2-2 2 2m-4 14 2 2 2-2M9 4h12M9 12h12M9 20h12',
    vertical: 'M3 3h18M3 21h18M12 7v10m-3-7 3-3 3 3m-6 4 3 3 3-3',
    columns: 'M3 3h7v18H3zM14 3h7v18h-7z',
    rectangle: 'M3 5h18v14H3z',
    'rounded-rectangle': 'M7 5h10a4 4 0 0 1 4 4v6a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4V9a4 4 0 0 1 4-4z',
    'arrow-left': 'M3 12 11 4v5h10v6H11v5z',
    'arrow-right': 'M21 12 13 4v5H3v6h10v5z',
    oval: 'M2 12a10 7 0 1 0 20 0 10 7 0 1 0-20 0',
    line: 'M3 19 21 5',
    close: 'm5 5 14 14M5 19 19 5',
    link: 'M10 14a4 4 0 0 0 6 0l3-3a4 4 0 0 0-6-6l-1 1M14 10a4 4 0 0 0-6 0l-3 3a4 4 0 0 0 6 6l1-1',
    'link-target':
      'M3 12a9 9 0 1 0 18 0 9 9 0 1 0-18 0M8 12a4 4 0 1 0 8 0 4 4 0 1 0-8 0M12 1v6M12 17v6M1 12h6M17 12h6',
  };
  if (['left', 'center', 'right', 'justify'].includes(name)) {
    const x = name === 'center' ? 6 : name === 'right' ? 10 : 2;
    return `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 4h20M${x} 9h${name === 'justify' ? 20 : 12}M2 14h20M${x} 19h${name === 'justify' ? 20 : 12}"/></svg>`;
  }
  if (['bullets', 'numbering'].includes(name))
    return `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5h13M9 12h13M9 19h13"/>${name === 'bullets' ? '<circle cx="3" cy="5" r="1"/><circle cx="3" cy="12" r="1"/><circle cx="3" cy="19" r="1"/>' : '<text x="1" y="7">1</text><text x="1" y="14">2</text><text x="1" y="21">3</text>'}</svg>`;
  if (['superscript', 'subscript', 'font-larger', 'font-smaller'].includes(name))
    return `<svg viewBox="0 0 24 24" aria-hidden="true"><text class="sf-icon-letter" x="2" y="19">${name.startsWith('font') ? 'A' : 'x'}</text><text x="15" y="${name === 'subscript' ? 22 : 8}">${name === 'font-larger' ? '+' : name === 'font-smaller' ? '−' : '2'}</text></svg>`;
  return `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name] || paths.text}"/></svg>`;
}
function editorTool(action, label, icon = action, extra = '') {
  return `<button type="button" class="sf-icon-button" data-action="${action}" aria-label="${label}" title="${label}" ${extra}>${editorIcon(icon)}</button>`;
}
function createEditorChrome() {
  const chrome = document.createElement('div');
  chrome.id = 'sf-editor';
  chrome.dataset.sfTransient = '';
  const tool = editorTool,
    group = (label, top, bottom, classes = '') =>
      `<div class="sf-tool-group ${classes}"><div class="sf-tool-row">${top}</div><div class="sf-tool-row">${bottom}</div><span class="sf-group-label">${label}</span></div>`;
  chrome.innerHTML = `
    <header class="sf-toolbar" aria-label="Präsentationswerkzeuge">
      <span class="sf-brand">SlideFactory</span>${tool('undo', 'Rückgängig', 'undo')}${tool('thumbnails', 'Folienübersicht', 'overview', 'aria-pressed="true"')}
      <span class="sf-toolbar-spacer"></span><button type="button" data-action="guidance" class="sf-edit-controls" aria-expanded="false">Kommentare</button><button type="button" data-action="notes" aria-expanded="false">Referentennotizen</button>${tool('postits', 'Post-its anzeigen / verbergen', 'eye', 'aria-pressed="true"')}<button type="button" data-action="presenter">Referentenansicht</button><button type="button" data-action="print">Drucken/PDF</button><button type="button" data-action="save" class="sf-save">HTML speichern</button><button type="button" data-action="edit" class="sf-primary">Bearbeiten</button>
    </header>
    <div class="sf-context" aria-label="Bearbeitungswerkzeuge">
      <div class="sf-tool-group sf-painter-group">${tool('painter', 'Format kopieren', 'painter', 'aria-pressed="false"')}<span class="sf-group-label">Format</span></div>
      ${group('Einfügen', tool('new-slide', 'Leere Folie einfügen', 'slide') + tool('text', 'Textfeld einfügen') + tool('insert', 'Bild einfügen', 'image'), tool('shapes', 'Form einfügen', 'shapes', 'aria-haspopup="dialog" aria-expanded="false"') + tool('replace', 'Bild ersetzen', 'replace', 'data-needs="image"') + tool('link', 'Folienlink einfügen', 'link', 'aria-haspopup="dialog" aria-expanded="false"') + tool('link-target', 'Linkziel ändern', 'link-target', 'data-needs="link" aria-haspopup="dialog" aria-expanded="false"'))}
      ${group('Schrift', `<select id="sf-font-family" aria-label="Schriftart" data-needs="text">${['Arial', 'Calibri', 'Georgia', 'Times New Roman', 'Verdana', 'Courier New'].map((font) => `<option>${font}</option>`).join('')}</select><select id="sf-font-preset" aria-label="Schriftgröße" data-needs="text">${[8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 40, 44, 48, 54, 60, 72, 96].map((size) => `<option value="${size}">${size} pt</option>`).join('')}</select>${tool('font-larger', 'Schrift vergrößern', 'font-larger', 'data-needs="text"')}${tool('font-smaller', 'Schrift verkleinern', 'font-smaller', 'data-needs="text"')}`, ['bold', 'italic', 'underline', 'strikeThrough', 'superscript', 'subscript', 'highlight', 'text-color'].map((action, i) => tool(action, ['Fett', 'Kursiv', 'Unterstrichen', 'Durchgestrichen', 'Hochgestellt', 'Tiefgestellt', 'Textmarker · Gelb', 'Textfarbe'][i], ['bold', 'italic', 'underline', 'strike', 'superscript', 'subscript', 'highlight', 'color'][i], 'data-needs="text"')).join(''), 'sf-font-group')}
      ${group(
        'Absatz',
        [
          ['bullets', 'Aufzählung'],
          ['numbering', 'Nummerierte Liste'],
          ['spacing', 'Zeilenabstand'],
          ['vertical', 'Vertikale Ausrichtung'],
          ['columns', 'Textspalten'],
        ]
          .map(([action, label]) => tool(action, label, action, 'data-needs="text"'))
          .join(''),
        [
          ['left', 'Linksbündig'],
          ['center', 'Zentriert'],
          ['right', 'Rechtsbündig'],
          ['justify', 'Blocksatz'],
        ]
          .map(([action, label]) => tool(action, label, action, 'data-needs="text"'))
          .join(''),
      )}
      ${group('Objekt', tool('fill', 'Füllfarbe', 'fill', 'data-needs="object"') + tool('border', 'Kantenfarbe', 'border', 'data-needs="object"'), tool('crop', 'Bild zuschneiden', 'crop', 'data-needs="image"') + tool('delete-object', 'Objekt löschen', 'trash', 'data-needs="object"'))}
      ${group('Post-its', tool('postit', 'Post-it einfügen'), '')}
      ${group('Farbschema', '<select id="sf-palette" aria-label="Farbschema"></select><input id="sf-background" type="color" aria-label="Hintergrundfarbe" title="Hintergrundfarbe">', '', 'sf-scheme-group')}
      <div data-context="crop" hidden><label for="sf-zoom">Bildausschnitt</label><input id="sf-zoom" type="range" min="1" max="4" step="0.01" value="1"><button type="button" data-action="apply">Übernehmen</button><button type="button" data-action="cancel">Abbrechen</button></div>
    </div>
    <nav id="sf-thumbnails" class="sf-thumbnails" aria-label="Folienübersicht"><div class="sf-sidebar-heading"><div class="sf-nav"><button type="button" data-action="previous" aria-label="Vorherige Folie">‹</button><span id="sf-counter"></span><button type="button" data-action="next" aria-label="Nächste Folie">›</button></div><select id="sf-slide-choice" aria-label="Folie auswählen"></select></div><div id="sf-thumbnail-list"></div></nav><div id="sf-sidebar-resize" role="separator" tabindex="0" aria-label="Breite der Folienübersicht" aria-controls="sf-thumbnails" aria-orientation="vertical"></div>
    <aside class="sf-panel" hidden><p id="sf-panel-slide" class="sf-panel-slide" aria-live="polite"></p><div data-panel="guidance"><h2>Kommentare</h2><p>Ein Kommentar für die Weiterarbeit an dieser Folie.</p><label for="sf-guidance">Bearbeitungskommentar</label><textarea id="sf-guidance" aria-describedby="sf-panel-slide" rows="9"></textarea><label class="sf-check"><input id="sf-addressed" type="checkbox">Hinweis erledigt</label></div><button type="button" data-action="close-panel">Schließen</button></aside>
    <aside class="sf-notes-panel" aria-label="Notizenbereich" hidden><div id="sf-notes-resize" role="separator" tabindex="0" aria-label="Höhe der Referentennotizen" aria-controls="sf-notes" aria-orientation="horizontal"></div><div id="sf-note-tools"></div><div id="sf-notes" aria-label="Referentennotizen"></div></aside>
    <div class="sf-feedback"><span id="sf-save-state" class="sf-save-state" aria-live="polite" aria-atomic="true"></span><span role="status" aria-live="polite"></span><span role="alert" hidden></span></div>
    <input id="sf-image-file" type="file" accept="image/png,image/jpeg,image/webp" aria-label="Bilddatei auswählen" hidden>
    <div id="sf-menu" class="sf-menu" role="dialog" aria-label="Werkzeugoptionen" hidden><header><strong id="sf-menu-label"></strong>${tool('close-menu', 'Schließen', 'close')}</header><div id="sf-menu-body"></div></div>
    <dialog id="sf-print-dialog" aria-labelledby="sf-print-title"><h2 id="sf-print-title">Drucken/PDF</h2><label for="sf-print-mode">Inhalt</label><select id="sf-print-mode"><option value="slides">Folien</option><option value="notes">Folien mit Notizen darunter</option><option value="only-notes">Nur Notizen</option></select><label for="sf-print-range">Folien (leer = alle)</label><input id="sf-print-range" type="text" placeholder="1,3-5" inputmode="text"><p id="sf-print-error" role="alert"></p><div><button type="button" data-action="cancel-print">Abbrechen</button><button type="button" data-action="confirm-print">Drucken</button></div></dialog>`;
  return chrome;
}
