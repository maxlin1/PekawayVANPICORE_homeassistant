"""Integrationstest: Einrichtung über die Oberfläche und Nivellierung mit Ersatz-Entitäten."""

from __future__ import annotations

import asyncio
import math

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.vanpi_core.const import DOMAIN

VEHICLE = {
    "forward": "+x",
    "wheelbase": 431.8,
    "track": 173.5,
    "block_height": 2.1,
    "stacks": 2,
    "blocks_per_stack": 3,
    "tolerance": 1.5,
    "auto_off_minutes": 15,
}


def set_accel(hass: HomeAssistant, x: float, y: float, z: float) -> None:
    for axis, value in zip("xyz", (x, y, z), strict=True):
        hass.states.async_set(f"sensor.acc_{axis}", str(value), {"unit_of_measurement": "g"})


async def setup_entry(hass: HomeAssistant):
    set_accel(hass, 0.0, 0.0, 1.0)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"source": "entities"}
    )
    assert result["step_id"] == "entities"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"entity_x": "sensor.acc_x", "entity_y": "sensor.acc_y", "entity_z": "sensor.acc_z"},
    )
    assert result["step_id"] == "vehicle"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], VEHICLE)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    return result["result"]


async def test_leveling_flow(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass)
    assert entry.options["stacks"] == 2

    pitch = "sensor.leveling_pitch"
    # Aus: nicht verfügbar
    assert hass.states.get(pitch).state == "unavailable"

    switch = "switch.leveling_active"
    await hass.services.async_call("switch", "turn_on", {"entity_id": switch}, blocking=True)

    # Nullung auf ebenem Boden
    zero = "button.leveling_save_as_level"
    await hass.services.async_call("button", "press", {"entity_id": zero}, blocking=True)

    # Front 2 Grad tiefer
    a = math.radians(-2.0)
    set_accel(hass, math.sin(a), 0.0, math.cos(a))
    await asyncio.sleep(1.5)
    await hass.async_block_till_done()
    value = float(hass.states.get(pitch).state)
    assert abs(value - (-2.0)) < 0.2

    rec = "sensor.leveling_block_recommendation"
    assert "Vorne" in hass.states.get(rec).state

    await hass.services.async_call("switch", "turn_off", {"entity_id": switch}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(pitch).state == "unavailable"

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_options_flow(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**VEHICLE, "block_height": 3.0}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options["block_height"] == 3.0
    assert entry.runtime_data.leveling.vehicle.block_height == 3.0
