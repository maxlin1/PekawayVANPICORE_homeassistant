"""Integrationstest der Board-Module als Subentries mit Ersatz-Hardware."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.vanpi_core.modules import ads1115, i2c, io, mcp23017, tanks, victron
from custom_components.vanpi_core.modules import config_flow as sub_flow

from .fakes import FakeAdsBus, FakeMcpBus, bus_cm
from .test_integration import setup_entry
from .test_modules_units import SHUNT, make_block

MPPT = [("PID", "0xA056"), ("V", "13360"), ("I", "1400"), ("VPV", "43380"), ("PPV", "19"),
        ("CS", "3"), ("MPPT", "2"), ("OR", "0x00000000"), ("ERR", "0"), ("LOAD", "ON"),
        ("H19", "25225"), ("H20", "18"), ("H21", "52"), ("H22", "13"), ("H23", "7")]


@pytest.fixture
def hardware(monkeypatch):
    mcp_bus = FakeMcpBus()
    ads_bus = FakeAdsBus({0: 0.49, 1: 1.0})

    def fake_bus(n):
        raise AssertionError("echter I2C-Zugriff im Test")

    monkeypatch.setattr(i2c, "i2c_bus", fake_bus)
    monkeypatch.setattr(mcp23017, "i2c_bus", lambda n: bus_cm(mcp_bus))
    monkeypatch.setattr(ads1115, "i2c_bus", lambda n: bus_cm(ads_bus))
    monkeypatch.setattr(sub_flow, "probe", lambda bus, addr: True)
    monkeypatch.setattr(io, "IO_POLL_INTERVAL", 0.01)
    pullups: list[tuple[int, bool]] = []
    monkeypatch.setattr(tanks, "set_pullup", lambda ch, on: pullups.append((ch, on)) or 531)
    ads_bus.pullups = pullups
    return mcp_bus, ads_bus


class FakeReader:
    """Ersetzt den seriellen Lese-Thread: liefert einen Block je Port."""

    blocks = {"/dev/ttyAMA5": SHUNT, "/dev/ttyAMA4": MPPT}

    def __init__(self, port, baudrate, on_block, on_error) -> None:
        from custom_components.vanpi_core.modules.vedirect import VEDirectParser

        self.port = port
        self.parser = VEDirectParser()
        for block in self.parser.feed(make_block(self.blocks[port])):
            on_block(block)

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def join(self, timeout=None) -> None:
        pass


async def add_subentry(hass, entry, kind, steps):
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, kind), context={"source": config_entries.SOURCE_USER}
    )
    for user_input in steps:
        assert result["type"] is FlowResultType.FORM, result
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input
        )
    await hass.async_block_till_done()
    return result


def entity_id(hass, unique_suffix: str, domain: str) -> str:
    registry = er.async_get(hass)
    for e in registry.entities.values():
        if e.platform == "vanpi_core" and e.domain == domain and e.unique_id.endswith(unique_suffix):
            return e.entity_id
    raise AssertionError(f"{domain} *{unique_suffix} nicht gefunden")


async def test_io_module(hass: HomeAssistant, hardware) -> None:
    mcp_bus, _ = hardware
    # alte Komponente mit Namen
    MockConfigEntry(
        domain="mcp23017",
        data={"i2c_address": 0x20, "pin_number": 8, "pin_name": "Trittstufe rein",
              "platform": "switch"},
    ).add_to_hass(hass)
    entry = await setup_entry(hass)
    result = await add_subentry(
        hass, entry, "io",
        [
            {"name": "VAN PI", "i2c_bus": 1, "address": "0x20", "invert_inputs": True,
             "invert_relays": False, "keep_state": True},
            {"relay_1": "Trittstufe rein", "input_7": "Zündung ein"},
        ],
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await asyncio.sleep(0.05)
    await hass.async_block_till_done()

    relay = entity_id(hass, "_relay_1", "switch")
    assert relay == "switch.van_pi_trittstufe_rein"
    assert hass.states.get(relay).state == "off"
    await hass.services.async_call("switch", "turn_on", {"entity_id": relay}, blocking=True)
    assert mcp_bus.regs[0x1A] == 0x01
    assert hass.states.get(relay).state == "on"

    ign = entity_id(hass, "_input_7", "binary_sensor")
    assert ign == "binary_sensor.van_pi_zundung_ein"
    assert hass.states.get(ign).state == "off"
    mcp_bus.pins_in = 0xBF  # Eingang 7 gegen Masse
    await asyncio.sleep(0.05)
    await hass.async_block_till_done()
    assert hass.states.get(ign).state == "on"

    # Relais von außen geschaltet (alte Komponente) -> neue Integration zeigt es
    mcp_bus.regs[0x1A] = 0x03
    await asyncio.sleep(0.05)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id(hass, "_relay_2", "switch")).state == "on"

    # Doppelte Adresse wird abgelehnt
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "io"), context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"name": "x", "i2c_bus": 1, "address": "0x20", "invert_inputs": True,
         "invert_relays": False, "keep_state": True},
    )
    assert result["errors"] == {"address": "already_configured"}

    # Nivellierung bleibt unberührt
    assert hass.states.get("switch.leveling_active") is not None
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_tank_module_and_reconfigure(hass: HomeAssistant, hardware) -> None:
    entry = await setup_entry(hass)
    result = await add_subentry(
        hass, entry, "tank",
        [{"name": "Abwasser", "channel": "1", "unit": "L",
          "curve": "0:0, 0.49:50, 1.6:100", "divider_ratio": 1,
          "scan_interval": 5, "address": "0x48"}],
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await asyncio.sleep(0.05)
    await hass.async_block_till_done()
    level = "sensor.abwasser_fullstand"
    assert float(hass.states.get(level).state) == pytest.approx(50, abs=0.5)
    volt = hass.states.get("sensor.abwasser_spannung")
    assert float(volt.state) == pytest.approx(0.49, abs=0.01)
    assert hardware[1].pullups == [(1, False)]
    assert volt.attributes["pull_up"] == "aus"

    # ungültige Kennlinie
    bad = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "tank"), context={"source": config_entries.SOURCE_USER}
    )
    bad = await hass.config_entries.subentries.async_configure(
        bad["flow_id"],
        {"name": "x", "channel": "2", "unit": "L", "curve": "kaputt",
         "divider_ratio": 1, "scan_interval": 5,
         "address": "0x48"},
    )
    assert bad["errors"] == {"curve": "invalid_curve"}

    # Ändern: Kennlinie linear bis 0.98 V = 100 L
    subentry_id = next(k for k, s in entry.subentries.items() if s.subentry_type == "tank")
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "tank"),
        context={"source": config_entries.SOURCE_RECONFIGURE, "subentry_id": subentry_id},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"name": "Abwasser", "channel": "1", "unit": "%",
         "curve": "0:0, 0.98:100", "divider_ratio": 1,
         "scan_interval": 5, "address": "0x48"},
    )
    assert result["reason"] == "reconfigure_successful"
    await asyncio.sleep(0.05)
    await hass.async_block_till_done()
    state = hass.states.get(level)
    assert float(state.state) == pytest.approx(50, abs=0.5)
    assert state.attributes["unit_of_measurement"] == "%"
    assert hass.states.get("sensor.abwasser_widerstand") is None

    # Sensortyp je Kanalpaar über das Zahnrad am Haupteintrag: 1+2 auf Widerstandsgeber
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"pair_12": "resistive", "pair_34": "voltage"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await asyncio.sleep(0.05)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.abwasser_widerstand") is not None
    assert (1, True) in hardware[1].pullups and (3, False) in hardware[1].pullups
    assert hass.states.get("sensor.abwasser_spannung").attributes["pull_up"] == "an"

    # Löschen entfernt die Entitäten
    hass.config_entries.async_remove_subentry(entry, subentry_id)
    await hass.async_block_till_done()
    assert hass.states.get(level) is None
    assert subentry_id not in entry.runtime_data.modules.modules
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_onewire_module(hass: HomeAssistant, hardware, tmp_path) -> None:
    sensor = tmp_path / "28-0000012345ab"
    sensor.mkdir()
    (sensor / "w1_slave").write_text("aa : crc=57 YES\naa t=8125\n")
    # Name aus der alten Komponente
    registry = er.async_get(hass)
    old = MockConfigEntry(domain="onewire_sysbus")
    old.add_to_hass(hass)
    from homeassistant.helpers import device_registry as dr

    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=old.entry_id, identifiers={("onewire_sysbus", "28-0000012345ab")},
        name="28-0000012345ab",
    )
    dr.async_get(hass).async_update_device(device.id, name_by_user="Außen")
    registry.async_get_or_create(
        "sensor", "onewire_sysbus", "/sys/bus/w1/devices/28-0000012345ab/w1_slave",
        config_entry=old, original_name="Temperature", device_id=device.id,
    )

    entry = await setup_entry(hass)
    result = await add_subentry(
        hass, entry, "onewire",
        [{"name": "1-Wire", "mount_dir": str(tmp_path), "scan_interval": 30}],
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    state = hass.states.get("sensor.1_wire_aussen")
    assert state is not None and float(state.state) == pytest.approx(8.1, abs=0.05)

    again = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "onewire"), context={"source": config_entries.SOURCE_USER}
    )
    assert again["type"] is FlowResultType.ABORT
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_victron_modules(hass: HomeAssistant, hardware, monkeypatch, freezer) -> None:
    from datetime import timedelta

    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    monkeypatch.setattr(victron, "SerialReader", FakeReader)
    with patch("os.path.exists", return_value=True):
        entry = await setup_entry(hass)
        r1 = await add_subentry(
            hass, entry, "victron",
            [{"device_type": "shunt", "port": "/dev/ttyAMA5", "scan_interval": 5}],
        )
        r2 = await add_subentry(
            hass, entry, "victron",
            [{"device_type": "mppt", "port": "/dev/ttyAMA4", "scan_interval": 5}],
        )
    assert r1["title"] == "SmartShunt" and r2["title"] == "MPPT"
    freezer.tick(timedelta(seconds=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert float(hass.states.get("sensor.smartshunt_batteriespannung").state) == 13.31
    assert float(hass.states.get("sensor.smartshunt_ladezustand").state) == 95.6
    assert float(hass.states.get("sensor.smartshunt_maximale_spannung_starter").state) == 14.619
    assert hass.states.get("sensor.smartshunt_restlaufzeit").state == "unknown"
    assert hass.states.get("sensor.smartshunt_gerat").state == "SmartShunt 500A/50mV"
    assert hass.states.get("binary_sensor.smartshunt_alarm").state == "off"

    assert float(hass.states.get("sensor.mppt_pv_leistung").state) == 19
    assert float(hass.states.get("sensor.mppt_maximale_leistung_heute").state) == 52
    assert float(hass.states.get("sensor.mppt_ertrag_gestern").state) == 0.13
    assert hass.states.get("sensor.mppt_ladestatus").state == "Bulk"
    assert hass.states.get("binary_sensor.mppt_lastausgang").state == "on"
    assert hass.states.get("sensor.mppt_gerat").state == "SmartSolar MPPT 100/30"

    # Keine Daten mehr -> nach 30 s nicht verfügbar
    freezer.tick(timedelta(seconds=40))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.mppt_pv_leistung").state == "unavailable"
    assert hass.states.get("sensor.mppt_gerat").state == "Keine Daten"

    # Gleicher Port ein zweites Mal wird abgelehnt
    with patch("os.path.exists", return_value=True):
        dup = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "victron"), context={"source": config_entries.SOURCE_USER}
        )
        dup = await hass.config_entries.subentries.async_configure(
            dup["flow_id"], {"device_type": "shunt", "port": "/dev/ttyAMA5", "scan_interval": 5}
        )
    assert dup["errors"] == {"port": "already_configured"}
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_modules_survive_restart(hass: HomeAssistant, hardware) -> None:
    entry = await setup_entry(hass)
    await add_subentry(
        hass, entry, "tank",
        [{"name": "Frischwasser", "channel": "2", "unit": "L",
          "curve": "0:0, 2.5:100", "divider_ratio": 1,
          "scan_interval": 5, "address": "0x48"}],
    )
    assert await hass.config_entries.async_reload(entry.entry_id)
    await asyncio.sleep(0.05)
    await hass.async_block_till_done()
    assert float(hass.states.get("sensor.frischwasser_fullstand").state) == pytest.approx(40, abs=0.5)
    assert await hass.config_entries.async_unload(entry.entry_id)
