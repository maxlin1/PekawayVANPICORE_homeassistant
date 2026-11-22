"""VAN PI CORE: Integration für das Pekaway VAN PI CORE Board.

Aktuell enthalten: Nivellierung mit dem MPU6050 auf dem Board (oder einem
anderen Beschleunigungssensor). Weitere Board-Funktionen (Relais, Eingänge,
Tanks, 1-Wire, Victron) folgen als eigene Module in dieser Integration.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .leveling.manager import LevelingManager


@dataclass
class VanPiData:
    leveling: LevelingManager


type VanPiConfigEntry = ConfigEntry[VanPiData]


async def async_setup_entry(hass: HomeAssistant, entry: VanPiConfigEntry) -> bool:
    leveling = LevelingManager(hass, entry)
    await leveling.async_setup()
    entry.runtime_data = VanPiData(leveling=leveling)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VanPiConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.leveling.async_shutdown()
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: VanPiConfigEntry) -> None:
    """Geänderte Einstellungen live übernehmen (Nivellierung bleibt an)."""
    entry.runtime_data.leveling.apply_options()
