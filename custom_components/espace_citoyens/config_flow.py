"""Config Flow pour Espace Citoyens."""
from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

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
    DOMAIN,
    TYPES_AVEC_RESERVATIONS,
    URL_COMMUNE_RE,
)

_LOGGER = logging.getLogger(__name__)


def _extract_commune(url: str) -> str | None:
    """Extrait le nom de la commune depuis l'URL Espace Citoyens."""
    match = re.search(URL_COMMUNE_RE, url.strip(), re.IGNORECASE)
    return match.group(1).lower() if match else None


class EspaceCitoyensConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gère la configuration initiale."""

    VERSION = 1

    def __init__(self) -> None:
        self._commune:  str = ""
        self._username: str = ""
        self._password: str = ""
        self._name:     str = ""
        self._url:      str = ""
        self._membres:  list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Étape 1 : URL du portail + identifiants + nom."""
        errors: dict[str, str] = {}

        if user_input is not None:
            raw_url  = user_input[CONF_URL].strip()
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]
            name     = user_input.get(CONF_NAME, "").strip()

            commune = _extract_commune(raw_url)
            if not commune:
                errors[CONF_URL] = "invalid_url"
            else:
                if not name:
                    name = f"Espace-Citoyens - {commune.capitalize()}"

                await self.async_set_unique_id(f"{commune}_{username}")
                self._abort_if_unique_id_configured()

                client = EspaceCitoyensClient(commune, username, password)
                try:
                    await client.async_login()
                    membres = await client.async_get_membres()
                except EspaceCitoyensAuthError:
                    errors["base"] = "invalid_auth"
                    membres = []
                except EspaceCitoyensConnectionError:
                    errors["base"] = "cannot_connect"
                    membres = []
                except Exception:
                    _LOGGER.exception("Erreur inattendue lors de la configuration")
                    errors["base"] = "unknown"
                    membres = []
                finally:
                    await client.async_close()

                if not errors:
                    self._commune  = commune
                    self._username = username
                    self._password = password
                    self._name     = name
                    self._url      = raw_url
                    self._membres  = [
                        m for m in membres
                        if m["type"] in TYPES_AVEC_RESERVATIONS
                    ]

                    if self._membres:
                        return await self.async_step_membres()

                    return self.async_create_entry(
                        title=name,
                        data={
                            CONF_URL:      raw_url,
                            CONF_USERNAME: username,
                            CONF_PASSWORD: password,
                            CONF_NAME:     name,
                            CONF_MEMBRES:  [],
                        },
                    )

        schema = vol.Schema({
            vol.Required(CONF_URL):      str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_NAME, default=""): str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_membres(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Étape 2 : sélection des membres."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._name,
                data={
                    CONF_URL:      self._url,
                    CONF_USERNAME: self._username,
                    CONF_PASSWORD: self._password,
                    CONF_NAME:     self._name,
                    CONF_MEMBRES:  user_input.get(CONF_MEMBRES, []),
                },
            )

        options = {
            m["id_dynamic"]: f"{m['nom']} ({m['type']})"
            for m in self._membres
        }

        schema = vol.Schema({
            vol.Required(
                CONF_MEMBRES, default=list(options.keys())
            ): cv.multi_select(options),
        })

        return self.async_show_form(step_id="membres", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> EspaceCitoyensOptionsFlow:
        return EspaceCitoyensOptionsFlow(config_entry)


class EspaceCitoyensOptionsFlow(config_entries.OptionsFlow):
    """Options : modifier le nom et les membres."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        commune = _extract_commune(self.config_entry.data.get(CONF_URL, "")) or ""

        current_name = (
            self.config_entry.options.get(CONF_NAME)
            or self.config_entry.data.get(CONF_NAME)
            or f"Espace-Citoyens - {commune.capitalize()}"
        )
        current_membres = (
            self.config_entry.options.get(CONF_MEMBRES)
            or self.config_entry.data.get(CONF_MEMBRES)
            or []
        )

        client = EspaceCitoyensClient(
            commune=commune,
            username=self.config_entry.data[CONF_USERNAME],
            password=self.config_entry.data[CONF_PASSWORD],
        )
        membres: list[dict[str, Any]] = []
        try:
            await client.async_login()
            membres = await client.async_get_membres()
        except Exception:
            pass
        finally:
            await client.async_close()

        membres_filtrés = [m for m in membres if m["type"] in TYPES_AVEC_RESERVATIONS]

        schema_dict: dict[Any, Any] = {
            vol.Optional(CONF_NAME, default=current_name): str,
        }
        if membres_filtrés:
            options = {
                m["id_dynamic"]: f"{m['nom']} ({m['type']})"
                for m in membres_filtrés
            }
            schema_dict[
                vol.Required(CONF_MEMBRES, default=current_membres)
            ] = cv.multi_select(options)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
        )
