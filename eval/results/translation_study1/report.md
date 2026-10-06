# Banc d'essai de traduction : rapport

- Date : 2026-10-05T10:03:05+00:00
- Phrases : 20 ; lancements par phrase/sens/modèle : 1
- Mesure de qualité : chrF (n-grammes de caractères 1 à 6, beta=2), 0 à 100, plus haut = meilleur
- **ff = Fulfulde du Nigéria (FLORES-200), proxy du pulaar sénégalais : voir la limite en tête de fichier avant toute conclusion définitive sur le pulaar.**

## Par modèle et par sens

| Modèle | Sens | Appels | Échecs | Tronqués | chrF moyen | Latence moy. | Tokens moy. | Raisonnement (tokens) | Coût |
|---|---|---|---|---|---|---|---|---|---|
| google/gemini-3.1-pro-preview | fr-wo | 13 | 0 |  | 30.1 | 7.2 s | 743 | 8104 | 0.1071 $ |
| google/gemini-3.1-pro-preview | wo-fr | 13 | 0 |  | 53.9 | 6.6 s | 690 | 7456 | 0.0977 $ |
| google/gemini-3.1-pro-preview | fr-ff | 13 | 0 |  | 21.2 | 7.6 s | 816 | 8829 | 0.1177 $ |
| google/gemini-3.1-pro-preview | ff-fr | 13 | 0 |  | 42.3 | 7.4 s | 811 | 9044 | 0.1161 $ |
| google/gemini-3.1-pro-preview | en-wo | 12 | 0 |  | 33.3 | 6.9 s | 687 | 6985 | 0.0923 $ |
| google/gemini-3.1-pro-preview | wo-en | 12 | 0 |  | 62.2 | 6.1 s | 644 | 6457 | 0.0835 $ |
| google/gemini-3.1-pro-preview | en-ff | 12 | 0 |  | 22.0 | 7.6 s | 758 | 7643 | 0.1018 $ |
| google/gemini-3.1-pro-preview | ff-en | 12 | 0 |  | 50.7 | 7.7 s | 703 | 7129 | 0.0914 $ |
| google/gemini-2.5-flash-lite | fr-wo | 20 | 0 |  | 19.3 | 1.2 s | 228 | 0 | 0.0014 $ |
| google/gemini-2.5-flash-lite | wo-fr | 20 | 0 |  | 45.5 | 0.7 s | 121 | 0 | 0.0005 $ |
| google/gemini-2.5-flash-lite | fr-ff | 20 | 0 |  | 18.7 | 1.1 s | 208 | 0 | 0.0012 $ |
| google/gemini-2.5-flash-lite | ff-fr | 20 | 0 |  | 31.1 | 0.9 s | 125 | 0 | 0.0005 $ |
| google/gemini-2.5-flash-lite | en-wo | 20 | 0 |  | 17.6 | 1.4 s | 266 | 0 | 0.0018 $ |
| google/gemini-2.5-flash-lite | wo-en | 20 | 0 |  | 46.3 | 1.0 s | 112 | 0 | 0.0004 $ |
| google/gemini-2.5-flash-lite | en-ff | 20 | 0 |  | 19.2 | 1.2 s | 194 | 0 | 0.0012 $ |
| google/gemini-2.5-flash-lite | ff-en | 20 | 0 |  | 34.8 | 0.6 s | 116 | 0 | 0.0004 $ |
| openai/gpt-5-mini | fr-wo | 20 | 0 |  | 23.6 | 1.9 s | 157 | 0 | 0.0037 $ |
| openai/gpt-5-mini | wo-fr | 20 | 0 |  | 40.3 | 1.3 s | 144 | 0 | 0.0029 $ |
| openai/gpt-5-mini | fr-ff | 20 | 0 |  | 20.7 | 1.6 s | 166 | 0 | 0.0038 $ |
| openai/gpt-5-mini | ff-fr | 20 | 0 |  | 32.7 | 1.5 s | 146 | 0 | 0.0028 $ |
| openai/gpt-5-mini | en-wo | 20 | 0 |  | 25.4 | 1.6 s | 143 | 0 | 0.0035 $ |
| openai/gpt-5-mini | wo-en | 20 | 0 |  | 40.9 | 1.3 s | 134 | 0 | 0.0025 $ |
| openai/gpt-5-mini | en-ff | 20 | 0 |  | 22.2 | 1.5 s | 154 | 0 | 0.0038 $ |
| openai/gpt-5-mini | ff-en | 20 | 0 |  | 33.5 | 1.4 s | 135 | 0 | 0.0024 $ |
| anthropic/claude-haiku-4.5 | fr-wo | 20 | 0 |  | 21.1 | 2.4 s | 205 | 0 | 0.0132 $ |
| anthropic/claude-haiku-4.5 | wo-fr | 20 | 0 |  | 35.9 | 1.8 s | 153 | 0 | 0.0075 $ |
| anthropic/claude-haiku-4.5 | fr-ff | 20 | 0 |  | 18.9 | 2.6 s | 212 | 0 | 0.0132 $ |
| anthropic/claude-haiku-4.5 | ff-fr | 20 | 0 |  | 30.8 | 1.8 s | 161 | 0 | 0.0075 $ |
| anthropic/claude-haiku-4.5 | en-wo | 20 | 0 |  | 24.7 | 2.3 s | 146 | 0 | 0.0090 $ |
| anthropic/claude-haiku-4.5 | wo-en | 20 | 0 |  | 37.6 | 1.7 s | 134 | 0 | 0.0057 $ |
| anthropic/claude-haiku-4.5 | en-ff | 20 | 0 |  | 20.4 | 2.5 s | 169 | 0 | 0.0105 $ |
| anthropic/claude-haiku-4.5 | ff-en | 20 | 0 |  | 32.4 | 1.9 s | 143 | 0 | 0.0058 $ |
| anthropic/claude-sonnet-5.5 | fr-wo | 20 | 0 |  | 30.0 | 4.6 s | 234 | 0 | 0.0273 $ |
| anthropic/claude-sonnet-5.5 | wo-fr | 20 | 0 |  | 49.7 | 2.7 s | 223 | 0 | 0.0238 $ |
| anthropic/claude-sonnet-5.5 | fr-ff | 20 | 0 |  | 20.6 | 5.6 s | 328 | 0 | 0.0446 $ |
| anthropic/claude-sonnet-5.5 | ff-fr | 20 | 0 |  | 38.4 | 2.7 s | 224 | 0 | 0.0231 $ |
| anthropic/claude-sonnet-5.5 | en-wo | 20 | 0 |  | 31.5 | 4.3 s | 205 | 0 | 0.0250 $ |
| anthropic/claude-sonnet-5.5 | wo-en | 20 | 0 |  | 51.8 | 2.7 s | 215 | 0 | 0.0223 $ |
| anthropic/claude-sonnet-5.5 | en-ff | 20 | 0 |  | 22.0 | 4.9 s | 268 | 0 | 0.0360 $ |
| anthropic/claude-sonnet-5.5 | ff-en | 20 | 0 |  | 37.2 | 2.9 s | 214 | 0 | 0.0212 $ |
| qwen/qwen3.8-27b | fr-wo | 20 | 0 |  | 24.6 | 3.6 s | 175 | 0 | 0.0048 $ |
| qwen/qwen3.8-27b | wo-fr | 20 | 0 |  | 38.5 | 1.9 s | 139 | 0 | 0.0029 $ |
| qwen/qwen3.8-27b | fr-ff | 20 | 0 |  | 16.2 | 5.8 s | 268 | 0 | 0.0095 $ |
| qwen/qwen3.8-27b | ff-fr | 20 | 0 |  | 29.0 | 2.4 s | 144 | 0 | 0.0025 $ |
| qwen/qwen3.8-27b | en-wo | 20 | 0 |  | 26.1 | 4.8 s | 163 | 0 | 0.0047 $ |
| qwen/qwen3.8-27b | wo-en | 20 | 0 |  | 39.4 | 1.8 s | 128 | 0 | 0.0021 $ |
| qwen/qwen3.8-27b | en-ff | 20 | 0 |  | 16.4 | 3.8 s | 283 | 0 | 0.0102 $ |
| qwen/qwen3.8-27b | ff-en | 20 | 0 |  | 30.3 | 1.4 s | 133 | 0 | 0.0023 $ |

