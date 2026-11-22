"""VAN PI CORE: Integration für das Pekaway VAN PI CORE Board.

Der Haupteintrag hält die Grundeinstellungen des Boards. Jede Funktion ist ein
eigener Eintrag darunter (Subentry): Nivellierung, Relais/Eingänge, Tanks,
1-Wire und Victron.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.loader import async_get_integration

from .const import DOMAIN, LEVELING_KEYS, PLATFORMS, SUBENTRY_LEVELING
from .leveling.manager import LevelingManager
from .modules import ModuleManager
from .modules.const import CONF_PAIR_12, CONF_PAIR_34, SUBENTRY_TANK_INPUTS
from .modules.tanks import pair_modes

_LOGGER = logging.getLogger(__name__)

CARD_URL = "/vanpi_core/vanpi-level-card.js"
CARD_FILE = Path(__file__).parent / "frontend" / "vanpi-level-card.js"


@dataclass
class VanPiData:
    leveling: LevelingManager | None
    modules: ModuleManager


type VanPiConfigEntry = ConfigEntry[VanPiData]


def leveling_subentry(entry: ConfigEntry) -> ConfigSubentry | None:
    return next(
        (s for s in entry.subentries.values() if s.subentry_type == SUBENTRY_LEVELING), None
    )


async def _async_register_card(hass: HomeAssistant) -> None:
    """Wasserwaage-Karte mitliefern: custom:vanpi-level-card, ohne Extra-Ressource."""
    if hass.data.get(f"{DOMAIN}_card"):
        return
    hass.data[f"{DOMAIN}_card"] = True
    if hass.http is None or "frontend" not in hass.config.components:
        return  # z. B. in Tests ohne Webserver
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_FILE), cache_headers=False)]
    )
    integration = await async_get_integration(hass, DOMAIN)
    add_extra_js_url(hass, f"{CARD_URL}?v={integration.version}")


async def async_setup_entry(hass: HomeAssistant, entry: VanPiConfigEntry) -> bool:
    await _async_register_card(hass)
    leveling = None
    subentry = leveling_subentry(entry)
    if subentry is not None:
        _enable_reset_button(hass, entry)
        leveling = LevelingManager(hass, entry, subentry.subentry_id)
        await leveling.async_setup()
    modules = ModuleManager(hass, entry)
    await modules.async_setup()
    entry.runtime_data = VanPiData(leveling=leveling, modules=modules)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VanPiConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        if entry.runtime_data.leveling:
            await entry.runtime_data.leveling.async_shutdown()
        await entry.runtime_data.modules.async_shutdown()
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: VanPiConfigEntry) -> None:
    """Änderungen live übernehmen (Nivellierung bleibt an)."""
    leveling = entry.runtime_data.leveling
    subentry = leveling_subentry(entry)
    if (leveling and leveling.subentry_id) != (subentry and subentry.subentry_id):
        # Nivellierung hinzugefügt oder gelöscht: einmal neu laden
        hass.config_entries.async_schedule_reload(entry.entry_id)
        return
    if leveling:
        leveling.apply_options()
    await entry.runtime_data.modules.async_sync()


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Version 1 -> 2: Nivellierung wird eigener Eintrag, Zahnrad = Board.

    - Sensorquelle (data) und Fahrzeugwerte (options) wandern in den neuen
      Eintrag "Nivellierung". Kalibrierung (.storage) und Entity-IDs bleiben.
    - Der Sensortyp der Tankeingänge kommt aus dem bisherigen Eintrag
      "Tankeingänge" in die Grundeinstellungen. Der Eintrag entfällt.
    """
    if entry.version > 2:
        return False
    if entry.version == 2:
        return True

    leveling = {
        k: v for k, v in {**entry.data, **entry.options}.items() if k in LEVELING_KEYS
    }
    modes = pair_modes(entry)  # liest noch den alten Eintrag "Tankeingänge"
    options = {CONF_PAIR_12: modes[1], CONF_PAIR_34: modes[3]}

    subentry = None
    if leveling:
        subentry = ConfigSubentry(
            data=leveling, subentry_type=SUBENTRY_LEVELING, title="Nivellierung", unique_id=None
        )
        hass.config_entries.async_add_subentry(entry, subentry)
    for old in [s for s in entry.subentries.values() if s.subentry_type == SUBENTRY_TANK_INPUTS]:
        hass.config_entries.async_remove_subentry(entry, old.subentry_id)

    hass.config_entries.async_update_entry(
        entry, data={}, options=options, version=2, minor_version=1
    )

    if subentry is not None:
        _move_leveling_to_subentry(hass, entry, subentry.subentry_id)
    _LOGGER.info("VAN PI CORE: Einstellungen auf Version 2 umgestellt")
    return True


def _move_leveling_to_subentry(hass: HomeAssistant, entry: ConfigEntry, subentry_id: str) -> None:
    """Bestehendes Gerät und Entitäten der Nivellierung dem neuen Eintrag zuordnen."""
    ent_reg = er.async_get(hass)
    prefix = f"{entry.entry_id}_leveling_"
    for reg in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if reg.unique_id.startswith(prefix):
            ent_reg.async_update_entity(reg.entity_id, config_subentry_id=subentry_id)
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(identifiers={(DOMAIN, f"{entry.entry_id}_leveling")})
    if device is None:
        return
    dev_reg.async_update_device(
        device.id, add_config_entry_id=entry.entry_id, add_config_subentry_id=subentry_id
    )
    if None in device.config_entries_subentries.get(entry.entry_id, set()):
        dev_reg.async_update_device(
            device.id, remove_config_entry_id=entry.entry_id, remove_config_subentry_id=None
        )


def _enable_reset_button(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Bis 0.1.2 war "Kalibrierung zurücksetzen" standardmäßig deaktiviert.

    Die Registry behält dieses Flag auch nach dem Update. Nur wenn die
    Integration es gesetzt hat (nicht der Nutzer), wird es wieder aktiviert.
    """
    registry = er.async_get(hass)
    unique_id = f"{entry.entry_id}_leveling_reset_calibration"
    entity_id = registry.async_get_entity_id("button", DOMAIN, unique_id)
    if entity_id is None:
        return
    reg_entry = registry.async_get(entity_id)
    if reg_entry and reg_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION:
        registry.async_update_entity(entity_id, disabled_by=None)
