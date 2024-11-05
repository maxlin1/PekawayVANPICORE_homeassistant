import logging
import math
import time
import threading
import json
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from collections import deque
from homeassistant.components.sensor import SensorEntity
from smbus2 import SMBus
from homeassistant.helpers.event import async_track_state_change_event

_LOGGER = logging.getLogger(__name__)

# MPU6050-Register
MPU6050_ADDR = 0x69
MPU6050_PWR_MGMT_1 = 0x6B
MPU6050_ACCEL_XOUT_H = 0x3B
MPU6050_ACCEL_YOUT_H = 0x3D
MPU6050_GYRO_XOUT_H = 0x43
MPU6050_GYRO_YOUT_H = 0x45

CALIBRATION_FILE = os.path.join(os.path.dirname(__file__), "mpu6050_calibration.json")
bus = SMBus(1)

class MPU6050AngleSensor(SensorEntity):
    def __init__(self, name, sensor_type):
        self._name = name
        self._sensor_type = sensor_type
        self._state = None
        self._attr_force_update = True
        self._attr_should_poll = True
        _LOGGER.debug(f"MPU6050AngleSensor {name} initialisiert.")

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def unique_id(self):
        return f"mpu6050_{self._sensor_type}"

    def update_state(self, value):
        self._state = round(value, 2)
        _LOGGER.debug(f"{self._sensor_type} Zustand auf {self._state} aktualisiert.")
        self.hass.add_job(self.async_write_ha_state)

