"""Grundgerüst der Board-Module.

Jedes Modul gehört zu genau einem Subentry (z. B. "Relaisboard",
"Frischwassertank", "SmartShunt") und bekommt ein eigenes Gerät in HA.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import Platform
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from ..const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


class BoardModule:
    """Basis: Start/Stop, Entitäten und Benachrichtigung bei neuen Werten."""

    model: str = ""
    manufacturer: str = MANUFACTURER

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, subentry: ConfigSubentry) -> None:
        self.hass = hass
        self.entry = entry
        self.subentry = subentry
        self.data: dict[str, Any] = dict(subentry.data)
        self.available = False
        self.last_error: str | None = None
        self._listeners: list[Callable[[], None]] = []
        # Callback, um später entdeckte Entitäten nachzureichen (1-Wire)
        self.add_entities_later: Callable[[Platform, list[Entity]], None] | None = None

    @property
    def subentry_id(self) -> str:
        return self.subentry.subentry_id

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.subentry_id)},
            name=self.subentry.title,
            manufacturer=self.manufacturer,
            model=self.model,
        )

    def unique_id(self, key: str) -> str:
        return f"{self.subentry_id}_{key}"

    async def async_prepare(self) -> None:
        """Vor dem Anlegen der Entitäten (z. B. Sensoren suchen). Darf nicht werfen."""

    async def async_start(self) -> None:
        """Hardware öffnen und Hintergrundaufgaben starten. Darf nicht werfen."""

    async def async_stop(self) -> None:
        """Alles stoppen und freigeben."""

    def create_entities(self) -> dict[Platform, list[Entity]]:
        return {}

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        self._listeners.append(listener)

        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove

    @callback
    def async_notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    @callback
    def set_error(self, error: str | None) -> None:
        """Verfügbarkeit setzen und Fehler nur bei Änderung loggen."""
        if error is None:
            if not self.available and self.last_error is not None:
                _LOGGER.info("%s: wieder verbunden", self.subentry.title)
            self.available = True
            self.last_error = None
            return
        if error != self.last_error:
            _LOGGER.warning("%s: %s", self.subentry.title, error)
        self.available = False
        self.last_error = error


class ModuleEntity(Entity):
    """Entität eines Board-Moduls, aktualisiert sich bei Benachrichtigung."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, module: BoardModule, key: str, name: str) -> None:
        self.module = module
        self._attr_unique_id = module.unique_id(key)
        self._attr_name = name
        self._attr_device_info = module.device_info

    @property
    def available(self) -> bool:
        return self.module.available

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.module.async_add_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()
