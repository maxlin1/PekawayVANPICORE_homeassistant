# VAN PI CORE für Home Assistant

[![Marketplace / HACS: Custom Repository](https://img.shields.io/badge/Marketplace%20%2F%20HACS-Custom%20Repository-41BDF5.svg)](https://github.com/maxlin1/PekawayVANPICORE_homeassistant#installation)
[![Release](https://img.shields.io/github/v/release/maxlin1/PekawayVANPICORE_homeassistant?include_prereleases&label=Release)](https://github.com/maxlin1/PekawayVANPICORE_homeassistant/releases)
[![Lizenz: MIT](https://img.shields.io/github/license/maxlin1/PekawayVANPICORE_homeassistant?label=Lizenz)](LICENSE)
[![Home Assistant ab 2026.2](https://img.shields.io/badge/Home%20Assistant-2026.2%2B-18BCF2.svg?logo=homeassistant&logoColor=white)](https://www.home-assistant.io)
[![hassfest](https://github.com/maxlin1/PekawayVANPICORE_homeassistant/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/maxlin1/PekawayVANPICORE_homeassistant/actions/workflows/hassfest.yaml)
[![HACS-Validierung](https://github.com/maxlin1/PekawayVANPICORE_homeassistant/actions/workflows/hacs.yaml/badge.svg)](https://github.com/maxlin1/PekawayVANPICORE_homeassistant/actions/workflows/hacs.yaml)

> ⚠️ **Privates Community-Projekt, Nutzung auf eigene Gefahr.** Bitte vor der Nutzung den
> [Haftungsausschluss und die Sicherheitshinweise](#haftungsausschluss-und-sicherheitshinweise) lesen.

Integration für das **[Pekaway VAN PI CORE](https://www.pekaway.de)** mit einem Raspberry Pi 4 und
Home Assistant OS. Relais, Eingänge, Tanks, Temperaturfühler, Victron-Geräte und eine Nivellierungshilfe für den Van,
komplett in der Oberfläche einzurichten.

*English: Home Assistant integration for the Pekaway VAN PI CORE board (relays, inputs, tank sensors, 1-Wire,
Victron VE.Direct, van leveling). Set up entirely in the UI. The documentation is in German; the integration
ships English and German translations.*

<img width="400" alt="VAN PI CORE" src="assets/preview.png">

## Funktionen

| Funktion | Hardware auf dem Board | Ergebnis in Home Assistant |
|---|---|---|
| **Relais & Eingänge** | MCP23017 (I2C `0x20`) | 8 Schalter, 8 Binärsensoren |
| **Tanks** | ADS1115, 4 Eingänge, Pull-up je Kanalpaar umschaltbar | Füllstand (L oder %) mit eigener Kennlinie, Spannung, Widerstand |
| **Temperatur** | 1-Wire (DS18B20 u. ä.) | ein Sensor je Fühler, automatisch gefunden |
| **Victron VE.Direct** | UART4, UART5 (oder jeder andere Port) | alle Werte von MPPT und SmartShunt/BMV, Energie-Dashboard-tauglich |
| **Nivellierung** | MPU6050 auf dem Board oder beliebiger X/Y/Z-Sensor (z. B. RuuviTag) | Neigung, Blockempfehlung je Rad, optional Luftfederung, Wasserwaage und Draufsicht als Dashboard-Karten |

Jede Funktion ist ein eigener Eintrag unter dem Hauptgerät *VAN PI CORE* und kann einzeln hinzugefügt, geändert
oder entfernt werden.

## Installation

Kurzfassung, die ausführliche Anleitung steht in [docs/installation.md](docs/installation.md):

1. **Home Assistant OS** mit dem Raspberry Pi Imager auf die SD-Karte schreiben.
2. **Board-Schnittstellen freischalten:** ein paar Zeilen in die `config.txt` und den I2C-Treiber `i2c-dev`
   aktivieren, per SSH-Entwicklerzugang oder direkt auf der SD-Karte. Danach zweimal neu starten.
3. **Integration installieren** über den Marketplace (*Einstellungen → Marketplace → Über Link hinzufügen*,
   bis HA 2026.10 über HACS) oder manuell.
4. **Einrichten:** *Einstellungen → Geräte & Dienste → Integration hinzufügen → VAN PI CORE*, danach die
   gewünschten Funktionen hinzufügen.

## Dokumentation

| | |
|---|---|
| [Installation](docs/installation.md) | Home Assistant OS auf dem RPi 4, I2C/UART/1-Wire freischalten, Integration installieren |
| [Einrichtung](docs/einrichtung.md) | Hauptgerät, Relais, Tanks, 1-Wire, Victron, Nivellierung, eigenes Van-Bild, Fehlersuche |
| [Module im Detail](docs/module.md) | Relais, Tanks, 1-Wire, Victron: Werte und Verhalten |
| [Nivellierung](docs/nivellierung.md) | Kalibrierung, Benutzung am Stellplatz, Entitäten, Dashboard-Karten |
| [Beispiel-Dashboard](docs/beispiele/dashboard-nivellierung.yaml) | fertige Ansicht für die Nivellierung |
| [Umstieg von den alten Komponenten](docs/migration.md) | von `mcp23017`, `ads_waterlevel`, `onewire_sysbus`, `victron_*`, `mpu650` |

## Voraussetzungen

- Pekaway VAN PI CORE mit Raspberry Pi 4
- Home Assistant OS, aktuelle Version (getestet mit Home Assistant 2026.2 und neuer)
- Für die Installation per Link: Marketplace (ab Home Assistant 2026.11 eingebaut) bzw. [HACS](https://hacs.xyz) bei
  älteren Versionen

## Alte Komponenten

Bis Version 1.x bestand dieses Repository aus sechs einzelnen Komponenten mit YAML-Konfiguration. Sie sind
nicht mehr im Hauptzweig enthalten. Ihr letzter Stand ist im Branch [`alte-komponenten-v1`](https://github.com/maxlin1/PekawayVANPICORE_homeassistant/tree/alte-komponenten-v1) gesichert und wird nicht mehr gepflegt. Wie der Umstieg geht, steht in
[docs/migration.md](docs/migration.md).

## Haftungsausschluss und Sicherheitshinweise

**Privates Projekt, ohne Gewähr.** Diese Integration ist in meiner Freizeit für meinen eigenen Van entstanden. Bei mir
funktioniert sie, getestet ist sie aber nur mit meiner Hardware und meinem Aufbau. Ob sie bei dir genauso funktioniert,
kann ich nicht zusagen.

- Die Nutzung erfolgt **auf eigene Gefahr**. Die Software wird unentgeltlich und „wie besehen“ bereitgestellt, ohne
  Gewährleistung für Funktion, Fehlerfreiheit oder Eignung für einen bestimmten Zweck (siehe auch [LICENSE](LICENSE)).
- Soweit gesetzlich zulässig, übernehme ich **keine Haftung** für Schäden an Fahrzeug, Bordelektrik, Batterien,
  angeschlossenen Geräten, Daten oder Personen, die direkt oder indirekt durch Installation oder Nutzung entstehen.
- **Arbeiten an der Bordelektrik** (12 V und erst recht 230 V) erfolgen auf eigenes Risiko. Im Zweifel eine
  Fachkraft fragen. Falsch angeschlossene Relais, Sensoren oder Batterieleitungen können Brände verursachen.
- **Keine sicherheitsrelevanten Funktionen** über Home Assistant schalten oder überwachen (z. B. Bremsen, Beleuchtung
  nach StVZO, Gaswarner, Rauchmelder, Ladegeräte ohne eigene Schutzschaltung). Home Assistant, der Raspberry Pi oder
  diese Integration können jederzeit ausfallen oder falsche Werte liefern.
- Messwerte (Tankstände, Batteriewerte, Temperaturen, Neigung) dienen nur der Information und können falsch sein.

**Im Straßenverkehr (StVO)**

- Die Fahrt-Kalibrierung der Nivellierung nur auf einer **verkehrsberuhigten, geraden Strecke** ohne andere
  Verkehrsteilnehmer durchführen, z. B. auf einem leeren Parkplatz. Kräftiges Bremsen nur, wenn niemand folgt.
- **Während der Fahrt nicht aufs Handy, Tablet oder Display schauen** und keine Einstellungen ändern. Alle Schritte
  vorher in Ruhe durchlesen. Die StVO gilt immer, insbesondere § 23 Abs. 1a (elektronische Geräte).
- Einbauten (Display, Halterungen, Kabel) so befestigen, dass sie bei einer Vollbremsung oder einem Unfall niemanden
  gefährden und die Sicht nicht einschränken.

**Beim Nivellieren**

- Die Blockempfehlung ist eine Rechenhilfe. Vor dem Auffahren auf Keile das Umfeld prüfen, langsam auffahren und eine
  zweite Person einweisen lassen, wenn möglich.
- Danach **Feststellbremse anziehen**, Gang bzw. P einlegen und die Keile bzw. Räder gegen Wegrollen sichern
  (Unterlegkeile). Nur auf tragfähigem, ebenem Untergrund nivellieren.
- **Nie unter einem Fahrzeug arbeiten, das nur auf Keilen, Auffahrrampen oder der Luftfederung steht.** Luftfederung
  nur im Stand und nach Herstellerangaben verstellen.

**Markenhinweis**

Dies ist ein unabhängiges Community-Projekt. Es steht in keiner Verbindung zu Pekaway, zu Victron Energy, zur
Open Home Foundation / Home Assistant, zu HACS oder zur Raspberry Pi Ltd. und wird von diesen weder unterstützt noch
geprüft. Alle genannten Marken- und Produktnamen gehören ihren jeweiligen Inhabern und werden nur zur Beschreibung der
Kompatibilität verwendet. Inhalte aus dem Marketplace bzw. HACS werden vom Home-Assistant-Projekt nicht getestet oder
unterstützt.

## Mitmachen und Hilfe

- Fehler und Wünsche: [GitHub Issues](https://github.com/maxlin1/PekawayVANPICORE_homeassistant/issues).
  Bitte Home-Assistant-Version, Integrationsversion und einen Auszug aus dem Protokoll (`vanpi_core`) angeben.
- Pull Requests sind willkommen, siehe [CONTRIBUTING.md](CONTRIBUTING.md).
- Änderungen je Version: [CHANGELOG.md](CHANGELOG.md).
- Austausch: [Pekaway Forum](https://forum.pekaway.de) und
  [Home Assistant Community](https://community.home-assistant.io).

Antworten können auch mal ein paar Tage dauern.

## Danksagungen

- Der Home-Assistant-Community für Dokumentation und Beispiele.
- Pekaway für das VAN PI CORE und die Hardware-Dokumentation.
- [@MikeTsenatek](https://github.com/MikeTsenatek), ohne ihn wäre das Projekt nicht so weit gekommen.
- [@schroeder-robert](https://github.com/schroeder-robert) für den Austausch und weitere Ideen.
- [@DerKleinePunk](https://github.com/DerKleinePunk) für Ideen und Austausch.
- Die alten Komponenten bauten auf [jpcornil-git/HA-mcp23017](https://github.com/jpcornil-git/HA-mcp23017) und
  [thecode/ha-onewire-sysbus](https://github.com/thecode/ha-onewire-sysbus) auf.

Viel Spaß mit dem VAN PI CORE in Home Assistant! Wenn ihr spannende Projekte umsetzt, teilt sie gern im Forum
oder per Pull Request.

## Lizenz

MIT, siehe [LICENSE](LICENSE).
