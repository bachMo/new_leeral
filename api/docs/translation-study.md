# Étude de traduction fr/en ↔ wolof/pulaar

> Transférée depuis le dépôt d'étude initial (`leeral-project`), adaptée aux chemins de ce
> dépôt. Répond à la question : existe-t-il une traduction wolof/pulaar ↔ français/anglais
> exploitable sur OpenRouter, et avec quel modèle ? Les décisions prises ici sont implémentées
> dans `app/ai/real/translation.py` et configurées par `AiSettings.translator_model_primary/
> fallback` — voir `AI_DECISIONS.md` pour le journal de décision complet.
> Code : [`../../eval/translate_bench.py`](../../eval/translate_bench.py) · Données :
> [`../../eval/translations/`](../../eval/translations/) · Résultats bruts :
> [`../../eval/results/translation_study1/`](../../eval/results/translation_study1/)

---

## 1. Contexte et question posée

Leeral traduit dans les deux sens entre sa langue pivot (français, tout le raisonnement de
`app/ai/` se fait en français — voir `AI_MODULE.md`) et ses deux langues cibles (wolof, pulaar) :
dans un sens pour l'explication audio (`AiEngine.localize`), dans l'autre pour le dialogue vocal
libre (`AiEngine.to_french`). Aucun traducteur spécialisé wolof/pulaar n'étant disponible sur
OpenRouter, cette étude compare des **modèles de langue généralistes** utilisés comme
traducteurs, en mesurant ce qui compte pour une décision de production : **qualité, coût,
vitesse**, pour chacune des 4 paires de langues et dans les deux sens.

**Déclencheur** : Claude Sonnet était déjà utilisé pour de la traduction wolof/français dans un
autre contexte, avec un résultat jugé satisfaisant en pratique. L'objectif de cette étude était
de trouver un équivalent moins cher. Gemini a été cité comme piste à vérifier.

---

## 2. Méthode

### 2.1 Données

