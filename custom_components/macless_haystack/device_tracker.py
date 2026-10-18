"""Device tracker for a Macless Haystack accessory."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.core import callback

from .const import BATTERY_STATUS
from .coordinator import MaclessHaystackCoordinator
from .entity import MaclessHaystackEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up the tracker entities."""
    coordinator: MaclessHaystackCoordinator = entry.runtime_data
    async_add_entities(
        MaclessDeviceTracker(coordinator, accessory)
        for accessory in coordinator.accessories
    )


class MaclessDeviceTracker(MaclessHaystackEntity, TrackerEntity):
    """GPS tracker for one accessory."""

    _attr_entity_category = None
    _attr_name = None

    def __init__(
        self, coordinator: MaclessHaystackCoordinator, accessory: dict[str, Any]
    ) -> None:
        super().__init__(coordinator, accessory)
        self._attr_unique_id = f"{self._accessory_id}_tracker"
        self._update_attrs()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Write the latest report to the state machine."""
        self._update_attrs()
        super()._handle_coordinator_update()

    def _update_attrs(self) -> None:
        state = self.accessory_state
        if state is None:
            return
        self._attr_latitude = state.latitude
        self._attr_longitude = state.longitude
        self._attr_location_accuracy = state.accuracy or 0
        self._attr_extra_state_attributes = {
            "confidence": state.confidence,
            "battery": BATTERY_STATUS.get(state.battery),
            "raw_status": state.status,
            "last_seen": state.last_seen.isoformat() if state.last_seen else None,
        }
