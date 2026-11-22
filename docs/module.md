# VAN PI CORE: Relais, Eingänge, Tanks, 1-Wire und Victron

Diese Board-Funktionen sind Teil der Integration **VAN PI CORE** (`vanpi_core`).
Jede Funktion wird als eigener Eintrag unter der Integration hinzugefügt und
bekommt ein eigenes Gerät:

**Einstellungen → Geräte & Dienste → VAN PI CORE → ⋮ bzw. „+“**

| Eintrag | Was entsteht | Ersetzt die alte Komponente |
|---|---|---|
| Relais & Eingänge hinzufügen | 8 Schalter (Relais), 8 Binärsensoren (Eingänge) | `mcp23017` |
| Tank hinzufügen (je Tank einmal) | Füllstand, Spannung, ggf. Widerstand | `ads_waterlevel` |
| 1-Wire hinzufügen | ein Temperatursensor je gefundenem Fühler | `onewire_sysbus` |
| Victron-Gerät hinzufügen (je Port einmal) | alle Werte von SmartShunt/BMV bzw. MPPT | `victron_smartshunt`, `victron_mppt` |

Ändern: beim Eintrag auf ⋮ → „Neu konfigurieren“. Löschen entfernt auch die Entitäten.
Die Nivellierung läuft dabei weiter.

## Relais & Eingänge (MCP23017)

- Standard für das VAN PI CORE: Adresse `0x20`, Bus 1, Eingänge invertiert, Relais nicht invertiert.
- Im zweiten Schritt vergibst du Namen. **Namen aus der alten `mcp23017`-Komponente werden vorausgefüllt.**
- „Relaiszustand beim Neustart behalten“: Relais bleiben beim HA-Neustart wie sie sind (wie `hw_sync: true`).
- Die Relaiszustände werden 10× pro Sekunde vom Chip gelesen. Schaltet die alte Komponente parallel ein Relais, zeigt die neue Integration das richtig an und überschreibt es nicht.

## Tank (ADS1115)

- Je Tank: Board-Kanal 1-4, Kennlinie, Einheit (L oder %).
- **Kennlinie** als Punkte `Spannung in Volt : Füllstand`, mit Komma getrennt.
  Beispiel 100-L-Tank: `0:0, 0.49:50, 1.6:100` heißt 0 V = 0 L, 0,49 V = 50 L,
  1,6 V = 100 L. Dazwischen wird linear gerechnet. Die aktuelle Spannung zeigt
  der Sensor „Spannung“ des Tanks. Ändern jederzeit über das Zahnrad am Tank.
- **Sensortyp der Tankeingänge:** Das Board schaltet den 47-kΩ-Pull-up immer für
  zwei Eingänge gemeinsam (GPIO19 für 1+2, GPIO16 für 3+4). Deshalb stellst du den
  Sensortyp nicht am einzelnen Tank ein, sondern am Zahnrad des Haupteintrags
  „VAN PI CORE“, je eine Auswahl für 1+2 und 3+4:
  *Spannung* (kapazitive Sonde, Stabsonde mit Platine; Pull-up aus) oder
  *Widerstandsgeber* (Schwimmer gegen Masse; Pull-up an). Voreingestellt ist
  *Spannung*. Gesetzt wird bei jedem Start von Home Assistant und sofort nach
  dem Speichern. Ein Eintrag „Tankeingänge“ aus Version 0.1.7 wird beim Update
  automatisch übernommen und entfernt.
- Jede Messung ist der Median aus 3 Einzelmessungen. Liest die alte Komponente
  gleichzeitig, werden vermischte Messungen erkannt und wiederholt.

## 1-Wire

- Findet alle Fühler unter `/sys/bus/w1/devices` (`dtoverlay=w1-gpio` in der `config.txt`).
- **Namen aus der alten `onewire_sysbus`-Komponente werden übernommen.**
- Neu angeschlossene Fühler erscheinen nach spätestens 5 Minuten automatisch.

## Victron VE.Direct (UART)

- VAN PI CORE: UART4 `/dev/ttyAMA4` = MPPT, UART5 `/dev/ttyAMA5` = SmartShunt.
- **Wichtig:** Ein Port kann nur von einem Programm gelesen werden. Vor dem Hinzufügen
  den alten YAML-Eintrag (`platform: victron_mppt` bzw. `victron_smartshunt`) für denselben
  Port auskommentieren und HA neu starten. Zurück geht es genauso.
- Jeder Datenblock wird per Prüfsumme geprüft, fehlerhafte Blöcke werden verworfen.
  Nach einem Fehler (Kabel ab, Port weg) verbindet sich das Modul selbst neu.
- Seit 30 s keine gültigen Daten → Werte „nicht verfügbar“, Sensor „Gerät“ zeigt „Keine Daten“.
- Korrigierte Werte gegenüber den alten Komponenten:
  - MPPT: PV-Leistung in W, Ladestatus als Text (Bulk, Absorption, Erhaltung …), H21/H23 sind
    die maximale Leistung heute/gestern in W, Ertrag gestern = H22, Fehler als Text.
  - SmartShunt: H6 = entnommene Ah gesamt, H8 = maximale Batteriespannung, H9 = Zeit seit
    Vollladung, H5 = vollständige Entladungen, H11/H12 = Unter-/Überspannungsalarme,
    H15/H16 = min./max. Spannung Starterbatterie in V (vorher in mV angezeigt).
- Gesamtertrag, geladene und entladene Energie sind für das Energie-Dashboard geeignet.

Victron-Geräte per **Bluetooth** (z. B. dein „Solar Grid“) laufen über die in Home Assistant
eingebaute Integration *Victron BLE* und brauchen hier nichts.

## Umstieg von den alten Komponenten

1. Neue Einträge hinzufügen. Relais, Eingänge, Tanks und 1-Wire können parallel zu den alten laufen.
2. Prüfen, ob die Werte stimmen.
3. Dashboards und Automationen auf die neuen Entitäten umstellen.
4. Alte Einträge löschen bzw. YAML entfernen.
