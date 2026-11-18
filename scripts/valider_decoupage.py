#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VALIDATION DE LA TABLE "province -> ancienne region (13)" avec des fichiers du Data Pack (PDI/CONASUR 2020-2022).

Ces tableaux Excel ont une colonne Region et une colonne Province (decoupage d'AVANT la reforme de 2025). On y releve
les couples (region, province) et on les compare a la table de reference. On ne lit QUE ces deux colonnes.
Aucune valeur chiffree n'est lue ni affichee ; la console n'affiche que des compteurs.

Sorties (dans DOSSIER) :
  EQ_03-transformation_D2_engineer_validation-ancien-decoupage_v1.csv      une ligne par province de la table :
        CONFIRME (meme region dans les fichiers) / DIFFERENT (autre region observee) / NON_OBSERVEE
  EQ_03-transformation_D2_engineer_provinces-hors-table_v1.csv             couples vus dans les fichiers mais absents de la table

Usage :
  python valider_decoupage.py DOSSIER_01_COLLECTE reference/ancien_decoupage_13_a_valider.csv DOSSIER_03 --equipe Burkina_Novation
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import load_workbook

ALIAS_REGIONS = {"haut bassins": "hauts bassins"}      # orthographes connues de la meme region


def norm(s) -> str:
    s = re.sub(r"[’‘ʼ'`´]", " ", str(s))
    t = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", t)).strip()


def nreg(s) -> str:
    """Cle de comparaison d'une region : sans accents, casse, tirets ni espaces (Plateau Central = PlateauCentral)."""
    n = ALIAS_REGIONS.get(norm(s), norm(s))
    return n.replace(" ", "")


def paires_du_fichier(chemin: Path):
    """Couples (region, province) d'un classeur : colonnes dont l'en-tete commence par 'region' et 'province'."""
    out = Counter()
    wb = load_workbook(chemin, read_only=True, data_only=True)
    try:
        for ws in wb.worksheets:
            it = ws.iter_rows(values_only=True)
            ent = None
            for i, row in enumerate(it):
                if i > 15:
                    break
                noms = [norm(c) if c is not None else "" for c in row]
                jr = next((j for j, n in enumerate(noms) if n.startswith("region")), None)
                jp = next((j for j, n in enumerate(noms) if n.startswith("province")), None)
                if jr is not None and jp is not None:
                    ent = (jr, jp)
                    break
            if ent is None:
                continue
            jr, jp = ent
            for row in it:
                if len(row) <= max(jr, jp):
                    continue
                r, p = row[jr], row[jp]
                if r is None or p is None or not str(r).strip() or not str(p).strip():
                    continue
                if norm(r).startswith("total") or norm(p).startswith("total"):
                    continue
                out[(str(r).strip(), str(p).strip())] += 1
    finally:
        wb.close()
    return out


def main(argv=None) -> int:
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Valide la table province -> ancienne region avec les fichiers PDI")
    ap.add_argument("depot", help="dossier 01_collecte")
    ap.add_argument("table", help="CSV province;ancienne_region")
    ap.add_argument("sortie", help="dossier 03_transformation")
    ap.add_argument("--equipe", required=True)
    ap.add_argument("--defi", default="D2")
    ap.add_argument("--role", default="engineer")
    ap.add_argument("--motif", default="*pdi*.xlsx", help="fichiers a examiner (defaut : *pdi*.xlsx)")
    a = ap.parse_args(argv)
    sortie = Path(a.sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    pre = f"{a.equipe}_03-transformation_{a.defi}_{a.role}"

    fichiers = sorted(Path(a.depot).glob(a.motif))
    obs = defaultdict(Counter)                    # province normalisee -> Counter(region normalisee) (en nb de fichiers)
    noms_vus = {}
    fichiers_par = defaultdict(set)               # (province, region) -> noms de fichiers : pour reperer les fichiers mal alignes
    n_lus = 0
    for f in fichiers:
        try:
            paires = paires_du_fichier(f)
        except Exception as e:
            print(f"  illisible : {f.name[:60]} ({str(e)[:60]})")
            continue
        if not paires:
            continue
        n_lus += 1
        vus_fichier = set()                                   # un couple compte UNE fois par fichier
        for (r, p), _ in paires.items():
            vus_fichier.add((norm(p), nreg(r)))
            noms_vus[(norm(p), nreg(r))] = (p, r)
        for k, rg in vus_fichier:
            obs[k][rg] += 1
            fichiers_par[(k, rg)].add(f.name)
    with open(a.table, encoding="utf-8-sig", newline="") as fh:
        table = list(csv.DictReader(fh, delimiter=";"))

    sorties, dans_table = [], set()
    for r in table:
        k, reg_t = norm(r["province"]), nreg(r["ancienne_region"])
        dans_table.add(k)
        c = obs.get(k, Counter())
        if not c:
            statut = "NON_OBSERVEE"
        elif set(c) == {reg_t}:
            statut = "CONFIRME"
        elif c.most_common(1)[0][0] == reg_t and c[reg_t] / sum(c.values()) >= 0.6:
            statut = "CONFIRME_MAJORITE"       # une minorite de fichiers dit autre chose : bruit de saisie probable
        else:
            statut = "DIFFERENT"
        sorties.append({"province_table": r["province"], "ancienne_region_table": r["ancienne_region"],
                        "regions_observees": "; ".join(f"{noms_vus[(k, rg)][1]} ({n} fichier(s))" for rg, n in c.most_common()),
                        "n_fichiers": sum(c.values()), "statut": statut,
                        "fichiers_par_region": " || ".join(
                            noms_vus[(k, rg)][1] + " -> " + ", ".join(
                                n.replace("Burkina_Novation_01-collecte_D2_engineer_", "").replace("_v1.xlsx", "")[:42]
                                for n in sorted(fichiers_par[(k, rg)])[:5]) for rg, _ in c.most_common())})
    hors = [{"province_observee": noms_vus[(k, rg)][0], "region_observee": noms_vus[(k, rg)][1], "n_fichiers": n}
            for k, c in sorted(obs.items()) if k not in dans_table for rg, n in c.items()]
    for nom, lignes, champs in ((f"{pre}_validation-ancien-decoupage_v1.csv", sorties,
                                 ["province_table", "ancienne_region_table", "regions_observees", "n_fichiers", "statut",
                                  "fichiers_par_region"]),
                                (f"{pre}_provinces-hors-table_v1.csv", hors,
                                 ["province_observee", "region_observee", "n_fichiers"])):
        with open(sortie / nom, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=champs, delimiter=";")
            w.writeheader()
            w.writerows(lignes)

    bilan = Counter(s["statut"] for s in sorties)
    regions_vues = {rg for c in obs.values() for rg in c}
    print(f"fichiers examines : {len(fichiers)} | exploitables (colonnes region et province) : {n_lus}")
    print(f"provinces de la table : {len(table)} | " + " ; ".join(f"{k}={v}" for k, v in sorted(bilan.items())))
    print(f"provinces observees hors table : {len(hors)} | regions distinctes observees : {len(regions_vues)}")
    print(f"-> {sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
