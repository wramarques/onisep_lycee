"""
Précalcul offline des données Affelnet
Génère 3 fichiers parquet/json exploitables directement par l'application.

Usage : env/Scripts/python.exe scripts/build_affelnet_data.py

Étapes :
  1. harmonisation-proxy.json     — µ/σ Paris 2022-2025 consolidés et normalisés
  2. ips-colleges-versailles.parquet — IPS collèges Versailles, dernière année, colonnes utiles
  3. capacite-2nde-gt.parquet     — Effectif 2nde GT dernière année par UAI (proxy capacité)
"""

import sys
import json
import pandas as pd
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT    = Path(__file__).parent.parent
AFFELNET = ROOT / "data/source/affelnet"

# Inputs
HARM_HIST    = AFFELNET / "harmonisation/statistiques.json"
HARM_RECENT  = AFFELNET / "harmonisation/stats_recentes.json"
IPS_PATH     = ROOT / "data/source/fr-en-ips_colleges.parquet"
EFF_PATH     = ROOT / "data/source/fr-en-lycee_gt-effectifs-niveau-sexe-lv.csv"

# Outputs
OUT_HARM  = AFFELNET / "harmonisation/harmonisation-proxy.json"
OUT_IPS   = AFFELNET / "ips-colleges-versailles.parquet"
OUT_CAPA  = AFFELNET / "capacite-2nde-gt.parquet"

# Normalisation des noms de champs disciplinaires
CHAMP_NORM = {
    "SCIENCES-TECHNO-DP": "SCIENCES-TECHNO",
    "SCIENCES-TECHNO":    "SCIENCES-TECHNO",
}


# ---------------------------------------------------------------------------
# 1. Harmonisation µ/σ — consolidation et normalisation
# ---------------------------------------------------------------------------
def build_harmonisation():
    print("--- 1. Harmonisation µ/σ ---")

    with open(HARM_HIST,   encoding="utf-8") as f:
        hist = json.load(f)
    with open(HARM_RECENT, encoding="utf-8") as f:
        recent = json.load(f)

    all_entries = hist + recent
    normalized = []
    for e in all_entries:
        champ = CHAMP_NORM.get(e["champ"], e["champ"])
        normalized.append({
            "annee":      int(e["annee"]),
            "champ":      champ,
            "moyenne":    e["moyenne"],
            "ecart_type": e["ecart-type"],
        })

    # Déduplication (au cas où)
    df = pd.DataFrame(normalized).drop_duplicates(subset=["annee", "champ"])
    df = df.sort_values(["annee", "champ"]).reset_index(drop=True)

    annees = sorted(df["annee"].unique())
    champs = sorted(df["champ"].unique())
    print(f"  Années : {annees}")
    print(f"  Champs : {champs}")
    print(f"  Entrées : {len(df)}")

    with open(OUT_HARM, "w", encoding="utf-8") as f:
        json.dump(df.to_dict(orient="records"), f, ensure_ascii=False, indent=2)
    print(f"  -> {OUT_HARM.name}\n")


# ---------------------------------------------------------------------------
# 2. IPS collèges Versailles — filtrage et catégorisation
# ---------------------------------------------------------------------------
def build_ips_versailles():
    print("--- 2. IPS collèges Versailles ---")

    df = pd.read_parquet(IPS_PATH)

    # Dernière année disponible
    derniere_annee = df["rentree_scolaire"].dropna().max()
    print(f"  Dernière année : {derniere_annee}")

    df_v = df[
        (df["rentree_scolaire"] == derniere_annee) &
        (df["academie"].str.upper().str.contains("VERSAILLES", na=False))
    ].copy()

    # Catégorie IPS pour bonus Affelnet
    def categorie_ips(ips):
        if pd.isna(ips):
            return None
        if ips >= 114:
            return "favorisé"
        if ips >= 89:
            return "intermédiaire"
        return "défavorisé"

    def bonus_ips(ips):
        if pd.isna(ips):
            return None
        if ips >= 114:
            return 0
        if ips >= 89:
            return 600
        return 1200

    df_v["categorie"] = df_v["ips"].apply(categorie_ips)
    df_v["bonus_ips"] = df_v["ips"].apply(bonus_ips)

    df_out = df_v[[
        "uai", "nom_de_l_etablissment", "nom_de_la_commune",
        "departement", "secteur", "ips", "categorie", "bonus_ips"
    ]].rename(columns={
        "nom_de_l_etablissment": "nom",
        "nom_de_la_commune":     "commune",
    }).reset_index(drop=True)

    print(f"  Collèges Versailles : {len(df_out)}")
    print(f"  Distribution : {df_out['categorie'].value_counts().to_dict()}")

    df_out.to_parquet(OUT_IPS, index=False)
    print(f"  -> {OUT_IPS.name}\n")


# ---------------------------------------------------------------------------
# 3. Capacité 2nde GT — dernière année par UAI
# ---------------------------------------------------------------------------
def build_capacite_2nde():
    print("--- 3. Capacité 2nde GT ---")

    df = pd.read_csv(
        EFF_PATH, sep=";", encoding="utf-8-sig", dtype=str,
        usecols=["Rentrée scolaire", "UAI", "2ndes GT"]
    )
    df["annee"]    = pd.to_numeric(df["Rentrée scolaire"], errors="coerce")
    df["capacite"] = pd.to_numeric(df["2ndes GT"], errors="coerce")
    df = df.dropna(subset=["annee", "UAI", "capacite"])

    # Dernière année disponible par UAI
    df_last = (
        df.sort_values("annee")
        .groupby("UAI")
        .last()
        .reset_index()
        [["UAI", "annee", "capacite"]]
        .rename(columns={"UAI": "uai", "annee": "annee_ref"})
    )
    df_last["annee_ref"] = df_last["annee_ref"].astype(int)
    df_last["capacite"]  = df_last["capacite"].astype(int)

    annee_max = df_last["annee_ref"].max()
    print(f"  Lycées avec données 2nde GT : {len(df_last)}")
    print(f"  Année max disponible        : {annee_max}")
    print(f"  Capacité médiane            : {df_last['capacite'].median():.0f} élèves")

    df_last.to_parquet(OUT_CAPA, index=False)
    print(f"  -> {OUT_CAPA.name}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=== Build données Affelnet ===\n")
    AFFELNET.mkdir(parents=True, exist_ok=True)

    build_harmonisation()
    build_ips_versailles()
    build_capacite_2nde()

    print("=== Terminé ===")
