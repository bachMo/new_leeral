# Lexique de noms de médicaments

> Comment constituer, vérifier et maintenir la liste de noms qui sert à contrôler la lecture des
> ordonnances. Transférée depuis le dépôt d'étude initial (`leeral-project`), adaptée aux chemins
> de ce dépôt.
> Code de construction : `scripts/lexicon/` · Tests : `tests/scripts/test_lexicon_build.py` ·
> Code de recherche en ligne : `app/ai/real/safety/lexicon.py` (tests :
> `tests/ai/test_lexicon.py`) · Fichier livré : `app/ai/real/data/lexicon_terms.csv`.

**Premier lexique réel construit** : **25 444 termes** (BDPM + ARP Sénégal — voir le détail dans
`lexicon_report.md` généré par le script). La section 7 ci-dessous reste la procédure de contrôle
à suivre (relecture par un pharmacien notamment) si le lexique doit être reconstruit ou étendu.
Point d'attention identifié en relecture : l'algorithme de suggestion de coquille (similarité
≥ 0,85) propose parfois une correction non pertinente lorsque deux DCI courtes partagent un long
préfixe commun (ex. `vitamine b6` → `vitamine c`) ; la propriété de sécurité tient toujours
(`suspect_typo` reste au plus `to_check`, voir `app/ai/real/prescription.py`), mais la suggestion
affichée à un relecteur humain peut l'induire en erreur et mérite un ajustement du seuil ou une
règle dédiée aux vitamines avant mise en production à plus grande échelle.

---

## 1. Rôle du lexique

Le lexique est une **liste de noms** (marques et DCI), sans aucun contenu médical rédigé. Il sert
à une seule chose : **vérifier qu'un nom lu existe vraiment**, pour que « Amoxicilline » soit
accepté et qu'« Amoxiciline » inventé par un modèle de lecture ne passe pas comme sûr (voir
`app/ai/real/safety/lexicon.py`, classe `Lexicon`).

Il ne dit **pas** qu'un médicament est disponible au Sénégal ni à quoi il sert. Il dit seulement :
ce nom est connu d'une source officielle.

---

## 2. Les sources

| Source | Ce qu'elle apporte | Accès | Points d'attention |
|---|---|---|---|
| **BDPM** (base publique des médicaments, France) | Noms de spécialités, substances actives (DCI) et dosages, forme, voie, titulaire ; codes ATC des médicaments d'intérêt thérapeutique majeur | Téléchargement libre, fichiers texte à tabulations, mise à jour mensuelle. Fichiers utilisés : `CIS_bdpm.txt`, `CIS_COMPO_bdpm.txt`, `CIS_MITM.txt` | Licence ouverte : **ne pas altérer les données, citer la source et la date de mise à jour**. Ne couvre que les produits commercialisés (ou arrêtés depuis moins de deux ans) **en France** : elle ne contient pas les génériques indiens ou locaux |
| **ARP Sénégal** : « Liste des AMMs » et « Médicaments RCP » | **Les marques réellement autorisées au Sénégal** : nom, numéro d'AMM, DCI, dosage, forme, voie, laboratoire, classe thérapeutique. Beaucoup de génériques de laboratoires indiens et d'agences locales, absents de la BDPM | Tableaux HTML publics sur arp.sn | Données **sales** (voir section 5). Conditions de réutilisation (mentions légales) à relire avant toute diffusion externe |
| **LNMPE** (liste nationale des médicaments et produits essentiels), révisions 2022 et 2025 | DCI, dosage, forme, niveaux de soins, marque de référence, pour les produits essentiels | PDF sur arp.sn | Utile pour **marquer les médicaments essentiels** et alimenter `app/ai/real/safety/pharmacology.py`. Non traité par le script (extraction de tableaux PDF à faire à part) |
| **ATC / DDD** (OMS) | Classification thérapeutique | Index consultable gratuitement en ligne ; export Excel **payant** | Non utilisé pour les noms. On récupère gratuitement l'ATC des médicaments majeurs via `CIS_MITM.txt` |

Sources complémentaires **non implémentées** (idées, à valider) :

- **Export du catalogue d'une pharmacie partenaire** : les noms qu'elle vend vraiment, y compris
  des marques absentes des listes officielles.
- **Boucle de retour** : tout nom lu sur une vraie ordonnance et absent du lexique devient un
  candidat. Un pharmacien le valide, puis il entre dans `manual_additions.csv`.
- **Liste modèle de l'OMS des médicaments essentiels** pour recouper des DCI (conditions de
  réutilisation à vérifier).

> Contacter l'ARP (contact@arp.sn) pour un export propre de la liste des AMM reste recommandé :
> plus fiable que le scraping HTML, et cela règle la question des conditions de réutilisation.

---

## 3. Principe de sécurité : le statut de la DCI

