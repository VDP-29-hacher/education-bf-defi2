#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LIAISON ANCIENNES REGIONS (13) / NOUVELLES REGIONS (17) - Etape 3 (03_transformation) - Defi 2.

Piege du PDF : "les anciennes (13) et nouvelles (17) regions ne se recoupent pas". On ne convertit JAMAIS des chiffres
d'un decoupage a l'autre. On passe par les PROVINCES, communes aux deux : chacune appartient a une ancienne region et a
une nouvelle (fond de carte COD-AB, niveau 2).

Entrees :
  - fond de carte COD-AB niveau 2 (bfa_admin2.geojson) : adm2_name, adm2_pcode, adm1_name (nouvelle region), adm1_pcode
  - table province;ancienne_region  (reference/ancien_decoupage_13_a_valider.csv : A VALIDER avec le RGPH 2019 / INSD)

Sorties (dans DOSSIER_03) :
  EQ_03-transformation_D2_engineer_liaison-provinces_v1.csv           province, P-codes, nouvelle region, ancienne region
  EQ_03-transformation_D2_engineer_correspondance-13-vers-17_v1.csv   ancienne region x nouvelle region (nb de provinces)
  EQ_03-transformation_D2_engineer_anomalies-liaison_v1.csv           provinces non appariees, suggestions, doublons
  EQ_03-transformation_D2_engineer_anciennes-regions-13_v1.geojson    les 13 anciennes regions (provinces regroupees), pour la carte
  LISEZ-MOI-liaison.txt

La console n'affiche que des compteurs. Un rapprochement approximatif de nom n'est jamais applique d'office (suggestion).

Usage :
  python liaison_regions.py bfa_admin2.geojson reference/ancien_decoupage_13_a_valider.csv DOSSIER_03 --equipe Burkina_Novation
