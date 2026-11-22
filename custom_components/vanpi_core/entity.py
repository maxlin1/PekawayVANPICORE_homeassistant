"""Gemeinsame Basis für VAN-PI-CORE-Entitäten."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER, MODEL
from .leveling.manager import LevelingManager


class LevelingEntity(Entity):
    """Entität des Nivellier-Moduls. Wird bei jeder Änderung vom Manager informiert."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager: LevelingManager, key: str) -> None:
        self.manager = manager
        entry_id = manager.entry.entry_id
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry_id}_leveling_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_leveling")},
            translation_key="leveling",
            manufacturer=MANUFACTURER,
            model=f"{MODEL} Nivellierung",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.manager.async_add_listener(self.async_write_ha_state))
