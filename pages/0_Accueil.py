import streamlit as st

st.title("Trouver le bon lycée GT — et calculer son score Affelnet")

st.markdown("""
Si vous avez un enfant de 3e qui prépare son orientation en 2nde, vous êtes probablement
passé par Affelnet — la plateforme nationale d'affectation — et vous avez vécu la même
frustration : pour trouver le lycée qui correspond au projet de votre enfant, il faut
visiter chaque établissement un par un, croiser les informations à la main, et espérer
ne rien oublier.

**Le problème ?** Les outils officiels partent d'un lycée pour en lister les enseignements.
Mais une famille raisonne dans l'autre sens : *"mon enfant veut faire telles options,
quel lycée le propose ?"*

Cet outil inverse cette logique.
""")

st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("🔍 Recherche d'établissements")
    st.caption("Toute la France")
    st.markdown("""
On part des enseignements souhaités pour trouver les lycées qui les proposent —
et non l'inverse.

- Filtrage croisé **options de 2nde** / **spécialités de 1ère**
- Affinage géographique par académie, département, commune
- Fiche détail par établissement : effectifs, évolution sur 5 ans, carte interactive

**Cette partie est opérationnelle pour l'ensemble des lycées GT français.**
""")
    st.page_link("pages/1_Recherche_Etablissements.py", label="Accéder à la recherche →", icon="🏫")

with col2:
    st.subheader("🎯 Simulateur de score Affelnet")
    st.caption("Académie de Versailles — 78 / 91 / 92 / 95")
    st.markdown("""
Le score Affelnet conditionne l'affectation, mais le rectorat ne le publie pas.
Ce simulateur le reconstitue à partir du barème officiel :

- **Bonus géographique** : secteur ou hors secteur, détecté automatiquement
- **Bonus IPS** : selon l'indice de position sociale du collège de l'élève
- **Bonus boursier**
- **Score scolaire** : notes trimestrielles → tranchage → harmonisation → pondération

**Fonctionnel uniquement pour les départements 78, 91, 92 et 95.**
""")
    st.page_link("pages/2_Simulateur_Affelnet.py", label="Accéder au simulateur →", icon="📊")

st.divider()

with st.expander("⚠️ Limites méthodologiques"):
    st.markdown("""
- **Score indicatif** : le calcul s'appuie sur le barème académique de Versailles, reconstitué
  à partir des travaux de [Frédéric Gaume](https://fgaume.medium.com/etude-du-score-affelnet-6f884c117339).
  Il ne s'agit pas d'un score officiel. Les seuils d'admission par établissement ne sont pas
  publiés pour l'académie de Versailles — le simulateur calcule un score mais ne peut pas
  conclure "admis" ou "refusé".
- **Harmonisation académique** : les paramètres µ/σ utilisés sont ceux de l'académie de Paris
  (2022–2025). Les valeurs de l'académie de Versailles ne sont pas publiées.
- **IPS collèges** : données arrêtées à 2021-2022.
- **Sectorisation** : 7 lycées sur 131 n'ont pas pu être associés automatiquement à un code UAI
  et sont exclus.
""")

with st.expander("📂 Sources de données"):
    st.markdown("""
**Application principale**
- [Enseignements optionnels de 2nde GT](https://opendata.onisep.fr) — ONISEP Idéo
- [Enseignements de spécialité de 1ère générale](https://opendata.onisep.fr) — ONISEP Idéo
- [Structures des établissements secondaires](https://opendata.onisep.fr) — ONISEP Idéo
- [Effectifs lycées GT](https://www.data.gouv.fr) — data.gouv.fr

**Simulateur Affelnet**
- [IPS des collèges](https://data.education.gouv.fr/explore/dataset/fr-en-ips_colleges) — data.education.gouv.fr
- PDFs de sectorisation GT — rectorat de Versailles (rentrée 2025)
- Paramètres µ/σ d'harmonisation — proxy académie de Paris 2022–2025,
  source [affelnet-paris.web.app](https://affelnet-paris.web.app)
""")
