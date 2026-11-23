# Changelog

Alle nennenswerten Änderungen an diesem Projekt. Format angelehnt an
[Keep a Changelog](https://keepachangelog.com/de/1.1.0/).

## [2.0.5] - 2026-11-23

### Neu
- Einstellung „Luftfederung: max. Unterschied links/rechts“ (`air_max_diff`).

### Geändert
- Liegt die Neigung innerhalb der Toleranz, werden keine Blöcke mehr empfohlen.
- Die Fahrzeuglage-Karte (`vanpi-tilt-card`) zeigt Seiten- und Heckansicht nebeneinander.

## [2.0.4] - 2026-11-23

### Neu
- Dashboard-Karte `custom:vanpi-tilt-card`: der Van von der Seite und von hinten, gekippt um die aktuelle Neigung.

### Geändert
- Klarere Feldnamen für Radstand und Spurweite in der Einrichtung.

## [2.0.3] - 2026-11-23

### Geändert
- Keine Blockempfehlung mehr, die den Rahmen um mehr als 3 cm verwindet (z. B. 3 Blöcke unter nur einem Rad).
- Die Wasserwaage zeigt immer die Richtung an.

## [2.0.2] - 2026-11-23

### Geändert
- Bei praktisch ebenem Stand (unter 0,2°) wird die Variante mit den wenigsten Blöcken empfohlen.
- Rohwerte als Diagnose im Status der Nivellierung.

## [2.0.1] - 2026-11-22

### Korrigiert
- hassfest-Prüfung: `pyserial` nicht mehr als Abhängigkeit im Manifest (bringt Home Assistant selbst mit).
- Interne Werte der Vorwärtsrichtung heißen jetzt `pos_x`/`neg_x` usw.; gespeicherte Einstellungen werden automatisch umgestellt.
- Beschreibungstexte ohne HTML-ähnliche Platzhalter.

## [2.0.0] - 2026-11-22

Neue Integration **VAN PI CORE** (`custom_components/vanpi_core`), die alle bisherigen Einzel-Komponenten ersetzt.

### Neu
- Einrichtung komplett in der Oberfläche: Hauptgerät VAN PI CORE mit Board-Grundeinstellungen
  (Sensortyp/Pull-ups der Tankeingänge), darunter je Funktion ein eigener Eintrag.
- Relais & Eingänge (MCP23017), Tanks (ADS1115) mit frei wählbarer Kennlinie, 1-Wire-Temperaturfühler,
  Victron VE.Direct (MPPT, SmartShunt/BMV) je Port.
- Nivellierung mit MPU6050 oder beliebigem X/Y/Z-Sensor: Neigung, Blockempfehlung je Rad, optional Luftfederung,
  Fahrt-Kalibrierung, Dashboard-Karten `vanpi-level-card` (Wasserwaage) und `vanpi-van-card` (Draufsicht).
- Schlafrichtung: bei nicht ganz ausgleichbarem Gelände wird unter fast gleich guten Varianten (max. 0,2° Unterschied) die mit Kopf höher empfohlen.
- Restneigung mit Richtung als Text (Attribut `restneigung_text`), z. B. „vorne 0,9° tiefer, rechts 0,4° tiefer“.
- Neue Dokumentation: Installation, Einrichtung, Umstieg, Beispiel-Dashboard, Haftungs- und Sicherheitshinweise.
- Installation über Marketplace/HACS möglich (nur noch eine Integration im Repository).

### Korrigiert (gegenüber den alten Komponenten)
- 1-Wire: aus `onewire_sysbus` übernommene Namen bleiben nach dem Entfernen der alten Komponente erhalten.
- Victron MPPT: PV-Leistung, Ladestatus als Text, Ertrag gestern, maximale Leistung heute/gestern.
- Victron SmartShunt: Zuordnung H5-H16, Starterbatterie-Spannung in V.
- Victron allgemein: Prüfsumme je Datenblock, automatische Wiederverbindung.

### Entfernt
- Die alten Komponenten `ads_waterlevel`, `mcp23017`, `mpu650`, `onewire_sysbus`, `victron_mppt`,
  `victron_smartshunt`. Ihr letzter Stand liegt im Branch
  [`alte-komponenten-v1`](https://github.com/maxlin1/PekawayVANPICORE_homeassistant/tree/alte-komponenten-v1).
  Umstieg: [docs/migration.md](docs/migration.md).

## [1.0.0] - 2024-11-05

Erste Veröffentlichung mit den Einzel-Komponenten (YAML-Konfiguration): Relais und Eingänge (MCP23017), Wasserstand
(ADS1115), MPU6050, 1-Wire, Victron MPPT und SmartShunt.

[2.0.5]: https://github.com/maxlin1/PekawayVANPICORE_homeassistant/releases/tag/2.0.5
[2.0.4]: https://github.com/maxlin1/PekawayVANPICORE_homeassistant/releases/tag/2.0.4
[1.0.0]: https://github.com/maxlin1/PekawayVANPICORE_homeassistant/releases/tag/V1.0.0
