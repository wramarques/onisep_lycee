import json
import sys
import unicodedata
import re
import math

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, ".")
from affelnet.scoring import (
    CHAMPS, COEFFICIENTS, COMPETENCES_SOCLE, NIVEAUX_SOCLE,
    score_bilan_periodique, score_socle, score_total,
)

# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------
AFFELNET_DIR = "data/source/affelnet"
SECTEUR_PATH = f"{AFFELNET_DIR}/sectorisation/sectorisation-versailles.parquet"
IPS_PATH     = f"{AFFELNET_DIR}/ips-colleges-versailles.parquet"
CAPA_PATH    = f"{AFFELNET_DIR}/capacite-2nde-gt.parquet"
HARM_PATH    = f"{AFFELNET_DIR}/harmonisation/harmonisation-proxy.json"

# ---------------------------------------------------------------------------
# Labels UI
# ---------------------------------------------------------------------------
CHAMP_LABELS = {
    "MATHEMATIQUES":    "Mathématiques",
    "FRANCAIS":         "Français",
    "HISTOIRE-GEO":     "Histoire-Géo / EMC",
    "LANGUES VIVANTES": "Langues vivantes (LV1+LV2)",
    "SCIENCES-TECHNO":  "Sciences & Techno (PC / SVT / Techno)",
    "ARTS":             "Arts (Arts plastiques / Éducation musicale)",
    "EPS":              "EPS",
}

MATIERES_PAR_CHAMP = {
    "MATHEMATIQUES": [
        ("MATHS", "Mathématiques"),
    ],
    "FRANCAIS": [
        ("FRANCAIS", "Français"),
    ],
    "HISTOIRE-GEO": [
        ("HISTOIRE_GEO", "Histoire-Géo"),
        ("EMC", "EMC"),
    ],
    "LANGUES VIVANTES": [
        ("LV1", "LV1"),
        ("LV2", "LV2"),
    ],
    "SCIENCES-TECHNO": [
        ("PHYS_CHIMIE", "Physique-Chimie"),
        ("SVT", "SVT"),
        ("TECHNO", "Technologie"),
    ],
    "ARTS": [
        ("ARTS_PLASTIQUES", "Arts plastiques"),
        ("EDU_MUSICALE", "Éducation musicale"),
    ],
    "EPS": [
        ("EPS", "EPS"),
    ],
}

SOCLE_MATIERES = {
    "Langages des arts et du corps": "EPS, arts plastiques, education musicale, expression orale/scenique.",
    "Langues étrangères et régionales": "LV1, LV2, sections/langues regionales le cas echeant.",
    "Langue française": "Francais (oral, ecrit, comprehension, redaction).",
    "Langages mathématiques, scientifiques et informatiques": "Mathematiques, physique-chimie, SVT, technologie, numerique.",
    "Formation de la personne et du citoyen": "EMC, vie de classe, projets citoyens, comportement et engagement.",
    "Méthodes et outils pour apprendre": "Toutes matieres: organisation, autonomie, methode de travail, recherche documentaire.",
    "Représentations du monde et activité humaine": "Histoire-geographie, lettres, langues, arts et culture generale.",
    "Systèmes naturels et systèmes techniques": "SVT, physique-chimie, technologie, demarche experimentale.",
}

# Profil élève exemple pour test rapide
EXEMPLE = {
    "commune":  "Boulogne-Billancourt",
    "college":  "JEAN MONNET",
    "boursier": False,
    "mode_2026": True,
    "notes": {
        "MATHS": [10.0, 10.0, 10.0],
        "FRANCAIS": [10.0, 10.0, 10.0],
        "HISTOIRE_GEO": [10.0, 10.0, 10.0],
        "EMC": [10.0, 10.0, 10.0],
        "LV1": [10.0, 10.0, 10.0],
        "LV2": [10.0, 10.0, 10.0],
        "PHYS_CHIMIE": [10.0, 10.0, 10.0],
        "SVT": [10.0, 10.0, 10.0],
        "TECHNO": [10.0, 10.0, 10.0],
        "ARTS_PLASTIQUES": [10.0, 10.0, 10.0],
        "EDU_MUSICALE": [10.0, 10.0, 10.0],
        "EPS": [10.0, 10.0, 10.0],
    },
    "socle": ["Maîtrise satisfaisante"] * 5 + ["Très bonne maîtrise"] * 3,
}


