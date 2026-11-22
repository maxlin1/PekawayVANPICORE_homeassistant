"""Einrichtung über die Oberfläche: Sensorquelle, Fahrzeug und Blöcke."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_AUTO_OFF,
    CONF_BLOCK_HEIGHT,
    CONF_BLOCKS_PER_STACK,
    CONF_ENTITY_X,
    CONF_ENTITY_Y,
    CONF_ENTITY_Z,
    CONF_FORWARD,
    CONF_I2C_BUS,
    CONF_MPU_ADDRESS,
    CONF_SOURCE,
    CONF_STACKS,
    CONF_TOLERANCE,
    CONF_TRACK,
    CONF_WHEELBASE,
    DEFAULTS,
    DOMAIN,
    FORWARD_AXES,
    FORWARD_DRIVE,
    SOURCE_ENTITIES,
    SOURCE_MPU6050,
)
from .leveling.mpu6050 import MPU6050

MPU_ADDRESSES = {"0x68": 0x68, "0x69": 0x69}


def _cm(min_v: float, max_v: float, step: float) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=min_v, max=max_v, step=step, unit_of_measurement="cm",
            mode=selector.NumberSelectorMode.BOX,
        )
    )


def _int(min_v: int, max_v: int, unit: str | None = None) -> selector.NumberSelector:
    config = selector.NumberSelectorConfig(
        min=min_v, max=max_v, step=1, mode=selector.NumberSelectorMode.BOX
    )
    if unit:
        config["unit_of_measurement"] = unit
    return selector.NumberSelector(config)


def vehicle_schema(values: dict[str, Any]) -> vol.Schema:
    v = {**DEFAULTS, **values}
    return vol.Schema(
        {
            vol.Required(CONF_FORWARD, default=v[CONF_FORWARD]): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[FORWARD_DRIVE, *FORWARD_AXES],
                    translation_key="forward",
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(CONF_WHEELBASE, default=v[CONF_WHEELBASE]): _cm(100, 1000, 0.1),
            vol.Required(CONF_TRACK, default=v[CONF_TRACK]): _cm(80, 300, 0.1),
            vol.Required(CONF_BLOCK_HEIGHT, default=v[CONF_BLOCK_HEIGHT]): _cm(0.5, 30, 0.1),
            vol.Required(CONF_STACKS, default=v[CONF_STACKS]): _int(1, 4),
            vol.Required(CONF_BLOCKS_PER_STACK, default=v[CONF_BLOCKS_PER_STACK]): _int(1, 10),
            vol.Required(CONF_TOLERANCE, default=v[CONF_TOLERANCE]): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.1, max=5, step=0.1, unit_of_measurement="°",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(CONF_AUTO_OFF, default=v[CONF_AUTO_OFF]): _int(0, 240, "min"),
        }
    )


def entities_schema(values: dict[str, Any]) -> vol.Schema:
    sensor = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))
    return vol.Schema(
        {
            vol.Required(CONF_ENTITY_X, default=values.get(CONF_ENTITY_X, vol.UNDEFINED)): sensor,
            vol.Required(CONF_ENTITY_Y, default=values.get(CONF_ENTITY_Y, vol.UNDEFINED)): sensor,
            vol.Required(CONF_ENTITY_Z, default=values.get(CONF_ENTITY_Z, vol.UNDEFINED)): sensor,
        }
    )


def _normalize_numbers(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    for key in (CONF_STACKS, CONF_BLOCKS_PER_STACK, CONF_AUTO_OFF):
        if key in out:
            out[key] = int(out[key])
    return out


class VanPiConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._data[CONF_SOURCE] = user_input[CONF_SOURCE]
            if user_input[CONF_SOURCE] == SOURCE_MPU6050:
                return await self.async_step_mpu6050()
            return await self.async_step_entities()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SOURCE, default=SOURCE_MPU6050): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[SOURCE_MPU6050, SOURCE_ENTITIES],
                            translation_key="source",
                        )
                    )
                }
            ),
        )

    async def async_step_mpu6050(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            bus = int(user_input[CONF_I2C_BUS])
            address = MPU_ADDRESSES[user_input[CONF_MPU_ADDRESS]]
            mpu = MPU6050(bus, address)
            found = await self.hass.async_add_executor_job(mpu.probe)
            await self.hass.async_add_executor_job(mpu.sleep)
            if found:
                self._data.update({CONF_I2C_BUS: bus, CONF_MPU_ADDRESS: address})
                return await self.async_step_vehicle()
            errors["base"] = "mpu_not_found"
        return self.async_show_form(
            step_id="mpu6050",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_I2C_BUS, default=DEFAULTS[CONF_I2C_BUS]): _int(0, 10),
                    vol.Required(CONF_MPU_ADDRESS, default="0x69"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=list(MPU_ADDRESSES))
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_entities(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_vehicle()
        return self.async_show_form(step_id="entities", data_schema=entities_schema({}))

    async def async_step_vehicle(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title="VAN PI CORE",
                data=self._data,
                options=_normalize_numbers(user_input),
            )
        return self.async_show_form(step_id="vehicle", data_schema=vehicle_schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return VanPiOptionsFlow()


class VanPiOptionsFlow(OptionsFlow):
    """Fahrzeug, Blöcke und Ausrichtung jederzeit änderbar."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=_normalize_numbers(user_input))
        return self.async_show_form(
            step_id="init", data_schema=vehicle_schema(dict(self.config_entry.options))
        )
