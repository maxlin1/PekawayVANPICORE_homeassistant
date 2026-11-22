"""Konstanten der VAN PI CORE Integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "vanpi_core"
MANUFACTURER = "Pekaway"
MODEL = "VAN PI CORE"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Nivellierung: Winkelquelle
CONF_SOURCE = "source"
SOURCE_MPU6050 = "mpu6050"
SOURCE_ENTITIES = "entities"
CONF_I2C_BUS = "i2c_bus"
CONF_MPU_ADDRESS = "mpu_address"
CONF_ENTITY_X = "entity_x"
CONF_ENTITY_Y = "entity_y"
CONF_ENTITY_Z = "entity_z"

# Nivellierung: Ausrichtung
CONF_FORWARD = "forward"
FORWARD_DRIVE = "drive"  # aus Fahrt-Kalibrierung
FORWARD_AXES = ["+x", "-x", "+y", "-y", "+z", "-z"]

# Fahrzeug und Blöcke
CONF_WHEELBASE = "wheelbase"
CONF_TRACK = "track"
CONF_BLOCK_HEIGHT = "block_height"
CONF_STACKS = "stacks"
CONF_BLOCKS_PER_STACK = "blocks_per_stack"
CONF_TOLERANCE = "tolerance"
CONF_AUTO_OFF = "auto_off_minutes"

DEFAULTS = {
    CONF_SOURCE: SOURCE_MPU6050,
    CONF_I2C_BUS: 1,
    CONF_MPU_ADDRESS: 0x69,
    CONF_FORWARD: FORWARD_DRIVE,
    CONF_WHEELBASE: 350.0,
    CONF_TRACK: 170.0,
    CONF_BLOCK_HEIGHT: 2.1,
    CONF_STACKS: 2,
    CONF_BLOCKS_PER_STACK: 3,
    CONF_TOLERANCE: 1.0,
    CONF_AUTO_OFF: 15,
}

SAMPLE_INTERVAL = 0.05  # 20 Hz
PUBLISH_INTERVAL = 0.5  # höchstens 2 Updates pro Sekunde an HA
PUBLISH_MIN_CHANGE_DEG = 0.1
LEVEL_DEBOUNCE_S = 2.0
STORAGE_VERSION = 1
