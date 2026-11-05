# SlideFactory

SlideFactory macht die gemeinsame Arbeit an individuell gestalteten
HTML-Präsentationen wiederverwendbar. Der Agent baut Folien und
Diagramme im Chat aus deinen Inhalten. Du korrigierst Details direkt in der Präsentation und speicherst
Hinweise für seine nächste Runde. Eine vollständige Offline-HTML ist der gemeinsame
Arbeitsstand und das Ergebnis.

[![CI](https://github.com/NashEQify/SlideFactory/actions/workflows/ci.yml/badge.svg)](https://github.com/NashEQify/SlideFactory/actions/workflows/ci.yml)

**Editor 1.7.0.** Was der eingebettete Editor kann:

- **Bearbeiten im Browser:** Text, Textboxen, Bilder (einfügen, ersetzen, zuschneiden),
  sechs Formen, Farben, Schriftgrößen für Mehrfachauswahl, Formatpinsel,
  Rückgängig/Wiederholen.
- **Folien verwalten:** per Maus sortieren, ausblenden, löschen; Folienlinks mit
  Rücksprung, etwa zu Backup-Folien.
- **Zusammenarbeit mit dem Agenten:** Kommentare pro Folie und Post-its als Feedback;
  beides bleibt in der gespeicherten HTML und ist für die nächste Agentenrunde lesbar.
- **Präsentieren:** Vollbild, Referentenansicht mit Notizen, Zeitplan pro Folie und Teil,
  Countdown bis Meeting-Ende.
- **Ausgeben:** Druck/PDF (Folien, Folien mit Notizen, nur Notizen) und
  `HTML speichern` als Arbeitsstand mit Notizen oder als Weitergabe ohne Notizen.
- **Kein Server, keine App:** Eine Präsentation ist eine einzige Offline-HTML; Entwürfe
  liegen bis zum Speichern im Browser.

## Sofort ausprobieren

Öffne eine vollständige Startdatei im Browser:

- [Consulting](skills/slidefactory/assets/starter.html): klare Flächen und serifenlose Typografie.
- [Editorial](skills/slidefactory/assets/starter-editorial.html): eigener Aufbau mit Serifentypografie.

Ohne Beispielinhalte: [Consulting leer](skills/slidefactory/assets/blank.html)
oder [Editorial leer](skills/slidefactory/assets/blank-editorial.html). Diese
Dateien enthalten eine leere Folie, den Editor und die Farbschemata; keine
Text-, Bild- oder Font-Assets. Sie lassen sich direkt offline öffnen.
Alle vier Basisdateien enthalten `git@griessing.com` als HTML-Author-Metadatum.

`Bearbeiten` öffnet die feste Werkzeugleiste. Text: direkt anklicken; Position:
Textbox an ihrer Fläche ziehen oder Pfeiltasten nutzen; Größe: Griffe. Während
der Texteingabe wählt Ziehen Text aus; `Esc` beendet die Texteingabe und erlaubt
wieder das Verschieben. Das Bild-plus-Symbol in der linken Einfügegruppe
fügt Bilder ein. Dort gibt es auch leere Folien, Textfelder und sechs Formen:
Rechteck, abgerundetes Rechteck, Pfeil links/rechts, Oval und Linie. Gleiche
Seitenlängen ergeben ein Quadrat. Ausgewählte Bilder lassen sich ersetzen,
zuschneiden oder über den Papierkorb löschen; der Rückgängig-Pfeil stellt sie
wieder her. `Entf` löscht ausgewählte Bilder, Textboxen, eingefügte Formen und Post-its,
ebenfalls mit Rückgängig. Während der Texteingabe löscht `Entf` nur Text;
`Esc` wechselt zurück zur Objektauswahl. `Kommentare` speichert Hinweise zur aktuellen Folie.
Schriftfamilie und Punktgröße wählst du aus Dropdowns; die beiden A-Pfeil-Buttons
ändern die Größe um jeweils 2 pt. Textfarbe, Füllung und Kante haben kleine
Farbwähler. Die Pipette nutzt die native Browserfunktion, wenn diese verfügbar ist.
Ganz links kopiert der Formatpinsel die Formatierung einmal auf ein angeklicktes
Ziel; `Esc` bricht ab. Inhalt und Position werden dabei nicht kopiert.
Das Textmarker-Symbol markiert ausgewählten Text gelb; erneutes Anwenden entfernt
die Markierung. Ohne Textauswahl wird der ausgewählte Textblock markiert.
Referentennotizen sind im Hauptfenster auch ohne Folien-Bearbeitungsmodus sofort
beschreibbar: Fett/Kursiv, pt-Dropdown und nummerierte oder einfache Listen.
Ziehe die Trennlinie über dem Notizbereich nach oben, um mehr Schreibfläche zu
erhalten; die Folie wird passend kleiner. Der Notizschalter öffnet und schließt
den Bereich. `Farbschema` bietet
Cyan/Amber und Indigo/Grün, jeweils dunkel/hell. Daneben wählst du eine eigene
Hintergrundfarbe; ein neues Farbschema setzt sie zurück. Die Vorlage wählst du im
Chat über ihren Dateipfad.

Die linke Folienübersicht lässt sich am rechten Rand verstellen und einklappen.
Ihr Schalter und Rückgängig sitzen neben SlideFactory; der Folienzähler steht
über den Miniaturen. Vollbild findest du unten rechts auf der Folie oder über `F`.
Im Vollbild verschwindet das Icon; `F` oder `Esc` beendet Vollbild. Beim Schreiben
in Textfeldern, Notizen und Kommentaren bleibt `F` ein normaler Buchstabe.
Im Bearbeitungsmodus ziehst du Miniaturen an die gewünschte Stelle; eine Linie
zeigt die Einfügeposition. Am oberen/unteren Rand scrollt die Übersicht weiter.
`Esc` oder Loslassen außerhalb bricht ab. Jeder abgeschlossene Zug lässt sich
mit einem Rückgängig-Schritt zurücknehmen. Die Verschiebepfeile entfallen;
auf einer fokussierten Miniatur verschiebt `Alt+↑/↓` per Tastatur. Das kleine
× löscht weiterhin die Folie.
Wiederholen bleibt über `Strg+Umschalt+Z` beziehungsweise `Cmd+Umschalt+Z` verfügbar.

Die Referentenansicht beginnt direkt mit aktueller und nächster Folie. Darunter
stehen die formatierten Notizen einmal zum Lesen. Timer, Play/Pause und Uhrzeit
sitzen kompakt bei der nächsten Folie; darunter stehen groß die Abweichung
vom Zeitplan (`+00:35 hinter Plan` rot, `−00:20 vor Plan` grün), die Zeit auf der
aktuellen Folie gegen ihre Sollzeit (`data-sf-duration`) und die Zeit im aktuellen
Teil gegen den Plan (`Teil B 14:05 / Plan 13:30 · Budget 40:00`). Teile markiert
`data-sf-part`, ihr Budget `data-sf-part-duration`; ohne Teile gilt das ganze
Deck. Der Plan folgt der am weitesten erreichten Folie: Zurückblättern senkt ihn
nicht, die Zeit dort zählt ehrlich als Verzug. Zeit auf Backup-Folien ohne Teil
zählt zum Teil, aus dem du hingesprungen bist. ■ stoppt und setzt alles
zurück (eine eigene Reset-Taste gibt es seit 1.3.4 nicht mehr). Unter **Ende** trägst du eine
Uhrzeit ein (z. B. Meeting-Ende); dann läuft `noch 47:12 bis 12:00` herunter, in
den letzten 10 Minuten gelb, danach rot `+03:10 über 12:00`. Der Wert bleibt pro
Deck im Browser gespeichert, nicht in der HTML; × löscht ihn. Der Timer läuft auch
dann flüssig weiter, wenn das Hauptfenster im Hintergrund liegt. Das × oben rechts oder `Esc` schließt
die Ansicht; Pfeiltasten und Bild↑/Bild↓ wechseln die Folie.

Folienlinks fügst du mit dem Ketten-Icon in der Gruppe *Einfügen* ein und wählst
die Zielfolie aus der Liste; das Fadenkreuz ändert das Ziel eines markierten Links.
Die Beschriftung ist normaler Text, Position, Löschen und Rückgängig funktionieren
wie bei Textfeldern; das Aussehen kommt aus der Vorlage. Im Bearbeitungsmodus
springt ein Link nie. In der Ansicht und im Vollbild merkt sich SlideFactory die
Ausgangsfolie: `Rücktaste` (auch in der Referentenansicht) oder der Chip unten
mittig springt zurück, Pfeiltasten blättern wie gewohnt. Backup-Folien brauchen so
keine fest verdrahteten Rücklinks. Ein Link auf eine gelöschte Folie wird beim
Bearbeiten rot gestrichelt markiert.

Gelbe Post-its halten Feedback direkt auf der Folie. Ziehe sie an ihrer Fläche,
ändere ihre Größe, schreibe per Doppelklick und lösche sie über das kleine ×.
Ein gemeinsames Icon in der oberen Leiste zeigt oder verbirgt sie auch im
Präsentationsmodus. Unten rechts auf der Folie sitzt nur das Vollbild-Icon,
das im Vollbild ausgeblendet wird.
Text und Position bleiben in der gespeicherten HTML, auch bei ausgeblendeten Zetteln.

`Drucken/PDF` oder `Strg/Cmd+P` öffnet eine kleine Auswahl: alle Folien oder Bereiche wie `1, 3-5`,
dazu **Folien**, **Folien mit Notizen darunter** oder **Nur Notizen**. Danach nutzt
du den Browserdruckdialog und gegebenenfalls „Als PDF speichern“. Bilder,
Zuschnitte, Diagramme und eingebettete Fonts bleiben enthalten. Reine Folien
nutzen 16:9-Papier (320 × 180 mm), Notizmodi A4 hochkant; lange Notizen laufen
auf Folgeseiten weiter. Der direkte Druck über das Browsermenü verwendet ebenfalls
das Folienformat, auch bei migrierten Decks mit größerem, skaliertem Innenlayout.
Für eigene Diagramme mit asynchroner Vorbereitung nutze
`Drucken/PDF` oder `Strg/Cmd+P`, damit diese Vorbereitung abgeschlossen wird.
Die HTML gibt Format und vollständige Farbausgabe vor; manuell geänderte
Einstellungen im Browserdruckdialog können diese Vorgaben überschreiben.
Bei großen Decks zeigt die Druckvorschau den Ladefortschritt und wartet bis zu
zwei Minuten auf Folienressourcen. Mit `Abbrechen` lässt sich die Vorbereitung
beenden.

`Fertig` beendet das Bearbeiten und hält den Browserentwurf. **`HTML speichern`
lädt die vollständige aktuelle Datei herunter.** Nenne diese gespeicherte Datei
im nächsten Chat. Ohne Download ist die ursprüngliche Datei auf der Festplatte
weiterhin der ältere Stand. Es ist kein laufender Server erforderlich.
Ein dauerhafter Hinweis unten zeigt ungespeicherte Änderungen, auch nach
`Fertig`, beim Folienwechsel und nach Browserwiederherstellung. Nach dem Download
steht dort „HTML-Download gestartet · Neue Datei verwenden“. Neue Eingaben
werden wieder als ungespeichert markiert; zusätzliche Arbeitsdateien sind unnötig.
`HTML speichern` fragt nach der Art: **Arbeitsstand mit
Notizen** ist die Datei für die Weiterarbeit. **Weitergabe ohne Notizen** lädt
eine Kopie ohne Referentennotizen, Kommentare und Post-its herunter, etwa zum
Verschicken mit funktionierendem Editor. Sie gilt nicht als gespeicherter
Arbeitsstand; der Hinweis auf ungespeicherte Änderungen bleibt stehen.

## Neue Präsentation im eigenen Arbeitsordner

Der Skill liegt in [`skills/slidefactory`](skills/slidefactory). Für Agenten, die
Skills aus `~/.agents/skills` laden, genügt ein Link auf diesen Ordner:

```bash
ln -s "$PWD/skills/slidefactory" ~/.agents/skills/slidefactory
```

Danach verwendest du ihn im Chat als `$slidefactory` und nennst die gewünschte
Vorlagendatei. Änderungen am Repo gelten damit auch für die verknüpfte Version.

Starte dort einen Chat und schreibe beispielsweise:

> Lies `<repo>/skills/slidefactory/SKILL.md`.
> Nutze `<repo>/skills/slidefactory/assets/starter.html`
> als Vorlage. Erstelle hier `presentation.html` für [Ziel, Publikum, Inhalte].

Der [Skill](skills/slidefactory/SKILL.md) enthält Methode, vollständige Vorlagen,
HTML-Konventionen und den Helfer für gezielte Änderungen. Ein eigenes Repo pro
Präsentation oder eine globale Skill-Installation ist nicht erforderlich. Zur
Weiterarbeit gibst du die neueste gespeicherte HTML an, statt erneut zu starten.
`<repo>` steht für deinen Klon dieses Repositorys.

Optional direkt aus der Shell (Python 3, keine Zusatzpakete):

```bash
python3 <repo>/skills/slidefactory/scripts/deck.py new --template <repo>/skills/slidefactory/assets/starter.html --output /dein/arbeitsordner/presentation.html --title 'Meine Präsentation'
python3 <repo>/skills/slidefactory/scripts/deck.py inspect /dein/arbeitsordner/presentation.html --slide intro
```

Den gemeinsamen Editor in einer bestehenden, zuletzt gespeicherten HTML
aktualisierst du gezielt in eine neue Datei:

```bash
python3 <repo>/skills/slidefactory/scripts/deck.py upgrade-editor /dein/arbeitsordner/presentation.html --output /dein/arbeitsordner/presentation-updated.html
```

Die Quelldatei bleibt erhalten. Geprüfte Ressourcenkennungen verhindern, dass
eigene Änderungen am Editor selbst überschrieben werden: unbekannte oder
veränderte Editorressourcen werden abgelehnt. Folien, eigene CSS/Skripte, Bilder,
Notizen, Kommentare und Gestaltung außerhalb dieser Ressourcen bleiben erhalten.
Die neue Datei ist wieder eine vollständige Offline-HTML.

## Das Paket weiterentwickeln

`src/editor/` ist der gemeinsame Editor; `src/designs/` hält Farbrollen und Designs,
`src/templates/` neutrale Layoutbeispiele. Eine neue Designvorlage verwendet denselben
HTML-Vertrag. Die Quelle und die fertige Ein-Datei-Vorlage sind getrennt, damit
gewöhnliche Folienänderungen keinen Build verlangen.

```bash
npm ci
npm run build
pip install -r requirements-dev.txt
python3 -m playwright install chromium
python3 -m pytest -q
```

Bei jedem Push und Pull Request prüft die [CI](.github/workflows/ci.yml), dass die
eingecheckten Startdateien dem Build aus `src/` entsprechen, und führt alle Tests
mit Chromium aus.

Der Build benötigt Node ≥18; Terser ist eine reine Entwicklungsabhängigkeit für
kompakte fertige Dateien. Ohne installierten Minifier erzeugt der Builder größere,
lesbare Dateien. Die Entwicklungstests benötigen pytest, Pillow und Playwright;
`SF_BROWSER=firefox` beziehungsweise `SF_BROWSER=webkit` wählt weitere
Testbrowser. Standard ist Chromium, dessen Pfad sich mit
`SF_CHROMIUM_EXECUTABLE` setzen lässt. Die fertigen Präsentationen brauchen diese
Werkzeuge nicht. Ein Build erzeugt neue Deck-/Revisionskennungen für die Starter.

## Architektur und Entscheidungen

- [Projektabsicht](intent.md) und [Regeln für Agenten](AGENTS.md).
- [Lösung und Architekturschaubild](docs/architecture/solution-sketch.md).
- [Paket und Benutzung](docs/architecture/package-layout.md), [Bedienung](docs/architecture/editor-experience.md).
- [Implementierungsvertrag](docs/specs/001-working-package.md), [Editor-Ausbau](docs/specs/003-editor-usability.md), [alle Specs](docs/specs/README.md).
- Entscheidungen: [lokale Änderungen und HTML als Arbeitsstand](docs/decisions/ADR-001-local-editor-transactions.md),
  [Design-Bibliothek (Vorschlag)](docs/decisions/ADR-002-design-library.md).
- [Vergleich mit Slidev, PPTist und Presenton](docs/research/2026-10-10-existing-solutions.md).

Präsentationen, Bilder, Notizen und Screenshots aus echten Projekten gehören nicht
in dieses Repository; die Tests verwenden synthetische Fixtures. Fachliche Inhalte,
Recherche und Beratungsprozess liegen außerhalb dieses Technikpakets.

## Mitmachen

Änderungen laufen über Pull Requests:

1. Einen Branch anlegen: `git switch -c <thema>`.
2. Ändern, committen und den Branch pushen: `git push -u origin <thema>`.
3. Einen Pull Request öffnen (`gh pr create` oder auf GitHub).
4. Die CI baut die Startdateien und führt alle Tests aus; gemergt wird erst bei Grün.

Bei Änderungen in `src/` vor dem Commit `npm run build` ausführen und die
erzeugten Dateien unter `skills/slidefactory/assets/` mit committen.

## Lizenz

[Apache-2.0](LICENSE).
