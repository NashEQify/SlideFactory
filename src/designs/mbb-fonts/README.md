# Fonts of the Clean MBB design

The build embeds these files into `mbb.html` and `mbb-blank.html` as WOFF2 data
URLs, so a deck needs no font request. Licence: SIL Open Font License 1.1, see
[OFL.txt](OFL.txt); the subsets keep the full name table of the originals.

| File | Source |
|---|---|
| `Zain-700.woff2`, `Zain-800.woff2` | Zain 2.000, The Zain Project Authors, https://github.com/googlefonts/zain |
| `Inter-400.woff2`, `Inter-600.woff2`, `Inter-700.woff2` | Inter 4.001, The Inter Project Authors, https://github.com/rsms/inter |

Zain sets titles, numbers and badges; Inter sets all other text. The weights
cover the design CSS; other weights fall back to the nearest one.

The subsets keep Latin text: Basic Latin, Latin-1 (German umlauts, ß), typographic
quotes and dashes, bullet, ellipsis, €, ™, arrows and a few math signs. They were
made with fontTools 4.68:

```bash
pyftsubset Inter-400.ttf --flavor=woff2 --no-hinting --desubroutinize --name-IDs='*' \
  --layout-features='kern,liga,calt,tnum,case' \
  --unicodes='U+0020-007E,U+00A0-00FF,U+0152-0153,U+0160-0161,U+0178,U+017D-017E,U+2013-2014,U+2018-201A,U+201C-201E,U+2022,U+2026,U+2030,U+2039-203A,U+20AC,U+2122,U+2190-2193,U+2212,U+2264-2265,U+2248,U+2260,U+00D7'
```

The file name gives family and weight; `scripts/build-starter.mjs` derives the
`@font-face` rules from it.
