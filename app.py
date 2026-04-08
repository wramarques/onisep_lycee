import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

DATA_SPES = "data/source/ideo-enseignements_de_specialite_de_premiere_generale.csv"
DATA_OPTS = "data/source/ideo-enseignements_optionnels_de_seconde_generale_et_technologique.csv"
DATA_GEO        = "data/source/ideo-structures-secondaires.csv"
DATA_EFFECTIFS  = "data/source/fr-en-lycee_gt-effectifs-niveau-sexe-lv.csv"

COL_UAI     = "UAI lieu de cours"
COL_NOM     = "Libellé lieu de cours"
COL_COMMUNE = "Commune lieu de cours"
COL_DEP     = "Département lieu de cours"
COL_ACAD    = "Académie lieu de cours"
COL_LIEN    = "Identifiant et fiche onisep lieu de cours"
COL_SPES    = "Enseignements de spécialité de classe de 1ère générale"
COL_OPTS    = "Enseignements optionnels et langues de classe de 2nde GT"


@st.cache_data
def load_data():
    def read_csv(path):
        df = pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype=str)
        df.columns = df.columns.str.strip().str.replace('"', "")
        return df

    df_spe = read_csv(DATA_SPES)
    df_opt = read_csv(DATA_OPTS)

    # --- Explode multi-value columns ---
    def split_lv(value):
        """Éclate 'LV1 : anglais, allemand' en ['LV1 : anglais', 'LV1 : allemand']."""
        if pd.isna(value) or ' : ' not in value:
            return [value]
        prefix, langs = value.split(' : ', 1)
        if ',' not in langs:
            return [value]
        return [f"{prefix} : {lang.strip()}" for lang in langs.split(',')]

    def explode_col(df, col):
        df = df.copy()
        df[col] = df[col].str.split(" / ")
        df = df.explode(col)
        df[col] = df[col].str.strip()
        df[col] = df[col].apply(split_lv)
        df = df.explode(col)
        df[col] = df[col].str.strip()
        return df

    df_spe_exp = explode_col(df_spe, COL_SPES)
    df_opt_exp = explode_col(df_opt, COL_OPTS)

    # --- Sets d'enseignements par UAI (sans NaN) ---
    spe_by_uai = df_spe_exp.dropna(subset=[COL_SPES]).groupby(COL_UAI)[COL_SPES].apply(set)
    opt_by_uai = df_opt_exp.dropna(subset=[COL_OPTS]).groupby(COL_UAI)[COL_OPTS].apply(set)

    # --- UAIs communs aux deux fichiers ---
    uais_communs = set(spe_by_uai.index) & set(opt_by_uai.index)

    # --- Info établissement ---
    etab_cols = [COL_UAI, COL_NOM, COL_COMMUNE, COL_DEP, COL_ACAD, COL_LIEN,
                 "Adresse lieu de cours", "Code postal lieu de cours"]
    etab_spe = df_spe[etab_cols].drop_duplicates(COL_UAI).set_index(COL_UAI)
    etab_opt = df_opt[etab_cols].drop_duplicates(COL_UAI).set_index(COL_UAI)
    etab = etab_spe.combine_first(etab_opt).reset_index()
    etab = etab[etab[COL_UAI].isin(uais_communs)]

    # --- Listes de valeurs uniques pour les filtres ---
    spes_list = sorted(df_spe_exp[COL_SPES].dropna().unique())
    opts_list = sorted(df_opt_exp[COL_OPTS].dropna().unique())

    # --- Mapping académie → départements ---
    etab_all = df_spe[etab_cols].drop_duplicates(COL_UAI).set_index(COL_UAI)\
        .combine_first(df_opt[etab_cols].drop_duplicates(COL_UAI).set_index(COL_UAI))\
        .reset_index()
    acad_dep = (
        etab_all.groupby(COL_ACAD)[COL_DEP]
        .apply(lambda x: sorted(x.dropna().unique()))
        .to_dict()
    )

    return spe_by_uai, opt_by_uai, etab, spes_list, opts_list, acad_dep, uais_communs


@st.cache_data
def load_geo():
    df = pd.read_csv(DATA_GEO, sep=";", encoding="utf-8-sig", dtype=str)
    df.columns = df.columns.str.strip()
    df["lat"] = pd.to_numeric(df["latitude (Y)"].str.strip(), errors="coerce")
    df["lon"] = pd.to_numeric(df["longitude (X)"].str.strip(), errors="coerce")
    df = df.dropna(subset=["lat", "lon"])
    return df[["code UAI", "lat", "lon", "statut", "telephone"]]


