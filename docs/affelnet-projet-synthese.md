# Projet Affelnet — Synthèse & Documentation technique

> Généré à partir d'une session de recherche — Avril 2026  
> Objectif : application de simulation / prédiction d'affectation au lycée

---

## 1. Contexte général

**Affelnet** (Affectation des élèves par le Net) est le logiciel national du Ministère de l'Éducation Nationale qui gère l'affectation des collégiens de 3e dans les lycées publics.

- Couvre : entrée en 2de GT, 2de professionnelle, 1re année de CAP
- Fonctionne par académie (paramètres locaux sur une base logicielle nationale)
- **Académie cible du projet : Versailles** (78 / 91 / 92 / 95)
- Utilisateurs cibles : familles / élèves de 3e

### Calendrier type (académie de Versailles)

| Période | Étape |
|---|---|
| Avril | Consultation des offres de formation |
| Mai (5–26) | Saisie des vœux (via téléservice ou établissement) |
| Début juin | Décision d'orientation du conseil de classe |
| 30 juin | Publication des résultats tour 1 |
| Début juillet | Inscription dans l'établissement d'affectation |
| Juillet | Tour 2 pour les non-affectés |

---

## 2. Algorithme d'affectation

### 2.1 Appariement : Gale & Shapley (Deferred Acceptance)

L'algorithme est le même dans toutes les académies françaises.

- Les **lycées** proposent (côté lycée-optimal)
- Le classement des lycées est généré automatiquement par un **score en points**
- L'algorithme est **stable** : si un élève avec moins de points est admis à un lycée, c'est que l'élève évincé a été admis ailleurs sur un vœu mieux classé
- **Conséquence importante** : on peut mettre ses vœux préférés en premier sans risquer de perdre les lycées de repli

### 2.2 Deux tours séparés

L'algorithme tourne **deux fois** :
1. D'abord uniquement avec les **boursiers** (places réservées)
2. Ensuite avec les **non-boursiers** sur les places restantes

---

## 3. Calcul du score (barème)

Le score d'un vœu = somme de 4 composantes :

```
Score = Bonus géographique + Bonus IPS + Bonus boursier + Score scolaire (LSU)
```

### 3.1 Bonus géographique (critère dominant)

