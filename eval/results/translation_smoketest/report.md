# Banc d'essai de traduction : rapport

- Date : 2026-10-05T08:41:06+00:00
- Phrases : 20 ; lancements par phrase/sens/modèle : 1
- Mesure de qualité : chrF (n-grammes de caractères 1 à 6, beta=2), 0 à 100, plus haut = meilleur
- **ff = Fulfulde du Nigéria (FLORES-200), proxy du pulaar sénégalais : voir la limite en tête de fichier avant toute conclusion définitive sur le pulaar.**

## Par modèle et par sens

| Modèle | Sens | Appels | Échecs | chrF moyen | Latence moy. | Tokens moy. | Coût |
|---|---|---|---|---|---|---|---|
| google/gemini-2.5-flash-lite | fr-wo | 20 | 0 | 19.2 | 1.4 s | 227 | 0.0014 $ |

## Synthèse par modèle (toutes les phrases et tous les sens confondus)

| Modèle | chrF moyen global | Latence moy. | Coût total | Fournisseurs servis |
|---|---|---|---|---|
| google/gemini-2.5-flash-lite | 19.2 | 1.4 s | 0.0014 $ | {'Google': 20} |

## Recommandation par paire de langues (moyenne des deux sens)

| Paire | Meilleur chrF | Modèle | Moins cher à chrF comparable | Modèle |
|---|---|---|---|---|
| fr<->wo | 19.2 | google/gemini-2.5-flash-lite | 19.2 | google/gemini-2.5-flash-lite |
| fr<->ff | n/a | - | - | - |
| en<->wo | n/a | - | - | - |
| en<->ff | n/a | - | - | - |

Rappel : 50 phrases par sens donne une tendance, pas une garantie. « Moins cher à chrF comparable » = le moins cher parmi les modèles à moins de 3 points chrF du meilleur.