@st.cache_data
def load_effectifs():
    # Toutes les colonnes de données (0=année, 10=UAI, 14=total, 15-179=sections)
    df = pd.read_csv(DATA_EFFECTIFS, sep=";", encoding="utf-8-sig",
                     usecols=range(180), header=0, dtype=str)
    # utf-8-sig gère le BOM automatiquement
    # Renommer les colonnes clés, garder les autres telles quelles
    df = df.rename(columns={
        df.columns[0]: "annee",
        df.columns[10]: "UAI",
        df.columns[14]: "total",
    })
    for c in df.columns:
        if c != "UAI":
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.sort_values(["UAI", "annee"])


# Structure des sections par niveau : section → [total_col, filles, garçons, LV1×4, LV2×5]
SECTIONS = {
    "2nde": {
        "GT":    {"total": "2ndes GT",    "detail": ["2ndes GT filles","2ndes GT garçons","2ndes GT LV1 allemand","2ndes GT LV1 anglais","2ndes GT LV1 espagnol","2ndes GT LV1 autres langues","2ndes GT LV2 allemand","2ndes GT LV2 anglais","2ndes GT LV2 espagnol","2ndes GT LV2 italien","2ndes GT LV2 autres langues"]},
        "STHR":  {"total": "2ndes STHR",  "detail": []},
        "TMD":   {"total": "2ndes TMD",   "detail": []},
        "BT":    {"total": "2ndes BT",    "detail": []},
    },
    "1ère": {
        "G":     {"total": "1ères G",     "detail": ["1ères G filles","1ères G garçons","1ères G LV1 allemand","1ères G LV1 anglais","1ères G LV1 espagnol","1ères G LV1 autres langues","1ères G LV2 allemand","1ères G LV2 anglais","1ères G LV2 espagnol","1ères G LV2 italien","1ères G LV2 autres langues"]},
        "STI2D": {"total": "1ères STI2D", "detail": ["1ères STI2D filles","1ères STI2D garçons","1ères STI2D LV1 allemand","1ères STI2D LV1 anglais","1ères STI2D LV1 espagnol","1ères STI2D LV1 autres langues","1ères STI2D LV2 allemand","1ères STI2D LV2 anglais","1ères STI2D LV2 espagnol","1ères STI2D LV2 italien","1ères STI2D LV2 autres langues"]},
        "STL":   {"total": "1ères STL",   "detail": ["1ères STL filles","1ères STL garçons","1ères STL LV1 allemand","1ères STL LV1 anglais","1ères STL LV1 espagnol","1ères STL LV1 autres langues","1ères STL LV2 allemand","1ères STL LV2 anglais","1ères STL LV2 espagnol","1ères STL LV2 italien","1ères STL LV2 autres langues"]},
        "STMG":  {"total": "1ères STMG",  "detail": ["1ères STMG filles","1ères STMG garçons","1ères STMG LV1 allemand","1ères STMG LV1 anglais","1ères STMG LV1 espagnol","1ères STMG LV1 autres langues","1ères STMG LV2 allemand","1ères STMG LV2 anglais","1ères STMG LV2 espagnol","1ères STMG LV2 italien","1ères STMG LV2 autres langues"]},
        "ST2S":  {"total": "1ères ST2S",  "detail": ["1ères ST2S filles","1ères ST2S garçons","1ères ST2S LV1 allemand","1ères ST2S LV1 anglais","1ères ST2S LV1 espagnol","1ères ST2S LV1 autres langues","1ères ST2S LV2 allemand","1ères ST2S LV2 anglais","1ères ST2S LV2 espagnol","1ères ST2S LV2 italien","1ères ST2S LV2 autres langues"]},
        "STD2A": {"total": "1ères STD2A", "detail": ["1ères STD2A filles","1ères STD2A garçons","1ères STD2A LV1 allemand","1ères STD2A LV1 anglais","1ères STD2A LV1 espagnol","1ères STD2A LV1 autres langues","1ères STD2A LV2 allemand","1ères STD2A LV2 anglais","1ères STD2A LV2 espagnol","1ères STD2A LV2 italien","1ères STD2A LV2 autres langues"]},
        "STHR":  {"total": "1ères STHR",  "detail": []},
        "TMD":   {"total": "1ères TMD",   "detail": []},
        "BT":    {"total": "1ères BT",    "detail": []},
    },
    "Terminale": {
        "G":     {"total": "Terminales G",     "detail": ["Terminales G filles","Terminales G garçons","Terminales G LV1 allemand","Terminales G LV1 anglais","Terminales G LV1 espagnol","Terminales G LV1 autres langues","Terminales G LV2 allemand","Terminales G LV2 anglais","Terminales G LV2 espagnol","Terminales G LV2 italien","Terminales G LV2 autres langues"]},
        "STI2D": {"total": "Terminales STI2D", "detail": ["Terminales STI2D filles","Terminales STI2D garçons","Terminales STI2D LV1 allemand","Terminales STI2D LV1 anglais","Terminales STI2D LV1 espagnol","Terminales STI2D LV1 autres langues","Terminales STI2D LV2 allemand","Terminales STI2D LV2 anglais","Terminales STI2D LV2 espagnol","Terminales STI2D LV2 italien","Terminales STI2D LV2 autres langues"]},
        "STL":   {"total": "Terminales STL",   "detail": ["Terminales STL filles","Terminales STL garçons","Terminales STL LV1 allemand","Terminales STL LV1 anglais","Terminales STL LV1 espagnol","Terminales STL LV1 autres langues","Terminales STL LV2 allemand","Terminales STL LV2 anglais","Terminales STL LV2 espagnol","Terminales STL LV2 italien","Terminales STL LV2 autres langues"]},
        "STMG":  {"total": "Terminales STMG",  "detail": ["Terminales STMG filles","Terminales STMG garçons","Terminales STMG LV1 allemand","Terminales STMG LV1 anglais","Terminales STMG LV1 espagnol","Terminales STMG LV1 autres langues","Terminales STMG LV2 allemand","Terminales STMG LV2 anglais","Terminales STMG LV2 espagnol","Terminales STMG LV2 italien","Terminales STMG LV2 autres langues"]},
        "ST2S":  {"total": "Terminales ST2S",  "detail": ["Terminales ST2S filles","Terminales ST2S garçons","Terminales ST2S LV1 allemand","Terminales ST2S LV1 anglais","Terminales ST2S LV1 espagnol","Terminales ST2S LV1 autres langues","Terminales ST2S LV2 allemand","Terminales ST2S LV2 anglais","Terminales ST2S LV2 espagnol","Terminales ST2S LV2 italien","Terminales ST2S LV2 autres langues"]},
        "STD2A": {"total": "Terminales STD2A", "detail": ["Terminales STD2A filles","Terminales STD2A garçons","Terminales STD2A LV1 allemand","Terminales STD2A LV1 anglais","Terminales STD2A LV1 espagnol","Terminales STD2A LV1 autres langues","Terminales STD2A LV2 allemand","Terminales STD2A LV2 anglais","Terminales STD2A LV2 espagnol","Terminales STD2A LV2 italien","Terminales STD2A LV2 autres langues"]},
        "STHR":  {"total": "Terminales STHR",  "detail": []},
        "TMD":   {"total": "Terminales TMD",   "detail": []},
        "BT":    {"total": "Terminales BT",    "detail": []},
    },
}


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Recherche lycées", layout="wide")



