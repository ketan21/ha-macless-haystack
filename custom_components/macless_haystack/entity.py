"""Base entity for the Macless Haystack integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AccessoryState, MaclessHaystackCoordinator
from .crypto import accessory_unique_id


class MaclessHaystackEntity(CoordinatorEntity[MaclessHaystackCoordinator]):
    """Entity for one accessory."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: MaclessHaystackCoordinator, accessory: dict[str, Any]
    ) -> None:
        super().__init__(coordinator)
        self._accessory_id = accessory_unique_id(accessory)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._accessory_id)},
            name=accessory.get("name") or "FindMy device",
            manufacturer="Macless Haystack",
            model="FindMy accessory",
        )

    @property
    def accessory_state(self) -> AccessoryState | None:
        """Return the latest state of this accessory."""
        return self.coordinator.data.get(self._accessory_id)
