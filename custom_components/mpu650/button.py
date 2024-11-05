import logging
from homeassistant.components.button import ButtonEntity

_LOGGER = logging.getLogger(__name__)

class CustomButton(ButtonEntity):
    def __init__(self, name, manager):
        self._name = name
        self._manager = manager

    @property
    def name(self):
        return self._name

    def press(self):
        self._manager.calibrate()

    @property
    def unique_id(self):
        return "input_button.richte_auf_0_aus"

    @property
    def icon(self):
        return "mdi:play"

def setup_platform(hass, config, add_entities, discovery_info=None):
    manager = hass.data.get("mpu6050_sensor_manager")
    custom_button = CustomButton("Richte Auf 0 Aus", manager)
    add_entities([custom_button])
