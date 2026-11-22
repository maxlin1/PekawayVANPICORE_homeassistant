"""VAN PI CORE: Integration für das Pekaway VAN PI CORE Board.

Aktuell enthalten: Nivellierung mit dem MPU6050 auf dem Board (oder einem
anderen Beschleunigungssensor). Weitere Board-Funktionen (Relais, Eingänge,
Tanks, 1-Wire, Victron) folgen als eigene Module in dieser Integration.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, PLATFORMS
from .leveling.manager import LevelingManager
from .modules import ModuleManager


@dataclass
class VanPiData:
    leveling: LevelingManager
    modules: ModuleManager


type VanPiConfigEntry = ConfigEntry[VanPiData]


async def async_setup_entry(hass: HomeAssistant, entry: VanPiConfigEntry) -> bool:
    _enable_reset_button(hass, entry)
    leveling = LevelingManager(hass, entry)
    await leveling.async_setup()
    modules = ModuleManager(hass, entry)
    await modules.async_setup()
    entry.runtime_data = VanPiData(leveling=leveling, modules=modules)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VanPiConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.leveling.async_shutdown()
        await entry.runtime_data.modules.async_shutdown()
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: VanPiConfigEntry) -> None:
    """Geänderte Einstellungen live übernehmen (Nivellierung bleibt an)."""
    entry.runtime_data.leveling.apply_options()
    await entry.runtime_data.modules.async_sync()


def _enable_reset_button(hass: HomeAssistant, entry: VanPiConfigEntry) -> None:
    """Bis 0.1.2 war "Kalibrierung zurücksetzen" standardmäßig deaktiviert.

    Die Registry behält dieses Flag auch nach dem Update. Nur wenn die
    Integration es gesetzt hat (nicht der Nutzer), wird es wieder aktiviert.
    """
    registry = er.async_get(hass)
    unique_id = f"{entry.entry_id}_leveling_reset_calibration"
    entity_id = registry.async_get_entity_id("button", DOMAIN, unique_id)
    if entity_id is None:
        return
    reg_entry = registry.async_get(entity_id)
    if reg_entry and reg_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION:
        registry.async_update_entity(entity_id, disabled_by=None)
