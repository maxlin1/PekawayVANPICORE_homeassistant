[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
## homeassistant_PekawayVANPICORE

Diese benutzerdefinierte Komponente integriert das VAN PI CORE Board mit Home Assistant und ermöglicht es dir, die Systeme deines Vans über die Home Assistant zu überwachen und zu steuern.


### Features

- Integriert Inputs 1-8
- Integriert Relais 1-8
- Integriert MPU6050 (Beschleunigungs- und Lagersensor für die Van Ausrichtung)
- Integriert ADS1115 (Wasserlevel)
- Integriert bis zu 5 1-Wire Sensoren (als Temperatursensoren)
- Integriert Uart 1 (RJ45)
- Integriert Uart 2 (RJ11 LIN)
- Integriert UART 4 (MPPT 75/15 Victron)
- Integriert UART 5 (SmartShunt 500A/50mV Victron)


# Installation

## 1. Vorbereitung der Integration

In der Datei mnt/boot/config.txt muss folgendes hinzugefügt werden:


```
dtparam=i2c_vc=on
dtparam=i2c_arm=on                                                   
dtoverlay=w1-gpio
dtoverlay=uart1
dtoverlay=uart2 
dtoverlay=uart4
dtoverlay=uart5
```

ℹ️ Die UART3 darf nicht angegeben werden auf diesem Pin liegt der 1-Wire Temp Sensor! 

### Dazu mpssen wir uns auf den RPI Verbinden 

#### 1. Einstellungen -> Add-ons -> ADD-On Store -> SUCHE: Advanced SSH & Web Terminal

<img width="350
" alt="Bildschirmfoto 2024-10-18 um 10 50 10" src="assets/Bildschirmfoto 2024-11-04 um 21.55.13.png">

 
ℹ️ Es gibt zwei Zugänge am Terminal:

Port 22 welcher Zugriff zum Docker Container gibt
Port 22222 welcher Zugriff direkt auf das Hauptsystem gibt. (diese brauchen wir)

- Ihr braucht einen **leeren USB-Stick** und ein **authorized_keyfile**
(SSH-Key erstellen ([Windows](https://docs.digitalocean.com/products/droplets/how-to/add-ssh-keys/create-with-putty/), [Mac](https://docs.github.com/de/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent#platform-mac)))

- Formatiere den USB-Stick mit FAT32 foratieren und benenne ihn `CONFIG` (case-sensetiv).
- Auf den USB-Stick den Public Key als Textdatei mit dem namen **authorized_keys** (keine Erweiterung) kopieren
- Den USB-Stick anschließen
- Dann über das zuvor installierte SSH Web Termilal Plugin den Befehl 
```ha os import``` eingeben.


- <img width="350
" alt="Bildschirmfoto 2024-10-18 um 10 50 10" src="assets/Bildschirmfoto 2024-11-05 um 07.14.15.png">

- HomeAssistant rebooten (USB Stick muss beim ersten Start  stecken bleiben, danach einfach wieder abziehen)

- Beim Neustarten immer über `Entwicklerwerkzeuge`-> 'Konfiguration Prüfen`-> dann 'Neu Starten' -> 'Homeassistant Neustarten'
(Das gibt die Sicherheit das alle Konfigurationen passen)

- <img width="350
" alt="Bildschirmfoto 2024-10-18 um 10 50 10" src="assets/Bildschirmfoto 2024-11-05 um 07.16.25.png">

ℹ️  Zum Deaktivieren einen leeren CONFIG benannten USB-Stick anstecken und das System neustarten, dann wird der Zugang wieder deaktiviert.


Auf den RPI via Terminal verbinden, Mac über das Terminal:
```
 ssh root@homeassistant.local -p 22222 
 ```

Windows: Über Putty (Der Private key (Endung .ppk) Key muss über Connection -> ssh -> Auth hinterlegt werden).

<img width="350
" alt="Bildschirmfoto 2024-10-18 um 10 50 10" src="assets/Bildschirmfoto 2024-11-04 um 21.38.08.png">

Die Oben angegebenen Zeilen am Ende der config.txt hinzufügen und neustarten!

````
vi /mnt/boot/config.txt
````

```
mkdir -p /mnt/boot/CONFIG/modules
echo "i2c-dev" > /mnt/boot/CONFIG/modules/rpi-i2c.conf
```

Durch die CONFIG kann es sein das ihr nach dem `reboot`nicht mehr via ssh auf den PI kommt, dann müsstet ihr den Step mit dem USB Sickt einfach wiederholen, hier muss ich mir noch was einfallen lassen. Für Tips bin ich dankbar. ggf. kann man die Config modules auch direkt mit am USB Stick anlegen. 

```
reboot
```


## 2. Installation der Integration
### Methode A: Installation über HACS (empfohlen)
* Nutze [HACS](https://hacs.xyz/) -> [Install and download anleitung ](https://hacs.xyz/docs/use/download/download/) -> Plugin schnell finden [hier](https://my.home-assistant.io/redirect/supervisor_addon/?addon=cb646a50_get&repository_url=https%3A%2F%2Fgithub.com%2Fhacs%2Faddons) klicken 

* Füge https://github.com/maxlin1/homeassistant_PekawayVANPICORE zu Ihren [benutzerdefinierten Repositories](https://hacs.xyz/docs/faq/custom_repositories/) hinzu

### Methode B: Manuelle Installation
* Klonen oder lade  dieses Repository herunter
* Verschiebe den inhalt des Ordners custom_components/ im Download in Ihren Home Assistant Konfigurationsordner
* Starten Home Assistant neu und löschen Sie den Browser-Cache (oder starten Sie den Browser neu)
  Dies ist erforderlich, damit der neue Konfigurationsassistent angezeigt wird

## 3. Einrichtung der Komponente

Fürs bearbeiten der `configuration.yml` nütze ich den `Studio Code Server` es geht aber auch der `File editor` unter  Einstellungen -> Ads-ons -> ADD-ON Store

<img width="350
" alt="Bildschirmfoto 2024-10-18 um 10 50 10" src="assets/Bildschirmfoto 2024-11-04 um 22.21.54.png">



### A. Die configuration.yaml bearbeiten
* Füge die Konfiguration wie im Beispiel unten gezeigt in Ihre configuration.yaml ein
```

sensor:
  - platform: mpu6050

  - platform: victron_component
    port: "/dev/ttyAMA4"
    baudrate: 19200
    sleeptime: 10

  - platform: smartshunt
    port: "/dev/ttyAMA5"
    baudrate: 19200
    sleeptime: 10

  - platform: ads_waterlevel
    sensors:
      - name: "Water Tank 1"
        channel: 0
        divider_ratio: 3
        measure_type: "capacitive"
        mapping_file: "/config/custom_components/ads_waterlevel/mapping_tank1.json"
      - name: "Water Tank 2"
        channel: 1
        divider_ratio: 3
        measure_type: "capacitive"
        mapping_file: "/config/custom_components/ads_waterlevel/mapping_tank2.json"
      - name: "Water Tank 3"
        channel: 2
        divider_ratio: 3
        measure_type: "capacitive"
        mapping_file: "/config/custom_components/ads_waterlevel/mapping_tank3.json"
      - name: "Water Tank 4"
        channel: 3
        divider_ratio: 3
        measure_type: "resistive"
        mapping_file: "/config/custom_components/ads_waterlevel/mapping_tank4.json"

switch:
  - platform: mpu6050

  - platform: mcp23017
    i2c_address: 0x20
    hw_sync: true
    pins:
      8: Relais_1
      9: Relais_2
      10: Relais_3
      11: Relais_4
      12: Relais_5
      13: Relais_6
      14: Relais_7
      15: Relais_8

button:
  - platform: mpu6050

binary_sensor:
  - platform: mcp23017
    i2c_address: 0x20
    invert_logic: true
    pins:
      0: Button_1
      1: Button_2
      2: Button_3
      3: Button_4
      4: Button_5
      5: Button_6
      6: Button_7
      7: Button_8

```

### Need help?
- Report bugs or issues on [GitHub](https://github.com/maxlin1/homeassistant_PekawayVANPICORE/issues)
- Ask questions in the [Home Assistant Community](https://community.home-assistant.io)



## Danke an die Entwickler folgender Komponenten, Ich habed diese mit integriert

- mcp23017: [Repository](https://github.com/jpcornil-git/HA-mcp23017) für die Relais und Eingänge
- 1-Wire: [MCP23017 component](https://github.com/thecode/ha-onewire-sysbus) für die Temperatur Sensoren
- [RPi GPIO expander](https://github.com/jpcornil-git/RPiHat_GPIO_Expander)