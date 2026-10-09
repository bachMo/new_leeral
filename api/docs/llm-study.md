# Choix du LLM d'explication et de dialogue

> Transférée depuis le dépôt d'étude initial (`leeral-project`), adaptée aux chemins de ce
> dépôt. Décision pour `app/ai/real/reasoning.py` (`Reasoner`, utilisé par `analysis.py`,
> `dialogue.py`, `writing.py`, `vocabulary.py`). Contrairement au Reader (lecture d'ordonnances,
> voir `AI_DECISIONS.md`) et au Translator (`translation-study.md`), ce choix n'a **pas** fait
> l'objet d'un banc d'essai chiffré par Leeral lui-même : il s'appuie sur une revue de benchmarks
> publics de contexte long (RULER, NIAH-2, MRCR v2), complétée par une comparaison de prix sur le
> catalogue réel d'OpenRouter.

---

## 1. Le problème posé

Le LLM d'explication/dialogue doit assembler une réponse à partir du texte lu d'un document,
**sans jamais rien inventer** — voir le contrôle de cohérence numérique (`dialogue.py`,
`numbers_are_grounded`) et de date/montant (`analysis.py`, `_date_in_text`/`_amount_in_text`), qui
appliquent déjà cette règle en code, pas seulement en consigne de prompt. Deux besoins
additionnels sont apparus en discussion :

1. **Ne rien oublier** : un document long (plusieurs dizaines de pages, un contrat par exemple)
   doit être couvert sans qu'un élément noyé dans beaucoup de texte ne soit silencieusement
   ignoré.
