"""Konstanten der VAN PI CORE Integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "vanpi_core"
DOCS_URL = (
    "https://github.com/maxlin1/PekawayVANPICORE_homeassistant/blob/main/docs/nivellierung.md"
)
MANUFACTURER = "Pekaway"
MODEL = "VAN PI CORE"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Nivellierung ist ein eigener Eintrag (Subentry) unter VAN PI CORE
SUBENTRY_LEVELING = "leveling"

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
# Luftfederung hinten (links/rechts getrennt verstellbar)
CONF_AIR_SUSPENSION = "air_suspension"
CONF_AIR_UP = "air_up"
CONF_AIR_DOWN = "air_down"

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
    CONF_AIR_SUSPENSION: False,
    CONF_AIR_UP: 2.0,
    CONF_AIR_DOWN: 2.0,
}

# Nur diese Schlüssel gehören zur Nivellierung (alte Optionen wie
# auto_off_minutes werden bei der Migration verworfen)
LEVELING_KEYS = (
    CONF_SOURCE, CONF_I2C_BUS, CONF_MPU_ADDRESS, CONF_ENTITY_X, CONF_ENTITY_Y,
    CONF_ENTITY_Z, CONF_FORWARD, CONF_WHEELBASE, CONF_TRACK, CONF_BLOCK_HEIGHT,
    CONF_STACKS, CONF_BLOCKS_PER_STACK, CONF_TOLERANCE,
    CONF_AIR_SUSPENSION, CONF_AIR_UP, CONF_AIR_DOWN,
)

AUTO_OFF_MINUTES = 15  # fest, Nivellierung schaltet sich danach selbst ab
SAMPLE_INTERVAL = 0.05  # 20 Hz
PUBLISH_INTERVAL = 0.5  # höchstens 2 Updates pro Sekunde an HA
PUBLISH_MIN_CHANGE_DEG = 0.1
LEVEL_DEBOUNCE_S = 2.0
STORAGE_VERSION = 1
