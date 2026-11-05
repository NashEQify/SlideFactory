/* Shared codec and native editor. These functions are also serialized into the popup. */
function createNotesCodec(document) {
  const blocks = new Set(['p', 'ul', 'ol']),
    inline = new Set(['br', 'strong', 'em', 'span']);
  const normalized = (text) => text.replace(/\r\n?/g, '\n').replace(/\u00a0/g, ' ');
  const escape = (text) =>
    normalized(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  function tree(html) {
    const node = document.createElement('template');
    node.innerHTML = html;
    return node.content;
  }
  function serialize(root) {
    return [...root.childNodes]
      .map((node) => {
        if (node.nodeType === 3) return escape(node.data);
        if (node.nodeType !== 1) return '';
        const tag = node.localName;
        return `<${tag}${tag === 'span' ? ` style="font-size:${node.getAttribute('style').slice(10, -2)}pt"` : ''}>${tag === 'br' ? '' : serialize(node) + `</${tag}>`}`;
      })
      .join('');
  }
  function validTree(root, parent = 'root') {
    for (const node of root.childNodes) {
      if (node.nodeType === 3) {
        if (!['p', 'li', 'strong', 'em', 'span'].includes(parent)) return false;
        continue;
      }
      if (node.nodeType !== 1) return false;
      const tag = node.localName,
        allowed =
          parent === 'root'
            ? blocks
            : parent === 'ul' || parent === 'ol'
              ? new Set(['li'])
              : parent === 'li'
                ? new Set([...inline, 'ul', 'ol'])
                : inline;
      if (!allowed.has(tag)) return false;
      if (tag === 'span') {
        const size = node.getAttribute('style');
        if (
          node.attributes.length !== 1 ||
          !/^font-size:(?:\d+(?:\.\d+)?|\.\d+)pt$/.test(size || '')
        )
          return false;
        const points = Number(size.slice(10, -2));
        if (!Number.isFinite(points) || points < 8 || points > 72) return false;
      } else if (node.attributes.length) return false;
      if (!validTree(node, tag)) return false;
    }
    return true;
  }
  function projection(root) {
    function visit(node) {
      if (node.nodeType === 3) return normalized(node.data);
      if (node.nodeType !== 1 && node.nodeType !== 11) return '';
      if (node.localName === 'br') return '\n';
      let text = '';
      for (const child of node.childNodes) {
        if (
          node.localName === 'li' &&
          ['ul', 'ol'].includes(child.localName) &&
          text &&
          !text.endsWith('\n')
        )
          text += '\n';
        text += visit(child);
      }
      if (node.localName === 'p' || (node.localName === 'li' && !text.endsWith('\n'))) text += '\n';
      return text;
    }
    return visit(root).replace(/\n$/, '');
  }
  function sanitize(html) {
    const source = tree(html),
      out = document.createDocumentFragment(),
      paragraphs = new WeakMap();
    function paragraph(target) {
      let p = paragraphs.get(target);
      if (!p) {
        p = document.createElement('p');
        target.append(p);
        paragraphs.set(target, p);
      }
      return p;
    }
    source
      .querySelectorAll('script,style,iframe,object,embed,img,svg,math,link,meta,template')
      .forEach((node) => node.remove());
    function appendChildren(input, target, context) {
      for (const child of input.childNodes) append(child, target, context);
    }
    function append(node, target, context) {
      if (node.nodeType === 3) {
        const value = normalized(node.data);
        if (!value) return;
        if (context === 'root') {
          paragraph(target).append(document.createTextNode(value));
        } else if (context === 'list') {
          const li = document.createElement('li');
          li.textContent = value;
          target.append(li);
        } else target.append(document.createTextNode(value));
        return;
      }
      if (node.nodeType !== 1) return;
      let tag = { b: 'strong', i: 'em', div: 'p', font: 'span' }[node.localName] || node.localName;
      if (!blocks.has(tag) && !inline.has(tag) && tag !== 'li') {
        appendChildren(node, target, context);
        return;
      }
      if (context === 'inline' && (blocks.has(tag) || tag === 'li')) {
        appendChildren(node, target, 'inline');
        target.append(document.createElement('br'));
        return;
      }
      if (context === 'root' && !blocks.has(tag)) {
        append(node, paragraph(target), 'inline');
        return;
      }
      if (context === 'list' && tag !== 'li') {
        const li = document.createElement('li');
        target.append(li);
        append(node, li, 'li');
        return;
      }
      if (tag === 'p' && context === 'li') {
        appendChildren(node, target, 'inline');
        target.append(document.createElement('br'));
        return;
      }
      if (tag === 'li' && context !== 'list') {
        appendChildren(node, target, context);
        return;
      }
      if (context === 'root') paragraphs.delete(target);
      const copy = document.createElement(tag);
      if (tag === 'span') {
        const raw = node.getAttribute('style') || '',
          match = raw.match(/(?:^|;)\s*font-size\s*:\s*(\d+(?:\.\d+)?(?:pt|px))\s*(?:;|$)/);
        const size = match ? match[1] : node.style.fontSize;
        const points = /^\d+(?:\.\d+)?pt$/.test(size)
          ? Number(size.slice(0, -2))
          : /^\d+(?:\.\d+)?px$/.test(size)
            ? Number(size.slice(0, -2)) * 0.75
            : null;
        if (points === null || points < 8 || points > 72) {
          appendChildren(node, target, context);
          return;
        }
        copy.setAttribute('style', `font-size:${points}pt`);
      }
      target.append(copy);
      if (tag !== 'br')
        appendChildren(
          node,
          copy,
          tag === 'ul' || tag === 'ol' ? 'list' : tag === 'li' ? 'li' : 'inline',
        );
    }
    appendChildren(source, out, 'root');
    return { version: 1, text: projection(out), html: serialize(out) };
  }
  function validate(format) {
    if (
      !format ||
      typeof format !== 'object' ||
      Array.isArray(format) ||
      format.version !== 1 ||
      Object.keys(format).sort().join(',') !== 'html,text,version' ||
      typeof format.text !== 'string' ||
      typeof format.html !== 'string' ||
      format.text.length > 200000 ||
      format.html.length > 800000
    )
      throw Error('Ungültige formatierte Referentennotizen.');
    const root = tree(format.html);
    if (!validTree(root) || serialize(root) !== format.html || projection(root) !== format.text)
      throw Error('Ungültiges Notizformat oder abweichender Notiztext.');
    return format;
  }
  const plain = (text) => (text === '' ? '' : `<p>${escape(text).replace(/\n/g, '<br>')}</p>`);
  function current(meta, id) {
    const text = meta.notes[id] || '',
      format = meta.notesFormat?.[id];
    return format?.text === text ? format : null;
  }
  function display(meta, id) {
    const format = current(meta, id);
    if (format) return format.html;
    const text = meta.notes[id] || '',
      old = meta.notesProvenance?.[id];
    return old?.text === text ? sanitize(old.html).html : plain(text);
  }
  return {
    sanitize,
    validate,
    plain,
    current,
    display,
    projection: (html) => projection(tree(html)),
  };
}
function createNotesEditor(field, toolbar, callbacks, codec) {
  const listIcon = (ordered) =>
    `<svg width="18" height="18" viewBox="0 0 20 20" aria-hidden="true"><path d="M8 4h11M8 10h11M8 16h11" fill="none" stroke="currentColor" stroke-width="1.5"/>${ordered ? '<text x="1" y="6" fill="currentColor" font-family="sans-serif" font-size="6">1</text><text x="1" y="12" fill="currentColor" font-family="sans-serif" font-size="6">2</text><text x="1" y="18" fill="currentColor" font-family="sans-serif" font-size="6">3</text>' : '<g fill="currentColor"><circle cx="3" cy="4" r="1.3"/><circle cx="3" cy="10" r="1.3"/><circle cx="3" cy="16" r="1.3"/></g>'}</svg>`;
  const document = field.ownerDocument,
    window = document.defaultView;
  let range = null,
    composing = false,
    dirty = false,
    stored = { text: '', format: null },
    baseline = '';
  field.setAttribute('role', 'textbox');
  field.setAttribute('aria-multiline', 'true');
  field.classList.add('sf-note-input');
  toolbar.classList.add('sf-note-tools');
  toolbar.setAttribute('role', 'toolbar');
  toolbar.setAttribute('aria-label', 'Notizen formatieren');
  toolbar.innerHTML =
    '<button type="button" data-note="bold" aria-label="Notizen fett" title="Fett">B</button><button type="button" data-note="italic" aria-label="Notizen kursiv" title="Kursiv">I</button><select aria-label="Notizschriftgröße">' +
    [8, 10, 12, 14, 16, 18, 20, 24, 28, 36, 48, 72]
      .map((n) => `<option value="${n}"${n === 14 ? ' selected' : ''}>${n} pt</option>`)
      .join('') +
    '</select><button type="button" data-note="insertUnorderedList" aria-label="Aufzählung" title="Aufzählung">' +
    listIcon(false) +
    '</button><button type="button" data-note="insertOrderedList" aria-label="Nummerierte Liste" title="Nummerierte Liste">' +
    listIcon(true) +
    '</button>';
  function read() {
    if (!dirty || field.innerHTML === baseline) return stored;
    const format = codec.sanitize(field.innerHTML);
    return { text: format.text, format };
  }
  function set(text, format = null) {
    stored = { text, format };
    field.innerHTML = format?.text === text ? format.html : codec.plain(text);
    baseline = field.innerHTML;
    range = null;
    dirty = false;
  }
  // Existing owner settlement can read a field without depending on the widget implementation.
  Object.defineProperty(field, 'value', {
    get: () => read().text,
    set: (value) => {
      dirty = true;
      field.innerHTML = codec.plain(String(value));
    },
  });
  function remember() {
    const selected = window.getSelection();
    if (
      selected.rangeCount &&
      field.contains(selected.anchorNode) &&
      field.contains(selected.focusNode)
    )
      range = selected.getRangeAt(0).cloneRange();
  }
  document.addEventListener('selectionchange', remember);
  function restore() {
    field.focus();
    const selected = window.getSelection();
    if (!range || !field.contains(range.commonAncestorContainer)) {
      range = document.createRange();
      range.selectNodeContents(field);
    }
    selected.removeAllRanges();
    selected.addRange(range);
  }
  function input() {
    dirty = true;
    callbacks.input(read(), composing);
  }
  function format(command, value) {
    if (field.contentEditable !== 'true') return;
    callbacks.settle();
    callbacks.begin();
    restore();
    if (command === 'size') {
      if (range.collapsed) {
        range.selectNodeContents(field);
        const selected = window.getSelection();
        selected.removeAllRanges();
        selected.addRange(range);
      }
      document.execCommand('fontSize', false, '7');
      for (const font of field.querySelectorAll('font[size="7"]')) {
        const span = document.createElement('span');
        span.style.fontSize = `${value}pt`;
        span.append(...font.childNodes);
        font.replaceWith(span);
      }
    } else {
      document.execCommand('styleWithCSS', false, false);
      document.execCommand(command, false);
    }
    remember();
    input();
    callbacks.settle();
  }
  toolbar.addEventListener('mousedown', (event) => {
    if (event.target.closest('button')) event.preventDefault();
  });
  toolbar.addEventListener('click', (event) => {
    const button = event.target.closest('[data-note]');
    if (button) format(button.dataset.note);
  });
  toolbar
    .querySelector('select')
    .addEventListener('change', (event) => format('size', event.target.value));
  field.addEventListener('beforeinput', (event) => {
    if (['historyUndo', 'historyRedo'].includes(event.inputType)) {
      event.preventDefault();
      callbacks.history(event.inputType === 'historyRedo');
      return;
    }
    callbacks.begin();
  });
  field.addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && !event.altKey && !event.isComposing) {
      const key = event.key.toLowerCase();
      if (['z', 'y'].includes(key)) {
        event.preventDefault();
        event.stopPropagation();
        callbacks.history(key === 'y' || event.shiftKey);
      } else if (key === 'b' || key === 'i') {
        event.preventDefault();
        format(key === 'b' ? 'bold' : 'italic');
      }
    }
  });
  field.addEventListener('input', input);
  field.addEventListener('compositionstart', () => {
    composing = true;
    callbacks.begin();
  });
  field.addEventListener('compositionend', () => {
    composing = false;
    input();
    callbacks.settle();
  });
  field.addEventListener('blur', () => {
    if (!composing) callbacks.settle();
  });
  field.addEventListener('paste', (event) => {
    event.preventDefault();
    event.stopPropagation();
    callbacks.begin();
    const html = event.clipboardData.getData('text/html');
    const normalized = html
      ? codec.sanitize(html).html
      : codec.plain(event.clipboardData.getData('text/plain'));
    document.execCommand('insertHTML', false, normalized);
    input();
  });
  function editable(value) {
    field.contentEditable = String(value);
    field.setAttribute('aria-readonly', String(!value));
    for (const control of toolbar.querySelectorAll('button,select')) control.disabled = !value;
  }
  editable(true);
  return { read, set, editable };
}