# ---------------------------------------------------------------------------
# Chargement données (caché)
# ---------------------------------------------------------------------------
@st.cache_data
def load_secteur():
    return pd.read_parquet(SECTEUR_PATH)


@st.cache_data
def load_ips():
    return pd.read_parquet(IPS_PATH)


@st.cache_data
def load_capa():
    return pd.read_parquet(CAPA_PATH)


@st.cache_data
def load_harmo():
    with open(HARM_PATH, encoding="utf-8") as f:
        data = json.load(f)
    # Dernière année disponible par champ
    df = pd.DataFrame(data)
    derniere = df.groupby("champ")["annee"].max().reset_index()
    df = df.merge(derniere, on=["champ", "annee"])
    return {
        row["champ"]: {"moyenne": row["moyenne"], "ecart_type": row["ecart_type"]}
        for _, row in df.iterrows()
    }


def normalize(s):
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def fmt_points(value):
    if value is None:
        return "—"
    return f"{int(round(value)):,}".replace(",", " ")


def build_radar_chart(rows, axis_order, max_points, title):
    """Rendu radar robuste (cartesien) pour eviter les soucis theta/radius selon versions Vega."""
    df = pd.DataFrame(rows).copy()
    n_axes = len(axis_order)
    idx_by_axis = {a: i for i, a in enumerate(axis_order)}

    df["axis_idx"] = df["Axe"].map(idx_by_axis)
    df["angle"] = df["axis_idx"].apply(lambda i: 2 * math.pi * i / n_axes)
    df["x"] = df.apply(lambda r: r["Points"] * math.sin(r["angle"]), axis=1)
    df["y"] = df.apply(lambda r: r["Points"] * math.cos(r["angle"]), axis=1)

    # Fermer les polygones en repetant le premier point de chaque serie.
    closes = []
    for serie, g in df.groupby("Serie"):
        first = g.sort_values("axis_idx").iloc[0].copy()
        first["axis_idx"] = n_axes
        first["angle"] = 2 * math.pi
        first["x"] = first["Points"] * math.sin(first["angle"])
        first["y"] = first["Points"] * math.cos(first["angle"])
        closes.append(first)
    if closes:
        df = pd.concat([df, pd.DataFrame(closes)], ignore_index=True)

    # Grille radar: cercles + rayons.
    ring_levels = [max_points * f for f in [0.25, 0.5, 0.75, 1.0]]
    ring_rows = []
    for r in ring_levels:
        for i in range(n_axes + 1):
            angle = 2 * math.pi * i / n_axes
            ring_rows.append({"ring": r, "x": r * math.sin(angle), "y": r * math.cos(angle), "order": i})
    rings_df = pd.DataFrame(ring_rows)

    spoke_rows = []
    labels_rows = []
    for i, axis_name in enumerate(axis_order):
        angle = 2 * math.pi * i / n_axes
        x2 = max_points * math.sin(angle)
        y2 = max_points * math.cos(angle)
        spoke_rows.append({"axis": axis_name, "x": 0.0, "y": 0.0, "x2": x2, "y2": y2})
        labels_rows.append({
            "axis": axis_name,
            "x": (max_points * 1.12) * math.sin(angle),
            "y": (max_points * 1.12) * math.cos(angle),
        })
    spokes_df = pd.DataFrame(spoke_rows)
    labels_df = pd.DataFrame(labels_rows)

    rings = alt.Chart(rings_df).mark_line(color="#D7DCE5").encode(
        x=alt.X("x:Q", scale=alt.Scale(domain=[-max_points * 1.2, max_points * 1.2]), axis=None),
        y=alt.Y("y:Q", scale=alt.Scale(domain=[-max_points * 1.2, max_points * 1.2]), axis=None),
        detail="ring:Q",
        order="order:Q",
    )

    spokes = alt.Chart(spokes_df).mark_rule(color="#E3E7EF").encode(
        x=alt.X("x:Q", scale=alt.Scale(domain=[-max_points * 1.2, max_points * 1.2]), axis=None),
        y=alt.Y("y:Q", scale=alt.Scale(domain=[-max_points * 1.2, max_points * 1.2]), axis=None),
        x2="x2:Q",
        y2="y2:Q",
    )

    polygons = alt.Chart(df).mark_line(point=True, strokeWidth=2).encode(
        x=alt.X("x:Q", scale=alt.Scale(domain=[-max_points * 1.2, max_points * 1.2]), axis=None),
        y=alt.Y("y:Q", scale=alt.Scale(domain=[-max_points * 1.2, max_points * 1.2]), axis=None),
        color=alt.Color("Serie:N", sort=["Obtenu", "Potentiel max"]),
        detail="Serie:N",
        order="axis_idx:Q",
        tooltip=["Axe:N", "Serie:N", alt.Tooltip("Points:Q", format=",.0f")],
    )

    labels = alt.Chart(labels_df).mark_text(fontSize=10, color="#4B5563").encode(
        x=alt.X("x:Q", scale=alt.Scale(domain=[-max_points * 1.2, max_points * 1.2]), axis=None),
        y=alt.Y("y:Q", scale=alt.Scale(domain=[-max_points * 1.2, max_points * 1.2]), axis=None),
        text="axis:N",
    )

    return (alt.layer(rings, spokes, polygons, labels).properties(title=title, height=360))


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Simulateur Affelnet", layout="wide")
st.title("Simulateur Affelnet — Académie de Versailles")
st.caption("Voie générale et technologique (2nde GT) · Rentrée 2026")