Les listes de l'ARP contiennent des coquilles (par exemple « AMOXCILLINE », « AMOXICIILLINE » ou
« ARTHEMETER »). Si on les ajoutait telles quelles au lexique, une lecture erronée « Amoxcilline »
**trouverait une correspondance exacte** et passerait pour sûre. C'est exactement l'erreur
plausible qu'on veut éviter.

Chaque entrée porte donc un statut :

| Statut | Définition | Droit dans le moteur de lecture |
|---|---|---|
| `official` / `verified` | Terme issu d'une source de référence (BDPM), ou chaque composant de la DCI existe dans une référence, ou ajout manuel validé par un professionnel | Peut contribuer à classer une ligne `sure` (voir `TRUSTED_STATUSES` dans `lexicon.py`) |
| `suspect_typo` | Un composant n'est pas dans la référence mais ressemble à un composant vérifié (similarité d'au moins 0,85, index par trigrammes). Une suggestion est fournie | **Au plus `to_check`**, jamais `sure` |
| `unverified` | Aucun rapprochement de référence (DCI absente, rare, multivitamines, nom exotique) | **Au plus `to_check`** |

Règle codée dans `app/ai/real/safety/lexicon.py` (`Lexicon.lookup`, `TRUSTED_STATUSES`) et
`app/ai/real/prescription.py` (`verify_line`) : **une entrée dont le statut n'est pas `official`/
`verified` ne peut jamais produire une ligne `sure`.** Testé dans `tests/ai/test_lexicon.py` et
`tests/ai/test_prescription_verification.py`.

`Lexicon` retient aussi, par terme, l'ensemble des `kind` (`brand`/`dci`/`dci_core`) sous lesquels
il apparaît avec un statut de confiance dans `lexicon_terms.csv`. `Lexicon.lookup(name,
dci_only=True)` restreint la recherche (correspondance exacte et suggestion floue) aux termes dont
au moins un `kind` est `dci` ou `dci_core` — utilisé par `verify_line` pour vérifier une DCI
rapportée par le modèle de lecture (`MedicationReading.dci_read`) sans jamais la confondre avec une
marque homonyme. Voir `AI_DECISIONS.md` décision 17 : cette DCI n'est acceptée que si elle est
explicitement écrite sur l'ordonnance, jamais déduite de la marque.

---

## 4. Le pipeline

```text
fetch.py          build.py                                                        check_coverage.py
   |                 |                                                                   |
   v                 v                                                                   v
data/raw/<date>/  parse BDPM + parse ARP + manual_additions.csv                 noms d'ordonnances
 CIS_bdpm.txt        |                                                                   |
 CIS_COMPO_bdpm.txt  v                                                                   v
 CIS_MITM.txt     normalisation (marque sans dosage, DCI en composants et cœurs)    exact / proche / absent
 arp_*.html          |
 (jamais modifiés)   v
                  statut de chaque DCI (référence = BDPM + ajouts validés)
                     |
                     v
                  déduplication
                     |
                     v
          app/ai/real/data/ : lexicon_entries.csv, lexicon_terms.csv,
                               lexicon_report.md, lexicon_manifest.json
```

### 4.1 Fichiers produits

| Fichier | Contenu |
|---|---|
| `lexicon_entries.csv` | Une ligne par produit (marque + DCI + dosage + forme) |
| `lexicon_terms.csv` | Termes cherchables dédoublonnés : `brand`, `dci`, `dci_core`, avec statut et sources. **C'est ce fichier qui est livré dans `app/ai/real/data/` et chargé par `Lexicon.load()`** |
| `lexicon_report.md` | Comptes, contrôle de complétude de l'ARP, **coquilles probables**, DCI non vérifiées les plus fréquentes |
| `lexicon_manifest.json` | Date de construction, **date de mise à jour de la BDPM (obligation de licence)**, empreintes SHA-256 des entrées |

### 4.2 Colonnes de `lexicon_entries.csv`

`source`, `external_code`, `name`, `name_normalized`, `label_normalized`, `dci`, `dci_normalized`,
`dci_core`, `strength`, `form`, `route`, `holder`, `therapeutic_class`, `atc_code`, `dci_status`,
`dci_suggestion`, `is_active`, `also_in`, `validated_by`.

### 4.3 Colonnes de `lexicon_terms.csv` (format livré, chargé en production)

`term`, `kind` (`brand` / `dci` / `dci_core`), `status` (`official` / `verified` /
`suspect_typo` / `unverified` / `manual_unvalidated` / `validated`), `n_entries`, `sources`.

---

## 5. Règles de normalisation (couvertes par les tests)

