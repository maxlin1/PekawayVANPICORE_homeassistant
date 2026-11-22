# Installation

Diese Anleitung führt in drei Schritten von einer leeren SD-Karte zur laufenden Integration:

1. [Home Assistant OS auf den Raspberry Pi 4 bringen](#1-home-assistant-os-installieren)
2. [Board-Schnittstellen freischalten (I2C, UART, 1-Wire)](#2-board-schnittstellen-freischalten)
3. [Integration VAN PI CORE installieren](#3-integration-installieren)

Danach geht es mit der [Einrichtung in der Oberfläche](einrichtung.md) weiter.

> **Kurzfassung:** SD-Karte mit dem Raspberry Pi Imager flashen, starten, Board-Schnittstellen über die
> `config.txt` und `i2c-dev` freischalten (zweimal neu starten!), Integration per HACS installieren, unter
> *Einstellungen → Geräte & Dienste* „VAN PI CORE“ hinzufügen.

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
5. Wer [Weg B aus Schritt 2](#weg-b-direkt-auf-der-sd-karte-ohne-terminal) nutzen will, erledigt ihn jetzt,
   solange die Karte noch am PC hängt.
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
(Temperaturfühler) und mehrere UARTs (Victron VE.Direct, RJ45, LIN). Bei Home Assistant OS sind diese
Schnittstellen ab Werk aus. Zum Einschalten sind zwei Dinge nötig:

1. **Zeilen in der `config.txt`** auf der Boot-Partition (schaltet I2C, 1-Wire und die UARTs in der Hardware ein):

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

2. **Den I2C-Treiber `i2c-dev` laden**, damit `/dev/i2c-1` entsteht. Das geht bei Home Assistant OS nur über eine
   Datei `CONFIG/modules/rpi-i2c.conf` mit dem Inhalt `i2c-dev`, die beim Start importiert wird.

Dafür gibt es zwei Wege. Beide nutzen denselben Import-Mechanismus von Home Assistant OS.

### Weg A: SSH-Entwicklerzugang (bewährt)

So wurde das Board bisher freigeschaltet. Die normale SSH-App (*Terminal & SSH* bzw. *Advanced SSH & Web Terminal*)
reicht dafür **nicht**, weil sie in einem Container läuft und die Boot-Partition nicht sieht. Man braucht den
Entwicklerzugang auf Port 22222.

1. SSH-Schlüsselpaar am PC/Mac erzeugen, z. B. `ssh-keygen -t ed25519`
   ([Anleitung Windows](https://learn.microsoft.com/de-de/windows-server/administration/openssh/openssh_keymanagement),
   [Anleitung Mac](https://docs.github.com/de/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent)).
2. USB-Stick mit **FAT32** formatieren und **`CONFIG`** nennen (Großbuchstaben).
3. Auf den Stick kopieren:
   - Datei **`authorized_keys`** (ohne Endung) mit dem Inhalt des öffentlichen Schlüssels (`….pub`)
   - Ordner **`modules`** mit der Datei **`rpi-i2c.conf`**, Inhalt: `i2c-dev`
4. Stick an den Pi stecken und in der SSH-App `ha os import` ausführen (oder Home Assistant neu starten).
5. Vom PC/Mac verbinden: `ssh root@homeassistant.local -p 22222`
   (Windows mit PuTTY: privaten Schlüssel unter *Connection → SSH → Auth* angeben).
6. `vi /mnt/boot/config.txt`, die Zeilen von oben **ganz ans Ende** schreiben, speichern.
7. `reboot`. Danach noch **ein zweites Mal neu starten** (Begründung unten).
8. Zugang wieder schließen: Stick leeren (nur `modules` drauf lassen oder ganz leer), erneut `ha os import`.

### Weg B: direkt auf der SD-Karte (ohne Terminal)

Home Assistant OS liest den Ordner `CONFIG` nicht nur von einem USB-Stick, sondern auch direkt von der
Boot-Partition. Damit lässt sich alles am PC/Mac erledigen, am bequemsten direkt nach dem Flashen.

> ⚠️ Dieser Weg folgt dem Quellcode von Home Assistant OS
> ([`haos-config`](https://github.com/home-assistant/operating-system/blob/dev/buildroot-external/rootfs-overlay/usr/sbin/haos-config)),
> ist aber auf dem VAN PI CORE noch nicht von mehreren Leuten bestätigt. Rückmeldungen gern als Issue. Klappt es
> nicht, Weg A nehmen.

1. SD-Karte in den Kartenleser. Die Boot-Partition erscheint als Laufwerk **`hassos-boot`**.
   Läuft Home Assistant schon: vorher *Einstellungen → System → ⏻ → System herunterfahren*, warten, bis die grüne
   LED aus ist, Strom ab, Karte entnehmen. Bei Start von SSD die SSD per USB an den PC hängen.
2. **`config.txt`** mit einem reinen Texteditor öffnen (Windows: Editor, Mac: VS Code oder TextEdit mit
   *Format → In reinen Text umwandeln*), die Zeilen von oben **ganz ans Ende** schreiben, speichern.
3. Auf `hassos-boot` den Ordner **`CONFIG`** anlegen, darin **`modules`**, darin die Datei **`rpi-i2c.conf`** mit
   der Zeile `i2c-dev`. Ergebnis: `hassos-boot/CONFIG/modules/rpi-i2c.conf`.
4. Karte auswerfen, einsetzen, starten. Nach dem Hochfahren **ein zweites Mal neu starten**
   (*Einstellungen → System → ⏻ → Neu starten → System neu starten*).

### Warum es oft „nicht funktioniert“ (Stolperfallen)

- **Zweiter Neustart fehlt.** Home Assistant OS übernimmt `CONFIG/modules` erst spät im Startvorgang, nachdem die
  Treiber schon geladen sind. `i2c-dev` wird deshalb erst beim **nächsten** Start geladen. Direkt nach dem ersten
  Start fehlt `/dev/i2c-1` noch, obwohl alles richtig ist.
- **Der Ordner `CONFIG` verschwindet.** Das ist gewollt: Nach dem Import löscht Home Assistant OS den Ordner von der
  Boot-Partition. Die Einstellung ist dann dauerhaft gespeichert.
- **Falsche Dateiendung.** Windows blendet Endungen oft aus, aus `rpi-i2c.conf` wird unbemerkt
  `rpi-i2c.conf.txt`. Diese Datei wird ignoriert. Im Explorer *Ansicht → Dateinamenerweiterungen* einschalten.
  Ebenso muss `authorized_keys` ohne Endung sein.
- **Formatierter Text.** TextEdit auf dem Mac speichert ohne Umstellung als RTF. Dann ist die `config.txt`
  unbrauchbar.
- **USB-Stick und Boot-Ordner gleichzeitig.** Steckt ein Stick namens `CONFIG`, wird nur der Stick gelesen und der
  Ordner auf der Boot-Partition ignoriert.
- **Nicht am Ende eingetragen.** Die `config.txt` hat Abschnitte wie `[pi4]`. Neue Zeilen gehören hinter die letzte
  Zeile `[all]`, sonst gelten sie unter Umständen nur für ein bestimmtes Modell.

Updates von Home Assistant OS behalten die `config.txt` auf dem Raspberry Pi 4 bei, die Freischaltung ist also nur
einmal nötig.

### Prüfen, ob es geklappt hat

*Einstellungen → System → Hardware → ⋮ → Alle Hardware*. Dort sollten auftauchen:

- `/dev/i2c-1` (und `/dev/i2c-0`)
- `/dev/ttyAMA1`, `/dev/ttyAMA2`, `/dev/ttyAMA4`, `/dev/ttyAMA5` (die genaue Nummerierung kann je nach
  Home-Assistant-OS-Version abweichen; maßgeblich ist, was hier steht)
- unter `w1_bus_master1` die angeschlossenen 1-Wire-Fühler (`28-…`)

Fehlt nur `/dev/i2c-1`, die UARTs sind aber da: `config.txt` ist richtig, `i2c-dev` fehlt noch. Noch einmal neu
starten, sonst `rpi-i2c.conf` prüfen (Endung!) und erneut importieren.

Fehlt etwas, meldet es spätestens die Integration beim Einrichten („Kein MCP23017 gefunden. I2C aktiviert?“,
„Verzeichnis nicht gefunden. Steht dtoverlay=w1-gpio in der config.txt?“, „Schnittstelle gibt es nicht“).

<details>
<summary>Warum nicht die App „HassOS I2C Configurator“?</summary>

Die Community-App aus <https://github.com/adamoutler/HassOSConfigurator> schaltet nur **I2C** ein, nicht UART und
1-Wire. Für das VAN PI CORE reicht das nicht.

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

Nur `vanpi_core` wird gebraucht. Die alten Einzel-Komponenten gehören **nicht** mehr nach
`/config/custom_components` (siehe [Umstieg](migration.md)).

### Weiter

Integration hinzufügen und Funktionen einrichten: **[einrichtung.md](einrichtung.md)**

[![Integration hinzufügen](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=vanpi_core)
