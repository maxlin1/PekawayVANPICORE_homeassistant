"""Schaltbare Pull-ups der Tankeingänge (sysfs-GPIO).

Der VAN PI CORE hat auf den ADS1115-Eingängen schaltbare 47-kΩ-Pull-ups
nach 3,3 V (U5, 74LVC2G66). Ein GPIO schaltet immer ein Kanalpaar:

* BCM-GPIO 19 -> Tankeingang 1 und 2
* BCM-GPIO 16 -> Tankeingang 3 und 4

HIGH = Pull-up an (Widerstandsgeber), LOW = aus (Spannung / kapazitiv).
Im HA-Container funktionieren RPi.GPIO, lgpio und gpiod nicht zuverlässig,
sysfs dagegen schon. Die sysfs-Nummer ist Basis des SoC-gpiochips + BCM-Nummer
(Pi 4 mit aktuellem Kernel: 512 + n). Die Basis wird gelesen, nicht geraten.
"""

from __future__ import annotations

import glob
import os
import time

SYSFS_GPIO = "/sys/class/gpio"
PULLUP_GPIO = {1: 19, 2: 19, 3: 16, 4: 16}
# Labels der SoC-GPIO-Controller (Pi 3/4, Pi 5)
_SOC_LABELS = ("pinctrl-bcm2711", "pinctrl-bcm2835", "pinctrl-rp1", "raspberrypi-exp-gpio")


class GpioError(OSError):
    """sysfs-GPIO nicht nutzbar."""


def pair_of(channel: int) -> tuple[int, int]:
    """Die beiden Kanäle, die sich einen Pull-up-Schalter teilen."""
    return (1, 2) if channel in (1, 2) else (3, 4)


def _read(path: str) -> str:
    with open(path, encoding="ascii") as f:
        return f.read().strip()


def _write(path: str, value: str) -> None:
    with open(path, "w", encoding="ascii") as f:
        f.write(value)


def soc_base(root: str = SYSFS_GPIO) -> int:
    """Basisnummer des SoC-gpiochips in sysfs."""
    chips = []
    for chip in glob.glob(os.path.join(root, "gpiochip*")):
        try:
            label = _read(os.path.join(chip, "label"))
            base = int(_read(os.path.join(chip, "base")))
            ngpio = int(_read(os.path.join(chip, "ngpio")))
        except (OSError, ValueError):
            continue
        chips.append((label, base, ngpio))
    for wanted in _SOC_LABELS[:3]:
        for label, base, _ in chips:
            if label == wanted:
                return base
    # Fallback: größter Controller (der SoC hat 54-58 Leitungen)
    big = [c for c in chips if c[2] >= 54]
    if big:
        return min(big, key=lambda c: c[1])[1]
    raise GpioError(f"kein SoC-gpiochip unter {root} gefunden")


def set_pullup(channel: int, on: bool, root: str = SYSFS_GPIO) -> int:
    """Pull-up für das Kanalpaar von `channel` setzen. Gibt die sysfs-Nummer zurück."""
    pin = soc_base(root) + PULLUP_GPIO[channel]
    node = os.path.join(root, f"gpio{pin}")
    try:
        if not os.path.isdir(node):
            _write(os.path.join(root, "export"), str(pin))
            for _ in range(20):  # udev braucht einen Moment
                if os.path.isdir(node):
                    break
                time.sleep(0.05)
        _write(os.path.join(node, "direction"), "high" if on else "low")
        if _read(os.path.join(node, "value")) != ("1" if on else "0"):
            _write(os.path.join(node, "value"), "1" if on else "0")
    except OSError as err:
        raise GpioError(f"GPIO {pin} (BCM {PULLUP_GPIO[channel]}): {err}") from err
    return pin


def get_pullup(channel: int, root: str = SYSFS_GPIO) -> bool | None:
    """Aktueller Zustand oder None, wenn der Pin nicht exportiert ist."""
    try:
        pin = soc_base(root) + PULLUP_GPIO[channel]
        node = os.path.join(root, f"gpio{pin}")
        if _read(os.path.join(node, "direction")) != "out":
            return None
        return _read(os.path.join(node, "value")) == "1"
    except (OSError, GpioError):
        return None
