# Décisions et règles d'or du module IA

Historique des décisions qui ont façonné `app/ai/` et pourquoi, transféré et adapté depuis le
dépôt d'étude initial (`leeral-project`) pour qu'aucun de ces choix ne se reperde. Complète
`AI_MODULE.md` (le « quoi » et le « comment ») avec le « pourquoi ». Comme `AI_MODULE.md`, ce
fichier change rarement et toute décision notable sur `app/ai/` devrait y ajouter une ligne.

---

## 1. Règles d'or (sécurité du produit, non négociables)

Ces règles s'appliquent à tout code qui touche `app/ai/`, qu'il soit dans `mock/` ou `real/`.

1. **Jamais de posologie inventée.** Une dose, une durée ou une fréquence provient du document
   lu ou n'est pas affichée. Pour une ordonnance, voir `real/prescription.py` : le dosage n'est
   affiché que pour une ligne `sure` (`prescription_text.py`, `_posology`).
2. **Jamais de traduction d'un nom de médicament ou d'un nombre.** Protégé par un jeton
   (`real/safety/protected_tokens.py`, `⟦0⟧`, `⟦1⟧`...) avant l'appel au traducteur, et réinséré
   tel quel après. Un jeton manquant ou dupliqué après traduction déclenche une nouvelle tentative
   sur le modèle de secours, jamais une valeur devinée.
3. **L'incertitude est toujours visible.** Une ligne `to_check` ou `unreadable` ne ressemble
   jamais à une ligne `sure` (`MedicationLine.status`, `field_statuses`).
4. **Le LLM n'invente pas le contenu factuel.** `dialogue.py` (`numbers_are_grounded`) rejette
   toute réponse contenant un chiffre absent du document source et la remplace par une réponse
   prudente ; `analysis.py` (`_date_in_text`, `_amount_in_text`) ne garde une date ou un montant
   renvoyé par le LLM que s'il apparaît effectivement dans le texte lu.
5. **Aucun avis médical, juridique ou financier précis.** Le LLM renvoie vers le pharmacien, le
   médecin ou l'organisme compétent pour tout ce qui dépasse ce que le document dit explicitement
   (`prompts.PRESCRIPTION_SAFETY_RULES`, `ANSWER_FREE_QUESTION`).
6. **Une sortie de modèle non conforme ne plante jamais silencieusement.** Toute réponse JSON est
   validée par Pydantic (`real/pages.py`, `real/prescription.py`, `real/analysis.py`,
   `real/dialogue.py`, `real/writing.py`, `real/vocabulary.py`) ; un format invalide devient
   `AiOutputError`, jamais une valeur par défaut devinée.
7. **Toute évolution du module passe par `AiEngine`.** Le reste de l'application n'appelle jamais
   un fournisseur (`OpenRouterClient`, `KirikuClient`) directement — voir `AI_MODULE.md`.

---

## 2. Pas d'entraînement de modèle, briques existantes + plan B pour chacune

**Décision (hackathon).** Aucune brique IA n'est entraînée ou affinée : lecture, traduction,
LLM, ASR/TTS sont tous des modèles généralistes déjà disponibles (OpenRouter, KIRIKU), choisis
et validés par comparaison plutôt que construits. `MockAiEngine` sert de plan B pour développer
et tester sans aucune des briques réelles.

**Raison.** Contrainte de temps (hackathon) : entraîner quoi que ce soit n'était pas réaliste
dans le délai disponible, et des modèles généralistes bien choisis suffisent à la tâche.

---

## 3. Lexique de noms (liste ouverte), pas une base de fiches rédigées

**Décision.** Le lexique (`real/safety/lexicon.py`, `LEXICON.md`) est une liste de noms sans
aucun contenu médical rédigé : il vérifie qu'un nom **existe**, pas ce qu'il **fait**. Noms de
marque et DCI uniquement, jamais de posologie ou d'indication dans le lexique lui-même.

**Raison.** Vérifie la lecture sans jamais avoir à rédiger ou maintenir du contenu médical — la
responsabilité la plus lourde à porter pour une petite équipe.

---

## 4. Wolof et pulaar uniquement, alphabet latin

**Décision.** Seules langues cibles : wolof et pulaar, toutes deux en alphabet latin. L'Ajami
(écriture arabe du pulaar/wolof) est exclu. Le sérère est accepté par le modèle de données et
affiché « bientôt » (voir `api/README.md`, section Choix techniques) : KIRIKU n'a pas de voix
sérère pour l'instant (`real/clients/kiriku.py`, `_TTS_VOICES` ne couvre que `wo`/`ff` ; `_ASR_
LANGUAGES` accepte `srr` en entrée, vérifié sans voix de sortie correspondante).

**Raison.** Concentration du périmètre sur les deux langues où KIRIKU offre à la fois ASR et TTS.

**Vérifié empiriquement le 7 octobre 2026** (`leeral check-ai --language sr`, après avoir
temporairement ajouté `Language.SERER: "srr"` à `_TTS_VOICES` et `Language.SERER` à
`AVAILABLE_LANGUAGES` pour le test) : KIRIKU refuse la requête TTS avec `400 "Unsupported voice:
srr. Use one of ['wolof', 'pulaar']."` — réponse directe du fournisseur, pas une supposition.
Les deux changements ont été annulés après le test. **Ne pas retenter sans revérifier la
documentation KIRIKU au moment voulu** : rien n'indique qu'une voix sérère arrivera, mais rien
n'indique le contraire non plus — ce test date du 7 octobre 2026, pas une garantie permanente.
La traduction (`anthropic/claude-sonnet-5.5`) a répondu sans erreur pour le sérère pendant ce
test, mais sans aucune validation de qualité (aucun locuteur, aucune étude — voir décision 22) :
ça ne veut rien dire de plus que « l'appel API n'a pas échoué ».

---

## 5. Le texte structuré est la source de vérité du document

**Décision.** `DocumentAnalysis`/`DocumentContext` (`contracts.py`) sont la source de vérité :
tout raisonnement se fait en français, à partir de ces objets. La traduction et la voix sont
produites à la fin, par `localize` puis `speak` — jamais l'inverse (voir `AI_MODULE.md`, « Le
contrat »).

**Raison.** Découple lecture et explication, rend chaque étape testable isolément (les tests de
`tests/ai/` construisent directement ces objets sans repasser par un modèle).

---

## 6. Double lecture d'ordonnance obligatoire, lexique non optionnel

