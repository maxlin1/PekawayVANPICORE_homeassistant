# Alte Komponenten (nicht mehr gepflegt)

Diese Komponenten waren bis Version 1.x der Inhalt dieses Repositorys. Sie sind durch die Integration
**VAN PI CORE** (`custom_components/vanpi_core`) ersetzt und liegen hier nur noch zum Nachschlagen.

| Komponente | Ersetzt durch |
|---|---|
| `ads_waterlevel` | Tank (ADS1115) |
| `mcp23017` | Relais & Eingänge (MCP23017) |
| `mpu650` | Nivellierung |
| `onewire_sysbus` | 1-Wire-Temperatursensoren |
| `victron_mppt` | Victron VE.Direct (MPPT) |
| `victron_smartshunt` | Victron VE.Direct (SmartShunt/BMV) |

Umstieg: [docs/migration.md](../docs/migration.md).

Einige Komponenten basieren auf fremden Projekten:
[jpcornil-git/HA-mcp23017](https://github.com/jpcornil-git/HA-mcp23017) (MCP23017) und
[thecode/ha-onewire-sysbus](https://github.com/thecode/ha-onewire-sysbus) (1-Wire).
