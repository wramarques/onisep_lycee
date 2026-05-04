"""
Test de lookup sectorisation + enrichissement fiche établissement
Cas test : Boulogne-Billancourt, Avenue du Général Leclerc
Usage : env/Scripts/python.exe scripts/test_lookup_sectorisation.py
"""

import sys
import re
import unicodedata
import pdfplumber
import pandas as pd
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PDF_PATH    = Path("data/source/affelnet/sectorisation/lycee-de-secteur-92-hauts-de-seine.pdf")
GEO_PATH    = Path("data/source/ideo-structures-secondaires.csv")
SPES_PATH   = Path("data/source/ideo-enseignements_de_specialite_de_premiere_generale.csv")
OPTS_PATH   = Path("data/source/ideo-enseignements_optionnels_de_seconde_generale_et_technologique.csv")

LINE_RE  = re.compile(r"^(?P<ville>[^:]+?)\s*:\s*(?P<voie>.+?)\s+(?P<code_zone>\S+)\s+(?P<lycees>\[.+)$")
LYCEE_RE = re.compile(r"\[(?P<tag>.)\]\s*(?P<nom>[^,(]+?)\s*\((?P<commune>[^)]+)\)")


def normalize(s):
    """Minuscules, sans accents, sans ponctuation superflue."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).strip()


def parse_pdf():
    rows = []
    with pdfplumber.open(PDF_PATH) as pdf:
        for page in pdf.pages:
            for line in (page.extract_text() or "").splitlines():
                m = LINE_RE.match(line.strip())
                if not m:
                    continue

                for lm in LYCEE_RE.finditer(m.group("lycees")):
                    principal_tag = lm.group("tag").strip().upper()
                    rows.append({
                        "ville":         m.group("ville").strip(),
                        "voie":          m.group("voie").strip(),
                        "code_zone":     m.group("code_zone").strip(),
                        "lycee_nom":     lm.group("nom").strip(),
                        "lycee_commune": lm.group("commune").strip(),
                        "principal":     principal_tag in {"X", "×"},
                    })
    df = pd.DataFrame(rows)
    df["ville_n"]  = df["ville"].apply(normalize)
    df["voie_n"]   = df["voie"].apply(normalize)
    return df


def lookup(df_secteur, ville_query, voie_query):
    v = normalize(ville_query)
    r = normalize(voie_query)
    # Ville exacte, voie contient les mots-clés de la requête
    mots = r.split()
    mask_ville = df_secteur["ville_n"].str.contains(v, regex=False)
    mask_voie  = df_secteur["voie_n"].apply(lambda x: all(m in x for m in mots))
    return df_secteur[mask_ville & mask_voie]


def load_geo():
    df = pd.read_csv(GEO_PATH, sep=";", encoding="utf-8-sig", dtype=str)
    df.columns = df.columns.str.strip()
    df["nom_n"] = df["nom"].apply(normalize)
    return df


def load_enseignements():
    def read(path, col):
        df = pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype=str)
        df.columns = df.columns.str.strip().str.replace('"', "")
        uai_col = "UAI lieu de cours"
        df[col] = df[col].str.split(" / ")
        df = df.explode(col)
        df[col] = df[col].str.strip()
        return df.dropna(subset=[col]).groupby(uai_col)[col].apply(set)

    spes = read(SPES_PATH, "Enseignements de spécialité de classe de 1ère générale")
    opts = read(OPTS_PATH, "Enseignements optionnels et langues de classe de 2nde GT")
    return spes, opts


def main():
    ville_q = "Boulogne-Billancourt"
    voie_q  = "avenue du général leclerc"

    print(f"=== Lookup sectorisation ===")
    print(f"Ville : {ville_q}")
    print(f"Voie  : {voie_q}\n")

    print("Parsing PDF...")
    df_sec = parse_pdf()
    print(f"  {len(df_sec)} lignes chargées\n")

    hits = lookup(df_sec, ville_q, voie_q)

    if hits.empty:
        print("Aucune voie trouvée pour cette recherche.")
        return

    # Zone unique pour cette adresse
    zones = hits["code_zone"].unique()
    print(f"Zone(s) trouvée(s) : {zones}\n")

    # Lycées de la zone (dédupliqués)
    lycees_zone = hits[["lycee_nom", "lycee_commune", "principal"]].drop_duplicates()
    print(f"--- {len(lycees_zone)} lycée(s) de secteur ---\n")

    # Chargement données de référence
    print("Chargement données établissements...")
    df_geo  = load_geo()
    spes, opts = load_enseignements()

    for _, row in lycees_zone.sort_values("principal", ascending=False).iterrows():
        tag = "(principal)" if row["principal"] else ""
        print(f"{'='*60}")
        print(f"  {row['lycee_nom']} — {row['lycee_commune']} {tag}")
        print(f"{'='*60}")

        # Jointure sur nom normalisé
        nom_n = normalize(row["lycee_nom"])
        match = df_geo[df_geo["nom_n"].str.contains(nom_n, regex=False)]

        if match.empty:
            # Tentative mot par mot (noms courts comme "JOLIOT-CURIE")
            mots = [m for m in nom_n.split() if len(m) > 3]
            match = df_geo[df_geo["nom_n"].apply(lambda x: all(m in x for m in mots))]

        if match.empty:
            print("  Fiche ONISEP : non trouvée (correspondance manuelle nécessaire)")
            print()
            continue

        # Prendre le lycée le plus proche (filtre sur commune si plusieurs)
        if len(match) > 1:
            commune_n = normalize(row["lycee_commune"])
            sub = match[match["commune"].apply(normalize).str.contains(commune_n, regex=False)]
            if not sub.empty:
                match = sub

        etab = match.iloc[0]
        uai  = etab["code UAI"]

        print(f"  UAI      : {uai}")
        print(f"  Statut   : {etab.get('statut', '—')}")
        print(f"  Adresse  : {etab.get('adresse', '')} {etab.get('CP', '')} {etab.get('commune', '')}")
        print(f"  Tél      : {etab.get('telephone', '—')}")
        print(f"  Académie : {etab.get('académie', etab.get('academie', '—'))}")

        # Enseignements
        s = spes.get(uai, set())
        o = opts.get(uai, set())
        if s:
            print(f"  Spécialités 1ère ({len(s)}) : {', '.join(sorted(s)[:5])}{'...' if len(s)>5 else ''}")
        if o:
            print(f"  Options 2nde  ({len(o)}) : {', '.join(sorted(o)[:5])}{'...' if len(o)>5 else ''}")
        print()


if __name__ == "__main__":
    main()
