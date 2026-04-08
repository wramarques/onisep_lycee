# Recherche d'établissements — Lycée général

Application Streamlit permettant de trouver des lycées proposant une combinaison donnée d'options de 2nde et de spécialités de 1ère générale.

## Fonctionnalités

- Filtrage géographique par académie et département (en cascade)
- Recherche par nom d'établissement
- Filtrage pédagogique croisé : options de 2nde / spécialités de 1ère
- Fiche détail par établissement (adresse, lien ONISEP, liste complète des enseignements)

## Installation

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Sources de données

Données ouvertes ONISEP — Idéo :

- [Enseignements optionnels de 2nde générale et technologique](https://opendata.onisep.fr/data/60113c3d5fee0/2-ideo-enseignements-optionnels-de-seconde-generale-et-technologique.htm?tab=table_696e194665dfb)
- [Enseignements de spécialité de 1ère générale](https://opendata.onisep.fr/data/60113f395cce6/2-ideo-enseignements-de-specialite-de-premiere-generale.htm?tab=table_696e14792e7ed)
- [Lycées — données générales](https://www.data.gouv.fr/datasets/lycees-donnees-generales) (coordonnées géographiques, statut, contact)

Les fichiers CSV sont à placer dans `data/source/`.
