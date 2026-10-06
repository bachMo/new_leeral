# Leeral

Leeral explique à voix haute, en wolof et en pulaar, les documents écrits en français : ordonnances, factures, courriers, convocations. On photographie le document dans l'application ou on l'envoie sur WhatsApp, puis on pose ses questions en vocal.

Projet de l'équipe New Wave (Mamadou Bachir Sy, Ahmadou Ndiaye) pour le Kiriku Voice Challenge d'AI Hub Senegal.

| Dossier | Contenu |
|---|---|
| `api/` | Backend FastAPI, worker ARQ et module IA (voir `api/README.md` et `api/docs/AI_MODULE.md`) |
| `mobile/` | Application Expo (React Native) |
| `web/` | Site web |

## Configuration

Toute la configuration passe par un seul fichier `.env` à la racine du dépôt :

```powershell
copy .env.example .env
```

Le `.env` contient les secrets : il n'est jamais versionné.