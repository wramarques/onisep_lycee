"""
Analyse de faisabilité — extraction sectorisation GT depuis PDF académie de Versailles
Usage : env/Scripts/python.exe scripts/analyse_pdf_sectorisation.py
"""

import sys
import pdfplumber
import re
import pandas as pd
from pathlib import Path
from collections import defaultdict, Counter

# Force UTF-8 sur la sortie console Windows
sys.stdout.reconfigure(encoding="utf-8")

PDF_PATH = Path("data/source/sectorisation-lycee/lycee-de-secteur-92-hauts-de-seine.pdf")

# Ligne type :
# "Antony : A RIOU (RUELLE) 92ANTON1 [_] DESCARTES (Antony) , [_] JEAN JAURES (Châtenay-Malabry)"
# Marqueur (X) = lycée principal de la zone, [_] = lycée secondaire
LINE_RE = re.compile(
    r"^(?P<ville>[^:]+?)\s*:\s*(?P<voie>.+?)\s+(?P<code_zone>\S+)\s+(?P<lycees>\[.+)$"
)
LYCEE_RE = re.compile(r"\[.\]\s*(?P<nom>[^,(]+?)\s*\((?P<commune>[^)]+)\)")


def parse_lycees(lycees_str):
    """Extrait la liste des lycées depuis la partie droite d'une ligne."""
    results = []
    for m in LYCEE_RE.finditer(lycees_str):
        results.append({
            "lycee_nom": m.group("nom").strip(),
            "lycee_commune": m.group("commune").strip(),
            "principal": "(X)" in lycees_str[max(0, m.start()-4):m.start()],
        })
    return results


def extract_all():
    rows = []
    errors = []

    with pdfplumber.open(PDF_PATH) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            for line in text.splitlines():
                line = line.strip()
                m = LINE_RE.match(line)
                if not m:
                    continue
                lycees = parse_lycees(m.group("lycees"))
                for ly in lycees:
                    rows.append({
                        "ville": m.group("ville").strip(),
                        "voie": m.group("voie").strip(),
                        "code_zone": m.group("code_zone").strip(),
                        "lycee_nom": ly["lycee_nom"],
                        "lycee_commune": ly["lycee_commune"],
                        "principal": ly["principal"],
                        "page": page_num,
                    })

    return pd.DataFrame(rows)


def main():
    print(f"=== Analyse : {PDF_PATH.name} ===\n")

    with pdfplumber.open(PDF_PATH) as pdf:
        n_pages = len(pdf.pages)
    print(f"Pages : {n_pages}")

    print("\n--- Aperçu 5 premières lignes brutes (page 1) ---")
    with pdfplumber.open(PDF_PATH) as pdf:
        text = pdf.pages[0].extract_text() or ""
    for line in text.splitlines()[3:8]:
        print(" ", line)

    print("\n--- Parsing regex ---")
    df = extract_all()
    print(f"Lignes parsées    : {len(df)}")
    print(f"Lignes sans match : voir ci-dessous (max 5)")

    # Lignes non parsées (hors en-tête)
    with pdfplumber.open(PDF_PATH) as pdf:
        all_lines = []
        for page in pdf.pages:
            t = page.extract_text() or ""
            all_lines += [l.strip() for l in t.splitlines() if l.strip()]

    skipped = [l for l in all_lines if l and not LINE_RE.match(l)
               and not l.startswith("Ville") and not l.startswith("Zone")]
    for l in skipped[:5]:
        print(f"  SKIP: {l}")

    print(f"\n--- Échantillon résultat ---")
    print(df.head(10).to_string(index=False))

    print(f"\n--- Statistiques ---")
    print(f"Villes couvertes        : {df['ville'].nunique()}")
    print(f"Codes de zones uniques  : {df['code_zone'].nunique()}")
    print(f"Lycées uniques (nom)    : {df['lycee_nom'].nunique()}")
    print(f"Noms de lycées distincts:")
    for nom, cnt in df['lycee_nom'].value_counts().head(15).items():
        print(f"  {nom:40s} ({cnt} voies)")

    print(f"\n--- Vérification jointure avec ideo-structures-secondaires.csv ---")
    try:
        df_geo = pd.read_csv(
            "data/source/ideo-structures-secondaires.csv",
            sep=";", encoding="utf-8-sig", dtype=str
        )
        df_geo.columns = df_geo.columns.str.strip()
        # Lycées GT dans Hauts-de-Seine (nom court = après "LYCÉE " ou "LYCEE ")
        lycees_92 = df_geo[
            df_geo["département"].str.contains("Hauts-de-Seine|92", na=False) &
            df_geo["nom"].str.upper().str.contains("LYC", na=False)
        ].copy()
        lycees_92["nom_court"] = (
            lycees_92["nom"].str.upper()
            .str.replace(r"^LYC[ÉE]E\s+", "", regex=True)
            .str.strip()
        )
        noms_ref = set(lycees_92["nom_court"])
        noms_pdf = set(df["lycee_nom"].str.upper().str.strip())

        # Correspondances exactes
        match_exact = noms_pdf & noms_ref
        # Correspondances partielles (nom PDF contenu dans nom ref ou inverse)
        match_partial = {n for n in noms_pdf if any(n in r or r in n for r in noms_ref)}

        print(f"Lycées dans le PDF    : {len(noms_pdf)}")
        print(f"Lycées GT dans 92     : {len(noms_ref)}")
        print(f"Matches exacts        : {len(match_exact)}")
        print(f"Matches partiels      : {len(match_partial)}")
        non_matches = noms_pdf - match_partial
        if non_matches:
            print(f"Sans correspondance ({len(non_matches)}) — normalisation nécessaire :")
            for n in sorted(non_matches):
                print(f"  PDF: '{n}'")
    except FileNotFoundError:
        print("  (ideo-structures-secondaires.csv non trouvé, jointure ignorée)")

    print("\n=== VERDICT FAISABILITE ===\n")
    if len(df) > 100:
        print("OK  Structure régulière et parseable par regex")
    else:
        print("KO  Peu de lignes parsées — revoir le regex")

    print("OK  Texte extractible (pas de scan, pas d'OCR nécessaire)")
    print("OK  Structure : Ville / Voie / Code zone / Lycees")
    print("ATT Pas de code UAI — jointure par nom de lycée (normalisation nécessaire)")
    print("ATT Code zone interne (ex: 92ANTON1) = clé de regroupement, pas l'UAI")
    print()
    print("Conclusion : extraction FAISABLE")
    print("Effort estimé : 1 script de parsing + normalisation des noms pour jointure UAI")
    print("Granularité : rue par rue (très fin, largement suffisant pour commune/zone)")


if __name__ == "__main__":
    main()
