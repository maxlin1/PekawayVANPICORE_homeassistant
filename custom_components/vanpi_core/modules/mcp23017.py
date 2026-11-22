"""MCP23017-Treiber für die Relais und Eingänge des VAN PI CORE.

Kompatibel zur alten Komponente `mcp23017`: Der Baustein wird in den
Registermodus IOCON.BANK=1 geschaltet (Port A ab 0x00, Port B ab 0x10).
Ausgänge werden immer frisch vom Chip gelesen und dann geändert (kein Cache).
So überschreibt diese Integration keine Relais, die gleichzeitig noch von der
alten Komponente geschaltet werden.

Alle Methoden blockieren und laufen im Executor.
"""

from __future__ import annotations

from .i2c import i2c_bus

# Register im BANK=1-Modus, Offset je Port (A = 0x00, B = 0x10)
IODIR = 0x00
GPPU = 0x06
GPIO = 0x09
OLAT = 0x0A
IOCON_BANK1 = 0x05
IOCON_BANK0 = 0x0B  # nur im BANK=0-Modus belegt
BANK_BIT = 0x80
PORT_B = 0x10


def _reg(register: int, pin: int) -> tuple[int, int]:
    """Registeradresse und Bitmaske für einen Pin 0-15."""
    if pin < 8:
        return register, 1 << pin
    return register + PORT_B, 1 << (pin - 8)


class MCP23017:
    def __init__(self, bus: int, address: int) -> None:
        self.bus_no = bus
        self.address = address

    def _update_bits(self, bus, register: int, mask: int, value: bool) -> None:
        old = bus.read_byte_data(self.address, register)
        new = (old | mask) if value else (old & ~mask & 0xFF)
        if new != old:
            bus.write_byte_data(self.address, register, new)

    def setup(self, input_pins: list[int], output_pins: list[int], reset_outputs: bool) -> None:
        with i2c_bus(self.bus_no) as bus:
            # In BANK=1 schalten. Ist er schon in BANK=1, ist 0x0B unbelegt
            # (liest 0, Schreiben wird ignoriert).
            iocon = bus.read_byte_data(self.address, IOCON_BANK0)
            bus.write_byte_data(self.address, IOCON_BANK0, iocon | BANK_BIT)
            if not bus.read_byte_data(self.address, IOCON_BANK1) & BANK_BIT:
                raise OSError("MCP23017 lässt sich nicht in den BANK=1-Modus schalten")
            for pin in input_pins:
                reg, mask = _reg(IODIR, pin)
                self._update_bits(bus, reg, mask, True)
                reg, mask = _reg(GPPU, pin)
                self._update_bits(bus, reg, mask, True)
            for pin in output_pins:
                if reset_outputs:
                    reg, mask = _reg(OLAT, pin)
                    self._update_bits(bus, reg, mask, False)
                reg, mask = _reg(IODIR, pin)
                self._update_bits(bus, reg, mask, False)

    def read_state(self) -> tuple[int, int]:
        """Liefert (Eingänge GPIO, Ausgänge OLAT) als je 16 Bit."""
        with i2c_bus(self.bus_no) as bus:
            gpio_a = bus.read_byte_data(self.address, GPIO)
            gpio_b = bus.read_byte_data(self.address, GPIO + PORT_B)
            olat_a = bus.read_byte_data(self.address, OLAT)
            olat_b = bus.read_byte_data(self.address, OLAT + PORT_B)
        return gpio_a | (gpio_b << 8), olat_a | (olat_b << 8)

    def set_output(self, pin: int, value: bool) -> None:
        with i2c_bus(self.bus_no) as bus:
            reg, mask = _reg(OLAT, pin)
            self._update_bits(bus, reg, mask, value)
