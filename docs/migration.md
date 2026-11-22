# Umstieg von den alten Komponenten

Bis Version 1.x bestand dieses Repository aus sechs einzelnen Komponenten, die per YAML eingerichtet wurden.
Sie sind jetzt in der Integration **VAN PI CORE** (`vanpi_core`) zusammengefasst und werden in der Oberfläche
eingerichtet. Der letzte Stand der alten Komponenten ist im Branch [`alte-komponenten-v1`](https://github.com/maxlin1/PekawayVANPICORE_homeassistant/tree/alte-komponenten-v1) gesichert. Sie werden nicht
mehr weiterentwickelt.

| Alte Komponente | Einrichtung früher | Neu in VAN PI CORE |
|---|---|---|
| `mcp23017` | YAML `switch:` / `binary_sensor:` oder Config-Flow | Relais & Eingänge (MCP23017) |
| `ads_waterlevel` | YAML `sensor: - platform: ads_waterlevel` | Tank (ADS1115), je Tank ein Eintrag; Sensortyp am Zahnrad von VAN PI CORE |
| `onewire_sysbus` | Config-Flow | 1-Wire-Temperatursensoren |
| `victron_mppt` | YAML `sensor: - platform: victron_mppt` | Victron VE.Direct, Gerätetyp MPPT |
| `victron_smartshunt` | YAML `sensor: - platform: victron_smartshunt` | Victron VE.Direct, Gerätetyp SmartShunt/BMV |
| `mpu650` (MPU6050) | YAML `sensor:` / `switch:` / `button:` | Nivellierung |

## Schritt für Schritt

1. **VAN PI CORE installieren** und das Hauptgerät hinzufügen ([Installation](installation.md),
   [Einrichtung](einrichtung.md)). Die `config.txt` bleibt, wie sie ist.
2. **Funktionen einzeln umziehen.** Relais & Eingänge, Tanks und 1-Wire können eine Weile **parallel** zu den alten
   Komponenten laufen. So lassen sich die Werte vergleichen.
   - Namen der Relais und Eingänge aus der alten `mcp23017`-Komponente werden vorausgefüllt.
   - Namen der 1-Wire-Fühler aus `onewire_sysbus` werden übernommen.
   - Tankkennlinien aus der YAML (`mapping_points`) übertragen: aus
     `- { v: 0.49, l: 50 }` wird in der Kennlinie `0.49:50`.
3. **Victron: nie parallel.** Ein serieller Port verträgt nur einen Leser. Erst den alten YAML-Block für den Port
   auskommentieren, Home Assistant neu starten, dann das Victron-Gerät hinzufügen.
4. **Dashboards und Automationen umstellen** (siehe unten).
5. **Alte Komponenten entfernen:**
   - YAML-Blöcke der alten Plattformen aus `configuration.yaml` löschen.
   - Einträge von `mcp23017` und `onewire_sysbus` unter *Einstellungen → Geräte & Dienste* löschen.
   - Die Ordner `ads_waterlevel`, `mcp23017`, `mpu650`, `onewire_sysbus`, `victron_mppt`, `victron_smartshunt`
     aus `/config/custom_components/` löschen.
   - Home Assistant neu starten.

## Entity-IDs behalten

Die neuen Entitäten haben andere IDs als die alten. Damit Automationen, Skripte und Dashboards ohne Anpassung
weiterlaufen, kannst du einer neuen Entität die alte ID geben:

1. Alte Komponente entfernen (Schritt 5), damit die alte ID frei wird. Bleibt die alte Entität als
   „nicht mehr bereitgestellt“ stehen, sie unter *Einstellungen → Geräte & Dienste → Entitäten* löschen.
2. Die neue Entität öffnen → Zahnrad → **Entitäts-ID** auf die alte ID ändern, z. B. `switch.relais_1`.

Alternativ in *Einstellungen → Automationen & Szenen* die alten IDs durch die neuen ersetzen. Home Assistant zeigt
unter *Einstellungen → Reparaturen* an, wo noch nicht vorhandene Entitäten verwendet werden.

## Geänderte Werte bei Victron

Die neuen Victron-Module rechnen einige Werte richtig, die in den alten Komponenten falsch skaliert oder vertauscht
waren (z. B. PV-Leistung, Ladestatus als Text, Ertrag gestern, Starterbatterie-Spannung in V statt mV). Verlaufsdaten
aus der alten Komponente sind deshalb nicht direkt mit den neuen vergleichbar. Details in [module.md](module.md).

## Nivellierung mit RuuviTag oder anderer Lösung

Wer bisher mit einem RuuviTag, einem Bluetooth-Neigungssensor oder einer eigenen Template-Lösung nivelliert hat:

- Die Nivellierung kann den **MPU6050 auf dem Board** nutzen oder weiterhin die **Beschleunigungs-Entitäten X/Y/Z**
  des bisherigen Sensors (Einheit g, mg oder m/s²).
- Kalibrierung (Vorwärtsrichtung, „Als eben speichern“) einmal neu machen, siehe [nivellierung.md](nivellierung.md).
- Dashboard: alte Karten durch die mitgelieferten Karten `custom:vanpi-level-card` und `custom:vanpi-van-card`
  ersetzen, Vorlage in [beispiele/dashboard-nivellierung.yaml](beispiele/dashboard-nivellierung.yaml).
  Eigene `input_boolean`-Helfer und Template-Sensoren für Blöcke oder Hubhöhe werden nicht mehr gebraucht.
- Separat installierte Lovelace-Karten (z. B. eine Wasserwaagen-Karte unter `/config/www`) und deren Einträge unter
  *Einstellungen → Dashboards → ⋮ → Ressourcen* können danach entfernt werden.
