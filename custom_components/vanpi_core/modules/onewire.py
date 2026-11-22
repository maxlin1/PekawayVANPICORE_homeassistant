"""Modul 1-Wire: Temperatursensoren (DS18B20 u. a.) über das Kernel-Sysfs.

Liest /sys/bus/w1/devices/<id>/w1_slave direkt, ohne Zusatzbibliothek.
Neue Sensoren werden alle 5 Minuten erkannt und automatisch hinzugefügt.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import Platform, UnitOfTemperature
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity

from .base import BoardModule, ModuleEntity
from .const import (
    CONF_MOUNT_DIR,
    CONF_SCAN_INTERVAL,
    ONEWIRE_DEFAULT_DIR,
    ONEWIRE_DEFAULT_INTERVAL,
    ONEWIRE_FAMILIES,
)

_LOGGER = logging.getLogger(__name__)

DISCOVERY_INTERVAL = 300
# 85,000 °C ist der Einschaltwert des DS18B20 (keine gültige Messung)
POWER_ON_VALUE = 85000


def discover(mount_dir: str) -> list[str]:
    try:
        names = os.listdir(mount_dir)
    except OSError:
        return []
    return sorted(
        n for n in names if len(n) > 3 and n[2] == "-" and n[:2].upper() in ONEWIRE_FAMILIES
    )


def read_temperature(path: str, retries: int = 3) -> float:
    """Liest eine w1_slave-Datei. Wirft OSError bei CRC-Fehler oder Fehlwert."""
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with open(path, encoding="ascii", errors="replace") as f:
                lines = f.read().splitlines()
            if len(lines) < 2 or not lines[0].strip().endswith("YES"):
                raise OSError("CRC-Fehler")
            pos = lines[1].find("t=")
            if pos < 0:
                raise OSError("kein Messwert")
            milli = int(lines[1][pos + 2 :])
            if milli == POWER_ON_VALUE:
                raise OSError("Einschaltwert 85 °C")
            return round(milli / 1000, 2)
        except (OSError, ValueError) as err:
            last = err
            if attempt + 1 < retries:
                time.sleep(0.2)
    raise OSError(str(last))


class OneWireModule(BoardModule):
    model = "1-Wire-Bus"

    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.mount_dir = self.data.get(CONF_MOUNT_DIR) or ONEWIRE_DEFAULT_DIR
        self.interval = max(5, int(self.data.get(CONF_SCAN_INTERVAL, ONEWIRE_DEFAULT_INTERVAL)))
        self.sensor_ids: list[str] = []
        self.values: dict[str, float | None] = {}
        self._task: asyncio.Task | None = None

    async def async_prepare(self) -> None:
        self.sensor_ids = await self.hass.async_add_executor_job(discover, self.mount_dir)
        self.values = await self.hass.async_add_executor_job(self._read_all)
        self.available = True

    async def async_start(self) -> None:
        self._task = self.entry.async_create_background_task(
            self.hass, self._run(), f"vanpi_core onewire {self.subentry.title}"
        )

    async def async_stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def _path(self, sensor_id: str) -> str:
        return os.path.join(self.mount_dir, sensor_id, "w1_slave")

    def _read_all(self) -> dict[str, float | None]:
        values: dict[str, float | None] = {}
        for sensor_id in list(self.sensor_ids):
            try:
                values[sensor_id] = read_temperature(self._path(sensor_id))
            except OSError as err:
                if self.values.get(sensor_id) is not None:
                    _LOGGER.warning("1-Wire %s: %s", sensor_id, err)
                values[sensor_id] = None
        return values

    async def _run(self) -> None:
        next_discovery = time.monotonic() + DISCOVERY_INTERVAL
        await asyncio.sleep(self.interval)  # erste Messung kam schon aus async_prepare
        while True:
            if time.monotonic() >= next_discovery:
                next_discovery = time.monotonic() + DISCOVERY_INTERVAL
                found = await self.hass.async_add_executor_job(discover, self.mount_dir)
                new = [s for s in found if s not in self.sensor_ids]
                if new and self.add_entities_later:
                    _LOGGER.info("1-Wire: neue Sensoren %s", ", ".join(new))
                    self.sensor_ids.extend(new)
                    self.add_entities_later(
                        Platform.SENSOR, [OneWireTemperature(self, s) for s in new]
                    )
            self.values = await self.hass.async_add_executor_job(self._read_all)
            self.async_notify()
            await asyncio.sleep(self.interval)

    def old_name(self, sensor_id: str) -> str | None:
        """Namen aus der alten Komponente onewire_sysbus übernehmen.

        Dort hieß die Entität "Temperature", den Namen (z. B. "Außen") hat man
        meist dem Gerät gegeben. Deshalb zuerst den Gerätenamen nehmen.
        """
        registry = er.async_get(self.hass)
        unique = f"/sys/bus/w1/devices/{sensor_id}/w1_slave"
        entity_id = registry.async_get_entity_id("sensor", "onewire_sysbus", unique)
        if not entity_id or not (entry := registry.async_get(entity_id)):
            return None
        if entry.device_id and (device := dr.async_get(self.hass).async_get(entry.device_id)):
            if device.name_by_user:
                return device.name_by_user
        if entry.name and entry.name.lower() != "temperature":
            return entry.name
        return None

    def create_entities(self) -> dict[Platform, list[Entity]]:
        return {Platform.SENSOR: [OneWireTemperature(self, s) for s in self.sensor_ids]}


class OneWireTemperature(ModuleEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1
    module: OneWireModule

    def __init__(self, module: OneWireModule, sensor_id: str) -> None:
        self._old_name = module.old_name(sensor_id)
        super().__init__(module, sensor_id.lower(), f"Temperatur {sensor_id}")
        self.sensor_id = sensor_id
        self._attr_extra_state_attributes = {"sensor_id": sensor_id}
        if self._old_name:
            # Beim ersten Anlegen bestimmt der alte Name die Entity-ID.
            self._attr_name = self._old_name

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Den übernommenen Namen dauerhaft als Namen in der Registry ablegen.
        # So bleibt er erhalten, auch wenn onewire_sysbus später entfernt wird.
        if not self._old_name or not self.registry_entry:
            return
        if self.registry_entry.name is None:
            er.async_get(self.hass).async_update_entity(
                self.entity_id, name=self._old_name
            )

    @property
    def available(self) -> bool:
        return self.module.values.get(self.sensor_id) is not None

    @property
    def native_value(self) -> float | None:
        return self.module.values.get(self.sensor_id)
