"""Modul Tank (ein Kanal des ADS1115 auf dem VAN PI CORE)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    Platform,
    UnitOfElectricPotential,
    UnitOfVolume,
)
from homeassistant.helpers.entity import Entity

from .ads1115 import ADS1115
from .base import BoardModule, ModuleEntity
from .const import (
    ADS_DEFAULT_ADDRESS,
    CONF_ADDRESS,
    CONF_CHANNEL,
    CONF_CURVE,
    CONF_DIVIDER,
    CONF_I2C_BUS,
    CONF_MODE,
    CONF_PULLUP,
    CONF_SCAN_INTERVAL,
    CONF_UNIT,
    CONF_VREF,
    MODE_RESISTIVE,
    TANK_DEFAULT_CURVE,
    TANK_DEFAULT_INTERVAL,
    UNIT_LITERS,
)
from .curve import interpolate, parse_curve
from .gpio import GpioError, set_pullup

_LOGGER = logging.getLogger(__name__)


class TankModule(BoardModule):
    model = "VAN PI CORE Tankeingang (ADS1115)"

    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.ads = ADS1115(
            int(self.data.get(CONF_I2C_BUS, 1)),
            int(self.data.get(CONF_ADDRESS, ADS_DEFAULT_ADDRESS)),
        )
        self.onboard = int(self.data.get(CONF_ADDRESS, ADS_DEFAULT_ADDRESS)) == ADS_DEFAULT_ADDRESS
        self.channel = int(self.data[CONF_CHANNEL])  # 1-4 wie auf dem Board
        self.curve = parse_curve(self.data.get(CONF_CURVE) or TANK_DEFAULT_CURVE)
        self.divider = float(self.data.get(CONF_DIVIDER, 1.0)) or 1.0
        self.resistive = self.data.get(CONF_MODE) == MODE_RESISTIVE
        self.pullup = float(self.data.get(CONF_PULLUP, 47000))
        self.vref = float(self.data.get(CONF_VREF, 3.3))
        self.interval = max(1, int(self.data.get(CONF_SCAN_INTERVAL, TANK_DEFAULT_INTERVAL)))
        self.voltage: float | None = None
        self.pullup_on: bool | None = None  # tatsächlich gesetzter Zustand
        self.pullup_error: str | None = None
        self._task: asyncio.Task | None = None

    @property
    def level(self) -> float | None:
        if self.voltage is None:
            return None
        return round(interpolate(self.curve, self.voltage), 1)

    @property
    def resistance(self) -> float | None:
        v = self.voltage
        if v is None or v >= self.vref:
            return None
        return round(self.pullup * v / (self.vref - v))

    async def async_start(self) -> None:
        self._task = self.entry.async_create_background_task(
            self.hass, self._run(), f"vanpi_core tank {self.subentry.title}"
        )

    async def async_stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _apply_pullup(self) -> None:
        """Pull-up des Kanalpaars passend zum Sensortyp schalten."""
        want = self.resistive
        try:
            pin = await self.hass.async_add_executor_job(set_pullup, self.channel, want)
        except GpioError as err:
            if str(err) != self.pullup_error:
                _LOGGER.warning(
                    "%s: Pull-up konnte nicht %sgeschaltet werden (%s). "
                    "Messwerte können verfälscht sein.",
                    self.subentry.title, "ein" if want else "aus", err,
                )
            self.pullup_error = str(err)
            self.pullup_on = None
        else:
            if self.pullup_on is None:
                _LOGGER.debug("%s: Pull-up %s (sysfs %s)", self.subentry.title, want, pin)
            self.pullup_error = None
            self.pullup_on = want

    async def _run(self) -> None:
        # Pull-up einmal beim Start setzen (HA-Start oder geänderter Tank).
        # Den Schalter gibt es nur für den ADS1115 auf dem Board.
        if self.onboard:
            await self._apply_pullup()
        while True:
            try:
                v_adc = await self.hass.async_add_executor_job(
                    self.ads.read_voltage, self.channel - 1
                )
            except OSError as err:
                self.voltage = None
                self.set_error(f"ADS1115 Kanal {self.channel}: {err}")
            else:
                self.voltage = round(v_adc * self.divider, 3)
                self.set_error(None)
            self.async_notify()
            await asyncio.sleep(self.interval)

    def create_entities(self) -> dict[Platform, list[Entity]]:
        sensors: list[Entity] = [TankLevelSensor(self), TankVoltageSensor(self)]
        if self.resistive:
            sensors.append(TankResistanceSensor(self))
        return {Platform.SENSOR: sensors}


class TankLevelSensor(ModuleEntity, SensorEntity):
    _attr_icon = "mdi:storage-tank"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0
    module: TankModule

    def __init__(self, module: TankModule) -> None:
        super().__init__(module, "level", "Füllstand")
        if module.data.get(CONF_UNIT, UNIT_LITERS) == UNIT_LITERS:
            self._attr_native_unit_of_measurement = UnitOfVolume.LITERS
            self._attr_device_class = SensorDeviceClass.VOLUME_STORAGE
        else:
            self._attr_native_unit_of_measurement = PERCENTAGE

    @property
    def native_value(self) -> float | None:
        return self.module.level


class TankVoltageSensor(ModuleEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    module: TankModule

    def __init__(self, module: TankModule) -> None:
        super().__init__(module, "voltage", "Spannung")

    @property
    def native_value(self) -> float | None:
        return self.module.voltage

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        m = self.module
        return {
            "kanal": m.channel,
            "pull_up": {True: "an", False: "aus", None: "unbekannt"}[m.pullup_on],
            **({"pull_up_fehler": m.pullup_error} if m.pullup_error else {}),
        }


class TankResistanceSensor(ModuleEntity, SensorEntity):
    _attr_icon = "mdi:omega"
    _attr_native_unit_of_measurement = "Ω"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    module: TankModule

    def __init__(self, module: TankModule) -> None:
        super().__init__(module, "resistance", "Widerstand")

    @property
    def native_value(self) -> float | None:
        return self.module.resistance