"""
from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path

SEUIL_FLOU = 0.86


def norm(s) -> str:
    s = re.sub(r"[’‘ʼ'`´]", " ", str(s))
    t = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", t)).strip()


def arrondir(c, nd=5):
    return round(c, nd) if isinstance(c, (int, float)) else [arrondir(x, nd) for x in c]


def polygones(geom):
    if not geom:
        return []
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return list(geom["coordinates"])
    return []


def ecrire_csv(chemin: Path, lignes: list, champs: list):
    with open(chemin, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=champs, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(lignes)


def main(argv=None) -> int:
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Liaison 13 anciennes / 17 nouvelles regions par les provinces")
    ap.add_argument("admin2", help="GeoJSON COD-AB niveau 2 (provinces)")
    ap.add_argument("decoupage", help="CSV province;ancienne_region")
    ap.add_argument("sortie", help="dossier 03_transformation")
    ap.add_argument("--equipe", required=True)
    ap.add_argument("--defi", default="D2")
    ap.add_argument("--role", default="engineer")
    ap.add_argument("--alias", help="CSV brut;officiel : corrections validees des noms de provinces")
    ap.add_argument("--appliquer-flou", action="store_true", help="appliquer aussi les rapprochements approximatifs")
    a = ap.parse_args(argv)
    sortie = Path(a.sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    pre = f"{a.equipe}_03-transformation_{a.defi}_{a.role}"

    # --- fond de carte : provinces et leur nouvelle region -------------------------------------------
    feats = json.loads(Path(a.admin2).read_text(encoding="utf-8")).get("features", [])
    par_pcode, par_nom = {}, {}
    for ft in feats:
        p = ft.get("properties", {})
        if not p.get("adm2_name"):
            continue
        fiche = {"province": p["adm2_name"], "pcode": p.get("adm2_pcode", ""), "nouvelle_region": p.get("adm1_name", ""),
                 "pcode_nouvelle_region": p.get("adm1_pcode", ""), "geometry": ft.get("geometry")}
        par_pcode[fiche["pcode"] or fiche["province"]] = fiche
        for k in ("adm2_name", "adm2_name1", "adm2_name2", "adm2_name3"):
            if p.get(k):
                par_nom.setdefault(norm(p[k]), fiche)
    alias = {}
    if a.alias and Path(a.alias).exists():
        with open(a.alias, encoding="utf-8-sig", newline="") as f:
            alias = {norm(r["brut"]): r["officiel"] for r in csv.DictReader(f, delimiter=";") if r.get("brut")}

    # --- table de l'ancien decoupage -----------------------------------------------------------------
    with open(a.decoupage, encoding="utf-8-sig", newline="") as f:
        ancien = list(csv.DictReader(f, delimiter=";"))
    liaison, anomalies, deja = [], [], {}
    for r in ancien:
        prov, reg = r["province"].strip(), r["ancienne_region"].strip()
        k = norm(alias.get(norm(prov), prov))
        fiche, statut, suggestion = par_nom.get(k), "OK", ""
        if fiche is None:
            m = difflib.get_close_matches(k, list(par_nom), n=1, cutoff=SEUIL_FLOU)
            if m:
                suggestion = par_nom[m[0]]["province"]
                statut = "A VALIDER (suggestion)"
                if a.appliquer_flou:
                    fiche = par_nom[m[0]]
            else:
                statut = "INCONNUE du fond de carte"
        ligne = {"province_table": prov, "ancienne_region": reg, "statut_appariement": statut, "suggestion": suggestion,
                 "validation_table": r.get("statut", ""), "province": "", "pcode_province": "", "nouvelle_region": "",
                 "pcode_nouvelle_region": ""}
        if fiche is not None:
            ligne.update(province=fiche["province"], pcode_province=fiche["pcode"], nouvelle_region=fiche["nouvelle_region"],
                         pcode_nouvelle_region=fiche["pcode_nouvelle_region"])
            if fiche["pcode"] in deja:
                anomalies.append({"type": "province_en_double", "detail": f"{prov} et {deja[fiche['pcode']]} designent la meme province"})
            deja[fiche["pcode"]] = prov
        else:
            anomalies.append({"type": "province_non_appariee", "detail": f"{prov} ({reg}) : {statut}"
                                                                          + (f" -> {suggestion}" if suggestion else "")})
        liaison.append(ligne)
    sans_ancienne = [f for pc, f in par_pcode.items() if pc not in deja]
    for f in sans_ancienne:
        anomalies.append({"type": "province_du_fond_de_carte_sans_ancienne_region",
                          "detail": f"{f['province']} ({f['pcode']}) : absente de la table de l'ancien decoupage"})
    ecrire_csv(sortie / f"{pre}_liaison-provinces_v1.csv", liaison,
               ["province", "pcode_province", "nouvelle_region", "pcode_nouvelle_region", "ancienne_region",
                "statut_appariement", "suggestion", "province_table", "validation_table"])

    # --- correspondance 13 -> 17 ---------------------------------------------------------------------
    croise = defaultdict(list)
    for l in liaison:
        if l["pcode_province"]:
            croise[(l["ancienne_region"], l["nouvelle_region"])].append(l["province"])
    n_par_ancienne = defaultdict(int)
    for (anc, _), provs in croise.items():
        n_par_ancienne[anc] += len(provs)
    nb_nouv = defaultdict(int)
    for (anc, _) in croise:
        nb_nouv[anc] += 1
    corr = [{"ancienne_region": anc, "nouvelle_region": nou, "n_provinces": len(provs),
             "part_des_provinces_de_l_ancienne_region": round(len(provs) / n_par_ancienne[anc], 3),
             "ancienne_region_decoupee": "oui" if nb_nouv[anc] > 1 else "non", "provinces": "; ".join(sorted(provs))}
            for (anc, nou), provs in sorted(croise.items())]
    ecrire_csv(sortie / f"{pre}_correspondance-13-vers-17_v1.csv", corr,
               ["ancienne_region", "nouvelle_region", "n_provinces", "part_des_provinces_de_l_ancienne_region",
                "ancienne_region_decoupee", "provinces"])

    # --- GeoJSON des 13 anciennes regions (provinces regroupees : pas d'union topologique) --------------
    groupes = defaultdict(list)
    for l in liaison:
        if l["pcode_province"]:
            groupes[l["ancienne_region"]].append(par_pcode[l["pcode_province"]])
    sorties = []
    for reg, fiches in sorted(groupes.items()):
        polys = [arrondir(p) for f in fiches for p in polygones(f["geometry"])]
        sorties.append({"type": "Feature", "properties": {"ancienne_region": reg, "n_provinces": len(fiches),
                                                           "provinces": [f["province"] for f in fiches]},
                        "geometry": {"type": "MultiPolygon", "coordinates": polys}})
    (sortie / f"{pre}_anciennes-regions-13_v1.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": sorties}, ensure_ascii=False), encoding="utf-8")
    ecrire_csv(sortie / f"{pre}_anomalies-liaison_v1.csv", anomalies, ["type", "detail"])

    decoupees = sorted({c["ancienne_region"] for c in corr if c["ancienne_region_decoupee"] == "oui"})
    (sortie / "LISEZ-MOI-liaison.txt").write_text(
        f"LIAISON 13 anciennes regions / 17 nouvelles regions - equipe {a.equipe}\nGenere le {datetime.now():%Y-%m-%d %H:%M}\n\n"
        "Methode : on ne convertit jamais de chiffres d'un decoupage a l'autre. Chaque province appartient a une ancienne region\n"
        "(table de reference) et a une nouvelle region (fond de carte COD-AB, niveau 2).\n"
        "ATTENTION : la table de l'ancien decoupage vient de la connaissance d'un assistant IA, non verifiee : elle doit etre\n"
        "validee avec une source officielle (RGPH 2019, annuaire statistique INSD) avant tout usage.\n"
        "- liaison-provinces : une ligne par province (P-codes, nouvelle region, ancienne region, statut d'appariement)\n"
        "- correspondance-13-vers-17 : combien de provinces de chaque ancienne region tombent dans chaque nouvelle region\n"
        "- anciennes-regions-13.geojson : les 13 anciennes regions (provinces regroupees) pour la carte\n"
        "- anomalies-liaison : provinces non appariees ou en double\n", encoding="utf-8")

    n_ok = sum(1 for l in liaison if l["pcode_province"])
    print(f"table de l'ancien decoupage : {len(ancien)} provinces | appariees au fond de carte : {n_ok} | "
          f"non appariees : {len(ancien) - n_ok}")
    print(f"fond de carte : {len(par_pcode)} provinces | sans ancienne region : {len(sans_ancienne)} | "
          f"nouvelles regions : {len({f['nouvelle_region'] for f in par_pcode.values()})}")
    print(f"anciennes regions : {len(groupes)} | decoupees sur plusieurs nouvelles regions : {len(decoupees)}")
    print(f"anomalies : {len(anomalies)} -> {sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
