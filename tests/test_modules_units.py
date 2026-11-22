"""Rechenteile der Board-Module: VE.Direct, Kennlinie, 1-Wire, ADS1115."""

from __future__ import annotations

import pytest

from custom_components.vanpi_core.modules.curve import (
    CurveError,
    interpolate,
    parse_curve,
)
from custom_components.vanpi_core.modules.onewire import discover, read_temperature
from custom_components.vanpi_core.modules.vedirect import (
    VEDirectParser,
    convert,
    product_name,
)


def make_block(fields: list[tuple[str, str]]) -> bytes:
    body = b"".join(b"\r\n" + k.encode() + b"\t" + v.encode() for k, v in fields)
    body += b"\r\nChecksum\t"
    checksum = (256 - sum(body) % 256) % 256
    return body + bytes([checksum])


SHUNT = [("PID", "0xA389"), ("V", "13310"), ("I", "-210"), ("SOC", "956"), ("H15", "-15"),
         ("H16", "14619"), ("H6", "-20779140"), ("TTG", "-1"), ("AR", "0"), ("Alarm", "OFF")]


def test_parser_valid_block_in_chunks() -> None:
    parser = VEDirectParser()
    data = make_block(SHUNT) * 2
    blocks = []
    for i in range(0, len(data), 7):
        blocks += parser.feed(data[i : i + 7])
    assert len(blocks) == 2
    assert blocks[0]["V"] == "13310"
    assert parser.bad_blocks == 0


def test_parser_rejects_bad_checksum_and_recovers() -> None:
    parser = VEDirectParser()
    bad = bytearray(make_block(SHUNT))
    bad[10] ^= 0x01
    assert parser.feed(bytes(bad)) == []
    assert parser.bad_blocks == 1
    assert len(parser.feed(make_block(SHUNT))) == 1


def test_parser_skips_hex_frames() -> None:
    parser = VEDirectParser()
    block = make_block(SHUNT)
    mixed = block[:20] + b":A0102000543\n" + block[20:]
    assert len(parser.feed(mixed)) == 1


def test_conversions() -> None:
    assert convert("mv", "13310") == 13.31
    assert convert("mv", "14619") == 14.619  # H16 Starter max, mV laut Spezifikation
    assert convert("mah", "-20779140") == -20779.14  # H6 kumulierte Ah
    assert convert("permille", "956") == 95.6
    assert convert("ttg", "-1") is None
    assert convert("ttg", "90") == 1.5
    assert convert("10wh", "25225") == 252.25
    assert convert("cs", "3") == "Bulk"
    assert convert("cs", "99") == "Code 99"
    assert convert("or", "0x00000000") == "Kein Grund"
    assert convert("or", "0x00000001") == "Keine Eingangsleistung"
    assert convert("ar", "5") == "Unterspannung, Niedriger Ladezustand"
    assert convert("onoff", "ON") is True
    assert convert("mv", "---") is None
    assert product_name("0xA056") == "SmartSolar MPPT 100/30"
    assert product_name("0xFFFF") == "Victron 0xFFFF"


def test_curve() -> None:
    pts = parse_curve("0:0, 0.49:50, 1.6:100")
    assert interpolate(pts, 0.245) == pytest.approx(25)
    assert interpolate(pts, 2.0) == 100
    assert parse_curve("0,5:10; 1,0:20") == [(0.5, 10.0), (1.0, 20.0)]
    with pytest.raises(CurveError):
        parse_curve("0:0")
    with pytest.raises(CurveError):
        parse_curve("abc")


def test_onewire_read(tmp_path) -> None:
    sensor = tmp_path / "28-0000012345ab"
    sensor.mkdir()
    (tmp_path / "w1_bus_master1").mkdir()
    (sensor / "w1_slave").write_text(
        "72 01 4b 46 7f ff 0e 10 57 : crc=57 YES\n72 01 4b 46 7f ff 0e 10 57 t=23125\n"
    )
    assert discover(str(tmp_path)) == ["28-0000012345ab"]
    assert read_temperature(str(sensor / "w1_slave")) == pytest.approx(23.125, abs=0.01)
    (sensor / "w1_slave").write_text("72 01 : crc=57 NO\n72 01 t=23125\n")
    with pytest.raises(OSError):
        read_temperature(str(sensor / "w1_slave"), retries=1)
    (sensor / "w1_slave").write_text("50 05 : crc=57 YES\n50 05 t=85000\n")
    with pytest.raises(OSError):
        read_temperature(str(sensor / "w1_slave"), retries=1)


def test_mcp23017_driver(monkeypatch) -> None:
    from custom_components.vanpi_core.modules import mcp23017 as mod

    from .fakes import FakeMcpBus, bus_cm

    bus = FakeMcpBus()
    monkeypatch.setattr(mod, "i2c_bus", lambda n: bus_cm(bus))
    chip = mod.MCP23017(1, 0x20)
    chip.setup(list(range(8)), list(range(8, 16)), reset_outputs=False)
    assert bus.bank == 1
    assert bus.regs[0x10] == 0x00  # Port B Ausgang
    assert bus.regs[0x00] == 0xFF and bus.regs[0x06] == 0xFF  # Port A Eingang + Pull-up
    # Relais 5 (Pin 12) an, Relais 1 von "außen" (alte Komponente) gesetzt
    bus.regs[0x1A] = 0x01
    chip.set_output(12, True)
    assert bus.regs[0x1A] == 0x11  # Relais 1 bleibt erhalten
    bus.pins_in = 0xFE
    gpio, olat = chip.read_state()
    assert gpio & 0xFF == 0xFE and olat >> 8 == 0x11
    # Zweiter Start (BANK schon 1) funktioniert genauso
    chip.setup(list(range(8)), list(range(8, 16)), reset_outputs=True)
    assert bus.regs[0x1A] == 0x00


def test_ads1115_driver(monkeypatch) -> None:
    from custom_components.vanpi_core.modules import ads1115 as mod

    from .fakes import FakeAdsBus, bus_cm

    bus = FakeAdsBus({0: 0.49, 1: 2.5})
    monkeypatch.setattr(mod, "i2c_bus", lambda n: bus_cm(bus))
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    ads = mod.ADS1115(1, 0x48)
    assert ads.read_voltage(0) == pytest.approx(0.49, abs=0.001)
    assert ads.read_voltage(1) == pytest.approx(2.5, abs=0.001)
    # Kanalwechsel durch einen zweiten Leser wird erkannt und wiederholt
    bus.hijack_once = True
    assert ads.read_voltage(1) == pytest.approx(2.5, abs=0.001)
