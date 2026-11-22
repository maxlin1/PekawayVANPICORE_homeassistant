"""Ersatz-Hardware für Tests."""

from __future__ import annotations

from contextlib import contextmanager


class FakeMcpBus:
    """MCP23017 nach dem Einschalten (BANK=0), schaltet wie der echte auf BANK=1 um."""

    def __init__(self) -> None:
        self.bank = 0
        self.regs = {r: 0 for r in range(0x20)}
        self.regs[0x00] = self.regs[0x10] = 0xFF  # IODIR: alles Eingang
        self.pins_in = 0xFF  # Eingänge offen (Pull-up -> high)

    def _map(self, reg: int) -> int | None:
        if self.bank == 1:
            return reg if (reg & 0x0F) <= 0x0A else None
        # BANK=0: A/B abwechselnd -> auf BANK=1-Adressen umrechnen
        if reg > 0x15:
            return None
        return (reg >> 1) | (0x10 if reg & 1 else 0)

    def read_byte_data(self, addr: int, reg: int) -> int:
        m = self._map(reg)
        if m is None:
            return 0
        if m == 0x09:
            return self.pins_in
        if m == 0x19:
            return self.regs[0x1A]
        if m in (0x05, 0x15):
            return 0x80 if self.bank else 0
        return self.regs[m]

    def write_byte_data(self, addr: int, reg: int, value: int) -> None:
        m = self._map(reg)
        if m is None:
            return
        if m in (0x05, 0x15):
            self.bank = 1 if value & 0x80 else 0
            return
        self.regs[m] = value

    def read_byte(self, addr: int) -> int:
        return 0


class FakeAdsBus:
    def __init__(self, volts: dict[int, float]) -> None:
        self.volts = volts
        self.config = 0x8583
        self.hijack_once = False

    def write_i2c_block_data(self, addr: int, reg: int, data: list[int]) -> None:
        self.config = (data[0] << 8) | data[1]

    def read_i2c_block_data(self, addr: int, reg: int, n: int) -> list[int]:
        if reg == 0x01:
            value = self.config | 0x8000
            if self.hijack_once:
                # die alte Komponente schaltet dazwischen auf einen anderen Kanal
                self.hijack_once = False
                value = (value & ~0x7000) | ((((value >> 12) & 7) % 4 + 4 + 1) % 4 + 4) << 12
                self.config = value
            return [value >> 8, value & 0xFF]
        ain = ((self.config >> 12) & 7) - 4
        raw = int(self.volts.get(ain, 0.0) / 4.096 * 32768)
        return [(raw >> 8) & 0xFF, raw & 0xFF]

    def read_byte(self, addr: int) -> int:
        return 0


@contextmanager
def bus_cm(bus):
    yield bus
