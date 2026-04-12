# Espace Citoyens pour Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue.svg)](https://www.home-assistant.io/)

Intégration Home Assistant pour les portails **Espace Citoyens** développés par la société **Arpège**.

Récupère automatiquement les réservations de vos enfants dans un calendrier Home Assistant :
- Cantine / Restauration scolaire
- Périscolaire (garderie matin et soir)
- Centre de loisirs / ALSH (mercredis, petites et grandes vacances)

---

## ⚠️ Avertissement

**Cette intégration est fournie telle quelle, sans garantie d'aucune sorte.**
Le créateur de cette intégration ne peut être tenu responsable des problèmes potentiels liés à son utilisation, notamment : perte de données, dysfonctionnements de Home Assistant, incompatibilités avec les mises à jour du portail Espace Citoyens ou de Home Assistant, ou tout autre dommage direct ou indirect.

**Utilisez cette intégration à vos propres risques.**

---

## Installation via HACS

1. Dans HACS, cliquez sur **Intégrations**
2. Menu ⋮ → **Dépôts personnalisés**
3. Ajoutez l'URL `https://github.com/Najihel/homeassistant_espace-citoyens.net`, catégorie **Intégration**
4. Cliquez sur **Espace Citoyens** → **Télécharger**
5. Redémarrez Home Assistant

## Installation manuelle

Copiez le dossier `custom_components/espace_citoyens/` dans votre répertoire `config/custom_components/`.

---

## Configuration

1. **Paramètres → Appareils et services → Ajouter une intégration**
2. Recherchez **Espace Citoyens**
3. Renseignez :
   - **URL du portail** : l'URL complète de votre espace citoyens  
     Ex : `https://www.espace-citoyens.net/ma-commune/espace-citoyens/`
   - **Identifiant** et **Mot de passe** : vos identifiants du portail
   - **Nom du calendrier** (optionnel) : nom affiché dans HA, ex : `Famille Martin`
4. Sélectionnez les membres de la famille à surveiller

---

## Entités créées

### Calendrier
Un seul calendrier par commune. Les événements sont préfixés par le nom du membre :
```
Alice – Accueil Périscolaire matin
Bob – Restauration scolaire
```

### Capteurs
| Entité | Description |
|--------|-------------|
| `sensor.reservations_*` | Nombre de réservations futures |
| `sensor.prochain_evenement_*` | Titre du prochain événement réservé |

---

## Compatibilité

Testé sur les communes utilisant la plateforme Arpège Espace Citoyens.
Requiert Home Assistant 2024.1 ou supérieur.

---

## Crédits

- **Code** : généré par [Claude.ai](https://claude.ai)
- **Logo** : [Logo Mairie — Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Logo-Mairie.svg)
- **Portail** : [Espace-Citoyens.net par Arpège](https://arpege.fr/logiciels-gestion-relation-citoyen/portail-citoyen)
