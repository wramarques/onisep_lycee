"""
Extracteur offline : PDFs sectorisation → sectorisation-versailles.parquet
Parse les 4 PDFs de l'académie de Versailles (78/91/92/95), joint les UAI
depuis ideo-structures-secondaires.csv et exporte un parquet exploitable.

Usage : env/Scripts/python.exe scripts/build_sectorisation.py
"""

import sys
import re
import unicodedata
import pdfplumber
import pandas as pd
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------
ROOT        = Path(__file__).parent.parent
PDF_DIR     = ROOT / "data/source/affelnet/sectorisation"
GEO_PATH    = ROOT / "data/source/ideo-structures-secondaires.csv"
OUTPUT      = ROOT / "data/source/affelnet/sectorisation/sectorisation-versailles.parquet"

PDFS = {
    "78": PDF_DIR / "lycee-de-secteur-78-yvelines.pdf",
    "91": PDF_DIR / "lycee-de-secteur-91-essonne.pdf",
    "92": PDF_DIR / "lycee-de-secteur-92-hauts-de-seine.pdf",
    "95": PDF_DIR / "lycee-de-secteur-95-val-d-oise.pdf",
}

# Correspondances manuelles nom_pdf_normalisé → UAI
# À compléter après vérification des cas non résolus automatiquement
MANUAL_UAI = {
    # "nom normalise sans accent": "UAI"
    # Exemples à valider lors du premier run :
    # "la folie saint james": "0921234X",
}

# ---------------------------------------------------------------------------
# Regex parsing
# ---------------------------------------------------------------------------
LINE_RE  = re.compile(r"^(?P<ville>[^:]+?)\s*:\s*(?P<voie>.+?)\s+(?P<code_zone>\S+)\s+(?P<lycees>\[.+)$")
LYCEE_RE = re.compile(r"\[(?P<tag>.)\]\s*(?P<nom>[^,(]+?)\s*\((?P<commune>[^)]+)\)")


