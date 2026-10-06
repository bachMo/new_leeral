# Module IA de Leeral

Ce guide est pour Ahmadou. Tout le traitement IA vit dans `app/ai/`. Le reste de l'API n'appelle jamais un modèle directement : il passe par une seule interface, `AiEngine`. Tu peux donc changer un modèle, un prompt ou un fournisseur sans toucher aux routes, aux services ou à la base.

## Où est quoi

```
app/ai/
├── engine.py             l'interface AiEngine : la seule chose que le reste de l'API connaît
├── contracts.py          les types échangés (PageInput, DocumentAnalysis, MedicationLine, Answer…)
├── settings.py           toutes les variables IA du .env (modèles, clés, seuils)
├── factory.py            AI_PROVIDER=mock|real → choisit le moteur
├── errors.py             AiUnavailableError, AiAuthError, AiOutputError, TranslationError…
├── metering.py           compte les appels et le coût OpenRouter de chaque tâche (table ai_jobs)
├── audio.py              WAV → MP3, concaténation, silence
├── quality.py            contrôle de la photo (flou, luminosité, taille), avant tout envoi
├── prescription_text.py  texte d'explication d'une ordonnance, construit sans LLM
├── mock/engine.py        moteur simulé, sans réseau, pour développer l'app
└── real/
    ├── engine.py         RealAiEngine : assemble tout le pipeline
    ├── prompts.py        TOUS les prompts, au même endroit
    ├── clients/          http.py (User-Agent, relances 429/5xx), kiriku.py (ASR, TTS), openrouter.py
    ├── pages.py          double classification (photo ou texte), transcription, préparation des images
    ├── prescription.py   double lecture, alignement, vérification ligne par ligne
    ├── translation.py    traduction phrase par phrase avec jetons protégés, modèle de secours
    ├── speech.py         découpage ≤ 500 caractères, TTS en parallèle, MP3
    ├── analysis.py       analyse d'un document (titre, résumé, points clés, montants, dates)
    ├── dialogue.py       réponses aux questions, avec contrôle des chiffres
    ├── writing.py        compréhension des réponses et rédaction (CV, lettres)
    ├── vocabulary.py     mots utiles d'un document pour « Apprendre le français »
    ├── reasoning.py      choix du LLM court ou long selon la taille du prompt
    ├── safety/           lexique, règles de pharmacologie, jetons protégés
    └── data/             lexicon_terms.csv, pharmacology_rules.csv
```

## Le contrat

