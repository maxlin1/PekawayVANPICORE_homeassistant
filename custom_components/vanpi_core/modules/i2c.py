"""Gemeinsamer I2C-Zugriff: ein SMBus-Objekt und eine Sperre je Bus.

Die Sperre gilt zwischen den Modulen dieser Integration. Alle Funktionen
blockieren und laufen im Executor.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

from smbus2 import SMBus


class _Bus:
    def __init__(self, bus_no: int) -> None:
        self.bus_no = bus_no
        self.lock = threading.Lock()
        self.smbus: SMBus | None = None


_buses: dict[int, _Bus] = {}
_registry_lock = threading.Lock()


@contextmanager
def i2c_bus(bus_no: int) -> Iterator[SMBus]:
    with _registry_lock:
        entry = _buses.setdefault(bus_no, _Bus(bus_no))
    with entry.lock:
        if entry.smbus is None:
            entry.smbus = SMBus(bus_no)
        try:
            yield entry.smbus
        except OSError:
            # Beim nächsten Zugriff neu öffnen (z. B. nach einer Busstörung)
            try:
                entry.smbus.close()
            finally:
                entry.smbus = None
            raise


def probe(bus_no: int, address: int) -> bool:
    try:
        with i2c_bus(bus_no) as bus:
            bus.read_byte(address)
    except OSError:
        return False
    return True
