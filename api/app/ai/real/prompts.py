LANGUAGE_NAMES = {
    "fr": "French",
    "wo": "Wolof",
    "ff": "Fulfulde (Pular/Fula)",
    "sr": "Serer",
}

CLASSIFY_IMAGE = """Tu regardes la photo d'un document. Détermine son type et sa langue. \
Réponds uniquement par un objet JSON valide, sans aucun texte autour.

Types possibles : "prescription" (ordonnance médicale, liste de médicaments prescrits), \
"lab_result" (résultat ou demande d'analyse, PAS une liste de médicaments), "invoice" (facture), \
"contract" (contrat), "school" (bulletin, convocation scolaire), \
"bank" (relevé, courrier de banque), \
"administrative" (courrier officiel, attestation, certificat), "letter" (autre lettre), \
"unknown" (si tu n'es pas sûr).

Langues possibles : "fr", "en", "mixed", "unknown".

Ne devine jamais si tu hésites : mets "confident": false plutôt que de forcer un type.

Format exact :
{"document_type": "...", "document_language": "fr|en|mixed|unknown", "confident": true}"""

CLASSIFY_TEXT = (
    CLASSIFY_IMAGE.replace("Tu regardes la photo d'un document.", "Tu lis le texte d'un document.")
    .replace("{", "{{")
    .replace("}", "}}")
    + "\n\n<document>\n{text}\n</document>"
)

TRANSCRIBE_PAGE = """Recopie fidèlement tout le texte lisible de cette photo de document, \
dans l'ordre de lecture, ligne par ligne. N'invente rien, ne corrige rien, ne résume rien. \
Écris [illisible] à la place d'un passage que tu ne peux pas lire. \
Si le haut ou le bas de la page n'apparaît pas dans la photo (la page continue visiblement \
hors du cadre), écris [page_coupee] sur une ligne à part, à l'endroit où le contenu manque. \
Réponds uniquement avec le texte recopié."""

READ_PRESCRIPTION = """Tu lis la photo d'une ordonnance médicale. Réponds uniquement par un \
objet JSON valide, sans aucun texte autour.

Règles :
- Ne devine jamais. Si un nom, un dosage, un nombre de prises ou une durée est illisible ou \
incertain, mets null pour ce champ et indique "legible": "partial" ou "no".
- Ne corrige pas un nom de médicament : écris exactement ce que tu lis.
- Ne complète jamais une posologie absente de l'ordonnance.
- "times_per_day" est un entier (prises par jour). "duration_days" est un entier (jours).
- "strength" est le dosage lu avec son unité, par exemple "500 mg".
- "legible": "yes" seulement si TOUTE la ligne est lisible sans aucun doute.
- "page_cut_off": true si le haut ou le bas de la page n'apparaît pas dans la photo (la page \
continue visiblement hors du cadre, il peut donc manquer une ligne de médicament). false si \
toute la page est dans le cadre, même si certaines lignes sont illisibles.
- "form" est la forme pharmaceutique (comprimé, sirop, gélule...) seulement si elle est écrite ; \
sinon null. Ne la déduis jamais du nom du médicament.
- "instructions" est une consigne particulière écrite sur la ligne, autre que le moment de prise \
(par exemple "à jeun", "ne pas écraser") ; sinon null.
- "dci_read" est la dénomination commune internationale (DCI) seulement si elle est écrite \
explicitement sur l'ordonnance, en plus ou à la place du nom de marque ; sinon null. Ne déduis \
jamais la DCI à partir du nom de marque : si seule la marque est écrite, laisse "dci_read" à null.
- "line_position" est la position verticale approximative du milieu de cette ligne sur la page, \
entre 0 (tout en haut) et 1 (tout en bas) ; une estimation grossière suffit, mets null si tu ne \
peux vraiment pas estimer.

Format exact :
{"document_language": "fr|en|mixed|unknown", "page_cut_off": false,
 "medications": [{"raw": "ligne telle que lue", "name_read": "...", "dci_read": "...",
 "strength": "...", "form": "...", "times_per_day": 3, "duration_days": 7, "timing": "...",
 "instructions": "...", "line_position": 0.4, "legible": "yes|partial|no"}]}"""

