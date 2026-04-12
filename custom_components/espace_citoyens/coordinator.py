"""DataUpdateCoordinator pour Espace Citoyens."""
from __future__ import annotations

import logging
import re
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    EspaceCitoyensAuthError,
    EspaceCitoyensClient,
    EspaceCitoyensConnectionError,
)
from .const import (
    CONF_MEMBRES,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL_HOURS,
    DOMAIN,
    TYPES_AVEC_RESERVATIONS,
    URL_COMMUNE_RE,
)

_LOGGER = logging.getLogger(__name__)


def _extract_commune(url: str) -> str:
    match = re.search(URL_COMMUNE_RE, url, re.IGNORECASE)
    return match.group(1).lower() if match else "inconnu"


class EspaceCitoyensCoordinator(DataUpdateCoordinator):
    """
    Récupère et met à jour les données de tous les membres sélectionnés.

    Structure de self.data :
    {
      "membres": [ { id_dynamic, nom, type, evenements } ],
      "tous_evenements": [ ... ],
      "par_type": { "cantine": [...], "periscolaire": [...], ... },
    }
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry   = entry
        self.commune = _extract_commune(entry.data.get(CONF_URL, ""))

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=DEFAULT_SCAN_INTERVAL_HOURS),
        )

        self.client = EspaceCitoyensClient(
            commune=self.commune,
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
        )
        self._membres_config: list[str] = (
            entry.options.get(CONF_MEMBRES)
            or entry.data.get(CONF_MEMBRES)
            or []
        )
        self._membres_info: list[dict[str, Any]] = []

    @property
    def cal_name(self) -> str:
        """Nom du calendrier configuré."""
        return (
            self.entry.options.get(CONF_NAME)
            or self.entry.data.get(CONF_NAME)
            or f"Espace-Citoyens - {self.commune.capitalize()}"
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Appelé par HA toutes les `update_interval`."""
        try:
            # ── 1. Membres (mis en cache, rechargés si vide) ───────────────────
            if not self._membres_info:
                self._membres_info = await self.client.async_get_membres()
                _LOGGER.debug(
                    "[%s] %d membres : %s",
                    self.commune,
                    len(self._membres_info),
                    [(m["nom"], m["type"]) for m in self._membres_info],
                )

            # ── 2. Filtrage selon la sélection utilisateur ────────────────────
            if self._membres_config:
                membres_actifs = [
                    m for m in self._membres_info
                    if m["id_dynamic"] in self._membres_config
                ]
            else:
                membres_actifs = [
                    m for m in self._membres_info
                    if m["type"] in TYPES_AVEC_RESERVATIONS
                ]

            # ── 3. Calendriers ────────────────────────────────────────────────
            membres_data: list[dict[str, Any]] = []
            tous_evenements: list[dict[str, Any]] = []

            for membre in membres_actifs:
                id_dyn = membre["id_dynamic"]
                try:
                    evenements = await self.client.async_get_calendrier(id_dyn)
                except EspaceCitoyensConnectionError as err:
                    _LOGGER.warning(
                        "Impossible de récupérer le calendrier de %s (id=%s) : %s",
                        membre["nom"], id_dyn, err,
                    )
                    evenements = []

                membres_data.append({**membre, "evenements": evenements})
                tous_evenements.extend(evenements)

            # ── 4. Index par type ─────────────────────────────────────────────
            par_type: dict[str, list[dict[str, Any]]] = {
                "cantine": [], "periscolaire": [], "centre_aere": [], "autre": [],
            }
            for evt in tous_evenements:
                par_type.setdefault(evt.get("type", "autre"), []).append(evt)

            return {
                "membres":         membres_data,
                "tous_evenements": tous_evenements,
                "par_type":        par_type,
            }

        except EspaceCitoyensAuthError as err:
            raise UpdateFailed(f"Erreur d'authentification : {err}") from err
        except EspaceCitoyensConnectionError as err:
            raise UpdateFailed(f"Erreur de connexion : {err}") from err
        except Exception as err:
            _LOGGER.exception("Erreur inattendue dans le coordinator")
            raise UpdateFailed(f"Erreur inattendue : {err}") from err
