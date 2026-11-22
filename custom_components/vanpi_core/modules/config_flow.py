"""Einrichtung der Board-Module als Subentries ("+ Relaisboard hinzufügen" usw.)."""

from __future__ import annotations

import glob
import os
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.helpers import selector

from .const import (
    ADS_DEFAULT_ADDRESS,
    CONF_ADDRESS,
    CONF_CHANNEL,
    CONF_CURVE,
    CONF_DEVICE_TYPE,
    CONF_DIVIDER,
    CONF_I2C_BUS,
    CONF_INVERT_INPUTS,
    CONF_INVERT_RELAYS,
    CONF_KEEP_STATE,
    CONF_MOUNT_DIR,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_UNIT,
    DEVICE_MPPT,
    DEVICE_SHUNT,
    MCP_DEFAULT_ADDRESS,
    ONEWIRE_DEFAULT_DIR,
    ONEWIRE_DEFAULT_INTERVAL,
    SUBENTRY_IO,
    SUBENTRY_ONEWIRE,
    SUBENTRY_TANK,
    SUBENTRY_VICTRON,
    TANK_DEFAULT_CURVE,
    TANK_DEFAULT_INTERVAL,
    UNIT_LITERS,
    UNIT_PERCENT,
    VANPI_INPUT_PINS,
    VANPI_RELAY_PINS,
    VICTRON_DEFAULT_INTERVAL,
)
from .curve import CurveError, format_curve, parse_curve
from .i2c import probe
from .io import input_key, relay_key

MCP_ADDRESSES = [f"0x{a:02x}" for a in range(0x20, 0x28)]
ADS_ADDRESSES = [f"0x{a:02x}" for a in range(0x48, 0x4C)]


def _text() -> selector.TextSelector:
    return selector.TextSelector()


def _number(min_v: float, max_v: float, step: float = 1, unit: str | None = None):
    config = selector.NumberSelectorConfig(
        min=min_v, max=max_v, step=step, mode=selector.NumberSelectorMode.BOX
    )
    if unit:
        config["unit_of_measurement"] = unit
    return selector.NumberSelector(config)


def _select(options: list[str], key: str | None = None, custom: bool = False):
    config = selector.SelectSelectorConfig(
        options=options, mode=selector.SelectSelectorMode.DROPDOWN, custom_value=custom
    )
    if key:
        config["translation_key"] = key
    return selector.SelectSelector(config)


class _BaseSubentryFlow(ConfigSubentryFlow):
    """Gemeinsam: Werte beim Ändern vorbelegen, Doppelte erkennen."""

    subentry_type: str = ""

    def _current(self) -> dict[str, Any]:
        if self.source == SOURCE_RECONFIGURE:
            sub = self._get_reconfigure_subentry()
            return {**sub.data, CONF_NAME: sub.title}
        return {}

    def _others(self) -> list[dict[str, Any]]:
        own = self.context.get("subentry_id") if self.source == SOURCE_RECONFIGURE else None
        return [
            dict(s.data)
            for s in self._get_entry().subentries.values()
            if s.subentry_type == self.subentry_type and s.subentry_id != own
        ]

    def _finish(self, title: str, data: dict[str, Any]) -> SubentryFlowResult:
        if self.source == SOURCE_RECONFIGURE:
            return self.async_update_and_abort(
                self._get_entry(), self._get_reconfigure_subentry(), title=title, data=data
            )
        return self.async_create_entry(title=title, data=data)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        return await self.async_step_user(user_input)


# --- Relais und Eingänge ---------------------------------------------------


