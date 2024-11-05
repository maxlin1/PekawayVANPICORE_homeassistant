import json
import aiofiles
import os
from homeassistant.components.sensor import SensorEntity
from smbus2 import SMBus
import logging

_LOGGER = logging.getLogger(__name__)

class ADSWaterLevelVoltageSensor(SensorEntity):
    """Sensor für die Spannung (Volt)."""
    def __init__(self, name, channel, divider_ratio, mapping_file, water_level_sensor):
        self._name = f"{name} Voltage"
        self._channel = channel
        self._divider_ratio = divider_ratio
        self._mapping_file = mapping_file
        self._voltage = None
        self._water_level_sensor = water_level_sensor
        self._bus = SMBus(1)

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return f"{self._voltage} V" if self._voltage is not None else None

    @property
    def icon(self):
        return "mdi:flash"  # Icon für Volt

    def read_raw_value(self):
        try:
            raw_data = self._bus.read_i2c_block_data(0x48, self._channel, 2)
            return int.from_bytes(raw_data, byteorder="big")
        except Exception as e:
            _LOGGER.error(f"Fehler beim Lesen von Kanal {self._channel}: {e}")
            return None

    def calculate_voltage(self, raw_value):
        voltage = (raw_value * 3.3) / (32767 * self._divider_ratio)
        return round(voltage, 2)

    async def async_update(self):
        raw_value = self.read_raw_value()
        if raw_value is not None:
            self._voltage = self.calculate_voltage(raw_value)
            await self._water_level_sensor.update_liters(self._voltage)

class ADSWaterLevelSensor(SensorEntity):
    """Separate Entität für die Literangabe."""
    def __init__(self, name, mapping_file):
        self._name = f"{name} Level"
        self._mapping_file = mapping_file
        self._mapping = None
        self._state = None

    async def load_mapping(self):
        try:
            async with aiofiles.open(self._mapping_file, 'r') as f:
                data = await f.read()
                self._mapping = {float(k): v for k, v in json.loads(data).items()}
        except Exception as e:
            _LOGGER.error(f"Fehler beim Laden der Mapping-Datei {self._mapping_file}: {e}")

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return f"{self._state} L" if self._state is not None else None

    @property
    def icon(self):
        return "mdi:water"  # Icon für Liter

    def interpolate(self, voltage):
        if not self._mapping:
            return None
        keys = sorted(self._mapping.keys())
        for i, key in enumerate(keys):
            if voltage == key:
                return round(self._mapping[key], 2)
            elif voltage < key:
                if i == 0:
                    return round(self._mapping[key], 2)
                lower_key = keys[i - 1]
                upper_key = key
                lower_value = self._mapping[lower_key]
                upper_value = self._mapping[upper_key]
                interpolated_value = lower_value + (upper_value - lower_value) * ((voltage - lower_key) / (upper_key - lower_key))
                return round(interpolated_value, 2)
        return round(self._mapping[keys[-1]], 2)

    async def update_liters(self, voltage):
        self._state = self.interpolate(voltage)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    entities = []
    for sensor_config in config.get("sensors", []):
        water_level_sensor = ADSWaterLevelSensor(
            name=sensor_config["name"],
            mapping_file=sensor_config["mapping_file"]
        )
        await water_level_sensor.load_mapping()
        voltage_sensor = ADSWaterLevelVoltageSensor(
            name=sensor_config["name"],
            channel=sensor_config["channel"],
            divider_ratio=sensor_config["divider_ratio"],
            mapping_file=sensor_config["mapping_file"],
            water_level_sensor=water_level_sensor
        )
        entities.append(voltage_sensor)
        entities.append(water_level_sensor)
    async_add_entities(entities)
