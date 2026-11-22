"""VE.Direct-Textprotokoll (Victron MPPT, SmartShunt, BMV).

Ein Datenblock besteht aus Zeilen "\r\nLABEL\tWERT" und endet mit
"\r\nChecksum\t<Byte>". Die Summe aller Bytes eines Blocks ergibt 0 (mod 256).
Dazwischen können HEX-Nachrichten (":...\n") stehen, die nicht zur Prüfsumme
zählen und ignoriert werden. Blöcke mit falscher Prüfsumme werden verworfen.
"""

from __future__ import annotations

from collections.abc import Callable

_CR = 0x0D
_LF = 0x0A
_TAB = 0x09
_COLON = 0x3A
_MAX_FIELD = 64
_MAX_FIELDS = 40


class VEDirectParser:
    """Byteweiser Parser. `feed()` gibt vollständige, geprüfte Blöcke zurück."""

    WAIT, KEY, VALUE, CHECKSUM, HEX = range(5)

    def __init__(self) -> None:
        self._reset()
        self.bad_blocks = 0
        self.good_blocks = 0

    def _reset(self) -> None:
        self._state = self.WAIT
        self._sum = 0
        self._key = bytearray()
        self._value = bytearray()
        self._fields: dict[str, str] = {}
        self._before_hex = self.WAIT

    def feed(self, data: bytes) -> list[dict[str, str]]:
        blocks: list[dict[str, str]] = []
        for byte in data:
            block = self._byte(byte)
            if block is not None:
                blocks.append(block)
        return blocks

    def _byte(self, b: int) -> dict[str, str] | None:
        if self._state == self.HEX:
            if b == _LF:
                self._state = self._before_hex
            return None
        if b == _COLON and self._state != self.CHECKSUM:
            self._before_hex = self._state
            self._state = self.HEX
            return None

        self._sum = (self._sum + b) & 0xFF

        if self._state == self.WAIT:
            if b == _LF:
                self._state = self.KEY
                self._key.clear()
            return None
        if self._state == self.KEY:
            if b == _TAB:
                if self._key == b"Checksum":
                    self._state = self.CHECKSUM
                else:
                    self._state = self.VALUE
                    self._value.clear()
            elif b in (_CR, _LF) or len(self._key) > _MAX_FIELD:
                self._resync()
            else:
                self._key.append(b)
            return None
        if self._state == self.VALUE:
            if b == _CR:
                if len(self._fields) < _MAX_FIELDS:
                    key = self._key.decode("ascii", "replace")
                    self._fields[key] = self._value.decode("ascii", "replace")
                self._state = self.WAIT
            elif len(self._value) > _MAX_FIELD:
                self._resync()
            else:
                self._value.append(b)
            return None
        # CHECKSUM: dieses Byte gehört noch zur Summe
        fields = self._fields
        ok = self._sum == 0 and bool(fields)
        self._reset()
        if ok:
            self.good_blocks += 1
            return fields
        self.bad_blocks += 1
        return None

    def _resync(self) -> None:
        self.bad_blocks += 1
        self._reset()


# --- Umrechnung ----------------------------------------------------------


def _int(v: str) -> int:
    return int(v.strip())


def _scaled(factor: float, digits: int | None = None) -> Callable[[str], float]:
    def conv(v: str) -> float:
        value = _int(v) * factor
        return round(value, digits) if digits is not None else value

    return conv


def _text(v: str) -> str:
    return v.strip()


def _onoff(v: str) -> bool:
    return v.strip().upper() == "ON"


def _hex_int(v: str) -> int:
    v = v.strip()
    return int(v, 16) if v.lower().startswith("0x") else int(v)


def _ttg(v: str) -> float | None:
    minutes = _int(v)
    return None if minutes < 0 else round(minutes / 60, 2)


CS_STATES = {
    0: "Aus",
    1: "Niedrige Leistung",
    2: "Fehler",
    3: "Bulk",
    4: "Absorption",
    5: "Erhaltung (Float)",
    6: "Speicher",
    7: "Ausgleich (manuell)",
    9: "Wechselrichten",
    11: "Netzteil",
    245: "Startet",
    246: "Wiederholte Absorption",
    247: "Ausgleich (automatisch)",
    248: "BatterySafe",
    252: "Externe Steuerung",
}

MPPT_STATES = {0: "Aus", 1: "Spannungs-/Strombegrenzt", 2: "MPP-Tracking aktiv"}

ERR_CODES = {
    0: "Kein Fehler",
    2: "Batteriespannung zu hoch",
    17: "Laderegler zu heiß",
    18: "Überstrom",
    19: "Stromrichtung umgekehrt",
    20: "Bulk-Zeitlimit überschritten",
    21: "Stromsensor-Fehler",
    26: "Anschlussklemmen überhitzt",
    28: "Leistungsstufe",
    33: "PV-Spannung zu hoch",
    34: "PV-Strom zu hoch",
    38: "Eingang abgeschaltet (Batterie-Überspannung)",
    39: "Eingang abgeschaltet (Strom im Aus-Zustand)",
    65: "Kommunikationswarnung",
    66: "Inkompatibles Gerät",
    67: "BMS-Verbindung verloren",
    114: "CPU-Temperatur zu hoch",
    116: "Kalibrierdaten verloren",
    119: "Einstellungen ungültig",
}