[**FLORES-200**](https://github.com/facebookresearch/flores/blob/main/flores200/README.md)
(Meta/NLLB Team, licence CC-BY-SA-4.0), téléchargé directement depuis l'hébergement public de
Meta (`dl.fbaipublicfiles.com/nllb/flores200_dataset.tar.gz`, pas de compte nécessaire — les
miroirs HuggingFace du jeu de données sont, eux, protégés par connexion).

**20 phrases** du split `devtest` tirées aléatoirement (graine fixe `20261005`, reproductible),
alignées entre français (`fra_Latn`), anglais (`eng_Latn`), wolof (`wol_Latn`) et la colonne
notée `ff` (`fuv_Latn`, voir limite ci-dessous). Fichier : `eval/translations/sample_20.json`.

> Échantillon volontairement réduit de 50 à 20 phrases en cours d'étude pour respecter un budget
> de test de 3 $ au total.

### 2.2 Limite majeure à garder en tête : le pulaar sénégalais n'est pas testé directement

**FLORES-200 n'a pas de code dédié pour le pulaar du Sénégal (Fouta Toro).** La seule variété
fula/fulfulde du jeu de données est `fuv_Latn`, le **fulfulde du Nigéria** — une langue proche
mais distincte (vocabulaire, orthographe, usages régionaux différents). Faute d'un corpus
parallèle ouvert et accessible sans compte pour le pulaar sénégalais, cette étude utilise
`fuv_Latn` comme **meilleur proxy disponible**. Les scores notés « ff » mesurent donc une
capacité de traduction en fulfulde/peul en général, **pas spécifiquement le pulaar du Sénégal**.
Les chiffres sur wolof (`wol_Latn`) n'ont pas cette réserve : c'est la bonne langue.

**Conséquence pratique : ne pas trancher sur le pulaar à partir de cette étude seule.** Avant
toute décision de production sur cette langue, faire relire un échantillon de sorties par un
locuteur natif du pulaar sénégalais.

### 2.3 Sens testés

Les 8 sens utiles au produit : `fr→wo`, `wo→fr`, `fr→ff`, `ff→fr`, `en→wo`, `wo→en`, `en→ff`, `ff→en`.

### 2.4 Modèles comparés

Choisis sur le catalogue réel d'OpenRouter (prix vérifiés le 5 octobre 2026, pas supposés) pour
couvrir un éventail de fournisseurs et de prix, plus Claude Sonnet comme référence connue :

| Modèle | Rôle dans l'étude |
|---|---|
| `anthropic/claude-sonnet-5.5` | **Référence connue** (déjà utilisé avec succès ailleurs pour le wolof) |
| `google/gemini-3.1-pro-preview` | Piste Gemini haut de gamme à vérifier |
| `google/gemini-2.5-flash-lite` | Gemini économique |
| `openai/gpt-5-mini` | Alternative OpenAI, milieu de gamme |
| `anthropic/claude-haiku-4.5` | Alternative Anthropic économique |
| `qwen/qwen3.8-27b` | Déjà éprouvé dans ce projet (lecture d'ordonnances, `eval/read_bench.py`) |

### 2.5 Mesure de qualité : chrF

**chrF** (Popović 2015, F-score de n-grammes de caractères 1 à 6, bêta=2), implémenté en
bibliothèque standard dans `translate_bench.py`. Choisi plutôt que BLEU parce qu'il ne dépend
d'aucun tokeniseur de mots — inexistant et peu fiable pour le wolof et le pulaar — et parce que
c'est la mesure utilisée par l'équipe NLLB elle-même pour évaluer FLORES-200.

**Limite de la mesure** : chrF compare à une **seule** traduction de référence. Une traduction
tout à fait correcte mais formulée différemment (paraphrase, synonyme, ordre des mots) est
pénalisée comme si elle était fausse. **chrF est fiable pour classer les modèles entre eux sur le
même jeu de phrases, beaucoup moins comme seuil absolu de « bonne » ou « mauvaise » traduction.**
C'est pour cette raison que Claude Sonnet sert de point de repère : son niveau de chrF sur cet
échantillon indique ce qu'un système **déjà jugé satisfaisant en production** obtient avec cette
mesure, ce qui recalibre la lecture des autres scores.

---

## 3. Incident méthodologique rencontré (et corrigé)

Deux modèles (`google/gemini-3.1-pro-preview`, `anthropic/claude-sonnet-5.5`) renvoient une
erreur `400 "Reasoning is mandatory for this endpoint and cannot be disabled."` quand on demande
`reasoning.effort = "none"` — même cas déjà rencontré avec `meta/muse-glimmer-30b` dans
`eval/read_bench.py`. Corrigé avec `--reasoning-effort minimal`.

Plus sérieux : avec un budget de réponse (`MAX_TOKENS`) fixé à 400, `google/gemini-3.1-pro-preview`
consommait la quasi-totalité du budget en raisonnement caché (**396 tokens sur 400**, vérifié sur
plusieurs phrases) avant de produire sa réponse, qui se retrouvait **coupée après quelques mots**
sans qu'aucune erreur ne soit renvoyée. Le premier passage sur ce modèle (chrF ≈ 19, le plus bas
de tous) était donc un artefact de troncature, pas une vraie mesure de qualité — et a coûté
**0,78 $** pour rien. Corrigé en portant `MAX_TOKENS` à 1500 et en suivant désormais
`reasoning_tokens` dans chaque enregistrement (colonnes « Tronqués » et « Raisonnement (tokens) »
du rapport, avec avertissement automatique si une troncature est détectée). Ce run a été refait,
cette fois correctement.

**Le budget de 0,80 $ fixé pour ce second passage a été atteint avant la fin** (97 appels sur
160) : les chiffres de `google/gemini-3.1-pro-preview` dans cette étude portent sur un échantillon
partiel (entre 12 et 13 phrases par sens au lieu de 20), à prendre comme tendance seulement.

---

## 4. Résultats

### 4.1 chrF moyen par modèle, toutes paires et tous sens confondus

| Modèle | chrF moyen | Coût pour 1000 traductions | Latence moyenne |
|---|---|---|---|
| `google/gemini-3.1-pro-preview` | 39,4 *(échantillon partiel, 100/160)* | **8,08 $** | 7,1 s |
| `anthropic/claude-sonnet-5.5` | 35,1 | 1,40 $ | 3,8 s |
| `openai/gpt-5-mini` | 29,9 | 0,16 $ | 1,5 s |
| `google/gemini-2.5-flash-lite` | 29,1 | **0,05 $** | **1,0 s** |
| `anthropic/claude-haiku-4.5` | 27,7 | 0,45 $ | 2,1 s |
| `qwen/qwen3.8-27b` | 27,6 | 0,24 $ | 3,2 s (fournisseur non figé, voir 5.3) |

### 4.2 Détail par paire de langues (chrF, moyenne des deux sens)

| Paire | `gemini-3.1-pro`* | `sonnet-5.5` | `gpt-5-mini` | `gemini-2.5-flash-lite` | `haiku-4.5` | `qwen3.8-27b` |
|---|---|---|---|---|---|---|
| fr↔wo | 42,0 | 39,9 | 31,9 | 32,4 | 28,5 | 31,5 |
| fr↔ff | 31,7 | 29,5 | 26,7 | 24,9 | 24,8 | 22,6 |
| en↔wo | 47,8 | 41,7 | 33,1 | 32,0 | 31,2 | 32,7 |
| en↔ff | 36,3 | 29,6 | 27,8 | 27,0 | 26,4 | 23,4 |

\* échantillon partiel (voir section 3). Détail complet (par sens, latences, tokens) dans
`eval/results/translation_study1/report.md`.

### 4.3 Coût réel de cette étude

**1,96 $ dépensés sur 3 $ de budget**, dont **0,78 $ perdus** sur l'incident de troncature de la
section 3 (argent réellement débité chez OpenRouter avant la correction, même si les réponses
invalides ont été supprimées du cache local). Coût utile : 1,18 $.

---

## 5. Ce que ça dit

### 5.1 Sonnet n'est pas hors de portée, mais rien ne l'égale complètement sur cet échantillon

Sur chaque paire de langues, `claude-sonnet-5.5` obtient un chrF supérieur aux quatre modèles
« bon marché » — l'écart varie fortement selon la paire : jusqu'à +8,6 points sur en↔wo, mais
moins de +2 points sur fr↔ff et en↔ff (voir tableau 4.2). Avec la mesure chrF qui pénalise les
paraphrases correctes (voir 2.5), cet écart est probablement **surestimé** : une partie de ce que
chrF compte comme des erreurs sur les modèles moins chers est sans doute de la reformulation
acceptable, pas une vraie contresens. Une relecture humaine d'un petit échantillon serait
nécessaire pour trancher précisément combien de cet écart est réel.

### 5.2 Gemini (la piste suggérée) : pas l'équivalent moins cher recherché

`google/gemini-3.1-pro-preview` obtient le meilleur chrF (mais sur un échantillon partiel, à
confirmer), **pour 8,08 $ les 1000 traductions — presque 6 fois plus cher que Sonnet**, avec une
latence de 7 secondes par appel (raisonnement caché important, voir section 3). Ce n'est donc pas
la piste à suivre pour réduire les coûts : c'est le modèle le plus cher et le plus lent de toute
l'étude. `google/gemini-2.5-flash-lite`, en revanche, est le **moins cher de tous** (0,05 $/1000,
28 fois moins cher que Sonnet) pour une qualité très proche de `gpt-5-mini`.