| Méthode | Rôle |
|---|---|
| `check_image(image)` | contrôle local de la photo, appelé à l'envoi |
| `analyze_document(pages)` | lit les pages et produit `DocumentAnalysis` (résumé français, points clés, questions proposées, lignes d'ordonnance) |
| `simplify(document)` | version « plus simple » en français |
| `localize(text_fr, language, protected_terms)` | français → wolof ou pulaar |
| `to_french(text, language)` | wolof ou pulaar → français |
| `speak(text, language)` | voix KIRIKU, renvoie un MP3 |
| `transcribe(audio, filename, language)` | voix → texte avec KIRIKU |
| `answer(context)` | réponse en français à une question, à partir du document |
| `interpret_writing_answer(field, answer_fr)` | extrait l'information d'une réponse orale |
| `compose_writing(type, fields, values)` | rédige le CV ou la lettre |
| `extract_vocabulary(text_fr, limit)` | mots à apprendre |

Tout raisonne en français. La traduction et la voix se font à la fin, par `localize` puis `speak`. Les services de l'API stockent le texte français, le texte traduit et l'audio.

## Pipeline d'un document

1. `check_image` à l'envoi. Photo floue, sombre ou trop petite : refus immédiat avec `IMAGE_TOO_BLURRY`, `IMAGE_TOO_DARK` ou `IMAGE_UNREADABLE`.
2. Les PDF texte gardent leur texte. Une page PDF sans texte est rendue en image. Un DOCX devient du texte.
3. Double classification de la première page, photo ou texte. Si un des deux modèles voit une ordonnance, on prend la voie ordonnance : en cas de doute, on choisit la voie la plus prudente. Une ordonnance en PDF ou en DOCX passe donc aussi par la double lecture.
4. Ordonnance : double lecture → alignement → vérification → explication par gabarit, sans LLM.
5. Autre document : transcription de chaque page → analyse par le LLM. Les montants et les dates renvoyés sont gardés seulement s'ils apparaissent dans le texte lu.
6. L'API traduit le résumé et les points clés avec `localize`, puis les fait lire avec `speak`.

## Sécurité des ordonnances

- Une ligne n'est `sure` que si les deux lectures sont d'accord, toutes deux `legible: yes`, et si le nom est reconnu exactement par le lexique (`official` ou `verified`).
- Une incohérence de dose ou de durée (`pharmacology_rules.csv`) fait passer la ligne en `to_check`.
- Si le nom est illisible, toute la ligne est `unreadable`.
- Le moment de prise (« après le repas ») est vérifié comme les autres champs.
- Le dosage n'est jamais lu ni affiché pour une ligne `to_check` : seulement le nom.
- L'explication ne donne une posologie que pour les lignes `sure`. Pour les autres, elle renvoie vers le pharmacien.
- À la traduction, les noms de médicaments et tous les nombres sont remplacés par `⟦0⟧`, `⟦1⟧`… Chaque jeton doit revenir exactement une fois : sinon, on relance avec le modèle de secours. Si la phrase échoue encore, elle est remplacée par un avertissement traduit, jamais par du français. Si rien ne se traduit, la tâche échoue avec `TRANSLATION_FAILED`.
- Une réponse qui contient un chiffre absent du document est remplacée par une réponse prudente. Les chiffres de la question ne comptent pas : « C'est 3 fois par jour ? » ne peut pas être confirmé si le 3 n'est pas sur l'ordonnance.

## Ce qui a changé par rapport à ton dépôt

- Lexique : la suggestion pointe toujours vers un terme fiable, jamais vers sa propre coquille. Une faute sur la première lettre est rattrapée (index par trigrammes au lieu de la première lettre). Les termes de moins de 3 lettres ne comptent plus.
- Traduction : une phrase en échec n'est plus perdue en silence, et le français n'est jamais lu à la place.
- Nom de fichier audio nettoyé avant l'envoi à KIRIKU (plus de traversée de répertoire).
- Réponses JSON validées par Pydantic : une sortie invalide devient `AiOutputError` au lieu de faire planter la tâche.
- Lectures et classifications A et B en parallèle, plusieurs pages, PDF et DOCX.

## Travailler sur le module

```powershell
leeral check-ai --language wo
pytest tests/ai
```

`check-ai` appelle une fois chaque capacité avec les vraies clés : traduction, voix, retour en français, analyse. `tests/ai/test_real_engine.py` fait tourner `RealAiEngine` contre de fausses réponses HTTP : c'est l'endroit où ajouter un cas quand tu modifies un prompt ou un parseur.

- **Changer un modèle** : seulement le `.env` (`READER_MODEL_A`, `TRANSLATOR_MODEL_PRIMARY`, `LLM_MODEL_SHORT`…).
- **Changer un prompt** : `app/ai/real/prompts.py`. Garde le format JSON demandé, il est validé dans le module correspondant.
- **Mettre à jour le lexique** : remplace `app/ai/real/data/lexicon_terms.csv` par la sortie de ton script de construction (colonnes `term`, `kind`, `status`).
- **Ajouter une capacité** : ajoute la méthode dans `engine.py`, puis dans `mock/engine.py` et `real/engine.py`. mypy signale tout oubli.
- **Suivre les coûts** : chaque tâche écrit sa durée, ses appels et son coût OpenRouter dans `ai_jobs`.

Jamais de contenu de document, de transcription ni de numéro de téléphone dans les journaux. Les ordonnances de `eval/` restent hors de ce dépôt.