## Synthèse par modèle (toutes les phrases et tous les sens confondus)

| Modèle | chrF moyen global | Latence moy. | Coût total | Fournisseurs servis |
|---|---|---|---|---|
| google/gemini-3.1-pro-preview | 39.4 | 7.1 s | 0.8075 $ | {'Google': 100} |
| google/gemini-2.5-flash-lite | 29.1 | 1.0 s | 0.0073 $ | {'Google': 160} |
| openai/gpt-5-mini | 29.9 | 1.5 s | 0.0254 $ | {'OpenAI': 160} |
| anthropic/claude-haiku-4.5 | 27.7 | 2.1 s | 0.0724 $ | {'Amazon Bedrock': 160} |
| anthropic/claude-sonnet-5.5 | 35.1 | 3.8 s | 0.2234 $ | {'Claude Platform on AWS': 160} |
| qwen/qwen3.8-27b | 27.6 | 3.2 s | 0.0390 $ | {'AkashML': 8, 'DekaLLM': 23, 'Darkbloom': 30, 'Novita': 6, 'Chutes': 4, 'Mancer 2': 5, 'CoreWeave': 3, 'Ionstream': 21, 'Phala': 11, 'Venice': 2, 'Wafer': 20, 'Reka': 12, 'DeepInfra': 7, 'Cloudflare': 1, 'Parasail': 3, 'Alibaba': 3, 'Cerebras': 1} |

## Recommandation par paire de langues (moyenne des deux sens)

| Paire | Meilleur chrF | Modèle | Moins cher à chrF comparable | Modèle |
|---|---|---|---|---|
| fr<->wo | 42.0 | google/gemini-3.1-pro-preview | 39.9 | anthropic/claude-sonnet-5.5 |
| fr<->ff | 31.7 | google/gemini-3.1-pro-preview | 29.5 | anthropic/claude-sonnet-5.5 |
| en<->wo | 47.8 | google/gemini-3.1-pro-preview | 47.8 | google/gemini-3.1-pro-preview |
| en<->ff | 36.3 | google/gemini-3.1-pro-preview | 36.3 | google/gemini-3.1-pro-preview |

Rappel : 50 phrases par sens donne une tendance, pas une garantie. « Moins cher à chrF comparable » = le moins cher parmi les modèles à moins de 3 points chrF du meilleur.
