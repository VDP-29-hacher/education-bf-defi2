#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PREPARATION DU PAQUET A DEPOSER SUR LA PLATEFORME (equation.africadataentry.com) - etape 01_collecte.

Contraintes de la plateforme (capture d'ecran) :
  - 20 fichiers maximum et 500 Mo au total pour TOUT l'espace de l'equipe (toutes les etapes !) ;
  - categorie "Donnees" : .csv .tsv .xlsx .xls .json .parquet .zip uniquement (donc PDF, GeoJSON... dans un .zip).
Le depot 01_collecte (centaines de fichiers, >1 Go) est un dossier de TRAVAIL, pas le paquet a deposer.

Ce script construit, SANS MODIFIER 01_collecte, un paquet conforme et leger :
  1. registre des sources (CSV annote)                         -> a deposer tel quel
  2. couverture des annees (CSV)                                -> a deposer tel quel
  3. base principale (xlsx, decision PRINCIPAL)                 -> a deposer telle quelle
  4. un .zip des sources RETENUES non-PDF (CSV extraits, cartes GeoJSON...) + LISEZ-MOI + manifeste sha256
  5. (option --avec-pdf) un .zip des PDF retenus ; par defaut les PDF restent references dans le registre
     (producteur, lien, sha256) mais ne sont pas envoyes : ils viennent du Data Pack de l'organisateur.
Verifie : nombre de fichiers, poids, extensions, integrite des zip (sha256 des membres).

Usage : python preparer_depot.py DOSSIER_01_COLLECTE --equipe Burkina_Novation [--sortie DOSSIER] [--budget-mo 120] [--avec-pdf]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

EXT_DONNEES = {".csv", ".tsv", ".xlsx", ".xls", ".json", ".parquet", ".zip"}
Mo = 1024 * 1024


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def faire_zip(cible: Path, membres: list, extras: dict) -> list:
    """Zip deflate. membres = [(chemin, nom_dans_zip)] ; extras = {nom: texte}. Retourne le manifeste."""
    manifeste = []
    with zipfile.ZipFile(cible, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for chemin, nom in membres:
            z.write(chemin, nom)
            manifeste.append((nom, sha256(chemin), chemin.stat().st_size))
        for nom, texte in extras.items():
            z.writestr(nom, texte)
    return manifeste


def texte_manifeste(m: list) -> str:
    return "fichier;sha256;taille_octets\n" + "".join(f"{n};{h};{t}\n" for n, h, t in m)


def verifier_zip(cible: Path, manifeste: list) -> bool:
    with zipfile.ZipFile(cible) as z:
        if z.testzip() is not None:
            return False
        attendu = {n: h for n, h, _ in manifeste}
        for nom, h in attendu.items():
            if hashlib.sha256(z.read(nom)).hexdigest() != h:
                return False
    return True


def main(argv=None) -> int:
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Construit le paquet conforme aux limites de la plateforme")
    ap.add_argument("depot", help="dossier 01_collecte")
    ap.add_argument("--equipe", required=True)
    ap.add_argument("--defi", default="D2")
    ap.add_argument("--role", default="engineer")
    ap.add_argument("--sortie", help="dossier de sortie (defaut : ../depot_plateforme a cote de 01_collecte)")
    ap.add_argument("--budget-mo", type=float, default=120.0,
                    help="poids max de CE paquet (defaut 120 Mo) : l'espace de 500 Mo sert a toutes les etapes")
    ap.add_argument("--max-fichiers", type=int, default=6, help="nombre max de fichiers de CE paquet (defaut 6 sur 20)")
    ap.add_argument("--avec-pdf", action="store_true", help="envoyer aussi les PDF retenus (lourd)")
    a = ap.parse_args(argv)

    depot = Path(a.depot)
    regs = sorted(depot.glob("*_registre-sources_v1.csv"))
    if not regs:
        print("ERREUR : registre introuvable dans", depot)
        return 1
    reg = regs[-1]
    couv = sorted(depot.glob("*_couverture-annees_v1.csv"))
    sortie = Path(a.sortie) if a.sortie else depot.parent / "depot_plateforme"
    sortie.mkdir(parents=True, exist_ok=True)
    prefixe = f"{a.equipe}_01-collecte_{a.defi}_{a.role}"

    with open(reg, encoding="utf-8-sig", newline="") as f:
        lignes = list(csv.DictReader(f, delimiter=";"))
    if not lignes or "decision_defi2" not in lignes[0]:
        print("ERREUR : registre non annote. Lancez d'abord annoter_registre.py")
        return 1
    retenus = [r for r in lignes if r["decision_defi2"] in ("PRINCIPAL", "RETENU") and r["fichier_depose"]]
    manquants = [r["fichier_depose"] for r in retenus if not (depot / r["fichier_depose"]).is_file()]
    if manquants:
        print("ERREUR : fichiers retenus absents du depot :", manquants[:5])
        return 1

    produits = []                                           # (chemin, role)
    for src in [reg] + couv[-1:]:
        shutil.copy2(src, sortie / src.name)
        produits.append(sortie / src.name)
    principal = [r for r in retenus if r["decision_defi2"] == "PRINCIPAL"]
    for r in principal:
        shutil.copy2(depot / r["fichier_depose"], sortie / r["fichier_depose"])
        produits.append(sortie / r["fichier_depose"])

    lisez = (f"PAQUET DEPOSE - etape 01_collecte - equipe {a.equipe}, defi {a.defi}, role {a.role}\n"
             f"Genere le {datetime.now():%Y-%m-%d %H:%M} par preparer_depot.py\n\n"
             "Ce paquet est un extrait leger du depot de travail 01_collecte (1 Go). Il contient :\n"
             f"- {reg.name} : registre des sources (producteur, publication, periode, lien, decision et motif, sha256)\n"
             "- le fichier de couverture des annees 2016-2025\n"
             "- la base principale DGESS (xlsx)\n"
             "- le zip des sources retenues non-PDF (extractions CSV de travail, fonds de carte COD-AB)\n"
             "Les PDF retenus (annuaires DGESS, rapports INSD) ne sont pas renvoyes : ils sont references dans le\n"
             "registre (producteur, lien, empreinte sha256) et viennent du Data Pack de l'organisateur.\n"
             "Les CSV extraits des PDF sont des extractions automatiques : a controler contre le PDF.\n"
             "Le manifeste.csv du zip donne l'empreinte sha256 de chaque fichier.\n")
    notes = ""
    lm_depot = depot / "LISEZ-MOI.txt"
    if lm_depot.exists():
        t = lm_depot.read_text(encoding="utf-8")
        i = t.find("NOTES DE L'EQUIPE")
        notes = "\n" + t[i:] if i >= 0 else ""

    autres = [r for r in retenus if r["decision_defi2"] == "RETENU"]
    groupes = [("sources-retenues-donnees-cartes", [r for r in autres if not r["fichier_depose"].lower().endswith(".pdf")])]
    if a.avec_pdf:
        groupes.append(("sources-retenues-pdf", [r for r in autres if r["fichier_depose"].lower().endswith(".pdf")]))
    for nom_g, rs in groupes:
        if not rs:
            continue
        membres = [(depot / r["fichier_depose"], r["fichier_depose"]) for r in rs]
        cible = sortie / f"{prefixe}_{nom_g}_v1.zip"
        m = faire_zip(cible, membres, {"LISEZ-MOI.txt": lisez + notes})
        z_man = texte_manifeste(m)
        with zipfile.ZipFile(cible, "a", zipfile.ZIP_DEFLATED) as z:
            z.writestr("manifeste.csv", z_man)
        if not verifier_zip(cible, m):
            print("ERREUR : controle d'integrite du zip echoue :", cible.name)
            return 2
        produits.append(cible)
        print(f"zip {cible.name} : {len(rs)} fichiers -> {cible.stat().st_size / Mo:.1f} Mo (integrite verifiee)")

    (sortie / "LISEZ-MOI.txt").write_text(lisez + notes, encoding="utf-8")

    total = sum(p.stat().st_size for p in produits)
    print("\n== PAQUET PRET (a deposer dans la categorie « Donnees ») dans", sortie)
    for p in produits:
        flag = "" if p.suffix.lower() in EXT_DONNEES else "   <-- EXTENSION NON AUTORISEE"
        print(f"  {p.stat().st_size / Mo:8.2f} Mo  {p.name}{flag}")
    print(f"  {'-' * 40}\n  {total / Mo:8.2f} Mo  {len(produits)} fichier(s) (limites de ce paquet : {a.max_fichiers} fichiers, {a.budget_mo:.0f} Mo ;"
          " plateforme : 20 fichiers, 500 Mo pour toutes les etapes)")
    print("  + LISEZ-MOI.txt a deposer dans Documentation (ou dans Code, .txt autorise) ; il est aussi dans le zip.")
    ok = len(produits) <= a.max_fichiers and total <= a.budget_mo * Mo and all(p.suffix.lower() in EXT_DONNEES for p in produits)
    print("CONFORME" if ok else "NON CONFORME : reduisez le contenu (voir les limites ci-dessus)")
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