class IoSubentryFlow(_BaseSubentryFlow):
    subentry_type = SUBENTRY_IO

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._title = ""

    def _old_names(self, address: int) -> dict[str, str]:
        """Namen aus der alten Komponente mcp23017 übernehmen (gleiche Adresse)."""
        names: dict[str, str] = {}
        for entry in self.hass.config_entries.async_entries("mcp23017"):
            data = entry.data
            if data.get("i2c_address") != address:
                continue
            pin, name = data.get("pin_number"), str(data.get("pin_name", "")).strip()
            if not name:
                continue
            if pin in VANPI_RELAY_PINS:
                names[relay_key(VANPI_RELAY_PINS.index(pin) + 1)] = name
            elif pin in VANPI_INPUT_PINS:
                names[input_key(VANPI_INPUT_PINS.index(pin) + 1)] = name
        return names

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        current = self._current()
        if user_input is not None:
            bus = int(user_input[CONF_I2C_BUS])
            address = int(user_input[CONF_ADDRESS], 16)
            if any(int(o[CONF_ADDRESS]) == address for o in self._others()):
                errors[CONF_ADDRESS] = "already_configured"
            elif not await self.hass.async_add_executor_job(probe, bus, address):
                errors["base"] = "not_found"
            else:
                self._title = user_input[CONF_NAME].strip() or "VAN PI"
                self._data = {
                    CONF_I2C_BUS: bus,
                    CONF_ADDRESS: address,
                    CONF_INVERT_INPUTS: user_input[CONF_INVERT_INPUTS],
                    CONF_INVERT_RELAYS: user_input[CONF_INVERT_RELAYS],
                    CONF_KEEP_STATE: user_input[CONF_KEEP_STATE],
                    "names": current.get("names") or self._old_names(address),
                }
                return await self.async_step_names()
        v = {
            CONF_NAME: "VAN PI",
            CONF_I2C_BUS: 1,
            CONF_ADDRESS: MCP_DEFAULT_ADDRESS,
            CONF_INVERT_INPUTS: True,
            CONF_INVERT_RELAYS: False,
            CONF_KEEP_STATE: True,
            **current,
        }
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=v[CONF_NAME]): _text(),
                vol.Required(CONF_I2C_BUS, default=v[CONF_I2C_BUS]): _number(0, 10),
                vol.Required(CONF_ADDRESS, default=f"0x{int(v[CONF_ADDRESS]):02x}"): _select(
                    MCP_ADDRESSES
                ),
                vol.Required(CONF_INVERT_INPUTS, default=v[CONF_INVERT_INPUTS]): bool,
                vol.Required(CONF_INVERT_RELAYS, default=v[CONF_INVERT_RELAYS]): bool,
                vol.Required(CONF_KEEP_STATE, default=v[CONF_KEEP_STATE]): bool,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_names(self, user_input: dict[str, Any] | None = None):
        keys = [relay_key(n) for n in range(1, 9)] + [input_key(n) for n in range(1, 9)]
        if user_input is not None:
            self._data["names"] = {
                k: str(user_input.get(k, "")).strip() for k in keys if str(user_input.get(k, "")).strip()
            }
            return self._finish(self._title, self._data)
        names = self._data.get("names", {})
        schema = vol.Schema(
            {
                vol.Optional(k, description={"suggested_value": names.get(k)}): _text()
                for k in keys
            }
        )
        return self.async_show_form(step_id="names", data_schema=schema)


# --- Tank --------------------------------------------------------------------


class TankSubentryFlow(_BaseSubentryFlow):
    subentry_type = SUBENTRY_TANK

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        current = self._current()
        if user_input is not None:
            channel = int(user_input[CONF_CHANNEL])
            address = int(user_input[CONF_ADDRESS], 16)
            try:
                curve = format_curve(parse_curve(user_input[CONF_CURVE]))
            except CurveError:
                errors[CONF_CURVE] = "invalid_curve"
            else:
                if any(
                    int(o[CONF_CHANNEL]) == channel and int(o[CONF_ADDRESS]) == address
                    for o in self._others()
                ):
                    errors[CONF_CHANNEL] = "already_configured"
                elif not await self.hass.async_add_executor_job(probe, 1, address):
                    errors["base"] = "not_found"
            if not errors:
                data = {
                    CONF_I2C_BUS: 1,
                    CONF_ADDRESS: address,
                    CONF_CHANNEL: channel,
                    CONF_UNIT: user_input[CONF_UNIT],
                    CONF_CURVE: curve,
                    CONF_DIVIDER: float(user_input[CONF_DIVIDER]),
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                }
                title = user_input.get(CONF_NAME, "").strip() or f"Tank {channel}"
                return self._finish(title, data)
        used = {int(o[CONF_CHANNEL]) for o in self._others()}
        free = next((c for c in range(1, 5) if c not in used), 1)
        v = {
            CONF_NAME: "",
            CONF_ADDRESS: ADS_DEFAULT_ADDRESS,
            CONF_CHANNEL: free,
            CONF_UNIT: UNIT_LITERS,
            CONF_CURVE: TANK_DEFAULT_CURVE,
            CONF_DIVIDER: 1.0,
            CONF_SCAN_INTERVAL: TANK_DEFAULT_INTERVAL,
            **current,
        }
        if user_input:
            v.update(user_input)
            v[CONF_ADDRESS] = int(user_input[CONF_ADDRESS], 16)
        schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, description={"suggested_value": v[CONF_NAME]}): _text(),
                vol.Required(CONF_CHANNEL, default=str(v[CONF_CHANNEL])): _select(
                    ["1", "2", "3", "4"]
                ),
                vol.Required(CONF_UNIT, default=v[CONF_UNIT]): _select([UNIT_LITERS, UNIT_PERCENT]),
                vol.Required(CONF_CURVE, default=v[CONF_CURVE]): selector.TextSelector(
                    selector.TextSelectorConfig(multiline=True)
                ),
                vol.Required(CONF_DIVIDER, default=v[CONF_DIVIDER]): _number(0.1, 20, 0.001),
                vol.Required(CONF_SCAN_INTERVAL, default=v[CONF_SCAN_INTERVAL]): _number(1, 300, 1, "s"),
                vol.Required(CONF_ADDRESS, default=f"0x{int(v[CONF_ADDRESS]):02x}"): _select(
                    ADS_ADDRESSES
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


# --- 1-Wire ------------------------------------------------------------------


class OneWireSubentryFlow(_BaseSubentryFlow):
    subentry_type = SUBENTRY_ONEWIRE

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if self.source != SOURCE_RECONFIGURE and self._others():
            return self.async_abort(reason="already_configured")
        errors: dict[str, str] = {}
        current = self._current()
        if user_input is not None:
            mount_dir = user_input[CONF_MOUNT_DIR].strip()
            if not await self.hass.async_add_executor_job(os.path.isdir, mount_dir):
                errors[CONF_MOUNT_DIR] = "invalid_path"
            else:
                return self._finish(
                    user_input[CONF_NAME].strip() or "1-Wire",
                    {
                        CONF_MOUNT_DIR: mount_dir,
                        CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                    },
                )
        v = {
            CONF_NAME: "1-Wire",
            CONF_MOUNT_DIR: ONEWIRE_DEFAULT_DIR,
            CONF_SCAN_INTERVAL: ONEWIRE_DEFAULT_INTERVAL,
            **current,
        }
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=v[CONF_NAME]): _text(),
                vol.Required(CONF_MOUNT_DIR, default=v[CONF_MOUNT_DIR]): _text(),
                vol.Required(CONF_SCAN_INTERVAL, default=v[CONF_SCAN_INTERVAL]): _number(5, 600, 1, "s"),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


