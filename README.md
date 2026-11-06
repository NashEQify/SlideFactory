# SlideFactory

SlideFactory ist ein Skill für Coding-Agenten wie Claude Code und Codex.
Der Agent baut aus deinen Inhalten eine Präsentation als eine Offline-HTML.
Du öffnest sie im Browser, bearbeitest direkt, präsentierst und speicherst.
Zur Weiterarbeit gibst du dem Agenten die neueste gespeicherte HTML.

[![CI](https://github.com/NashEQify/SlideFactory/actions/workflows/ci.yml/badge.svg)](https://github.com/NashEQify/SlideFactory/actions/workflows/ci.yml)

## Sofort ausprobieren

Öffne eine Startdatei aus deinem Klon direkt im Browser (GitHub zeigt nur den Quelltext):

- [Consulting](skills/slidefactory/assets/consulting.html): klare Flächen, serifenlose Schrift.
- [Editorial](skills/slidefactory/assets/editorial.html): eigener Aufbau, Serifenschrift.
- [Clean MBB](skills/slidefactory/assets/mbb.html): dunkler Beratungslook mit Aussagetiteln.
- Ohne Beispielinhalt: [Consulting leer](skills/slidefactory/assets/consulting-blank.html), [Editorial leer](skills/slidefactory/assets/editorial-blank.html), [Clean MBB leer](skills/slidefactory/assets/mbb-blank.html).

Was der eingebettete Editor (Version 1.8.0) kann:

- Text direkt bearbeiten, Objekte verschieben und in der Größe ändern.
- Bilder einfügen, ersetzen und zuschneiden; Formen, Textfelder und Folien einfügen.
- Schriftart, Schriftgröße, Farben, Textmarker und Format übertragen.
- Folien sortieren, ausblenden, löschen; Folienlinks mit Rücksprung, etwa zu Backup-Folien.
- Kommentare und Post-its pro Folie als Hinweise für den Agenten.
- Referentennotizen direkt unter der Folie.
- Vollbild und Referentenansicht mit Notizen, nächster Folie und Zeitplan.
- Drucken/PDF: Folien, Folien mit Notizen oder nur Notizen.
- Farbschemata dunkel/hell, unabhängig vom Layout.
- Rückgängig/Wiederholen für alle Änderungen.
- `HTML speichern` → *Arbeitsstand mit Notizen*: die Datei für die Weiterarbeit.
- `HTML speichern` → *Weitergabe ohne Notizen*: Kopie ohne Notizen, Kommentare und Post-its.
- Läuft offline, ohne Server und ohne App.
- Jede Startdatei beginnt mit Übersichtsfolien zu Schriftgrößen, Farben und Komponenten.

## Als Skill einrichten

Im Wurzelordner deines Klons, für Claude Code:

```bash
mkdir -p ~/.claude/skills && ln -s "$PWD/skills/slidefactory" ~/.claude/skills/slidefactory
```

Für Codex und andere Agenten, die `~/.agents/skills` lesen:

```bash
mkdir -p ~/.agents/skills && ln -s "$PWD/skills/slidefactory" ~/.agents/skills/slidefactory
```

Aufruf im Chat: `/slidefactory` (Claude Code) bzw. `$slidefactory` (Codex). Beispiel:

> /slidefactory Nutze `<repo>/skills/slidefactory/assets/consulting.html` als Vorlage.
> Erstelle hier `presentation.html` für [Ziel, Publikum, Inhalte].

Das Design wählst du über den Dateipfad der Startdatei; `<repo>` ist dein Klon.

Das kannst du vom Agenten verlangen:

- Ein neues Deck aus einem Design erstellen.
- Ein bestehendes Deck später ändern: Nenne die neueste gespeicherte HTML.
  Kennungen und deine direkten Änderungen bleiben erhalten.
- Den Editor in einem älteren Deck aktualisieren.
- Farben wechseln, ohne das Layout zu ändern.
- Eigene Diagramme und Folienaufbauten ergänzen.

Der Agent erledigt das nach den Anweisungen im [Skill](skills/slidefactory/SKILL.md).
Du musst selbst keine Python- oder Shell-Befehle ausführen.

## Architektur und Entscheidungen

- [Projektabsicht](intent.md) und [Regeln für Agenten](AGENTS.md).
- [Lösung und Architekturschaubild](docs/architecture/solution-sketch.md).
- [Paket und Benutzung](docs/architecture/package-layout.md), [Bedienung](docs/architecture/editor-experience.md).
- [Implementierungsvertrag](docs/specs/001-working-package.md), [Editor-Ausbau](docs/specs/003-editor-usability.md), [alle Specs](docs/specs/README.md).
- Entscheidungen: [HTML als Arbeitsstand](docs/decisions/ADR-001-local-editor-transactions.md), [Design-Bibliothek (Vorschlag)](docs/decisions/ADR-002-design-library.md).
- [Vergleich mit Slidev, PPTist und Presenton](docs/research/2026-10-10-existing-solutions.md).

Echte Präsentationen, Bilder, Notizen und Screenshots gehören nicht in dieses Repository.

## Das Paket weiterentwickeln

`src/editor/` ist der Editor, `src/designs/` hält Designs und Farbrollen, `src/templates/` Layoutbeispiele.

```bash
npm ci
npm run build
pip install -r requirements-dev.txt
python3 -m playwright install chromium
python3 -m pytest -q
```

Die [CI](.github/workflows/ci.yml) prüft, dass die Startdateien dem Build aus `src/` entsprechen, und führt alle Tests aus.
`SF_BROWSER=firefox` oder `SF_BROWSER=webkit` wählt einen anderen Testbrowser.

Bei Änderungen in `src/`: `npm run format` und `npm run build` ausführen und die
erzeugten Dateien unter `skills/slidefactory/assets/` mit committen.

## Lizenz

[Apache-2.0](LICENSE).
