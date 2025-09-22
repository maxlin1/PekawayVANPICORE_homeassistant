from __future__ import annotations

from datetime import timedelta
import json
import aiofiles
import logging
import os
import time
from typing import List, Tuple, Optional, Dict, Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfElectricPotential, UnitOfVolume
from homeassistant.helpers.entity import DeviceInfo
from smbus2 import SMBus

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=5)

# ---- ADS1115 ---------------------------------------------------------------
ADS_ADDR_DEFAULT = 0x48
REG_CONV   = 0x00
REG_CONFIG = 0x01

# Single-ended MUX AINx vs GND
MUX_MAP = {0: 0x4000, 1: 0x5000, 2: 0x6000, 3: 0x7000}

# PGA ±4.096 V → passt gut für 0–3.3V Signale
PGA_BITS    = 0x0200
PGA_RANGE_V = 4.096

# Single-shot, 128 SPS, Comparator disabled
OS_START     = 0x8000
MODE_SINGLE  = 0x0100
DR_128SPS    = 0x0080
COMP_DISABLE = 0x0003

def _build_cfg(channel: int) -> int:
    return OS_START | MUX_MAP[channel] | PGA_BITS | MODE_SINGLE | DR_128SPS | COMP_DISABLE

# ---- Hilfen ----------------------------------------------------------------
def ch_human_to_ain(ch: int) -> int:
    """
    Erlaubt channel: 1..4 (Board-Beschriftung) oder 0..3 (AIN direkt).
    """
    ch = int(ch)
    if 1 <= ch <= 4:
        return ch - 1         # 1→0, 2→1, 3→2, 4→3
    if 0 <= ch <= 3:
        return ch
    raise ValueError(f"Ungültiger channel: {ch}")

def build_linear_mapping(v_max: float, invert: bool, steps: int = 10) -> List[Tuple[float, float]]:
    """
    Baut eine lineare (V→L)-Kurve von 0..v_max → 0..100 L (oder invertiert).
    steps = Anzahl Intervalle (10 → 11 Stützpunkte).
    """
    pts: List[Tuple[float, float]] = []
    for i in range(steps + 1):
        v = round(v_max * i / steps, 3)
        l = round(100.0 * i / steps, 1)
        if invert:
            l = round(100.0 - l, 1)
        pts.append((v, l))
    return pts

def normalize_mapping_points(items: List[Dict[str, Any]], v_max: float, invert: bool) -> List[Tuple[float, float]]:
    """
    Erwartet Liste von {v: <volt>, l: <liter>} und sortiert diese.
    Ergänzt ggf. (0→0/100) und (v_max→100/0).
    """
    pts = []
    for it in items:
        v = float(it["v"]); l = float(it["l"])
        pts.append((v, l))
    pts.sort(key=lambda x: x[0])

    # Start/Ende erzwingen, falls nicht vorhanden
    have0 = any(abs(v) < 1e-6 for v, _ in pts)
    haveMax = any(abs(v - v_max) < 1e-6 for v, _ in pts)
    if not have0:
        pts = [ (0.0, 100.0 if invert else 0.0) ] + pts
    if not haveMax:
        pts = pts + [ (v_max, 0.0 if invert else 100.0) ]
    return pts

