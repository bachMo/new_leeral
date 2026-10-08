# Leeral API

Backend de Leeral. On photographie ou on envoie un document en français (photo, plusieurs pages, PDF ou DOCX) dans l'application ou sur WhatsApp. Leeral l'explique à voix haute en wolof ou en pulaar, puis répond aux questions posées en vocal. L'API gère aussi « Leeral écrit pour moi » (CV, lettres), l'apprentissage du français et l'abonnement Leeral+.

## Stack

| Rôle | Choix |
|---|---|
| API | FastAPI, Pydantic v2 |
| Base de données | PostgreSQL, SQLAlchemy 2 (async, asyncpg), Alembic |
| Tâches de fond | ARQ sur Redis |
| Fichiers | Cloudflare R2 (URL signées), stockage local en développement |
| IA | Module `app/ai` : KIRIKU (ASR, TTS) et OpenRouter (lecture, traduction, LLM), ou un moteur simulé |
| WhatsApp | Meta Cloud API (Graph v25.0) |
| Qualité | ruff, mypy strict, pytest |

## Architecture

```
app/
├── main.py                 création de l'application, cycle de vie
├── api/                    couche HTTP : routes v1, dépendances, présentation, erreurs
├── schemas/                contrats JSON d'entrée et de sortie
├── services/               logique métier (un service par fonctionnalité)
├── repositories/           requêtes SQL, une classe par agrégat
├── models/                 modèles SQLAlchemy (30 tables)
├── db/                     moteur, session, unité de travail
├── ai/                     module IA isolé (voir docs/AI_MODULE.md)
├── channels/whatsapp/      réception des webhooks et assistant WhatsApp
├── integrations/           R2, WhatsApp Graph API, paiement
├── workers/                tâches ARQ et tâches planifiées
├── core/                   configuration, erreurs, sécurité, langues, journaux
└── cli.py                  commandes d'administration (`leeral ...`)
migrations/                 migrations Alembic
scripts/smoke_test.py       test de bout en bout d'une API lancée
tests/                      tests unitaires
```

Une requête suit toujours le même chemin : `route → service → repository → modèle`. Les routes ne contiennent pas de logique. Les traitements longs (lecture, explication, réponse vocale, rédaction) sont mis en file par l'unité de travail **après** la validation de la transaction, puis exécutés par le worker. L'application interroge ensuite l'état (`pending` → `ready`).

Toutes les erreurs ont la même enveloppe :

```json
{"error": {"code": "IMAGE_TOO_BLURRY", "message": "La photo est floue. Reprends-la sans bouger.",
  "message_key": "errors.image_too_blurry", "audio_key": "error.image_too_blurry",
  "retryable": false, "request_id": "…", "fields": {"page": 0}}}
```

`audio_key` correspond à une consigne vocale disponible sur `GET /v1/prompts`.

## Installation (Windows)

