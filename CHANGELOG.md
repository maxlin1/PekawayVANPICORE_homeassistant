# Changelog

Alle nennenswerten Änderungen an diesem Projekt. Format angelehnt an
[Keep a Changelog](https://keepachangelog.com/de/1.1.0/).

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
- Neue Dokumentation: Installation, Einrichtung, Umstieg, Beispiel-Dashboard, Haftungs- und Sicherheitshinweise.
- Installation über Marketplace/HACS möglich (nur noch eine Integration im Repository).

### Korrigiert (gegenüber den alten Komponenten)
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

[2.0.0]: https://github.com/maxlin1/PekawayVANPICORE_homeassistant/releases/tag/v2.0.0
[1.0.0]: https://github.com/maxlin1/PekawayVANPICORE_homeassistant/releases/tag/V1.0.0