READ_PRESCRIPTION_TEXT = (
    READ_PRESCRIPTION.replace(
        "Tu lis la photo d'une ordonnance médicale.", "Tu lis le texte d'une ordonnance médicale."
    )
    .replace("{", "{{")
    .replace("}", "}}")
    + "\n\n<ordonnance>\n{text}\n</ordonnance>"
)

ANALYZE_DOCUMENT = """Tu aides une personne qui ne lit pas le français à comprendre un document \
administratif. Voici le texte du document, extrait automatiquement (il peut contenir des erreurs \
de lecture).

<document>
{text}
</document>

Date du jour : {today}.

Réponds uniquement par un objet JSON valide, sans texte autour, au format exact :
{{"title": "titre court du document, 6 mots maximum",
 "doc_type": "invoice|letter|contract|lab_result|school|bank|administrative|other",
 "category": "health|money|school|admin|other",
 "issuer": "organisme ou personne qui a envoyé le document, ou null",
 "document_date": "AAAA-MM-JJ ou null",
 "urgency": "urgent|soon|none",
 "urgency_label": "phrase très courte sur ce qui presse, ou null",
 "main_due_date": "date limite principale AAAA-MM-JJ ou null",
 "main_amount_xof": montant principal à payer en francs CFA (entier) ou null,
 "summary_fr": "explication orale en 4 à 8 phrases courtes",
 "key_points": [{{"kind": "action|date|amount|info", "tag": "un mot", "title_fr": "...",
   "detail_fr": "... ou null", "due_date": "AAAA-MM-JJ ou null", "amount_xof": entier ou null}}],
 "suggested_questions": ["question 1", "question 2", "question 3"],
 "contract": null si ce n'est pas un contrat, sinon
   {{"duration": "durée de l'engagement telle qu'écrite, ou null",
    "auto_renewal": "condition de reconduction telle qu'écrite, ou null",
    "termination": "condition de résiliation telle qu'écrite, ou null",
    "penalties": ["pénalité telle qu'écrite", "..."],
    "parties": ["partie au contrat telle qu'écrite", "..."],
    "amounts": [{{"label": "à quoi correspond le montant", "amount_xof": entier ou null}}],
    "vigilance_points": ["point auquel la personne doit prêter attention, décrit sans jugement",
     "..."]}}}}

Règles :
- "summary_fr" sera traduit puis lu à voix haute : phrases simples, tutoiement, pas de liste, \
pas de sigle non expliqué. Commence par dire de quel document il s'agit et qui l'envoie, puis ce \
qu'il faut faire et avant quand.
- N'invente jamais une date, un montant, un nom ou une obligation qui n'est pas dans le texte.
- N'ajoute aucun conseil, recommandation ou mise en garde qui ne figure pas explicitement dans \
le texte. Si le document ne dit rien sur un point, n'en parle pas.
- 2 à 5 points clés, du plus important au moins important.
- Les questions proposées sont celles que la personne se poserait, formulées à la première \
personne, courtes.
- Remplis "contract" uniquement si le document est un contrat ou un engagement avec des \
conditions (durée, résiliation, pénalités...). Chaque champ reprend ce qui est écrit dans le \
texte, jamais une valeur déduite ou habituelle pour ce type de contrat. Laisse à null ou vide \
ce qui n'est pas écrit.
- Pour "vigilance_points" : décris le fait sans jugement ni recommandation. Ne dis jamais à la \
personne de signer, de ne pas signer, ou ce qu'elle devrait faire. Ne donne aucun avis juridique."""

SIMPLIFY = """Réécris cette explication pour une personne qui a du mal à comprendre. \
Garde seulement l'essentiel : ce que c'est, ce qu'il faut faire, avant quand. 3 phrases courtes \
au maximum, tutoiement, mots de tous les jours. Ne rajoute aucune information.

<explication>
{summary}
</explication>

Réponds uniquement par un objet JSON valide : {{"summary_fr": "..."}}"""

