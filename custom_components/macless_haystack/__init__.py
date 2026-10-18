"""The Macless Haystack integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import MaclessHaystackCoordinator

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER, Platform.SENSOR]

MaclessHaystackConfigEntry = ConfigEntry[MaclessHaystackCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: MaclessHaystackConfigEntry
) -> bool:
    """Set up one configured endpoint."""
    coordinator = MaclessHaystackCoordinator(hass, entry)
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


async def _async_update_listener(
    hass: HomeAssistant, entry: MaclessHaystackConfigEntry
) -> None:
    """Reload the entry when the options change."""
    await hass.config_entries.async_reload(entry.entry_id)
