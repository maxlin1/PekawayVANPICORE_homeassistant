import logging
import asyncio
from homeassistant.components.switch import SwitchEntity

_LOGGER = logging.getLogger(__name__)

class CustomSwitch(SwitchEntity):
    def __init__(self, name, manager):
        self._name = name
        self._is_on = False
        self._manager = manager

    @property
    def name(self):
        return self._name

    @property
    def is_on(self):
        return self._is_on

    def turn_on(self, **kwargs):
        self._is_on = True
        #self._manager.start()
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        self._is_on = False
        #self._manager.stop()
        self.schedule_update_ha_state()

    @property
    def unique_id(self):
        return "mpu6050_switch"

    @property
    def icon(self):
        return "mdi:power"

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    # Versucht alle 2 Sekunden, den manager zu laden, bis zu 5 Mal (insgesamt 10 Sekunden)
    for attempt in range(5):
        manager = hass.data.get("mpu6050_sensor_manager")
        if manager:
            custom_switch = CustomSwitch("Schalte Ausrichtung Ein", manager)
            async_add_entities([custom_switch])
            _LOGGER.info("MPU6050 Custom Switch erfolgreich hinzugefügt.")
            return
        else:
            _LOGGER.warning(f"Versuch {attempt+1}: MPU6050 Sensor Manager nicht gefunden, erneuter Versuch in 2 Sekunden...")
            await asyncio.sleep(2)

    _LOGGER.error("MPU6050 Sensor Manager konnte nicht gefunden werden. Switch wird nicht hinzugefügt.")
