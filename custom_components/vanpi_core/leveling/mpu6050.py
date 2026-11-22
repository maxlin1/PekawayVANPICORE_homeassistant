"""Minimaler MPU6050-Treiber (nur Beschleunigung) über smbus2.

Alle Methoden blockieren und müssen im Executor laufen.
"""

from __future__ import annotations

import logging

from smbus2 import SMBus

_LOGGER = logging.getLogger(__name__)

REG_PWR_MGMT_1 = 0x6B
REG_ACCEL_CONFIG = 0x1C
REG_CONFIG = 0x1A
REG_ACCEL_XOUT_H = 0x3B
REG_WHO_AM_I = 0x75

SLEEP_BIT = 0x40
CLOCK_PLL_X = 0x01
LSB_PER_G = 16384.0  # Messbereich +-2 g
DLPF_21HZ = 0x04  # interner Tiefpass ca. 21 Hz, glättet Vibrationen


class MPU6050:
    def __init__(self, bus: int, address: int) -> None:
        self._bus_no = bus
        self._address = address
        self._bus: SMBus | None = None

    def open(self) -> None:
        if self._bus is None:
            self._bus = SMBus(self._bus_no)

    def close(self) -> None:
        if self._bus is not None:
            self._bus.close()
            self._bus = None

    def probe(self) -> bool:
        """Prüft, ob ein MPU6050 (oder kompatibel) antwortet."""
        try:
            self.open()
            assert self._bus is not None
            self._bus.read_byte_data(self._address, REG_WHO_AM_I)
        except OSError:
            self.close()
            return False
        return True

    def wake(self) -> None:
        self.open()
        assert self._bus is not None
        self._bus.write_byte_data(self._address, REG_PWR_MGMT_1, CLOCK_PLL_X)
        self._bus.write_byte_data(self._address, REG_CONFIG, DLPF_21HZ)
        self._bus.write_byte_data(self._address, REG_ACCEL_CONFIG, 0x00)

    def sleep(self) -> None:
        """Schlafmodus: Sensor misst nicht mehr, kaum Stromverbrauch."""
        try:
            self.open()
            assert self._bus is not None
            self._bus.write_byte_data(self._address, REG_PWR_MGMT_1, SLEEP_BIT)
        except OSError as err:
            _LOGGER.debug("MPU6050 Schlafmodus nicht gesetzt: %s", err)
        finally:
            self.close()

    def read_accel(self) -> tuple[float, float, float]:
        """Beschleunigung in g (x, y, z) in einem I2C-Lesevorgang."""
        assert self._bus is not None
        raw = self._bus.read_i2c_block_data(self._address, REG_ACCEL_XOUT_H, 6)

        def s16(hi: int, lo: int) -> int:
            v = (hi << 8) | lo
            return v - 0x10000 if v >= 0x8000 else v

        return (
            s16(raw[0], raw[1]) / LSB_PER_G,
            s16(raw[2], raw[3]) / LSB_PER_G,
            s16(raw[4], raw[5]) / LSB_PER_G,
        )
