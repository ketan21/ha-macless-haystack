"""The Macless Haystack integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_MODE, MODE_APPLE, MODE_ENDPOINT
from .coordinator import BaseMaclessHaystackCoordinator, EndpointCoordinator
from .coordinator_apple import AppleAccountCoordinator

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER, Platform.SENSOR]

MaclessHaystackConfigEntry = ConfigEntry[BaseMaclessHaystackCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: MaclessHaystackConfigEntry
) -> bool:
    """Set up one configured account or endpoint."""
    if entry.data.get(CONF_MODE, MODE_ENDPOINT) == MODE_APPLE:
        coordinator: BaseMaclessHaystackCoordinator = AppleAccountCoordinator(
            hass, entry
        )
    else:
        coordinator = EndpointCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MaclessHaystackConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, entry: MaclessHaystackConfigEntry
) -> bool:
    """Add the mode to the entries of version 1."""
    if entry.version == 1:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_MODE: MODE_ENDPOINT}, version=2
        )
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: MaclessHaystackConfigEntry
) -> None:
    """Reload the entry when the options change."""
    await hass.config_entries.async_reload(entry.entry_id)
