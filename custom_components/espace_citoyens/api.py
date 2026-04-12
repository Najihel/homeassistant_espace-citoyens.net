"""
Client HTTP pour Espace Citoyens (Arpège).

Gestion de session :
  - Connexion propre via GET (CSRF) + POST (login)
  - Déconnexion explicite via /Home/LogOff avant chaque reconnexion
  - Reconnexion automatique si HTTP 500 ou redirection vers Logon
  - La session aiohttp est recréée à chaque cycle login/logoff
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, time
from html import unescape
from typing import Any

import aiohttp
from bs4 import BeautifulSoup

from .const import (
    AUTH_COOKIE,
    KEYWORDS_CENTRE_AERE,
    KEYWORDS_PERISCOLAIRE,
    KEYWORDS_CANTINE,
    MEMBRE_IMAGES,
    STATUT_BIENTOT,
    TYPE_AUTRE,
    TYPE_CANTINE,
    TYPE_CENTRE_AERE,
    TYPE_PERISCOLAIRE,
    URL_CALENDRIER,
    URL_COMPTE,
    URL_HOME,
    URL_LOGIN,
    URL_LOGOFF,
)

_LOGGER = logging.getLogger(__name__)


# ── Exceptions ─────────────────────────────────────────────────────────────────

class EspaceCitoyensAuthError(Exception):
    """Identifiants incorrects."""

class EspaceCitoyensConnectionError(Exception):
    """Problème réseau ou serveur inaccessible."""

class EspaceCitoyensParseError(Exception):
    """Impossible de parser la réponse."""


# ── Client ─────────────────────────────────────────────────────────────────────

class EspaceCitoyensClient:
    """Gère l'authentification et les appels API Espace Citoyens."""

    def __init__(self, commune: str, username: str, password: str) -> None:
        self.commune  = commune.strip().lower()
        self.username = username
        self.password = password
        self._session: aiohttp.ClientSession | None = None
        self._authenticated = False

    # ── Utilitaires ────────────────────────────────────────────────────────────

    def _url(self, template: str, **kwargs: Any) -> str:
        return template.format(commune=self.commune, **kwargs)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Retourne la session HTTP existante ou en crée une nouvelle."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(ssl=False)
            self._session = aiohttp.ClientSession(
                connector=connector,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:149.0) "
                        "Gecko/20100101 Firefox/149.0"
                    ),
                    "Accept-Language": "fr,fr-FR;q=0.9,en-US;q=0.8,en;q=0.7",
                },
            )
        return self._session

    async def _close_session(self) -> None:
        """Ferme proprement la session HTTP."""
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    async def async_close(self) -> None:
        """Déconnexion propre + fermeture de la session."""
        if self._authenticated:
            await self._async_logoff()
        await self._close_session()
        self._authenticated = False

    # ── Déconnexion ────────────────────────────────────────────────────────────

    async def _async_logoff(self) -> None:
        """
        Déconnexion explicite via /Home/LogOff.

        Permet au serveur de libérer la session et évite les conflits
        lors de la prochaine reconnexion.
        """
        if self._session is None or self._session.closed:
            return
        logoff_url = self._url(URL_LOGOFF)
        compte_url = self._url(URL_COMPTE)
        try:
            async with self._session.get(
                logoff_url,
                headers={"Referer": compte_url},
                allow_redirects=True,
            ) as resp:
                _LOGGER.debug("LogOff HTTP %s pour %s", resp.status, self.commune)
        except Exception as err:
            _LOGGER.debug("LogOff ignoré (erreur) : %s", err)

    # ── Authentification ───────────────────────────────────────────────────────

    async def async_login(self) -> None:
        """
        Authentifie l'utilisateur.

        Cycle complet :
          1. Déconnexion de l'éventuelle session précédente (LogOff)
          2. Fermeture et recréation de la session HTTP (cookies repartent à zéro)
          3. GET page de login → extraction du token CSRF
          4. POST credentials
        """
        # Déconnexion propre si déjà connecté
        if self._authenticated:
            await self._async_logoff()
            self._authenticated = False

        # Recrée une session fraîche (sans cookies résiduels)
        await self._close_session()
        session = await self._get_session()

        home_url  = self._url(URL_HOME)
        login_url = self._url(URL_LOGIN)

        try:
            # ── GET : page de login → token CSRF ──────────────────────────────
            _LOGGER.debug("[%s] GET %s", self.commune, home_url)
            async with session.get(home_url, allow_redirects=True) as resp:
                if resp.status != 200:
                    raise EspaceCitoyensConnectionError(
                        f"Portail inaccessible (HTTP {resp.status})"
                    )
                html = await resp.text()

            soup = BeautifulSoup(html, "html.parser")
            token_input = soup.find("input", {"name": "__RequestVerificationToken"})
            if not token_input:
                raise EspaceCitoyensParseError("Token CSRF introuvable dans la page de login")
            csrf_token = token_input.get("value", "")

            # ── POST : envoi des credentials ──────────────────────────────────
            payload = {
                "__RequestVerificationToken": csrf_token,
                "username": self.username,
                "password": self.password,
            }
            _LOGGER.debug("[%s] POST %s", self.commune, login_url)
            async with session.post(
                login_url,
                data=payload,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Referer": home_url,
                    "Origin": "https://www.espace-citoyens.net",
                },
                allow_redirects=True,
            ) as resp:
                final_url = str(resp.url)
                _LOGGER.debug("[%s] Redirection finale : %s (HTTP %s)", self.commune, final_url, resp.status)

                if "Logon" in final_url or "Home" in final_url:
                    body = await resp.text()
                    soup2 = BeautifulSoup(body, "html.parser")
                    err_el = soup2.find(class_=re.compile(r"error|alert|invalid", re.I))
                    msg = err_el.get_text(strip=True) if err_el else "Identifiants incorrects"
                    raise EspaceCitoyensAuthError(msg)

                if resp.status not in (200, 302):
                    raise EspaceCitoyensConnectionError(
                        f"Erreur connexion (HTTP {resp.status})"
                    )

        except (aiohttp.ClientError, TimeoutError) as err:
            raise EspaceCitoyensConnectionError(f"Erreur réseau : {err}") from err

        self._authenticated = True
        _LOGGER.info("[%s] Authentification réussie pour %s", self.commune, self.username)

    async def _ensure_auth(self) -> None:
        """Reconnecte si la session n'est pas authentifiée."""
        if not self._authenticated:
            await self.async_login()

    async def _handle_session_expired(self) -> None:
        """
        Gère l'expiration de session (HTTP 500 ou redirection Logon).

        Effectue un cycle LogOff + Login complet pour repartir sur une
        session propre.
        """
        _LOGGER.info(
            "[%s] Session expirée détectée — reconnexion en cours", self.commune
        )
        self._authenticated = False
        await self.async_login()

    # ── Famille ────────────────────────────────────────────────────────────────

    async def async_get_membres(self) -> list[dict[str, Any]]:
        """
        Scrape CompteCitoyen pour récupérer les membres de la famille.

        Retourne une liste de dicts :
          { id_dynamic, nom, type, image }
        """
        await self._ensure_auth()
        session = await self._get_session()
        url = self._url(URL_COMPTE)

        try:
            async with session.get(url) as resp:
                if resp.status == 500 or "Logon" in str(resp.url):
                    await self._handle_session_expired()
                    session = await self._get_session()
                    async with session.get(url) as resp2:
                        html = await resp2.text()
                else:
                    html = await resp.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise EspaceCitoyensConnectionError(f"Erreur réseau : {err}") from err

        return self._parse_membres(html)

    def _parse_membres(self, html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        membres: list[dict[str, Any]] = []
        seen: set[str] = set()
        pattern = re.compile(r"DetailPersonne\?idDynamic=(\d+)")

        for a_tag in soup.find_all("a", href=pattern):
            href = a_tag.get("href", "")
            match = pattern.search(href)
            if not match:
                continue
            id_dynamic = match.group(1)
            if id_dynamic in seen:
                continue
            seen.add(id_dynamic)

            img = a_tag.find("img")
            nom = img.get("alt", "").strip() if img else ""
            img_src = img.get("src", "") if img else ""
            img_file = img_src.split("/")[-1]
            type_membre = MEMBRE_IMAGES.get(img_file, "inconnu")

            membres.append({
                "id_dynamic": id_dynamic,
                "nom":        nom or f"Membre {id_dynamic}",
                "type":       type_membre,
                "image":      img_file,
            })
            _LOGGER.debug("[%s] Membre : id=%s nom=%s type=%s", self.commune, id_dynamic, nom, type_membre)

        if not membres:
            _LOGGER.warning("[%s] Aucun membre trouvé sur CompteCitoyen", self.commune)
        return membres

    # ── Calendrier ─────────────────────────────────────────────────────────────

    async def async_get_calendrier(self, id_dynamic: str) -> list[dict[str, Any]]:
        """
        Récupère le calendrier d'un membre.

        En cas de HTTP 500 (session expirée côté serveur) :
          → LogOff + Login complet + nouvelle tentative (une seule fois)
        """
        await self._ensure_auth()
        return await self._fetch_calendrier(id_dynamic, retry=True)

    async def _fetch_calendrier(
        self, id_dynamic: str, retry: bool
    ) -> list[dict[str, Any]]:
        session = await self._get_session()
        url = self._url(URL_CALENDRIER, id_dynamic=id_dynamic)

        try:
            async with session.get(
                url, headers={"X-Requested-With": "XMLHttpRequest"}
            ) as resp:

                # ── Session expirée (500 ou redirect Logon) ────────────────────
                if resp.status == 500 or "Logon" in str(resp.url):
                    if retry:
                        await self._handle_session_expired()
                        return await self._fetch_calendrier(id_dynamic, retry=False)
                    raise EspaceCitoyensConnectionError(
                        f"Erreur calendrier idDynamic={id_dynamic} (HTTP {resp.status}) après reconnexion"
                    )

                if resp.status != 200:
                    raise EspaceCitoyensConnectionError(
                        f"Erreur calendrier idDynamic={id_dynamic} (HTTP {resp.status})"
                    )

                data = await resp.json(content_type=None)

        except (aiohttp.ClientError, TimeoutError) as err:
            raise EspaceCitoyensConnectionError(f"Erreur réseau : {err}") from err

        return self._parse_calendrier(data, id_dynamic)

    def _parse_calendrier(
        self, data: dict[str, Any], id_dynamic: str
    ) -> list[dict[str, Any]]:
        groupes_raw    = data.get("EvenementsGroupes", [])
        evenements_raw = data.get("EvenementSystemes", [])

        if not evenements_raw:
            return []

        groupes_index: dict[str, dict[str, Any]] = {
            g["IdGroupeEvt"]: {
                "lib":  g.get("LibNomGroupeEvt", ""),
                "type": self._detect_type(g.get("LibNomGroupeEvt", "")),
                "lieu": g.get("LibComplementGroupeEvt", ""),
            }
            for g in groupes_raw
        }

        result = []
        for raw in evenements_raw:
            evt = self._normalise_evenement(raw, groupes_index, id_dynamic)
            if evt is not None:
                result.append(evt)

        _LOGGER.debug(
            "[%s] idDynamic=%s : %d événements (%d bruts)",
            self.commune, id_dynamic, len(result), len(evenements_raw),
        )
        return result

    def _normalise_evenement(
        self,
        raw: dict[str, Any],
        groupes_index: dict[str, dict[str, Any]],
        id_dynamic: str,
    ) -> dict[str, Any] | None:
        lib_evt   = raw.get("LibEvenement", "")
        id_evt    = raw.get("IdEvenement", "P0")
        date_int  = raw.get("DateEvenement")
        id_groupe = raw.get("IdGroupeEvt", "")
        heure_deb = raw.get("HeureDebutEvenement", "")
        heure_fin = raw.get("HeureFinEvenement", "")
        lib_corps = raw.get("LibCorpsEvenement", "")
        actions   = raw.get("ListeActions", [])

        if STATUT_BIENTOT in lib_evt:
            return None
        if not date_int:
            return None

        try:
            evt_date = _parse_date_int(date_int)
        except (ValueError, TypeError):
            return None

        all_day = not heure_deb or not heure_fin
        start_dt = end_dt = None
        if not all_day:
            try:
                start_dt = datetime.combine(evt_date, _parse_hhmm(heure_deb))
                end_dt   = datetime.combine(evt_date, _parse_hhmm(heure_fin))
            except ValueError:
                all_day = True

        statut_raw = lib_evt.rsplit("-", 1)[-1].strip()
        statut = {"Résa": "reservation", "Prés": "presence", "Abs": "absence"}.get(
            statut_raw, "reservation"
        )

        groupe    = groupes_index.get(id_groupe, {})
        groupe_lib = groupe.get("lib", "")
        lieu       = groupe.get("lieu", "")
        type_prest = groupe.get("type", TYPE_AUTRE)
        description = _html_to_text(lib_corps)
        action_libs = [a.get("LibAction", "") for a in actions]
        peut_modifier = any("Modifier" in a or "Effectuer" in a for a in action_libs)
        peut_absenter = any("absence" in a.lower() for a in action_libs)

        summary = _build_summary(groupe_lib, statut, lib_evt)

        uid = (
            f"ec_{id_dynamic}_{date_int}_{id_groupe}_{lib_evt}"
            if id_evt == "P0"
            else f"ec_{id_dynamic}_{id_evt}"
        )

        return {
            "uid":           uid,
            "id_dynamic":    id_dynamic,
            "date":          evt_date,
            "start":         start_dt,
            "end":           end_dt,
            "all_day":       all_day,
            "statut":        statut,
            "type":          type_prest,
            "groupe_lib":    groupe_lib,
            "lieu":          lieu,
            "summary":       summary,
            "description":   description,
            "peut_modifier": peut_modifier,
            "peut_absenter": peut_absenter,
        }

    @staticmethod
    def _detect_type(lib: str) -> str:
        lib_l = lib.lower()
        if any(k in lib_l for k in KEYWORDS_CANTINE):
            return TYPE_CANTINE
        if any(k in lib_l for k in KEYWORDS_PERISCOLAIRE):
            return TYPE_PERISCOLAIRE
        if any(k in lib_l for k in KEYWORDS_CENTRE_AERE):
            return TYPE_CENTRE_AERE
        return TYPE_AUTRE


# ── Fonctions utilitaires ──────────────────────────────────────────────────────

def _parse_date_int(value: int | str) -> date:
    s = str(value)
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def _parse_hhmm(value: str) -> time:
    v = value.strip()
    if len(v) == 4:
        return time(int(v[:2]), int(v[2:]))
    raise ValueError(f"Format heure invalide : {value!r}")


def _html_to_text(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return "\n".join(lines)


def _build_summary(groupe_lib: str, statut: str, lib_evt: str) -> str:
    if groupe_lib:
        title = groupe_lib
    else:
        parts = lib_evt.rsplit("-", 1)
        title = parts[0].strip() if len(parts) > 1 else lib_evt

    if statut == "absence":
        return f"{title} (Absent)"
    return title