class MPU6050SensorManager:
    def __init__(self, hass, sensors, target_interval=5):
        self.hass = hass
        self.sensors = sensors
        self._stop_event = threading.Event()
        self._thread = None
        self.target_interval = target_interval

        self.accel_x_window = deque(maxlen=20)
        self.accel_y_window = deque(maxlen=20)

        # Kalibrierungsdaten asynchron laden
        loop = asyncio.get_running_loop()
        loop.create_task(self.load_calibration_async())

        # Registrieren des Listeners für den Switch-Zustand
        async_track_state_change_event(
            self.hass, "switch.schalte_ausrichtung_ein", self.switch_listener
        )

        _LOGGER.info("MPU6050SensorManager initialisiert.")
        switch_state = hass.states.get("switch.schalte_ausrichtung_ein")
        if switch_state and switch_state.state == "on":
            self.start()

    async def load_calibration_async(self):
        def load_calibration():
            if os.path.exists(CALIBRATION_FILE):
                try:
                    with open(CALIBRATION_FILE, "r") as file:
                        calibration_data = json.load(file)
                        return calibration_data.get("x_offset", 0.0), calibration_data.get("y_offset", 0.0)
                except Exception as e:
                    _LOGGER.error(f"Fehler beim Laden der Kalibrierungsdaten: {e}")
            _LOGGER.info("Keine gespeicherten Kalibrierungsdaten gefunden. Standardwerte werden verwendet.")
            return 0.0, 0.0

        loop = asyncio.get_running_loop()
        x_offset, y_offset = await loop.run_in_executor(None, load_calibration)
        self.x_offset, self.y_offset = x_offset, y_offset
        _LOGGER.info("Kalibrierungsdaten erfolgreich geladen.")

    def switch_listener(self, event):
        new_state = event.data.get("new_state")
        if new_state and new_state.state == "on":
            self.start()
        elif new_state and new_state.state == "off":
            self.stop()

    def start(self):
        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(target=self.read_sensor_data)
            self._thread.start()
            _LOGGER.info("MPU6050SensorManager gestartet.")
        else:
            _LOGGER.warning("Datenlese-Thread läuft bereits.")
            _LOGGER.warning(self._thread.is_alive())

    def stop(self):
        if self._thread is not None and self._thread.is_alive():
            self._stop_event.set()
            self._thread.join()
            self._thread = None
            _LOGGER.info("MPU6050SensorManager gestoppt.")

    def save_calibration(self, x_offset, y_offset):
        calibration_data = {
            "x_offset": x_offset,
            "y_offset": y_offset
        }
        try:
            with open(CALIBRATION_FILE, "w") as file:
                json.dump(calibration_data, file)
            _LOGGER.info("Kalibrierungsdaten erfolgreich gespeichert.")
        except Exception as e:
            _LOGGER.error(f"Fehler beim Speichern der Kalibrierungsdaten: {e}")

    def calibrate(self):
        try:
            _LOGGER.info("Kalibrierung wird gestartet...")
            accel_x_offset = 0
            accel_y_offset = 0
            num_samples = 300

            for _ in range(num_samples):
                accel_x_offset += read_raw_data(MPU6050_ACCEL_XOUT_H)
                accel_y_offset += read_raw_data(MPU6050_ACCEL_YOUT_H)
                time.sleep(0.01)

            accel_x_offset /= num_samples
            accel_y_offset /= num_samples

            self.save_calibration(accel_x_offset, accel_y_offset)

            # Korrekte Zuweisung der Offsets
            self.x_offset = accel_x_offset
            self.y_offset = accel_y_offset

            _LOGGER.info("Kalibrierung abgeschlossen. Offsets gespeichert.")
        except Exception as e:
            _LOGGER.error(f"Fehler bei der Kalibrierung: {e}")

    def read_sensor_data(self):
        try:
            bus.write_byte_data(MPU6050_ADDR, MPU6050_PWR_MGMT_1, 0)
        except Exception as e:
            _LOGGER.error(f"Fehler bei der Initialisierung des MPU6050: {e}")
            return

        angle_x, angle_y = 0.0, 0.0

        while not self._stop_event.is_set():
            switch_state = self.hass.states.get("switch.schalte_ausrichtung_ein")
            if switch_state is None or switch_state.state == "off":
                _LOGGER.info("Schalter ist aus; Sensor-Updates sind pausiert.")
                self._stop_event.wait(5)
                continue

            start_time = time.time()
            try:
                accel_x = read_raw_data(MPU6050_ACCEL_XOUT_H) - self.x_offset
                accel_y = read_raw_data(MPU6050_ACCEL_YOUT_H) - self.y_offset
                #accel_z = read_raw_data(MPU6050_ACCEL_XOUT_H + 2)

                #gyro_x = read_raw_data(MPU6050_GYRO_XOUT_H) - self.x_offset
                #gyro_y = read_raw_data(MPU6050_GYRO_YOUT_H) - self.y_offset

                #accel_angle_x = math.atan2(accel_y, math.sqrt(accel_x**2 + accel_z**2)) * (180 / math.pi)
                #accel_angle_y = math.atan2(-accel_x, math.sqrt(accel_y**2 + accel_z**2)) * (180 / math.pi)

                #dt = time.time() - start_time
                angle_x = math.atan(accel_x / 16384.0) * (180 / math.pi)
                angle_y = math.atan(accel_y / 16384.0) * (180 / math.pi)


                for sensor in self.sensors:
                    if sensor._sensor_type == "x_angle":
                        sensor.update_state(angle_x)
                    elif sensor._sensor_type == "y_angle":
                        sensor.update_state(angle_y)

                time.sleep(max(0, self.target_interval - (time.time() - start_time)))
            except Exception as e:
                _LOGGER.error(f"Fehler beim Lesen der Sensordaten: {e}",stack_info=True, exc_info=True)
                break

def read_raw_data(addr):
    try:
        high = bus.read_byte_data(MPU6050_ADDR, addr)
        low = bus.read_byte_data(MPU6050_ADDR, addr + 1)

        value = ((high << 8) | low)
        if value > 32768:
            value = value - 65536
        return value
    except Exception as e:
        _LOGGER.error(f"Fehler beim Lesen von Rohdaten von {addr}: {e}")
        return 0

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    sensors = [
        MPU6050AngleSensor("MPU6050 X Winkel", "x_angle"),
        MPU6050AngleSensor("MPU6050 Y Winkel", "y_angle")
    ]

    manager = MPU6050SensorManager(hass, sensors, target_interval=5)
    hass.data["mpu6050_sensor_manager"] = manager
    async_add_entities(sensors)

    _LOGGER.info("MPU6050 Sensor-Plattform erfolgreich eingerichtet.")
