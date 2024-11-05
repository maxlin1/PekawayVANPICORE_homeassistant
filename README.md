# homeassistant_PekawayVANPICORE
VAN PI CORE Board Integration for Home Assistant
This custom component integrates the VAN PI CORE Board with Home Assistant, allowing you to monitor and control your van's systems through the Home Assistant interface.

Diese benutzerdefinierte Komponente integriert das VAN PI CORE Board mit Home Assistant und ermöglicht es dir, die Systeme deines Vans über die Home Assistant zu überwachen und zu steuern.

## Features

- Integriert Inputs 1-8
- Integriert Relais 1-8
- Integriert MPU6050 (Beschleunigungs- und Lagersensor für die Van Ausrichtung)
- Integriert ADS1115 (Wasserlevel)
- Integriert bis zu 5 1-Wire Sensoren (als Temperatursensoren)
- Integriert Uart 1 (RJ45)
- Integriert Uart 2 (RJ11 LIN)
- Integriert UART 4 (MPPT 75/15 Victron)
- Integriert UART 5 (SmartShunt 500A/50mV Victron)


## Configuration

Die Configuration der HACS Komponente in HomeAssistant findet ihr in der [info.md](./info.md) hier unter Installation packe ich die grund info wie Ihr Homeassistant installieren könnt.


## Installation


### Install Home Assistant ### 

SD Karte Flashen:

https://www.home-assistant.io/installation/raspberrypi#install-home-assistant-operating-system

- SD Karte in den RPI4 am PeakawayBoard einstetzen
- Strom anschließen
- Wichtig der RPI4 muss mit einem Router mit Internet verbunden sein!
- 5-10min je nach RPI 4/8GB warten

### Config Home Assistant ### 

Im Browser 'http://IP-VOM-RPI:8123/' eingeben, ist euer DNS im Router richtig konfiguriert sollte auch 'http://homeassistant.local:8123' gehen.

<img width="350" alt="Konfig Fenster Homeassistant" src="assets/377777963-13886d0d-30d3-4d62-821f-5db632fde90d.png">

Die Schritte zeige ich jetzt nicht im einzelnen sind aber selbterklärend und ihr müsst einfach Homeassistant mit Name, Passwort usw. konfigurieren.

Anschließend Sehen wir eine noch relativ leere Oberfläche.

<img width="350" alt="Erster Start Homeassistant" src="assets/377779266-6ce55e0e-9ff7-4df2-9c88-53bf6e7bb89c.png">


### Erweiterte Modus einschalten

Unten Links auf den 'Usernamen' klicken um dann den -> Erweiterten Modus einschalten.

<img width="350" alt="Erweiterter Modus" src="assets/377796060-22ff2178-28d7-4c6b-86b3-a63f1ed0face.png">


-> Neustart! Die installation ist Geschafft! 🥳

-> Nun geht es in der [info.md](./info.md) weiter


## Contributing Mitwirkung

Contributions are welcome! Please feel free to submit a Pull Request.
Mitwirken ist gerne gesehen!

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments Danksagungen

- Vielen Dank an die Home Assistant-Community für ihre hervorragende Dokumentation und Beispiele.

- Besonderer Dank gilt den Entwicklern des VAN PI CORE Board für ihre Hardware- und API-Dokumentation.

- Vielen dan an [@MikeTsenatek](https://github.com/MikeTsenatek) ohne ihn wäre ich nicht weiter gekommen. 

- Danke an [@MSchroederRobert](https://github.com/schroeder-robert) für den Austausch und weitere Ideen

- Danke an [@DerKleinePunk](https://github.com/DerKleinePunk) für seine Ideen und den Austausch

## Schluss Worte
Viel Spass mit eurem Peakaway board in Homeassistant wenn ihr spannende Projekte umgesetzt habe teilt Sie gerne mit der Comunity im [Pekaway Forum ](https://forum.pekaway.de) oder stellt einen Pullrequest so kann die Integration immer weiter wachsen.