### 5.3 Meilleur compromis identifié : `openai/gpt-5-mini`

**chrF à seulement 5,2 points de Sonnet en moyenne, pour un coût environ 9 fois inférieur**
(0,16 $ contre 1,40 $ les 1000 traductions) et une latence 2,5 fois plus courte. C'est le
candidat le plus solide pour un équivalent moins cher de Sonnet sur cette tâche, à confirmer par
une relecture humaine avant bascule en production.

`google/gemini-2.5-flash-lite` est une alternative encore moins chère (28× moins cher que Sonnet)
pour une qualité quasi identique à `gpt-5-mini` sur cet échantillon — à tester en premier si le
budget est la contrainte dominante.

`qwen/qwen3.8-27b` n'a pas été testé avec un fournisseur OpenRouter figé (`--provider`) : ses 160
appels ont été servis par 17 fournisseurs différents (DeepInfra, Reka, Cerebras, Venice...),
chacun pouvant quantifier le modèle différemment. Son chrF agrégé (27,6) est donc plus bruité que
les autres lignes du tableau — à refaire avec un fournisseur figé avant de l'exclure ou le retenir.

### 5.4 Limites de cette étude (à ne pas perdre de vue)

1. **20 phrases par sens** donne une tendance, pas une garantie statistique. La version
   initialement prévue (50 phrases) a été réduite pour tenir le budget.
2. **Le pulaar n'est pas directement testé** (section 2.2) : fulfulde du Nigéria utilisé comme
   proxy.
