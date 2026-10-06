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

## 13. Ce qui n'a pas été transféré tel quel

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
