# Service KIRIKU local

L'API hébergée de KIRIKU n'est plus disponible. Ce service fait tourner les modèles publiés par AI Hub Sénégal sur le CPU du serveur, avec les mêmes routes que l'ancienne API : l'API Leeral n'a rien à changer, seulement deux URL dans le `.env`.

| Route | Rôle | Modèle |
|---|---|---|
| `POST /v1/audio/speech` | texte → WAV, voix `wo` ou `ff` | [Kiriku-Wolof-TTS](https://huggingface.co/AIHubSN/Kiriku-Wolof-TTS), [Kiriku-Pulaar-TTS](https://huggingface.co/AIHubSN/Kiriku-Pulaar-TTS) (VITS, Coqui TTS) |
| `POST /v1/audio/transcriptions` | audio → `{"text": …}`, langue `wo`, `ff` ou `srr` | [M-Kiriku-ASR](https://huggingface.co/AIHubSN/M-Kiriku-ASR) (Whisper large-v3), converti en CTranslate2 int8 |
| `GET /health` | état des modèles chargés | |

## Mise en route

1. Sur Hugging Face, connecté au compte qui servira, accepter les conditions des trois modèles ci-dessus.
2. Créer un jeton en lecture (Settings → Access Tokens) et le mettre dans `HF_TOKEN` du `.env`.
3. `docker compose up -d --build kiriku`. Au premier démarrage, le service télécharge les modèles (environ 8 Go) et convertit la reconnaissance vocale : compter 20 à 40 minutes. Les modèles restent dans le volume `kiriku-models`.
4. Quand `docker compose logs kiriku` affiche `asr loaded`, mettre dans le `.env` :

```
TTS_BASE_URL=http://kiriku:9000
ASR_BASE_URL=http://kiriku:9000
TTS_CONCURRENCY=2
```

puis `docker compose up -d api worker`.

## Réglages

| Variable | Rôle |
|---|---|
| `HF_TOKEN` | jeton Hugging Face, utile seulement pour le premier téléchargement |
| `KIRIKU_THREADS` | cœurs utilisés, tous par défaut |
| `KIRIKU_ASR_BEAM_SIZE` | 5 par défaut ; 1 est plus rapide, un peu moins précis |

La vitesse par défaut des voix reprend celle de l'ancienne API : 1,2 en wolof, 1,0 en pulaar.