st.title("Recherche d'établissements")
st.caption("Source : ONISEP — Idéo enseignements spécialité 1ère & options 2nde GT")

spe_by_uai, opt_by_uai, etab, spes_list, opts_list, acad_dep, uais_communs = load_data()
df_geo = load_geo()
df_effectifs = load_effectifs()
etab_idx = etab.set_index(COL_UAI)

# ---------------------------------------------------------------------------
# Sidebar — filtres
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("#### 🗺️ Localisation")

    acads = sorted(acad_dep.keys())
    sel_acads = st.multiselect("Académie", acads, placeholder="Toutes")

    if sel_acads:
        deps_disponibles = sorted(
            {dep for a in sel_acads for dep in acad_dep.get(a, [])}
        )
    else:
        deps_disponibles = sorted(
            {dep for deps in acad_dep.values() for dep in deps}
        )
    sel_deps = st.multiselect("Département", deps_disponibles, placeholder="Tous")

    if sel_deps:
        communes_disponibles = sorted(
            etab_idx[etab_idx[COL_DEP].isin(sel_deps)][COL_COMMUNE].dropna().unique()
        )
    elif sel_acads:
        communes_disponibles = sorted(
            etab_idx[etab_idx[COL_ACAD].isin(sel_acads)][COL_COMMUNE].dropna().unique()
        )
    else:
        communes_disponibles = sorted(etab_idx[COL_COMMUNE].dropna().unique())
    sel_communes = st.multiselect("Commune", communes_disponibles, placeholder="Toutes")

    st.markdown("#### 🏫 Établissement")
    search_nom = st.text_input("Nom", placeholder="ex : Lycée Victor Hugo", label_visibility="collapsed")

    # --- UAIs après filtres géo + nom ---
    uais_base = uais_communs.copy()
    if sel_acads:
        uais_base &= set(etab_idx[etab_idx[COL_ACAD].isin(sel_acads)].index)
    if sel_deps:
        uais_base &= set(etab_idx[etab_idx[COL_DEP].isin(sel_deps)].index)
    if sel_communes:
        uais_base &= set(etab_idx[etab_idx[COL_COMMUNE].isin(sel_communes)].index)
    if search_nom:
        uais_base &= set(etab_idx[etab_idx[COL_NOM].str.contains(search_nom, case=False, na=False)].index)

    st.markdown("#### 🎓 Enseignements")

    prev_opts = st.session_state.get("sel_opts", [])
    prev_spes = st.session_state.get("sel_spes", [])

    if prev_spes:
        uais_with_spes = {u for u in uais_base if set(prev_spes) <= spe_by_uai.get(u, set())}
        opts_available = sorted({o for u in uais_with_spes for o in opt_by_uai.get(u, set())})
    else:
        opts_available = sorted({o for u in uais_base for o in opt_by_uai.get(u, set())})

    if prev_opts:
        uais_with_opts = {u for u in uais_base if set(prev_opts) <= opt_by_uai.get(u, set())}
        spes_available = sorted({s for u in uais_with_opts for s in spe_by_uai.get(u, set())})
    else:
        spes_available = sorted({s for u in uais_base for s in spe_by_uai.get(u, set())})

    sel_opts = st.multiselect("📚 Options de 2nde", opts_available, key="sel_opts")
    sel_spes = st.multiselect("🔬 Spécialités de 1ère", spes_available, key="sel_spes")

