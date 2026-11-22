# Einrichtung in Home Assistant

Alles wird in der Oberfläche eingerichtet, YAML ist nicht nötig. Voraussetzung: die
[Installation](installation.md) ist erledigt und die Board-Schnittstellen sind freigeschaltet.

Der Aufbau sieht so aus:

```text
VAN PI CORE                       ← Hauptgerät: Board-Grundeinstellungen (Zahnrad)
├── Nivellierung                  ← einmal
├── Relais & Eingänge (MCP23017)  ← einmal je Chip, beim VAN PI CORE: 0x20
├── Tank (ADS1115)                ← je Tank einmal, Kanal 1-4
├── 1-Wire-Temperatursensoren     ← einmal, findet alle Fühler selbst
└── Victron VE.Direct             ← je seriellem Port einmal
```

Jede Funktion ist ein eigener Eintrag mit eigenem Gerät. Du richtest nur ein, was du wirklich angeschlossen hast.

## 1. Hauptgerät VAN PI CORE

*Einstellungen → Geräte & Dienste → Integration hinzufügen → **VAN PI CORE***

[![Integration hinzufügen](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=vanpi_core)

Abgefragt werden nur die Grundeinstellungen des Boards, die für alle Funktionen gelten: der **Sensortyp der
Tankeingänge**. Das Board schaltet den 47-kΩ-Pull-up-Widerstand immer für zwei Eingänge gemeinsam (GPIO19 für
Eingang 1 + 2, GPIO16 für 3 + 4):

| Einstellung | Wann | Pull-up |
|---|---|---|
| **Spannung** | Geber mit eigener Ausgangsspannung, z. B. kapazitive Sonde oder Stabsonde mit Widerstandsplatine | aus |
| **Widerstandsgeber** | Schwimmer- oder Hebelgeber gegen Masse | an |

Ändern jederzeit über das **Zahnrad am Eintrag „VAN PI CORE“**. Die Pull-ups werden bei jedem Start von
Home Assistant gesetzt.

## 2. Funktionen hinzufügen

Auf der Seite der Integration (*Einstellungen → Geräte & Dienste → VAN PI CORE*) gibt es für jede Funktion einen
eigenen Punkt zum Hinzufügen (je nach Home-Assistant-Version als Schaltfläche oder im Menü **⋮** am Eintrag).
Ändern lässt sich jede Funktion später über das **Zahnrad am jeweiligen Untereintrag**. Löschen entfernt auch
die zugehörigen Entitäten.

### Relais & Eingänge (MCP23017)

**„Relais & Eingänge hinzufügen“**

- Für das VAN PI CORE passen die Vorgaben: Adresse `0x20`, I2C-Bus `1`, Eingänge invertiert, Relais nicht
  invertiert. GPA0-7 sind die Eingänge 1-8, GPB0-7 die Relais 1-8.
- **Relaiszustand beim Neustart behalten:** an = Relais bleiben beim Neustart von Home Assistant, wie sie sind.
  Aus = beim Start werden alle Relais ausgeschaltet.
- Im zweiten Schritt **Namen** vergeben, z. B.:

  | Relais | Beispielname | Eingang | Beispielname |
  |---|---|---|---|
  | 1 | Wasserpumpe | 1 | Taster Eingang |
  | 2 | Licht innen | 2 | Taster Heck |
  | 3 | Außenlicht | 3 | Zündung |
  | 4 | Kühlschrank | 4 | Tür offen |

  Leer lassen ergibt „Relais n“ bzw. „Eingang n“.

Ergebnis: 8 Schalter und 8 Binärsensoren.

### Tank (ADS1115)

**„Tank hinzufügen“**, für jeden Tank einmal.

- **Board-Kanal** 1-4 und **Name**, z. B. „Frischwasser“.
- **Einheit** L oder %.
- **Kennlinie** als Punkte `Spannung in Volt : Füllstand`, mit Komma getrennt. Dazwischen wird linear gerechnet.

  | Beispiel | Kennlinie |
  |---|---|
  | Linear, 0-2,5 V = 0-100 L | `0:0, 2.5:100` |
  | Ungleichmäßiger Tank (100 L) | `0:0, 0.5:40, 1.0:70, 1.6:100` |
  | In Prozent | `0:0, 3.3:100` mit Einheit % |

  So findest du deine Kennlinie: Tank einrichten (erst mal mit `0:0, 3.3:100`), dann beim Befüllen in mehreren
  Schritten die Spannung am Sensor „… Spannung“ ablesen und notieren, wie viel im Tank ist. Die Punkte trägst du
  danach über das Zahnrad am Tank ein.

- **Faktor Spannungsteiler:** 1, wenn der Geber direkt angeschlossen ist.

Ergebnis: Füllstand, Spannung und bei Widerstandsgebern zusätzlich der Widerstand in Ω.

### 1-Wire-Temperatursensoren

**„1-Wire hinzufügen“**

Alle Fühler am Bus (DS18B20 u. ä.) werden automatisch gefunden. Neu angeschlossene Fühler erscheinen nach
spätestens 5 Minuten. Die Namen änderst du wie bei jeder Entität über das Zahnrad der Entität, z. B. in
„Temperatur Innen“ oder „Temperatur Kühlschrank“.

### Victron VE.Direct (pro Port)

**„Victron-Gerät hinzufügen“**, für jeden Port einmal.

| Board-Anschluss | Port | typisch |
|---|---|---|
| UART4 | `/dev/ttyAMA4` | Solarladeregler (MPPT) |
| UART5 | `/dev/ttyAMA5` | SmartShunt / BMV |

- **Gerätetyp** wählen (MPPT oder SmartShunt/BMV), **Name** vergeben.
- Ein Port kann nur von einem Programm gelesen werden. Läuft noch eine alte YAML-Konfiguration auf demselben Port,
  diese vorher entfernen (siehe [Umstieg](migration.md)).
- Ertrag sowie geladene und entladene Energie sind für das **Energie-Dashboard** geeignet.

Victron-Geräte per **Bluetooth** brauchen diese Integration nicht, dafür gibt es die in Home Assistant eingebaute
Integration *Victron BLE*.

Details zu allen Werten: [module.md](module.md).

### Nivellierung

**„Nivellierung einrichten“**

1. **Neigungssensor:** *MPU6050 auf dem Board* (I2C-Bus 1, Adresse `0x69`) oder drei beliebige Entitäten mit
   Beschleunigung X/Y/Z, z. B. von einem RuuviTag.
2. **Fahrzeug und Blöcke**, Beispielwerte für einen Fiat Ducato L3 (gilt so für viele Ducato-Basisfahrzeuge, am besten trotzdem nachmessen):

   | Feld | Beispiel | Hinweis |
   |---|---|---|
   | Vorwärtsrichtung des Boards | Aus Fahrt-Kalibrierung | oder die Board-Achse, die zur Front zeigt (+X, −X, …) |
   | Radstand | 403,5 cm | Mitte Vorderrad bis Mitte Hinterrad |
   | Spurweite | 180 cm | Mitte Reifen links bis Mitte Reifen rechts |
   | Höhe eines Blocks | 2,1 cm | Höhe einer Keilstufe |
   | Anzahl Stapel | 2 | wie viele Räder gleichzeitig unterlegt werden können |
   | Blöcke pro Stapel | 3 | Stufen je Keil |
   | Gilt als eben bis | 0,5° | |
   | Luftfederung an der Hinterachse | aus | an: max. Heben/Senken je Seite angeben |

3. Einmal kalibrieren (Vorwärtsrichtung und „Als eben speichern“) und am Stellplatz benutzen. Die ausführliche
   Anleitung mit allen Entitäten steht in **[nivellierung.md](nivellierung.md)**.

> ⚠️ **Sicherheit (StVO):** Die Fahrt-Kalibrierung nur auf einer verkehrsberuhigten, geraden und freien Strecke
> durchführen, z. B. auf einem leeren Parkplatz. Alle Schritte vorher in Ruhe lesen. Während der Fahrt nicht aufs
> Handy oder Display schauen und die StVO beachten. Nach dem Auffahren auf Keile Feststellbremse anziehen, gegen
> Wegrollen sichern und nie unter dem Fahrzeug arbeiten. Mehr dazu im
> [Haftungsausschluss](../README.md#haftungsausschluss-und-sicherheitshinweise).

#### Eigenes Van-Bild für die Draufsicht

Die Karte `custom:vanpi-van-card` zeigt Blöcke, fehlende Höhe und Luftfederung je Rad. Ohne Bild zeichnet sie einen
schlichten Van. Mit einem eigenen Foto sieht es so aus, wie dein Fahrzeug:

1. Bild deines Fahrzeugs **von oben** vorbereiten: Front zeigt **nach oben**, möglichst freigestellt
   (transparenter Hintergrund), PNG, etwa 400 × 800 Pixel.
2. In Home Assistant den Ordner **`/config/www`** anlegen, falls es ihn noch nicht gibt, und das Bild dort ablegen,
   z. B. als `/config/www/van_top.png` (Studio Code Server, File editor oder Samba share).
3. Wurde `/config/www` gerade neu angelegt: Home Assistant **einmal neu starten**.
4. In der Karte als **`/local/van_top.png`** angeben (`/config/www` ist im Browser `/local`).

```yaml
type: custom:vanpi-van-card
entity: sensor.nivellierung_blockempfehlung
image: /local/van_top.png   # optional
```

Die Karten der Integration (`vanpi-level-card`, `vanpi-van-card`) werden automatisch geladen, eine Ressource muss
nicht eingetragen werden.

## 3. Dashboard-Seite „Van Nivellierung“

Im Repository liegt eine fertige Dashboard-Seite:
**[beispiele/dashboard-nivellierung.yaml](beispiele/dashboard-nivellierung.yaml)**. Sie zeigt Schalter, Empfehlung
je Rad, Draufsicht, Wasserwaage, Kalibrier-Knöpfe und eine Kurzanleitung. Sie braucht nur Bordmittel von Home
Assistant und die beiden Karten dieser Integration.

**Karten:** `custom:vanpi-level-card` (Wasserwaage) und `custom:vanpi-van-card` (Draufsicht) bringt die Integration
selbst mit. Sie werden automatisch geladen. Es muss **nichts nach `/config/www` kopiert** und **keine Ressource
eingetragen** werden. Sollten die Karten nach einem Update fehlen, den Browser-Cache leeren bzw. die App neu laden.

**Seite einfügen:**

1. Die Datei [dashboard-nivellierung.yaml](beispiele/dashboard-nivellierung.yaml) auf GitHub öffnen und den Inhalt
   kopieren (Knopf *Copy raw file* oben rechts).
2. In Home Assistant das gewünschte Dashboard öffnen → ✏️ (*Dashboard bearbeiten*).
3. Neben den vorhandenen Ansichten auf **+** (*Ansicht hinzufügen*) → im Dialog **⋮ → In YAML bearbeiten**.
4. Den vorhandenen Text komplett durch den kopierten Inhalt ersetzen → **Speichern** → **Fertig**.

Ein eigenes Dashboard nur für den Van geht genauso: *Einstellungen → Dashboards → Dashboard hinzufügen → Neues
Dashboard von Grund auf*, öffnen und die Ansicht wie oben einfügen.

**Eigenes Van-Bild:** In der Seite ist `image: /local/van_top.png` eingetragen. Das Bild ablegen wie unter
[Eigenes Van-Bild für die Draufsicht](#eigenes-van-bild-für-die-draufsicht) beschrieben, oder die Zeile `image:`
löschen, dann zeichnet die Karte einen schlichten Van.

> Die Entity-IDs in der Vorlage gelten für eine Einrichtung auf Deutsch (`sensor.nivellierung_…`). Weichen sie bei
> dir ab, z. B. bei englischer Sprache (`sensor.leveling_…`), im YAML-Editor mit Suchen & Ersetzen anpassen. Die
> eigenen IDs stehen unter *Einstellungen → Geräte & Dienste → Entitäten*, Filter „VAN PI CORE“.

Die Karten einzeln in ein bestehendes Dashboard setzen: *Karte hinzufügen* → nach „VAN PI CORE“ suchen, oder als
YAML wie in [nivellierung.md](nivellierung.md#dashboard).

## Fehlersuche

| Meldung / Symptom | Ursache |
|---|---|
| „Kein MCP23017 gefunden. I2C aktiviert?“ / „Kein MPU6050 gefunden“ | I2C nicht freigeschaltet oder `rpi-i2c.conf` fehlt, siehe [Installation, Schritt 2](installation.md#2-board-schnittstellen-freischalten) |
| „Verzeichnis nicht gefunden. Steht dtoverlay=w1-gpio in der config.txt?“ | 1-Wire nicht freigeschaltet |
| „Schnittstelle gibt es nicht“ | `dtoverlay=uartN` fehlt, oder der Port heißt bei dir anders (unter *Einstellungen → System → Hardware* nachsehen) |
| Victron-Werte „nicht verfügbar“ | Seit 30 s keine gültigen Daten: Kabel, Port, oder eine alte YAML-Konfiguration liest denselben Port |
| Tankwert springt | Sensortyp (Spannung/Widerstandsgeber) am Zahnrad von VAN PI CORE prüfen |

Logs: *Einstellungen → System → Protokolle*, nach `vanpi_core` filtern. Mehr Details fürs Debugging:

```yaml
# configuration.yaml
logger:
  logs:
    custom_components.vanpi_core: debug
```
