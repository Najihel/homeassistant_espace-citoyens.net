"""Plateforme Calendrier pour Espace Citoyens.

Un seul calendrier par commune.
Chaque événement est préfixé par le prénom/nom du membre concerné.
Les doublons (même uid) sont automatiquement dédupliqués.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
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
    """Crée l'unique calendrier de la commune."""
    coordinator: EspaceCitoyensCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Nom personnalisé saisi lors de la configuration
    cal_name = (
        entry.options.get(CONF_NAME)
        or entry.data.get(CONF_NAME)
        or f"Espace-Citoyens - {coordinator.commune.capitalize()}"
    )

    async_add_entities([
        EspaceCitoyensCalendar(
            coordinator=coordinator,
            name=cal_name,
        )
    ])


class EspaceCitoyensCalendar(CoordinatorEntity, CalendarEntity):
    """
    Calendrier unique regroupant tous les événements de la commune.

    Chaque événement est préfixé par le nom du membre :
      "Gwendal – 📅 Réservation – Accueil Périscolaire matin"
    """

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: EspaceCitoyensCoordinator,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_name      = name
        self._attr_icon      = "mdi:calendar-account"
        self._attr_unique_id = (
            f"{coordinator.commune}_"
            f"{coordinator.entry.data.get('username', '')}_"
            f"calendar"
        )

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(
                DOMAIN,
                f"{self.coordinator.commune}_"
                f"{self.coordinator.entry.data.get('username', '')}",
            )},
            name=self._attr_name,
            manufacturer="Arpège",
            model="Espace Citoyens",
        )

    def _get_evenements_dedupliques(self) -> list[dict[str, Any]]:
        """
        Retourne tous les événements de tous les membres, sans doublons.

        La déduplication se fait sur l'uid de l'événement.
        Le nom du membre est ajouté dans chaque événement pour le préfixage.
        """
        if not self.coordinator.data:
            return []

        seen_uids: set[str] = set()
        result: list[dict[str, Any]] = []

        for membre in self.coordinator.data.get("membres", []):
            nom_membre = membre["nom"]
            for evt in membre.get("evenements", []):
                uid = evt["uid"]
                if uid in seen_uids:
                    continue
                seen_uids.add(uid)
                # Enrichit l'événement avec le nom du membre
                result.append({**evt, "_membre_nom": nom_membre})

        return result

    @property
    def event(self) -> CalendarEvent | None:
        """Prochain événement réservé à venir."""
        now = datetime.now(tz=dt_util.DEFAULT_TIME_ZONE)
        upcoming = [
            e for e in self._get_evenements_dedupliques()
            if e["statut"] in ("reservation", "presence")
            and _evt_end_dt(e) >= now
        ]
        if not upcoming:
            return None
        nxt = min(upcoming, key=_evt_start_dt)
        return _to_calendar_event(nxt)

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Retourne tous les événements dans la plage demandée par HA."""
        result: list[CalendarEvent] = []
        for evt in self._get_evenements_dedupliques():
            evt_start = _evt_start_dt(evt)
            evt_end   = _evt_end_dt(evt)
            if evt_end >= start_date and evt_start <= end_date:
                result.append(_to_calendar_event(evt))
        return result


# ── Fonctions utilitaires ──────────────────────────────────────────────────────

def _as_local(dt: datetime) -> datetime:
    """S'assure qu'un datetime est timezone-aware en heure locale HA."""
    if dt.tzinfo is None:
        return dt_util.as_local(dt)
    return dt


def _evt_start_dt(evt: dict[str, Any]) -> datetime:
    """Retourne le datetime de début, timezone-aware."""
    if evt.get("start"):
        return _as_local(evt["start"])
    d = evt["date"]
    return dt_util.as_local(datetime(d.year, d.month, d.day, 0, 0, 0))


def _evt_end_dt(evt: dict[str, Any]) -> datetime:
    """Retourne le datetime de fin, timezone-aware."""
    if evt.get("end"):
        return _as_local(evt["end"])
    d = evt["date"]
    end_date = date(d.year, d.month, d.day) + timedelta(days=1)
    return dt_util.as_local(
        datetime(end_date.year, end_date.month, end_date.day, 0, 0, 0)
    )


def _to_calendar_event(evt: dict[str, Any]) -> CalendarEvent:
    """
    Convertit un événement normalisé en CalendarEvent HA.

    Le titre est préfixé par le nom du membre :
      "Gwendal – 📅 Réservation – Accueil Périscolaire matin"

    Règles HA strictes :
      - Journée entière → start/end de type `date`
      - Avec heure      → start/end de type `datetime` timezone-aware
    """
    if evt["all_day"]:
        d = evt["date"]
        start: date | datetime = d
        end:   date | datetime = d + timedelta(days=1)
    else:
        start = _evt_start_dt(evt)
        end   = _evt_end_dt(evt)
        if end <= start:
            end = start + timedelta(hours=1)

    # Préfixe par le nom du membre
    nom_membre = evt.get("_membre_nom", "")
    summary = f"{nom_membre} – {evt['summary']}" if nom_membre else evt["summary"]

    # Description enrichie
    desc_parts = [evt["description"]] if evt.get("description") else []
    if evt.get("lieu"):
        desc_parts.append(f"Lieu : {evt['lieu']}")
    description = "\n".join(desc_parts) or None

    return CalendarEvent(
        start=start,
        end=end,
        summary=summary,
        description=description,
        uid=evt["uid"],
    )
