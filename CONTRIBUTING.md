# Mitmachen

Beiträge sind willkommen: Fehlermeldungen, Doku-Verbesserungen und Pull Requests.

## Fehler melden

Bitte die Vorlage unter [Issues](https://github.com/maxlin1/PekawayVANPICORE_homeassistant/issues/new/choose)
nutzen und Versionen sowie einen Protokollauszug angeben. Keine persönlichen Daten (IP-Adressen, Standorte, Tokens)
posten.

## Code beitragen

- Alles, was die Integration zum Laufen braucht, liegt in `custom_components/vanpi_core/`.
- Tests: `pip install pytest-homeassistant-custom-component`, dann `pytest` im Repository-Wurzelverzeichnis.
- Vor einem Pull Request müssen die GitHub Actions (hassfest, HACS-Validierung) grün sein.
- Benutzertexte gibt es auf Deutsch und Englisch: `strings.json`, `translations/de.json`, `translations/en.json`
  gemeinsam ändern.
- In Tests, Doku und Beispielen nur Beispielwerte verwenden, keine eigenen Entity-IDs, Namen oder Fahrzeugdaten.

Mit dem Einreichen eines Beitrags stimmst du zu, dass er unter der [MIT-Lizenz](LICENSE) des Projekts veröffentlicht
wird.
