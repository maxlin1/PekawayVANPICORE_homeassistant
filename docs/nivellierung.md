# Nivellierung (VAN PI CORE)

Die Integration **VAN PI CORE** (`custom_components/vanpi_core`) berechnet am Stellplatz, unter welche Räder wie viele Blöcke gehören, damit der Van gerade steht.

## Installation

1. Integration installieren, am einfachsten über den Marketplace (bis HA 2026.10: HACS) oder manuell, siehe [Installation](installation.md#3-integration-installieren).
2. Home Assistant neu starten.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → VAN PI CORE**. Abgefragt werden nur die Grundeinstellungen des Boards (Sensortyp der Tankeingänge).
4. Auf der Integrationsseite **„Nivellierung einrichten“** wählen und den Neigungssensor angeben:
   - **MPU6050 auf dem Board** (Standard: I2C-Bus 1, Adresse 0x69), oder
   - **andere Entitäten** mit Beschleunigung X/Y/Z, z. B. ein RuuviTag (Einheit g, mg oder m/s²).
5. Fahrzeug und Blöcke eintragen: Radstand, Spurweite, Blockhöhe (Höhe einer Keilstufe), Anzahl Stapel (wie viele Keile), Blöcke pro Stapel (Stufen je Keil), Toleranz „eben“.

Mit **Luftfederung an der Hinterachse** (z. B. Goldschmidt) den Schalter einschalten und eintragen, wie weit jede Seite maximal angehoben und abgesenkt werden kann. Die Empfehlung kombiniert dann Keile und Luftfederung und nennt z. B. „Vorne rechts: 2 Blöcke (9.0 cm), Luftfederung hinten links +1.2 cm, Luftfederung hinten rechts −0.4 cm“.

**Schlafrichtung (Kopf zeigt nach):** Ziel bleibt immer, den Van möglichst auf 0,0° zu bringen. Nur wenn das mit den vorhandenen Blöcken nicht ganz geht, wählt die Empfehlung unter allen Varianten, die höchstens 0,2° schlechter sind als die beste, eine, die den Kopf mindestens 0,2° höher legt. Fast gleiche Varianten springen so nicht hin und her. Eine deutlich schiefere Variante wird also nie wegen der Schlafrichtung empfohlen. Einstellen kann man die Seite, zu der der Kopf zeigt (z. B. „Rechts (Schiebetür)“ bei Querschläfern). Standard ist „Keine Vorgabe“.

Fahrzeug und Blöcke ändert man später über das **Zahnrad am Eintrag „Nivellierung“**. Das Zahnrad oben bei VAN PI CORE gehört zu den Grundeinstellungen des Boards.

Beispiel Fiat Ducato L3 (5,99 m): Radstand 403,5 cm, Spurweite rund 180 cm (am besten nachmessen, Mitte Reifen zu Mitte Reifen).

## Einmalige Kalibrierung

1. **Vorwärtsrichtung** festlegen (in den Einstellungen, Standard ist „Aus Fahrt-Kalibrierung“):
   - Board parallel zum Fahrzeug verbaut: die Achse wählen, die nach vorne zeigt (+X, −X, …).
   - Board schräg oder unbekannt: **„Aus Fahrt-Kalibrierung“** wählen und dann:

     > ⚠️ **Sicherheit:** Die Fahrt-Kalibrierung nur auf einer verkehrsberuhigten, geraden und freien Strecke durchführen, z. B. auf einem leeren Parkplatz (mindestens 50 m, ohne Kurven, ohne Ausparken). Alle Schritte vorher in Ruhe lesen, dann starten. Während der Fahrt nicht auf Handy oder Display schauen und die StVO beachten. Nutzung auf eigene Gefahr.

     1. Auf gerader Strecke anhalten, **„Fahrt-Kalibrierung starten“** drücken, 2 Sekunden stehen bleiben.
     2. Zügig auf etwa 15–20 km/h anfahren, dann kräftig bis zum Stillstand bremsen. Nicht lenken, nicht rückwärts.
     3. Für ein genaueres Ergebnis Schritt 2 noch ein- bis zweimal wiederholen, **ohne** zwischendurch zu beenden.
     4. Im Stand **„Fahrt-Kalibrierung beenden“** drücken. Im Status-Sensor zeigt `fahrtrichtung_entspricht` die erkannte Board-Achse.
     Eine neue Aufnahme ersetzt die alte Fahrtrichtung komplett. Die Ebene bleibt dabei erhalten.
2. Van auf **wirklich ebenen** Boden stellen (z. B. mit Wasserwaage prüfen) und **„Als eben speichern“** drücken (3 Sekunden nicht bewegen). Wichtig: Wer am schrägen Stellplatz speichert, macht diese Schräglage zur Null, alle späteren Werte sind dann falsch. Ohne Nullung nimmt die Integration an, dass das Board gerade eingebaut ist. „Als eben speichern“ kann jederzeit wiederholt werden, z. B. wenn das Board verrutscht ist. Es ändert nur die Ebene, die Fahrtrichtung bleibt. **„Kalibrierung zurücksetzen“** löscht beides.

Die Kalibrierung liegt im Home-Assistant-Speicher (`.storage`) und übersteht Updates und Neustarts.

## Am Stellplatz

1. Schalter **„Nivellierung Aktiv“** einschalten.
2. Ablesen: **Blockempfehlung**, z. B. „Hinten links: 3 Blöcke (6.3 cm), Vorne links: 1 Block (2.1 cm)“.
3. Blöcke unterlegen, draufrollen. Die Werte aktualisieren sich live, **„Eben“** geht nach 2 Sekunden Ruhe auf „an“.
4. Ausschalten, oder es schaltet nach der eingestellten Zeit automatisch ab (nach 15 Minuten). Die Uhrzeit steht im Status-Sensor unter `automatisch_aus_um`. Einstellungen ändern schaltet die Nivellierung nicht mehr aus.

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
| `sensor.nivellierung_restneigung` | verbleibende Gesamtneigung nach dem Blockplan (längs und quer zusammen). Attribut `restneigung_text` nennt die Richtung, z. B. „vorne 0,9° tiefer, rechts 0,4° tiefer (Kopf 0,4° tiefer)“ |
| `binary_sensor.nivellierung_eben` | an = eben (innerhalb der Toleranz) |
| `button.nivellierung_als_eben_speichern` | Nullung |
| `button.nivellierung_fahrt_kalibrierung_*` | starten, beenden, abbrechen |
| `sensor.nivellierung_status` | Status und Kalibrier-Infos, u. a. `fahrtrichtung_entspricht` (welche Board-Achse die Fahrt-Kalibrierung ergeben hat) |

Die genauen Entity-IDs hängen von der Sprache bei der Einrichtung ab.

## Berechnung

- **Achsen:** Aus „oben“ (Nullung) und der Vorwärtsrichtung entsteht ein rechtshändiges Achsensystem. Jede Einbaulage funktioniert, Vorzeichen-Helfer sind nicht nötig.
- **Glättung:** 20 Messungen pro Sekunde, Median über 5 Werte gegen Ausreißer, dann ein ruhiger Mittelwert (1,5 s). Bei echter Lageänderung über 0,5° wird sofort nachgezogen, deshalb reagiert die Anzeige beim Draufrollen nach etwa einer halben Sekunde. An Home Assistant gehen höchstens 2 Werte pro Sekunde und nur bei Änderung ab 0,1°.
- **Hubhöhe:** bezogen auf das höchste Rad, mit vollem Radstand und voller Spurweite.
- **Blockplan:** alle Kombinationen aus bis zu „Anzahl Stapel“ Rädern mit 0 bis „Blöcke pro Stapel“ Blöcken. Gewählt wird die kleinste Restneigung (Ausgleichsebene durch die vier Radpunkte), bei Gleichstand die Variante mit weniger Blöcken.

Federung, Reifen und Untergrund werden nicht modelliert. Die Live-Anzeige nach dem Draufrollen zeigt das echte Ergebnis.

## Dashboard

Die Integration bringt eine runde Wasserwaage mit, ohne dass eine Ressource eingetragen werden muss:

```yaml
type: custom:vanpi-level-card
entity_pitch: sensor.nivellierung_neigung_langs
entity_roll: sensor.nivellierung_neigung_quer
tolerance: 1.5   # grüner Kreis
max_angle: 5     # Rand der Libelle
```

Wie bei einer echten Libelle wandert die Blase zur höheren Seite. Oben ist vorne, rechts ist rechts in Fahrtrichtung. Neigung längs ist positiv, wenn vorne höher ist, quer positiv, wenn rechts höher ist.

Dazu die Draufsicht mit Blöcken, fehlender Höhe und Luftfederung je Rad:

```yaml
type: custom:vanpi-van-card
entity: sensor.nivellierung_blockempfehlung
image: /local/van_top.png   # optional
```

Ohne `image` zeichnet die Karte einen schlichten Van. Für ein eigenes Foto ein Bild des eigenen Fahrzeugs von oben (Front zeigt nach oben, möglichst freigestellt, PNG) per Studio Code Server, Samba oder File Editor unter `/config/www/` ablegen, z. B. `/config/www/van_top.png`, und in der Karte als `/local/van_top.png` angeben. Nach dem ersten Anlegen von `/config/www` Home Assistant einmal neu starten.

Ein vollständiges Beispiel-Dashboard steht unter [beispiele/dashboard-nivellierung.yaml](beispiele/dashboard-nivellierung.yaml). Den Umstieg von RuuviTag-Vorlagen oder anderen Nivellier-Lösungen beschreibt [migration.md](migration.md).
