# Recherche d'établissements — Lycée général

Application Streamlit permettant de trouver des lycées proposant une combinaison donnée d'options de 2nde et de spécialités de 1ère générale, et de simuler son score d'affectation Affelnet (académie de Versailles).

## Fonctionnalités

- Filtrage géographique par académie, département et commune (en cascade)
- Recherche par nom d'établissement
- Filtrage pédagogique croisé : options de 2nde / spécialités de 1ère
- Fiche détail par établissement (adresse, lien ONISEP, effectifs, évolution)
- Carte interactive (OpenStreetMap)
- **Simulateur Affelnet** — calcul du score d'affectation pour l'académie de Versailles (78 / 91 / 92 / 95)

### Simulateur Affelnet

Le simulateur calcule le score Affelnet d'un élève de 3e pour ses vœux d'entrée en 2nde GT :

```
Score = Bonus géographique + Bonus IPS + Bonus boursier + Score scolaire
```

**Saisie :**
- Profil élève : commune de résidence, collège (IPS), boursier, mode de calcul (avant / après réforme 2026)
- Notes par trimestre sur 7 champs disciplinaires (Maths, Français, Histoire-Géo, Langues, Sciences, Arts, EPS)
- Niveaux de maîtrise du socle commun (8 compétences)
- Vœux : les lycées de secteur sont détectés automatiquement ; d'autres lycées peuvent être ajoutés manuellement

**Résultats :**
- Décomposition du score scolaire par champ (note tranchée → harmonisée → pondérée)
- Score total par vœu avec décomposition de chaque composante
- Indicateur de capacité d'accueil (effectif 2nde GT de référence)
- Bouton "Charger un exemple" pour tester rapidement avec un profil pré-rempli

**Limites méthodologiques** (affichées dans l'interface) :
- Paramètres µ/σ d'harmonisation issus de l'académie de Paris (proxy — Versailles ne publie pas ces données)
- Seuils d'admission par lycée non publiés pour Versailles → pas de verdict "admis / refusé"
- IPS collèges arrêtés à 2021-2022
- 7 lycées sur 131 exclus de la sectorisation (UAI non résolu automatiquement)

## Installation

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Sources de données

### Application principale

Données ouvertes ONISEP — Idéo (fichiers à placer dans `data/source/`) :

- [Enseignements optionnels de 2nde GT](https://opendata.onisep.fr/data/60113c3d5fee0/2-ideo-enseignements-optionnels-de-seconde-generale-et-technologique.htm)
- [Enseignements de spécialité de 1ère générale](https://opendata.onisep.fr/data/60113f395cce6/2-ideo-enseignements-de-specialite-de-premiere-generale.htm)
- [Structures des établissements secondaires](https://opendata.onisep.fr) — coordonnées géo, statut, contact
- [Effectifs lycées GT](https://www.data.gouv.fr/datasets/effectifs-deleves-par-niveau-sexe-langues-vivantes-1-et-2-les-plus-frequentes-par-lycee-denseignement-general-et-technologique-date-dobservation-au-debut-du-mois-doctobre-chaque-annee) — data.gouv.fr

### Simulateur Affelnet (données à placer dans `data/source/affelnet/`)

- [IPS des collèges](https://data.education.gouv.fr/explore/dataset/fr-en-ips_colleges) — indice de position sociale par établissement (data.education.gouv.fr), format parquet
- PDFs de sectorisation GT académie de Versailles — `ac-versailles.fr` (78 Yvelines, 91 Essonne, 92 Hauts-de-Seine, 95 Val-d'Oise)
- µ/σ d'harmonisation académique — proxy Paris 2022–2025, source [affelnet-paris.web.app](https://affelnet-paris.web.app)

## Préparation des données offline

Avant le premier lancement, ou après mise à jour des sources Affelnet, exécuter les scripts de précalcul dans l'ordre :

```bash
# 1. Extraire la sectorisation depuis les 4 PDFs → parquet
#    Entrée  : data/source/affelnet/sectorisation/*.pdf
#    Sortie  : data/source/affelnet/sectorisation/sectorisation-versailles.parquet
env/Scripts/python.exe scripts/build_sectorisation.py

# 2. Précalculer les données Affelnet (harmonisation, IPS, capacités)
#    Entrée  : sources ci-dessus + fr-en-lycee_gt-effectifs-niveau-sexe-lv.csv
#    Sorties : data/source/affelnet/harmonisation/harmonisation-proxy.json
#              data/source/affelnet/ips-colleges-versailles.parquet
#              data/source/affelnet/capacite-2nde-gt.parquet
env/Scripts/python.exe scripts/build_affelnet_data.py
```

### Fichiers générés

| Fichier | Description |
|---|---|
| `sectorisation-versailles.parquet` | 657 communes × 176 zones × 124 lycées UAI — sectorisation GT Versailles |
| `harmonisation-proxy.json` | µ/σ par champ disciplinaire 2022–2025 (proxy Paris pour harmonisation académique) |
| `ips-colleges-versailles.parquet` | 529 collèges Versailles avec IPS, catégorie et bonus Affelnet précalculé |
| `capacite-2nde-gt.parquet` | Effectif 2nde GT dernière année par lycée (proxy capacité d'accueil) |

### Limites méthodologiques

> Ces données sont utilisées à des fins de simulation indicative. Elles ne permettent pas de prédire avec certitude le résultat d'une affectation Affelnet.

- **Harmonisation académique** : les paramètres µ/σ utilisés sont ceux de l'académie de Paris (2022–2025). Les valeurs de l'académie de Versailles ne sont pas publiées. L'impact sur le score calculé est faible (les deux académies ont des distributions proches) mais introduit une approximation.
- **Seuils d'admission** : les scores du dernier élève admis par lycée ne sont pas publiés pour Versailles. Le simulateur calcule un score mais ne peut pas conclure "admis" ou "refusé".
- **IPS collèges** : données arrêtées à 2021-2022. L'IPS évolue peu d'une année sur l'autre ; l'approximation est acceptable.
- **Capacités d'accueil** : estimées à partir des effectifs réels de 2nde GT (dernière année disponible), pas des capacités théoriques officielles.
- **Sectorisation** : issue de PDFs publiés par le rectorat de Versailles (rentrée 2025). 7 lycées sur 131 n'ont pas pu être associés automatiquement à un code UAI et sont exclus.

## Auteur

[William Ramarques](https://www.linkedin.com/in/william-ramarques-1a017525/)
