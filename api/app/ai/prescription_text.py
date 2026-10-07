from collections.abc import Sequence

from app.ai.contracts import KeyPointDraft, MedicationLine

SUGGESTED_QUESTIONS = (
    "Comment je dois prendre ces médicaments ?",
    "Combien de temps dure le traitement ?",
    "Qu'est-ce que je dois vérifier avec le pharmacien ?",
)


def _posology(line: MedicationLine) -> str | None:
    parts: list[str] = []
    if line.times_per_day:
        parts.append(
            "1 fois par jour" if line.times_per_day == 1 else f"{line.times_per_day} fois par jour"
        )
    if line.duration_days:
        parts.append(f"pendant {line.duration_days} jours")
    if line.timing:
        parts.append(line.timing)
    return ", ".join(parts) if parts else None


def _line_label(line: MedicationLine) -> str:
    name = line.display_name or "ce médicament"
    if line.status != "sure" or not line.strength:
        return name
    return f"{name} {line.strength}"


CUT_OFF_WARNING = (
    "Attention, une partie de l'ordonnance n'était pas dans la photo. "
    "Il peut y avoir d'autres médicaments que Leeral n'a pas vus."
)


def explain_prescription(
    lines: Sequence[MedicationLine], *, simple: bool, cut_off: bool = False
) -> str:
    if not lines:
        base = (
            "Leeral n'a trouvé aucun médicament lisible sur cette ordonnance. "
            "Montre-la à ton pharmacien pour qu'il te la lise."
        )
        return f"{CUT_OFF_WARNING} {base}" if cut_off else base
    sentences: list[str] = [CUT_OFF_WARNING] if cut_off else []
    if not simple:
        count = len(lines)
        sentences.append(
            "C'est une ordonnance avec un médicament."
            if count == 1
            else f"C'est une ordonnance avec {count} médicaments."
        )
    for line in lines:
        if line.status == "sure":
            posology = _posology(line)
            if posology:
                sentences.append(f"{_line_label(line)} : {posology}.")
            else:
                sentences.append(
                    f"{_line_label(line)} : la façon de le prendre n'est pas écrite clairement. "
                    "Demande au pharmacien."
                )
        elif line.status == "to_check":
            label = line.name_read or "un médicament"
            sentences.append(
                f"Pour {label}, Leeral n'est pas sûr de sa lecture. "
                "Montre cette ligne au pharmacien pour vérifier."
            )
        else:
            sentences.append(
                "Une ligne de l'ordonnance est illisible. Demande au pharmacien de te la lire."
            )
    sentences.append(
        "Vérifie toujours avec ton pharmacien avant de prendre un médicament."
        if not simple
        else "Demande au pharmacien si tu as un doute."
    )
    return " ".join(sentences)


def prescription_key_points(
    lines: Sequence[MedicationLine], *, cut_off: bool = False
) -> tuple[KeyPointDraft, ...]:
    points: list[KeyPointDraft] = []
    if cut_off:
        points.append(
            KeyPointDraft(
                kind="info",
                tag="Incomplet",
                title_fr="Une partie de l'ordonnance manque",
                detail_fr="Le haut ou le bas de la page n'était pas dans la photo.",
            )
        )
    for line in lines:
        if line.status == "unreadable":
            points.append(
                KeyPointDraft(
                    kind="info",
                    tag="Illisible",
                    title_fr="Ligne illisible",
                    detail_fr="Demande au pharmacien de te la lire.",
                )
            )
            continue
        detail = _posology(line) if line.status == "sure" else None
        points.append(
            KeyPointDraft(
                kind="action",
                tag="Médicament" if line.status == "sure" else "À vérifier",
                title_fr=_line_label(line),
                detail_fr=detail or "À vérifier avec le pharmacien.",
            )
        )
    return tuple(points)


def prescription_context(lines: Sequence[MedicationLine], *, cut_off: bool = False) -> str:
    labels = {"sure": "lu avec certitude", "to_check": "à vérifier", "unreadable": "illisible"}
    rows = []
    for line in lines:
        posology = _posology(line) if line.status == "sure" else None
        rows.append(
            f"- {_line_label(line)} ({labels[line.status]})"
            + (f" : {posology}" if posology else "")
        )
    header = "Médicaments de l'ordonnance"
    if cut_off:
        header += " (la page est coupée, cette liste peut être incomplète)"
    return f"{header} :\n" + "\n".join(rows)