| Situation | Points |
|---|---|
| Lycée de secteur 1 (domicile de l'élève) | **~32 640 pts** |
| Lycée hors secteur (secteur 2) | **~17 760 pts** |
| Très hors secteur (secteur 3) | **~16 800 pts** |

> ⚠️ Ce bonus représente ~80% du score total — c'est le critère qui détermine presque entièrement l'affectation.  
> La sectorisation ne s'applique qu'à la voie GT. **Il n'y a pas de sectorisation pour la voie professionnelle.**

### 3.2 Bonus IPS (Indice de Position Sociale)

Attribué selon l'IPS du **collège de scolarisation** de l'élève :

| IPS du collège | Bonus |
|---|---|
| Collège favorisé | 0 pt |
| Collège intermédiaire | 600 pts |
| Collège défavorisé | 1 200 pts |

Les données IPS des collèges sont disponibles en open data : `data.education.gouv.fr`

### 3.3 Bonus boursier

- **+600 points** si l'élève est boursier de l'Éducation nationale
- Inopérant au 1er tour (les boursiers concourent séparément)
- Utile au 2e tour pour prioriser les boursiers sur les places restantes

### 3.4 Score scolaire — Bilan périodique (jusqu'à ~4 800 pts)

Calcul en **4 étapes** :

#### Étape 1 : Tranchage des notes

Chaque note trimestrielle est convertie sur une échelle à 4 niveaux :

| Moyenne | Points |
|---|---|
| < 5 | 3 pts |
| 5 ≤ moy < 10 | 8 pts |
| 10 ≤ moy < 15 | 13 pts |
| ≥ 15 | 16 pts |

On calcule ensuite la **moyenne des trimestres tranchés** (arrondie à 2 décimales).

#### Étape 2 : Regroupement en 7 champs disciplinaires

| Champ | Matières |
|---|---|
| MATHÉMATIQUES | Mathématiques |
| FRANÇAIS | Français |
| HISTOIRE-GÉO | moyenne(Histoire-Géo, EMC) |
| LANGUES VIVANTES | moyenne(LV1, LV2) |
| SCIENCES-TECHNO | moyenne(Physique-Chimie, SVT, Technologie) |
| ARTS | moyenne(Arts Plastiques, Éducation Musicale) |
| EPS | EPS |

#### Étape 3 : Harmonisation académique

Formule appliquée par champ disciplinaire :

```
H = 10 × [10 + (T - µ) / σ]
```

Où :
- `T` = note du champ disciplinaire de l'élève
- `µ` = moyenne académique du champ
- `σ` = écart-type académique du champ

> ⚠️ Les valeurs µ et σ **ne sont pas publiées par l'académie de Versailles** (contrairement à Paris).  
> Pour Paris, ces données sont disponibles de 2021 à 2025 (voir section Sources).

#### Étape 4 : Pondération

| Champ | Coefficient |
|---|---|
| Mathématiques | **5** |
| Français | **5** |
| Histoire-Géo | 4 |
| Langues Vivantes | 4 |
| Sciences-Techno | 4 |
| Arts | 4 |
| EPS | 4 |

**Score bilan périodique = somme pondérée des 7 champs harmonisés** (arrondi à 3 décimales)

> **Nouveauté 2026** : suite à la réforme du DNB, les notes sont valorisées au réel (sur 20) sans application des tranches 5/10/15/20. Un lissage académique est appliqué.

### 3.5 Score scolaire — Bilan de fin de cycle (jusqu'à 4 800 pts)

8 compétences du socle commun, évaluées sur 50 points chacune :

| Compétence | Points possibles |
|---|---|
| Maîtrise insuffisante | 10 |
| Maîtrise fragile | 25 |
| Maîtrise satisfaisante | 40 |
| Très bonne maîtrise | 50 |

**Score socle = somme des 8 compétences × 12**  
Maximum : 400 × 12 = **4 800 pts**

Les 8 compétences :
1. Langages des arts et du corps
2. Langues étrangères et régionales
3. Langue française
4. Langages mathématiques, scientifiques et informatiques
5. Formation de la personne et du citoyen
6. Méthodes et outils pour apprendre
7. Représentations du monde et activité humaine
8. Systèmes naturels et systèmes techniques

---

## 4. État des données disponibles

### 4.1 Ce qui est accessible (open data)

| Donnée | URL | Format |
|---|---|---|
| IPS des collèges | `data.education.gouv.fr` | CSV |
| Capacités d'accueil par lycée | `data.education.gouv.fr` | CSV |
| Attractivité voie pro (nb vœux vs capacité) | `data.education.gouv.fr` | CSV / API |
| Coefficients champs disciplinaires par formation | `ac-versailles.fr/affelnet-documents` | PDF (fiches) |
| Adresses et géolocalisation des établissements | `data.education.gouv.fr` | CSV / API |

### 4.2 Ce qui N'est PAS public pour Versailles

| Donnée manquante | Impact |
|---|---|
| **Seuils d'admission par lycée** (barème dernier entrant) | Impossible de dire "admis / refusé" |
| **Paramètres statistiques µ et σ** par champ | Harmonisation approximative seulement |
| **Table collège → lycées de secteur** avec bonus IPS structurée | Sectorisation à reconstruire |

### 4.3 Ce qui existe pour Paris (académie de Paris uniquement)

Le travail de reverse-engineering de Frédéric Gaume ([@fgaume](https://github.com/fgaume/affelnet)) a produit pour Paris :
- Seuils d'admission non-boursiers 2021–2025 par lycée
- Seuils d'admission boursiers partiels 2025
- Paramètres µ / σ de 2021 à 2025 par champ disciplinaire
- Table complète collège → 5 lycées de secteur 1 + bonus IPS
- Application web : https://affelnet75.web.app/

> ⚠️ Ces données sont **spécifiques à Paris** et non transposables à Versailles.

---

## 5. Impact de l'absence de données sur le projet

### Ce qu'on peut faire malgré tout

- ✅ Calculer le **score exact** d'un élève sur chaque vœu
- ✅ Comparer des scénarios (ordre des vœux, impact d'un lycée de secteur vs hors secteur)
- ✅ Identifier les **leviers d'amélioration** du score scolaire
- ✅ Positionner l'élève dans la **distribution académique** (percentile estimé)
- ✅ Utiliser la **pression par lycée** (nb vœux / capacité) comme proxy de sélectivité

### Ce qu'on ne peut pas faire

- ❌ Prédire l'admission / le refus avec certitude
- ❌ Donner une probabilité précise d'admission par lycée
- ❌ Classer les lycées par seuil d'accessibilité réel

### Positionnement produit recommandé

> **Simulateur de score + aide à la stratégie de vœux**  
> (plutôt que prédicteur d'affectation)

---

## 6. Stratégie de collecte de données (moyen terme)

Pour construire les données manquantes sur Versailles :

**Approche crowdsourcing** (inspirée de Gaume pour Paris) :
1. Après les résultats du tour 1 (fin juin), inviter les familles à soumettre leur **fiche-barème** (document remis par le rectorat sur demande)
2. Agréger les seuils du dernier admis par lycée
3. Constituer progressivement une base historique année après année

> La fiche-barème individuelle contient : score de l'élève + score du dernier admis pour chaque lycée demandé.

---

## 7. Architecture applicative suggérée

```
affelnet-simulator/
├── data/
│   ├── ips-colleges.csv          # open data : IPS par collège
│   ├── capacites-lycees.csv      # open data : capacités d'accueil
│   ├── sectorisation.json        # à construire : collège → lycées de secteur
│   └── seuils-historiques.json   # à collecter : seuils admission par lycée/année
├── src/
│   ├── scoring/
│   │   ├── tranchage.js          # étape 1 : conversion notes → points
│   │   ├── champs.js             # étape 2 : regroupement disciplinaire
│   │   ├── harmonisation.js      # étape 3 : H = 10×[10+(T-µ)/σ]
│   │   ├── ponderation.js        # étape 4 : coefficients × harmonisé
│   │   └── score-total.js        # bonus géo + IPS + boursier + LSU
│   ├── matching/
│   │   └── gale-shapley.js       # algorithme d'appariement (optionnel)
│   └── ui/
│       └── simulator.jsx         # interface React
└── README.md
```

---

## 8. Sources & références

| Source | URL | Contenu |
|---|---|---|
| Académie de Versailles | `ac-versailles.fr/affelnet-lycee-121477` | Procédure officielle |
| Documents Affelnet Versailles | `ac-versailles.fr/affelnet-documents` | Fiches coefficients, calendrier |
| Data Education nationale | `data.education.gouv.fr` | Datasets open data |
| Onisep open data | `opendata.onisep.fr` | Attractivité voie pro |
| Arrêté légifrance 2023 | `legifrance.gouv.fr/jorf/id/JORFTEXT000048736103` | Cadre légal du traitement |
| Travail Frédéric Gaume (Paris) | `github.com/fgaume/affelnet` | Reverse-engineering algorithme |
| Article score Affelnet | `fgaume.medium.com/etude-du-score-affelnet-6f884c117339` | Détail calcul score Paris |
| Article algorithme appariement | `fgaume.medium.com/lalgorithme-d-appariement-d-affelnet-3156a50a3594` | Gale & Shapley expliqué |
| Note IPP réforme Paris | `ipp.eu/wp-content/uploads/2023/02/Note_IPP_88.pdf` | Évaluation réforme IPS 2021 |
| Boîte à outils Paris | `affelnet75.web.app` | App de simulation Paris |

---

## 9. Points de vigilance pour le développement

1. **Lissage académique** : sans les µ/σ de Versailles, utiliser ceux de Paris comme approximation ou proposer une entrée manuelle
2. **Réforme 2026** : le calcul des notes change (suppression du tranchage 5/10/15/20, valorisation au réel) — prévoir deux modes de calcul selon l'année
3. **Sectorisation** : l'académie de Versailles propose un outil en ligne de recherche du lycée de secteur — envisager un scraping ou une intégration API si disponible
4. **Voie pro vs GT** : pas de sectorisation en voie pro, coefficients différents par famille de métiers
5. **Boursiers** : traitement séparé au 1er tour — le simulateur doit clairement distinguer les deux cas
6. **Dérogations** : 6 motifs officiels permettent de demander un lycée hors secteur (appliqué uniquement sur le 1er vœu)

---

*Document généré le 17 avril 2026*
