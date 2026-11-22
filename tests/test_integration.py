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
}


def set_accel(hass: HomeAssistant, x: float, y: float, z: float) -> None:
    for axis, value in zip("xyz", (x, y, z), strict=True):
        hass.states.async_set(f"sensor.acc_{axis}", str(value), {"unit_of_measurement": "g"})


async def setup_entry(hass: HomeAssistant, leveling: bool = True):
    """Haupteintrag (Board) anlegen und Nivellierung als eigenen Eintrag einrichten."""
    set_accel(hass, 0.0, 0.0, 1.0)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"pair_12": "voltage", "pair_34": "voltage"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    await hass.async_block_till_done()
    if not leveling:
        return entry
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "leveling"), context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"source": "entities"}
    )
    assert result["step_id"] == "entities"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"entity_x": "sensor.acc_x", "entity_y": "sensor.acc_y", "entity_z": "sensor.acc_z"},
    )
    assert result["step_id"] == "vehicle"
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], VEHICLE)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    return entry


def leveling_subentry_id(entry) -> str:
    return next(s.subentry_id for s in entry.subentries.values() if s.subentry_type == "leveling")


async def test_leveling_flow(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass)
    assert entry.subentries[leveling_subentry_id(entry)].data["stacks"] == 2

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


async def test_reconfigure_leveling(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass)
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.leveling_active"}, blocking=True
    )
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "leveling"),
        context={"source": config_entries.SOURCE_RECONFIGURE,
                 "subentry_id": leveling_subentry_id(entry)},
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**VEHICLE, "block_height": 3.0}
    )
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert entry.subentries[leveling_subentry_id(entry)].data["block_height"] == 3.0
    assert entry.runtime_data.leveling.vehicle.block_height == 3.0
    # Einstellungen ändern schaltet die Nivellierung nicht aus
    assert hass.states.get("switch.leveling_active").state == "on"
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_auto_off_after_15_minutes(hass: HomeAssistant) -> None:
    from datetime import timedelta

    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    entry = await setup_entry(hass)
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.leveling_active"}, blocking=True
    )
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=14))
    await hass.async_block_till_done()
    assert hass.states.get("switch.leveling_active").state == "on"
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=16))
    await hass.async_block_till_done()
    assert hass.states.get("switch.leveling_active").state == "off"
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_reset_button_reenabled_after_update(hass: HomeAssistant) -> None:
    """Alte Installationen: von der Integration deaktivierter Button wird aktiviert."""
    from homeassistant.helpers import entity_registry as er

    entry = await setup_entry(hass)
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "button", DOMAIN, f"{entry.entry_id}_leveling_reset_calibration"
    )
    assert entity_id
    registry.async_update_entity(entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get(entity_id).disabled_by is None


async def test_board_options_and_single_leveling(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"pair_12": "resistive", "pair_34": "voltage"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["pair_12"] == "resistive"
    again = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "leveling"), context={"source": config_entries.SOURCE_USER}
    )
    assert again["type"] is FlowResultType.ABORT


async def test_without_leveling(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass, leveling=False)
    assert entry.runtime_data.leveling is None
    assert hass.states.get("switch.leveling_active") is None


async def test_migration_v1(hass: HomeAssistant) -> None:
    """Alte Einrichtung: Nivellierung im Haupteintrag, Tankeingänge als eigener Eintrag."""
    from homeassistant.config_entries import ConfigSubentryData
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    set_accel(hass, 0.0, 0.0, 1.0)
    entry = MockConfigEntry(
        domain=DOMAIN, version=1, title="VAN PI CORE",
        data={"source": "entities", "entity_x": "sensor.acc_x",
              "entity_y": "sensor.acc_y", "entity_z": "sensor.acc_z"},
        options={**VEHICLE, "auto_off_minutes": 1},
        subentries_data=[ConfigSubentryData(
            data={"pair_12": "resistive", "pair_34": "voltage"},
            subentry_type="tank_inputs", title="Tankeingänge", unique_id=None,
        )],
    )
    entry.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, f"{entry.entry_id}_leveling")}
    )
    old = ent_reg.async_get_or_create(
        "switch", DOMAIN, f"{entry.entry_id}_leveling_active",
        config_entry=entry, device_id=device.id, suggested_object_id="camper_nivellierung_aktiv",
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 2
    assert entry.data == {}
    assert entry.options == {"pair_12": "resistive", "pair_34": "voltage"}
    types = [s.subentry_type for s in entry.subentries.values()]
    assert types == ["leveling"]
    sub_id = leveling_subentry_id(entry)
    data = entry.subentries[sub_id].data
    assert data["wheelbase"] == VEHICLE["wheelbase"] and data["source"] == "entities"
    assert "auto_off_minutes" not in data
    # Entity-ID bleibt, hängt jetzt am Eintrag Nivellierung
    reg = ent_reg.async_get(old.entity_id)
    assert reg.config_subentry_id == sub_id
    assert hass.states.get("switch.camper_nivellierung_aktiv") is not None
    dev = dev_reg.async_get(device.id)
    assert dev.config_entries_subentries[entry.entry_id] == {sub_id}
