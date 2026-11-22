"""ADS1115-Treiber für die Tankeingänge des VAN PI CORE.

Einzelmessung, Messbereich ±4,096 V, 128 Messungen/s (wie die alte
Komponente `ads_waterlevel`). Nach jeder Messung wird geprüft, ob im
Konfigurationsregister noch unser Kanal steht. Liest parallel noch die alte
Komponente denselben Baustein, wird ein vermischter Wert so verworfen und
die Messung wiederholt.

Alle Methoden blockieren und laufen im Executor.
"""

from __future__ import annotations

import statistics
import time

from .i2c import i2c_bus

REG_CONV = 0x00
REG_CONFIG = 0x01
MUX_SINGLE = {0: 0x4000, 1: 0x5000, 2: 0x6000, 3: 0x7000}
MUX_MASK = 0x7000
OS_BIT = 0x8000
PGA_4V096 = 0x0200
MODE_SINGLE = 0x0100
DR_128SPS = 0x0080
COMP_DISABLE = 0x0003
FULL_SCALE_V = 4.096
CONVERSION_TIME = 0.009


class AdsReadError(OSError):
    pass


class ADS1115:
    def __init__(self, bus: int, address: int) -> None:
        self.bus_no = bus
        self.address = address

    def _read_config(self, bus) -> int:
        hi, lo = bus.read_i2c_block_data(self.address, REG_CONFIG, 2)
        return (hi << 8) | lo

    def _single(self, ain: int) -> float:
        cfg = OS_BIT | MUX_SINGLE[ain] | PGA_4V096 | MODE_SINGLE | DR_128SPS | COMP_DISABLE
        with i2c_bus(self.bus_no) as bus:
            bus.write_i2c_block_data(self.address, REG_CONFIG, [cfg >> 8, cfg & 0xFF])
            deadline = time.monotonic() + 0.1
            time.sleep(CONVERSION_TIME)
            while True:
                status = self._read_config(bus)
                if status & OS_BIT:
                    break
                if time.monotonic() > deadline:
                    raise AdsReadError("ADS1115: Messung nicht fertig")
                time.sleep(0.002)
            hi, lo = bus.read_i2c_block_data(self.address, REG_CONV, 2)
            after = self._read_config(bus)
        if (status & MUX_MASK) != MUX_SINGLE[ain] or (after & MUX_MASK) != MUX_SINGLE[ain]:
            raise AdsReadError("ADS1115: Kanal wurde während der Messung umgeschaltet")
        raw = (hi << 8) | lo
        if raw > 0x7FFF:
            raw -= 0x10000
        return max(0.0, raw * FULL_SCALE_V / 32768.0)

    def read_voltage(self, ain: int, samples: int = 3, retries: int = 3) -> float:
        """Median aus mehreren Einzelmessungen in Volt am ADS-Eingang."""
        values: list[float] = []
        errors = 0
        while len(values) < samples:
            try:
                values.append(self._single(ain))
            except AdsReadError:
                errors += 1
                if errors > retries:
                    raise
                time.sleep(0.02)
        return statistics.median(values)
