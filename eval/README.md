# eval/

Bancs d'essai et jeu de test ayant servi à choisir les modèles IA de Leeral (lecture
d'ordonnances, traduction, transcription). Transféré depuis le dépôt d'étude initial
(`leeral-project`) : les conclusions sont déjà appliquées dans `api/app/ai/settings.py`
(`READER_MODEL_A/B`, `TRANSLATOR_MODEL_PRIMARY/FALLBACK`, `LLM_MODEL_SHORT/LONG`) — ce dossier
est la preuve et la méthode derrière ces choix, pas du code à lancer en production.

Projet Python autonome (bibliothèque standard uniquement pour les bancs d'essai eux-mêmes ;
`ruff`/`mypy`/`pytest` comme dépendances de développement).

## Contenu

- `read_bench.py` : banc d'essai de lecture d'ordonnances (double lecture, modèles OpenRouter).
- `transcription_bench.py` : banc d'essai de transcription générique (documents hors ordonnance).
- `translate_bench.py` : banc d'essai de traduction fr/en ↔ wolof/pulaar (données FLORES-200).
- `lexicon.py` / `apply_lexicon.py` : vérification du lexique de médicaments contre les lectures.
- `test_*.py` : tests contre de fausses réponses HTTP (aucun appel réseau réel, aucun coût).
- `ordonnances/` : photos réelles d'ordonnances + vérité terrain (`*.truth.json`). **Jamais
  commitées** (voir `.gitignore` à la racine) — présentes seulement en local.
  `SPLIT.md` documente quelles ordonnances ont servi à la mise au point du prompt/seuils et
  lesquelles sont restées un contrôle non vu avant la décision finale.
- `documents/` : documents réels hors ordonnance (factures, courriers...). Même règle : jamais
  commités.
- `results/` : sorties des bancs d'essai.
  - `EXPERIMENTS.md`, `translation_study1/report.md`, `translation_smoketest/report.md` :
    rapports agrégés, committables (aucun contenu de document réel).
  - `real/` : analyses détaillées sur les vraies ordonnances (`AUDIT_PERFORMANCE.md`,
    `FINDINGS.md`, `lexicon_effect.md`...). **Jamais commité** : ces fichiers citent des extraits
    de lecture réels.
- `translations/sample_20.json` : 20 phrases FLORES-200 (Meta/NLLB, CC-BY-SA-4.0), alignées
  fr/en/wo/ff, utilisées par `translate_bench.py`. Donnée ouverte, committable.

## Installation et vérification (aucun appel réseau)

```bash
cd eval
python -m venv .venv && .venv/Scripts/activate   # ou : uv venv
pip install ruff mypy pytest
ruff format --check . && ruff check . && mypy --strict . && pytest
```

## Lancer un banc d'essai réel

```bash
export OPENROUTER_API_KEY=...        # jamais dans un fichier ; PowerShell : $env:OPENROUTER_API_KEY="..."
cd eval
python read_bench.py --images ordonnances --out results/essai1 --runs 3 \
    --provider deepinfra --models qwen/qwen3.8-27b meta/muse-glimmer-30b --max-cost 1.0
```

`--max-cost` arrête les nouveaux appels dès que le budget est atteint ; le relancer reprend sans
refacturer les appels déjà réussis.

## Conclusions déjà appliquées dans `api/app/ai/`

| Décision | Modèle retenu | Code |
|---|---|---|
| Lecture d'ordonnance (double lecture obligatoire) | `qwen/qwen3.8-27b` + `meta/muse-glimmer-30b`, fournisseur `deepinfra` | `AiSettings.reader_model_a/b` |
| Traduction fr/en ↔ wolof/pulaar | `google/gemini-2.5-flash-lite` (principal), `openai/gpt-5-mini` (secours) | `AiSettings.translator_model_primary/fallback` |
| LLM d'explication/dialogue | `qwen/qwen3.8-27b` (court), `google/gemini-3.1-pro-preview` (document long, > 8000 tokens estimés) | `AiSettings.llm_model_short/long` |
| Lexique de médicaments | 25 444 termes (BDPM + ARP Sénégal) | `api/app/ai/real/data/lexicon_terms.csv`, construit par `api/scripts/lexicon/` |

Détail et justification de chaque choix : `api/docs/AI_DECISIONS.md`, `api/docs/LEXICON.md`,
`api/docs/translation-study.md`, `api/docs/llm-study.md`.

## Limites connues

- Le seuil de suggestion du lexique (similarité ≥ 0,85) peut proposer une correction non
  pertinente entre deux DCI courtes qui partagent un long préfixe (ex. deux vitamines) : la
  propriété de sécurité tient (`suspect_typo` reste au plus `to_check`), mais la suggestion
  affichée à un relecteur humain peut l'induire en erreur.
- Aucune relecture par un pharmacien des règles de pharmacologie (`pharmacology_rules.csv`,
  colonne `reviewed_by` vide) ni du rapport de coquilles du lexique.
- Pulaar non testé sur un corpus sénégalais : `translate_bench.py` utilise le fulfulde du Nigéria
  (FLORES-200), seul corpus ouvert disponible au moment de l'étude.
