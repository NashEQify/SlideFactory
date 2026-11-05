# SlideFactory — Projektregeln für Agenten

Projektabsicht: [intent.md](intent.md). Benutzung: [skills/slidefactory/SKILL.md](skills/slidefactory/SKILL.md).

- LLM-geführte Erstellung und Weiterentwicklung; Mensch und Agent arbeiten sequentiell.
- Pro Präsentation eine vollständige offline nutzbare HTML je gespeichertem Stand.
  Keine Pflicht zu einem Server, einer App oder einzelnen Folien-Dateien.
- Direkte Text/Layout/Bildänderungen und folienbezogene Agentenhinweise müssen den
  HTML-Download, erneutes Öffnen und die nächste Agentenänderung überleben.
- Weiterarbeit startet mit der neuesten gespeicherten HTML. Kein Neuaufbau aus
  einer älteren Vorlage bei einer kleinen Änderung; dauerhafte Kennungen erhalten.
- `Fertig` beendet Bearbeitung; `HTML speichern` → *Arbeitsstand mit Notizen* ist
  der Dateihandoff, *Weitergabe ohne Notizen* nur eine ausgehende Kopie.
- Mehrere Designs sind gleichberechtigt. Auswahl per Dateipfad im Chat, keine
  Template-Auswahl-UI. Farben/Dark/Light sind unabhängig vom Layout.
- Gestalterische Freiheit: individueller HTML/CSS/SVG-Aufbau und neue Diagramme
  sind erlaubt. Der gemeinsame Editor gehört in alle fertigen Startdateien.
- Private Präsentationen, Inhalte, Fonts, Bilder und Screenshots gehören nicht in
  dieses Repository. Originale erhalten; abgeleitete Dateien separat ablegen.
- Kein integrierter Chat und kein paralleles Bearbeiten derselben Datei.

Wartung: `npm run build` erzeugt die eingebetteten Starter aus `src/`; die
erzeugten Dateien unter `skills/slidefactory/assets/` werden mit eingecheckt.
Tests: `python3 -m pytest` (Playwright mit Chromium).
