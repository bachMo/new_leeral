# Marques, opérateurs et institutions sénégalais courants : un nom propre comme « Orange Money »
# ou « Wave » désigne le même service quelle que soit la langue parlée, le traduire n'a aucun sens
# et produit souvent un charabia qui induit en erreur. Liste non exhaustive (voir aussi
# l'extraction dynamique dans `app/ai/real/analysis.py`, qui couvre ce qui manque ici) : on ne
# traduit jamais un nom propre, donc l'y ajouter ne présente pas le même risque qu'une table de
# traduction (contrairement à `posology_phrases.py`).
KNOWN_BRAND_NAMES: tuple[str, ...] = (
    # Argent mobile
    "Orange Money",
    "Wave",
    "Free Money",
    "Wizall",
    "Joni Joni",
    # Télécom
    "Orange",
    "Free",
    "Expresso",
    "Sonatel",
    # Énergie et eau
    "Senelec",
    "Sen'Eau",
    "SDE",
    # Poste
    "La Poste",
    "Poste Finances",
    # Banques et microfinance
    "Banque Islamique du Sénégal",
    "CBAO",
    "Ecobank",
    "Société Générale",
    "BICIS",
    "UBA",
    "Banque Agricole",
    "Bank of Africa",
    "Crédit Mutuel du Sénégal",
    "Crédit Mutuel",
    # Administration
    "CMU",
    "IPRES",
    "CSS",
)


def known_brand_terms(text: str) -> tuple[str, ...]:
    """Known brand/institution names found verbatim (case-insensitive) in `text`."""
    lowered = text.lower()
    return tuple(name for name in KNOWN_BRAND_NAMES if name.lower() in lowered)
