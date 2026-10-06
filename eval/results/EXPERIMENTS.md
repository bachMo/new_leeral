# Journal d'expériences — banc d'essai de lecture

Une entrée par expérience. Voir le brief complet (fourni par l'humain le 4 octobre 2026) pour la méthode, les critères de décision (PARTIE E) et les garde-fous contre les biais (PARTIE F).

> Les données réelles (images, vérités terrain, réponses brutes, extraits précis) vivent uniquement
> dans `eval/ordonnances/`, `eval/documents/` et `eval/results/real/` — **gitignorés, jamais commités**
> (documents personnels réels). Ce journal ne contient que des constats génériques, sans donnée
> personnelle. Le détail précis (avec extraits réels) est dans `results/real/FINDINGS.md` et
> `results/real/AUDIT_PERFORMANCE.md` (local, jamais commités).

---

## 2026-10-05 — Jeu de contrôle (4 ordonnances) + lot `new_ocr_data` (25 images, domaines variés)

### Jeu de contrôle

4 ordonnances fraîches (Abidjan) évaluées une seule fois avec la config finaliste (double lecture +
lexique). **0 erreur non signalée pour les deux modèles**, confirmant la sûreté sur un échantillon
nettement plus dur (photos floues, 0% de noms exacts, 95% de désaccord). Réserve méthodologique
documentée : ces 4 images ont été regardées une fois pour les trier avant de savoir si c'était des
ordonnances — pas une blindness parfaite, décision explicite de l'utilisateur d'accepter ce
compromis plutôt que de perdre la donnée. Détail : `eval/ordonnances/SPLIT.md` (local).

### Lot `new_ocr_data` : 25 images, 5 domaines différents

Pas un lot d'ordonnances : devoirs d'élève notés, cahier de comptabilité manuscrit, rapports
imprimés (anglais), carte de prière. 5 doublons exacts du lot précédent ignorés. 16 documents
ajoutés à `eval/documents/` pour `transcription_bench.py` (sur décision explicite : traiter
génériquement, pas de classification par cas pour l'instant).

### Bug réel trouvé : vérité terrain polluée par mes propres notes

J'avais ajouté des avertissements ("[AVERTISSEMENT : vérité terrain BASSE CONFIANCE...]") **à
l'intérieur** de 8 fichiers `.truth.txt`. `transcription_bench.py` compare tout le contenu du
fichier au mot à mot : mes notes ont été comptées comme texte "omis" par le modèle, gonflant
artificiellement l'erreur. Corrigé (notes retirées des 8 fichiers) ; renotation gratuite (appels
déjà en cache, 0 $ de recoût) avec `transcription_bench.py` relancé.

### Découverte réelle après correction : boucle de répétition dégénérée sur `meta/muse-glimmer-30b`

Sur 2 documents difficiles (page de mathématiques dense, tableau KPI dense), `muse-glimmer-30b` ne
s'est pas contenté de mal lire : il est entré en **boucle de répétition dégénérée**, produisant
3000+ "mots" (en réalité des points de suspension ou une phrase répétée des centaines de fois)
au lieu de suivre la consigne "marque [illisible] si tu n'es pas sûr". Confirmé en inspectant le
texte brut (pas un artefact de notation). `qwen/qwen3.8-27b` ne montre PAS ce comportement sur les
mêmes documents (transcriptions longues mais de bonne foi, cohérentes). **Nuance la recommandation
du 4 octobre** : muse-glimmer-30b reste le plus sûr pour l'extraction structurée (JSON forcé avec
champ `legible`), mais semble moins fiable que qwen pour la transcription libre face à du contenu
qu'il ne comprend pas. Coût de cette découverte : 0 $ (appels déjà faits, bug de notation corrigé
après coup).

---

---

## 2026-10-05 — pharmacology_rules.py, quality.py, classify.py + constat sur le jeu de contrôle

### `safety/pharmacology_rules.py` (complément au lexique)