Prérequis : [uv](https://docs.astral.sh/uv/), PostgreSQL et Redis.

```powershell
cd new_leeral\api
uv python install 3.13
uv venv --python 3.13 .venv
.venv\Scripts\Activate.ps1
uv pip install -e ".[dev]"
copy ..\.env.example ..\.env
```

Python 3.12 ou 3.13 est requis : la 3.11 est trop ancienne pour le code, et certaines dépendances n'ont pas encore de version Windows pour la 3.14.

### Base de données

L'API crée elle-même ses tables avec Alembic. Il faut donc une base **vide**. Si tu as déjà exécuté l'ancien script SQL dans pgAdmin, supprime cette base puis recrée-la (outil de requête connecté à la base `postgres`) :

```sql
DROP DATABASE IF EXISTS leeral;
CREATE DATABASE leeral;
```

Puis mets le mot de passe dans `DATABASE_URL` du `.env` et lance :

```powershell
alembic upgrade head
```

### Configuration (`.env`)

Le fichier `.env` est à la racine du dépôt (`new_leeral/.env`), à côté de `.env.example`. Un `api/.env` est aussi lu s'il existe, et ses valeurs priment.

Valeurs à remplir toi-même :

| Variable | Valeur |
|---|---|
| `DATABASE_URL` | mot de passe PostgreSQL |
| `JWT_SECRET` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `META_APP_SECRET`, `WHATSAPP_ACCESS_TOKEN` | console Meta (régénérés) |
| `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | Cloudflare R2 (régénérées), puis `STORAGE_BACKEND=r2` |
| `ASR_*`, `TTS_*`, `OPENROUTER_API_KEY` | clés KIRIKU et OpenRouter, puis `AI_PROVIDER=real` |

Pour démarrer sans aucune clé : `AI_PROVIDER=mock`, `STORAGE_BACKEND=local`, `OTP_DELIVERY=console` (le code de connexion s'affiche dans le terminal de l'API).

Pour une démo publique sans envoi de SMS ni de modèle WhatsApp payant : `OTP_DELIVERY=demo` et `OTP_DEMO_CODE` (autant de chiffres que `OTP_LENGTH`). Ce code fixe fonctionne pour tous les numéros : à réserver à la démo.

## Lancer

Deux terminaux, environnement activé dans chacun :

```powershell
uvicorn app.main:app --reload --port 8000
```

```powershell
arq app.workers.settings.WorkerSettings
```

Documentation interactive : http://localhost:8000/docs

### Données de départ

```powershell
leeral seed-channel --display-number "+1 555 638 9708"
leeral seed-words
leeral sync-prompts
```

`seed-words` crée le vocabulaire de base et sa traduction audio. `sync-prompts` génère les consignes vocales des écrans de l'application (`app.*`), de WhatsApp et des erreurs. `GET /prompts` renvoie toujours le texte de chaque consigne, et son audio dès qu'il est généré. Relance les deux après le passage à `AI_PROVIDER=real` (`sync-prompts --force`).

### Vérifier que tout marche

```powershell
python scripts/smoke_test.py
```

Le script parcourt l'application de bout en bout : invité, photo d'une facture, explication simple, question, création du compte (il demande le code OTP), PDF, lettre, séance d'apprentissage, paiement simulé.

```powershell
leeral check-ai --language wo
ruff check . ; mypy app ; pytest
```

## Points d'entrée (`/v1`)

| Domaine | Routes |
|---|---|
| Général | `GET /health`, `GET /languages`, `GET /prompts?language=wo` |
| Connexion | `POST /auth/guest`, `POST /auth/otp/request`, `POST /auth/otp/verify`, `POST /auth/refresh`, `POST /auth/logout` |
| Compte | `GET /me`, `PATCH /me`, `DELETE /me` |
| Documents | `POST /documents` (multipart `files`), `GET /documents`, `GET /documents/{id}`, `DELETE /documents/{id}`, `POST /documents/{id}/retry`, `POST /documents/{id}/explanations`, `POST /documents/{id}/conversation`, `GET /library` |
| Questions | `GET /conversations/{id}/messages`, `POST /conversations/{id}/messages` (multipart : `audio`, `text` ou `suggested_question_id`) |
| Écrire pour moi | `GET /writings/types`, `POST /writings`, `GET /writings/{id}`, `POST /writings/{id}/answers`, `POST /writings/{id}/confirm`, `POST /writings/{id}/skip` |
| Apprendre | `GET /learning/overview`, `GET /learning/words`, `POST /learning/sessions`, `POST /learning/sessions/{id}/answers`, `POST /learning/sessions/{id}/finish` |
| Leeral+ | `GET /billing/plans`, `POST /billing/checkout`, `GET /billing/payments/{token}`, `POST /billing/payments/{token}/simulate` |
| Voix | `POST /speech/transcriptions` (multipart `audio`) : texte entendu et sa traduction en français |
| WhatsApp | `GET` et `POST /webhooks/whatsapp` |

Un invité qui vérifie son numéro avec son jeton d'invité dans l'en-tête `Authorization` garde ses documents : la même ligne `users` devient un compte, et ses fichiers passent de `tmp/` à `users/` dans R2.

## WhatsApp en local

```powershell
ngrok http 8000 --url <ton-domaine-statique>.ngrok-free.app
```

Dans la console Meta, URL de rappel : `https://<ton-domaine>/v1/webhooks/whatsapp`, jeton de vérification : `WHATSAPP_VERIFY_TOKEN`, champ abonné : `messages`. Chaque requête est vérifiée avec `META_APP_SECRET` (en-tête `X-Hub-Signature-256`). Le modèle `leeral_rappel` est envoyé sans variable.

## Choix techniques

- Les valeurs d'énumération sont stockées en texte et validées dans le code. Elles sont en anglais (`pending`, `ready`, `health`…), comme le reste du code.
- Table ajoutée au schéma validé : `prescription_lines`, une ligne par médicament lu avec son statut (`sure`, `to_check`, `unreadable`).
- Le sérère est accepté par le modèle de données et affiché « bientôt » : KIRIKU n'a pas encore de voix sérère.
- `words.audio_fr_key` est facultatif : la prononciation française d'un mot est jouée par la synthèse vocale du téléphone, KIRIKU ne parlant pas français.
- Les documents des invités sont supprimés après 24 h, les invités inactifs après 30 jours (tâches planifiées du worker).
- Un traitement interrompu (coupure, délai dépassé) ne reste jamais bloqué : une tâche planifiée passe en échec tout ce qui est en attente depuis plus de 20 minutes, et `POST /documents/{id}/retry` relance un document en échec.
- Le paiement est simulé derrière une interface : brancher Wave ou PayDunya revient à ajouter une implémentation de `PaymentGateway`.