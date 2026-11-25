"""Modul Victron VE.Direct (MPPT-Laderegler, SmartShunt, BMV) über UART.

Ein eigener Lese-Thread liest die serielle Schnittstelle mit Timeout,
prüft jede Prüfsumme und verbindet sich nach Fehlern selbst neu. Werte gehen
höchstens alle `scan_interval` Sekunden an Home Assistant und nur, wenn sie
sich geändert haben.

Entitäten entstehen erst, wenn das Gerät das Feld wirklich sendet. Ein
SmartShunt hat z. B. kein Relais und ein MPPT ohne Lastausgang keinen
Laststrom; solche Entitäten blieben sonst für immer "nicht verfügbar".
Hat das Gerät eine Minute lang Daten geliefert, werden alte Einträge für
Felder, die es nie sendet, aus der Entitätsregistrierung entfernt.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    Platform,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .base import BoardModule, ModuleEntity
from .const import (
    CONF_BAUDRATE,
    CONF_DEVICE_TYPE,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    DEVICE_MPPT,
    DEVICE_SHUNT,
    VICTRON_DEFAULT_BAUD,
    VICTRON_DEFAULT_INTERVAL,
    VICTRON_STALE_AFTER,
)
from .vedirect import VEDirectParser, convert, product_name

_LOGGER = logging.getLogger(__name__)

V = UnitOfElectricPotential.VOLT
A = UnitOfElectricCurrent.AMPERE
W = UnitOfPower.WATT
KWH = UnitOfEnergy.KILO_WATT_HOUR
AH = "Ah"
DIAG = EntityCategory.DIAGNOSTIC
MEAS = SensorStateClass.MEASUREMENT
TOTAL_INC = SensorStateClass.TOTAL_INCREASING


@dataclass(frozen=True, kw_only=True)
class Field:
    label: str  # VE.Direct-Label
    key: str  # Teil der unique_id
    name: str
    kind: str  # Umrechnung, siehe vedirect.CONVERTERS
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    precision: int | None = None
    icon: str | None = None
    category: EntityCategory | None = None
    enabled: bool = True


MPPT_FIELDS: tuple[Field, ...] = (
    Field(label="V", key="battery_voltage", name="Batteriespannung", kind="mv", unit=V,
          device_class=SensorDeviceClass.VOLTAGE, state_class=MEAS, precision=2),
    Field(label="I", key="battery_current", name="Ladestrom", kind="ma", unit=A,
          device_class=SensorDeviceClass.CURRENT, state_class=MEAS, precision=1),
    Field(label="VPV", key="pv_voltage", name="PV-Spannung", kind="mv", unit=V,
          device_class=SensorDeviceClass.VOLTAGE, state_class=MEAS, precision=1),
    Field(label="PPV", key="pv_power", name="PV-Leistung", kind="w", unit=W,
          device_class=SensorDeviceClass.POWER, state_class=MEAS, precision=0),
    Field(label="IL", key="load_current", name="Laststrom", kind="ma", unit=A,
          device_class=SensorDeviceClass.CURRENT, state_class=MEAS, precision=1),
    Field(label="CS", key="charge_state", name="Ladestatus", kind="cs", icon="mdi:battery-charging"),
    Field(label="MPPT", key="tracker", name="Tracker-Modus", kind="mppt", icon="mdi:solar-power"),
    Field(label="OR", key="off_reason", name="Abschaltgrund", kind="or", icon="mdi:power-off",
          category=DIAG),
    Field(label="ERR", key="error", name="Fehler", kind="err", icon="mdi:alert"),
    Field(label="H19", key="yield_total", name="Gesamtertrag", kind="10wh", unit=KWH,
          device_class=SensorDeviceClass.ENERGY, state_class=TOTAL_INC, precision=2),
    Field(label="H20", key="yield_today", name="Ertrag heute", kind="10wh", unit=KWH,
          device_class=SensorDeviceClass.ENERGY, state_class=TOTAL_INC, precision=2),
    Field(label="H21", key="max_power_today", name="Maximale Leistung heute", kind="w", unit=W,
          device_class=SensorDeviceClass.POWER, state_class=MEAS, precision=0),
    Field(label="H22", key="yield_yesterday", name="Ertrag gestern", kind="10wh", unit=KWH,
          device_class=SensorDeviceClass.ENERGY, precision=2),
    Field(label="H23", key="max_power_yesterday", name="Maximale Leistung gestern", kind="w",
          unit=W, device_class=SensorDeviceClass.POWER, precision=0),
    Field(label="HSDS", key="day_sequence", name="Tageszähler", kind="int", icon="mdi:counter",
          category=DIAG, enabled=False),
    Field(label="FW", key="firmware", name="Firmware", kind="fw", icon="mdi:chip", category=DIAG),
)

SHUNT_FIELDS: tuple[Field, ...] = (
    Field(label="V", key="battery_voltage", name="Batteriespannung", kind="mv", unit=V,
          device_class=SensorDeviceClass.VOLTAGE, state_class=MEAS, precision=2),
    Field(label="I", key="battery_current", name="Batteriestrom", kind="ma", unit=A,
          device_class=SensorDeviceClass.CURRENT, state_class=MEAS, precision=2),
    Field(label="P", key="power", name="Leistung", kind="w", unit=W,
          device_class=SensorDeviceClass.POWER, state_class=MEAS, precision=0),
    Field(label="SOC", key="soc", name="Ladezustand", kind="permille", unit=PERCENTAGE,
          device_class=SensorDeviceClass.BATTERY, state_class=MEAS, precision=1),
    Field(label="CE", key="consumed_ah", name="Verbrauchte Ah", kind="mah", unit=AH,
          state_class=MEAS, precision=1, icon="mdi:battery-minus"),
    Field(label="TTG", key="time_to_go", name="Restlaufzeit", kind="ttg", unit=UnitOfTime.HOURS,
          device_class=SensorDeviceClass.DURATION, state_class=MEAS, precision=1),
    Field(label="VS", key="starter_voltage", name="Starterbatterie", kind="mv", unit=V,
          device_class=SensorDeviceClass.VOLTAGE, state_class=MEAS, precision=2),
    Field(label="VM", key="mid_voltage", name="Mittelpunktspannung", kind="mv", unit=V,
          device_class=SensorDeviceClass.VOLTAGE, state_class=MEAS, precision=2, enabled=False),
    Field(label="DM", key="mid_deviation", name="Mittelpunktabweichung", kind="permille",
          unit=PERCENTAGE, state_class=MEAS, precision=1, enabled=False),
    Field(label="T", key="temperature", name="Batterietemperatur", kind="int",
          unit=UnitOfTemperature.CELSIUS, device_class=SensorDeviceClass.TEMPERATURE,
          state_class=MEAS, enabled=False),
    Field(label="AR", key="alarm_reason", name="Alarmgrund", kind="ar", icon="mdi:alert-circle"),
    Field(label="MON", key="monitor_mode", name="Betriebsart", kind="mon", category=DIAG,
          enabled=False),
    Field(label="H1", key="deepest_discharge", name="Tiefste Entladung", kind="mah", unit=AH,
          precision=1, icon="mdi:history", category=DIAG),
    Field(label="H2", key="last_discharge", name="Letzte Entladung", kind="mah", unit=AH,
          precision=1, icon="mdi:history", category=DIAG),
    Field(label="H3", key="average_discharge", name="Durchschnittliche Entladung", kind="mah",
          unit=AH, precision=1, icon="mdi:history", category=DIAG),
    Field(label="H4", key="charge_cycles", name="Ladezyklen", kind="int", icon="mdi:refresh",
          state_class=TOTAL_INC, category=DIAG),
    Field(label="H5", key="full_discharges", name="Vollständige Entladungen", kind="int",
          icon="mdi:battery-alert-variant-outline", state_class=TOTAL_INC, category=DIAG),
    Field(label="H6", key="cumulative_ah", name="Entnommene Ah gesamt", kind="mah", unit=AH,
          precision=0, icon="mdi:sigma", category=DIAG),
    Field(label="H7", key="min_voltage", name="Minimale Batteriespannung", kind="mv", unit=V,
          device_class=SensorDeviceClass.VOLTAGE, precision=2, category=DIAG),
    Field(label="H8", key="max_voltage", name="Maximale Batteriespannung", kind="mv", unit=V,
          device_class=SensorDeviceClass.VOLTAGE, precision=2, category=DIAG),
    Field(label="H9", key="since_full", name="Zeit seit Vollladung", kind="seconds_h",
          unit=UnitOfTime.HOURS, device_class=SensorDeviceClass.DURATION, precision=1,
          category=DIAG),
    Field(label="H10", key="auto_syncs", name="Automatische Synchronisationen", kind="int",
          icon="mdi:sync", state_class=TOTAL_INC, category=DIAG),
    Field(label="H11", key="low_voltage_alarms", name="Unterspannungsalarme", kind="int",
          icon="mdi:alert-octagram", state_class=TOTAL_INC, category=DIAG),
    Field(label="H12", key="high_voltage_alarms", name="Überspannungsalarme", kind="int",
          icon="mdi:alert-octagram", state_class=TOTAL_INC, category=DIAG),
    Field(label="H13", key="low_aux_alarms", name="Unterspannungsalarme Starter", kind="int",
          icon="mdi:alert-octagram", state_class=TOTAL_INC, category=DIAG, enabled=False),
    Field(label="H14", key="high_aux_alarms", name="Überspannungsalarme Starter", kind="int",
          icon="mdi:alert-octagram", state_class=TOTAL_INC, category=DIAG, enabled=False),
    Field(label="H15", key="min_aux_voltage", name="Minimale Spannung Starter", kind="mv",
          unit=V, device_class=SensorDeviceClass.VOLTAGE, precision=2, category=DIAG),
    Field(label="H16", key="max_aux_voltage", name="Maximale Spannung Starter", kind="mv",
          unit=V, device_class=SensorDeviceClass.VOLTAGE, precision=2, category=DIAG),
    Field(label="H17", key="energy_discharged", name="Entladene Energie", kind="10wh", unit=KWH,
          device_class=SensorDeviceClass.ENERGY, state_class=TOTAL_INC, precision=2),
    Field(label="H18", key="energy_charged", name="Geladene Energie", kind="10wh", unit=KWH,
          device_class=SensorDeviceClass.ENERGY, state_class=TOTAL_INC, precision=2),
    Field(label="FW", key="firmware", name="Firmware", kind="fw", icon="mdi:chip", category=DIAG),
)

FIELDS = {DEVICE_MPPT: MPPT_FIELDS, DEVICE_SHUNT: SHUNT_FIELDS}

# Zustand als Binärsensor
MPPT_BINARY = (("LOAD", "load", "Lastausgang", BinarySensorDeviceClass.POWER),)
SHUNT_BINARY = (
    ("Alarm", "alarm", "Alarm", BinarySensorDeviceClass.PROBLEM),
    ("Relay", "relay", "Relais", BinarySensorDeviceClass.POWER),
)
BINARY = {DEVICE_MPPT: MPPT_BINARY, DEVICE_SHUNT: SHUNT_BINARY}

# So lange muss ein Gerät Daten liefern, bevor nie gesendete Felder als
# "gibt es bei diesem Gerät nicht" gelten (Verlaufsblöcke kommen seltener).
VICTRON_CLEANUP_AFTER = 60


class SerialReader(threading.Thread):
    """Liest VE.Direct-Blöcke und übergibt sie an `on_block` (im Lese-Thread)."""

    def __init__(self, port: str, baudrate: int, on_block, on_error) -> None:
        super().__init__(name=f"vanpi_core VE.Direct {port}", daemon=True)
        self.port = port
        self.baudrate = baudrate
        self.on_block = on_block
        self.on_error = on_error
        self.stop_event = threading.Event()
        self.parser = VEDirectParser()

    def run(self) -> None:
        import serial  # noqa: PLC0415  (pyserial nur laden, wenn gebraucht)

        backoff = 2.0
        while not self.stop_event.is_set():
            try:
                with serial.Serial(self.port, self.baudrate, timeout=1) as ser:
                    backoff = 2.0
                    self.parser = VEDirectParser()
                    while not self.stop_event.is_set():
                        data = ser.read(256)
                        if not data:
                            continue
                        for block in self.parser.feed(data):
                            self.on_block(block)
            except Exception as err:  # noqa: BLE001  (Port weg, Gerät abgesteckt ...)
                self.on_error(f"{self.port}: {err}")
                self.stop_event.wait(backoff)
                backoff = min(backoff * 2, 60.0)

    def stop(self) -> None:
        self.stop_event.set()


class VictronModule(BoardModule):
    manufacturer = "Victron Energy"

    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.device_type = self.data.get(CONF_DEVICE_TYPE, DEVICE_SHUNT)
        self.port = self.data[CONF_PORT]
        self.interval = max(1, int(self.data.get(CONF_SCAN_INTERVAL, VICTRON_DEFAULT_INTERVAL)))
        self.raw: dict[str, str] = {}
        self.last_block = 0.0
        self.product: str | None = None
        self.serial: str | None = None
        self._lock = threading.Lock()
        self._pending: dict[str, str] | None = None
        self._pending_error: str | None = None
        self._reader: SerialReader | None = None
        self._unsub: CALLBACK_TYPE | None = None
        self.model = "MPPT-Laderegler" if self.device_type == DEVICE_MPPT else "Batteriemonitor"
        # Bereits gebaute Entitäten je (Plattform, Feld); immer dieselben Objekte
        self._built: dict[tuple[Platform, str], Entity] = {}
        self._first_block: float | None = None
        self._cleaned_up = False

    # -- Lese-Thread ------------------------------------------------------

    def _on_block(self, block: dict[str, str]) -> None:
        with self._lock:
            self._pending = block
            self._pending_error = None

    def _on_error(self, error: str) -> None:
        with self._lock:
            self._pending_error = error

    # -- Event-Loop -------------------------------------------------------

    async def async_start(self) -> None:
        baud = int(self.data.get(CONF_BAUDRATE, VICTRON_DEFAULT_BAUD))
        self._reader = SerialReader(self.port, baud, self._on_block, self._on_error)
        self._reader.start()
        self._unsub = async_track_time_interval(
            self.hass, self._async_publish, timedelta(seconds=self.interval)
        )

    async def async_stop(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None
        if self._reader:
            self._reader.stop()
            await self.hass.async_add_executor_job(self._reader.join, 3)
            self._reader = None

    @callback
    def _async_publish(self, _now=None) -> None:
        with self._lock:
            block, self._pending = self._pending, None
            error = self._pending_error
        now = dt_util.utcnow().timestamp()
        if block:
            self.raw.update(block)
            self.last_block = now
            self.product = product_name(block.get("PID")) or self.product
            self.serial = block.get("SER#") or self.serial
            self.set_error(None)
            self._add_new_entities()
            if self._first_block is None:
                self._first_block = now
            elif not self._cleaned_up and now - self._first_block >= VICTRON_CLEANUP_AFTER:
                self._cleaned_up = True
                self._remove_unsent_entities()
        elif self.available and now - self.last_block > VICTRON_STALE_AFTER:
            self.set_error(error or f"{self.port}: seit {VICTRON_STALE_AFTER} s keine gültigen Daten")
        elif error and not self.available:
            self.set_error(error)
        else:
            return
        self.async_notify()

    def value(self, label: str, kind: str) -> Any:
        raw = self.raw.get(label)
        return None if raw is None else convert(kind, raw)

    def _build(self) -> dict[Platform, list[Entity]]:
        """Entitäten für alle bisher empfangenen Felder, neue zuerst bauen."""
        fresh: dict[Platform, list[Entity]] = {}

        def get(platform: Platform, label: str, factory) -> Entity:
            key = (platform, label)
            if key not in self._built:
                self._built[key] = factory()
                fresh.setdefault(platform, []).append(self._built[key])
            return self._built[key]

        get(Platform.SENSOR, "", lambda: VictronInfoSensor(self))
        for f in FIELDS[self.device_type]:
            if f.label in self.raw:
                get(Platform.SENSOR, f.label, lambda f=f: VictronSensor(self, f))
        for label, key, name, dc in BINARY[self.device_type]:
            if label in self.raw:
                get(
                    Platform.BINARY_SENSOR,
                    label,
                    lambda a=(label, key, name, dc): VictronBinarySensor(self, *a),
                )
        return fresh

    @callback
    def _add_new_entities(self) -> None:
        fresh = self._build()
        if self.add_entities_later:
            for platform, entities in fresh.items():
                self.add_entities_later(platform, entities)

    @callback
    def _remove_unsent_entities(self) -> None:
        """Registry-Einträge für Felder löschen, die dieses Gerät nie sendet."""
        keys = [(f.label, f.key) for f in FIELDS[self.device_type]]
        keys += [(label, key) for label, key, _n, _d in BINARY[self.device_type]]
        unsent = {self.unique_id(key) for label, key in keys if label not in self.raw}
        registry = er.async_get(self.hass)
        for entry in er.async_entries_for_config_entry(registry, self.entry.entry_id):
            if entry.config_subentry_id == self.subentry_id and entry.unique_id in unsent:
                _LOGGER.info(
                    "%s: %s entfernt, das Gerät sendet diesen Wert nicht",
                    self.subentry.title,
                    entry.entity_id,
                )
                registry.async_remove(entry.entity_id)

    def create_entities(self) -> dict[Platform, list[Entity]]:
        self._build()
        result: dict[Platform, list[Entity]] = {}
        for (platform, _label), entity in self._built.items():
            result.setdefault(platform, []).append(entity)
        return result


class VictronSensor(ModuleEntity, SensorEntity):
    module: VictronModule

    def __init__(self, module: VictronModule, field: Field) -> None:
        super().__init__(module, field.key, field.name)
        self.field = field
        self._attr_native_unit_of_measurement = field.unit
        self._attr_device_class = field.device_class
        self._attr_state_class = field.state_class
        self._attr_suggested_display_precision = field.precision
        self._attr_icon = field.icon
        self._attr_entity_category = field.category
        self._attr_entity_registry_enabled_default = field.enabled
        self._last: Any = object()

    @property
    def available(self) -> bool:
        return self.module.available and self.field.label in self.module.raw

    @property
    def native_value(self) -> Any:
        return self.module.value(self.field.label, self.field.kind)

    @callback
    def _handle_update(self) -> None:
        current = (self.available, self.native_value)
        if current != self._last:
            self._last = current
            self.async_write_ha_state()


class VictronInfoSensor(ModuleEntity, SensorEntity):
    """Produkt und Seriennummer, zugleich Verbindungsstatus."""

    _attr_icon = "mdi:information-outline"
    _attr_entity_category = DIAG
    module: VictronModule

    def __init__(self, module: VictronModule) -> None:
        super().__init__(module, "product", "Gerät")

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> str:
        if not self.module.available:
            return "Keine Daten"
        return self.module.product or "Unbekannt"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "port": self.module.port,
            "seriennummer": self.module.serial,
            "produkt_id": self.module.raw.get("PID"),
            "fehler": self.module.last_error,
        }


class VictronBinarySensor(ModuleEntity, BinarySensorEntity):
    module: VictronModule

    def __init__(self, module: VictronModule, label: str, key: str, name: str, dc) -> None:
        super().__init__(module, key, name)
        self.label = label
        self._attr_device_class = dc

    @property
    def available(self) -> bool:
        return self.module.available and self.label in self.module.raw

    @property
    def is_on(self) -> bool | None:
        return self.module.value(self.label, "onoff")