OR_REASONS = {
    0x00000001: "Keine Eingangsleistung",
    0x00000002: "Ausgeschaltet (Schalter)",
    0x00000004: "Ausgeschaltet (Gerätemodus)",
    0x00000008: "Fernsteuereingang",
    0x00000010: "Schutzfunktion aktiv",
    0x00000020: "Paygo",
    0x00000040: "BMS",
    0x00000080: "Motorabschaltung erkannt",
    0x00000100: "Eingangsspannung wird geprüft",
}

AR_REASONS = {
    1: "Unterspannung",
    2: "Überspannung",
    4: "Niedriger Ladezustand",
    8: "Unterspannung Starter",
    16: "Überspannung Starter",
    32: "Untertemperatur",
    64: "Übertemperatur",
    128: "Mittelpunktspannung",
    256: "Überlast",
    512: "DC-Welligkeit",
    1024: "Niedrige AC-Ausgangsspannung",
    2048: "Hohe AC-Ausgangsspannung",
    4096: "Kurzschluss",
    8192: "BMS-Abschaltung",
}

MON_TYPES = {
    -9: "Solarladegerät",
    -8: "Windgenerator",
    -7: "Wellengenerator",
    -6: "Lichtmaschine",
    -5: "Brennstoffzelle",
    -4: "Wassergenerator",
    -3: "DC-DC-Lader",
    -2: "AC-Ladegerät",
    -1: "Generische Quelle",
    0: "Batteriemonitor",
    1: "Generischer Verbraucher",
    2: "Elektrischer Antrieb",
    3: "Kühlschrank",
    4: "Wasserpumpe",
    5: "Bilgepumpe",
    6: "DC-System",
    7: "Wechselrichter",
    8: "Warmwasserbereiter",
}

PRODUCTS = {
    0x0203: "BMV-700",
    0x0204: "BMV-702",
    0x0205: "BMV-700H",
    0xA381: "BMV-712 Smart",
    0xA382: "BMV-710H Smart",
    0xA383: "BMV-712 Smart Rev2",
    0xA389: "SmartShunt 500A/50mV",
    0xA38A: "SmartShunt 1000A/50mV",
    0xA38B: "SmartShunt 2000A/50mV",
    0xA042: "BlueSolar MPPT 75/15",
    0xA043: "BlueSolar MPPT 100/15",
    0xA053: "SmartSolar MPPT 75/15",
    0xA054: "SmartSolar MPPT 75/10",
    0xA055: "SmartSolar MPPT 100/15",
    0xA056: "SmartSolar MPPT 100/30",
    0xA057: "SmartSolar MPPT 100/50",
    0xA060: "SmartSolar MPPT 100/20",
    0xA075: "SmartSolar MPPT 150/35",
}


def _lookup(table: dict[int, str]) -> Callable[[str], str]:
    def conv(v: str) -> str:
        code = _hex_int(v)
        return table.get(code, f"Code {code}")

    return conv


def _bits(table: dict[int, str], none_text: str) -> Callable[[str], str]:
    def conv(v: str) -> str:
        code = _hex_int(v)
        if code == 0:
            return none_text
        names = [name for bit, name in table.items() if code & bit]
        rest = code & ~sum(table)
        if rest:
            names.append(f"0x{rest:X}")
        return ", ".join(names)

    return conv


def product_name(pid: str | None) -> str | None:
    if not pid:
        return None
    try:
        code = _hex_int(pid)
    except ValueError:
        return None
    return PRODUCTS.get(code, f"Victron 0x{code:04X}")


CONVERTERS: dict[str, Callable[[str], object]] = {
    "mv": _scaled(0.001, 3),
    "ma": _scaled(0.001, 3),
    "mah": _scaled(0.001, 3),
    "w": _int,
    "int": _int,
    "permille": _scaled(0.1, 1),
    "10wh": _scaled(0.01, 2),
    "text": _text,
    "onoff": _onoff,
    "ttg": _ttg,
    "seconds_h": _scaled(1 / 3600, 2),
    "cs": _lookup(CS_STATES),
    "mppt": _lookup(MPPT_STATES),
    "err": _lookup(ERR_CODES),
    "or": _bits(OR_REASONS, "Kein Grund"),
    "ar": _bits(AR_REASONS, "Kein Alarm"),
    "mon": _lookup(MON_TYPES),
    "fw": _text,
}


def convert(kind: str, raw: str) -> object | None:
    try:
        return CONVERTERS[kind](raw)
    except (ValueError, KeyError):
        return None
