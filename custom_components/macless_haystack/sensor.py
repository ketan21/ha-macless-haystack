"""Sensors for a Macless Haystack accessory."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfLength

from .const import BATTERY_PERCENT, BATTERY_STATUS
from .coordinator import BaseMaclessHaystackCoordinator
from .entity import MaclessHaystackEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up the sensor entities."""
    coordinator: BaseMaclessHaystackCoordinator = entry.runtime_data
    entities: list[MaclessHaystackEntity] = []
    for accessory in coordinator.accessories:
        entities.extend(
            (
                MaclessBatterySensor(coordinator, accessory),
                MaclessAccuracySensor(coordinator, accessory),
                MaclessLastSeenSensor(coordinator, accessory),
            )
        )
    async_add_entities(entities)


class MaclessBatterySensor(MaclessHaystackEntity, SensorEntity):
    """Battery of an accessory."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_name = "Battery"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, accessory) -> None:
        super().__init__(coordinator, accessory)
        self._attr_unique_id = f"{self._accessory_id}_battery"

    @property
    def native_value(self) -> int | None:
        """Return the battery level as a percentage."""
        state = self.accessory_state
        if state is None or state.battery is None:
            return None
        return BATTERY_PERCENT.get(state.battery)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state = self.accessory_state
        return {"status": BATTERY_STATUS.get(state.battery)} if state else {}


class MaclessAccuracySensor(MaclessHaystackEntity, SensorEntity):
    """Horizontal accuracy of the latest report."""

    _attr_icon = "mdi:crosshairs-gps"
    _attr_name = "Accuracy"
    _attr_native_unit_of_measurement = UnitOfLength.METERS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, accessory) -> None:
        super().__init__(coordinator, accessory)
        self._attr_unique_id = f"{self._accessory_id}_accuracy"

    @property
    def native_value(self) -> int | None:
        state = self.accessory_state
        return state.accuracy if state else None


class MaclessLastSeenSensor(MaclessHaystackEntity, SensorEntity):
    """Time of the latest report."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_name = "Last seen"

    def __init__(self, coordinator, accessory) -> None:
        super().__init__(coordinator, accessory)
        self._attr_unique_id = f"{self._accessory_id}_last_seen"

    @property
    def native_value(self):
        state = self.accessory_state
        return state.last_seen if state else None
