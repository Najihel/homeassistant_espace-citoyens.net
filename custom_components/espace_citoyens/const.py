"""Constantes pour l'intégration Espace Citoyens (Arpège)."""

DOMAIN = "espace_citoyens"

# ── Clés de configuration ──────────────────────────────────────────────────────
CONF_URL      = "url"             # URL complète : https://www.espace-citoyens.net/COMMUNE/espace-citoyens/
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_MEMBRES  = "membres"         # liste des idDynamic sélectionnés
CONF_NAME     = "name"            # nom personnalisé du calendrier

# ── Extraction de la commune depuis l'URL ──────────────────────────────────────
# URL attendue : https://www.espace-citoyens.net/{commune}/espace-citoyens/
# Regex : groupe 1 = commune
URL_COMMUNE_RE = r"https?://www\.espace-citoyens\.net/([^/]+)/espace-citoyens"

# ── URLs (construites depuis la commune extraite) ──────────────────────────────
URL_HOME       = "https://www.espace-citoyens.net/{commune}/espace-citoyens/"
URL_LOGIN      = "https://www.espace-citoyens.net/{commune}/espace-citoyens/Home/Logon"
URL_LOGOFF     = "https://www.espace-citoyens.net/{commune}/espace-citoyens/Home/LogOff"
URL_COMPTE     = "https://www.espace-citoyens.net/{commune}/espace-citoyens/CompteCitoyen"
URL_CALENDRIER = (
    "https://www.espace-citoyens.net/{commune}/espace-citoyens"
    "/FichePersonne/DetailPersonneGetCalendrier?idDynamic={id_dynamic}"
)

# ── Cookie d'authentification ──────────────────────────────────────────────────
AUTH_COOKIE = "ASP.NET_SessionIdEC"

# ── Images → type de membre ───────────────────────────────────────────────────
MEMBRE_IMAGES = {
    "pere.png":        "pere",
    "mere.png":        "mere",
    "garcon.png":      "enfant",
    "fillette.png":    "enfant",
    "agent_fille.png": "contact",
    "agent_homme.png": "contact",
}
TYPES_AVEC_RESERVATIONS = {"pere", "mere", "enfant"}

# ── Détection du type de prestation ───────────────────────────────────────────
KEYWORDS_CANTINE      = ["restauration", "repas", "cantine"]
KEYWORDS_PERISCOLAIRE = ["périscolaire", "periscolaire", "garderie", "accueil péri"]
KEYWORDS_CENTRE_AERE  = ["alsh", "loisirs", "vacances", "centre aéré", "centre aere", "mercredis"]

# ── Statuts ────────────────────────────────────────────────────────────────────
STATUT_BIENTOT = "Bientôt disponible"

# ── Types de prestations ───────────────────────────────────────────────────────
TYPE_CANTINE      = "cantine"
TYPE_PERISCOLAIRE = "periscolaire"
TYPE_CENTRE_AERE  = "centre_aere"
TYPE_AUTRE        = "autre"

PRESTATION_LABELS = {
    TYPE_CANTINE:      "Restauration scolaire",
    TYPE_PERISCOLAIRE: "Périscolaire",
    TYPE_CENTRE_AERE:  "Centre de loisirs",
    TYPE_AUTRE:        "Autre",
}
PRESTATION_ICONS = {
    TYPE_CANTINE:      "mdi:food-fork-drink",
    TYPE_PERISCOLAIRE: "mdi:school",
    TYPE_CENTRE_AERE:  "mdi:beach",
    TYPE_AUTRE:        "mdi:calendar",
}

# ── Refresh ────────────────────────────────────────────────────────────────────
DEFAULT_SCAN_INTERVAL_HOURS = 1
