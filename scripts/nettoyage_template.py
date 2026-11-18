#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NETTOYAGE - Etape 2 (depot 02_nettoyage) - Defi 2 (parite filles-garcons, ecart urbain-rural).
Base visee : "Donnees statistiques prescolaire et primaire 2016-2025" (DGESS), par REGION (13 anciennes regions).

REGLE DU CHALLENGE : ce script est lance PAR VOUS, en local, sur les donnees brutes. L'IA n'a vu que la
STRUCTURE (libelles, nombre de nombres) et des donnees fictives. La console n'affiche que des COMPTEURS.

Entree : le classeur Excel de 01_collecte (copie en lecture seule : l'entree n'est jamais modifiee).

Structure geree (d'apres le profil reel de la base) :
  - plusieurs TABLEAUX par feuille, empiles ("Tableau 1 : ...", "Tableau 2 : ..."), ou un tableau par feuille ;
  - disposition A : annees en groupes de colonnes fusionnees + ligne G / F / T (PRESCOLAIRE, taux TBA/TBS...) ;
  - disposition B : annees en colonnes, sexe/statut/niveau en lignes (Feuil1, 2, 3, 4, 5, 9, 13, IPS...) ;
  - libelles a plusieurs niveaux : region, statut (public/prive/communautaire), milieu, niveau scolaire, sexe ;
  - lignes de sous-total ("Total Public", "Total <region>") et de total general : gardees, marquees (colonne agregat) ;
  - effectifs / nombres (sommables), taux et indices de parite IPS (non sommables) : controles adaptes.
SECURITE : un texte adresse "aux assistants automatiques" est present dans plusieurs cellules du fichier. Il est
RETIRE avant toute analyse et signale (anomalies) avec son adresse de cellule. Lisez ces cellules dans Excel.

Sorties (dans DOSSIER_02) :
  EQ_02-nettoyage_D2_engineer_tableaux-long_v1.csv       1 ligne = une valeur (region x statut x milieu x niveau x sexe x annee)
  EQ_02-nettoyage_D2_engineer_journal-nettoyage_v1.csv   chaque regle appliquee, lignes avant/apres
  EQ_02-nettoyage_D2_engineer_anomalies_v1.csv           a verifier (cellules suspectes, G+F<>T, sommes, libelles inconnus...)
  EQ_02-nettoyage_D2_engineer_correspondance-regions_v1.csv   region DGESS -> region du fond de carte (A VALIDER)
  LISEZ-MOI.txt

Usage :
  python nettoyage_template.py ENTREE.xlsx DOSSIER_02 --equipe Burkina_Novation [--reference bfa_admin1.geojson]
         [--alias alias_regions.csv] [--feuilles PRESCOLAIRE Feuil1] [--annee-min 2015 --annee-max 2024]
Hypothese a verifier : une annee numerique AAAA en en-tete designe l'annee scolaire AAAA-(AAAA+1).
"""
from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

# --------------------------------------------------------------------------------------------------
# A ADAPTER SI BESOIN
# --------------------------------------------------------------------------------------------------
SEXES = {"g": "garcons", "garcons": "garcons", "garcon": "garcons", "m": "garcons", "masculin": "garcons",
         "masc": "garcons", "hommes": "garcons",
         "f": "filles", "filles": "filles", "fille": "filles", "feminin": "filles", "fem": "filles", "femmes": "filles",
         "t": "total", "total": "total", "ensemble": "total"}
TOTAL_GENERAL = {"national", "burkina faso", "burkina", "ensemble", "total", "total general", "total national", "general"}
REGIONS_13 = {"boucle du mouhoun", "cascades", "centre", "centre est", "centre nord", "centre ouest", "centre sud", "est",
              "hauts bassins", "haut bassins", "nord", "plateau central", "sahel", "sud ouest"}
# Noms canoniques des 13 anciennes regions (+ variantes d'orthographe connues : ex. HAUT-BASSINS dans la base)
CANON_REGIONS = {"boucle du mouhoun": "Boucle du Mouhoun", "cascades": "Cascades", "centre": "Centre",
                 "centre est": "Centre-Est", "centre nord": "Centre-Nord", "centre ouest": "Centre-Ouest",
                 "centre sud": "Centre-Sud", "est": "Est", "hauts bassins": "Hauts-Bassins",
                 "haut bassins": "Hauts-Bassins", "nord": "Nord", "plateau central": "Plateau-Central",
                 "sahel": "Sahel", "sud ouest": "Sud-Ouest"}
STATUTS = {"public", "prive", "communautaire", "confessionnel", "franco arabe", "laic", "prive laic", "prive confessionnel"}
MILIEUX = {"urbain", "urbaine", "rural", "rurale", "indetermine", "indeterminee", "non determine"}
NIVEAUX_SCOL = {"petite section", "moyenne section", "grande section", "cp1", "cp2", "ce1", "ce2", "cm1", "cm2",
                "cp", "ce", "cm"}
# Libelles canoniques (une seule graphie par categorie : RURAL = Rural = rural ; Privé = PRIVE = prive)
CANON = {"milieu": {"urbain": "urbain", "urbaine": "urbain", "rural": "rural", "rurale": "rural",
                    "indetermine": "indetermine", "indeterminee": "indetermine", "non determine": "indetermine"},
         "statut": {"public": "public", "prive": "prive", "communautaire": "communautaire",
                    "confessionnel": "confessionnel", "franco arabe": "franco-arabe", "laic": "laic"},
         "niveau_scolaire": {"petite section": "Petite section", "moyenne section": "Moyenne section",
                             "grande section": "Grande section", "cp1": "CP1", "cp2": "CP2", "ce1": "CE1", "ce2": "CE2",
                             "cm1": "CM1", "cm2": "CM2", "cp": "CP", "ce": "CE", "cm": "CM"}}
# texte adresse a un assistant automatique (injection) : retire des cellules avant analyse
RX_IA = re.compile(r"(NOTE\s+FOR\s+ANY|AUTOMATED\s+ASSISTANT|IGNORE\s+(ALL\s+)?(PREVIOUS|PRIOR)\s+INSTRUCTIONS).*",
                   re.I | re.S)
ABSENT = {"", "-", "--", "nd", "n d", "na", "n a", "x", "..."}
DIMS = ["region", "statut", "milieu", "niveau_scolaire", "autre"]
TOLERANCE = 0.5
SEUIL_FLOU = 0.86
# Une annee numerique seule en en-tete (2016) : annee de DEBUT (2016-2017) ou de FIN (2015-2016) ? Se regle par --annee-numerique
ANNEE_NUM_MODE = "debut"
RX_ANNEE_PAIRE = r"(?<!\d)(20[0-3]\d)\s*[-/_]\s*(20[0-3]\d|\d{2})(?!\d)"
RX_ANNEE_SEULE = r"(?<!\d)(20[0-3]\d)(?!\d)"

journal: list = []


# --------------------------------------------------------------------------------------------------
# OUTILS
# --------------------------------------------------------------------------------------------------
def norm(s) -> str:
    s = re.sub(r"[’‘ʼ'`´]", " ", str(s))      # l'IPS / l’IPS -> "l ips" (et non "lips")
    t = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", t)).strip()


def vide(v) -> bool:
    return v is None or (isinstance(v, float) and v != v) or str(v).strip() == ""


def parse_annee(v):
    """'2016-2017', '2016/17', 2016, '2017 (provisoire)' -> (2016, '2016-2017') ; sinon None."""
    if vide(v):
        return None
    s = str(v)
    m = re.search(RX_ANNEE_PAIRE, s)
    if m:                                                      # '2015-2016', '2015/16' : annee scolaire explicite
        a = int(m.group(1))
        return a, f"{a}-{a + 1}"
    m = re.search(RX_ANNEE_SEULE, s)
    if not m:
        return None
    a = int(m.group(1)) - (1 if ANNEE_NUM_MODE == "fin" else 0)   # 2016 seul : debut ou fin d'annee scolaire
    return a, f"{a}-{a + 1}"


def annee_source(v) -> str:
    """'scolaire' (2015-2016 explicite) ou 'numerique' (annee seule : convention a confirmer)."""
    return "scolaire" if re.search(RX_ANNEE_PAIRE, str(v)) else "numerique"


def parse_nombre(v):
    if vide(v):
        return None, "absent"
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v), "ok"
    s = str(v).strip().replace(" ", "").replace(" ", "")
    if norm(s) in ABSENT:
        return None, "absent"
    try:
        return float(s.replace(",", ".")), "ok"
    except ValueError:
        return None, "non_numerique"


def lettre(j: int) -> str:
    s, j = "", j + 1
    while j:
        j, r = divmod(j - 1, 26)
        s = chr(65 + r) + s
    return s


def log(etape, regle, avant, apres, detail=""):
    journal.append({"etape": etape, "regle": regle, "avant": avant, "apres": apres,
                    "touchees": avant - apres if isinstance(avant, int) and isinstance(apres, int) else "",
                    "detail": detail})


def classer(label):
    """(type, valeur, sous_total) ; type : region/statut/milieu/niveau/sexe/total_general/autre."""
    lab = str(label).strip()
    n = norm(lab)
    if n in TOTAL_GENERAL:
        return "total_general", "total", False
    m = re.match(r"(?i)\s*total\s+(.+)$", lab)
    if m:
        t, v, _ = classer(m.group(1))
        return ("total_general", "total", False) if t == "total_general" else (t, v, True)
    if n in REGIONS_13:
        return "region", lab, False
    if n in STATUTS:
        return "statut", lab, False
    if n in MILIEUX:
        return "milieu", lab, False
    if n in NIVEAUX_SCOL:
        return "niveau", lab, False
    if SEXES.get(n) in ("garcons", "filles"):
        return "sexe", SEXES[n], False
    return "autre", lab, False


def type_valeur(titre: str) -> str:
    n = norm(titre)
    if re.search(r"\bips\b|indice de parite", n):
        return "indice_parite"
    if re.search(r"\b(taux|tba|tbs|tap|tab|achevement|reussite|tbps|tns)\b", n):
        return "taux"
    if re.search(r"effectif|inscrit", n):
        return "effectif"
    if re.search(r"nombre|ecoles|classes|enseignants|salles", n):
        return "nombre"
    return "inconnu"


def niveau_enseignement(titre: str, feuille: str):
    n = norm(titre)
    if re.search(r"prescolaire", n):
        return "prescolaire", "titre"
    if re.search(r"primaire", n):
        return "primaire", "titre"
    if "prescolaire" in norm(feuille):
        return "prescolaire", "feuille"
    return "primaire", "defaut (a confirmer)"


# --------------------------------------------------------------------------------------------------
# LECTURE : grille nettoyee, blocs, disposition
# --------------------------------------------------------------------------------------------------
def grille(ws, suspectes: list) -> list:
    """Feuille -> liste de lignes. Les textes 'pour assistants automatiques' sont retires AVANT les cellules
    fusionnees etendues ; leur adresse est consignee."""
    g = []
    for i, r in enumerate(ws.iter_rows(values_only=True)):
        ligne = []
        for j, v in enumerate(r):
            if isinstance(v, str) and RX_IA.search(v):
                suspectes.append((ws.title, f"{lettre(j)}{i + 1}", len(v)))
                v = RX_IA.sub("", v).strip() or None
            ligne.append(v)
        g.append(ligne)
    largeur = max((len(r) for r in g), default=0)
    for r in g:
        r.extend([None] * (largeur - len(r)))
    for m in ws.merged_cells.ranges:
        if m.min_row - 1 >= len(g):
            continue
        v = g[m.min_row - 1][m.min_col - 1]
        for i in range(m.min_row - 1, min(m.max_row, len(g))):
            for j in range(m.min_col - 1, min(m.max_col, largeur)):
                if vide(g[i][j]):
                    g[i][j] = v
    return g


def blocs_de(g):
    """[(debut, fin, titre)] : un bloc par 'Tableau N ...' ; sinon un seul bloc."""
    starts = []
    for i, row in enumerate(g):
        for j in (0, 1):
            if j < len(row) and not vide(row[j]) and re.match(r"^tableau\s*\d+", norm(row[j])):
                starts.append((i, str(row[j]).strip()))
                break
    if not starts:
        titre = next((str(c).strip() for r in g[:3] for c in r if not vide(c)), "")
        return [(0, len(g), titre)]
    return [(s, starts[k + 1][0] if k + 1 < len(starts) else len(g), t) for k, (s, t) in enumerate(starts)]


def detecter_bloc(g, s, e):
    """('A', ligne_sexes, colonnes) | ('B', ligne_annees, colonnes) | (None, None, [])."""
    fin = min(e, s + 8)
    for i in range(s, fin):
        cols = [j for j, v in enumerate(g[i]) if not vide(v) and norm(v) in SEXES]
        if len(cols) >= 2 and {SEXES[norm(g[i][j])] for j in cols} >= {"garcons", "filles"}:
            return "A", i, cols
    for i in range(s, fin):
        cols = [j for j, v in enumerate(g[i]) if j > 0 and not vide(v) and len(str(v)) < 40 and parse_annee(v)]
        if len(cols) >= 2:
            return "B", i, cols
    return None, None, []


def extraire_bloc(g, s, e, feuille, bloc_no, titre):
    mode, i_ent, cols = detecter_bloc(g, s, e)
    if mode is None:
        return None
    j0 = min(cols)
    id_cols = list(range(j0))
    annee_col, sexe_col, annee_src = {}, {}, {}
    if mode == "A":
        for j in cols:
            sexe_col[j] = SEXES[norm(g[i_ent][j])]
        for j in cols:                                          # annee : ligne la plus proche au-dessus, propagee a droite
            for r in range(i_ent - 1, s - 1, -1):
                v, k = g[r][j], j
                while vide(v) and k > j0:
                    k -= 1
                    v = g[r][k]
                if parse_annee(v):
                    annee_col[j], annee_src[j] = parse_annee(v), annee_source(v)
                    break
        debut = i_ent + 1
    else:
        for j in cols:
            annee_col[j], annee_src[j] = parse_annee(g[i_ent][j]), annee_source(g[i_ent][j])
        debut = i_ent + 1

    lignes, sans_lib = [], []
    stats = {"lignes_vides": 0, "lignes_notes": 0, "lignes_sans_libelle": 0}
    for r in range(debut, e):
        ligne = g[r]
        a_valeurs = any(not vide(ligne[j]) for j in cols)
        labs = {j: str(ligne[j]).strip() for j in id_cols if not vide(ligne[j])}
        if not a_valeurs and not labs:
            stats["lignes_vides"] += 1
        elif not a_valeurs:
            stats["lignes_notes"] += 1
        elif not labs:
            stats["lignes_sans_libelle"] += 1
            kinds = [parse_nombre(ligne[j])[1] for j in cols if not vide(ligne[j])]
            sans_lib.append((r + 1, kinds.count("ok"), len(kinds) - kinds.count("ok")))
        else:
            lignes.append((r, labs))
    # typage de chaque colonne de libelles par vote sur ses libelles (l'en-tete peut mentir : "REGION" pour des milieux)
    type_col = {}
    for j in id_cols:
        votes = Counter()
        for _, labs in lignes:
            if j in labs:
                t, _, sous = classer(labs[j])
                if t != "total_general" and not sous:      # un libelle "Total X" (souvent fusionne sur 2 colonnes) ne vote pas
                    votes[t] += 1
        type_col[j] = votes.most_common(1)[0][0] if votes else "autre"
    recs, non_classes = [], Counter()
    derniers = {}
    for r, labs in lignes:
        a_total = any(classer(v)[0] == "total_general" or classer(v)[2] for j, v in labs.items() if type_col[j] != "sexe")
        pleins = dict(labs)
        for j in id_cols:
            if j not in pleins:
                if a_total:
                    pleins[j] = "total"
                elif j in derniers:
                    pleins[j] = derniers[j]
            if j in labs and not a_total:
                derniers[j] = labs[j]
            elif j in labs and a_total and type_col[j] == "sexe":
                derniers[j] = labs[j]
        dims = {d: "" for d in DIMS + ["sexe"]}
        for j in id_cols:
            lab = pleins.get(j)
            if lab is None:
                continue
            t, v, sous = classer(lab)
            col = {"niveau": "niveau_scolaire"}.get(type_col[j], type_col[j])
            if col == "sexe":
                dims["sexe"] = "total" if t == "total_general" else (SEXES.get(norm(lab)) or lab)
            elif t == "total_general" or lab == "total":
                dims[col] = "total"
            elif sous and t != type_col[j]:
                dims[col] = "total"            # sous-total "Total X" recopie dans une autre colonne par une fusion de cellules
            else:
                dims[col] = CANON.get(col, {}).get(norm(v), v)
                if col == "autre":
                    non_classes[lab] += 1
        non_sexe = [v for k, v in dims.items() if k != "sexe" and v != ""]
        agregat = "detail" if "total" not in non_sexe else ("national" if all(v == "total" for v in non_sexe) else "sous_total")
        for j in cols:
            a = annee_col.get(j)
            sexe = sexe_col.get(j, dims["sexe"])
            recs.append({"feuille": feuille, "bloc": bloc_no, "bloc_titre": titre[:120], "region_brute": dims["region"],
                         "statut": dims["statut"], "milieu": dims["milieu"], "niveau_scolaire": dims["niveau_scolaire"],
                         "autre": dims["autre"], "sexe": sexe, "annee": a, "annee_source": annee_src.get(j, ""),
                         "brut": g[r][j], "agregat": agregat,
                         "ligne_source": r + 1, "colonne_source": lettre(j)})
    return recs, {"mode": mode, "types": {lettre(j): t for j, t in type_col.items()}, "non_classes": non_classes,
                  "sans_libelle_rows": sans_lib, **stats}


# --------------------------------------------------------------------------------------------------
# REFERENCE DES REGIONS (fond de carte) ET RAPPROCHEMENT
# --------------------------------------------------------------------------------------------------
def charger_reference_regions(chemin: Path | None) -> dict:
    """norm(nom de region) -> fiche. GeoJSON COD-AB (adm1_name / adm1_pcode) ou CSV region;pcode."""
    if not chemin:
        return {}
    if chemin.suffix.lower() in (".geojson", ".json"):
        props = [f.get("properties", {}) for f in json.loads(chemin.read_text(encoding="utf-8")).get("features", [])]
    else:
        with open(chemin, encoding="utf-8-sig", newline="") as f:
            props = list(csv.DictReader(f, delimiter=";"))
    ref = {}
    for p in props:
        nom = p.get("adm1_name") or p.get("region")
        if nom:
            fiche = {"province": nom, "pcode": p.get("adm1_pcode", p.get("pcode", "")), "region": "", "region_pcode": ""}
            for k in ("adm1_name", "adm1_name1", "adm1_name2", "adm1_name3", "region"):
                if p.get(k):
                    ref.setdefault(norm(p[k]), fiche)
    return ref


def charger_alias(chemin: Path | None) -> dict:
    if not chemin or not chemin.exists():
        return {}
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        return {norm(r["brut"]): r["officiel"] for r in csv.DictReader(f, delimiter=";") if r.get("brut")}


def apparier(bruts, ref, alias, appliquer_flou=False):
    """Un rapprochement flou n'est qu'une SUGGESTION tant qu'il n'est pas valide (alias) ou applique (--appliquer-flou)."""
    table = {}
    for brut in sorted(set(bruts)):
        k = norm(brut)
        e = {"region_brute": brut, "cle": k, "type": "", "score": "", "region_officielle": "", "pcode_region": "",
             "statut": "", "applique": "oui", "suggestion": "", "suggestion_pcode": ""}
        cible = alias.get(k)
        k2, e["type"] = (norm(cible), "alias") if cible is not None else (k, "exact")
        if k2 in ref:
            e.update(region_officielle=ref[k2]["province"], pcode_region=ref[k2]["pcode"], statut="OK")
        elif ref:
            m = difflib.get_close_matches(k2, list(ref), n=1, cutoff=SEUIL_FLOU)
            if m:
                f = ref[m[0]]
                e.update(type="flou", score=round(difflib.SequenceMatcher(None, k2, m[0]).ratio(), 3), statut="A VALIDER",
                         suggestion=f["province"], suggestion_pcode=f["pcode"])
                if appliquer_flou:
                    e.update(region_officielle=f["province"], pcode_region=f["pcode"])
                else:
                    e["applique"] = "non"
            else:
                e.update(type="inconnu", statut="INCONNU", applique="non")
        else:
            e.update(type="sans_reference", statut="SANS REFERENCE", applique="non")
        table[brut] = e
    return table


# --------------------------------------------------------------------------------------------------
# PROGRAMME PRINCIPAL
# --------------------------------------------------------------------------------------------------
def main(argv=None) -> int:
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Nettoyage etape 2 - Defi 2 (aucune valeur n'est affichee a l'ecran)")
    ap.add_argument("entree", help="classeur .xlsx (copie dans 01_collecte)")
    ap.add_argument("sortie", help="dossier 02_nettoyage")
    ap.add_argument("--equipe", required=True)
    ap.add_argument("--defi", default="D2")
    ap.add_argument("--role", default="engineer")
    ap.add_argument("--reference", help="GeoJSON COD-AB niveau 1 (bfa_admin1.geojson) ou CSV region;pcode")
    ap.add_argument("--alias", help="CSV brut;officiel (corrections manuelles des noms de regions)")
    ap.add_argument("--appliquer-flou", action="store_true", help="appliquer aussi les rapprochements flous")
    ap.add_argument("--feuilles", nargs="*", help="feuilles a traiter (defaut : toutes)")
    ap.add_argument("--annee-min", type=int, default=2015, help="debut de la fenetre (annee de debut d'annee scolaire)")
    ap.add_argument("--annee-max", type=int, default=2024)
    ap.add_argument("--annee-numerique", choices=["debut", "fin"], default="debut",
                    help="une annee seule en en-tete (2016) est l'annee de DEBUT (2016-2017) ou de FIN (2015-2016) ?")
    a = ap.parse_args(argv)
    global ANNEE_NUM_MODE
    ANNEE_NUM_MODE = a.annee_numerique

    entree, sortie = Path(a.entree), Path(a.sortie)
    if not entree.is_file():
        print("ERREUR : fichier d'entree introuvable")
        return 1
    sortie.mkdir(parents=True, exist_ok=True)
    pre = f"{a.equipe}_02-nettoyage_{a.defi}_{a.role}"

    wb = load_workbook(entree, data_only=True)               # lecture pure : l'entree n'est jamais modifiee
    recs, suspectes, inconnus, blocs_info, sans_lib_all = [], [], [], [], []
    for ws in wb.worksheets:
        if a.feuilles and ws.title not in a.feuilles:
            continue
        g = grille(ws, suspectes)
        for no, (s, e, titre) in enumerate(blocs_de(g), start=1):
            res = extraire_bloc(g, s, e, ws.title, no, titre)
            if res is None:
                log("lecture", f"{ws.title} / tableau {no} : disposition non reconnue", 0, 0, "ni G/F/T ni annees en colonnes")
                inconnus.append((ws.title, no))
                print(f"[{ws.title} #{no}] disposition non reconnue")
                continue
            r, info = res
            sans_lib_all += [(ws.title, no, *x) for x in info["sans_libelle_rows"]]
            tv = type_valeur(titre)
            for x in r:
                x["type_valeur"] = tv
            recs += r
            blocs_info.append((ws.title, no, info["mode"], tv, len(r)))
            log("lecture", f"{ws.title} / tableau {no} : disposition {info['mode']}, type {tv}", e - s,
                len({x["ligne_source"] for x in r}),
                f"{len(r)} valeurs ; vides={info['lignes_vides']} notes={info['lignes_notes']} "
                f"sans_libelle={info['lignes_sans_libelle']} ; colonnes de libelles : {info['types']}")
            ys = sorted({x["annee"][0] for x in r if x["annee"]})
            srcs = "/".join(sorted({x["annee_source"] for x in r}))
            print(f"[{ws.title} #{no}] {info['mode']}, {tv}, {len(r)} valeurs, annees {ys[0] if ys else '?'}-{ys[-1] if ys else '?'}"
                  f" ({srcs}), colonnes {info['types']}")
    wb.close()
    if not recs:
        print("ERREUR : aucune donnee extraite. Lancez profil_structure.py --squelette et adaptez detecter_bloc.")
        return 2

    anomalies = []

    def anom(type_, **k):
        base = {"type": type_, "feuille": "", "bloc": "", "region": "", "statut": "", "milieu": "", "niveau_scolaire": "",
                "sexe": "", "annee": "", "valeur_observee": "", "valeur_attendue": "", "detail": ""}
        base.update(k)
        anomalies.append(base)

    for feuille, cellule, n in suspectes:
        anom("cellule_suspecte", feuille=feuille, detail=f"{cellule} : texte adresse a un assistant automatique retire "
                                                         f"({n} caracteres) - a lire dans Excel")
    log("securite", "texte adresse aux assistants automatiques retire des cellules", len(suspectes), 0,
        f"{len(suspectes)} cellule(s) ; adresses dans anomalies")
    for feuille, bloc, ligne_x, n_nb, n_txt in sans_lib_all:
        anom("ligne_sans_libelle", feuille=feuille, bloc=bloc,
             detail=f"L{ligne_x} : {n_nb} nombre(s) et {n_txt} texte(s) dans les colonnes de valeurs, aucun libelle : ligne ignoree")
    log("lecture", "lignes avec valeurs mais sans libelle (ignorees, listees dans anomalies)", len(sans_lib_all), 0, "")

    df = pd.DataFrame(recs)
    conv = df["brut"].map(parse_nombre)
    df["valeur"] = conv.map(lambda x: x[0])
    df["statut_valeur"] = conv.map(lambda x: x[1])
    n_abs, n_nn = int((df.statut_valeur == "absent").sum()), int((df.statut_valeur == "non_numerique").sum())
    log("nombres", "valeurs absentes laissees vides (jamais remplacees par 0)", len(df), len(df),
        f"{n_abs} absentes ; {n_nn} non numeriques -> vides")
    for x in df[df.statut_valeur == "non_numerique"].itertuples():
        anom("valeur_non_numerique", feuille=x.feuille, bloc=x.bloc, region=x.region_brute, sexe=x.sexe,
             annee=x.annee[1] if x.annee else "", valeur_observee=x.brut, detail=f"L{x.ligne_source}{x.colonne_source}")
    for x in df[df.statut_valeur == "absent"].head(500).itertuples():
        anom("valeur_absente", feuille=x.feuille, bloc=x.bloc, region=x.region_brute, statut=x.statut, milieu=x.milieu,
             niveau_scolaire=x.niveau_scolaire, sexe=x.sexe, annee=x.annee[1] if x.annee else "",
             detail=f"L{x.ligne_source}{x.colonne_source} : cellule vide, laissee vide (jamais 0)")
    for x in df[(df.valeur < 0)].itertuples():
        anom("valeur_negative", feuille=x.feuille, bloc=x.bloc, region=x.region_brute, sexe=x.sexe,
             annee=x.annee[1] if x.annee else "", valeur_observee=x.valeur, detail=f"L{x.ligne_source}{x.colonne_source}")
    df["annee_scolaire"] = df["annee"].map(lambda x: x[1] if x else "")
    df["annee_debut"] = df["annee"].map(lambda x: x[0] if x else None)
    sans_annee = int((df.annee_scolaire == "").sum())
    lib_conv = ("annee de DEBUT : AAAA lue comme AAAA-(AAAA+1)" if ANNEE_NUM_MODE == "debut"
                else "annee de FIN : AAAA lue comme (AAAA-1)-AAAA")
    log("annee", f"annee scolaire AAAA-AAAA ; annee numerique en en-tete = {lib_conv} (convention --annee-numerique {ANNEE_NUM_MODE})", len(df), len(df),
        f"{sans_annee} valeurs sans annee reconnue")

    # --- regions -------------------------------------------------------------------------------------
    # noms canoniques des 13 regions DGESS (harmonise HAUT-BASSINS / HAUTS-BASSINS, la casse...) ; region_brute = tel quel
    df["region"] = df["region_brute"].map(lambda b: CANON_REGIONS.get(norm(b), b))
    var = df[(df.region_brute != "") & (df.region_brute.map(norm) != df.region.map(norm))].drop_duplicates(
        ["feuille", "bloc", "region_brute"])
    for x in var.itertuples():
        anom("variante_orthographe", feuille=x.feuille, bloc=x.bloc, region=x.region_brute, valeur_observee=x.region_brute,
             valeur_attendue=x.region, detail=f"L{x.ligne_source} : nom de region harmonise")
    log("regions", "variantes d'orthographe des 13 regions harmonisees (region_brute conserve le nom d'origine)",
        len(var), 0, ", ".join(sorted({f"{b} -> {c}" for b, c in zip(var.region_brute, var.region, strict=True)})) or "aucune")
    ref = charger_reference_regions(Path(a.reference) if a.reference else None)
    alias = charger_alias(Path(a.alias) if a.alias else None)
    noms = [x for x in df["region"].unique() if x not in ("", "total")]
    table = apparier(noms, ref, alias, a.appliquer_flou)
    df["region_officielle"] = df["region"].map(lambda b: "total" if b == "total" else table.get(b, {}).get("region_officielle", ""))
    df["pcode_region"] = df["region"].map(lambda b: table.get(b, {}).get("pcode_region", ""))
    stat = Counter(e["statut"] for e in table.values())
    n_ref = len({v["pcode"] for v in ref.values()})
    log("regions", "regions DGESS rapprochees du fond de carte (par le nom)", len(table), len(table),
        " ; ".join(f"{k}={v}" for k, v in stat.items()) + (f" ; fond de carte : {n_ref} regions" if ref else " ; aucune reference")
        + ("" if n_ref in (0, 13) else " ; ATTENTION 13 anciennes regions DGESS contre " + str(n_ref) + " du fond de carte : perimetres a verifier"))
    pd.DataFrame(table.values()).to_csv(sortie / f"{pre}_correspondance-regions_v1.csv", sep=";", index=False,
                                        encoding="utf-8-sig")
    # --- libelles non classes ------------------------------------------------------------------------
    for x in df[df.autre != ""].drop_duplicates(["feuille", "bloc", "autre"]).itertuples():
        anom("libelle_non_classe", feuille=x.feuille, bloc=x.bloc, valeur_observee=x.autre,
             detail=f"L{x.ligne_source} : ni region, ni statut, ni milieu, ni niveau connus")
    # --- doublons ------------------------------------------------------------------------------------
    cle = ["feuille", "bloc", "region", "statut", "milieu", "niveau_scolaire", "autre", "sexe", "annee_scolaire"]
    d = df.duplicated(cle, keep=False)
    conflit = df[d].groupby(cle, dropna=False)["valeur"].nunique(dropna=False)
    n0 = len(df)
    for k in conflit[conflit > 1].index:
        anom("doublon_conflictuel", feuille=k[0], bloc=k[1], region=k[2], statut=k[3], milieu=k[4], niveau_scolaire=k[5],
             sexe=k[7], annee=k[8], valeur_observee="valeurs differentes", detail="garde la premiere occurrence")
    df = df.drop_duplicates(cle, keep="first")
    log("doublons", "doublons (meme cle) supprimes, 1re occurrence conservee", n0, len(df),
        f"dont {int((conflit > 1).sum())} cle(s) conflictuelle(s)")
    # --- controles (effectifs / nombres seulement : les taux et IPS ne se somment pas) -------------------
    cnt = df[df.type_valeur.isin(["effectif", "nombre"])]
    idx = ["feuille", "bloc", "region", "statut", "milieu", "niveau_scolaire", "autre", "annee_scolaire"]
    if not cnt.empty and {"garcons", "filles", "total"} <= set(cnt.sexe):
        piv = cnt.pivot_table(index=idx, columns="sexe", values="valeur", aggfunc="first")
        if {"garcons", "filles", "total"} <= set(piv.columns):
            ecart = (piv.garcons + piv.filles - piv.total).abs()
            mauvais = ecart[ecart > TOLERANCE]
            for k, v in mauvais.items():
                anom("G+F<>T", feuille=k[0], bloc=k[1], region=k[2], statut=k[3], milieu=k[4], niveau_scolaire=k[5], annee=k[7],
                     valeur_observee=piv.loc[k, "garcons"] + piv.loc[k, "filles"], valeur_attendue=piv.loc[k, "total"],
                     detail=f"ecart {v:g}")
            log("controle", "garcons + filles = total (effectifs)", int(ecart.notna().sum()),
                int(ecart.notna().sum() - len(mauvais)), f"{len(mauvais)} ecart(s) -> anomalies")
    if not cnt.empty:
        n_tot = n_bad = 0
        for dim in DIMS:
            if not (cnt[dim] == "total").any():
                continue
            autres = [x for x in DIMS if x != dim] + ["feuille", "bloc", "annee_scolaire", "sexe"]
            det = cnt[(cnt[dim] != "total") & (cnt[dim] != "") & (cnt.agregat != "national")]
            tot = cnt[cnt[dim] == "total"].drop_duplicates(autres).set_index(autres)["valeur"].rename("publie")
            somme = det.groupby(autres, dropna=False)["valeur"].sum(min_count=1).rename("calcule")
            comp = pd.concat([somme, tot], axis=1, join="inner").dropna()
            mauvais = comp[(comp.calcule - comp.publie).abs() > TOLERANCE]
            n_tot += len(comp)
            n_bad += len(mauvais)
            for k, v in mauvais.iterrows():
                kk = dict(zip(autres, k, strict=False))
                anom("somme<>total_publie", feuille=kk["feuille"], bloc=kk["bloc"], region=kk.get("region", "total"),
                     statut=kk.get("statut", "total"), milieu=kk.get("milieu", "total"),
                     niveau_scolaire=kk.get("niveau_scolaire", "total"), sexe=kk["sexe"], annee=kk["annee_scolaire"],
                     valeur_observee=v.calcule, valeur_attendue=v.publie, detail=f"total selon la dimension '{dim}' ; ecart {v.calcule - v.publie:g}")
        log("controle", "somme des lignes de detail = total/sous-total publie", n_tot, n_tot - n_bad, f"{n_bad} ecart(s) -> anomalies")
    # --- couverture des annees -----------------------------------------------------------------------
    annees = sorted({int(x) for x in df.annee_debut.dropna()})
    attendues = list(range(a.annee_min, a.annee_max + 1))
    manque = [y for y in attendues if y not in annees]
    log("controle", f"couverture des annees de debut {a.annee_min}-{a.annee_max}", len(attendues), len(attendues) - len(manque),
        f"manquantes : {manque or 'aucune'} ; presentes : {annees}")

    # --- sortie --------------------------------------------------------------------------------------
    nv = df.apply(lambda r: niveau_enseignement(r["bloc_titre"], r["feuille"]), axis=1)
    df["niveau_enseignement"] = nv.map(lambda x: x[0])
    df["niveau_enseignement_source"] = nv.map(lambda x: x[1])
    df["referentiel_region"] = "DGESS : 13 anciennes regions"
    df["annee_numerique_convention"] = ANNEE_NUM_MODE        # debut ou fin : lu par verifier_total_annuaire.py
    final = df[["feuille", "bloc", "bloc_titre", "type_valeur", "niveau_enseignement", "niveau_enseignement_source",
                "region", "region_brute", "region_officielle", "pcode_region", "referentiel_region", "statut", "milieu",
                "niveau_scolaire", "autre", "sexe", "annee_scolaire", "annee_debut", "annee_source", "annee_numerique_convention", "valeur", "agregat", "ligne_source",
                "colonne_source"]].sort_values(["feuille", "bloc", "annee_debut", "region_brute", "statut", "milieu",
                                                "niveau_scolaire", "sexe"])
    final.to_csv(sortie / f"{pre}_tableaux-long_v1.csv", sep=";", index=False, encoding="utf-8-sig")
    log("sortie", "table longue ecrite (toutes les lignes : detail, sous_total, national)", len(df), len(final))
    pd.DataFrame(journal).to_csv(sortie / f"{pre}_journal-nettoyage_v1.csv", sep=";", index=False, encoding="utf-8-sig")
    cols = ["type", "feuille", "bloc", "region", "statut", "milieu", "niveau_scolaire", "sexe", "annee", "valeur_observee",
            "valeur_attendue", "detail"]
    pd.DataFrame(anomalies, columns=cols).to_csv(sortie / f"{pre}_anomalies_v1.csv", sep=";", index=False, encoding="utf-8-sig")
    (sortie / "LISEZ-MOI.txt").write_text(
        f"DEPOT 02_nettoyage - equipe {a.equipe}, defi {a.defi}, role {a.role}\n"
        f"Genere le {datetime.now():%Y-%m-%d %H:%M} par nettoyage_template.py\n"
        f"Entree : {entree.name} (copie de 01_collecte, jamais modifiee)\n\n"
        "- tableaux-long : 1 ligne = une valeur (region x statut x milieu x niveau x sexe x annee scolaire), avec le type\n"
        "  (effectif / nombre / taux / indice_parite), l'agregat (detail / sous_total / national) et l'adresse Excel d'origine\n"
        "- journal-nettoyage : chaque regle appliquee, lignes avant/apres\n"
        "- anomalies : a verifier (cellules suspectes, G+F<>T, sommes<>totaux, libelles inconnus, valeurs non numeriques)\n"
        "- correspondance-regions : region DGESS -> fond de carte, statuts OK / A VALIDER / INCONNU\n\n"
        "Pieges traites : 13 anciennes regions (jamais assimilees d'office aux 17 nouvelles : rapprochement par le nom, a\n"
        "valider) ; annee scolaire AAAA-AAAA distincte de l'annee civile ; sous-totaux et totaux gardes mais marques (ne pas\n"
        "les sommer deux fois : filtrer agregat = detail) ; taux et IPS non sommables ; valeurs manquantes jamais remplacees\n"
        "par 0 ; texte adresse aux assistants automatiques retire des cellules et signale.\n"
        "Limites : milieu urbain/rural disponible seulement au niveau national dans cette base ; une annee numerique AAAA en\n"
        "en-tete est lue comme l'annee scolaire AAAA-AAAA+1 (a confirmer dans Excel).\n", encoding="utf-8")

    n_hors_detail = int((final.agregat != "detail").sum())
    print(f"\n{len(final)} lignes ({len(final) - n_hors_detail} de detail, {n_hors_detail} sous-totaux/totaux) -> {sortie}")
    print(f"tableaux lus : {len(blocs_info)} | non reconnus : {len(inconnus)} | cellules suspectes retirees : {len(suspectes)}")
    print(f"anomalies a verifier : {len(anomalies)} | regions : " + ", ".join(f"{k}={v}" for k, v in stat.items()))
    print(f"annees de debut presentes : {annees} | manquantes {a.annee_min}-{a.annee_max} : {manque or 'aucune'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