# --- Victron -----------------------------------------------------------------


def _serial_ports() -> list[str]:
    ports = sorted(glob.glob("/dev/ttyAMA*")) + sorted(glob.glob("/dev/ttyUSB*"))
    ports += sorted(glob.glob("/dev/serial/by-id/*"))
    return ports


DEFAULT_NAMES = {DEVICE_MPPT: "MPPT", DEVICE_SHUNT: "SmartShunt"}


class VictronSubentryFlow(_BaseSubentryFlow):
    subentry_type = SUBENTRY_VICTRON

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        current = self._current()
        if user_input is not None:
            port = user_input[CONF_PORT].strip()
            if any(o[CONF_PORT] == port for o in self._others()):
                errors[CONF_PORT] = "already_configured"
            elif not await self.hass.async_add_executor_job(os.path.exists, port):
                errors[CONF_PORT] = "port_not_found"
            else:
                device_type = user_input[CONF_DEVICE_TYPE]
                return self._finish(
                    user_input.get(CONF_NAME, "").strip() or DEFAULT_NAMES[device_type],
                    {
                        CONF_PORT: port,
                        CONF_DEVICE_TYPE: device_type,
                        CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                    },
                )
        ports = await self.hass.async_add_executor_job(_serial_ports)
        used = {o[CONF_PORT] for o in self._others()}
        # VAN PI CORE: UART4 = MPPT, UART5 = SmartShunt
        if "/dev/ttyAMA5" not in used:
            guess_port, guess_type = "/dev/ttyAMA5", DEVICE_SHUNT
        else:
            guess_port, guess_type = "/dev/ttyAMA4", DEVICE_MPPT
        v = {
            CONF_NAME: "",
            CONF_PORT: guess_port,
            CONF_DEVICE_TYPE: guess_type,
            CONF_SCAN_INTERVAL: VICTRON_DEFAULT_INTERVAL,
            **current,
        }
        options = sorted(set(ports) | {v[CONF_PORT]})
        schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE_TYPE, default=v[CONF_DEVICE_TYPE]): _select(
                    [DEVICE_SHUNT, DEVICE_MPPT], "victron_type"
                ),
                vol.Required(CONF_PORT, default=v[CONF_PORT]): _select(options, custom=True),
                vol.Optional(CONF_NAME, description={"suggested_value": v[CONF_NAME]}): _text(),
                vol.Required(CONF_SCAN_INTERVAL, default=v[CONF_SCAN_INTERVAL]): _number(1, 300, 1, "s"),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


SUBENTRY_FLOWS: dict[str, type[ConfigSubentryFlow]] = {
    SUBENTRY_IO: IoSubentryFlow,
    SUBENTRY_TANK: TankSubentryFlow,
    SUBENTRY_ONEWIRE: OneWireSubentryFlow,
    SUBENTRY_VICTRON: VictronSubentryFlow,
}