ANSWER_QUESTION = """Tu es Leeral. Tu réponds à une question sur un document, pour une personne \
qui ne lit pas le français. Ta réponse sera traduite puis lue à voix haute.

<document>
{document}
</document>

<historique>
{history}
</historique>

Question : {question}

Règles :
- Réponds uniquement à partir du document. Si la réponse n'y est pas, dis-le simplement et \
conseille à qui s'adresser.
- N'invente jamais un chiffre, une date, un montant ou une dose.
{safety_rules}- 1 à 3 phrases courtes, tutoiement, mots simples.

Réponds uniquement par un objet JSON valide :
{{"answer": "...", "quote": "courte phrase du document qui justifie la réponse, ou null"}}"""

ANSWER_FREE_QUESTION = """Tu es Leeral, un assistant qui aide des personnes qui ne lisent pas le \
français dans leurs démarches de tous les jours. Ta réponse sera traduite puis lue à voix haute.

<historique>
{history}
</historique>

Question : {question}

Règles : 1 à 3 phrases courtes, tutoiement, mots simples. Pas de conseil médical, juridique ou \
financier précis : oriente vers la bonne personne. N'invente jamais un chiffre.

Réponds uniquement par un objet JSON valide : {{"answer": "...", "quote": null}}"""

PRESCRIPTION_SAFETY_RULES = """- C'est une ordonnance. Ne donne jamais une dose, un nombre de \
prises ou une durée qui n'est pas écrit dans la liste des médicaments ci-dessus.
- Pour une ligne marquée "à vérifier" ou "illisible", dis de demander au pharmacien.
- Ne donne aucun avis médical : pour tout le reste, renvoie vers le pharmacien ou le médecin.
"""

INTERPRET_WRITING_ANSWER = """Tu aides une personne à remplir un document. On lui a posé la \
question : "{question}". {hint}

Sa réponse (traduite automatiquement en français) : "{answer}"

Extrais l'information demandée, propre et bien écrite en français, prête à être mise dans le \
document. Ne rajoute rien qui n'est pas dans la réponse. Si la réponse ne contient pas \
l'information, mets null.

Réponds uniquement par un objet JSON valide : {{"value": "..." }}"""

COMPOSE_WRITING = """Tu rédiges en français un document professionnel pour une personne qui ne \
sait pas écrire le français. Type demandé : {writing_type}.

Informations données par la personne :
{facts}

Règles :
- Utilise uniquement ces informations. N'invente aucune expérience, aucun diplôme, aucune date, \
aucun chiffre. Si une information manque, n'écris pas la rubrique.
- Style sobre, phrases correctes, prêt à être imprimé.
- {documents_rule}
- "readback_fr" résume en 3 phrases ce que contient le document, pour le lire à voix haute à la \
personne avant qu'elle l'envoie.

Réponds uniquement par un objet JSON valide :
{{"documents": [{{"kind": "cv|cover_letter|letter", "title": "...",
  "sections": [{{"heading": "... ou null", "lines": ["...", "..."]}}]}}],
 "readback_fr": "..."}}"""

EXTRACT_VOCABULARY = """Voici un document en français. Choisis au plus {limit} mots du \
document utiles à apprendre pour une personne qui débute en lecture du français et doit gérer \
ses papiers (santé, argent, école, administration). Préfère les mots qui reviennent souvent dans \
ce genre de papiers. Pas de noms propres, pas de chiffres.

<document>
{text}
</document>

Réponds uniquement par un objet JSON valide :
{{"words": [{{"word_fr": "mot au singulier, en minuscules",
  "category": "health|money|school|admin|common",
  "sentence_fr": "phrase courte du document qui contient le mot"}}]}}"""

TRANSLATE = """Translate the following text from {source} to {target}. Output ONLY the \
translation. No explanation, no quotes, no notes. The text may contain markers of the exact form \
⟦0⟧, ⟦1⟧, ⟦2⟧ (a number between double angle brackets). These replace protected content \
(medication names, numbers) that must not be altered. Copy each marker into your translation \
EXACTLY as written, unchanged, in the equivalent position for its meaning in the sentence. Never \
translate, reformat, remove, or duplicate a marker.
Never write a draft, a correction, a rewrite, or any comment about your own answer — even if your \
first attempt feels wrong. Output must be a single line with no line breaks: only the final \
translation, nothing before it and nothing after it.

Text:
{text}"""