2. **Le prix** : ce fournisseur est appelé beaucoup plus souvent que le Reader (une fois par
   document pour l'analyse, puis à chaque tour de dialogue, à chaque mot de vocabulaire, à
   chaque champ d'un document rédigé), et potentiellement sur des contextes beaucoup plus gros
   pour un document long.

## 2. Ce que disent les benchmarks publics (contexte long)

Recherche faite le 5 octobre 2026 sur des classements de contexte long récents (RULER, NIAH-2 —
needle-in-a-haystack à plusieurs éléments, MRCR v2). Ces tests mesurent précisément le risque qui
inquiète pour un document long : retrouver **plusieurs** informations disséminées dans beaucoup
de texte, pas une seule.

| Test | Modèle (famille proche d'un candidat) | Score |
|---|---|---|
| NIAH-2 multi-aiguilles @ 1M tokens | Gemini 3 (Deep Think / 3.1 Pro) | **89 %** |
| NIAH-2 multi-aiguilles @ 1M tokens | Claude Opus 4.6/4.7 | 56 % |
| NIAH-2 multi-aiguilles @ 1M tokens | GPT-5.5 | 74 % |
| MRCR v2 8 aiguilles @ 128K | Claude Opus 4.6 | 93,0 % |
| MRCR v2 8 aiguilles @ 128K | Claude Sonnet 4.6 | 84,9 % |
| MRCR v2 8 aiguilles @ 128K | Gemini 3.1 Pro | 84,9 % |
| MRCR v2 8 aiguilles @ 128K | GPT-5.5 | 74,0 % |
| MRCR v2 8 aiguilles @ 128K | **Gemini 3.1 Flash Lite** | **60,1 %** |
| RULER @ 256K | Gemini 3 Deep Think | 84 % |
| RULER @ 256K | GPT-5.5 | 72 % |
| Classement composite long-contexte (BenchLM, sept. 2026) | GPT-5.5 | 85,3 |
| Classement composite long-contexte (BenchLM, sept. 2026) | **Qwen3.8 Max** | 79,6 |

**Le chiffre le plus directement utile** : sur le même test (MRCR v2, multi-éléments), la version
*Flash Lite* de Gemini 3.1 tombe à 60,1 % contre 84,9 % pour la version Pro de la même famille —
un écart de 25 points entre petit et gros modèle d'une même famille. C'est la confirmation
chiffrée que les petits modèles ("mini", "flash-lite", "haiku") oublient réellement plus sur du
contexte long et multi-éléments : ce n'est pas qu'une impression.

**Sur Qwen** : aucune donnée publique trouvée pour `qwen3.8-27b` spécifiquement (le modèle déjà
utilisé dans ce projet pour le Reader). Seul `Qwen3.8 Max` (le gros modèle de la famille) a un
score public, 79,6 — correct mais en retrait derrière GPT-5.5. Si le petit "27b" suit le même
écart que Gemini Flash Lite vs Pro, il est probablement **nettement plus faible** sur ce point
précis. Conséquence directe : `qwen3.8-27b` n'a pas été retenu comme modèle unique pour les
documents longs.

### Nuance importante

Ces tests stressent des contextes de 128K à 1M tokens. Un document Leeral typique (texte extrait
d'une ordonnance ou d'une facture, quelques échanges récents) fait probablement quelques milliers
de tokens, pas 100K+. D'après une des sources consultées, la plupart des modèles — petits compris
— restent proches de la saturation (96-99 %) jusqu'à environ 200K tokens sur un test à **une
seule** information recherchée ; l'écart se creuse surtout sur la recherche **multi-éléments**,
qui est le cas réel d'un document de plusieurs dizaines de pages avec plusieurs clauses ou
médicaments à restituer tous correctement.

**Limite à ne pas oublier** : ces chiffres portent sur des familles de modèles proches, pas
toujours la chaîne de modèle exacte disponible sur OpenRouter (`gemini-3.1-pro-preview`,
`qwen/qwen3.8-27b`...), et sur une tâche synthétique (recherche d'aiguilles), pas sur la tâche
réelle de Leeral (expliquer un document sans halluciner). Aucun remplacement à un vrai banc
d'essai Leeral si une décision plus ferme est nécessaire plus tard.

## 3. Comparaison de prix (catalogue OpenRouter réel, 5 octobre 2026)

| Modèle | Prompt / 1M | Complétion / 1M | Coût estimé, doc. court (~150+200 tokens) | Coût estimé, doc. long (~50k+1500 tokens) |
|---|---|---|---|---|
| `google/gemini-2.5-flash-lite` | 0,10 $ | 0,40 $ | ~0,0001 $ | ~0,0056 $ |
| `openai/gpt-5-mini` | 0,25 $ | 2,00 $ | ~0,0004 $ | ~0,0155 $ |
| `google/gemini-2.5-flash` | 0,30 $ | 2,50 $ | ~0,0005 $ | ~0,0187 $ |
| `qwen/qwen3.8-27b` | 0,42 $ | 2,55 $ | ~0,0006 $ | ~0,0248 $ |
| `anthropic/claude-haiku-4.5` | 1,00 $ | 5,00 $ | ~0,0012 $ | ~0,0575 $ |
| `openai/gpt-5` | 1,25 $ | 10,00 $ | ~0,0022 $ | ~0,0775 $ |
| `anthropic/claude-sonnet-5.5` | 2,00 $ | 10,00 $ | ~0,0023 $ | ~0,1150 $ |
| `google/gemini-3.1-pro-preview` | 2,00 $ | 12,00 $ | ~0,0027 $ | ~0,1180 $ |

À l'échelle d'un document court (l'immense majorité), l'écart de prix entre tous ces modèles est
négligeable (quelques millièmes de dollar). Il ne devient significatif qu'à l'échelle d'un
document long — exactement là où la qualité de contexte long importe aussi.

## 4. Décision

**Deux vitesses plutôt qu'un seul modèle**, sur le même principe que le Reader (déjà deux modèles
pour la double lecture, voir `AI_DECISIONS.md`) :

- **`llm_model_short` = `qwen/qwen3.8-27b`** pour les documents courts (ordonnances, factures,
  courriers — l'immense majorité des cas). Déjà intégré et éprouvé dans ce projet (Reader), bon
  marché, et à cette échelle la littérature suggère que l'écart de fidélité entre petits et gros
  modèles ne s'est pas encore creusé.
- **`llm_model_long` = `google/gemini-3.1-pro-preview`** pour les documents longs. Meilleur score
  trouvé sur la recherche multi-éléments (le risque concret d'un document de plusieurs dizaines
  de pages), au prix d'un coût et d'une latence plus élevés — acceptables car ce cas restera rare.
- **Seuil de bascule : ~8000 tokens estimés** (`llm_long_document_token_threshold`), soit environ
  10 pages de texte extrait. Estimation grossière par nombre de caractères
  (`len(prompt) // 4`, voir `Reasoner._profile_for`), pas un vrai tokeniseur par fournisseur :
  suffisant pour une décision de routage, pas pour de la facturation. **Ce seuil est un point de
  départ à ajuster** une fois de vrais documents longs mesurés en pratique.

Implémenté dans `app/ai/real/reasoning.py` (`Reasoner`), configuré via `.env` (`LLM_MODEL_SHORT`,
`LLM_MODEL_LONG`, `LLM_LONG_DOCUMENT_TOKEN_THRESHOLD`).

## 5. Ce qui reste ouvert

- Pas de banc d'essai Leeral spécifique (hallucinations, respect du style) : à faire si une
  confirmation plus ferme est nécessaire, sur le même principe que `translation-study.md` mais
  avec une métrique différente (nombre halluciné absent du texte source, pas chrF). Les garde-fous
  déjà en code (`numbers_are_grounded`, validation de date/montant contre le texte) réduisent le
  risque sans le mesurer formellement.
- Le seuil de 8000 tokens et le choix de `gemini-3.1-pro-preview` comme modèle long n'ont pas été
  vérifiés sur un vrai document de 100 pages.
- Si `qwen/qwen3.8-27b` s'avère, à l'usage, insuffisant même sur des documents courts (aucune
  hallucination mesurée pour l'instant, faute de banc d'essai dédié), le même mécanisme de seuil
  permet de changer `llm_model_short` sans toucher au reste du pipeline.