# Avertissement méthodologique
st.warning(
    "**Simulation indicative uniquement.** "
    "Les paramètres d'harmonisation (µ/σ) sont ceux de l'académie de Paris (proxy). "
    "Les seuils d'admission par lycée ne sont pas publiés pour Versailles : "
    "ce simulateur calcule votre score mais ne peut pas prédire votre affectation.",
    icon="⚠️",
)

# Chargement
try:
    df_secteur = load_secteur()
    df_ips     = load_ips()
    df_capa    = load_capa()
    params_h   = load_harmo()
except FileNotFoundError as e:
    st.error(f"Fichier de données manquant : {e}. Lancez `scripts/build_affelnet_data.py`.")
    st.stop()

# ---------------------------------------------------------------------------
# Bouton exemple
# ---------------------------------------------------------------------------
col_title, col_ex = st.columns([4, 1])
with col_ex:
    if st.button("Charger un exemple", use_container_width=True):
        st.session_state["aff_exemple"] = True

use_exemple = st.session_state.get("aff_exemple", False)


def val(key, default):
    """Retourne la valeur d'exemple si le bouton a été cliqué, sinon default."""
    if not use_exemple:
        return default
    if key.startswith("note_"):
        parts = key.split("_")
        t_idx = int(parts[-1]) - 1
        matiere_id = "_".join(parts[1:-1])
        return EXEMPLE["notes"].get(matiere_id, [10.0, 10.0, 10.0])[t_idx]
    if key.startswith("socle_"):
        idx = int(key.split("_")[1])
        return EXEMPLE["socle"][idx]
    return EXEMPLE.get(key, default)


