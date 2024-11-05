import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import load_platform

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ads_waterlevel"

def setup(hass: HomeAssistant, config: dict):
    """Set up the ADS1115 Water Level component."""
    if DOMAIN not in config:
        return True

    # Lade die Sensor-Plattform gemäß den Konfigurationseinstellungen
    sensor_configs = config[DOMAIN].get("sensors", [])
    for sensor_config in sensor_configs:
        hass.data.setdefault(DOMAIN, []).append(sensor_config)

    # Lade die Sensor-Platform (sensor.py) für ads_waterlevel
    load_platform(hass, "sensor", DOMAIN, {}, config)

    _LOGGER.info("ADS1115 Water Level component geladen")
    return True
