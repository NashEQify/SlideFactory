import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { randomUUID, createHash } from 'node:crypto';

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
  const [layout, css] = await Promise.all([
    read(`src/templates/${design}.html`),
    read(`src/designs/${design}.css`).then(compactCss),
  ]);
  const slideIds = [...layout.matchAll(/data-sf-slide="([^"]+)"/g)].map((match) => match[1]);
  const metadata = {
    schemaVersion: 1,
    deckId: randomUUID(),
    revision: randomUUID(),
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
  const filename = design === 'consulting' ? 'starter.html' : 'starter-editorial.html';
  await writeFile(path.join(root, 'skills/slidefactory/assets', filename), html);
  console.log(`Built ${filename} (${Buffer.byteLength(html)} bytes)`);
  const blankMeta = {
    ...metadata,
    deckId: randomUUID(),
    revision: randomUUID(),
    notes: { intro: '' },
    guidance: { intro: { text: '', status: 'open' } },
  };
  const blankDeck =
    '<main id="sf-deck"><section class="sf-slide" data-sf-slide="intro" style="width:1600px;height:900px"></section></main>';
  const blank = html
    .replace(layout.replaceAll('{{SYNTHETIC_IMAGE}}', imageUrl), blankDeck)
    .replace(json(metadata), json(blankMeta));
  const blankName = design === 'consulting' ? 'blank.html' : 'blank-editorial.html';
  await writeFile(path.join(root, 'skills/slidefactory/assets', blankName), blank);
  console.log(
    `Built ${blankName} (${Buffer.byteLength(blank)} bytes; no authored text/images/fonts)`,
  );
}
