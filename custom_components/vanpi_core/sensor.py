"""Sensoren der Nivellierung."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import DEGREE, EntityCategory, Platform, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VanPiConfigEntry
from .entity import LevelingEntity
from .leveling.geometry import WHEELS
from .leveling.manager import LevelingManager


@dataclass(frozen=True, kw_only=True)
class LevelingSensorDescription(SensorEntityDescription):
    value: Callable[[LevelingManager], Any]
    attrs: Callable[[LevelingManager], dict[str, Any] | None] = lambda m: None
    always_available: bool = False


def _round(v: float | None, n: int = 1) -> float | None:
    return None if v is None else round(v, n)


def _lift(wheel: str) -> Callable[[LevelingManager], float | None]:
    return lambda m: None if m.state.lift is None else round(m.state.lift[wheel], 1)


def _blocks(wheel: str) -> Callable[[LevelingManager], int | None]:
    return lambda m: None if m.state.plan is None else m.state.plan.blocks[wheel]


def _plan_attrs(m: LevelingManager) -> dict[str, Any] | None:
    plan = m.state.plan
    if plan is None:
        return None
    return {
        "bloecke": plan.blocks,
        "restneigung_laengs": round(plan.residual_pitch, 2),
        "restneigung_quer": round(plan.residual_roll, 2),
        "blockhoehe_cm": m.vehicle.block_height,
    }


ANGLE = {
    "native_unit_of_measurement": DEGREE,
    "state_class": SensorStateClass.MEASUREMENT,
    "suggested_display_precision": 1,
}
LENGTH = {
    "native_unit_of_measurement": UnitOfLength.CENTIMETERS,
    "device_class": SensorDeviceClass.DISTANCE,
    "state_class": SensorStateClass.MEASUREMENT,
    "suggested_display_precision": 1,
}

SENSORS: list[LevelingSensorDescription] = [
    LevelingSensorDescription(key="pitch", icon="mdi:angle-acute", value=lambda m: _round(m.state.pitch, 2), **ANGLE),
    LevelingSensorDescription(key="roll", icon="mdi:angle-acute", value=lambda m: _round(m.state.roll, 2), **ANGLE),
    *[
        LevelingSensorDescription(key=f"lift_{w}", icon="mdi:arrow-up-bold", value=_lift(w), **LENGTH)
        for w in WHEELS
    ],
    *[
        LevelingSensorDescription(key=f"blocks_{w}", icon="mdi:layers-triple", value=_blocks(w))
        for w in WHEELS
    ],
    LevelingSensorDescription(
        key="recommendation",
        icon="mdi:lightbulb-on",
        value=lambda m: None if m.state.plan is None else m.state.plan.text(m.vehicle.block_height),
        attrs=_plan_attrs,
    ),
    LevelingSensorDescription(
        key="residual",
        icon="mdi:angle-acute",
        value=lambda m: None if m.state.plan is None else round(m.state.plan.residual, 2),
        **ANGLE,
    ),
    LevelingSensorDescription(
        key="status",
        icon="mdi:information-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda m: m.status[:255],
        attrs=lambda m: m.calibration_info(),
        always_available=True,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VanPiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    if (manager := entry.runtime_data.leveling) is not None:
        async_add_entities(
            [LevelingSensor(manager, d) for d in SENSORS], config_subentry_id=manager.subentry_id
        )
    entry.runtime_data.modules.register_platform(Platform.SENSOR, async_add_entities)


class LevelingSensor(LevelingEntity, SensorEntity):
    entity_description: LevelingSensorDescription

    def __init__(self, manager: LevelingManager, description: LevelingSensorDescription) -> None:
        super().__init__(manager, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        if self.entity_description.always_available:
            return True
        return self.manager.active and self.entity_description.value(self.manager) is not None

    @property
    def native_value(self) -> Any:
        return self.entity_description.value(self.manager)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return self.entity_description.attrs(self.manager)
