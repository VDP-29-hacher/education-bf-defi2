#!/usr/bin/env python3
"""RANGEMENT POUR LE DEPOT : copie le contenu de depot_final dans A_DEPOSER/, range comme sur la plateforme (une etape = un dossier,
puis la categorie Donnees / Code / Documentation), et ecrit le guide de depot (ordre, categorie, role, description, taille, sha256).

Entree  : depot_final/{donnees,code,documentation} + MANIFESTE.csv (produits par depot_final.py)
Sortie  : A_DEPOSER/01_collecte/Donnees/... ; A_DEPOSER/GUIDE_DE_DEPOT.txt ; A_DEPOSER/MANIFESTE.csv
Controle : chaque copie est verifiee par son empreinte sha256 contre le manifeste ; aucun fichier verrou (~$) ni temporaire.
Usage   : organiser_depot.py RACINE_DU_PROJET
"""
import csv, hashlib, os, re, shutil, stat, sys
from pathlib import Path

ETAPES = {"01": "01_collecte", "02": "02_nettoyage", "03": "03_transformation", "04": "04_analyse", "05": "05_interpretation"}
CATEGORIES = {"donnees": "Donnees", "code": "Code", "documentation": "Documentation"}
DESCRIPTIONS = [  # (motif dans le nom, description)
    ("registre-sources", "Registre des sources : producteur, publication, periode, decision et motif, sha256"),
    ("couverture-annees", "Annees couvertes par chaque source (annuaires 2016-2025)"),
    ("donnees-statistques", "Base DGESS prescolaire et primaire 2016-2025 (source principale, copie intacte)"),
    ("sources-retenues", "Sources retenues hors PDF : extractions CSV, fonds de carte COD-AB"),
    ("tableaux-long", "Table propre au format long : une ligne = une valeur observee"),
    ("controles-et-journaux", "Journal de nettoyage, anomalies, verification des totaux contre les annuaires"),
    ("annuaire-primaire-provinces", "Donnees par province (annuaire primaire 2024-2025) et controles ; population INSD si extraite"),
    ("dictionnaire-variables", "Dictionnaire des variables"),
    ("parite-effectifs", "Indices de parite filles / garcons calcules sur les effectifs"),
    ("tables-analyse-et-liaison", "Parite par taux, ecarts, tendances, liaison 13/17 regions, modele commun region x annee, GeoJSON"),
    ("architecture-pipeline", "Livrable Architect : parcours des donnees, modele de donnees, decisions, niveaux du modele, acces"),
    ("code-pipeline", "Tous les scripts du pipeline, README et requirements (relance en une commande)"),
    ("tableau-de-bord", "Solution : tableau de bord interactif hors connexion (Analyse, Tableau de bord, Carte, Aide a la decision, Prevision) et tables d'analyse"),
    ("_scientist_", "Role Data Scientist : code du modele, fiabilite des 4 modeles testes sur le passe, previsions par province"),
    ("documentation_v1", "Documentation (15 pages maximum) : comment la solution repond au Defi 2"),
    ("fiche-synthese", "Fiche de synthese nationale et 17 fiches regionales d'une page"),
    ("lisez-moi", "LISEZ-MOI de l'etape"),
]
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()


def decrire(nom):
    return next((d for m, d in DESCRIPTIONS if m in nom), "")


def main():
    racine = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    dep, cible = racine / "depot_final", racine / "A_DEPOSER"
    man = {r["fichier"]: r for r in csv.DictReader(open(dep / "MANIFESTE.csv", encoding="utf-8-sig"), delimiter=";")}
    if cible.exists():
        shutil.rmtree(cible, onerror=lambda f, p, e: (os.chmod(p, stat.S_IWRITE), f(p)))
    lignes, erreurs = [], []
    for cat_src, cat in CATEGORIES.items():
        for f in sorted((dep / cat_src).glob("*")):
            if f.name.startswith("~$") or f.name.startswith("."):
                erreurs.append(f"fichier temporaire ignore : {f.name} (fermer Word / Acrobat)"); continue
            m = re.search(r"_(0[1-5])-", f.name)
            if not m or f.name not in man:
                erreurs.append(f"hors convention ou absent du manifeste : {f.name}"); continue
            dossier = cible / ETAPES[m.group(1)] / cat
            dossier.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dossier / f.name)
            os.chmod(dossier / f.name, stat.S_IREAD | stat.S_IWRITE)
            ok = sha(dossier / f.name) == man[f.name]["sha256"]
            if not ok:
                erreurs.append(f"empreinte differente apres copie : {f.name}")
            role = re.search(r"_D2_([a-z]+)_", f.name).group(1)
            lignes.append({"etape": ETAPES[m.group(1)], "categorie": cat, "role": role, "fichier": f.name,
                           "taille_ko": round(f.stat().st_size / 1024), "sha256": man[f.name]["sha256"], "description": decrire(f.name)})
    lignes.sort(key=lambda r: (r["etape"], list(CATEGORIES.values()).index(r["categorie"]), r["fichier"]))
    shutil.copy2(dep / "MANIFESTE.csv", cible / "MANIFESTE.csv")
    total = sum(r["taille_ko"] for r in lignes)
    g = ["GUIDE DE DEPOT - Data Challenge Burkina 2026, Defi 2 - equipe " + (lignes[0]["fichier"].split("_0")[0] if lignes else ""), "",
         f"{len(lignes)} fichiers a deposer (limite plateforme : 20), {total / 1024:.1f} Mo au total (limite : 500 Mo).",
         "Chaque dossier ci-dessous correspond a un depot de la plateforme ; a l'interieur, le sous-dossier donne la categorie a choisir.",
         "Deposer dans l'ordre des etapes : le jury lit le parcours des donnees de 01 a 05.", "",
         "AVANT DE DEPOSER", "  - fermer Word et Acrobat (un fichier ouvert laisse un fichier verrou ~$ et bloque les relances) ;",
         "  - ne deposer QUE les fichiers de ce dossier (pas MANIFESTE.csv ni ce guide, sauf si la plateforme demande un document libre) ;",
         "  - verifier apres depot que chaque fichier apparait sous la bonne etape et la bonne categorie.", ""]
    for et in ETAPES.values():
        sel = [r for r in lignes if r["etape"] == et]
        if not sel:
            continue
        g.append(f"=== {et} ({len(sel)} fichier{'s' if len(sel) > 1 else ''}) ===")
        for r in sel:
            g.append(f"  [{r['categorie']}] {r['fichier']}")
            g.append(f"      role {r['role']} - {r['taille_ko']} Ko - {r['description']}")
        g.append("")
    g.append("Controle des copies : " + ("toutes les empreintes sha256 sont identiques au manifeste." if not erreurs else "PROBLEMES :"))
    g += [f"  - {e}" for e in erreurs]
    (cible / "GUIDE_DE_DEPOT.txt").write_text("\n".join(g) + "\n", encoding="utf-8")
    with open(cible / "GUIDE_DE_DEPOT.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(lignes[0].keys()), delimiter=";"); w.writeheader(); w.writerows(lignes)
    print(f"A_DEPOSER : {len(lignes)} fichiers ranges en {len({r['etape'] for r in lignes})} etapes ; {total / 1024:.1f} Mo ; "
          f"{'copies verifiees (sha256)' if not erreurs else str(len(erreurs)) + ' probleme(s)'}")
    for e in erreurs:
        print("  -", e)
    return 0 if not erreurs else 3


if __name__ == "__main__":
    sys.exit(main())