def interp(points: List[Tuple[float, float]], x: float) -> float:
    """
    Lineare Interpolation über sortierte (x→y)-Punkte.
    """
    if not points:
        return 0.0
    if x <= points[0][0]:
        return points[0][1]
    if x >= points[-1][0]:
        return points[-1][1]
    for i in range(1, len(points)):
        x0, y0 = points[i-1]; x1, y1 = points[i]
        if x0 <= x <= x1:
            if x1 == x0:
                return y0
            t = (x - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return points[-1][1]

# ---- Sensor-Entitäten ------------------------------------------------------
class ADSVoltageSensor(SensorEntity):
    _attr_device_class = "voltage"
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_state_class = "measurement"
    _attr_should_poll = True

    def __init__(self, base_name: str, ain: int, divider_ratio: float):
        self._base = base_name
        self._ain = ain
        self._ratio = float(divider_ratio or 1.0)
        self._bus = SMBus(1)
        self._addr = ADS_ADDR_DEFAULT
        self._last_vin: Optional[float] = None

        self._attr_name = f"{base_name} Voltage"
        self._attr_unique_id = f"ads_wl_v_{ain}_{base_name}"
        self._attr_device_info = DeviceInfo(
            identifiers={("ads_waterlevel", "ads1115")},
            name="ADS1115 Water Level",
            manufacturer="Custom",
            model="ADS1115"
        )

    def update(self) -> None:
        try:
            cfg = _build_cfg(self._ain)
            self._bus.write_i2c_block_data(self._addr, REG_CONFIG, [(cfg >> 8) & 0xFF, cfg & 0xFF])
            time.sleep(0.009)  # ~8 ms @128 SPS
            raw = self._bus.read_i2c_block_data(self._addr, REG_CONV, 2)
            val = (raw[0] << 8) | raw[1]
            if val > 0x7FFF:
                val -= 0x10000  # signed 16-bit

            v_adc = (val * PGA_RANGE_V) / 32768.0
            if v_adc < 0: v_adc = 0.0
            v_in = round(v_adc * self._ratio, 3)
            self._last_vin = v_in
            self._attr_native_value = round(v_in, 2)
        except Exception as e:
            _LOGGER.error("ADS1115 Read AIN%s fehlgeschlagen: %s", self._ain, e)
            self._attr_native_value = None
            self._last_vin = None

    def get_last_voltage(self) -> Optional[float]:
        return self._last_vin

class ADSLevelSensor(SensorEntity):
    _attr_native_unit_of_measurement = UnitOfVolume.LITERS
    _attr_state_class = "measurement"
    _attr_should_poll = True

    def __init__(self, base_name: str, voltage_sensor: ADSVoltageSensor,
                 mapping_points: List[Tuple[float, float]]):
        self._base = base_name
        self._vs = voltage_sensor
        self._map = mapping_points
        self._attr_name = f"{base_name} Level"
        self._attr_unique_id = f"ads_wl_l_{base_name}"

    def update(self) -> None:
        v = self._vs.get_last_voltage()
        if v is None:
            self._vs.update()
            v = self._vs.get_last_voltage()
        if v is None:
            self._attr_native_value = None
            return
        liters = interp(self._map, v)
        self._attr_native_value = round(liters, 1)

class ADSResistanceSensor(SensorEntity):
    """Nur bei mode: resistive – R aus Pull-Up berechnen."""
    _attr_native_unit_of_measurement = "Ω"
    _attr_state_class = "measurement"
    _attr_should_poll = True

    def __init__(self, base_name: str, voltage_sensor: ADSVoltageSensor, r_pullup: float, v_ref: float):
        self._base = base_name
        self._vs = voltage_sensor
        self._rpu = float(r_pullup or 47000.0)
        self._vref = float(v_ref or 3.3)
        self._attr_name = f"{base_name} Resistance"
        self._attr_unique_id = f"ads_wl_r_{base_name}"

    def update(self) -> None:
        v = self._vs.get_last_voltage()
        if v is None:
            self._vs.update()
            v = self._vs.get_last_voltage()
        if v is None or v >= self._vref:
            self._attr_native_value = None
            return
        r = self._rpu * (v / (self._vref - v))
        self._attr_native_value = round(r, 0)

# ---- Plattform-Setup -------------------------------------------------------
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    entities: List[SensorEntity] = []

    # Pair-Defaults (pro „1-2“ & „3-4“)
    pair_cfg: Dict[str, Dict[str, Any]] = config.get("pair_config", {})
    def defaults_for_channel_human(ch_human: int) -> Dict[str, Any]:
        pair_key = "1-2" if ch_human in (1,2) else "3-4"
        # Standardwerte:
        d = {
            "mode": "voltage",   # voltage | capacitive | resistive
            "v_max": 3.3,
            "invert": False,
            # "r_pullup_ohm": 47000, "v_ref": 3.3
        }
        d.update(pair_cfg.get(pair_key, {}))
        return d

    for s in config.get("sensors", []):
        name = s["name"]
        ch_human = int(s["channel"])  # 1..4 erlaubt
        ain = ch_human_to_ain(ch_human)

        # Pair-Defaults + Sensor-Overrides zusammenführen
        dfl = defaults_for_channel_human(ch_human)
        mode = s.get("mode", dfl["mode"])
        v_max = float(s.get("v_max", dfl.get("v_max", 3.3)))
        invert = bool(s.get("invert", dfl.get("invert", False)))
        divider_ratio = float(s.get("divider_ratio", 1.0))
        r_pullup = float(s.get("r_pullup_ohm", dfl.get("r_pullup_ohm", 47000)))
        v_ref = float(s.get("v_ref", dfl.get("v_ref", 3.3)))

        # Mapping-Punkte: entweder explizit aus YAML oder linear generieren
        mp_items = s.get("mapping_points")
        if mp_items:
            mapping = normalize_mapping_points(mp_items, v_max=v_max, invert=invert)
        else:
            mapping = build_linear_mapping(v_max=v_max, invert=invert, steps=10)

        # Entitäten erstellen
        v_ent = ADSVoltageSensor(name, ain, divider_ratio)
        l_ent = ADSLevelSensor(name, v_ent, mapping)
        entities.extend([v_ent, l_ent])

        if mode == "resistive":
            r_ent = ADSResistanceSensor(name, v_ent, r_pullup, v_ref)
            entities.append(r_ent)

        _LOGGER.debug(
            "Setup %s (CH%d→AIN%d): mode=%s v_max=%.2f invert=%s ratio=%.3f",
            name, ch_human, ain, mode, v_max, invert, divider_ratio
        )

    async_add_entities(entities)