# ---------------------------------------------------------------------------
# Sidebar — profil élève
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("#### 👤 Profil élève")

    mode_2026 = st.toggle(
        "Réforme 2026 (notes au réel)",
        value=val("mode_2026", True),
        help="Depuis la rentrée 2026, les notes sont valorisées directement sans tranchage 5/10/15/20.",
    )
    boursier = st.toggle("Boursier de l'Éducation nationale", value=val("boursier", False))

    st.markdown("#### 🏫 Collège de scolarisation")
    communes_ips = sorted(df_ips["commune"].dropna().unique())
    commune_college = st.selectbox(
        "Commune du collège", [""] + communes_ips,
        index=communes_ips.index(val("commune", "Boulogne-Billancourt")) + 1
        if val("commune", "") in communes_ips else 0,
    )

    college_sel = None
    ips_val     = None
    bonus_ips_v = 0
    cat_ips     = None

    if commune_college:
        colleges_dispo = df_ips[df_ips["commune"] == commune_college]["nom"].sort_values().tolist()
        college_nom = st.selectbox("Collège", [""] + colleges_dispo)
        if college_nom:
            row_c = df_ips[df_ips["nom"] == college_nom].iloc[0]
            ips_val     = row_c["ips"]
            cat_ips     = row_c["categorie"]
            bonus_ips_v = int(row_c["bonus_ips"])
            st.info(f"IPS : **{ips_val:.1f}** — {cat_ips} → **+{bonus_ips_v} pts**")

    st.markdown("#### 🗺️ Commune de résidence")
    DEP_LABELS = {"78": "78 — Yvelines", "91": "91 — Essonne", "92": "92 — Hauts-de-Seine", "95": "95 — Val-d'Oise"}
    dep_res = st.selectbox("Département", [""] + list(DEP_LABELS.keys()),
                           format_func=lambda x: DEP_LABELS.get(x, "Tous"))
    if dep_res:
        communes_secteur = sorted(df_secteur[df_secteur["departement"] == dep_res]["ville"].dropna().unique())
    else:
        communes_secteur = sorted(df_secteur["ville"].dropna().unique())
    commune_res = st.selectbox(
        "Commune", [""] + communes_secteur,
        index=communes_secteur.index(val("commune", "Boulogne-Billancourt")) + 1
        if val("commune", "") in communes_secteur else 0,
    )

    # Auto-complétion des voies selon la commune sélectionnée
    voie_options = []
    if commune_res and "voie" in df_secteur.columns:
        voie_options = sorted(
            df_secteur[df_secteur["ville"] == commune_res]["voie"].dropna().unique().tolist()
        )

    voie_auto = st.selectbox(
        "Rue / voie (auto-complétion)",
        [""] + voie_options,
        index=0,
        help="Tapez quelques lettres pour filtrer la liste des voies de la commune.",
    )
    voie_res = voie_auto

# ---------------------------------------------------------------------------
# Lycées de secteur détectés
# ---------------------------------------------------------------------------
lycees_secteur = pd.DataFrame()
if commune_res:
    df_commune = df_secteur[df_secteur["ville"] == commune_res].copy()

    # Lookup voie similaire au script de test: tous les mots de la requête
    if voie_res and "voie" in df_commune.columns:
        voie_query_n = normalize(voie_res)
        mots_voie = voie_query_n.split()
        df_commune["voie_n"] = df_commune["voie"].fillna("").apply(normalize)
        mask_voie = df_commune["voie_n"].apply(lambda x: all(m in x for m in mots_voie))
        hits = df_commune[mask_voie]
        if not hits.empty:
            zones = hits["code_zone"].dropna().unique().tolist()
            lycees_secteur = df_commune[df_commune["code_zone"].isin(zones)].drop_duplicates("uai")
        else:
            lycees_secteur = pd.DataFrame()
    else:
        lycees_secteur = df_commune.drop_duplicates("uai")

# ---------------------------------------------------------------------------
# Onglets principaux
# ---------------------------------------------------------------------------
tab_notes, tab_socle, tab_voeux, tab_resultats = st.tabs([
    "📝 Notes", "📋 Socle commun", "🏫 Mes vœux", "📊 Résultats"
])

# ---- Notes ----------------------------------------------------------------
with tab_notes:
    if not mode_2026:
        st.caption("Mode **avant 2026** : les notes sont tranchées (< 5 → 3 pts, 5-10 → 8 pts, 10-15 → 13 pts, ≥ 15 → 16 pts) avant calcul.")
    else:
        st.caption("Mode **2026** : notes valorisées au réel, sans tranchage.")

    st.caption("Saisie par matière. Les champs Affelnet sont agrégés automatiquement (ex. Histoire-Géo + EMC).")

    notes_par_matiere = {}
    for champ in CHAMPS:
        st.markdown(f"**{CHAMP_LABELS[champ]}**")
        for matiere_id, matiere_label in MATIERES_PAR_CHAMP[champ]:
            cols = st.columns(3)
            trimestrielles = []
            for i, col in enumerate(cols):
                n = col.number_input(
                    f"{matiere_label} - T{i+1}",
                    min_value=0.0, max_value=20.0, step=0.5,
                    value=val(f"note_{matiere_id}_{i+1}", 10.0),
                    key=f"note_{matiere_id}_{i+1}",
                    label_visibility="visible",
                )
                trimestrielles.append(n)
            notes_par_matiere[matiere_id] = trimestrielles

    notes_par_champ = {}
    for champ in CHAMPS:
        mat_ids = [m_id for m_id, _ in MATIERES_PAR_CHAMP[champ]]
        notes_par_champ[champ] = [
            round(sum(notes_par_matiere[m_id][t] for m_id in mat_ids) / len(mat_ids), 2)
            for t in range(3)
        ]

