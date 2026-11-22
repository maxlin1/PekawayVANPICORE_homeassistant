"""Schalter: Nivellierung an/aus."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    async_add_entities([LevelingSwitch(entry.runtime_data.leveling, "active")])
    entry.runtime_data.modules.register_platform(Platform.SWITCH, async_add_entities)


class LevelingSwitch(LevelingEntity, SwitchEntity):
    _attr_icon = "mdi:car-cog"

    @property
    def is_on(self) -> bool:
        return self.manager.active

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.manager.async_set_active(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.manager.async_set_active(False)
