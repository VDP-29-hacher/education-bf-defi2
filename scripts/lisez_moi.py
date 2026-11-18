#!/usr/bin/env python3
"""LISEZ-MOI GENERAL du projet (Defi 2), structure selon le plan conseille de la documentation et les criteres du jury.

Tous les chiffres sont lus dans les sorties du pipeline (aucune saisie a la main) : le document reste juste a chaque relance.
Entrees : 01_collecte/*registre-sources_v1.csv ; 04_analyse/*_donnees-plateforme_v1.json et tables de l'etape 4.
Sortie  : LISEZ-MOI.md et README.md (meme contenu, affiche par GitHub) a la racine ; LISEZ-MOI.md est repris dans le zip du code depose.
Usage   : lisez_moi.py [--racine DOSSIER] [--equipe Burkina_Novation]
"""
import argparse, csv, glob, json, os, sys
from collections import Counter
from datetime import date


def un(motif):
    f = sorted(glob.glob(motif))
    if not f:
        sys.exit(f"Introuvable : {motif} (lancez d'abord le pipeline)")
    return f[0]


def lire_csv(motif):
    with open(un(motif), encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


f2 = lambda v: "n.d." if v is None else f"{v:.2f}".replace(".", ",")
f3 = lambda v: "n.d." if v is None else f"{v:.3f}".replace(".", ",")
pc = lambda v: "n.d." if v is None else f"{round(v)} %"
nb = lambda v: "n.d." if v is None else f"{round(v):,}".replace(",", " ")
ya = lambda y: f"{y}/{str(y + 1)[2:]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--racine", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--equipe", default="Burkina_Novation")
    a = ap.parse_args()
    R = a.racine
    D = json.load(open(un(os.path.join(R, "04_analyse", "*_donnees-plateforme_v1.json")), encoding="utf-8"))
    reg = lire_csv(os.path.join(R, "01_collecte", "*_registre-sources_v1.csv"))
    dec = Counter(r["decision_defi2"] for r in reg)
    sig = lire_csv(os.path.join(R, "04_analyse", "*_ips-provinces-signalements_v1.csv"))

    Y = D["years"]; n1 = len(Y) - 1; y0, y1 = ya(Y[0]), ya(Y[n1])
    I, P = D["prov"]["ind"], D["prov"]
    z = D["acc"]["tbs_primaire"]["z"]
    rs = sorted([r for r in D["regions"] if z.get(r) and z[r]["t"][n1] is not None], key=lambda r: z[r]["t"][n1])
    lo, hi = rs[0], rs[-1]
    gap = [None if u is None or r is None else u - r for u, r in zip(D["mil"]["urbain"], D["mil"]["rural"], strict=True)]
    rural_bas = sum(1 for n in P["names"] if (I[n]["ecart_urbain_moins_rural"] or 0) > 0)
    acc60 = sorted([n for n in P["names"] if I[n]["effectif_dernier_sur_max"] is not None and I[n]["effectif_dernier_sur_max"] < 0.6],
                   key=lambda n: I[n]["effectif_dernier_sur_max"])
    perdus = sum(I[n]["eleves_perdus_depuis_max"] or 0 for n in acc60)
    filles = sum(I[n]["filles_manquantes_parite"] or 0 for n in P["names"])
    ips = {n: P["hist"][n][n1] for n in P["names"] if P["hist"][n][n1] is not None}
    pmin, pmax = min(ips, key=ips.get), max(ips, key=ips.get)
    p1 = [r["province"] for r in P["prio"] if r["priorite"] == 1]
    p2 = [r["province"] for r in P["prio"] if r["priorite"] == 2]
    mc = next(x for x in D["mc"] if x["r"] == "National")
    pt = sorted(D["ptbs"]["rows"], key=lambda x: x["t"]) if D.get("ptbs") else []
    sous = sorted([n for n, v in P["prev"].items() if v["statut"].startswith("sous")])
    an_prev = ya(P["prevAns"][-1])
    bt = D["bt"]; ret = next(b["modele"] for b in bt if b["retenu"] in (True, "True"))
    q = {b["horizon"]: b for b in bt if b["modele"] == ret}
    mods = sorted({b["modele"] for b in bt})
    liens = D.get("liens") or []
    sig_l = [l for l in liens if l["sig"]]
    typo = D.get("typo")
    groupes = Counter((r["g"], r["nom"]) for r in typo["rows"]) if typo else Counter()
    eq = a.equipe.replace("_", " ")
    L = []
    w = L.append

    w(f"# ÉDUCATION BF : disparités d'accès à l'école au Burkina Faso")
    w("")
    w(f"Data Challenge Burkina 2026, édition Éducation, **Défi 2**. Équipe **{eq}**. Document généré le {date.today().strftime('%d/%m/%Y')} "
      f"par `scripts/lisez_moi.py` à partir des sorties du pipeline : chaque chiffre ci-dessous est recalculé à chaque relance.")
    w("")
    w("Ce LISEZ-MOI suit le plan conseillé pour la documentation (sept parties), puis indique, critère par critère, où le jury "
      "trouvera la preuve de chaque point. Le dossier technique complet (15 pages) et la fiche de synthèse sont dans `05_interpretation`.")
    w("")
    w("| Partie | Où |")
    w("|---|---|")
    for i, t in enumerate(["Le défi", "Les données", "La préparation", "La méthode", "Les résultats", "La réponse au défi", "La reproduction"], 1):
        w(f"| {i}. {t} | [aller](#{i}-{t.lower().replace(' ', '-').replace('é', 'e').replace('à', 'a').replace('é', 'e')}) |")
    w("| Ce que le jury regarde | [aller](#ce-que-le-jury-regarde) |")
    w("")

    # 1
    w("## 1. Le défi")
    w("")
    w("**Question du Défi 2.** Où les écarts d'accès à l'école sont-ils les plus grands (filles et garçons, ville et campagne), et évoluent-ils ?")
    w("")
    w("**Notre reformulation.** Dans quelles régions et quelles provinces les enfants vont-ils le moins à l'école ? Où les filles "
      "sont-elles le plus en retard sur les garçons, et la campagne sur la ville ? Ces écarts se réduisent-ils depuis "
      f"{y0}, et où faut-il agir en premier ?")
    w("")
    w("Nous regardons trois écarts à la fois, au primaire et au préscolaire, de " f"{y0} à {y1} :")
    w("")
    w("- **l'écart entre territoires** : la part des enfants scolarisés (taux brut de scolarisation, TBS) et la perte d'élèves d'une province ;")
    w("- **l'écart entre filles et garçons** : l'indice de parité (IPS = filles ÷ garçons ; 1,00 = parité) ;")
    w("- **l'écart entre ville et campagne** : l'IPS en milieu urbain moins l'IPS en milieu rural.")
    w("")
    w("Les rôles de l'équipe : **Engineer** (collecte, nettoyage), **Architect** (modèle commun, liaison des territoires), "
      "**Analyst** (indicateurs, tableau de bord, interprétation), **Scientist** (liens, profils, prévision).")
    w("")

    # 2
    w("## 2. Les données")
    w("")
    w(f"Le registre des sources (`01_collecte`) recense **{len(reg)} fichiers**, chacun avec son empreinte sha256 et une décision pour le Défi 2 : "
      f"{dec['PRINCIPAL']} principal, {dec['RETENU']} retenus, {dec['SECONDAIRE']} secondaires, {dec['DOCUMENTATION']} de documentation, "
      f"{dec['ECARTE']} écartés (motif écrit pour chacun).")
    w("")
    w("| Source | Producteur | Ce que nous en tirons | Niveau |")
    w("|---|---|---|---|")
    w(f"| Base préscolaire et primaire {y0} à {y1} | DGESS / MENAPLN | élèves par sexe, statut, milieu, niveau ; TBS, TBA, TAP publiés | 13 anciennes régions |")
    w(f"| Annuaire statistique du primaire {y1} | DGESS | élèves par province, sexe, milieu et classe | 45 anciennes provinces |")
    w(f"| Projections de population 2020-2035 (RGPH 2019) | INSD | enfants de 6 à 11 ans par province et sexe ({D['ptbs']['annee'] if D.get('ptbs') else 'n.d.'}) | 45 provinces |")
    w("| Limites administratives COD-AB | IGB / OCHA (HDX) | cartes ; codes des anciennes et nouvelles entités | communes, provinces, régions |")
    w("")
    w("**Limites des données**")
    w("")
    for x in D["meta"]["limites"]:
        w(f"- {x}")
    w("- Les données sont agrégées et publiques : aucune information individuelle n'est utilisée.")
    w("")

    # 3
    w("## 3. La préparation")
    w("")
    w("| Ce que nous avons corrigé | Pourquoi |")
    w("|---|---|")
    w("| Tableaux Excel DGESS remis en format long (une ligne = une valeur), avec l'adresse de la cellule d'origine | pouvoir filtrer, contrôler et retrouver chaque chiffre |")
    w("| Sous-totaux et totaux gardés mais marqués | ne jamais les additionner deux fois |")
    w("| Année numérique seule lue comme année de **fin** (2025 = 2024-2025), vérifiée contre l'annuaire | éviter un décalage d'un an sur toute la série |")
    w("| Contrôle filles + garçons = total, et totaux nationaux comparés aux annuaires | repérer les erreurs de saisie |")
    w("| Noms de provinces harmonisés (Kouritenga, Komondjari, Balé, Boulkiemdé, Loroum…) | relier annuaire, population et carte |")
    w(f"| {len(sig)} IPS de province laissés vides et signalés (effectif tombé sous 10 % du maximum) | un IPS calculé sur une poignée d'élèves n'a pas de sens |")
    w(f"| Correspondance exacte des 45 anciennes provinces vers les {len(D['r17']['names'])} régions actuelles, commune par commune, par les codes COD-AB | donner des chiffres sur le découpage actuel sans estimation |")
    w("| Population 6-11 ans extraite des tableaux PDF de l'INSD, puis comparée à la population utilisée par la DGESS dans chaque région | calculer un TBS par province fiable |")
    w("| Sources hors sujet écartées (écoles géolocalisées, enseignants, post-primaire) | rester sur le Défi 2 |")
    w("| Valeurs manquantes jamais remplacées par zéro | ne pas inventer de données |")
    w("")
    w("Chaque règle est consignée dans le journal de nettoyage et chaque anomalie dans un fichier dédié (`02_nettoyage`).")
    w("")

    # 4
    w("## 4. La méthode")
    w("")
    w("| Méthode | Ce qu'elle fait | Pourquoi ce choix |")
    w("|---|---|---|")
    w("| Indicateurs d'écart | IPS, TBS par sexe, écart d'IPS ville moins campagne, élèves de la dernière année ÷ meilleure année depuis 2015 | lisibles par un décideur, comparables entre territoires |")
    w("| Règle de priorité | priorité 1 : IPS < 0,95 **et** effectifs < 60 % du maximum ; priorité 2 : un seul des deux | transparente et réglable dans l'outil |")
    w(f"| Liens (corrélation de Spearman) | {len(liens)} questions testées sur les 45 provinces, avec p-valeur | robuste aux valeurs extrêmes ; dit si deux écarts vont ensemble |")
    w(f"| Profils (k-moyennes) | {typo['k'] if typo else 'n.d.'} groupes de provinces sur l'accès, la parité et l'écart ville-campagne ; nombre de groupes choisi par le score de silhouette | regrouper les provinces qui appellent la même réponse |")
    w(f"| Prévision de l'IPS à 3 ans | {len(mods)} modèles comparés en se plaçant en 2019, 2020 et 2021 ; le plus fiable est retenu ({ret}) | une projection testée sur le passé, avec sa marge d'erreur |")
    w("")
    w(f"Erreur moyenne du modèle retenu : {f3(q[1]['mae'])} à un an, {f3(q[3]['mae'])} à trois ans. Marge à 80 % : ±{f3(q[1]['q80'])} à un an, "
      f"±{f3(q[3]['q80'])} à trois ans. Une projection prolonge la situation actuelle ; elle ne prédit pas l'effet d'une politique.")
    w("")

    # 5
    w("## 5. Les résultats")
    w("")
    w(f"- **L'écart le plus fort est territorial.** En {y1}, le TBS du primaire va de {pc(z[lo]['t'][n1])} ({lo}) à {pc(z[hi]['t'][n1])} ({hi}). "
      f"Au niveau national, il passe de {pc(z['National']['t'][0])} en {y0} à {pc(z['National']['t'][n1])}.")
    w(f"- **Il manque {nb(mc['plus'])} élèves** au primaire pour atteindre un TBS de 100 % ({nb(mc['pop'])} enfants d'âge primaire).")
    if pt:
        w(f"- **Par province**, le TBS va de {pc(pt[0]['t'])} ({pt[0]['p']}) à {pc(pt[-1]['t'])} ({pt[-1]['p']}).")
    w(f"- **Des provinces se vident** : {len(acc60)} sur 45 ont moins de 60 % des élèves de leur meilleure année ; ensemble, elles ont perdu {nb(perdus)} élèves.")
    w(f"- **Filles et garçons** : l'IPS national du primaire passe de {f2(D['nat']['pri'][0])} à {f2(D['nat']['pri'][n1])}, mais va de "
      f"{f2(ips[pmin])} ({pmin}) à {f2(ips[pmax])} ({pmax}) selon la province. Il faudrait inscrire {nb(filles)} filles de plus pour la parité partout.")
    w(f"- **Ville et campagne** : l'écart d'IPS passe de {f3(gap[0])} à {f3(gap[n1])}, mais la parité reste plus faible à la campagne dans {rural_bas} provinces sur 45.")
    w(f"- **Où agir d'abord** : {len(p1)} provinces en priorité 1 ({', '.join(p1)}) et {len(p2)} en priorité 2.")
    if sig_l:
        w(f"- **Les écarts se cumulent.** Sur {len(liens)} questions testées, {len(sig_l)} montrent un lien significatif (p < 0,05) :")
        for l in sig_l:
            w(f"  - {l['q']} Oui, corrélation de {f2(l['rho'])}.")
    w(f"- **Et demain** : si rien ne change, {len(sous)} provinces resteraient sous un IPS de 0,95 en {an_prev}, même dans le scénario haut.")
    w("")
    if groupes:
        w("| Profil de provinces | Nombre |")
        w("|---|---|")
        for (g, nom), c in sorted(groupes.items()):
            w(f"| {g}. {nom} | {c} |")
        w("")
    w("**Visualisations livrées**")
    w("")
    w("- La plateforme : une interface React servie par une API NestJS, ou une page autonome qui s'ouvre sans serveur "
      "(`tableau-de-bord.html` dans le zip de l'étape 4). Sept onglets : Accueil, Analyse, Tableau de bord, Carte, Aide à la décision, Prévision, Méthodes et données.")
    w("- La fiche de synthèse : une page nationale et 17 fiches régionales (PDF).")
    w("- Le dossier technique (Word, 15 pages au plus), avec cartes, courbes et tableaux.")
    w("")

    # 6
    w("## 6. La réponse au défi")
    w("")
    w("**Comment la solution aide un décideur**")
    w("")
    w("- **Ministère et DGESS** : choisir les provinces où rouvrir des classes et soutenir la scolarisation des filles, avec une règle transparente "
      "dont on règle les deux seuils dans l'onglet « Aide à la décision ».")
    w("- **Directions régionales** : imprimer la fiche d'une province (effectifs perdus, parité en ville et à la campagne, projection, filles à inscrire).")
    w("- **Partenaires et ONG** : repérer les zones où les écarts se cumulent et suivre leur évolution chaque année ; exporter les tables en CSV.")
    w("")
    w("**Limites** : un écart ne dit pas sa cause. La chute des effectifs signale une perte d'accès, le plus souvent des fermetures d'écoles, "
      "sans le démontrer. Le niveau province ne couvre que la dernière année ; il n'y a pas de niveau commune.")
    w("")
    w("**La suite possible** : croiser avec les fermetures d'écoles et les déplacements de population pour tester l'hypothèse sécuritaire ; "
      "descendre au niveau communal ; étendre au post-primaire ; mettre à jour chaque année avec le nouvel annuaire (le pipeline se relance tel quel).")
    w("")

    # 7
    w("## 7. La reproduction")
    w("")
    w("**Outils** : Windows avec PowerShell, Python 3.12 ou plus (`pip install -r requirements.txt`), et Node.js 20 ou plus pour la plateforme (facultatif).")
    w("")
    w("**Ordre des étapes**")
    w("")
    w("```powershell")
    w("pip install -r requirements.txt")
    w(f"powershell -ExecutionPolicy Bypass -File scripts\\lancer_pipeline.ps1 -Equipe {a.equipe} -AnneeNumerique fin")
    w("powershell -ExecutionPolicy Bypass -File plateforme\\lancer_plateforme.ps1     # puis http://localhost:3000")
    w("```")
    w("")
    w("| Étape | Dossier produit | Ce qui s'y fait |")
    w("|---|---|---|")
    w("| 01 Collecte | `01_collecte` | inventaire du Data Pack, registre des sources, empreintes sha256 |")
    w("| 02 Nettoyage | `02_nettoyage` | format long, contrôles des totaux, journal, anomalies, population INSD par province |")
    w("| 03 Transformation | `03_transformation` | parité, modèle commun région × année, liaison 45 provinces → 17 régions |")
    w("| 04 Analyse | `04_analyse` | indicateurs, liens, profils, priorités, prévision, tableau de bord, données de la plateforme |")
    w("| 05 Interprétation | `05_interpretation` | dossier technique, fiche de synthèse |")
    w("| Dépôt | `A_DEPOSER` | 20 fichiers nommés selon la convention, contrôlés, copiés avec vérification sha256 |")
    w("")
    w("Une étape seule : `-Etapes analyse,dashboard` par exemple. Les données brutes restent sur la machine de l'équipe : "
      "les étapes qui les lisent sont lancées en local, et la console n'affiche que des compteurs.")
    w("")

    # jury
    w("## Ce que le jury regarde")
    w("")
    w("| Critère | Ce que nous apportons | Où le vérifier |")
    w("|---|---|---|")
    w("| Caractère innovant de la solution | premiers chiffres du primaire sur les 17 régions actuelles par addition exacte des provinces ; TBS par province avec la population INSD ; "
      "écarts traduits en nombre d'enfants ; simulateur de ciblage réglable ; profils de provinces ; prévision testée sur le passé | onglets Carte, Aide à la décision, Prévision ; dossier, partie 11 |")
    w(f"| Pertinence et rigueur de l'analyse | {len(liens)} liens testés avec p-valeur ; {len(mods)} modèles de prévision comparés ; contrôles des totaux ; "
      f"{len(sig)} IPS non interprétables écartés et signalés ; aucune causalité affirmée | `04_analyse` (liens, typologie, backtest, signalements) ; dossier, parties 6 et 9 |")
    w("| Qualité de la visualisation et expérience utilisateur | sept onglets, cartes interactives avec zoom, courbes lissées, recherche de province, lien partageable, "
      "thème sombre, téléphone et tablette, clavier, mouvement réduit | `tableau-de-bord.html` (zip de l'étape 4) ou http://localhost:3000 |")
    w(f"| Impact possible sur le problème ciblé | {len(p1)} provinces prioritaires nommées, {nb(perdus)} élèves perdus et {nb(filles)} filles à inscrire chiffrés, "
      "fiches par province et par région prêtes à imprimer, pistes d'action | onglets Accueil et Aide à la décision ; fiche de synthèse |")
    w("| Faisabilité technique et opérationnelle | outils libres (Python, React, NestJS) ; page autonome sans serveur ni Internet ; exports CSV pour Excel ; "
      "mise à jour annuelle en une commande | partie 7 ; `plateforme/README.md` |")
    w("| Reproductibilité et qualité de la documentation | un pipeline en une commande ; chaque fichier nommé, horodaté et vérifié par sha256 ; un LISEZ-MOI par étape ; "
      "dossier de 15 pages ; ce document régénéré à chaque relance | `scripts/` ; `A_DEPOSER/GUIDE_DE_DEPOT.txt` ; ce LISEZ-MOI |")
    w("")
    out = os.path.join(R, "LISEZ-MOI.md")
    texte = "\n".join(L) + "\n"
    open(out, "w", encoding="utf-8").write(texte)
    open(os.path.join(R, "README.md"), "w", encoding="utf-8").write(texte)   # meme contenu, affiche sur la page du depot GitHub
    print(f"LISEZ-MOI general : {out} et README.md ({len(L)} lignes, 7 parties + criteres du jury)")


if __name__ == "__main__":
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    main()
