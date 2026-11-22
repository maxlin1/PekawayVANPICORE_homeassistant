"""Nivellierung: verbindet Sensor, Rechenkern und Home Assistant.

Der Sensor wird nur gelesen, solange die Nivellierung aktiv ist, eine Nullung
läuft oder eine Fahrt-Kalibrierung aufgenommen wird. Sonst schläft der
MPU6050, und alle Messwert-Entitäten sind "nicht verfügbar".
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from ..const import (
    AUTO_OFF_MINUTES,
    CONF_BLOCK_HEIGHT,
    CONF_BLOCKS_PER_STACK,
    CONF_ENTITY_X,
    CONF_ENTITY_Y,
    CONF_ENTITY_Z,
    CONF_FORWARD,
    CONF_I2C_BUS,
    CONF_MPU_ADDRESS,
    CONF_SOURCE,
    CONF_STACKS,
    CONF_TOLERANCE,
    CONF_TRACK,
    CONF_WHEELBASE,
    DEFAULTS,
    DOMAIN,
    FORWARD_DRIVE,
    LEVEL_DEBOUNCE_S,
    PUBLISH_INTERVAL,
    PUBLISH_MIN_CHANGE_DEG,
    SAMPLE_INTERVAL,
    SOURCE_MPU6050,
    STORAGE_VERSION,
)
from .drive_calibration import CalibrationError, DriveRecorder, average_directions
from .filter import AdaptiveVectorFilter, Debounce
from .geometry import (
    AXIS_VECTORS,
    BlockPlan,
    Orientation,
    OrientationError,
    Vector,
    Vehicle,
    best_block_plan,
    dot,
    lift_per_wheel,
    normalize,
)
from .mpu6050 import MPU6050

_LOGGER = logging.getLogger(__name__)

ZERO_SECONDS = 3.0
MAX_RECORD_SECONDS = 120


def _merged(entry: ConfigEntry) -> dict[str, Any]:
    return {**DEFAULTS, **entry.data, **entry.options}


@dataclass
class LevelState:
    pitch: float | None = None
    roll: float | None = None
    lift: dict[str, float] | None = None
    plan: BlockPlan | None = None
    level: bool | None = None


class LevelingManager:
    """Zustand und Ablauf der Nivellierung für einen Config-Eintrag."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.config = _merged(entry)
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}.leveling"
        )
        self._stored: dict[str, Any] = {}
        self._listeners: list[CALLBACK_TYPE] = []
        self._task: asyncio.Task | None = None
        self._auto_off_unsub: CALLBACK_TYPE | None = None
        self._filter = AdaptiveVectorFilter()
        self._level_debounce = Debounce(LEVEL_DEBOUNCE_S)
        self._mpu: MPU6050 | None = None
        self._last_publish = 0.0
        self._published: tuple[float, float] | None = None

        self.active = False
        self.recorder: DriveRecorder | None = None
        self._zero_samples: list[Vector] | None = None
        self.state = LevelState()
        self.status = "Bereit"

        self.auto_off_at: datetime | None = None
        self.apply_options()

    @callback
    def apply_options(self) -> None:
        """Einstellungen übernehmen, ohne die Nivellierung neu zu starten."""
        self.config = _merged(self.entry)
        self.vehicle = Vehicle(
            wheelbase=float(self.config[CONF_WHEELBASE]),
            track=float(self.config[CONF_TRACK]),
            block_height=float(self.config[CONF_BLOCK_HEIGHT]),
            stacks=int(self.config[CONF_STACKS]),
            blocks_per_stack=int(self.config[CONF_BLOCKS_PER_STACK]),
        )
        self.tolerance = float(self.config[CONF_TOLERANCE])
        self._published = None  # nächsten Wert sofort mit neuen Daten berechnen
        self._notify()

    # ------------------------------------------------------------------ setup

    async def async_setup(self) -> None:
        self._stored = await self._store.async_load() or {}
        if self.config[CONF_SOURCE] == SOURCE_MPU6050:
            self._mpu = MPU6050(
                int(self.config[CONF_I2C_BUS]), int(self.config[CONF_MPU_ADDRESS])
            )
            # Beim Start sicher in den Schlafmodus
            await self.hass.async_add_executor_job(self._mpu.sleep)

    async def async_shutdown(self) -> None:
        await self._async_stop_sampling(force=True)

    # -------------------------------------------------------------- listeners

    @callback
    def async_add_listener(self, update: CALLBACK_TYPE) -> Callable[[], None]:
        self._listeners.append(update)

        def remove() -> None:
            self._listeners.remove(update)

        return remove

    @callback
    def _notify(self) -> None:
        for update in list(self._listeners):
            update()

    # ------------------------------------------------------------ properties

    @property
    def sampling(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def drive_runs(self) -> list[Vector]:
        return [tuple(v) for v in self._stored.get("forward_runs", [])]

    @property
    def zeroed(self) -> bool:
        return self._stored.get("up") is not None

    def calibration_info(self) -> dict[str, Any]:
        info: dict[str, Any] = {
            "nullung_gespeichert": self.zeroed,
            "vorwaertsrichtung": self.config[CONF_FORWARD],
            "fahrtrichtung_gespeichert": bool(self.drive_runs),
        }
        if self.auto_off_at is not None:
            info["automatisch_aus_um"] = self.auto_off_at.isoformat()
        if self.drive_runs:
            fwd, _ = average_directions(self.drive_runs)
            # Welche Board-Achse entspricht der Fahrtrichtung? Hilft beim Prüfen.
            axis, vec = max(AXIS_VECTORS.items(), key=lambda kv: dot(kv[1], fwd))
            angle = math.degrees(math.acos(max(-1.0, min(1.0, dot(vec, fwd)))))
            info["fahrtrichtung_entspricht"] = f"{axis} (Abweichung {angle:.0f}°)"
        if self.recorder is not None:
            info["signal_g"] = round(self.recorder.signal_g, 2)
            info["spitze_g"] = round(self.recorder.peak_g, 2)
        return info

    # ------------------------------------------------------------ orientation

    def _orientation(self, current: Vector) -> Orientation:
        up = self._stored.get("up")
        if up is None:
            # Ohne Nullung: nächstliegende Board-Achse als "oben" annehmen
            up = max(AXIS_VECTORS.values(), key=lambda a: sum(x * y for x, y in zip(a, current)))
        forward_cfg = self.config[CONF_FORWARD]
        if forward_cfg == FORWARD_DRIVE:
            if not self.drive_runs:
                raise OrientationError(
                    "Noch keine Fahrt-Kalibrierung. Bitte einmal anfahren und bremsen."
                )
            forward, _ = average_directions(self.drive_runs)
        else:
            forward = AXIS_VECTORS[forward_cfg]
        return Orientation.from_vectors(tuple(up), forward)

    # --------------------------------------------------------------- controls

    async def async_set_active(self, active: bool) -> None:
        if active == self.active:
            return
        self.active = active
        if self._auto_off_unsub:
            self._auto_off_unsub()
            self._auto_off_unsub = None
        self.auto_off_at = None
        if active:
            minutes = AUTO_OFF_MINUTES
            if minutes > 0:
                self._auto_off_unsub = async_call_later(
                    self.hass, minutes * 60, self._auto_off
                )
                self.auto_off_at = dt_util.now() + timedelta(minutes=minutes)
            self.status = "Aktiv"
            await self._async_start_sampling()
        else:
            self.state = LevelState()
            self._published = None
            self._level_debounce = Debounce(LEVEL_DEBOUNCE_S)
            self.status = "Aus"
            await self._async_stop_sampling()
        self._notify()

    @callback
    def _auto_off(self, _now: Any) -> None:
        self._auto_off_unsub = None
        _LOGGER.info("Nivellierung nach eingestellter Zeit automatisch ausgeschaltet")
        self.hass.async_create_task(self.async_set_active(False))

    async def async_zero(self) -> None:
        """Aktuelle Lage als eben speichern (3 s mitteln)."""
        self._zero_samples = []
        self.status = "Nullung läuft, Fahrzeug nicht bewegen"
        self._notify()
        await self._async_start_sampling()
        await asyncio.sleep(ZERO_SECONDS)
        samples, self._zero_samples = self._zero_samples, None
        await self._async_stop_sampling()
        if not samples:
            self.status = "Nullung fehlgeschlagen: keine Messwerte"
            self._notify()
            raise HomeAssistantError(self.status)
        n = len(samples)
        mean = (
            sum(s[0] for s in samples) / n,
            sum(s[1] for s in samples) / n,
            sum(s[2] for s in samples) / n,
        )
        self._stored["up"] = list(normalize(mean))
        await self._store.async_save(self._stored)
        self._filter.reset()
        self.status = "Als eben gespeichert"
        self._notify()

    async def async_drive_start(self) -> None:
        self.recorder = DriveRecorder()
        self.status = "Fahrt-Aufnahme: 2 s stehen bleiben, dann 1 bis 3 Mal anfahren und bis zum Stillstand bremsen, danach beenden"
        self._notify()
        await self._async_start_sampling()

    async def async_drive_stop(self) -> None:
        recorder, self.recorder = self.recorder, None
        await self._async_stop_sampling()
        if recorder is None:
            raise HomeAssistantError("Es läuft keine Fahrt-Aufnahme")
        try:
            forward = recorder.result()
        except CalibrationError as err:
            self.status = f"Fahrt nicht gespeichert: {err}"
            self._notify()
            raise HomeAssistantError(self.status) from err
        # Eine Aufnahme (mit beliebig vielen Anfahr-/Bremsvorgängen) ersetzt
        # die alte Fahrtrichtung komplett. Die Ebene ("Als eben") bleibt.
        self._stored["forward_runs"] = [list(forward)]
        await self._store.async_save(self._stored)
        self.status = (
            "Fahrtrichtung gespeichert. Unter Einstellungen 'Vorwärtsrichtung: "
            "aus Fahrt-Kalibrierung' wählen, falls noch nicht geschehen."
            if self.config[CONF_FORWARD] != FORWARD_DRIVE
            else "Fahrtrichtung gespeichert"
        )
        self._notify()

    async def async_drive_cancel(self) -> None:
        self.recorder = None
        await self._async_stop_sampling()
        self.status = "Fahrt-Aufnahme abgebrochen"
        self._notify()

    async def async_reset_calibration(self) -> None:
        self._stored = {}
        await self._store.async_save(self._stored)
        self.status = "Kalibrierung zurückgesetzt"
        self._notify()

    # --------------------------------------------------------------- sampling

    def _needed(self) -> bool:
        return self.active or self.recorder is not None or self._zero_samples is not None

    async def _async_start_sampling(self) -> None:
        if self.sampling:
            return
        if self._mpu is not None:
            await self.hass.async_add_executor_job(self._mpu.wake)
        self._filter.reset()
        self._task = self.entry.async_create_background_task(
            self.hass, self._async_loop(), f"{DOMAIN}_leveling"
        )

    async def _async_stop_sampling(self, force: bool = False) -> None:
        if not force and self._needed():
            return
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._mpu is not None:
            await self.hass.async_add_executor_job(self._mpu.sleep)

    async def _async_read(self) -> Vector | None:
        if self._mpu is not None:
            return await self.hass.async_add_executor_job(self._mpu.read_accel)
        values = []
        for key in (CONF_ENTITY_X, CONF_ENTITY_Y, CONF_ENTITY_Z):
            st = self.hass.states.get(self.config.get(key, ""))
            try:
                value = float(st.state)  # type: ignore[union-attr]
            except (AttributeError, TypeError, ValueError):
                return None
            unit = (st.attributes.get("unit_of_measurement") or "").lower()
            if unit in ("m/s²", "m/s2"):
                value /= 9.80665
            elif unit == "mg":
                value /= 1000.0
            values.append(value)
        return (values[0], values[1], values[2])

    async def _async_loop(self) -> None:
        last = time.monotonic()
        errors = 0
        while True:
            start = time.monotonic()
            try:
                sample = await self._async_read()
                errors = 0
            except OSError as err:
                errors += 1
                if errors == 5:
                    _LOGGER.warning("Beschleunigungssensor nicht lesbar: %s", err)
                    self.status = f"Sensorfehler: {err}"
                    self._notify()
                sample = None
            if sample is not None:
                self._process(sample, start, start - last)
            last = start
            await asyncio.sleep(max(0.0, SAMPLE_INTERVAL - (time.monotonic() - start)))

    @callback
    def _process(self, sample: Vector, now: float, dt: float) -> None:
        if self._zero_samples is not None:
            self._zero_samples.append(sample)
        if self.recorder is not None:
            self.recorder.add(now, sample)
            if now - self._last_publish >= 1.0:
                self._last_publish = now
                self._notify()  # Live-Signal für die Anzeige
            if self.recorder.samples and now - self.recorder.samples[0][0] > MAX_RECORD_SECONDS:
                self.hass.async_create_task(self.async_drive_stop())
            return
        if not self.active:
            return

        vec = self._filter.update(sample, max(dt, 1e-3))
        if now - self._last_publish < PUBLISH_INTERVAL:
            return
        try:
            pitch, roll = self._orientation(vec).angles(vec)
        except OrientationError as err:
            self.status = str(err)
            self.state = LevelState()
            self._last_publish = now
            self._notify()
            return

        level = self._level_debounce.update(
            abs(pitch) <= self.tolerance and abs(roll) <= self.tolerance, now
        )
        if (
            self._published is not None
            and abs(pitch - self._published[0]) < PUBLISH_MIN_CHANGE_DEG
            and abs(roll - self._published[1]) < PUBLISH_MIN_CHANGE_DEG
            and level == self.state.level
        ):
            return
        self._published = (pitch, roll)
        self._last_publish = now
        self.state = LevelState(
            pitch=pitch,
            roll=roll,
            lift=lift_per_wheel(self.vehicle, pitch, roll),
            plan=best_block_plan(self.vehicle, pitch, roll),
            level=level,
        )
        if not self.zeroed:
            self.status = "Aktiv (ohne Nullung, bitte 'Als eben speichern')"
        elif self.status.startswith("Sensorfehler") or self.status == "Aktiv":
            self.status = "Aktiv"
        self._notify()