# ---- Socle ----------------------------------------------------------------
with tab_socle:
    st.caption("8 compétences du socle commun (Brevet des collèges).")
    st.info(
        "Ces evaluations sont decidees par l'equipe pedagogique (enseignants, sous coordination du professeur principal), "
        "puis validees en fin de cycle 4, generalement au conseil de classe de 3e. "
        "Elles reposent sur des observations dans plusieurs matieres et situations, pas sur une seule note.",
        icon="ℹ️",
    )
    niveaux_socle = []
    for i, comp in enumerate(COMPETENCES_SOCLE):
        niv = st.radio(
            comp,
            options=list(NIVEAUX_SOCLE.keys()),
            index=list(NIVEAUX_SOCLE.keys()).index(val(f"socle_{i}", "Maîtrise satisfaisante")),
            horizontal=True,
            key=f"socle_{i}",
            help=f"Matieres principalement concernees: {SOCLE_MATIERES.get(comp, 'Evaluation transversale pluridisciplinaire.')}",
        )
        niveaux_socle.append(niv)

    s_socle = score_socle(niveaux_socle)
    st.metric("Score socle", f"{s_socle} pts", help="Maximum : 4 800 pts")

# ---- Vœux ----------------------------------------------------------------
with tab_voeux:
    if lycees_secteur.empty and not commune_res:
        st.info("Renseignez votre commune de résidence dans la barre latérale pour voir vos lycées de secteur.")
    elif voie_res and "voie" not in df_secteur.columns:
        st.warning(
            "La recherche par rue n'est pas disponible avec ce fichier de sectorisation. "
            "Relancez scripts/build_sectorisation.py pour régénérer le parquet avec la colonne voie."
        )
        st.markdown(f"**Lycées de secteur pour {commune_res}** (fallback commune uniquement)")
    elif lycees_secteur.empty:
        if voie_res:
            st.warning(f"Aucune correspondance pour « {commune_res} / {voie_res} » dans la sectorisation Versailles.")
        else:
            st.warning(f"Commune « {commune_res} » non trouvée dans la sectorisation Versailles.")
    else:
        if voie_res:
            st.markdown(f"**Lycées de secteur pour {commune_res} / {voie_res}** (détectés automatiquement)")
        else:
            st.markdown(f"**Lycées de secteur pour {commune_res}** (détectés automatiquement)")

    voeux = []
    if not lycees_secteur.empty:
        for _, r in lycees_secteur.iterrows():
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.markdown(f"**{r['lycee_nom']}** — {r['lycee_commune']}")
            secteur_val = c2.selectbox(
                "Secteur", [1, 2, 3],
                format_func=lambda x: {1: "Secteur 1 (mon lycée)", 2: "Hors secteur", 3: "Très hors secteur"}[x],
                index=0 if r["principal"] else 1,
                key=f"secteur_{r['uai']}",
                label_visibility="collapsed",
            )
            inclus = c3.checkbox("Inclure", value=True, key=f"incl_{r['uai']}")
            if inclus:
                voeux.append({"uai": r["uai"], "nom": r["lycee_nom"], "commune": r["lycee_commune"], "secteur": secteur_val})

    st.markdown("---")
    st.markdown("**Ajouter un lycée manuellement**")
    autres_lycees = sorted(df_secteur["lycee_nom"].dropna().unique())
    autre_nom = st.selectbox("Rechercher un lycée", [""] + autres_lycees, key="autre_lycee")
    if autre_nom:
        row_a = df_secteur[df_secteur["lycee_nom"] == autre_nom].iloc[0]
        sect_a = st.selectbox(
            "Secteur",
            [1, 2, 3],
            format_func=lambda x: {1: "Secteur 1", 2: "Hors secteur", 3: "Très hors secteur"}[x],
            index=1,
            key="secteur_autre",
        )
        if st.button("Ajouter ce lycée"):
            voeux.append({"uai": row_a["uai"], "nom": autre_nom, "commune": row_a["lycee_commune"], "secteur": sect_a})

    st.session_state["voeux"] = voeux

