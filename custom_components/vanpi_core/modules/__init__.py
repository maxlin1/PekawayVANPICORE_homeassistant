"""Board-Module des VAN PI CORE als Config-Subentries.

Jedes Subentry (Relaisboard, Tank, 1-Wire, Victron-Gerät) wird ein Modul mit
eigenem Gerät. Der ModuleManager startet/stoppt die Module und gleicht sie bei
jeder Änderung an den Subentries ab, ohne die Nivellierung neu zu laden.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .base import BoardModule
from .const import (
    SUBENTRY_IO,
    SUBENTRY_ONEWIRE,
    SUBENTRY_TANK,
    SUBENTRY_TANK_INPUTS,
    SUBENTRY_VICTRON,
)
from .io import IoModule
from .onewire import OneWireModule
from .tanks import TankInputsModule, TankModule, pair_modes
from .victron import VictronModule

_LOGGER = logging.getLogger(__name__)

MODULE_TYPES: dict[str, type[BoardModule]] = {
    SUBENTRY_IO: IoModule,
    SUBENTRY_TANK: TankModule,
    SUBENTRY_ONEWIRE: OneWireModule,
    SUBENTRY_VICTRON: VictronModule,
    SUBENTRY_TANK_INPUTS: TankInputsModule,
}


def _fingerprint(entry: ConfigEntry, subentry: ConfigSubentry) -> tuple:
    extra: tuple = ()
    if subentry.subentry_type in (SUBENTRY_TANK, SUBENTRY_TANK_INPUTS):
        # Tanks hängen am Sensortyp ihres Kanalpaars
        extra = tuple(sorted(pair_modes(entry).items()))
    return (subentry.title, repr(sorted(subentry.data.items())), extra)


class ModuleManager:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.modules: dict[str, BoardModule] = {}
        self._fingerprints: dict[str, tuple] = {}
        self._adders: dict[Platform, AddConfigEntryEntitiesCallback] = {}
        self._entities: dict[str, list[Entity]] = {}

    async def async_setup(self) -> None:
        for subentry in self.entry.subentries.values():
            await self._async_start(subentry)

    async def async_shutdown(self) -> None:
        for subentry_id in list(self.modules):
            await self._async_stop(subentry_id)

    @callback
    def register_platform(
        self, platform: Platform, add_entities: AddConfigEntryEntitiesCallback
    ) -> None:
        """Von den Plattformdateien aufgerufen: Entitäten aller Module hinzufügen."""
        self._adders[platform] = add_entities
        for subentry_id, module in self.modules.items():
            self._add(subentry_id, platform, module.create_entities().get(platform, []))

    def _add(self, subentry_id: str, platform: Platform, entities: list[Entity]) -> None:
        if not entities or platform not in self._adders:
            return
        self._entities.setdefault(subentry_id, []).extend(entities)
        self._adders[platform](entities, config_subentry_id=subentry_id)

    def _later_adder(self, subentry_id: str) -> Callable[[Platform, list[Entity]], None]:
        def add(platform: Platform, entities: list[Entity]) -> None:
            self._add(subentry_id, platform, entities)

        return add

    async def _async_start(self, subentry: ConfigSubentry) -> None:
        cls = MODULE_TYPES.get(subentry.subentry_type)
        if cls is None:
            _LOGGER.warning("Unbekannter Modultyp %s", subentry.subentry_type)
            return
        try:
            module = cls(self.hass, self.entry, subentry)
            await module.async_prepare()
        except Exception:  # noqa: BLE001  (ein fehlerhaftes Modul darf den Rest nicht stoppen)
            _LOGGER.exception("Modul %s konnte nicht angelegt werden", subentry.title)
            return
        module.add_entities_later = self._later_adder(subentry.subentry_id)
        self.modules[subentry.subentry_id] = module
        self._fingerprints[subentry.subentry_id] = _fingerprint(self.entry, subentry)
        await module.async_start()
        for platform in self._adders:
            self._add(subentry.subentry_id, platform, module.create_entities().get(platform, []))

    async def _async_stop(self, subentry_id: str, remove_entities: bool = False) -> None:
        module = self.modules.pop(subentry_id, None)
        self._fingerprints.pop(subentry_id, None)
        entities = self._entities.pop(subentry_id, [])
        if module:
            await module.async_stop()
        if remove_entities:
            for entity in entities:
                if entity.hass is not None:
                    await entity.async_remove()

    async def async_sync(self) -> None:
        """Nach Änderungen an den Subentries: hinzugefügte starten, geänderte neu starten."""
        current = self.entry.subentries
        for subentry_id in list(self.modules):
            if subentry_id not in current:
                # Entitäten entfernt HA beim Löschen des Subentries selbst
                await self._async_stop(subentry_id)
        for subentry_id, subentry in current.items():
            if subentry_id not in self.modules:
                await self._async_start(subentry)
            elif self._fingerprints.get(subentry_id) != _fingerprint(self.entry, subentry):
                await self._async_stop(subentry_id, remove_entities=True)
                await self._async_start(subentry)
