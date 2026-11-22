# Installation

Diese Anleitung führt in drei Schritten von einer leeren SD-Karte zur laufenden Integration:

1. [Home Assistant OS auf den Raspberry Pi 4 bringen](#1-home-assistant-os-installieren)
2. [Board-Schnittstellen freischalten (I2C, UART, 1-Wire)](#2-board-schnittstellen-freischalten)
3. [Integration VAN PI CORE installieren](#3-integration-installieren)

Danach geht es mit der [Einrichtung in der Oberfläche](einrichtung.md) weiter.

> **Kurzfassung für Eilige:** SD-Karte mit dem Raspberry Pi Imager flashen, **bevor** sie in den Pi kommt die
> Zeilen aus [Schritt 2](#2-board-schnittstellen-freischalten) in die `config.txt` auf der Karte schreiben, starten,
> Integration per HACS installieren, unter *Einstellungen → Geräte & Dienste* „VAN PI CORE“ hinzufügen.

---

## 1. Home Assistant OS installieren

Du brauchst:

- Raspberry Pi 4 auf dem VAN PI CORE (2 GB RAM reichen, 4 GB oder mehr sind angenehmer)
- microSD-Karte ab 32 GB (Anwendungsklasse A2 empfohlen) und einen Kartenleser am PC/Mac
- Netzwerkkabel zum Router (für die Ersteinrichtung am einfachsten), Internetzugang

Die offizielle Anleitung von Home Assistant ist immer aktuell:
<https://www.home-assistant.io/installation/raspberrypi>. Kurz zusammengefasst:

1. [Raspberry Pi Imager](https://www.raspberrypi.com/software/) auf dem PC/Mac installieren und starten.
2. **Gerät:** *Raspberry Pi 4*.
3. **Betriebssystem:** *Other specific-purpose OS → Home assistants and home automation → Home Assistant →
   Home Assistant OS (RPi 4/400)*.
4. **Speicher:** die SD-Karte wählen und schreiben lassen. Die Frage nach „OS-Anpassungen“ mit *Nein* beantworten,
   Home Assistant OS nutzt sie nicht.
5. **Karte noch nicht in den Pi stecken.** Zuerst [Schritt 2](#2-board-schnittstellen-freischalten) erledigen,
   solange die Karte am PC hängt. Das spart später jeden Terminal-Zugriff.
6. Karte in den Pi, Netzwerkkabel anschließen, Strom an. Der erste Start dauert einige Minuten.
7. Im Browser <http://homeassistant.local:8123> öffnen (klappt das nicht, die IP-Adresse des Pi im Router
   nachschauen und `http://<IP-Adresse>:8123` verwenden).
8. Den Einrichtungsassistenten durchklicken: Benutzer anlegen, Standort, Einheiten.

Empfohlen nach der Ersteinrichtung:

- **Erweiterten Modus** einschalten: unten links auf den eigenen Namen → *Erweiterter Modus*.
- Eine Möglichkeit, Dateien in `/config` abzulegen, z. B. die App **Studio Code Server** oder **File editor**
  (*Einstellungen → Apps*, in älteren Versionen *Add-ons*), alternativ die App **Samba share** für den Zugriff
  vom PC aus. Das brauchst du für die manuelle Installation und für ein eigenes Van-Bild bei der Nivellierung.

WLAN statt Kabel geht natürlich auch: *Einstellungen → System → Netzwerk*.

---

## 2. Board-Schnittstellen freischalten

Das VAN PI CORE spricht mit dem Raspberry Pi über I2C (Relais, Eingänge, Tanks, Lagesensor), 1-Wire
(Temperaturfühler) und mehrere UARTs (Victron VE.Direct, RJ45, LIN). Diese Schnittstellen sind bei
Home Assistant OS ab Werk aus und werden in der Datei `config.txt` auf der Boot-Partition eingeschaltet.

### Empfohlen: direkt auf der SD-Karte (ohne Terminal, ohne SSH)

Die Boot-Partition der SD-Karte ist FAT32 und erscheint am PC/Mac als Laufwerk **`hassos-boot`**.
Windows, macOS und Linux können sie ohne Zusatzprogramme öffnen.

1. SD-Karte in den Kartenleser stecken (bei einer frisch geflashten Karte ggf. einmal ab- und wieder anstecken).
2. Auf dem Laufwerk `hassos-boot` die Datei **`config.txt`** mit einem einfachen Texteditor öffnen
   (Windows: Editor/Notepad, Mac: TextEdit im Modus „Reiner Text“ oder VS Code).
3. **Ganz am Ende** diese Zeilen anfügen und speichern:

   ```ini
   # VAN PI CORE
   dtparam=i2c_vc=on
   dtparam=i2c_arm=on
   dtoverlay=w1-gpio
   dtoverlay=uart1
   dtoverlay=uart2
   dtoverlay=uart4
   dtoverlay=uart5
   ```

   > ℹ️ **Kein `uart3`!** Auf dessen Pin (GPIO4) liegt beim VAN PI CORE der 1-Wire-Bus.

4. Auf demselben Laufwerk einen Ordner **`CONFIG`** anlegen (Großbuchstaben), darin einen Ordner **`modules`** und
   darin eine Textdatei **`rpi-i2c.conf`** mit genau einer Zeile:

   ```text
   i2c-dev
   ```

   Ergebnis: `hassos-boot/CONFIG/modules/rpi-i2c.conf`. Achte darauf, dass der Editor keine Endung wie `.txt`
   anhängt. Home Assistant OS übernimmt die Datei beim Start und lädt damit den I2C-Treiber. Es ist normal, dass der
   Ordner `CONFIG` danach wieder verschwindet.

5. Karte auswerfen, in den Pi stecken und starten. Gerade nach Schritt 4 kann ein **zweiter Neustart** nötig sein,
   bevor `/dev/i2c-1` erscheint.

**Home Assistant läuft schon?** Dann genauso, nur vorher sauber herunterfahren:
*Einstellungen → System → ⏻ (oben rechts) → System herunterfahren*. Warten, bis die grüne LED aus ist, Strom ab,
Karte entnehmen, Schritte 1-5. Startest du von einer SSD statt von der SD-Karte, die SSD per USB an den PC hängen.

### Prüfen, ob es geklappt hat

*Einstellungen → System → Hardware → ⋮ → Alle Hardware*. Dort sollten auftauchen:

- `/dev/i2c-1` (und `/dev/i2c-0`)
- `/dev/ttyAMA1`, `/dev/ttyAMA2`, `/dev/ttyAMA4`, `/dev/ttyAMA5` (die genaue Nummerierung kann je nach
  Home-Assistant-OS-Version abweichen; maßgeblich ist, was hier steht)
- unter `w1_bus_master1` die angeschlossenen 1-Wire-Fühler (`28-…`)

Fehlt etwas, meldet es spätestens die Integration beim Einrichten („Kein MCP23017 gefunden. I2C aktiviert?“,
„Verzeichnis nicht gefunden. Steht dtoverlay=w1-gpio in der config.txt?“, „Schnittstelle gibt es nicht“).

### Alternativen (nur falls der Weg über die SD-Karte nicht geht)

<details>
<summary><b>Entwicklerzugang per SSH auf Port 22222</b> (wenn die Karte nicht entnommen werden kann)</summary>

So war es in älteren Versionen dieser Anleitung beschrieben. Es funktioniert weiterhin, ist aber deutlich aufwändiger.
Die SSH-App (*Terminal & SSH* bzw. *Advanced SSH & Web Terminal*) reicht dafür **nicht**, weil sie nur in einem
Container läuft und die Boot-Partition nicht schreiben darf.

1. SSH-Schlüsselpaar am PC/Mac erzeugen (z. B. `ssh-keygen -t ed25519`).
2. USB-Stick mit FAT32 formatieren und **`CONFIG`** nennen.
3. Auf den Stick: Datei **`authorized_keys`** (ohne Endung) mit dem Inhalt des öffentlichen Schlüssels
   (`…pub`) und, für I2C, den Ordner `modules` mit `rpi-i2c.conf` wie oben.
4. Stick an den Pi stecken und in der SSH-App `ha os import` ausführen (oder Home Assistant neu starten).
5. Vom PC: `ssh root@homeassistant.local -p 22222`, dann `vi /mnt/boot/config.txt`, die Zeilen von oben ans Ende
   schreiben, speichern, `reboot`.
6. Zugang wieder schließen: leeren `CONFIG`-Stick einstecken und erneut importieren.

</details>

<details>
<summary><b>App „HassOS I2C Configurator“</b> (Community)</summary>

Die Community-App aus <https://github.com/adamoutler/HassOSConfigurator> schaltet nur **I2C** ein, nicht UART und
1-Wire. Für das VAN PI CORE reicht das nicht, deshalb wird sie hier nicht empfohlen.

</details>

---

## 3. Integration installieren

### Variante A: HACS (empfohlen)

1. [HACS installieren](https://hacs.xyz/docs/use/download/download/), falls noch nicht vorhanden.
2. Dieses Repository in HACS öffnen:

   [![In HACS öffnen](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=maxlin1&repository=PekawayVANPICORE_homeassistant&category=integration)

   Oder von Hand: *HACS → ⋮ → Benutzerdefinierte Repositories*, URL
   `https://github.com/maxlin1/PekawayVANPICORE_homeassistant`, Typ **Integration**.
3. **VAN PI CORE** auswählen → *Herunterladen*.
4. Home Assistant neu starten (*Einstellungen → System → ⏻ → Home Assistant neu starten*).

Updates erscheinen danach automatisch unter *Einstellungen → Updates*.

### Variante B: manuell

1. Auf GitHub *Code → Download ZIP* (oder ein Release) herunterladen und entpacken.
2. Den Ordner **`custom_components/vanpi_core`** nach **`/config/custom_components/vanpi_core`** kopieren,
   z. B. per Drag & Drop in **Studio Code Server** oder über die **Samba share**. Gibt es
   `/config/custom_components` noch nicht, einfach anlegen.
3. Home Assistant neu starten.

Nur `vanpi_core` wird gebraucht. Die alten Einzel-Komponenten liegen unter `legacy/` und gehören **nicht** mehr nach
`/config/custom_components` (siehe [Umstieg](migration.md)).

### Weiter

Integration hinzufügen und Funktionen einrichten: **[einrichtung.md](einrichtung.md)**

[![Integration hinzufügen](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=vanpi_core)