# ---- Résultats ------------------------------------------------------------
with tab_resultats:
    voeux_calc = st.session_state.get("voeux", [])

    bilan, detail_champs = score_bilan_periodique(notes_par_champ, params_h, mode_2026)
    s_socle_r = score_socle(niveaux_socle)
    score_scolaire = bilan + s_socle_r

    max_bilan = 4800
    max_socle = 4800
    max_bonus_geo = 32640
    max_bonus_ips = 1200
    max_bonus_boursier = 600
    score_total_max = max_bilan + max_socle + max_bonus_geo + max_bonus_ips + max_bonus_boursier

    st.markdown("**Décomposition du score scolaire**")
    rows_detail = []
    for champ in CHAMPS:
        d = detail_champs.get(champ, {})
        rows_detail.append({
            "Champ": CHAMP_LABELS[champ],
            "Coeff.": COEFFICIENTS[champ],
            "T (note tranchée/réelle)": d.get("T", "—"),
            "H (harmonisé)": round(d["H"], 1) if d.get("H") else "—",
            "Points": f"{round(d.get('points', 0), 1):,.1f}".replace(",", " "),
        })
    st.dataframe(pd.DataFrame(rows_detail), use_container_width=True, hide_index=True)

    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Bilan périodique", f"{fmt_points(bilan)} pts", help="Max théorique : 4 800 pts")
    col_b.metric("Socle commun",     f"{fmt_points(s_socle_r)} pts",  help="Max : 4 800 pts")
    col_c.metric("Score scolaire",   f"{fmt_points(score_scolaire)} pts")
    col_d.metric("Score max possible", f"{fmt_points(score_total_max)} pts")

    with st.expander("Comment interpréter le score final ?"):
        st.markdown(
            "- Le score final est un score de **classement relatif** pour un vœu, pas une certitude d'admission.\n"
            "- Il est recalculé **pour chaque vœu** (notamment selon le bonus géographique).\n"
            "- Formule : **Score final = score scolaire (notes + socle) + bonus (géo, IPS, boursier)**.\n"
            "- Le bonus géographique pèse fortement : un lycée de secteur 1 donne souvent un avantage décisif.\n"
            "- Le score sert à comparer des stratégies de vœux, mais ne remplace pas les seuils d'admission officiels."
        )

    if not voeux_calc:
        st.info("Ajoutez des vœux dans l'onglet **Mes vœux** pour voir votre score par lycée.")
    else:
        st.markdown("---")
        st.markdown("**Score par vœu**")
        st.caption("Le score scolaire inclut: Bilan périodique + Socle commun.")

        rows_voeux = []
        for v in voeux_calc:
            sc = score_total(
                secteur=v["secteur"],
                ips=ips_val,
                categorie_ips_val=cat_ips,
                boursier=boursier,
                bilan=bilan,
                socle=s_socle_r,
            )
            capa_row = df_capa[df_capa["uai"] == v["uai"]]
            capa = int(capa_row["capacite"].iloc[0]) if not capa_row.empty else "—"

            rows_voeux.append({
                "Lycée":              v["nom"],
                "Commune":            v["commune"],
                "Secteur":            {1: "Secteur 1", 2: "Hors secteur", 3: "Très hors secteur"}[v["secteur"]],
                "Bilan périodique":   fmt_points(bilan),
                "Socle commun":       fmt_points(s_socle_r),
                "Score scolaire":     fmt_points(score_scolaire),
                "Bonus géo":          fmt_points(sc["bonus_geo"]),
                "Bonus IPS":          fmt_points(sc["bonus_ips"]),
                "Bonus boursier":     fmt_points(sc["bonus_boursier"]),
                "Places 2nde GT (réf.)": capa,
                "Score par vœu":      fmt_points(sc["total"]),
            })

        df_voeux = pd.DataFrame(rows_voeux)

        # Tableau compact pour limiter la largeur en affichage principal
        cols_compactes = [
            "Lycée",
            "Secteur",
            "Bonus géo",
            "Score scolaire",
            "Score par vœu",
            "Places 2nde GT (réf.)",
        ]
        st.dataframe(df_voeux[cols_compactes], use_container_width=True, hide_index=True)

        with st.expander("Voir le détail du calcul par vœu"):
            st.dataframe(df_voeux, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("**Radars de progression (obtenu vs potentiel max)**")
    st.caption("Lecture: echelle normalisee a 100% par axe. Le pourtour correspond au potentiel maximal.")

    # Radar NOTES : echelle normalisee 0-100% par axe
    notes_ordre = [CHAMP_LABELS[c] for c in CHAMPS]
    notes_rows = []
    for champ in CHAMPS:
        label = CHAMP_LABELS[champ]
        points_obtenus = float(detail_champs.get(champ, {}).get("points", 0) or 0)
        points_max = COEFFICIENTS[champ] * 160  # repartition de 4 800 pts sur somme coeffs=30
        pct_obtenu = (points_obtenus / points_max * 100) if points_max else 0
        notes_rows.append({"Axe": label, "Serie": "Obtenu", "Points": pct_obtenu})
        notes_rows.append({"Axe": label, "Serie": "Potentiel max", "Points": 100})

    notes_radar = build_radar_chart(
        rows=notes_rows,
        axis_order=notes_ordre,
        max_points=100,
        title="Notes - 7 champs disciplinaires (%)",
    )

    # Radar SOCLE : echelle normalisee 0-100% par competence
    socle_rows = []
    socle_ordre = [f"C{i+1}" for i in range(len(COMPETENCES_SOCLE))]
    for i, comp in enumerate(COMPETENCES_SOCLE):
        axe = f"C{i+1}"
        niveau = niveaux_socle[i]
        points_obtenus = NIVEAUX_SOCLE.get(niveau, 0) * 12
        points_max = 600
        pct_obtenu = (points_obtenus / points_max * 100) if points_max else 0
        socle_rows.append({"Axe": axe, "Competence": comp, "Serie": "Obtenu", "Points": pct_obtenu})
        socle_rows.append({"Axe": axe, "Competence": comp, "Serie": "Potentiel max", "Points": 100})

    socle_radar = build_radar_chart(
        rows=socle_rows,
        axis_order=socle_ordre,
        max_points=100,
        title="Socle commun - 8 competences (%)",
    )

    c_r1, c_r2 = st.columns(2)
    c_r1.altair_chart(notes_radar, use_container_width=True)
    c_r2.altair_chart(socle_radar, use_container_width=True)
    st.markdown("**Correspondance C1-C8 (socle commun)**")
    for i, comp in enumerate(COMPETENCES_SOCLE):
        st.write(f"C{i+1} - {comp}")

    st.caption(
        "**Limites :** score calculé avec les paramètres d'harmonisation de Paris (proxy). "
        "Les seuils d'admission pour Versailles ne sont pas publics — "
        "ce score ne permet pas de conclure sur l'admission. "
        "Les places 2nde GT indiquées sont les effectifs réels de la dernière année disponible (2024)."
    )

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.caption(
    "Réalisé par [William Ramarques](https://www.linkedin.com/in/william-ramarques-1a017525/) &nbsp;·&nbsp; "
    "Sources : "
    "[Barème Affelnet Versailles](https://www.ac-versailles.fr/affelnet-lycee-121477) · "
    "[IPS collèges](https://data.education.gouv.fr/explore/dataset/fr-en-ips_colleges) · "
    "[Paramètres harmonisation Paris](https://affelnet-paris.web.app)"
)