def normalize(s: str) -> str:
    """Minuscules, sans accents, tirets → espaces, espaces multiples réduits."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[-–]", " ", s)
    s = re.sub(r"[^a-z0-9 ]", "", s.lower())
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------------------
# Parsing PDF
# ---------------------------------------------------------------------------
def parse_pdf(path: Path, dep: str) -> pd.DataFrame:
    rows = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for line in (page.extract_text() or "").splitlines():
                m = LINE_RE.match(line.strip())
                if not m:
                    continue
                lycees_str = m.group("lycees")
                for lm in LYCEE_RE.finditer(lycees_str):
                    principal_tag = lm.group("tag").strip().upper()
                    rows.append({
                        "departement":   dep,
                        "ville":         m.group("ville").strip(),
                        "voie":          m.group("voie").strip(),
                        "code_zone":     m.group("code_zone").strip(),
                        "lycee_nom_pdf": lm.group("nom").strip(),
                        "lycee_commune": lm.group("commune").strip(),
                        "principal":     principal_tag in {"X", "×"},
                    })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Chargement référentiel ONISEP
# ---------------------------------------------------------------------------
def load_geo() -> pd.DataFrame:
    df = pd.read_csv(GEO_PATH, sep=";", encoding="utf-8-sig", dtype=str)
    df.columns = df.columns.str.strip()
    # Filtrer sur lycées GT de l'académie de Versailles uniquement
    df = df[
        df["académie"].str.contains("Versailles", na=False) &
        df["nom"].str.upper().str.contains("LYC", na=False)
    ].copy()
    # Nom court normalisé : retirer "Lycée " / "Lycée général " etc.
    df["nom_court"] = (
        df["nom"]
        .str.upper()
        .str.replace(r"^LYC[ÉE]E\s+(G[ÉE]N[ÉE]RAL\s+)?", "", regex=True)
    )
    df["nom_n"] = df["nom_court"].apply(normalize)
    df["commune_n"] = df["commune"].apply(normalize)
    return df[["code UAI", "nom", "nom_n", "commune", "commune_n", "département",
               "adresse", "CP", "statut", "telephone"]].rename(columns={"code UAI": "uai"})


# ---------------------------------------------------------------------------
# Jointure nom PDF → UAI
# ---------------------------------------------------------------------------
def join_uai(df_raw: pd.DataFrame, df_geo: pd.DataFrame) -> pd.DataFrame:
    """Résout les UAI par matching normalisé avec fallback par mots-clés."""

    # Index de recherche : nom_n → liste de lignes geo
    geo_by_nom  = df_geo.groupby("nom_n")
    geo_by_comm = df_geo.groupby("commune_n")

    def resolve(lycee_nom_pdf: str, commune_pdf: str) -> tuple[str | None, str | None]:
        nom_n     = normalize(lycee_nom_pdf)
        commune_n = normalize(commune_pdf)

        # 1. Correspondance manuelle
        if nom_n in MANUAL_UAI:
            return MANUAL_UAI[nom_n], "manuel"

        # 2. Match exact normalisé
        if nom_n in geo_by_nom.groups:
            candidates = df_geo.loc[geo_by_nom.groups[nom_n]]
            # Affiner par commune si ambiguïté
            sub = candidates[candidates["commune_n"].str.contains(commune_n, regex=False)]
            row = sub.iloc[0] if not sub.empty else candidates.iloc[0]
            return row["uai"], "exact"

        # 3. Match par mots significatifs (>3 chars)
        mots = [m for m in nom_n.split() if len(m) > 3]
        if mots:
            mask = df_geo["nom_n"].apply(lambda x: all(m in x for m in mots))
            candidates = df_geo[mask]
            if not candidates.empty:
                sub = candidates[candidates["commune_n"].str.contains(commune_n, regex=False)]
                row = sub.iloc[0] if not sub.empty else candidates.iloc[0]
                return row["uai"], "partiel"

        return None, "non_resolu"

    uais, methods = zip(*df_raw.apply(
        lambda r: resolve(r["lycee_nom_pdf"], r["lycee_commune"]), axis=1
    ))
    df_raw = df_raw.copy()
    df_raw["uai"]    = uais
    df_raw["_match"] = methods
    return df_raw


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=== Build sectorisation-versailles.parquet ===\n")

    df_geo = load_geo()
    print(f"Référentiel ONISEP chargé : {len(df_geo)} lycées GT Versailles\n")

    all_frames = []
    for dep, path in PDFS.items():
        print(f"Parsing {path.name}...")
        df = parse_pdf(path, dep)
        print(f"  {len(df)} lignes brutes")
        df = join_uai(df, df_geo)
        stats = df["_match"].value_counts().to_dict()
        print(f"  Matching : {stats}")
        all_frames.append(df)

    df_all = pd.concat(all_frames, ignore_index=True)

    # --- Rapport non résolus ---
    non_resolus = df_all[df_all["_match"] == "non_resolu"][
        ["departement", "lycee_nom_pdf", "lycee_commune"]
    ].drop_duplicates().sort_values(["departement", "lycee_nom_pdf"])

    if not non_resolus.empty:
        print(f"\n--- {len(non_resolus)} lycée(s) sans UAI (à ajouter dans MANUAL_UAI) ---")
        for _, r in non_resolus.iterrows():
            print(f"  [{r['departement']}] '{r['lycee_nom_pdf']}' ({r['lycee_commune']})")
        print()

    # --- Déduplication au niveau voie ---
    df_out = (
        df_all[df_all["uai"].notna()]
        [[
            "departement", "ville", "voie", "code_zone",
            "uai", "lycee_nom_pdf", "lycee_commune", "principal"
        ]]
        .drop_duplicates(subset=["ville", "voie", "code_zone", "uai"])
        .sort_values(["departement", "ville", "voie", "code_zone"])
        .reset_index(drop=True)
        .rename(columns={"lycee_nom_pdf": "lycee_nom"})
    )

    # --- Stats finales ---
    print(f"Résultat final :")
    print(f"  Communes couvertes : {df_out['ville'].nunique()}")
    print(f"  Zones uniques      : {df_out['code_zone'].nunique()}")
    print(f"  Lycées (UAI)       : {df_out['uai'].nunique()}")
    print(f"  Lignes total       : {len(df_out)}")
    print()
    print(df_out.head(10).to_string(index=False))

    # --- Export ---
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_parquet(OUTPUT, index=False)
    print(f"\nExporté : {OUTPUT}")


if __name__ == "__main__":
    main()