3. **chrF à une seule référence** pénalise les paraphrases correctes (section 2.5) : les écarts
   de qualité ci-dessus sont une base de discussion, pas un verdict final.
4. **Un seul lancement par phrase** (`--runs 1`) : la stabilité d'un modèle d'un appel à l'autre
   n'a pas été mesurée (contrairement à `read_bench.py` qui fait 3 lancements pour l'OCR).
5. `google/gemini-3.1-pro-preview` : échantillon partiel (97/160 appels, budget atteint).

---

## 6. Recommandation

1. **Ne pas retenir `gemini-3.1-pro-preview`** comme piste d'économie : c'est le plus cher des
   six modèles testés (malgré le meilleur chrF).
2. **Décision retenue et configurée** (voir `AI_DECISIONS.md`) : `google/gemini-2.5-flash-lite`
   comme modèle **principal** (qualité statistiquement égale à `gpt-5-mini` sur cet échantillon,
   29,1 vs 29,9 chrF — écart dans le bruit sur 20 phrases — mais 3× moins cher et plus rapide),
   `openai/gpt-5-mini` en **repli** (`app/ai/real/translation.py`, bascule automatique uniquement
   sur panne fournisseur, pas sur simple différence de qualité). Deux fournisseurs différents
   (Google, OpenAI) pour ne pas dépendre d'un seul en cas de panne ou de changement de prix. Une
   relecture par un locuteur natif sur un échantillon reste recommandée avant toute bascule de
   production à plus grande échelle.
3. **Avant toute décision définitive sur le pulaar** : obtenir ou constituer un petit corpus de
   référence en pulaar sénégalais (le fulfulde du Nigéria ne suffit pas), par exemple avec l'aide
   d'un locuteur natif.
4. Les résultats en→* sont systématiquement meilleurs que fr→* sur cet échantillon pour toutes
   les paires, un signal (faible, à l'échelle de 20 phrases) en faveur d'un pivot anglais plutôt
   que français si jamais le pivot devait être figé différemment — à vérifier sur un échantillon
   plus large avant d'en faire une décision.

---

## 7. Reproduire ou étendre cette étude

```bash
cd eval
python -m venv .venv && .venv/Scripts/activate
pip install ruff mypy pytest
ruff format --check . && ruff check . && mypy --strict . && pytest
export OPENROUTER_API_KEY=...   # jamais dans un fichier ; PowerShell : $env:OPENROUTER_API_KEY="..."
python translate_bench.py --data translations/sample_20.json --out results/translation_essai2 \
    --models openai/gpt-5-mini google/gemini-2.5-flash-lite --max-cost 1.0
```

`--dry-run` compte les appels (et donc une estimation de coût) sans rien dépenser. Relancer avec
la liste complète de `--models` régénère un rapport fusionné à partir du cache, sans nouveau coût
pour ce qui est déjà réussi (voir docstring de `translate_bench.py`).

---

## 8. Service de traduction construit

Le choix ci-dessus est implémenté dans `app/ai/real/` :

- `real/translation.py` (`Translator`) : traduit phrase par phrase, un essai sur le modèle
  principal puis sur le modèle de secours en cas d'échec fournisseur, et renvoie un avertissement
  traduit (jamais le français brut) pour toute phrase qui échoue encore après la relance — voir
  `UNTRANSLATED_NOTICE_FR`.
- `real/safety/protected_tokens.py` : protège les noms de médicaments et les nombres par des
  jetons `⟦N⟧` avant traduction, en un seul passage (repasser sur un texte déjà protégé ferait
  re-matcher le chiffre interne à un jeton déjà posé). Vérifie que chaque jeton revient exactement
  une fois avant de le restituer ; sinon, nouvelle tentative, puis échec contrôlé de la phrase.
- `real/clients/openrouter.py` : le prompt (`real/prompts.py`, `TRANSLATE`) instruit explicitement
  le modèle de préserver tout jeton caractère pour caractère — sans cette instruction, le modèle
  essaie de les « traduire » et les perd (vérifié contre la vraie API dans le dépôt d'étude).
- Exposé par `AiEngine.localize()` (français → langue cible) et `AiEngine.to_french()` (langue
  cible → français), consommés par les services qui orchestrent l'explication d'un document et le
  dialogue vocal (voir `AI_MODULE.md`).

Tests : `tests/ai/test_protected_tokens.py`, `tests/ai/test_real_engine.py`.
