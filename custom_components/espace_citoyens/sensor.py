"""Plateforme Sensor pour Espace Citoyens."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from .const import CONF_NAME, DOMAIN
from .coordinator import EspaceCitoyensCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: EspaceCitoyensCoordinator = hass.data[DOMAIN][entry.entry_id]

    cal_name = (
        entry.options.get(CONF_NAME)
        or entry.data.get(CONF_NAME)
        or f"Espace-Citoyens - {coordinator.commune.capitalize()}"
    )

    async_add_entities([
        EspaceCitoyensCompteurSensor(coordinator, cal_name),
        EspaceCitoyensProchainSensor(coordinator, cal_name),
    ])


class _Base(CoordinatorEntity, SensorEntity):
    """Base commune."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: EspaceCitoyensCoordinator,
        cal_name: str,
        unique_suffix: str,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_name      = name
        self._attr_unique_id = (
            f"{coordinator.commune}_"
            f"{coordinator.entry.data.get('username', '')}_"
            f"{unique_suffix}"
        )
        self._cal_name = cal_name

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(
                DOMAIN,
                f"{self.coordinator.commune}_"
                f"{self.coordinator.entry.data.get('username', '')}",
            )},
            name=self._cal_name,
            manufacturer="Arpège",
            model="Espace Citoyens",
        )

    def _get_reservations_futures(self) -> list[dict[str, Any]]:
        """Retourne toutes les réservations futures, dédupliquées."""
        if not self.coordinator.data:
            return []
        now = dt_util.now().date()
        seen: set[str] = set()
        result = []
        for membre in self.coordinator.data.get("membres", []):
            for evt in membre.get("evenements", []):
                if evt["uid"] in seen:
                    continue
                seen.add(evt["uid"])
                if evt["statut"] == "reservation" and evt["date"] >= now:
                    result.append({**evt, "_membre_nom": membre["nom"]})
        return sorted(result, key=lambda e: e["date"])


class EspaceCitoyensCompteurSensor(_Base):
    """Nombre de réservations futures sur la commune."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "réservations"
    _attr_icon = "mdi:calendar-check"

    def __init__(self, coordinator: EspaceCitoyensCoordinator, cal_name: str) -> None:
        super().__init__(
            coordinator,
            cal_name,
            unique_suffix="compteur_reservations",
            name=f"Réservations – {cal_name}",
        )

    @property
    def native_value(self) -> int:
        return len(self._get_reservations_futures())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        futures = self._get_reservations_futures()
        return {
            "commune": self.coordinator.commune,
            "prochaines": [
                {
                    "membre": e["_membre_nom"],
                    "date":   e["date"].isoformat(),
                    "heure":  e["start"].strftime("%H:%M") if e.get("start") else "Journée",
                    "titre":  e["summary"],
                    "type":   e["type"],
                    "lieu":   e.get("lieu", ""),
                }
                for e in futures[:10]
            ],
        }


class EspaceCitoyensProchainSensor(_Base):
    """Titre du prochain événement réservé."""

    _attr_icon = "mdi:calendar-arrow-right"

    def __init__(self, coordinator: EspaceCitoyensCoordinator, cal_name: str) -> None:
        super().__init__(
            coordinator,
            cal_name,
            unique_suffix="prochain_evenement",
            name=f"Prochain événement – {cal_name}",
        )

    def _get_prochain(self) -> dict[str, Any] | None:
        futures = self._get_reservations_futures()
        return futures[0] if futures else None

    @property
    def native_value(self) -> str:
        evt = self._get_prochain()
        if not evt:
            return "Aucune réservation"
        nom = evt.get("_membre_nom", "")
        return f"{nom} – {evt['summary']}" if nom else evt["summary"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        evt = self._get_prochain()
        if not evt:
            return {"commune": self.coordinator.commune}
        return {
            "commune": self.coordinator.commune,
            "membre":  evt.get("_membre_nom", ""),
            "date":    evt["date"].isoformat(),
            "heure":   evt["start"].strftime("%H:%M") if evt.get("start") else "Journée",
            "type":    evt["type"],
            "groupe":  evt.get("groupe_lib", ""),
            "lieu":    evt.get("lieu", ""),
        }