# ---------------------------------------------------------------------------
# Filtrage final
# ---------------------------------------------------------------------------
uais = uais_base.copy()

if sel_spes:
    uais = {u for u in uais if set(sel_spes) <= spe_by_uai.get(u, set())}

if sel_opts:
    uais = {u for u in uais if set(sel_opts) <= opt_by_uai.get(u, set())}

# ---------------------------------------------------------------------------
# Résultats
# ---------------------------------------------------------------------------

st.subheader(f"{len(uais)} établissement(s) trouvé(s)")

if uais:
    result = (
        etab[etab[COL_UAI].isin(uais)]
        .sort_values([COL_DEP, COL_NOM])
        .reset_index(drop=True)
    )

    tab_liste, tab_carte = st.tabs(["Liste", "Carte"])

    with tab_liste:
        display = result[[COL_UAI, COL_NOM, COL_COMMUNE, COL_DEP, COL_ACAD]].copy()
        display = display.merge(df_geo[["code UAI", "statut"]], left_on=COL_UAI, right_on="code UAI", how="left").drop(columns=[COL_UAI, "code UAI"])
        display.columns = ["Établissement", "Commune", "Département", "Académie", "Statut"]

        col_list, col_detail = st.columns([2, 3])

        with col_list:
            st.caption("Cliquez sur une ligne pour voir le détail.")
            selection = st.dataframe(
                display,
                use_container_width=True,
                on_select="rerun",
                selection_mode="single-row",
                height=600,
            )

        with col_detail:
            selected_rows = selection.selection.rows
            if selected_rows:
                row = result.iloc[selected_rows[0]]
                uai = row[COL_UAI]
                geo_row = df_geo[df_geo["code UAI"] == uai]

                with st.container(border=True):
                    st.subheader(row[COL_NOM])
                    meta = []
                    if not geo_row.empty:
                        g = geo_row.iloc[0]
                        if pd.notna(g["statut"]):
                            meta.append(f"**Statut :** {g['statut']}")
                        if pd.notna(g["telephone"]) and g["telephone"]:
                            meta.append(f"**Tél :** {g['telephone']}")
                    adresse = ", ".join(filter(pd.notna, [
                        row.get("Adresse lieu de cours"),
                        row.get("Code postal lieu de cours"),
                        row[COL_COMMUNE],
                    ]))
                    st.write(f"{adresse} — {row[COL_DEP]} — Académie de {row[COL_ACAD]}")
                    if meta:
                        st.markdown(" &nbsp;|&nbsp; ".join(meta))
                    if pd.notna(row[COL_LIEN]):
                        st.markdown(f"[Voir la fiche ONISEP]({row[COL_LIEN]})")

                    eff_etab = df_effectifs[df_effectifs["UAI"] == uai].sort_values("annee")
                    if not eff_etab.empty:
                        st.write("")
                        st.markdown("**Effectifs**")
                        derniere = eff_etab.iloc[-1]
                        annee = int(derniere["annee"])
                        c1, c2, c3, c4 = st.columns(4)
                        def mv(val):
                            return int(val) if pd.notna(val) else "—"
                        c1.metric("Total", mv(derniere["total"]), help=f"Rentrée {annee}")
                        c2.metric("2nde GT", mv(derniere[SECTIONS["2nde"]["GT"]["total"]]))
                        c3.metric("1ère G",  mv(derniere[SECTIONS["1ère"]["G"]["total"]]))
                        c4.metric("Term. G", mv(derniere[SECTIONS["Terminale"]["G"]["total"]]))

                        if len(eff_etab) > 1:
                            with st.expander("Évolution des effectifs"):
                                tabs_eff = st.tabs(list(SECTIONS.keys()))
                                for tab_eff, (niveau, sections) in zip(tabs_eff, SECTIONS.items()):
                                    with tab_eff:
                                        actives = {
                                            sec: info for sec, info in sections.items()
                                            if info["total"] in eff_etab.columns
                                            and eff_etab[info["total"]].fillna(0).gt(0).any()
                                        }
                                        if not actives:
                                            st.caption("Aucun effectif.")
                                            continue
                                        totaux = eff_etab.set_index("annee")[
                                            [info["total"] for info in actives.values()]
                                        ].copy()
                                        totaux.index = totaux.index.astype(int).astype(str)
                                        totaux.columns = list(actives.keys())
                                        st.line_chart(totaux)
                                        for sec, info in actives.items():
                                            detail_cols = [c for c in info["detail"]
                                                           if c in eff_etab.columns
                                                           and eff_etab[c].fillna(0).gt(0).any()]
                                            if detail_cols:
                                                with st.expander(f"Détail {sec}"):
                                                    detail = eff_etab.set_index("annee")[detail_cols].copy()
                                                    detail.index = detail.index.astype(int).astype(str)
                                                    detail.columns = [
                                                        c.replace(f"{niveau}s {sec} ", "").replace(f"1ères {sec} ", "").replace(f"Terminales {sec} ", "")
                                                        for c in detail_cols
                                                    ]
                                                    st.line_chart(detail)

                    st.write("")
                    col_opt, col_spe = st.columns(2)
                    with col_opt:
                        st.markdown("**Options de 2nde**")
                        for o in sorted(opt_by_uai.get(uai, set())):
                            if o in sel_opts:
                                st.markdown(f"- **:blue[{o}]**")
                            else:
                                st.write(f"- {o}")
                    with col_spe:
                        st.markdown("**Spécialités de 1ère**")
                        for s in sorted(spe_by_uai.get(uai, set())):
                            if s in sel_spes:
                                st.markdown(f"- **:blue[{s}]**")
                            else:
                                st.write(f"- {s}")
            else:
                st.info("Sélectionnez un établissement dans la liste pour voir son détail.")

    with tab_carte:
        geo_result = result.merge(df_geo, left_on=COL_UAI, right_on="code UAI", how="inner").drop_duplicates(COL_UAI)
        n_sans_coords = len(result) - len(geo_result)
        if n_sans_coords > 0:
            st.caption(f"{n_sans_coords} établissement(s) sans coordonnées géographiques ne figurent pas sur la carte.")
        if geo_result.empty:
            st.warning("Aucune coordonnée disponible pour ces établissements.")
        else:
            m = folium.Map(location=[46.5, 2.5], zoom_start=6, tiles="OpenStreetMap")
            cluster = MarkerCluster().add_to(m)
            for _, r in geo_result.iterrows():
                folium.Marker(
                    location=[r["lat"], r["lon"]],
                    tooltip=f"{r[COL_NOM]} — {r[COL_COMMUNE]} ({r[COL_DEP]})",
                    icon=folium.Icon(color="red", icon="graduation-cap", prefix="fa"),
                ).add_to(cluster)
            st_folium(m, use_container_width=True, height=500)

else:
    if sel_spes or sel_opts or sel_acads or sel_deps:
        st.info("Aucun établissement ne correspond à cette combinaison.")
    else:
        st.info("Utilisez les filtres dans la barre latérale pour lancer une recherche.")
