"""Binärsensor: Fahrzeug steht eben."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VanPiConfigEntry
from .entity import LevelingEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VanPiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([LevelBinarySensor(entry.runtime_data.leveling, "level")])
    entry.runtime_data.modules.register_platform(Platform.BINARY_SENSOR, async_add_entities)


class LevelBinarySensor(LevelingEntity, BinarySensorEntity):
    _attr_icon = "mdi:format-align-middle"

    @property
    def available(self) -> bool:
        return self.manager.active and self.manager.state.level is not None

    @property
    def is_on(self) -> bool | None:
        return self.manager.state.level
