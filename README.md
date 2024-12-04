# homeassistant_PekawayVANPICORE
VAN PI CORE Board Integration for Home Assistant
This custom component integrates the VAN PI CORE Board with Home Assistant, allowing you to monitor and control your van's systems through the Home Assistant interface.

Diese benutzerdefinierte Komponente integriert das VAN PI CORE Board mit Home Assistant und ermöglicht es dir, die Systeme deines Vans über die Home Assistant zu überwachen und zu steuern.

## Disclaimer

Ich habe mein Bestes getan, um diese Komponente so zuverlässig und nützlich wie möglich zu gestalten. Bitte beachte jedoch:

- Die Nutzung dieser Komponente erfolgt auf eigenes Risiko.
- Ich kann leider keine Haftung für etwaige Schäden übernehmen, die durch die Verwendung oder Nichtverwendung entstehen könnten.
- Dies gilt für alle Arten von Schäden, sei es direkt oder indirekt.

Bei mir funktioniert die Komponente einwandfrei, und ich bin zuversichtlich, dass sie auch bei dir  laufen wird! 😊
Solltest du dennoch auf Probleme stoßen oder Fragen haben, zögere  bitte nicht, mich zu kontaktieren. Ich helfe im Rahmen meiner Möglichkeiten gerne weiter und freue mich über dein Feedback!
Eine Antwort kann jedoch auch mal mehrere Tage dauern.

## Features

- Integriert Inputs 1-8
- Integriert Relais 1-8
- Integriert MPU6050 (Beschleunigungs- und Lagersensor für die Van Ausrichtung)
- Integriert ADS1115 (Wasserlevel)
- Integriert bis zu 5 1-Wire Sensoren (als Temperatursensoren)
- Integriert UART 1 (RJ45)
- Integriert UART 2 (RJ11 LIN)
- Integriert UART 4 (MPPT 75/15 Victron)
- Integriert UART 5 (SmartShunt 500A/50mV Victron)

INFO: UART3 gibt es nicht auf dem Pin lauscht der 1-Wire Sensor!

## 1. Installation von Homeassistant

Wer noch nie Homeassistant selbst installiert hat findet in der [installHA.md](./installHA.md) die Anleitung Stand Novemner 2024.

## 2. Configuration und Installation

Die Configuration der HACS Komponente in HomeAssistant findet ihr in der [info.md](./info.md) 


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
