#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DEPOT FINAL sur la plateforme equation.africadataentry.com : PREPARER les paquets et VERIFIER avant de deposer.

Contraintes (PDF du challenge + capture de la plateforme) :
  - modele de nom EQUIPE_ETAPE_DEFI_ROLE_description_vN.ext ; pas d'espace ni d'accent ; versions numerotees ;
  - un LISEZ-MOI par depot ; une etape = un depot (01_collecte, 02_nettoyage, 03_transformation...) ;
  - 20 fichiers maximum et 500 Mo au total pour toute l'equipe ; categorie Donnees : .csv .tsv .xlsx .xls .json .parquet .zip ;
    categorie Code : .zip .py .r .ipynb .sql .js .ts .java .txt.

  python depot_final.py preparer --equipe Burkina_Novation      construit depot_final/{donnees,code,documentation} + MANIFESTE.csv puis verifie
  python depot_final.py verifier [--dossier depot_final]   controle automatique (noms, extensions, limites, CSV, zip, texte suspect,
                                                            chemins personnels, coherence des chiffres, completude du registre)
La console n'affiche que des compteurs et des noms de fichiers.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import os
import re
import shutil
import stat
import subprocess
import sys
import zipfile
from importlib import metadata
from pathlib import Path

NOM_RX = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)*?_0[1-5]-[a-z0-9]+_D[1-3]_(engineer|architect|analyst|scientist)_[a-z0-9]+(?:-[a-z0-9]+)*_v\d+\.[a-z0-9]+$")
EXT = {"donnees": {"csv", "tsv", "xlsx", "xls", "json", "parquet", "zip"},
       "code": {"zip", "py", "r", "ipynb", "sql", "js", "ts", "java", "txt"},
       "documentation": {"pdf", "docx", "md", "txt", "html"}}
MAX_FICHIERS, MAX_MO = 20, 500
INTERDITS = [(re.compile(r"NOTE\s+FOR\s+ANY", re.I), "texte adresse a un assistant automatique"),
             (re.compile(r"[A-Za-z]:\\Users\\", re.I), "chemin personnel Windows (nom d'utilisateur)"),
             (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "adresse e-mail")]
PERSO = re.compile(r"[A-Za-z]:\\Users\\[^\\\s;\"]+\\Downloads\\challenge\\")
RX_IA = re.compile(r"NOTE\s+FOR\s+ANY.*", re.I | re.S)       # texte adresse a un assistant automatique (jusqu'a la fin de la cellule)
MARQUE = "[texte adresse a un assistant automatique retire]"
Mo = 1024 * 1024


def assainir_csv(t: str) -> str:
    """Retire les chemins personnels et, cellule par cellule, le texte adresse aux assistants automatiques."""
    t = PERSO.sub("", t)
    sortie = io.StringIO()
    w = csv.writer(sortie, delimiter=";", lineterminator="\r\n")
    for ligne in csv.reader(io.StringIO(t), delimiter=";"):
        w.writerow([RX_IA.sub(MARQUE, c) for c in ligne])
    return sortie.getvalue()


def assainir_texte(t: str) -> str:
    return RX_IA.sub(MARQUE, PERSO.sub("", t))


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def supprimer(chemin: Path):
    """rmtree qui leve l'attribut lecture seule (les copies de la collecte sont en lecture seule sous Windows)."""
    def forcer(fonction, p, *_):
        os.chmod(p, stat.S_IWRITE)
        fonction(p)
    try:
        shutil.rmtree(chemin, onexc=forcer)
    except TypeError:                                     # Python < 3.12
        shutil.rmtree(chemin, onerror=forcer)