| Règle | Exemple |
|---|---|
| Minuscules, sans accents, ligatures dépliées, ponctuation en espace | `Œstrogène  Béta-Bloquant` donne `oestrogene beta bloquant` |
| Entités HTML décodées, y compris mal casées chez l'ARP | `GEN&EACUTE;VRIER` donne `GENÉVRIER` |
| Nom de marque coupé au dosage, au conditionnement ou à la forme | `ZERODOL P 100 MG/500 MG` donne `zerodol p` ; `ALBENDAZOLE UBITHERA 400MG B/50` donne `albendazole ubithera` |
| Un nombre au tout début est conservé | `5-FLUOROURACILE SANDOZ` donne `5 fluorouracile sandoz` |
| Un chiffre collé à une lettre est conservé | `VITAMINE B12` reste `vitamine b12` |
| Association de DCI éclatée en composants triés | `ACECLOFENAC + PARACETAMOL` donne `aceclofenac`, `paracetamol` |
| Cœur de DCI sans le sel ni l'hydrate | `chlorhydrate de metformine` donne `metformine` ; `amlodipine besilate` donne `amlodipine` ; `amoxicilline trihydratee` donne `amoxicilline` |
| `acide folique` n'est **pas** un sel | Reste `acide folique` |

Limites assumées : le retrait des sels est une **heuristique** (liste de sels fréquents). Les
noms très particuliers (`clavulanate de potassium`, multivitamines) restent tels quels et
sortent en `unverified` ou `suspect_typo`, ce qui est le comportement sûr.

---

## 6. Utilisation

### 6.1 Commandes

```bash
cd api

# 1. Télécharger les sources brutes (BDPM + pages ARP)
python -m scripts.lexicon.fetch --raw-dir data/raw/2026-10-04

# 2. Construire le lexique
python -m scripts.lexicon.build \
    --raw-dir data/raw/2026-10-04 \
    --out-dir app/ai/real/data \
    --bdpm-date 29/09/2026          # date affichée sur la page de téléchargement de la BDPM

# 3. Mesurer la couverture sur des noms lus dans de vraies ordonnances (un nom par ligne)
python -m scripts.lexicon.check_coverage \
    --terms app/ai/real/data/lexicon_terms.csv \
    --names ../eval/noms_ordonnances.txt
```

Le script n'utilise que la bibliothèque standard.

### 6.2 Dossiers et Git

| Dossier | Contenu | Git |
|---|---|---|
| `api/data/raw/<date>/` | Fichiers bruts téléchargés (jamais modifiés) | **Ignoré** (`.gitignore`) |
| `api/data/raw/<date>/lisible/` | Copies de confort des sources brutes en CSV avec en-têtes, UTF-8, générées par `python -m scripts.lexicon._preview_raw --raw-dir data/raw/<date>`. Pour l'inspection humaine rapide uniquement | **Ignoré** (sous `data/raw/`) |
| `api/app/ai/real/data/` | Lexique construit, rapport, manifeste | Versionné (reproductibilité, revue en PR) |
| `api/data/raw/<date>/manual_additions.csv` | Ajouts manuels : `label,dci,strength,form,validated_by` | Versionné à part recommandé |

### 6.3 Plan B si le téléchargement automatique de l'ARP échoue

1. **Enregistrer la page depuis le navigateur** (« Enregistrer sous », page complète) et déposer
   le fichier sous `data/raw/<date>/arp_liste_amms.html`. Le parseur le lit tel quel. **Le plus
   rapide.**
2. Si le tableau est chargé dynamiquement (le rapport affiche « ATTENTION : aucun tableau... » ou
   un nombre de lignes très faible) : utiliser un navigateur automatisé pour récupérer le HTML
   complet.
3. Demander un export à l'ARP.
4. En dernier recours : BDPM seule + ajouts manuels (couverture nettement plus faible pour les
   génériques locaux).

---

## 7. Contrôles avant toute reconstruction du lexique

1. `lexicon_report.md` : ordre de grandeur des entrées et des marques distinctes cohérent avec
   les sources ; aucun avertissement sur l'ARP.
2. **Relecture par un pharmacien** de la section « Coquilles probables » : confirmer les
   corrections, ajouter les cas manquants.
3. Parcourir la liste des **DCI non vérifiées les plus fréquentes** : certaines sont des DCI
   légitimes absentes de la BDPM. Les valider et les ajouter à `manual_additions.csv` avec
   `validated_by`.
4. `check_coverage.py` sur les noms de médicaments de vraies ordonnances de test (voir `eval/`) :
   noter le pourcentage d'exact, de proche, d'absent. Tout « absent » est un candidat à un ajout
   manuel.
5. Citer **la source et la date de la BDPM** là où le lexique est exposé.

---

## 8. Limites du lexique (à garder en tête)

- Il vérifie l'**existence d'un nom**, pas la **justesse d'une prescription**.
- Il ne contient **pas les abréviations manuscrites** (« Amox », « Para »). Elles se traitent par
  un petit dictionnaire d'alias validé par un pharmacien (`manual_additions.csv` ou table
  d'alias).
- Un médicament **vendu mais non listé** (marché informel, nouvelle AMM) sera « absent » : c'est
  le comportement voulu, renvoi au pharmacien.
- Les listes officielles évoluent : sans mise à jour régulière, la couverture se dégrade. BDPM :
  mensuelle. ARP : à chaque nouvelle version de la liste.
