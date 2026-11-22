"""Modul Relais und Eingänge (MCP23017 auf dem VAN PI CORE)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import Platform
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import Entity

from .base import BoardModule, ModuleEntity
from .const import (
    CONF_ADDRESS,
    CONF_I2C_BUS,
    CONF_INVERT_INPUTS,
    CONF_INVERT_RELAYS,
    CONF_KEEP_STATE,
    IO_POLL_INTERVAL,
    VANPI_INPUT_PINS,
    VANPI_RELAY_PINS,
)
from .mcp23017 import MCP23017

_LOGGER = logging.getLogger(__name__)

RETRY_SECONDS = 10


def relay_key(number: int) -> str:
    return f"relay_{number}"


def input_key(number: int) -> str:
    return f"input_{number}"


class IoModule(BoardModule):
    model = "VAN PI CORE Relais/Eingänge (MCP23017)"

    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.chip = MCP23017(int(self.data.get(CONF_I2C_BUS, 1)), int(self.data[CONF_ADDRESS]))
        self.invert_inputs = bool(self.data.get(CONF_INVERT_INPUTS, True))
        self.invert_relays = bool(self.data.get(CONF_INVERT_RELAYS, False))
        self.inputs = 0
        self.outputs = 0
        self._task: asyncio.Task | None = None
        self._configured = False

    async def async_start(self) -> None:
        self._task = self.entry.async_create_background_task(
            self.hass, self._run(), f"vanpi_core io {self.subentry.title}"
        )

    async def async_stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _configure(self) -> None:
        reset = not self.data.get(CONF_KEEP_STATE, True)
        await self.hass.async_add_executor_job(
            self.chip.setup, VANPI_INPUT_PINS, VANPI_RELAY_PINS, reset
        )
        self._configured = True

    async def _run(self) -> None:
        while True:
            try:
                if not self._configured:
                    await self._configure()
                inputs, outputs = await self.hass.async_add_executor_job(self.chip.read_state)
            except OSError as err:
                self._configured = False
                self.set_error(f"MCP23017 0x{self.chip.address:02x} nicht erreichbar: {err}")
                self.async_notify()
                await asyncio.sleep(RETRY_SECONDS)
                continue
            changed = not self.available or inputs != self.inputs or outputs != self.outputs
            self.inputs, self.outputs = inputs, outputs
            self.set_error(None)
            if changed:
                self.async_notify()
            await asyncio.sleep(IO_POLL_INTERVAL)

    def input_on(self, pin: int) -> bool:
        level = bool(self.inputs & (1 << pin))
        return level != self.invert_inputs

    def relay_on(self, pin: int) -> bool:
        level = bool(self.outputs & (1 << pin))
        return level != self.invert_relays

    async def async_set_relay(self, pin: int, on: bool) -> None:
        level = on != self.invert_relays
        try:
            await self.hass.async_add_executor_job(self.chip.set_output, pin, level)
        except OSError as err:
            raise HomeAssistantError(f"Relais konnte nicht geschaltet werden: {err}") from err
        if level:
            self.outputs |= 1 << pin
        else:
            self.outputs &= ~(1 << pin)
        self.async_notify()

    def create_entities(self) -> dict[Platform, list[Entity]]:
        names = self.data.get("names", {})
        relays: list[Entity] = [
            RelaySwitch(self, pin, n, names.get(relay_key(n)) or f"Relais {n}")
            for n, pin in enumerate(VANPI_RELAY_PINS, start=1)
        ]
        inputs: list[Entity] = [
            InputBinarySensor(self, pin, n, names.get(input_key(n)) or f"Eingang {n}")
            for n, pin in enumerate(VANPI_INPUT_PINS, start=1)
        ]
        return {Platform.SWITCH: relays, Platform.BINARY_SENSOR: inputs}


class RelaySwitch(ModuleEntity, SwitchEntity):
    _attr_icon = "mdi:electric-switch"
    module: IoModule

    def __init__(self, module: IoModule, pin: int, number: int, name: str) -> None:
        super().__init__(module, relay_key(number), name)
        self.pin = pin
        self._attr_extra_state_attributes = {"relais": number, "pin": pin}

    @property
    def is_on(self) -> bool:
        return self.module.relay_on(self.pin)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.module.async_set_relay(self.pin, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.module.async_set_relay(self.pin, False)


class InputBinarySensor(ModuleEntity, BinarySensorEntity):
    _attr_icon = "mdi:import"
    module: IoModule

    def __init__(self, module: IoModule, pin: int, number: int, name: str) -> None:
        super().__init__(module, input_key(number), name)
        self.pin = pin
        self._attr_extra_state_attributes = {"eingang": number, "pin": pin}

    @property
    def is_on(self) -> bool:
        return self.module.input_on(self.pin)
