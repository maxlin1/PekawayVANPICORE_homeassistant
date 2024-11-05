import logging

_LOGGER = logging.getLogger(__name__)
_LOGGER.info("MPU6050 integration is initializing")

async def async_setup(hass, config):
    _LOGGER.debug("MPU6050 integration setup complete")
    return True

async def async_setup_entry(hass, entry):
    _LOGGER.info("MPU6050 integration setup from entry complete")
    return True
