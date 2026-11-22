"""Knöpfe: Nullung und Fahrt-Kalibrierung."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VanPiConfigEntry
from .entity import LevelingEntity
from .leveling.manager import LevelingManager


@dataclass(frozen=True, kw_only=True)
class LevelingButtonDescription(ButtonEntityDescription):
    press: Callable[[LevelingManager], Awaitable[None]]
    available: Callable[[LevelingManager], bool] = lambda m: True


BUTTONS = (
    LevelingButtonDescription(
        key="zero",
        icon="mdi:target",
        press=lambda m: m.async_zero(),
    ),
    LevelingButtonDescription(
        key="drive_start",
        icon="mdi:record-circle",
        press=lambda m: m.async_drive_start(),
        available=lambda m: m.recorder is None,
    ),
    LevelingButtonDescription(
        key="drive_stop",
        icon="mdi:stop-circle",
        press=lambda m: m.async_drive_stop(),
        available=lambda m: m.recorder is not None,
    ),
    LevelingButtonDescription(
        key="drive_cancel",
        icon="mdi:close-circle",
        press=lambda m: m.async_drive_cancel(),
        available=lambda m: m.recorder is not None,
    ),
    LevelingButtonDescription(
        key="reset_calibration",
        icon="mdi:restore",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        press=lambda m: m.async_reset_calibration(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VanPiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    manager = entry.runtime_data.leveling
    async_add_entities(LevelingButton(manager, d) for d in BUTTONS)


class LevelingButton(LevelingEntity, ButtonEntity):
    entity_description: LevelingButtonDescription

    def __init__(self, manager: LevelingManager, description: LevelingButtonDescription) -> None:
        super().__init__(manager, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        return self.entity_description.available(self.manager)

    async def async_press(self) -> None:
        await self.entity_description.press(self.manager)