18 médicaments de départ (DRAFT, `reviewed_by` vide, sourcés de notices RCP standard). Branché
dans `pipeline/read.py` : une ligne ne reste jamais `sure` si la dose/durée est implausible, même
si lexique et double lecture sont d'accord. Test dédié qui reproduit le cas réel "Fentanyl 800mg"
(section 3ter de `AUDIT_PERFORMANCE.md`) : passe le lexique seul (`sure`), intercepté dès que
`pharmacology_rules.py` est actif. Bug réel trouvé et corrigé en écrivant les tests : un objet
vide-mais-valide (`__len__ == 0`) était traité comme absent par `x or get_x()` — remplacé par des
vérifications explicites `is not None` partout où ça s'applique (lexique inclus).

### `pipeline/quality.py` et `pipeline/classify.py`

`quality.py` : flou (variance du Laplacien), luminosité, résolution, et une heuristique
approximative de cadrage (bord de l'image). Testé sur des images synthétiques (pas besoin de
vraies photos pour ce genre de contrôle mathématique).

`classify.py` + `providers/classifier.py` : type de document + langue, un appel OpenRouter bref
avant la lecture complète. **Validé contre 4 vraies images** (coût négligeable, ~0,0002 $) : les
deux angles morts trouvés le 4 octobre sont désormais fermés — un certificat médical est classé
`letter` (pas `prescription`), un bon de labo est classé `lab_result` (pas `prescription`), tous
deux avec confiance. Une imprécision mineure et sans risque notée : une ordonnance vierge (modèle
papier non rempli) est classée `prescription` avec confiance au lieu de signaler une incertitude —
pas dangereux (Reader n'y trouvera simplement aucun médicament), mais à améliorer.

### Jeu de contrôle séparé (PARTIE F du brief) : toujours pas de vrai jeu de contrôle

Constat honnête plutôt qu'un jeu de contrôle de façade : les 30 ordonnances réelles ont déjà
toutes servi à construire leur vérité terrain, trouver des cas réels (Xylca/Xykaa, Gardenal,
Haldol, Fentanyl) et calibrer `pharmacology_rules.py`. Les désigner maintenant comme "contrôle"
contredirait la règle même du brief (PARTIE F : pas de fuite de la vérité, jamais relu avant
l'évaluation finale). Infrastructure de suivi mise en place (`eval/ordonnances/SPLIT.md`, local) :
toute nouvelle ordonnance entre en "mise au point" par défaut, ne passe en "contrôle" que si
jamais analysée, et n'est évaluée qu'une seule fois à la fin. **Il manque des ordonnances
fraîches, jamais vues, pour qu'un vrai jeu de contrôle existe.**

---

## 2026-10-04 — Lexique de médicaments branché sur `read_bench.py` (Phase 2 point e du brief)

### Objectif

Mesurer l'effet d'un rapprochement flou contre le vrai lexique de médicaments (déjà construit dans
`apps/api/app/data/lexicon/`, 21 528 entrées BDPM + ARP Sénégal) sur les erreurs non signalées.
Nouveaux fichiers : `eval/lexicon.py` (chargement + rapprochement flou, seuil 0,85 documenté dans
`docs/lexique-medicaments.md`) et `eval/apply_lexicon.py` (renotation hors ligne des résultats déjà
enregistrés — **aucun nouvel appel réseau, coût 0 $**). 7 nouveaux tests (`test_lexicon.py`,
`test_apply_lexicon.py`), 25 tests au total, tous verts.

### Résultat

`qwen/qwen3.8-27b` : 12 → **2** erreurs non signalées (7 lignes gagnées en sécurité, 8 rétrogradées
à tort — majoritairement le dosage d'une ligne dont le nom seul était en cause, comportement voulu
par la règle « confiance de la ligne = minimum de ses champs »). `meta/muse-glimmer-30b` : 0 → 0
(inchangé).

### Limite découverte, confirmée par un cas réel

Le lexique seul ne peut pas détecter une lecture qui dérape vers le nom d'un **autre vrai
médicament** (le nom existe dans le lexique, donc il passe). Cas précis dans
`results/real/AUDIT_PERFORMANCE.md` section 3ter. Confirme que `pharmacology_rules.py` (cohérence
des doses, pas encore écrit) reste nécessaire en plus du lexique, pas à sa place — conforme à
l'architecture déjà documentée, maintenant avec une preuve concrète.

### Conséquence sur la recommandation de modèle

Le lexique resserre fortement l'écart entre les deux modèles trouvé dans l'entrée précédente :
recommandation révisée vers « double lecture + lexique obligatoire sur les deux modèles » plutôt
qu'un choix d'un seul modèle. Détail dans `results/real/AUDIT_PERFORMANCE.md` section 7 (local).

---

## 2026-10-04 — Échantillon d'ordonnances agrandi de 4 à 30 (26 exemples en ligne, anonymisés)

### Objectif

Le précédent échantillon (4 ordonnances) était jugé trop petit pour trancher quoi que ce soit.
26 ordonnances supplémentaires (exemples anonymisés trouvés en ligne par l'utilisateur, consentement
confirmé) ont été intégrées à `eval/ordonnances/` (vérité terrain construite à la main, champs
incertains laissés `null` plutôt que devinés). Un document trouvé dans le même lot (certificat
médical de cause de décès d'une personne réelle nommée) a été explicitement exclu : hors périmètre
« ordonnance », et d'une catégorie de sensibilité différente des autres exemples.

### Résultat principal : le classement entre les deux modèles s'inverse

Sur 4 ordonnances, les deux modèles avaient 0 erreur non signalée. **Sur 30 ordonnances (312 champs
comparés), `qwen/qwen3.8-27b` est passé à 12 erreurs non signalées, tandis que
`meta/muse-glimmer-30b` est resté à 0.** Les cas précis incluent au moins deux erreurs confiantes
sur des médicaments réels (pas seulement sur le contenu de test volontairement absurde inclus dans
le lot). Détail avec extraits dans `results/real/AUDIT_PERFORMANCE.md` (local).

Recommandation révisée en conséquence (voir fichier local, section 7) : modèle le plus sûr des deux
en lecteur principal, l'autre en deuxième lecture indépendante — pas l'inverse de la recommandation
provisoire précédente.

### Limite de méthode trouvée (ne pas réinterpréter sans la lire)

Le compteur « médicaments omis » du rapport est partiellement un artefact : des lignes de vérité
terrain volontairement laissées sans nom (illisibles même pour l'annotateur humain) sont toujours
comptées comme omises par `match_meds`, qui ne sait pas ignorer une entrée de vérité sans nom.
N'affecte pas le chiffre d'erreurs non signalées (12 vs 0), qui reste fiable.

### Coût

0,0921 $ (qwen) + 0,0426 $ (muse-glimmer) = 0,1347 $ pour 120 appels (30 ordonnances x 2 modèles x
2 lancements).

---

## 2026-10-04 — Test réel sur 4 ordonnances et 7 documents personnels (fournis par l'utilisateur, avec son accord)

### Objectif

Premier test de bout en bout sur des documents réels (et non plus une image factice de Phase 0) :
4 ordonnances manuscrites avec `read_bench.py`, et 7 documents administratifs variés (lettre,
facture, certificats, contrat) avec un nouvel outil `transcription_bench.py` (transcription fidèle +
diff mot-à-mot, créé car `read_bench.py` est spécifique aux médicaments). Modèles : `qwen/qwen3.8-27b`
et `meta/muse-glimmer-30b`, fournisseur `deepinfra`. Coût total : 0,0261 $.

### Constats génériques (détail précis avec extraits réels dans `results/real/FINDINGS.md`, local)

- **Ordonnances** : 0 erreur non signalée sur les deux modèles (le garde-fou `legible: partial`
  fonctionne). Sur 24 champs comparés en double lecture : 33 % accord correct, 62 % désaccord (donc
  renvoyé au pharmacien), **4 % accord mais faux (1 cas)** — les deux modèles ont lu indépendamment
  le même nom de produit erroné. Ce cas précis illustre pourquoi le lexique de médicaments (ADR-002)
  est nécessaire en plus de la double lecture : un rapprochement flou contre une vraie liste de noms
  aurait probablement intercepté ce cas.
- **Documents généraux** : texte imprimé propre lu presque parfaitement (moins de 3 % d'erreur mots)
  par les deux modèles. Les formulaires manuscrits avec tableaux/cases à cocher sont le point faible
  net (45 à 83 % d'erreur mots), largement au-delà de la difficulté des ordonnances manuscrites
  simples.
- **Trouvé une invention confiante sans aucun signal d'incertitude** sur un document sans rapport
  avec une ordonnance : `qwen/qwen3.8-27b` a ajouté une phrase de clôture plausible mais totalement
  inventée. Confirme l'intérêt du schéma structuré avec champ `legible` obligatoire (déjà utilisé
  dans `read_bench.py`) plutôt qu'une transcription libre sans garde-fou pour tout usage réel.
- Au moins deux cas de dates confidentes mais fausses (mauvaise année, mauvais mois) sur un document
  hors ordonnance, sans aucun marqueur de doute — le risque "nombre déformé" décrit dans
  contexte-projet.md §11.5 ne concerne donc pas que les posologies.
- Correctif de méthode : une vérité terrain (`ord_01.truth.json`) contenait une unité ("mg") non
  écrite sur l'ordonnance d'origine, ajoutée par erreur en construisant le fichier. Corrigée avant
  toute lecture des résultats de notation sur ce champ.
- Limite découverte : le diff mot-à-mot séquentiel peut compter à tort des champs comme "omis"
  quand un modèle les a seulement réordonnés dans sa réponse (observé sur un formulaire) ; un
  alignement clé/valeur serait plus juste pour ce type de document (amélioration possible, non
  faite).

### Limites de cette session

Échantillon minuscule (4 + 7 documents), pas de séparation mise au point / jeu de contrôle, pas de
lexique de médicaments branché. Tendance, pas garantie — ne pas utiliser ces chiffres pour arrêter un
choix de modèle final (voir Phase 4 du brief, à faire plus tard sur un jeu plus grand et séparé).

### Bug corrigé dans l'outillage (les deux scripts)

`sys.stdout.write(report)` plantait sur Windows (console `cp1252`) dès qu'un caractère comme `○`
apparaissait dans une transcription — le fichier `report.md` (UTF-8) était toujours sauvegardé
correctement, seul l'affichage console plantait. Ajout de `print_report()` avec repli
`errors="replace"` dans `read_bench.py` et `transcription_bench.py`, avec test de régression.

---

## 2026-10-04 — Phase 0 : vérification de connectivité réelle

### Objectif

Confirmer que `read_bench.py` correspond bien au comportement réel de l'API OpenRouter (identifiants de modèles, paramètres acceptés, champs de la réponse) avant d'écrire la moindre vraie ordonnance dans `ordonnances/` (aucune image réelle disponible à cette date). Limite connue n°1 du brief (PARTIE C).

### Modèles et fournisseur

- `qwen/qwen3.8-27b` et `meta/muse-glimmer-30b` (paire 1, poids ouverts), fournisseur figé `deepinfra`.
- Budget : `--max-cost` fixé à 0,05 $ par série de test (bien sous le budget de 10 $ de la PARTIE A5).

### Jeu utilisé

Aucun jeu réel. Une seule image factice générée par code (PNG blanc 32x32, bibliothèque standard `zlib`, aucune dépendance), avec `medications: []` en vérité terrain. Cette image ne sert qu'à vérifier la mécanique de l'appel (format accepté, champs de la réponse) : elle ne permet AUCUNE mesure de précision de lecture. Fichiers supprimés après l'expérience (hors dépôt, dans un répertoire temporaire).

### Ce qui a été vérifié (lecture, gratuit)

- `GET /models` : 466 modèles listés. Confirmé :
  - `qwen/qwen3.8-27b` : 17 fournisseurs sur OpenRouter (dont `deepinfra`, `phala`, `together`, `alibaba`...).
  - `meta/muse-glimmer-30b` : seulement 3 fournisseurs (`phala`, `deepinfra`, `together`), comme attendu dans le brainstorm.
  - Identifiant réel de GPT-6.1 Sol : `openai/gpt-6.1-sol` (existe aussi `openai/gpt-6.1-sol-pro`).
  - Identifiant réel de Gemini 3.1 Pro : `google/gemini-3.1-pro-preview` (statut "Preview" confirmé dans l'identifiant lui-même).
  - Les deux modèles de la paire 1 supportent `response_format`, `structured_outputs`, `reasoning_effort` (utile pour la Phase 2.d du brief).

### Ce qui a été vérifié (appels réels, payants)

| Appel | Résultat | Coût |
|---|---|---|
| `qwen/qwen3.8-27b` via `deepinfra`, `reasoning.effort=none` | HTTP 200, OK, 0 token de raisonnement | 0,000088 $ |
| `meta/muse-glimmer-30b` via `deepinfra`, `reasoning.effort=none` | **HTTP 400** : `"Reasoning is mandatory for this endpoint and cannot be disabled."` | 0 $ (non facturé) |
| `meta/muse-glimmer-30b` via `phala`, `reasoning.effort=none` | HTTP 400, même erreur | 0 $ |
| `meta/muse-glimmer-30b` via `together`, `reasoning.effort=none` | HTTP 400, même erreur | 0 $ |
| Appel brut de contrôle, `reasoning.effort=minimal` | HTTP 200, OK, 22 tokens de raisonnement | 0,0000588 $ |
| `qwen/qwen3.8-27b` via `deepinfra`, `reasoning.effort=minimal` (après correctif) | HTTP 200, OK | 0,0005 $ |
| `meta/muse-glimmer-30b` via `deepinfra`, `reasoning.effort=minimal` (après correctif) | HTTP 200, OK, 178 tokens de raisonnement | 0,0003 $ |

**Coût total de la phase 0 : 0,0009 $** (moins d'un dixième de centime), sur un budget de 10 $.

### Écart détecté entre le code et la vraie API

Le code imposait `reasoning: {"effort": "none"}` pour tous les modèles quand `--thinking` n'est pas passé. `meta/muse-glimmer-30b` refuse ce réglage quel que soit le fournisseur (contrainte du modèle, pas du fournisseur) : le raisonnement est obligatoire chez lui. La décision n°5 du brainstorm ("le raisonnement est désactivé") ne tient donc pas pour ce modèle précis.

### Correctif appliqué

Ajout de l'option `--reasoning-effort {none,minimal,low,medium,high}` (défaut `none`, comportement inchangé pour les modèles qui acceptent de le désactiver). `meta/muse-glimmer-30b` doit être lancé avec `--reasoning-effort minimal`. Testé réellement : fonctionne, coût toujours très faible (22 à 178 tokens de raisonnement selon le prompt, de l'ordre de 0,0003 à 0,0006 $ par appel).

Code et tests mis à jour (`eval/read_bench.py`, `eval/test_read_bench.py`) ; `ruff format`, `ruff check`, `mypy --strict` et `pytest` (8 tests, faux serveur, aucun appel réseau) passent après le correctif.

### Conclusion

Le script colle maintenant au comportement réel de l'API pour les deux modèles de la paire 1, avec un fournisseur commun (`deepinfra`) qui les sert tous les deux. Rien d'autre n'a été mesuré (aucune précision de lecture, aucune donnée sur de vraies ordonnances). Phase 1 (base de référence réelle) ne peut pas commencer : il manque des ordonnances réelles (fictives ou anonymisées avec accord) et leurs annotations dans `eval/ordonnances/`.

### Prochaine étape

Dès que des images + annotations sont disponibles dans `eval/ordonnances/` : lancer la Phase 1 du brief (base de référence, 3 lancements, paire 1, `--reasoning-effort none` pour qwen et `minimal` pour muse-glimmer).
