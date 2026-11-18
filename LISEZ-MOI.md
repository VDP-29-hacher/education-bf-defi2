# ÉDUCATION BF : disparités d'accès à l'école au Burkina Faso

Data Challenge Burkina 2026, édition Éducation, **Défi 2**. Équipe **Burkina Novation**. Document généré le 18/11/2026 par `scripts/lisez_moi.py` à partir des sorties du pipeline : chaque chiffre ci-dessous est recalculé à chaque relance.

Ce LISEZ-MOI suit le plan conseillé pour la documentation (sept parties), puis indique, critère par critère, où le jury trouvera la preuve de chaque point. Le dossier technique complet (15 pages) et la fiche de synthèse sont dans `05_interpretation`.

| Partie | Où |
|---|---|
| 1. Le défi | [aller](#1-le-defi) |
| 2. Les données | [aller](#2-les-donnees) |
| 3. La préparation | [aller](#3-la-preparation) |
| 4. La méthode | [aller](#4-la-methode) |
| 5. Les résultats | [aller](#5-les-resultats) |
| 6. La réponse au défi | [aller](#6-la-reponse-au-defi) |
| 7. La reproduction | [aller](#7-la-reproduction) |
| Ce que le jury regarde | [aller](#ce-que-le-jury-regarde) |

## 1. Le défi

**Question du Défi 2.** Où les écarts d'accès à l'école sont-ils les plus grands (filles et garçons, ville et campagne), et évoluent-ils ?

**Notre reformulation.** Dans quelles régions et quelles provinces les enfants vont-ils le moins à l'école ? Où les filles sont-elles le plus en retard sur les garçons, et la campagne sur la ville ? Ces écarts se réduisent-ils depuis 2015/16, et où faut-il agir en premier ?

Nous regardons trois écarts à la fois, au primaire et au préscolaire, de 2015/16 à 2024/25 :

- **l'écart entre territoires** : la part des enfants scolarisés (taux brut de scolarisation, TBS) et la perte d'élèves d'une province ;
- **l'écart entre filles et garçons** : l'indice de parité (IPS = filles ÷ garçons ; 1,00 = parité) ;
- **l'écart entre ville et campagne** : l'IPS en milieu urbain moins l'IPS en milieu rural.

Les rôles de l'équipe : **Engineer** (collecte, nettoyage), **Architect** (modèle commun, liaison des territoires), **Analyst** (indicateurs, tableau de bord, interprétation), **Scientist** (liens, profils, prévision).

## 2. Les données

Le registre des sources (`01_collecte`) recense **403 fichiers**, chacun avec son empreinte sha256 et une décision pour le Défi 2 : 1 principal, 71 retenus, 221 secondaires, 8 de documentation, 102 écartés (motif écrit pour chacun).

| Source | Producteur | Ce que nous en tirons | Niveau |
|---|---|---|---|
| Base préscolaire et primaire 2015/16 à 2024/25 | DGESS / MENAPLN | élèves par sexe, statut, milieu, niveau ; TBS, TBA, TAP publiés | 13 anciennes régions |
| Annuaire statistique du primaire 2024/25 | DGESS | élèves par province, sexe, milieu et classe | 45 anciennes provinces |
| Projections de population 2020-2035 (RGPH 2019) | INSD | enfants de 6 à 11 ans par province et sexe (2024) | 45 provinces |
| Limites administratives COD-AB | IGB / OCHA (HDX) | cartes ; codes des anciennes et nouvelles entités | communes, provinces, régions |

**Limites des données**

- Données régionales par ancienne région (13) ; la correspondance avec les 17 régions actuelles est documentée à l'étape 3.
- Le niveau province (45 anciennes provinces) ne couvre que le primaire (annuaire 2024-2025) ; pas de niveau commune.
- L'IPS d'effectifs décrit la composition des inscrits ; les taux TBS, TBA et TAP (DGESS) mesurent l'accès rapporté à la population.
- Un IPS calculé sur un effectif effondré (moins de 10 % du maximum de la province) est laissé vide et signalé.
- La chute des effectifs signale une perte d'accès (fermetures d'écoles probables) sans en prouver la cause.
- Primaire 2017/18 : total national non retrouvé dans les annuaires ; années récentes possiblement provisoires.
- Aucune causalité : un écart ne dit pas sa cause. Les projections prolongent la situation actuelle, elles ne la prédisent pas.
- Les données sont agrégées et publiques : aucune information individuelle n'est utilisée.

## 3. La préparation

| Ce que nous avons corrigé | Pourquoi |
|---|---|
| Tableaux Excel DGESS remis en format long (une ligne = une valeur), avec l'adresse de la cellule d'origine | pouvoir filtrer, contrôler et retrouver chaque chiffre |
| Sous-totaux et totaux gardés mais marqués | ne jamais les additionner deux fois |
| Année numérique seule lue comme année de **fin** (2025 = 2024-2025), vérifiée contre l'annuaire | éviter un décalage d'un an sur toute la série |
| Contrôle filles + garçons = total, et totaux nationaux comparés aux annuaires | repérer les erreurs de saisie |
| Noms de provinces harmonisés (Kouritenga, Komondjari, Balé, Boulkiemdé, Loroum…) | relier annuaire, population et carte |
| 4 IPS de province laissés vides et signalés (effectif tombé sous 10 % du maximum) | un IPS calculé sur une poignée d'élèves n'a pas de sens |
| Correspondance exacte des 45 anciennes provinces vers les 17 régions actuelles, commune par commune, par les codes COD-AB | donner des chiffres sur le découpage actuel sans estimation |
| Population 6-11 ans extraite des tableaux PDF de l'INSD, puis comparée à la population utilisée par la DGESS dans chaque région | calculer un TBS par province fiable |
| Sources hors sujet écartées (écoles géolocalisées, enseignants, post-primaire) | rester sur le Défi 2 |
| Valeurs manquantes jamais remplacées par zéro | ne pas inventer de données |

Chaque règle est consignée dans le journal de nettoyage et chaque anomalie dans un fichier dédié (`02_nettoyage`).

## 4. La méthode

| Méthode | Ce qu'elle fait | Pourquoi ce choix |
|---|---|---|
| Indicateurs d'écart | IPS, TBS par sexe, écart d'IPS ville moins campagne, élèves de la dernière année ÷ meilleure année depuis 2015 | lisibles par un décideur, comparables entre territoires |
| Règle de priorité | priorité 1 : IPS < 0,95 **et** effectifs < 60 % du maximum ; priorité 2 : un seul des deux | transparente et réglable dans l'outil |
| Liens (corrélation de Spearman) | 7 questions testées sur les 45 provinces, avec p-valeur | robuste aux valeurs extrêmes ; dit si deux écarts vont ensemble |
| Profils (k-moyennes) | 5 groupes de provinces sur l'accès, la parité et l'écart ville-campagne ; nombre de groupes choisi par le score de silhouette | regrouper les provinces qui appellent la même réponse |
| Prévision de l'IPS à 3 ans | 4 modèles comparés en se plaçant en 2019, 2020 et 2021 ; le plus fiable est retenu (persistance) | une projection testée sur le passé, avec sa marge d'erreur |

Erreur moyenne du modèle retenu : 0,015 à un an, 0,025 à trois ans. Marge à 80 % : ±0,021 à un an, ±0,036 à trois ans. Une projection prolonge la situation actuelle ; elle ne prédit pas l'effet d'une politique.

## 5. Les résultats

- **L'écart le plus fort est territorial.** En 2024/25, le TBS du primaire va de 28 % (Sahel) à 115 % (Centre). Au niveau national, il passe de 86 % en 2015/16 à 79 %.
- **Il manque 895 759 élèves** au primaire pour atteindre un TBS de 100 % (4 203 855 enfants d'âge primaire).
- **Par province**, le TBS va de 9 % (Tapoa) à 115 % (Kadiogo).
- **Des provinces se vident** : 12 sur 45 ont moins de 60 % des élèves de leur meilleure année ; ensemble, elles ont perdu 301 210 élèves.
- **Filles et garçons** : l'IPS national du primaire passe de 0,94 à 0,99, mais va de 0,78 (Koulpélogo) à 1,07 (Sanguié) selon la province. Il faudrait inscrire 40 557 filles de plus pour la parité partout.
- **Ville et campagne** : l'écart d'IPS passe de 0,091 à 0,040, mais la parité reste plus faible à la campagne dans 39 provinces sur 45.
- **Où agir d'abord** : 8 provinces en priorité 1 (Kompienga, Banwa, Yagha, Sourou, Kossi, Soum, Gnagna, Nayala) et 13 en priorité 2.
- **Les écarts se cumulent.** Sur 7 questions testées, 4 montrent un lien significatif (p < 0,05) :
  - Les provinces où l'accès est faible ont-elles aussi moins de filles ? Oui, corrélation de 0,58.
  - Les provinces qui ont perdu des élèves ont-elles moins de filles ? Oui, corrélation de 0,49.
  - L'accès faible va-t-il avec un accès plus faible pour les filles ? Oui, corrélation de 0,59.
  - L'écart ville-campagne est-il plus grand là où l'accès est faible ? Oui, corrélation de -0,35.
- **Et demain** : si rien ne change, 8 provinces resteraient sous un IPS de 0,95 en 2027/28, même dans le scénario haut.

| Profil de provinces | Nombre |
|---|---|
| 1. Accès très faible, parité presque atteinte | 4 |
| 2. Accès très faible, peu de filles, fort écart ville-campagne | 9 |
| 3. Accès moyen, parité presque atteinte, fort écart ville-campagne | 7 |
| 4. Accès élevé, parité presque atteinte | 19 |
| 5. Accès élevé, parité atteinte | 6 |

**Visualisations livrées**

- La plateforme : une interface React servie par une API NestJS, ou une page autonome qui s'ouvre sans serveur (`tableau-de-bord.html` dans le zip de l'étape 4). Sept onglets : Accueil, Analyse, Tableau de bord, Carte, Aide à la décision, Prévision, Méthodes et données.
- La fiche de synthèse : une page nationale et 17 fiches régionales (PDF).
- Le dossier technique (Word, 15 pages au plus), avec cartes, courbes et tableaux.

## 6. La réponse au défi

**Comment la solution aide un décideur**

- **Ministère et DGESS** : choisir les provinces où rouvrir des classes et soutenir la scolarisation des filles, avec une règle transparente dont on règle les deux seuils dans l'onglet « Aide à la décision ».
- **Directions régionales** : imprimer la fiche d'une province (effectifs perdus, parité en ville et à la campagne, projection, filles à inscrire).
- **Partenaires et ONG** : repérer les zones où les écarts se cumulent et suivre leur évolution chaque année ; exporter les tables en CSV.

**Limites** : un écart ne dit pas sa cause. La chute des effectifs signale une perte d'accès, le plus souvent des fermetures d'écoles, sans le démontrer. Le niveau province ne couvre que la dernière année ; il n'y a pas de niveau commune.

**La suite possible** : croiser avec les fermetures d'écoles et les déplacements de population pour tester l'hypothèse sécuritaire ; descendre au niveau communal ; étendre au post-primaire ; mettre à jour chaque année avec le nouvel annuaire (le pipeline se relance tel quel).

## 7. La reproduction

**Outils** : Windows avec PowerShell, Python 3.12 ou plus (`pip install -r requirements.txt`), et Node.js 20 ou plus pour la plateforme (facultatif).

**Ordre des étapes**

```powershell
pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File scripts\lancer_pipeline.ps1 -Equipe Burkina_Novation -AnneeNumerique fin
powershell -ExecutionPolicy Bypass -File plateforme\lancer_plateforme.ps1     # puis http://localhost:3000
```

| Étape | Dossier produit | Ce qui s'y fait |
|---|---|---|
| 01 Collecte | `01_collecte` | inventaire du Data Pack, registre des sources, empreintes sha256 |
| 02 Nettoyage | `02_nettoyage` | format long, contrôles des totaux, journal, anomalies, population INSD par province |
| 03 Transformation | `03_transformation` | parité, modèle commun région × année, liaison 45 provinces → 17 régions |
| 04 Analyse | `04_analyse` | indicateurs, liens, profils, priorités, prévision, tableau de bord, données de la plateforme |
| 05 Interprétation | `05_interpretation` | dossier technique, fiche de synthèse |
| Dépôt | `A_DEPOSER` | 20 fichiers nommés selon la convention, contrôlés, copiés avec vérification sha256 |

Une étape seule : `-Etapes analyse,dashboard` par exemple. Les données brutes restent sur la machine de l'équipe : les étapes qui les lisent sont lancées en local, et la console n'affiche que des compteurs.

## Ce que le jury regarde

| Critère | Ce que nous apportons | Où le vérifier |
|---|---|---|
| Caractère innovant de la solution | premiers chiffres du primaire sur les 17 régions actuelles par addition exacte des provinces ; TBS par province avec la population INSD ; écarts traduits en nombre d'enfants ; simulateur de ciblage réglable ; profils de provinces ; prévision testée sur le passé | onglets Carte, Aide à la décision, Prévision ; dossier, partie 11 |
| Pertinence et rigueur de l'analyse | 7 liens testés avec p-valeur ; 4 modèles de prévision comparés ; contrôles des totaux ; 4 IPS non interprétables écartés et signalés ; aucune causalité affirmée | `04_analyse` (liens, typologie, backtest, signalements) ; dossier, parties 6 et 9 |
| Qualité de la visualisation et expérience utilisateur | sept onglets, cartes interactives avec zoom, courbes lissées, recherche de province, lien partageable, thème sombre, téléphone et tablette, clavier, mouvement réduit | `tableau-de-bord.html` (zip de l'étape 4) ou http://localhost:3000 |
| Impact possible sur le problème ciblé | 8 provinces prioritaires nommées, 301 210 élèves perdus et 40 557 filles à inscrire chiffrés, fiches par province et par région prêtes à imprimer, pistes d'action | onglets Accueil et Aide à la décision ; fiche de synthèse |
| Faisabilité technique et opérationnelle | outils libres (Python, React, NestJS) ; page autonome sans serveur ni Internet ; exports CSV pour Excel ; mise à jour annuelle en une commande | partie 7 ; `plateforme/README.md` |
| Reproductibilité et qualité de la documentation | un pipeline en une commande ; chaque fichier nommé, horodaté et vérifié par sha256 ; un LISEZ-MOI par étape ; dossier de 15 pages ; ce document régénéré à chaque relance | `scripts/` ; `A_DEPOSER/GUIDE_DE_DEPOT.txt` ; ce LISEZ-MOI |

