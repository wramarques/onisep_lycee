"""
Calcul du score Affelnet — fonctions pures.
Référence : barème académie de Versailles, voie GT 2nde.
"""

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

CHAMPS = [
    "MATHEMATIQUES",
    "FRANCAIS",
    "HISTOIRE-GEO",
    "LANGUES VIVANTES",
    "SCIENCES-TECHNO",
    "ARTS",
    "EPS",
]

COEFFICIENTS = {
    "MATHEMATIQUES":    5,
    "FRANCAIS":         5,
    "HISTOIRE-GEO":     4,
    "LANGUES VIVANTES": 4,
    "SCIENCES-TECHNO":  4,
    "ARTS":             4,
    "EPS":              4,
}

# Bonus géographique par niveau de secteur
BONUS_GEO = {1: 32640, 2: 17760, 3: 16800}

# Bonus IPS par catégorie
BONUS_IPS_CAT = {"favorisé": 0, "intermédiaire": 600, "défavorisé": 1200}

# Seuils IPS → catégorie
IPS_SEUILS = [(114, "favorisé"), (89, "intermédiaire"), (0, "défavorisé")]

# Niveaux socle commun
NIVEAUX_SOCLE = {
    "Maîtrise insuffisante":  10,
    "Maîtrise fragile":       25,
    "Maîtrise satisfaisante": 40,
    "Très bonne maîtrise":    50,
}

COMPETENCES_SOCLE = [
    "Langages des arts et du corps",
    "Langues étrangères et régionales",
    "Langue française",
    "Langages mathématiques, scientifiques et informatiques",
    "Formation de la personne et du citoyen",
    "Méthodes et outils pour apprendre",
    "Représentations du monde et activité humaine",
    "Systèmes naturels et systèmes techniques",
]


# ---------------------------------------------------------------------------
# Score scolaire — bilan périodique
# ---------------------------------------------------------------------------

def trancher(note: float) -> float:
    """Étape 1 : convertit une note sur 20 en points tranchés (avant 2026)."""
    if note < 5:  return 3
    if note < 10: return 8
    if note < 15: return 13
    return 16


def moyenne_champ(notes: list[float | None], mode_2026: bool = False) -> float | None:
    """
    Étapes 1+2 : moyenne trimestrielle d'un champ disciplinaire.
    notes : liste de 1 à 3 valeurs (None = trimestre absent).
    mode_2026 : True → notes au réel sans tranchage.
    """
    valides = [n for n in notes if n is not None]
    if not valides:
        return None
    if mode_2026:
        return round(sum(valides) / len(valides), 2)
    return round(sum(trancher(n) for n in valides) / len(valides), 2)


def harmoniser(T: float, mu: float, sigma: float) -> float:
    """Étape 3 : H = 10 × [10 + (T − µ) / σ]."""
    if sigma == 0:
        return 100.0
    return 10 * (10 + (T - mu) / sigma)


def score_bilan_periodique(
    notes_par_champ: dict[str, list[float | None]],
    params_harmo: dict[str, dict],
    mode_2026: bool = False,
) -> tuple[float, dict]:
    """
    Calcule le score bilan périodique et le détail par champ.

    notes_par_champ : {champ: [t1, t2, t3]}
    params_harmo    : {champ: {"moyenne": µ, "ecart_type": σ}}
    Retourne        : (score_total, detail_par_champ)
    """
    score = 0.0
    detail = {}
    for champ in CHAMPS:
        notes = notes_par_champ.get(champ, [None, None, None])
        T = moyenne_champ(notes, mode_2026)
        if T is None:
            detail[champ] = {"T": None, "H": None, "points": 0}
            continue
        p = params_harmo.get(champ, {"moyenne": 10.0, "ecart_type": 3.0})
        H = harmoniser(T, p["moyenne"], p["ecart_type"])
        coeff = COEFFICIENTS[champ]
        pts = coeff * H
        score += pts
        detail[champ] = {"T": T, "H": round(H, 3), "coeff": coeff, "points": round(pts, 3)}
    return round(score, 3), detail


# ---------------------------------------------------------------------------
# Score socle commun
# ---------------------------------------------------------------------------

def score_socle(niveaux: list[str]) -> int:
    """
    niveaux : liste de 8 chaînes parmi NIVEAUX_SOCLE.
    Retourne le score socle (max 4800).
    """
    total = sum(NIVEAUX_SOCLE.get(n, 0) for n in niveaux)
    return total * 12


# ---------------------------------------------------------------------------
# Bonus
# ---------------------------------------------------------------------------

def categorie_ips(ips: float) -> str:
    for seuil, cat in IPS_SEUILS:
        if ips >= seuil:
            return cat
    return "défavorisé"


def bonus_ips(ips: float | None, categorie: str | None = None) -> int:
    if categorie:
        return BONUS_IPS_CAT.get(categorie, 0)
    if ips is not None:
        return BONUS_IPS_CAT[categorie_ips(ips)]
    return 0


# ---------------------------------------------------------------------------
# Score total
# ---------------------------------------------------------------------------

def score_total(
    secteur: int,
    ips: float | None = None,
    categorie_ips_val: str | None = None,
    boursier: bool = False,
    bilan: float = 0.0,
    socle: int = 0,
) -> dict:
    """
    Calcule le score total et retourne la décomposition complète.
    secteur : 1 (lycée de secteur) / 2 (hors secteur) / 3 (très hors secteur)
    """
    b_geo    = BONUS_GEO.get(secteur, BONUS_GEO[2])
    b_ips    = bonus_ips(ips, categorie_ips_val)
    b_bours  = 600 if boursier else 0
    total    = b_geo + b_ips + b_bours + bilan + socle

    return {
        "total":          round(total, 0),
        "bonus_geo":      b_geo,
        "bonus_ips":      b_ips,
        "bonus_boursier": b_bours,
        "bilan_periodique": bilan,
        "socle":          socle,
    }