def copier(src: Path, dst: Path):
    """Copie ; pour un texte (csv, txt), retire les chemins personnels (nom d'utilisateur Windows)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() == ".csv":
        dst.write_text(assainir_csv(src.read_text(encoding="utf-8-sig")), encoding="utf-8-sig", newline="")
    elif src.suffix.lower() == ".txt":
        dst.write_text(assainir_texte(src.read_text(encoding="utf-8-sig")), encoding="utf-8")
    else:
        shutil.copyfile(src, dst)                         # copie le contenu seulement : pas l'attribut lecture seule
    os.chmod(dst, stat.S_IWRITE | stat.S_IREAD)


def faire_zip(cible: Path, membres: list, extras: dict | None = None):
    """membres = [(chemin_source, nom_dans_zip)] ; textes assainis ; extras = {nom: texte}."""
    with zipfile.ZipFile(cible, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for src, nom in membres:
            if src.suffix.lower() == ".csv":
                z.writestr(nom, assainir_csv(src.read_text(encoding="utf-8-sig")).encode("utf-8"))
            elif src.suffix.lower() in (".txt", ".py", ".ps1", ".md"):
                z.writestr(nom, PERSO.sub("", src.read_text(encoding="utf-8-sig")).encode("utf-8"))
            else:
                z.write(src, nom)
        for nom, texte in (extras or {}).items():
            z.writestr(nom, texte)


# --------------------------------------------------------------------------------------------------
# PREPARER
# --------------------------------------------------------------------------------------------------
def preparer(racine: Path, eq: str, defi: str, role: str) -> int:
    sorties = racine / "depot_final"
    if sorties.exists():
        supprimer(sorties)
    don, cod, doc = (sorties / x for x in ("donnees", "code", "documentation"))
    for d in (don, cod, doc):
        d.mkdir(parents=True)
    p = lambda etape, desc, ext: f"{eq}_{etape}_{defi}_{role}_{desc}_v1.{ext}"
    c01, c02, c03, scripts = racine / "01_collecte", racine / "02_nettoyage", racine / "03_transformation", racine / "scripts"

    # ---- 01 collecte : on reutilise preparer_depot.py (registre annote, couverture, base principale, zip des sources retenues) ----
    tmp = sorties / "_tmp01"
    r = subprocess.run([sys.executable, str(scripts / "preparer_depot.py"), str(c01), "--equipe", eq, "--sortie", str(tmp)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode not in (0,):
        print("ERREUR preparer_depot.py :", r.stdout[-400:], r.stderr[-400:])
        return 1
    for f in sorted(tmp.iterdir()):
        if f.name == "LISEZ-MOI.txt":
            copier(f, doc / p("01-collecte", "lisez-moi", "txt"))
        else:
            copier(f, don / f.name)                       # registre : chemins personnels retires
    supprimer(tmp)

    # ---- 02 nettoyage ----
    longue = next(c02.glob("*_tableaux-long_v1.csv"), None)
    if longue is None:
        print("ERREUR : table propre introuvable dans 02_nettoyage")
        return 1
    copier(longue, don / longue.name)
    membres02 = [(f, f.name) for pat in ("*_journal-nettoyage_v1.csv", "*_anomalies_v1.csv",
                                          "*_verification-total-annuaire-*-20??-20??_v1.csv") for f in sorted(c02.glob(pat))]
    lm02 = (c02 / "LISEZ-MOI.txt").read_text(encoding="utf-8") if (c02 / "LISEZ-MOI.txt").exists() else ""
    lm02 += ("\nVerifications des totaux : les totaux nationaux de la base sont cherches dans les annuaires 2024-2025 (prescolaire "
             "et primaire) et 2017-2018 (primaire). Prescolaire : 10 annees sur 10 retrouvees. Primaire : annee 2017-2018 non "
             "retrouvee dans les annuaires (a verifier).\nFormat : separateur ';', UTF-8, decimales au POINT.\n")
    faire_zip(don / p("02-nettoyage", "controles-et-journaux", "zip"), membres02, {"LISEZ-MOI.txt": lm02})
    (doc / p("02-nettoyage", "lisez-moi", "txt")).write_text(lm02, encoding="utf-8")

    # ---- 02 (suite) : extraction par PROVINCE depuis l'annuaire (table longue + controles) ----
    fprov = sorted(c02.glob("*annuaire-primaire-*-provinces_v1.csv"))      # table longue + fichier de controles
    tab_prov = [x for x in fprov if "controles" not in x.name]
    if tab_prov:
        lm_prov = "EXTRACTION PAR PROVINCE - annuaire statistique de l'enseignement primaire 2024-2025 (DGESS)\n\nTable longue : tableaux 'historique des effectifs par province' (10 annees), 'par region', 'effectifs et redoublants par classe' (historique)\net 'repartition des eleves et redoublants par niveau d'etudes et sexe' (public, prive, public + prive, urbain, rural), 45 anciennes provinces.\nMethode : extraction par script local depuis l'extraction CSV du PDF ; chaque ligne garde son numero de ligne source.\nControles : G+F=T ; somme des provinces = Total Region ; urbain+rural = ensemble ; public+prive = ensemble ; somme des classes = Total ;\nrepartition = historique pour 2024. Tous a zero ecart pour la repartition 2024-2025.\nIncoherences de l'annuaire signalees, non corrigees : 2 ecarts < 1 % entre provinces et region (Centre-Ouest) ; l'historique par classe\ndiffere de l'historique des effectifs dans 102 cas sur 1344 -> il n'est pas utilise dans l'analyse ; 1 total national urbain incoherent ;\n16 cellules vides (colonnes redoublants). Orthographes de l'annuaire : Kourittenga = Kouritenga, Komandjari = Komondjari.\nFormat : separateur ';', UTF-8, decimales au POINT.\n"
        pop = sorted(c02.glob("*population-insd-provinces_v1.csv"))     # projections INSD par province (si l'equipe les a extraites)
        if pop:
            lm_prov += ("\nPOPULATION INSD PAR PROVINCE : projections RGPH 2019 (2020-2035) extraites par scripts/extraction_population_insd.py "
                        "(lance par l'equipe) ; table population-insd-provinces + controles (provinces trouvees, doublons, valeurs suspectes).\n")
        faire_zip(don / p("02-nettoyage", "annuaire-primaire-provinces", "zip"),
                  [(x, x.name) for x in tab_prov + [y for y in fprov if "controles" in y.name] + pop], {"LISEZ-MOI.txt": lm_prov})

    # ---- 03 transformation ----
    for pat in ("*_parite-effectifs_v1.csv", "*_dictionnaire-variables_v1.csv"):
        f = next(c03.glob(pat), None)
        if f:
            copier(f, don / f.name)
    inclus = ("*_ecarts-par-dimension_v1.csv", "*_classement-regions_v1.csv", "*_tendances_v1.csv", "*_parite-taux_v1.csv",
              "*_controle-ips_v1.csv", "*_journal-transformation_v1.csv", "*_liaison-officielle-*_v1.csv",
              "*_correspondance-13-vers-17-officielle_v1.csv", "*_comparaison-reconstruction-officielle_v1.csv",
              "*_anomalies-liaison-officielle_v1.csv", "*_anciennes-regions-13-officiel_v1.geojson", "*_anciennes-provinces-officiel_v1.geojson",
              "*_validation-ancien-decoupage_v1.csv", "*_liaison-communes_v1.csv", "*_liaison-provinces-nouvelles_v1.csv",
              "*_correspondance-13-vers-17-communes_v1.csv", "*_anomalies-liaison-communes_v1.csv",
              "*_architect_modele-commun-region-annee_v1.csv")
    membres03 = [(f, f.name) for pat in inclus for f in sorted(c03.glob(pat))]
    lm03 = (c03 / "LISEZ-MOI.txt").read_text(encoding="utf-8") if (c03 / "LISEZ-MOI.txt").exists() else ""
    lm03 += ("\nLIAISON 13 anciennes / 17 nouvelles regions : methode officielle par les codes (adm*_pcode_old du classeur COD-AB, "
             "Guide du Data Pack). Resultat : 0 commune a cheval ; 3 anciennes regions decoupees (Boucle du Mouhoun, Est, Sahel). "
             "La reconstruction par les noms de communes (fichiers PDI) est conservee comme controle : 349 communes sur 351 "
             "identiques a l'officiel (2 homonymes).\nTable des 45 provinces d'avant la reforme : validee contre adm2_name_old. "
             "Format : separateur ';', UTF-8, decimales au POINT.\n")
    faire_zip(don / p("03-transformation", "tables-analyse-et-liaison", "zip"), membres03, {"LISEZ-MOI.txt": lm03})
    (doc / p("03-transformation", "lisez-moi", "txt")).write_text(lm03, encoding="utf-8")

    # ---- 04 analyse et 05 interpretation (fichiers deja nommes selon la regle ; role analyst) ----
    c04, c05 = racine / "04_analyse", racine / "05_interpretation"
    if c04.exists() and c05.exists():
        zdb = next(c04.glob("*_tableau-de-bord_v1.zip"), None)
        if zdb:
            copier(zdb, don / zdb.name)
            # les tables de l'etape 4 (regions, provinces, classes) voyagent dans le zip du tableau de bord (economie de fichiers)
            with zipfile.ZipFile(don / zdb.name, "a", zipfile.ZIP_DEFLATED) as zadd:
                for tab in sorted(c04.glob("*_analyst_*_v1.csv")):
                    zadd.write(tab, tab.name)
                lm_src = next(c04.glob("*_analyst_lisez-moi_v1.txt"), None)
                if lm_src:
                    zadd.write(lm_src, "LISEZ-MOI-etape4.txt")
        # role Data Scientist : son propre paquet (code + tables + LISEZ-MOI)
        zsc = next(c04.glob("*_scientist_*_v1.zip"), None)
        if zsc:
            copier(zsc, don / zsc.name)
        lm04 = next(c04.glob("*_lisez-moi_v1.txt"), None)
        if lm04:
            copier(lm04, doc / lm04.name)
        for pat in ("*_fiche-synthese_v1.pdf", "*_documentation_v1.docx"):
            f = next(c05.glob(pat), None)
            if f:
                copier(f, doc / f.name)
        arch = next((racine / "architecture").glob("*_architecture-pipeline_v1.pdf"), None)
        if arch:
            copier(arch, doc / arch.name)
    else:
        print("INFO : 04_analyse / 05_interpretation absents : etapes 4 et 5 non incluses.")

    # ---- code : scripts + reference + README + requirements ----
    exclus = {"liaison_regions.py"}                       # remplace par liaison_officielle.py (par les codes)
    membres = [(f, f"scripts/{f.name}") for f in sorted(scripts.glob("*.py")) if f.name not in exclus]
    membres += [(f, f"scripts/{f.name}") for f in sorted(scripts.glob("*.ps1"))]
    membres += [(f, f"scripts/reference/{f.name}") for f in sorted((scripts / "reference").glob("*.csv"))]
    # plateforme React + NestJS : sources seulement (ni node_modules, ni fichiers compiles)
    pf = racine / "plateforme"
    if pf.exists():
        ignores = {"node_modules", "dist", "dist-autonome"}
        membres += [(f, "plateforme/" + f.relative_to(pf).as_posix()) for f in sorted(pf.rglob("*"))
                    if f.is_file() and not ignores.intersection(f.relative_to(pf).parts)]
    def ver(m):
        try:
            return f"{m}=={metadata.version(m)}"
        except Exception:
            return m
    reqs = "\n".join(ver(m) for m in ("pandas", "numpy", "scipy", "scikit-learn", "openpyxl", "pypdf", "matplotlib", "reportlab", "python-docx")) + "\n"
    readme = ("RELANCER LE TRAVAIL - equipe " + eq + " - Defi 2 (parite filles-garcons, ecart urbain-rural)\n\n"
              "Prerequis : Python 3.12, pip install -r requirements.txt (pypdf est facultatif : lecture directe d'un PDF).\n"
              "Dossiers attendus (a cote de scripts/) : donnees_brutes/ (Data Pack + base DGESS), puis 01_collecte, 02_nettoyage,\n"
              "03_transformation sont crees par les scripts.\n\n"
              "Ordre des etapes (Windows PowerShell) :\n"
              "  powershell -ExecutionPolicy Bypass -File scripts\\lancer_pipeline.ps1 -Etapes collecte,annoter -Equipe " + eq + "\n"
              "  powershell -ExecutionPolicy Bypass -File scripts\\lancer_pipeline.ps1 -AnneeNumerique fin -Equipe " + eq + "\n"
              "     (nettoyage -> verification des totaux -> transformation -> validation -> liaisons)\n"
              "  powershell -ExecutionPolicy Bypass -File scripts\\lancer_pipeline.ps1 -Etapes analyse,interpretation,documentation -Equipe " + eq + "\n"
              "     (04_analyse : indicateurs, figures, tableau de bord ; 05_interpretation : fiche d'une page, dossier technique)\n"
              "  python scripts\\depot_final.py preparer --equipe " + eq + "     (paquets a deposer + verification)\n\n"
              "Scripts : collecte_template.py (etape 1), annoter_registre.py, profil_structure.py (structure sans valeurs),\n"
              "nettoyage_template.py (etape 2), verifier_total_annuaire.py, transformation_template.py (etape 3),\n"
              "liaison_officielle.py (13/17 regions par les codes), liaison_communes.py (controle par les noms),\n"
              "valider_decoupage.py, preparer_depot.py, depot_final.py ; niveau province : profil_csv.py (structure sans valeurs),\n"
              "extraction_provinces.py (annuaire -> 45 provinces, A LANCER PAR L'EQUIPE), analyse_provinces.py ; etapes 4-5 : analyse_template.py,\n"
              "dashboard_template.py, interpretation_template.py, documentation_template.py, architecture_template.py.\n"
              "Etapes du lanceur pour le niveau province : -Etapes provinces ; puis -Etapes analyse,analyse_provinces,dashboard,interpretation,documentation,architecture,depot.\n\n"
              "Plateforme React + NestJS (Node.js 20+) : powershell -ExecutionPolicy Bypass -File plateforme\\lancer_plateforme.ps1\n"
              "     puis http://localhost:3000 (API : /api/sante, /api/priorites?ips=0.95&acces=0.6 ; voir plateforme/README.md).\n\n"
              "Regles respectees : les scripts sont lances par l'equipe en local ; la console n'affiche que des compteurs ;\n"
              "aucune donnee brute n'est envoyee a une IA (voir la note 6 du LISEZ-MOI de la collecte).\n"
              "Convention des annees : annee scolaire AAAA-AAAA ; une annee numerique seule du classeur DGESS est une annee de FIN\n"
              "(2025 = 2024-2025), confirmee par comparaison avec l'annuaire 2024-2025 (option --annee-numerique fin).\n")
    faire_zip(cod / p("03-transformation", "code-pipeline", "zip"), membres, {"README_RELANCER.txt": readme, "requirements.txt": reqs})

    # ---- manifeste ----
    lignes = []
    for cat in ("donnees", "code", "documentation"):
        for f in sorted((sorties / cat).iterdir()):
            lignes.append({"fichier": f.name, "categorie": cat, "taille_octets": f.stat().st_size, "sha256": sha256(f)})
    with open(sorties / "MANIFESTE.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["fichier", "categorie", "taille_octets", "sha256"], delimiter=";")
        w.writeheader()
        w.writerows(lignes)
    print(f"{len(lignes)} fichiers prepares dans {sorties}")
    return verifier(sorties)


# --------------------------------------------------------------------------------------------------
# VERIFIER
# --------------------------------------------------------------------------------------------------
def verifier(dossier: Path) -> int:
    bilan = {"PASS": 0, "WARN": 0, "FAIL": 0}

    def res(niv, msg):
        bilan[niv] += 1
        print(f"[{niv}] {msg}")

    fichiers = [(cat, f) for cat in ("donnees", "code", "documentation") for f in sorted((dossier / cat).glob("*"))]
    if not fichiers:
        print("ERREUR : aucun fichier dans", dossier)
        return 1
    total = sum(f.stat().st_size for _, f in fichiers)
    (res("PASS", f"{len(fichiers)} fichiers (limite {MAX_FICHIERS}, etapes 1 a 5 incluses)")
     if len(fichiers) <= MAX_FICHIERS else res("FAIL", f"{len(fichiers)} fichiers > {MAX_FICHIERS}"))
    (res("PASS", f"{total / Mo:.1f} Mo au total (limite {MAX_MO} Mo)") if total <= MAX_MO * Mo else res("FAIL", f"{total / Mo:.1f} Mo > {MAX_MO}"))

    textes_cache = {}
    for cat, f in fichiers:
        ext = f.suffix.lower().lstrip(".")
        if not NOM_RX.match(f.name):
            res("FAIL", f"nom non conforme au modele EQUIPE_ETAPE_DEFI_ROLE_description_vN : {f.name}")
        if ext not in EXT[cat]:
            res("FAIL", f"extension .{ext} non autorisee en categorie {cat} : {f.name}")
        elif cat == "documentation":
            res("WARN", f"extensions de la categorie Documentation non confirmees (capture coupee) : {f.name}")
        if f.stat().st_size == 0:
            res("FAIL", f"fichier vide : {f.name}")
        # contenu
        corps = []
        if ext == "csv":
            try:
                with open(f, encoding="utf-8-sig", newline="") as fh:
                    lignes = list(csv.reader(fh, delimiter=";"))
                largeur = {len(l) for l in lignes}
                if len(lignes) < 2:
                    res("FAIL", f"CSV sans donnees : {f.name}")
                elif len(largeur) > 1:
                    res("FAIL", f"CSV aux lignes de largeurs differentes {sorted(largeur)} : {f.name}")
                else:
                    res("PASS", f"CSV lisible, {len(lignes) - 1} lignes x {len(lignes[0])} colonnes : {f.name[:70]}")
                textes_cache[f.name] = lignes
                corps.append(f.read_text(encoding="utf-8-sig"))
            except Exception as e:
                res("FAIL", f"CSV illisible ({e}) : {f.name}")
        elif ext == "zip":
            try:
                with zipfile.ZipFile(f) as z:
                    if z.testzip() is not None:
                        res("FAIL", f"zip corrompu : {f.name}")
                        continue
                    noms = z.namelist()
                    mauvais = [n for n in noms if n.startswith("/") or ".." in n.split("/") or "__pycache__" in n or n.endswith(".pyc")]
                    if mauvais:
                        res("FAIL", f"zip avec chemins ou fichiers indesirables {mauvais[:3]} : {f.name}")
                    if not any(n.endswith(("LISEZ-MOI.txt", "README_RELANCER.txt")) for n in noms):
                        res("FAIL", f"pas de LISEZ-MOI dans le zip : {f.name}")
                    else:
                        res("PASS", f"zip intact, {len(noms)} membres, LISEZ-MOI present : {f.name[:60]}")
                    for n in noms:
                        if n.lower().endswith((".csv", ".txt", ".py", ".ps1", ".md")):
                            corps.append(z.read(n).decode("utf-8-sig", errors="replace"))
                        if n.endswith("journal-nettoyage_v1.csv"):
                            textes_cache["journal02"] = list(csv.reader(io.StringIO(z.read(n).decode("utf-8-sig")), delimiter=";"))
            except Exception as e:
                res("FAIL", f"zip illisible ({e}) : {f.name}")
        elif ext in ("txt", "py"):
            corps.append(f.read_text(encoding="utf-8-sig", errors="replace"))
        brut = "sources-retenues" in f.name                  # copies fideles des originaux du Data Pack
        for rx, quoi in INTERDITS:
            n = sum(1 for t in corps if rx.search(t))
            if n == 0:
                continue
            if brut and ("assistant automatique" in quoi or "e-mail" in quoi):
                res("WARN", f"{n} fichier(s) des sources brutes copiees contiennent : {quoi} "
                            f"(present dans les originaux publics du Data Pack, laisse intact) : {f.name[:40]}")
            else:
                res("FAIL", f"{quoi} trouve dans {n} fichier(s) : {f.name}")

    # coherence : lignes de la table propre = ligne 'sortie' du journal
    longue = next((v for k, v in textes_cache.items() if k.endswith("_tableaux-long_v1.csv")), None)
    jr = textes_cache.get("journal02")
    if longue and jr:
        ent = jr[0]
        sortie = next((r for r in jr[1:] if r and r[ent.index("etape")] == "sortie"), None)
        if sortie:
            attendu = int(float(sortie[ent.index("apres")]))
            (res("PASS", f"table propre : {len(longue) - 1} lignes = ligne 'sortie' du journal ({attendu})")
             if attendu == len(longue) - 1 else res("FAIL", f"table propre {len(longue) - 1} lignes <> journal {attendu}"))
    # vocabulaire controle de la table propre (garde-fou : une graphie par categorie, 13 regions, pas de libelle recopie par erreur)
    if longue:
        ent = longue[0]
        attendu = {"milieu": {"", "urbain", "rural", "indetermine", "total"},
                   "statut": {"", "public", "prive", "communautaire", "confessionnel", "franco-arabe", "laic", "total"},
                   "niveau_scolaire": {"", "total", "Petite section", "Moyenne section", "Grande section", "CP1", "CP2", "CE1", "CE2",
                                       "CM1", "CM2", "CP", "CE", "CM"},
                   "sexe": {"", "garcons", "filles", "total"}, "agregat": {"detail", "sous_total", "national"}}
        for col, ok in attendu.items():
            if col in ent:
                hors = {r[ent.index(col)] for r in longue[1:]} - ok
                (res("PASS", f"vocabulaire de la colonne {col} conforme") if not hors
                 else res("FAIL", f"colonne {col} : libelles inattendus {sorted(hors)[:4]}"))
        if "region" in ent:
            regs = {r[ent.index("region")] for r in longue[1:]} - {"", "total"}
            (res("PASS", "13 regions harmonisees") if len(regs) == 13 else res("FAIL", f"{len(regs)} noms de regions au lieu de 13 : {sorted(regs)[:15]}"))
    # completude du registre
    reg = next((v for k, v in textes_cache.items() if k.endswith("_registre-sources_v1.csv")), None)
    if reg:
        ent = reg[0]
        try:
            idx = {c: ent.index(c) for c in ("decision_defi2", "producteur_source", "publication", "annee_ou_periode")}
            retenus = [r for r in reg[1:] if r[idx["decision_defi2"]] in ("PRINCIPAL", "RETENU")]
            vides = [r for r in retenus if not all(r[idx[c]] for c in ("producteur_source", "publication", "annee_ou_periode"))]
            (res("PASS", f"registre : {len(retenus)} fichiers retenus, tous avec producteur, publication et periode")
             if not vides else res("FAIL", f"registre : {len(vides)} fichiers retenus sans source complete"))
        except ValueError:
            res("FAIL", "registre non annote (colonnes decision_defi2 / sources absentes)")
    # une etape = un depot : LISEZ-MOI par etape
    etapes = {m.group(1) for _, f in fichiers if (m := re.match(r"^[A-Za-z][A-Za-z0-9_]*?_(0[1-5]-[a-z]+)_", f.name))}
    for e in sorted(etapes):
        # etape 5 : la fiche et le dossier technique tiennent lieu de LISEZ-MOI
        a_lm = any(("lisez-moi" in f.name or (e.startswith("05") and ("documentation" in f.name or "fiche" in f.name)))
                   and f"_{e}_" in f.name for _, f in fichiers)
        res("PASS", f"LISEZ-MOI present pour l'etape {e}") if a_lm else res("FAIL", f"pas de LISEZ-MOI pour l'etape {e}")
    print(f"\nBILAN : {bilan['PASS']} PASS, {bilan['WARN']} WARN, {bilan['FAIL']} FAIL")
    print("PRET A DEPOSER" if bilan["FAIL"] == 0 else "A CORRIGER AVANT DE DEPOSER")
    return 0 if bilan["FAIL"] == 0 else 3


def main(argv=None) -> int:
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Preparer et verifier les depots pour la plateforme")
    sp = ap.add_subparsers(dest="cmd", required=True)
    pp = sp.add_parser("preparer")
    pp.add_argument("--equipe", required=True)
    pp.add_argument("--defi", default="D2")
    pp.add_argument("--role", default="engineer")
    pp.add_argument("--racine", help="dossier du projet (defaut : parent de scripts/)")
    pv = sp.add_parser("verifier")
    pv.add_argument("--dossier", help="dossier a controler (defaut : depot_final)")
    a = ap.parse_args(argv)
    racine = Path(getattr(a, "racine", None) or Path(__file__).resolve().parent.parent)
    if a.cmd == "preparer":
        return preparer(racine, a.equipe, a.defi, a.role)
    return verifier(Path(a.dossier) if a.dossier else racine / "depot_final")


if __name__ == "__main__":
    sys.exit(main())
