import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { createHash } from 'node:crypto';

const root = fileURLToPath(new URL('../', import.meta.url));
const read = (name) => readFile(path.join(root, name), 'utf8');
const json = (value) => JSON.stringify(value, null, 2).replace(/</g, '\\u003c');
const modules = [
  'notes',
  'document',
  'interaction',
  'images',
  'objects',
  'text-tools',
  'preview',
  'print',
  'presenter',
  'toolbar',
  'editor',
];
// Sources are formatted for reading; embedded CSS drops the formatting whitespace again.
// Safe while the stylesheets hold no quoted strings or url() values.
// Starter identities derive from their inputs, so an unchanged build reproduces identical files.
const stableId = (...parts) => {
  const hex = createHash('sha256').update(parts.join('\0')).digest('hex');
  const variant = ((parseInt(hex[16], 16) & 3) | 8).toString(16);
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-4${hex.slice(13, 16)}-${variant}${hex.slice(17, 20)}-${hex.slice(20, 32)}`;
};
// Overview slides state each type role's size from the design CSS itself, so they cannot drift.
const fontSize = (css, role) => {
  const rule = css.match(new RegExp(`\\.sf-slide \\.${role} \\{([^}]*)\\}`));
  const size = rule?.[1].match(/font(?:-size)?:[^;]*?(\d+)px/);
  if (!size) throw Error(`No font size for .${role} in the design CSS.`);
  return size[1];
};
const withSizes = (overview, css) =>
  overview.replace(/\{\{size:([\w-]+)\}\}/g, (_, role) => fontSize(css, role));
const compactCss = (css) =>
  css.replace(/\n\s*/g, '').replace(/ \{/g, '{').replace(/: /g, ':').trim();
const [runtimeParts, editorCss, schemesText, image] = await Promise.all([
  Promise.all(modules.map((name) => read(`src/editor/${name}.js`))),
  read('src/editor/editor.css').then(compactCss),
  read('src/designs/schemes.json'),
  read('src/designs/abstract.svg'),
]);
const readableRuntime = `(() => {\n'use strict';\n${runtimeParts.join('\n\n')}\n})();`;
let runtime = readableRuntime;
try {
  const { minify } = await import('terser');
  // Preserve function boundaries: the self-contained popup runs via toString().
  // No property mangling; module contracts and authored hooks keep their names.
  runtime = (
    await minify(readableRuntime, {
      compress: {
        inline: false,
        reduce_vars: false,
        reduce_funcs: false,
        hoist_funs: false,
        hoist_vars: false,
      },
      mangle: { reserved: ['startEditor', 'doc', 'popupRuntime'] },
      keep_fnames: /^(startEditor|popupRuntime)$/,
      format: { comments: false },
    })
  ).code;
} catch (error) {
  if (error.code !== 'ERR_MODULE_NOT_FOUND') throw error;
  console.warn('Build without minifier; npm ci enables compact ready files.');
}
if (/<\/script/i.test(runtime)) throw Error('Runtime must not contain a literal script end tag.');
const schemes = JSON.parse(schemesText);
const editorVersion = '1.7.1',
  fingerprint = (value) =>
    createHash('sha256').update(value.replace(/\r\n/g, '\n'), 'utf8').digest('hex');
const manifest = {
  schemaVersion: 1,
  editorVersion,
  cssSha256: fingerprint(editorCss),
  runtimeSha256: fingerprint(runtime),
};
const releases = JSON.parse(await read('src/editor/releases.json'));
releases[editorVersion] = {
  manifest: true,
  cssSha256: manifest.cssSha256,
  runtimeSha256: manifest.runtimeSha256,
};
const imageUrl = `data:image/svg+xml;base64,${Buffer.from(image).toString('base64')}`;
await mkdir(path.join(root, 'skills/slidefactory/assets'), { recursive: true });
await writeFile(
  path.join(root, 'skills/slidefactory/assets/editor-releases.json'),
  json({ schemaVersion: 1, current: editorVersion, releases }) + '\n',
);
for (const design of ['consulting', 'editorial']) {
  const [examples, readableCss, overviewSource] = await Promise.all([
    read(`src/templates/${design}.html`),
    read(`src/designs/${design}.css`),
    read(`src/designs/${design}-overview.html`),
  ]);
  const css = compactCss(readableCss);
  // Every starter opens with its design overview; deck.py new leaves it out of a new deck.
  const overview = withSizes(overviewSource, readableCss).trim();
  const deckOpen = '<main id="sf-deck" aria-label="Präsentation">\n';
  if (!examples.startsWith(deckOpen)) throw Error(`${design}.html must open with ${deckOpen}`);
  const layout = `${deckOpen}  ${overview}\n${examples.slice(deckOpen.length)}`;
  const slideIds = [...layout.matchAll(/data-sf-slide="([^"]+)"/g)].map((match) => match[1]);
  const metadata = {
    schemaVersion: 1,
    deckId: stableId('deck', design),
    revision: stableId('revision', design, css, editorCss, runtime, layout, schemesText),
    title: `SlideFactory · ${design === 'consulting' ? 'Consulting' : 'Editorial'}`,
    templateId: design,
    templateVersion: '1.0.0',
    colorScheme: 'cyan-dark',
    pageWidth: 1600,
    pageHeight: 900,
    notes: Object.fromEntries(slideIds.map((id) => [id, ''])),
    guidance: Object.fromEntries(slideIds.map((id) => [id, { text: '', status: 'open' }])),
  };
  const theme = `:root{${Object.entries(schemes['cyan-dark'].tokens)
    .map(([key, value]) => `--sf-${key}:${value};`)
    .join('')}}`;
  const html = `<!DOCTYPE html>\n<html lang="de"><head><meta charset="utf-8"><meta name="author" content="git@griessing.com"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${metadata.title}</title>\n<style id="sf-theme-tokens">${theme}</style>\n<style id="sf-design">${css}</style>\n<style id="sf-editor-styles">${editorCss}</style>\n</head><body class="sf-design-${design}">\n${layout.replaceAll('{{SYNTHETIC_IMAGE}}', imageUrl)}\n<script id="sf-document" type="application/json">${json(metadata)}</script>\n<script id="sf-color-schemes" type="application/json">${json(schemes)}</script>\n<script id="sf-editor-manifest" type="application/json">${json(manifest)}</script>\n<script id="sf-runtime">${runtime}</script>\n</body></html>\n`;
  const filename = design === 'consulting' ? 'consulting.html' : 'editorial.html';
  await writeFile(path.join(root, 'skills/slidefactory/assets', filename), html);
  console.log(`Built ${filename} (${Buffer.byteLength(html)} bytes)`);
  const blankDeck = `${deckOpen}  ${overview}\n  <section class="sf-slide" data-sf-slide="intro" style="width:1600px;height:900px"></section>\n</main>`;
  const blankIds = [...blankDeck.matchAll(/data-sf-slide="([^"]+)"/g)].map((match) => match[1]);
  const blankMeta = {
    ...metadata,
    deckId: stableId('deck', design, 'blank'),
    revision: stableId('revision', design, 'blank', css, editorCss, runtime, schemesText, overview),
    notes: Object.fromEntries(blankIds.map((id) => [id, ''])),
    guidance: Object.fromEntries(blankIds.map((id) => [id, { text: '', status: 'open' }])),
  };
  const blank = html
    .replace(layout.replaceAll('{{SYNTHETIC_IMAGE}}', imageUrl), blankDeck)
    .replace(json(metadata), json(blankMeta));
  const blankName = design === 'consulting' ? 'consulting-blank.html' : 'editorial-blank.html';
  await writeFile(path.join(root, 'skills/slidefactory/assets', blankName), blank);
  console.log(
    `Built ${blankName} (${Buffer.byteLength(blank)} bytes; design overview, no authored text/images/fonts)`,
  );
}
