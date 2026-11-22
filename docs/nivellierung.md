# Nivellierung (VAN PI CORE)

Die Integration **VAN PI CORE** (`custom_components/vanpi_core`) berechnet am Stellplatz, unter welche Räder wie viele Blöcke gehören, damit der Van gerade steht.

## Installation

1. Ordner `custom_components/vanpi_core` nach `/config/custom_components/` kopieren (später per HACS).
2. Home Assistant neu starten.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → VAN PI CORE**.
4. Neigungssensor wählen:
   - **MPU6050 auf dem Board** (Standard: I2C-Bus 1, Adresse 0x69), oder
   - **andere Entitäten** mit Beschleunigung X/Y/Z, z. B. ein RuuviTag (Einheit g, mg oder m/s²).
5. Fahrzeug und Blöcke eintragen: Radstand, Spurweite, Blockhöhe, Anzahl Stapel, Blöcke pro Stapel, Toleranz „eben“, Auto-Aus.

Alle Werte lassen sich später über **Konfigurieren** ändern, z. B. bei neuen Keilen oder anderer Einbaulage.

## Einmalige Kalibrierung

1. **Vorwärtsrichtung** festlegen (in den Einstellungen):
   - Board parallel zum Fahrzeug verbaut: die Achse wählen, die nach vorne zeigt (+X, −X, …).
   - Board schräg oder unbekannt: **„Aus Fahrt-Kalibrierung“** wählen und dann:
     1. Auf gerader Strecke anhalten, **„Fahrt-Kalibrierung starten“** drücken, 1 Sekunde stehen bleiben.
     2. Zügig auf etwa 20 km/h anfahren, dann kräftig bis zum Stillstand bremsen. Nicht lenken.
     3. **„Fahrt-Kalibrierung beenden“** drücken.
     4. Am besten 2–3 Mal wiederholen. Die letzten 3 Fahrten werden gemittelt, die Streuung steht im Status-Sensor.
2. Van auf ebenen Boden stellen und **„Als eben speichern“** drücken (3 Sekunden nicht bewegen).

Die Kalibrierung liegt im Home-Assistant-Speicher (`.storage`) und übersteht Updates und Neustarts.

## Am Stellplatz

1. Schalter **„Nivellierung Aktiv“** einschalten.
2. Ablesen: **Blockempfehlung**, z. B. „Hinten links: 3 Blöcke (6.3 cm), Vorne links: 1 Block (2.1 cm)“.
3. Blöcke unterlegen, draufrollen. Die Werte aktualisieren sich live, **„Eben“** geht nach 2 Sekunden Ruhe auf „an“.
4. Ausschalten, oder es schaltet nach der eingestellten Zeit automatisch ab.

Ist die Nivellierung aus, wird der Sensor nicht gelesen (MPU6050 im Schlafmodus) und alle Messwerte sind „nicht verfügbar“. Beim Fahren entsteht also keine Last und nichts wird aufgezeichnet.

## Entitäten

| Entität | Bedeutung |
|---|---|
| `switch.nivellierung_aktiv` | Nivellierung an/aus |
| `sensor.nivellierung_neigung_langs` | Grad, + = Front höher |
| `sensor.nivellierung_neigung_quer` | Grad, + = rechte Seite höher |
| `sensor.nivellierung_hubhohe_*` | nötige Anhebung je Rad (cm), bezogen auf das höchste Rad |
| `sensor.nivellierung_blocke_*` | empfohlene Blöcke je Rad |
| `sensor.nivellierung_blockempfehlung` | Empfehlung als Text, Details in den Attributen |
| `sensor.nivellierung_restneigung` | verbleibende Neigung nach dem Blockplan |
| `binary_sensor.nivellierung_eben` | an = eben (innerhalb der Toleranz) |
| `button.nivellierung_als_eben_speichern` | Nullung |
| `button.nivellierung_fahrt_kalibrierung_*` | starten, beenden, abbrechen |
| `sensor.nivellierung_status` | Status und Kalibrier-Infos |

Die genauen Entity-IDs hängen von der Sprache bei der Einrichtung ab.

## Berechnung

- **Achsen:** Aus „oben“ (Nullung) und der Vorwärtsrichtung entsteht ein rechtshändiges Achsensystem. Jede Einbaulage funktioniert, Vorzeichen-Helfer sind nicht nötig.
- **Glättung:** 20 Messungen pro Sekunde, Median über 5 Werte gegen Ausreißer, dann ein ruhiger Mittelwert (1,5 s). Bei echter Lageänderung über 0,5° wird sofort nachgezogen, deshalb reagiert die Anzeige beim Draufrollen nach etwa einer halben Sekunde. An Home Assistant gehen höchstens 2 Werte pro Sekunde und nur bei Änderung ab 0,1°.
- **Hubhöhe:** bezogen auf das höchste Rad, mit vollem Radstand und voller Spurweite.
- **Blockplan:** alle Kombinationen aus bis zu „Anzahl Stapel“ Rädern mit 0 bis „Blöcke pro Stapel“ Blöcken. Gewählt wird die kleinste Restneigung (Ausgleichsebene durch die vier Radpunkte), bei Gleichstand die Variante mit weniger Blöcken.

Federung, Reifen und Untergrund werden nicht modelliert. Die Live-Anzeige nach dem Draufrollen zeigt das echte Ergebnis.

## Dashboard

Die `van-tilt-level-card` funktioniert direkt mit den neuen Sensoren:

```yaml
type: custom:van-tilt-level-card
entity_pitch: sensor.nivellierung_neigung_langs
entity_roll: sensor.nivellierung_neigung_quer
tolerance: 1.5
```

In der Draufsicht (picture-elements) einfach `sensor.ruuvitag_lift_*` und die Block-Templates durch `sensor.nivellierung_hubhohe_*` und `sensor.nivellierung_blocke_*` ersetzen, `input_boolean.leveling_aktiv` durch `switch.nivellierung_aktiv` und `binary_sensor.ruuvitag_van_level` durch `binary_sensor.nivellierung_eben` (Achtung: dort ist **an = eben**).