**Décision (5 octobre 2026, dépôt d'étude).** Double lecture : `qwen/qwen3.8-27b`
(`reasoning.effort=none`) + `meta/muse-glimmer-30b` (`reasoning.effort=minimal`, le raisonnement
n'est pas désactivable sur ce modèle — `"Reasoning is mandatory for this endpoint"`), fournisseur
OpenRouter figé `deepinfra` (sert les deux modèles, comparaison reproductible). Le lexique est
**obligatoire** sur le nom des deux lectures, jamais optionnel : voir règle d'or n°2.

**Raison.** Testé contre la vraie API sur 30 ordonnances réelles (`eval/`) : sans lexique, un des
deux modèles seul atteint 12 erreurs non signalées ; avec lexique + double lecture, 2 restantes
(limite connue : un nom qui dérape vers un *autre* vrai médicament existant passe le lexique, et
nécessite `pharmacology.py` pour être intercepté — voir décision 7). Détail chiffré :
`eval/results/EXPERIMENTS.md`.

---

## 7. Cohérence pharmacologique en complément du lexique

**Décision.** `real/safety/pharmacology.py` ajouté en complément du lexique (dose/durée
plausibles ; aliases par DCI, forme non vérifiée pour l'instant). Statut : ensemble de départ
DRAFT, `reviewed_by` vide dans `pharmacology_rules.csv` — aucune entrée n'a encore été relue par
un professionnel de santé.

**Raison.** Le lexique seul ne détecte pas une lecture qui dérape vers le nom d'un *autre* vrai
médicament : cas réel « Fentanyl 800mg » dans le dépôt d'étude, où 800 mg dépasse de plus de 300
fois la dose quotidienne maximale plausible des formes transmuqueuses — intercepté uniquement par
cette vérification, jamais par le lexique (qui confirme seulement que « Fentanyl » existe).

---

## 8. Classification du document avant la lecture

**Décision.** `real/pages.py` (`PageReader.classify`) classe le document (type + langue) **avant**
`analyze_document` ne décide de la voie ordonnance ou document générique, avec double
classification (deux modèles, même principe que la double lecture) : en cas de désaccord sur le
type, on choisit la voie la plus prudente (`_safest_type` : un désaccord impliquant
« prescription » reste « prescription », jamais classé par défaut en type inconnu moins
contraignant).

**Raison.** Ferme un angle mort validé contre de vraies images dans le dépôt d'étude : un
certificat médical et un bon de labo n'étaient pas distingués d'une ordonnance par le premier
banc d'essai de lecture (`read_bench.py`), qui n'avait pas d'étape de classification.

---

## 9. Choix du traducteur : `gemini-2.5-flash-lite` en principal, `gpt-5-mini` en secours

**Décision.** `google/gemini-2.5-flash-lite` retenu comme modèle **principal** de traduction :
qualité statistiquement égale à `openai/gpt-5-mini` sur l'échantillon testé (29,1 vs 29,9 chrF,
écart dans le bruit sur 20 phrases) mais 3× moins cher et plus rapide. `gpt-5-mini` gardé en
**secours** (`Translator`, bascule uniquement sur panne fournisseur, pas sur simple différence de
qualité) plutôt qu'écarté, pour dépendre de deux fournisseurs différents (Google, OpenAI).
`google/gemini-3.1-pro-preview` écarté : le plus cher et le plus lent des 6 modèles comparés,
malgré le meilleur chrF. Pulaar non définitivement tranché : aucun corpus ouvert pour le pulaar
sénégalais au moment de l'étude, seul le fulfulde du Nigéria (FLORES-200) a été testé.

**Raison.** Étude chiffrée sur 20 phrases FLORES-200 × 8 sens × 6 modèles — voir
`translation-study.md` pour le détail complet, y compris l'incident méthodologique corrigé en
cours d'étude (troncature de `gemini-3.1-pro-preview` par un budget de tokens trop court).

**Supersedée par la décision 22** (7 octobre 2026) : `gemini-2.5-flash-lite` remplacé par
`anthropic/claude-sonnet-5.5` comme modèle principal, suite à des erreurs de traduction réelles
non révélées par cette étude générique. Conservé ici pour mémoire : le raisonnement sur le choix
du fournisseur de secours (`gpt-5-mini`) et la réserve sur le pulaar restent valables.

---

## 10. Jetons protégés et traduction phrase par phrase avec repli gracieux

**Décision.** `real/safety/protected_tokens.py` (jetons `⟦N⟧` pour noms de médicaments et
nombres, avec limites de mots `\b` pour ne jamais couper un nombre en plein milieu d'un autre) et
`real/translation.py` (traduction phrase par phrase, une relance sur le modèle de secours si un
jeton est perdu, puis **remplacement par un avertissement traduit** — jamais le français brut —
si la phrase échoue encore). Si aucune phrase ne se traduit, la tâche échoue avec
`TranslationError` plutôt que de livrer un résultat partiellement en français.

**Raison.** Testé contre la vraie API dans le dépôt d'étude : le prompt générique du traducteur
ne préservait pas les jetons (le modèle essayait de les « traduire » et les perdait) tant qu'une
instruction explicite de préservation caractère-par-caractère n'avait pas été ajoutée au prompt
(`prompts.TRANSLATE`). Sans cette correction, la protection des jetons aurait échoué sur
pratiquement toutes les phrases contenant un médicament ou un nombre. Le repli par avertissement
traduit (plutôt qu'un échec dur ou du français non traduit silencieusement livré) a été ajouté
après coup : « ne jamais perdre une phrase en silence, et ne jamais lire du français à la place »
— voir `AI_MODULE.md`, section « Ce qui a changé ».

---

## 11. LLM à deux vitesses selon la taille du document

**Décision.** `real/reasoning.py` (`Reasoner`) choisit entre `llm_model_short`
(`qwen/qwen3.8-27b`) et `llm_model_long` (`google/gemini-3.1-pro-preview`) selon un seuil
d'environ 8000 tokens estimés (`llm_long_document_token_threshold`). Pas de banc d'essai Leeral
chiffré pour ce choix précis (contrairement au Reader et au Translator) : basé sur une revue de
benchmarks publics de contexte long (RULER, NIAH-2, MRCR v2) et une comparaison de prix sur le
catalogue réel d'OpenRouter.

**Raison.** Un petit modèle d'une famille oublie nettement plus sur une recherche multi-éléments
en contexte long que son grand frère (écart mesuré de 25 points, Gemini 3.1 Flash Lite 60,1 % vs
Gemini 3.1 Pro 84,9 % sur MRCR v2 8 aiguilles @ 128K) ; à l'échelle d'un document court, l'écart
de prix entre tous les candidats est négligeable — il ne devient significatif qu'à l'échelle d'un
document long. Détail complet : `llm-study.md`.

---

## 12. Seuils de qualité d'image recalibrés contre de vraies ordonnances

**Décision.** `quality_min_width`/`quality_min_height` à **300px** (pas 600) et aucune heuristique
de détection de cadrage approximatif par variance au bord (`_border_suggests_cutoff` du dépôt
d'étude) dans `app/ai/quality.py` : la fonction n'existe simplement pas ici.

**Raison.** Mesuré en testant le pipeline complet contre les 34 vraies ordonnances d'`eval/` dans
le dépôt d'étude : un seuil de résolution à 600px rejetait la quasi-totalité d'images réellement
lisibles par le Reader (ex. 497×557, 395×506 px) ; l'heuristique de cadrage par variance au bord
avait un taux de faux positifs mesuré d'environ 90 % sur ce même jeu réel (contenu normal jusqu'au
bord sur la plupart des photos). Les deux leçons sont déjà appliquées ici — ne pas les
réintroduire sans un vrai détecteur de document validé (un cadrage mal détecté reste, selon
`roadmap-technique.md` du dépôt d'étude, « faisable sous conditions », pas acquis).

---

## 13. Page coupée : signal jugé par le modèle de lecture, pas une heuristique locale

**Décision (7 octobre 2026).** Détection d'une page partiellement hors cadre (haut ou bas de la
page absent de la photo) confiée au modèle de lecture lui-même, jamais à une heuristique locale :
champ `"page_cut_off"` ajouté au JSON de `READ_PRESCRIPTION`/`READ_PRESCRIPTION_TEXT`
(`app/ai/real/prompts.py`), exigé **des deux modèles** avant d'être retenu
(`app/ai/real/prescription.py`, fonction `page_cut_off`) — même logique de prudence que
`both_legible`. Pour un document générique, marqueur texte `[page_coupee]` dans `TRANSCRIBE_PAGE`,
lu par un seul modèle (`app/ai/real/engine.py`, `_analyze_document`) : pas de double lecture ici,
le coût de doubler la transcription de **tout** document non-ordonnance pour ce seul signal
n'étant pas justifié par le même enjeu de sécurité qu'une posologie.

Une page signalée coupée **ne fait jamais disparaître les lignes déjà lues** : contrairement à un
nom de médicament illisible (`legible`), qui invalide la ligne elle-même, une page coupée ne dit
rien sur la fiabilité de ce qui a été lu, seulement sur ce qui pourrait manquer. Les informations
visibles restent donc affichées, et un avertissement (`CUT_OFF_WARNING` dans
`app/ai/prescription_text.py` et `app/ai/real/analysis.py`) est ajouté au début de l'explication
parlée et comme point clé dédié (tag `"Incomplet"`), plutôt que de rejeter tout le document.

**Raison.** Directement informé par la décision 12 : une heuristique locale par variance de pixels
avait un taux de faux positifs d'environ 90 % sur de vraies ordonnances. Laisser le modèle de
lecture juger (il voit le contenu, pas seulement les pixels du bord) évite de reproduire cette
erreur, mais le signal mono-modèle du chemin générique n'a pas encore été mesuré contre `eval/` —
à valider avant de le considérer pleinement fiable, même posture que `pharmacology_rules.csv`
(DRAFT, voir décision 7). Rejeter tout le document aurait aussi été plus simple à coder, mais
aurait privé l'utilisateur d'une information déjà lue avec certitude pour une simple question de
cadrage, un coût jugé disproportionné par rapport au risque (contrairement à une posologie
incomplète, où l'incertitude doit rester invisible nulle part dans l'explication).

---

## 14. Noms de mois traduits par dictionnaire figé, jamais par le traducteur

**Décision (7 octobre 2026).** Les jetons protégés (`real/safety/protected_tokens.py`) ne
couvrent que les nombres et les noms de médicaments : un nom de mois français (« octobre »)
partait en texte libre vers le traducteur, comme n'importe quel mot. Observé sur une vraie facture
(`eval/`, voir aussi `api/samples/facture.jpg`) : « 30 octobre 2026 » devient « 30 atum 2026 »
(« atum » = année en wolof), avec un `translation_token_mismatch duplicated=[...]` sur le nombre
voisin — le modèle de secours corrige le jeton numérique dupliqué mais pas le mois, puisque rien
ne lui dit que ce mot doit rester inchangé.

`real/safety/dates.py` (`localize_month_names`) remplace maintenant le nom du mois français par
son équivalent dans la langue cible **avant** l'appel au traducteur, puis l'ajoute aux
`protected_terms` de `Translator.localize` : le mot traduit est ensuite transformé en jeton comme
un nom de médicament, jamais retouché par le LLM.

**DRAFT, non relu par un locuteur natif.** Seul « oktoobar » (octobre, wolof) est confirmé,
d'après l'exemple donné par l'utilisateur lui-même. Les 11 autres mois wolof, et les 12 mois
pulaar et sérère, sont une hypothèse de travail (emprunt direct du français, même schéma
qu'« oktoobar ») — même statut que `pharmacology_rules.csv` (`reviewed_by` vide, décision 7) :
à faire valider avant de considérer ces noms fiables en production. Le sérère est inclus bien
qu'il ne soit pas encore dans `AVAILABLE_LANGUAGES` (décision 4), pour ne pas avoir à refaire ce
travail quand une voix TTS sérère sera disponible.

**Raison.** Un dictionnaire figé élimine cette classe d'erreur quelle que soit la qualité du
traducteur choisi (décision 9) : les noms de mois forment un vocabulaire fermé de 12 mots, pas un
problème de traduction générale.

---

## 15. Le résumé et les points clés sont filtrés des phrases contenant un chiffre inventé

**Décision (7 octobre 2026).** `analysis.py` ne vérifiait l'ancrage au texte source que pour les
champs structurés (`main_amount_xof`, `main_due_date`, et les mêmes champs par point clé) —
jamais pour le texte libre (`summary_fr`, `title_fr`/`detail_fr`). Observé en pratique : le LLM
ajoute parfois une information plausible mais absente du document (règle d'or n°4). `analyze_text`
découpe maintenant `summary_fr` en phrases (`translation.split_sentences`, déjà utilisé pour la
traduction) et retire toute phrase contenant un chiffre absent du texte lu, même principe que
`dialogue.numbers_are_grounded` pour les réponses ; un point clé dont le titre ou le détail
contient un chiffre non ancré est retiré en entier plutôt que bricolé. Chaque filtrage est loggé
(`leeral.ai.analysis`, `analysis_summary_ungrounded` / `analysis_key_point_ungrounded`) pour rester
visible plutôt que silencieux (règle d'or n°6). Le prompt `ANALYZE_DOCUMENT` interdit en outre
explicitement d'ajouter un conseil ou une mise en garde absente du texte.

**Limite assumée.** Ce filtre ne détecte que les hallucinations contenant un chiffre. Un conseil
inventé sans aucun nombre (« contacte le service client ») n'est pas détectable par ce moyen :
seule une vérification par un second appel LLM le pourrait, ce qui a été écarté ici pour ne pas
aggraver la latence déjà mesurée (décision 11, et le constat du 7 octobre 2026 sur la lenteur de
l'analyse). À surveiller via `leeral try-document` plutôt que résolu.

**Raison.** Même logique que `numbers_are_grounded` (décision existante pour `dialogue.py`) :
un chiffre absent du document source est un signal fort et vérifiable sans appel modèle
supplémentaire, contrairement à une hallucination purement qualitative.

---

## 16. Classification incertaine : question suggérée, jamais une réécriture silencieuse du type

**Décision (7 octobre 2026).** Quand la classification (`real/pages.py`, `PageReader.classify`)
n'est pas confiante ou renvoie `"unknown"`, le document n'est **pas** bloqué en attente d'une
confirmation : il suit la voie générique comme avant, mais `analyze_text` (`real/analysis.py`)
ajoute un point clé dédié (tag `"Incertain"`) et place « Quel est ce document ? » en tête des
questions suggérées — le circuit déjà existant (`DocumentSuggestedQuestion` →
`POST /conversations/{id}/messages` → `QuestionAnswerer`). La réponse de l'utilisateur reste
conversationnelle : elle n'écrit jamais `doc_type`/`category` en retour, qui restent ceux déduits
par le LLM.

**Raison.** Pas de nouveau statut `Document` ni de route de confirmation pour un cas qui n'empêche
pas de lire le document (contrairement à une ordonnance où le doute change la sécurité affichée) :
le mécanisme question/réponse existant suffit à faire savoir à l'utilisateur que Leeral n'est pas
sûr, sans le nouvel état intermédiaire qu'aurait demandé une réécriture fiable du type à partir
d'une réponse vocale libre.

---

## 17. DCI lue seulement si écrite, jamais déduite de la marque

**Décision (7 octobre 2026).** Le nouveau champ `dci_read` (`MedicationReading`,
`real/prompts.py`) n'est rempli par le modèle que si la DCI apparaît explicitement sur
l'ordonnance, en plus ou à la place de la marque — jamais déduite du nom de marque lu. Vérifié par
`Lexicon.lookup(name, dci_only=True)` (`real/safety/lexicon.py`), qui restreint la recherche aux
termes dont le `kind` (colonne déjà présente dans `lexicon_terms.csv`, voir `LEXICON.md` §4.3) est
`dci` ou `dci_core` — `Lexicon` conservait `kind` seulement par statut avant cette décision (le
premier `kind` rencontré pour un terme), ce qui aurait exclu à tort un terme comme « amoxicilline »
(à la fois marque, DCI et cœur de DCI selon la ligne du CSV) ; `kind` est maintenant un ensemble
par terme.

**Raison.** Construire une table marque→DCI (déjà calculable depuis `lexicon_entries.csv`, le
fichier intermédiaire du pipeline de construction, non livré) aurait donné une bien meilleure
couverture — la plupart des ordonnances n'écrivent que la marque — mais au prix d'un nouveau
pipeline de livraison et d'une relecture de `LEXICON.md`. Pour cette itération, lire uniquement ce
qui est écrit reste strictement dans l'esprit de la règle d'or n°1 (rien d'inventé) : un champ
souvent vide plutôt qu'une correspondance déduite, même fiable à 99 %.

---

## 18. Extraction de contrat via les points clés, pas une nouvelle table

**Décision (7 octobre 2026).** Les contrats n'ont pas de pipeline de double lecture dédié comme
les ordonnances : `ANALYZE_DOCUMENT` (`real/prompts.py`) gagne un champ JSON optionnel `"contract"`
(durée, reconduction, résiliation, pénalités, parties, montants), rempli par le même appel LLM
unique que tout document générique, uniquement quand le document en est un. `analyze_text`
(`real/analysis.py`, `_contract_key_points`) transforme ces champs en `KeyPointDraft` avec des tags
dédiés (`"Durée"`, `"Reconduction"`, `"Résiliation"`, `"Pénalité"`, `"Partie"`, `"Montant"`) —
le même mécanisme déjà utilisé pour tout document générique (`DocumentKeyPoint`, audio générée
automatiquement par `explanation_builder.py`). Pas de nouvelle table, pas de nouveau schéma de
sortie.

**Limite assumée.** Les montants sont vérifiés par `_amount_in_text` (règle d'or n°4), mais les
champs texte libre (durée, résiliation, parties, pénalités) n'ont pas d'équivalent code pour
vérifier leur présence mot pour mot dans le texte source — seule la consigne du prompt (« reprends
ce qui est écrit, jamais une valeur déduite ») les protège. Documenté plutôt que caché, même
posture que la décision 15 pour le résumé général.

**Raison.** Un contrat n'a pas le même enjeu de sécurité qu'une posologie (règle d'or n°1) : pas de
double lecture dédiée à justifier pour ce premier jet, et réutiliser `key_points` évite une
nouvelle table, un nouveau schéma de sortie et un nouveau presenter pour une structure que l'app
mobile/web n'a pas encore demandé d'afficher différemment.

---

## 19. Extrait d'image par ligne : position approximative, jamais une boîte englobante

**Décision (7 octobre 2026).** Pour montrer à l'utilisateur où se trouve une ligne `to_check`/
`unreadable` sur la photo, le modèle de lecture rapporte seulement une position verticale
approximative du milieu de la ligne (`"line_position"`, 0 à 1, `READ_PRESCRIPTION`), jamais une
boîte englobante précise. `app/ai/real/pages.py` (`crop_band`) découpe une bande horizontale
pleine largeur autour de cette position (moyenne des deux lectures si les deux l'ont rapportée,
`real/prescription.py`, `_line_position_estimate`) sur l'image d'origine — pas celle
redimensionnée pour l'appel au modèle, puisque la position est normalisée (0-1), donc indépendante
de la résolution. Découpe faite uniquement pour une ligne non `sure` (pas besoin de vérifier
visuellement une ligne déjà confirmée) ; le résultat (`MedicationLine.image_extract`, bytes
transitoires) est stocké par `document_processor.py` (jamais par `app/ai/`, qui ne touche pas au
stockage) et seule la clé (`image_key`) est conservée en base.

**Raison.** Même leçon que les décisions 12 et 13 : le grounding spatial précis (coordonnées
pixel) est un point faible connu des modèles de vision généralistes non spécialisés en détection
d'objets, contrairement à une estimation grossière de position qu'ils rapportent de façon plus
fiable. Une bande large plutôt qu'un point précis absorbe l'imprécision de l'estimation.

---

## 20. Cohérence entre pages : un médicament incohérent sur deux pages n'est jamais `sure`

**Décision (7 octobre 2026).** `real/prescription.py` (`_flag_cross_page_mismatches`), appelée en
fin de `read_pages` une fois toutes les pages lues : si le même médicament (nom affiché après
lexique) apparaît sur deux pages différentes avec un champ renseigné des deux côtés et différent
(`strength`, `times_per_day`, `duration_days`, `timing` — l'absence d'un côté n'est pas un
désaccord), les deux lignes repassent à `to_check` (jamais rétrogradées si déjà `unreadable`) avec
`pharmacology_flags` complété par `"cross_page_mismatch"`. Les champs déjà masqués pour une ligne
`to_check` (`prescription_text.py`) le restent automatiquement.

**Raison.** Une reprise de photo dupliquée (même page photographiée deux fois avec un résultat de
lecture légèrement différent) ou une vraie incohérence sur l'ordonnance ne doivent jamais aboutir à
deux lignes `sure` contradictoires : règle d'or n°3 (l'incertitude est toujours visible), appliquée
ici à travers les pages plutôt qu'à travers les deux modèles d'une même page.

---

## 21. Lecture de contrat : avertissement juridique systématique, jamais de conseil de signature

**Décision (7 octobre 2026).** `ANALYZE_DOCUMENT` gagne `"vigilance_points"` dans le bloc
`"contract"`, avec une règle explicite dans le prompt : ne jamais dire de signer ou de ne pas
signer, ne donner aucun avis juridique, décrire seulement ce qui est écrit. `analysis.py`
(`_contract_key_points`) ajoute en **premier** point clé, de façon déterministe (texte fixe, pas
généré par le LLM, même principe que `CUT_OFF_WARNING`) : « Ceci n'est pas un avis juridique. Pour
toute décision, demande à un professionnel du droit. » (tag `"Avis"`). Les points de vigilance
suivent (tag `"Vigilance"`), vérifiés par `_is_grounded` comme les autres champs libres du contrat
(décision 18).

**Raison.** Un avertissement généré par le LLM pourrait être omis ou reformulé de façon à en
atténuer la portée ; un texte fixe garantit qu'il est systématiquement présent dès qu'un contrat
est détecté, cohérent avec la règle d'or n°5 (aucun avis juridique précis) et le principe déjà
appliqué à `CONTRACT_DISCLAIMER` : jamais de responsabilité déléguée à la qualité d'une génération.

---

## 22. Changement de traducteur principal : `anthropic/claude-sonnet-5.5`

**Décision (7 octobre 2026).** `TRANSLATOR_MODEL_PRIMARY` passe de `google/gemini-2.5-flash-lite`
à `anthropic/claude-sonnet-5.5` (`reasoning_effort=minimal` — ce modèle refuse `"none"`, même
incident déjà rencontré dans l'étude initiale et avec `meta/muse-glimmer-30b`). `gpt-5-mini`
inchangé en secours (toujours deux fournisseurs différents). Déclenché par des erreurs réelles sur
la facture de test (`api/samples/facture.jpg`), observées via `leeral try-document` et absentes de
l'échantillon FLORES-200 de `translation-study.md` : « 15 jours » traduit en « 15 at » (15
**années** en wolof) et « courant coupé » traduit en « sa lékk bi » (« ta nourriture », non-sens).
`claude-sonnet-5.5` corrige les deux sur reproduction directe, et obtenait déjà le meilleur chrF de
l'étude sur toutes les paires (décision 9, section 4) — simplement écarté à l'époque pour son coût
(28× `gemini-2.5-flash-lite`) et sa latence (3,8×), pas pour sa qualité.

**Deux défauts trouvés en testant ce changement, corrigés avant la bascule :**
1. Sur la phrase la plus longue, `claude-sonnet-5.5` a renvoyé un premier essai suivi
   littéralement du texte « Rewrite properly: » puis d'un second essai — les deux bouts partaient
   dans l'audio final, sans qu'aucun jeton protégé ne soit perdu pour le détecter. Même famille
   d'incident que la troncature de `gemini-3.1-pro-preview` (décision 9) : un modèle qui ne
   respecte pas « output only the translation » sur les textes longs. Corrigé par une consigne
   explicite ajoutée à `prompts.TRANSLATE` (interdiction de brouillon ou de commentaire sur sa
   propre réponse) et un garde-fou dans `Translator._translate_sentence`
   (`app/ai/real/translation.py`) : toute sortie contenant un retour à la ligne est traitée comme
   un échec et relance la boucle de secours, exactement comme un jeton manquant ou dupliqué.
2. Sans rapport avec le choix du modèle : la console Windows plantait (`UnicodeEncodeError`) sur
   la lettre « ŋ », absente du codepage par défaut — touchait `leeral try-document`/`check-ai`
   avec n'importe quel modèle produisant cette lettre. Corrigé dans `app/cli.py` (`sys.stdout`/
   `sys.stderr` reconfigurés en UTF-8 au démarrage de `main()`).

**Limite non résolue par ce changement.** La réserve de la décision 9 sur le pulaar reste entière
— `claude-sonnet-5.5` n'a pas été testé contre un corpus de pulaar sénégalais validé, seulement
contre le fulfulde du Nigéria (`translation-study.md`, section 2.2) et contre une seule facture en
wolof. Aucune relecture par un locuteur natif (wolof ou pulaar) n'a encore eu lieu sur ce
changement.

**Le sérère n'a pas de statut « non résolu » ici : il n'a simplement jamais été évalué, par aucun
traducteur, ancien ou nouveau.** `ensure_available()` (`app/core/languages.py`) empêche tout
compte utilisateur d'avoir `language=sr` tant qu'aucune voix KIRIKU n'existe pour cette langue
(décision 4) — `Translator.localize()` ne reçoit donc jamais le sérère en conditions réelles, et
`leeral try-document`/`check-ai` ne l'acceptent même pas en argument (`--language` limité à
`AVAILABLE_LANGUAGES`). `translation-study.md` n'a testé ni le sérère ni un proxy pour cette
langue (contrairement au pulaar avec le fulfulde du Nigéria) : aucune mesure chrF, aucune
comparaison de modèle n'existe sur le sérère, pour `claude-sonnet-5.5` comme pour
`gemini-2.5-flash-lite` avant lui. Le tableau de mois en sérère (décision 14) est une
extrapolation du schéma wolof/pulaar sans aucun mot confirmé par un locuteur, à la différence
d'« oktoobar » en wolof. Le jour où une voix TTS sérère sera disponible, le choix du traducteur
pour cette langue devra être étudié depuis zéro, pas supposé hérité de ce qui a été décidé ici
pour le wolof et le pulaar.

**Raison.** Le compromis coût/qualité de la décision 9 a été pris sur un échantillon générique
(FLORES-200) qui ne représente pas le vocabulaire administratif réel des documents Leeral — le
chrF le plus proche de Sonnet (`gpt-5-mini`, −5,2 points) n'empêchait pas des erreurs de sens
franches sur ce vocabulaire précis. Face à des utilisateurs qui n'ont que l'audio pour comprendre
un document, la qualité a été jugée prioritaire sur le facteur 28 en coût.

---

## 23. Catalogue fermé pour les moments de prise, mécanisme prêt mais vide

**Décision (7 octobre 2026).** `real/safety/posology_phrases.py` (`localize_posology_phrase`) :
même mécanisme que `safety/dates.py` pour les mois (décision 14) — substitution déterministe
d'une phrase connue puis protection du résultat avant traduction — appliqué cette fois aux
expressions de moment de prise (« avant le repas », « au coucher », « à jeun »...). Branché dans
`Translator.localize()` (`app/ai/real/translation.py`, `_protect_known_phrases`), à côté des
mois. Volontairement limité à des **expressions multi-mots spécifiques au contexte médical** —
jamais un connecteur isolé comme « pendant » ou « jours », trop génériques et ambigus pour être
substitués sans risque dans un document qui n'est pas une ordonnance (contrairement aux mois,
sans ambiguïté possible hors contexte).

**`TRANSLATED_TIMING` est livré vide** (`{Language.WOLOF: {}, Language.PULAAR: {}, Language.SERER:
{}}`), à la différence du tableau des mois (décision 14, rempli en DRAFT). Tant qu'une entrée n'y
est pas, `localize_posology_phrase` ne substitue rien : le comportement actuel (traduction par
`claude-sonnet-5.5`, décision 22) continue de s'appliquer, sans régression. Un seul changement de
comportement pour l'instant : le prompt de style (`ANALYZE_DOCUMENT`,
`PRESCRIPTION_SAFETY_RULES`) interdit désormais explicitement les expressions idiomatiques et le
jargon, pour faciliter la traduction en amont — indépendant du catalogue.

**Raison du choix (vide plutôt que DRAFT comme les mois).** Une consigne de moment de prise mal
traduite a un impact santé réel et direct si elle est fausse (« avant » devenu « après » le repas,
par exemple), contrairement au nom d'un mois où l'impact d'une erreur est une confusion de date.
Ma confiance dans une formulation wolof/pulaar/sérère que je rédigerais moi-même est plus faible
ici qu'pour les mois, et l'enjeu plus grave si cette confiance est mal placée — décision prise
avec l'utilisateur de ne pas répéter la posture DRAFT de la décision 14 à ce niveau de risque.
**Remplir `TRANSLATED_TIMING` nécessite une relecture par un locuteur natif et, idéalement, un
pharmacien avant tout usage en production** (même exigence que `pharmacology_rules.csv`,
`reviewed_by` vide, décision 7).

**Point 2 du même chantier (ancrer l'explication sur la notice officielle du médicament) : non
traité, hors de portée d'une session de code.** Construire une base de notices (RCP/BDPM) vérifiée
est un travail de sourcing de contenu médical structuré avec relecture professionnelle — exactement
ce que la décision 3 exclut déjà délibérément du lexique (« la responsabilité la plus lourde à
porter pour une petite équipe »). Fabriquer un substitut moi-même aurait produit du contenu qui
ressemble à une notice validée sans en être une, plus dangereux que de ne rien livrer.

---

## 24. Classification découplée de la double lecture, pour la latence

**Décision (8 octobre 2026).** `real/pages.py` (`PageReader`) utilisait jusqu'ici `reader_a`/
`reader_b` (décision 6 : `qwen/qwen3.8-27b` + `meta/muse-glimmer-30b`) à la fois pour classifier
le document (type + langue) **et** pour la double lecture d'ordonnance — deux rôles au niveau
d'enjeu très différent partageant le même coût. `muse-glimmer-30b` a un raisonnement obligatoire
non désactivable (décision 6), mesuré à environ 16 s par appel ; pour une ordonnance, ce coût
était payé deux fois de suite (classification, puis lecture), mesuré à ~72 s en moyenne sur
l'échantillon `eval/` (contre ~57 s pour un document générique, un seul passage).

Nouveau couple dédié à la classification, sans rapport avec les modèles de lecture :
`classifier_model_a` (`qwen/qwen3.8-27b`, inchangé) + `classifier_model_b`
(`google/gemini-2.5-flash-lite`, repris du traducteur — décision 9, déjà éprouvé dans ce pipeline,
jamais de raisonnement forcé observé). `reader_a`/`reader_b` restent inchangés pour la double
lecture d'ordonnance elle-même : **la règle d'or de sécurité n'est pas touchée**, seul le rôle de
classification change de modèles.

**Mesuré après coup** (`leeral try-document`, logs `ai_http_request_finished`) : classification
~3,7 s (contre ~16 s), lecture de prescription inchangée (~7 s, bornée par le même couple qu'avant
— la variance mesurée vient du réseau/de la charge du fournisseur, pas du changement). Une
ordonnance testée est passée de ~72 s à **11,3 s** pour `analyze_document` ; une facture
photographiée de ~57 s à **23 s**.

**Deuxième changement, même logique** : `PageReader.classify()` ne double plus la classification
pour une page dont le texte est déjà extrait (PDF/DOCX, `page.image is None`) — l'ambiguïté y est
structurellement plus faible qu'une photo (pas de flou, pas de cadrage), un seul modèle suffit.
Un seul appel au lieu de deux sur ce chemin.

**Effet de bord corrigé en même temps, sans rapport avec le modèle** : `PageReader.prepare()`
appelait `prepare_image` (redimensionnement/recompression PIL, CPU) de façon synchrone dans une
méthode `async`, bloquant la boucle d'événements pendant le calcul — incohérent avec le reste du
module, qui passe déjà ce genre d'appel par `asyncio.to_thread` (`check_image`, `build_pages`).
Sans effet sur la latence d'un document seul, mais affecte la capacité du serveur réel à traiter
plusieurs requêtes en même temps. Corrigé (`prepare`/`content` passés en `async`).

**Raison.** Le coût d'un modèle à raisonnement obligatoire n'a de sens que là où l'enjeu sécurité
le justifie (lecture de posologie) — le reproduire pour une simple classification de type de
document n'apportait rien, même logique que la décision 13 (coût proportionné à l'enjeu).

---

## 25. Synthèse vocale : `TTS_CONCURRENCY` relevé de 1 à 4

**Décision (8 octobre 2026).** `.env` avait `TTS_CONCURRENCY=1`, forçant `SpeechSynthesizer.speak`
(`real/speech.py`) à synthétiser les morceaux d'un texte découpé (> `tts_max_input_chars`, 500
caractères) **en séquence** malgré un code déjà écrit pour le faire en parallèle
(`asyncio.gather` + `Semaphore`) — KIRIKU autorise jusqu'à 15 requêtes concurrentes par clé.
Relevé à **4**.

**Mesuré** (texte répété, isolé de tout autre appel) :
- 3 morceaux (~1000 caractères) : 8,7 s (séquentiel) contre 8,4 s (parallèle) — **gain négligeable**.
- 5 morceaux (~2000 caractères) : **30,8 s (séquentiel) contre 6,3 s (parallèle)** — gain net
  d'environ 5×.

L'effet n'est donc significatif qu'à partir d'un nombre de morceaux suffisant (au moins 4-5, donc
un texte de plus de 1500 caractères environ — un résumé long avec plusieurs points clés, pas une
phrase courte). Sur un texte court, ne pas s'attendre à un gain visible : le changement est sans
risque dans tous les cas (aucune régression de qualité, le découpage par phrase est inchangé) mais
son bénéfice dépend de la longueur du texte à lire.

**Raison.** `TTS_CONCURRENCY=1` neutralisait un mécanisme de parallélisation déjà écrit et déjà
sûr, sans qu'aucune trace dans ce dépôt n'indique que ce `1` était un choix délibéré (quota,
incident de stabilité) plutôt qu'un réglage jamais revisité.

---

## 26. Ce qui n'a pas été transféré tel quel

Décisions du dépôt d'étude qui ne s'appliquent plus ici, pour mémoire (ne pas les réintroduire
par erreur en pensant combler un manque) :

- **Identité/session** (participant anonyme, rattachement WhatsApp, ARQ pour le regroupement
  d'images) : ce dépôt a son propre modèle, plus abouti (invité → compte par OTP, JWT, voir
  `api/README.md`). Les décisions correspondantes du dépôt d'étude ne sont pas reprises.
- **Enveloppe d'erreur et catalogue de codes** : ce dépôt a son propre catalogue
  (`app/core/errors.py`, `ErrorCode`), plus large (facturation, apprentissage, rédaction). Les
  codes IA (`AI_PROVIDER_UNAVAILABLE`, `AI_PROVIDER_AUTH`, `AI_OUTPUT_INVALID`,
  `TRANSLATION_FAILED`) sont les mêmes dans l'esprit, portés dans `app/ai/errors.py`.
- **Schéma de base de données détaillé du dépôt d'étude** : supersedé par le schéma réellement
  migré ici (30 tables, voir `api/README.md`), non repris — il décrivait une base différente,
  jamais migrée au-delà d'un sous-ensemble partiel dans le dépôt d'étude.

---

## 27. Noms propres (marques, institutions) jamais traduits

**Décision (10 octobre 2026).** Signalé par l'utilisateur en testant avec des documents réels :
le traducteur altère parfois des noms propres comme « Orange Money », « Wave » ou « Banque
Islamique du Sénégal » — ce sont les mêmes mots quelle que soit la langue, les traduire n'a aucun
sens et produit du charabia. Même catégorie de problème que les noms de médicaments (décision déjà
en place via `protected_terms`), étendue ici aux documents génériques (factures, courriers...).

**Deux parties, les deux demandées par l'utilisateur :**
1. **Catalogue statique** (`app/ai/real/safety/brand_names.py`, `KNOWN_BRAND_NAMES`) : marques et
   institutions sénégalaises courantes (argent mobile, télécom, énergie, eau, banques,
   administration) — non exhaustif par construction, complété par la partie 2.
2. **Extraction dynamique** : `ANALYZE_DOCUMENT` (`prompts.py`) renvoie désormais `proper_nouns`
   (noms d'organisme/marque/service tels qu'écrits dans le texte). `analysis.py::analyze_text`
   ne garde que ceux qui apparaissent **verbatim** dans le document (`_protected_terms`,
   grounding identique au reste du module — jamais un nom inventé par le modèle) et les fusionne
   avec les correspondances du catalogue statique dans `DocumentAnalysis.protected_terms`.

**Câblage jusqu'au bout de la chaîne**, qui n'existait pas pour les documents génériques avant
cette décision : `DocumentContext` (`app/ai/contracts.py`) gagne un champ stocké
`extra_protected_terms`, unifié avec les noms de médicaments dans la propriété `protected_terms` ;
`ai_mapping.document_context()` le relit depuis `document.extracted_data["protected_terms"]` (déjà
persisté par `document_processor.py`, simplement jamais relu jusqu'ici) ; `cli.py` (chemin
`try-document`, sans base de données) le branche directement depuis `DocumentAnalysis`. Tous les
appelants existants de `protected_terms` (`cli.py`, `explanation_builder.py`,
`question_answerer.py`) en bénéficient sans modification de leur côté.

**Vérifié** sur un document réel (`eval/documents/doc_02.jpg`, mentionne SONATEL) via
`leeral try-document --language wo --back-translate` : « Sonatel » traverse la traduction en
wolof et la traduction retour en français sans altération (`ai_http` : `protected_terms=3`).

**Raison.** Contrairement aux expressions de posologie (décision 23) ou aux mois (décision 14),
protéger un nom propre ne demande aucune traduction à rédiger — on ne décide jamais de ce qu'il
devient dans une autre langue, on décide seulement de le laisser identique. Le risque qui a
justifié la prudence des décisions 14/23 (une traduction erronée que j'aurais rédigée moi-même)
ne s'applique donc pas ici, le mécanisme peut être activé sans relecture préalable par un locuteur
natif.

---

## 28. Nombres > 10 écrits en toutes lettres avant la synthèse vocale, générés par un algorithme cité plutôt qu'un LLM

**Décision (10 octobre 2026).** Deuxième point signalé par l'utilisateur : les montants, prix et
âges sont souvent « confus » dans l'audio. Hypothèse testée et confirmée par comparaison d'audio
octet pour octet : KIRIKU (TTS wolof/pulaar) convertit correctement les nombres 0 à 10 en mots,
mais **supprime silencieusement** tout nombre au-dessus de 10 au lieu de le prononcer (`'Fey
francs.'` et `'Fey 500 francs.'` produisent le même audio, 19226 octets — le « 500 » disparaît
sans erreur ni avertissement).

**Première approche testée, puis corrigée en cours de route.** L'utilisateur a d'abord proposé de
demander à un LLM (Claude) d'écrire chaque nombre en toutes lettres, avec une vérification par
appel indépendant en sens inverse (donner les mots seuls, sans le nombre d'origine, et demander
quelle valeur ils représentent) — un nombre qui ne survit pas à cet aller-retour étant laissé en
chiffres plutôt que risqué faux à l'oral. Cette vérification a immédiatement montré son utilité
avec `qwen/qwen3.8-27b` (nombres wolof incohérents, rejetés sans exception) puis semblé fiable
avec `claude-sonnet-5.5`. **Un cas a cependant révélé une faille du mécanisme lui-même** :
`claude-sonnet-5.5` proposait correctement « fanweer » pour 30, mais l'appel de vérification en
sens inverse a répondu (à tort) que « fanweer » représentait 20 — l'utilisateur a confirmé, en
citant Guérin (2020, voir plus bas), que 30 était la bonne réponse. La vérification aller-retour
n'est donc pas un oracle fiable : un LLM qui se trompe dans un sens n'est pas forcément plus juste
dans l'autre, et un nombre correct peut être rejeté à tort (faux négatif) — le mécanisme restait
sûr par construction (jamais de nombre faux prononcé avec confiance) mais sa fiabilité réelle était
surestimée.

**Approche finale : un algorithme déterministe, construit à partir de sources citées, plutôt que
du LLM.** L'utilisateur a fourni deux sources fiables qui couvrent l'essentiel du besoin :
- **Wolof** : Guérin, Maximilien (2020), « Système de numération en wolof : description et
  comparaison avec les autres langues atlantiques », *Faits de langues* 51(2), 121-144 — article
  relu par les pairs, qui décrit le système comme décimal à pivot additif 5, **entièrement
  régulier à l'exception de 20 et 30** (les deux formes citées : « ñaar fukk »/« nit » pour 20,
  « fanweer »/« ñett fukk » pour 30 — « fanweer » confirmé comme la forme la plus employée au
  Sénégal).
- **Pulaar** : Sylla, Yèro (1982), *Grammaire moderne du pulaar*, Les Nouvelles Éditions
  Africaines (Dakar) — citée dans l'article ci-dessus, structure identique mais sans irrégularité
  signalée. Un site grand public (languagesandnumbers.com) décrit une structure identique mais
  avec des mots différents pour 10/20/1000 (`nogay`, `wuluure`) — sa page précise que ce dialecte
  est le « pular fuuta » de l'ancien imamat du Fouta-Djalon, c'est-à-dire la Guinée, pas le
  pulaar sénégalais visé ici : écarté comme source pour cette raison précise, pas par principe.

`app/ai/real/safety/wolof_numerals.py` et `pulaar_numerals.py` implémentent chacun un générateur
déterministe (`spell_number(n) -> str | None`), **chacun reproduit exactement tous les exemples
travaillés donnés par sa source** (wolof : 11, 17, 19, 20, 30, 90, 100, 119, 426, 600, 1000, 4000,
9112 ; pulaar : 1245) — vérifié par test avant intégration.

**Recalibré le jour même** après remarque de l'utilisateur : les documents réels ont plus souvent
des montants élevés (loyer, facture, salaire) que des petits — se limiter à 0-9999 aurait laissé
la majorité des montants réalistes hors de portée de l'algorithme. Étendu à un multiplicateur de
dizaines/centaines devant « téeméer »/« junni » (ex. « ñaar fukk ak juróom-i junni » = 25 000),
même principe que la construction attestée, juste généralisé à un multiplicateur à plusieurs
chiffres. **Plafond différent entre les deux langues, pour une raison technique précise, pas
juste par prudence** :
- **Wolof : 0-99 999.** Un multiplicateur à 3 chiffres (ex. 500 pour 500 000) demanderait sa
  propre construction génitive interne (500 = « juróom-i téeméer »), puis une *deuxième* marque
  génitive par-dessus pour en faire un multiplicateur de « junni » — une double imbrication sans
  aucun appui textuel, même par extrapolation (contrairement au multiplicateur à 2 chiffres, qui
  ne s'imbrique jamais puisqu'il reste sous le seuil des centaines). Un bug exactement de cette
  nature (double trait d'union, incohérent) a été détecté par les tests avant d'être exclu par ce
  plafond plutôt que corrigé à l'aveugle.
- **Pulaar : 0-999 999.** Pas de risque d'imbrication ici : la construction pulaar juxtapose
  simplement la forme plurielle du mot de base et le multiplicateur écrit tel quel (pas de
  suffixe génitif à accrocher), donc un multiplicateur à 3 chiffres (« ujunnaaje teemedde joy » =
  500 000) ne pose pas le même problème.

**Le mécanisme LLM+vérification de la première approche est conservé, mais rétrogradé en
secours** (`app/ai/real/numerals.py`, `spell_out_numbers`) : pour chaque nombre trouvé, l'algorithme
déterministe est essayé en premier (gratuit, instantané, aucun appel réseau) ; seuls les nombres
hors de sa plage couverte (≥ 100 000 en wolof, ≥ 1 000 000 en pulaar) passent encore par le LLM
`claude-sonnet-5.5` avec vérification aller-retour (décision conservée malgré la faille découverte
: un faux négatif reste plus sûr qu'un faux positif, et c'est toujours mieux que rien pour ces
plages hors de portée de l'algorithme). Branché dans `RealAiEngine.speak()`
(`app/ai/real/engine.py`), donc appliqué partout où `speak()` est déjà appelé, sans changement
dans les appelants. Mesuré sur des textes de facture/loyer réalistes (`leeral`, script ad hoc) :
45 000, 99 999, 2 500 passent en 0,00 s (aucun appel réseau) ; 150 000 et 300 000 (hors plage
wolof) passent par le secours LLM, qui a accepté 300 000 et rejeté 150 000 lors du même test —
confirme que le secours reste imparfait sur cette plage, comme attendu, sans régression.

**Point technique rencontré et corrigé en cours de route (toujours valable pour le secours LLM)** :
à `reasoning_effort="minimal"`, `claude-sonnet-5.5` « réfléchit à voix haute » avant de répondre
au lieu de répondre directement en JSON, et dépassait le budget de tokens avant d'arriver au JSON
final (`AiOutputError`). Corrigé par une consigne explicite dans
`prompts.NUMBER_TO_WORDS`/`WORDS_TO_NUMBER` (même famille que la consigne anti-brouillon de
`TRANSLATE`, décision 22) et un budget de tokens nettement plus large.

**Limite connue, acceptée plutôt que corrigée ici.** Au-delà du plafond de chaque langue (100 000
en wolof, 1 000 000 en pulaar), tous les nombres ne sont pas convertis (le secours LLM rejette une
partie des propositions) — ceux-ci restent en chiffres, donc toujours supprimés par KIRIKU à
l'oral, comme avant cette décision. Le pulaar n'a, de plus, pas été vérifié aussi exhaustivement
que le wolof : l'article source ne lui consacre qu'une section courte et ne signale aucune
irrégularité, ce qui peut aussi vouloir dire qu'aucune n'a été cherchée pour ce système précis —
traiter comme moins éprouvé que le wolof, pas comme équivalent.

**Hors de portée de cette décision** : les suites de chiffres qui ne sont pas des quantités
(numéros de téléphone, numéros de série) peuvent être repérées par la même expression régulière et
« corrigées » en nombre cardinal à tort (un numéro de téléphone n'est pas un montant) — comportement
non pire qu'avant (ces chiffres étaient déjà supprimés par KIRIKU au-delà de 10) mais non résolu
par ce chantier, qui visait spécifiquement les montants et les âges signalés par l'utilisateur.

**Raison.** La première approche (décision initiale de ce point) supposait qu'un LLM serait plus
fiable qu'un tableau construit à la main pour un système agglutinant (fukk=10, teemeer=100,
junni=1000, composés par « ak »/« e ») — l'incident « fanweer » a montré que ce n'était vrai ni
dans un sens ni dans l'autre sans source fiable pour trancher. Une fois des sources citées,
vérifiables et relues par les pairs en main, un algorithme déterministe devient strictement
supérieur à une génération par LLM sur ce point précis : aucun risque d'erreur du modèle, aucun
coût, aucune latence, et une correction vérifiable (les exemples de la source) plutôt qu'une
vérification elle-même faillible.

---

## 29. Wolof étendu jusqu'à 9 999 999 (palier du million), grâce à un exemple trouvé par recherche web

**Décision (10 octobre 2026), même jour.** L'utilisateur a fait remarquer que les documents réels
ont plus souvent des montants élevés (loyer, facture, prêt, achat) que des petits — le plafond de
99 999 de la décision 28 aurait laissé la majorité des montants plausibles hors de portée de
l'algorithme. Demande explicite : chercher, par recherche web, de quoi couvrir le palier du
million, pour pouvoir ensuite composer jusqu'à 9 millions facilement.

**Recherche effectuée.** `languagesandnumbers.com` (déjà utilisé pour le pulaar, décision 28) n'a
pas de page wolof (vérifié directement : sa carte du site ne mentionne pas le wolof). Une
recherche plus large a trouvé la page de vocabulaire « 200 Words » du wolof par l'Université de
Boston (bu.edu/200word/wolof/numbers) — pas une source relue par les pairs, mais la seule trouvée
donnant un exemple réel au-delà de 10 000 : **« Fukki Téémééri Junni / Benn Milyoŋ »** pour un
million, soit deux formes valides : la forme composée native « fukk-i téeméer-i junni »
(littéralement 10 × 100 × 1000) et la forme empruntée au français « benn milyoŋ » (« un million »,
multiplicateur toujours explicite, contrairement à téeméer/junni qui l'omettent pour 1).

**Ce que cet exemple a corrigé.** En décomposant « fukk-i téeméer-i junni », la règle du suffixe
génitif « -i » (`_genitive` dans `wolof_numerals.py`) s'est révélée plus simple et plus générale
que ce que la décision 28 avait supposé : le suffixe s'attache **toujours seulement au dernier mot
de la phrase multiplicatrice**, y compris quand cette phrase porte déjà son propre « -i » issu d'un
niveau de construction précédent (ici : fukk-i d'abord, puis téeméer reçoit aussi -i en devenant à
son tour multiplicateur de junni) — seule exception, toujours attestée telle quelle : le composé
additif à deux mots juróom+unité (6 à 9), entièrement fusionné par des traits d'union
(juróom-benn-i). La décision 28 plafonnait à 99 999 précisément parce qu'elle n'avait pas cette
règle et produisait un double trait d'union incohérent au-delà — **ce plafond est levé**, la
nouvelle règle gère correctement n'importe quelle profondeur d'imbrication (vérifié par un balayage
automatique de 1 à 9 999 999 sans artefact).

**Portée : wolof seulement.** Une recherche équivalente pour le mot « million » en pulaar
sénégalais n'a rien donné de fiable — seule trouvaille : le fulfulde du Nigéria (`dubuure`/
`dubuuje`, source `languagesandnumbers.com`), un dialecte déjà écarté comme référence pour le
pulaar dans la décision 28 pour une raison similaire (mauvais pays). Pas de mot extrapolé sans
source : le pulaar reste plafonné à 999 999 (décision 28, inchangé), le secours LLM prenant le
relais au-delà comme avant.

**`app/ai/real/safety/wolof_numerals.py` couvre maintenant 0-9 999 999** (un chiffre de millions,
1 à 9, plus un reste 0-999 999 composé avec « ak »). Vérifié : tous les exemples travaillés des
deux sources (décision 28 + le nouvel exemple du million) reproduits exactement, plus des montants
réalistes testés en conditions réelles via `ai.speak()` (achat à 2 500 000, caution à 500 000,
prêt à 9 000 000) — tous résolus en 0,00 s, aucun appel réseau.

**Raison.** Le plafond de la décision 28 n'était pas une limite de confiance générale mais la
conséquence directe d'un seul point technique non résolu (l'imbrication du suffixe génitif) — une
fois ce point réglé par un exemple concret, rien ne justifiait de garder les montants de 100 000
à 9 999 999 sur le mécanisme de secours, moins fiable, alors que la majorité des montants réels
signalés par l'utilisateur se trouvent précisément dans cette plage.

## 30. Mots courts lus dans une phrase porteuse, avec des silences autour de la voix

**Constat.** Dans « Apprendre », les mots très courts (« oui », « non », « lait »…) sortaient de
KIRIKU coupés ou incompréhensibles : pour un mot seul, le TTS ne produisait qu'environ 0,1 s de
parole, la première syllabe étant souvent avalée. Répéter le mot deux fois donnait environ 1 s de
parole audible, mais l'écoute paraissait bizarre.

**Décision.**
- Le sens de chaque mot est lu dans une phrase porteuse : « Baat bi mooy : … » en wolof,
  « Konngol ngol ko : … » en pulaar (`spoken_meaning` dans `app/services/vocabulary_builder.py`).
  Le mot est ainsi prononcé en entier, environ 0,7 s de parole, sans répétition.
- Chaque morceau envoyé au TTS se termine par un point (`_with_final_stop`), pour que la voix
  descende en fin de phrase au lieu de couper net.
- `speak` ajoute 0,2 s de silence avant la voix et 0,4 s après (`LEAD_SILENCE_S`, `TAIL_SILENCE_S`
  dans `speech.py`), pour que le lecteur du téléphone ne mange pas le début ni la fin.

**Mise à jour des audios existants.** `leeral revoice-words` régénère l'audio de tous les mots déjà
en base avec ces règles.

**Raison.** Le problème venait de la longueur du texte envoyé au TTS, pas du mot lui-même : une
phrase courte et fixe autour du mot règle tous les cas sans traitement mot par mot.
