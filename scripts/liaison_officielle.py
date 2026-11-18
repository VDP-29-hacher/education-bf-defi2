#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LIAISON OFFICIELLE 13 anciennes regions / 17 nouvelles regions, par les CODES (methode recommandee par le Guide du Data Pack :
"Passez par adm3_pcode_old <-> adm3_pcode du classeur COD-AB pour relier les deux" ; "joignez sur les codes, pas sur les noms").

Source : bfa_admin_boundaries.xlsx (COD-AB, IGB/OCHA via HDX, version aout 2025). Chaque region, province et commune porte son
code ACTUEL et son code ANCIEN (adm*_pcode_old, adm*_name_old). L'ancienne region d'une commune est donnee par les 4 premiers
caracteres de son ancien code (BF46 = Boucle du Mouhoun...), dont le nom est lu dans la feuille bfa_admin1.

Ce script :
  1. construit la correspondance officielle 17 -> 13 (regions), nouvelles provinces -> anciennes provinces, communes -> ancienne region ;
  2. signale les communes dont l'ancienne region differe de celle de leur nouvelle region (communes "a cheval") ;
  3. COMPARE avec la reconstruction faite par les noms de communes (liaison_communes.py), si son CSV est fourni : accord / desaccord ;
  4. ecrit le GeoJSON des 13 anciennes regions (communes regroupees par ancien code).
Aucune valeur chiffree n'est lue. La console n'affiche que des compteurs.

Sorties (DOSSIER) :
  EQ_03-transformation_D2_engineer_liaison-officielle-communes_v1.csv
  EQ_03-transformation_D2_engineer_liaison-officielle-regions_v1.csv        (17 nouvelles regions -> ancienne region)
  EQ_03-transformation_D2_engineer_liaison-officielle-provinces_v1.csv      (47 provinces -> anciennes provinces / regions)
  EQ_03-transformation_D2_engineer_correspondance-13-vers-17-officielle_v1.csv
  EQ_03-transformation_D2_engineer_comparaison-reconstruction-officielle_v1.csv
  EQ_03-transformation_D2_engineer_anciennes-regions-13-officiel_v1.geojson

Usage :
  python liaison_officielle.py bfa_admin_boundaries.xlsx bfa_admin3.geojson DOSSIER_03 --equipe Burkina_Novation [--reconstruction liaison-communes.csv]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import load_workbook


def arrondir(c, nd=4):
    return round(c, nd) if isinstance(c, (int, float)) else [arrondir(x, nd) for x in c]


def polygones(geom):
    if not geom:
        return []
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return list(geom["coordinates"])
    return []


def feuille(wb, nom):
    ws = wb[nom]
    lignes = list(ws.iter_rows(values_only=True))
    ent = [str(c).strip() if c is not None else "" for c in lignes[0]]
    out = []
    for r in lignes[1:]:
        if not any(v is not None and str(v).strip() for v in r):
            continue
        out.append({ent[j]: ("" if v is None else str(v).strip()) for j, v in enumerate(r) if j < len(ent) and ent[j]})
    return out


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
    ap = argparse.ArgumentParser(description="Liaison officielle anciennes/nouvelles regions par les codes COD-AB")
    ap.add_argument("classeur", help="bfa_admin_boundaries.xlsx (COD-AB)")
    ap.add_argument("admin3", help="GeoJSON COD-AB niveau 3 (geometries des communes)")
    ap.add_argument("sortie", help="dossier 03_transformation")
    ap.add_argument("--equipe", required=True)
    ap.add_argument("--defi", default="D2")
    ap.add_argument("--role", default="engineer")
    ap.add_argument("--reconstruction", help="CSV liaison-communes (methode par les noms) pour la comparaison")
    a = ap.parse_args(argv)
    sortie = Path(a.sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    pre = f"{a.equipe}_03-transformation_{a.defi}_{a.role}"

    wb = load_workbook(a.classeur, read_only=True, data_only=True)
    f1, f2, f3 = feuille(wb, "bfa_admin1"), feuille(wb, "bfa_admin2"), feuille(wb, "bfa_admin3")
    wb.close()
    manque = [c for c in ("adm1_pcode_old", "adm1_name_old") if f1 and c not in f1[0]] + \
             [c for c in ("adm3_pcode_old",) if f3 and c not in f3[0]]
    if manque:
        print("ERREUR : colonnes absentes du classeur :", manque)
        return 1

    # ancien code de region (4 caracteres) -> nom de l'ancienne region
    nom_ancienne = {}
    for r in f1:
        nom_ancienne.setdefault(r["adm1_pcode_old"][:4], r["adm1_name_old"])
    reg_ancienne = {r["adm1_pcode"]: (r["adm1_name_old"], r["adm1_pcode_old"]) for r in f1}
    prov_info = {r["adm2_pcode"]: r for r in f2}
    # ancien code de province (6 caracteres) -> nom de l'ancienne province (meme methode que pour les regions)
    nom_prov_ancienne = {}
    for r in f2:
        if r.get("adm2_pcode_old"):
            nom_prov_ancienne.setdefault(r["adm2_pcode_old"][:6], r.get("adm2_name_old", ""))

    # --- regions : 17 -> 13 ------------------------------------------------------------------------------
    regions = [{"nouvelle_region": r["adm1_name"], "pcode_nouvelle_region": r["adm1_pcode"],
                "ancienne_region": r["adm1_name_old"], "pcode_ancienne_region": r["adm1_pcode_old"]} for r in f1]

    # --- communes ------------------------------------------------------------------------------------------
    communes, anomalies = [], []
    for r in f3:
        code_old = r.get("adm3_pcode_old", "")
        prov = prov_info.get(r.get("adm2_pcode", ""), {})
        reg_via_commune = nom_ancienne.get(code_old[:4], "")
        reg_via_nouvelle_region = reg_ancienne.get(r.get("adm1_pcode", ""), ("", ""))[0]
        origine = "code ancien de la commune"
        reg = reg_via_commune
        if not reg:
            reg, origine = reg_via_nouvelle_region, "nouvelle region (code ancien de commune absent ou inconnu)"
        a_cheval = bool(reg_via_commune and reg_via_nouvelle_region and reg_via_commune != reg_via_nouvelle_region)
        if a_cheval:
            anomalies.append({"type": "commune_a_cheval",
                              "detail": f"{r['adm3_name']} ({r.get('adm2_name','')}, nouvelle region {r.get('adm1_name','')}) : "
                                        f"ancienne region {reg_via_commune} alors que la nouvelle region correspond a {reg_via_nouvelle_region}"})
        communes.append({"commune": r["adm3_name"], "pcode_commune": r["adm3_pcode"], "pcode_ancien_commune": code_old,
                         "nom_ancien_commune": r.get("adm3_name_old", ""), "nouvelle_province": r.get("adm2_name", ""),
                         "pcode_nouvelle_province": r.get("adm2_pcode", ""), "ancienne_province": prov.get("adm2_name_old", ""),
                         "nouvelle_region": r.get("adm1_name", ""), "pcode_nouvelle_region": r.get("adm1_pcode", ""),
                         "ancienne_province_par_commune": nom_prov_ancienne.get(code_old[:6], "") or prov.get("adm2_name_old", ""),
                         "ancienne_region": reg, "origine": origine, "a_cheval": "oui" if a_cheval else "non"})

    # --- provinces : 47 -> anciennes provinces et regions ------------------------------------------------------
    par_prov = defaultdict(list)
    for c in communes:
        par_prov[c["pcode_nouvelle_province"]].append(c)
    provinces = []
    for pc, cs in sorted(par_prov.items()):
        info = prov_info.get(pc, {})
        rep = Counter(c["ancienne_region"] for c in cs)
        provinces.append({"pcode_province": pc, "nouvelle_province": info.get("adm2_name", cs[0]["nouvelle_province"]),
                          "nouvelle_region": cs[0]["nouvelle_region"], "ancienne_province": info.get("adm2_name_old", ""),
                          "pcode_ancien_province": info.get("adm2_pcode_old", ""), "n_communes": len(cs),
                          "ancienne_region_majoritaire": rep.most_common(1)[0][0],
                          "repartition_communes": "; ".join(f"{k} ({n})" for k, n in rep.most_common())})

    # --- correspondance 13 -> 17 par les communes ------------------------------------------------------------------
    croise = Counter((c["ancienne_region"], c["nouvelle_region"]) for c in communes)
    tot = Counter()
    for (anc, _), n in croise.items():
        tot[anc] += n
    corr = [{"ancienne_region": anc, "nouvelle_region": nou, "n_communes": n, "part_de_l_ancienne_region": round(n / tot[anc], 3),
             "ancienne_region_decoupee": "oui" if len({n2 for (a2, n2) in croise if a2 == anc}) > 1 else "non"}
            for (anc, nou), n in sorted(croise.items())]

    # --- comparaison avec la reconstruction par les noms -----------------------------------------------------------
    stats = Counter()
    comp = []
    if a.reconstruction and Path(a.reconstruction).is_file():
        with open(a.reconstruction, encoding="utf-8-sig", newline="") as f:
            mine = {r["pcode_commune"]: r for r in csv.DictReader(f, delimiter=";")}
        off = {c["pcode_commune"]: c for c in communes}
        for pc, o in off.items():
            m = mine.get(pc)
            if not m:
                stats["absente de la reconstruction"] += 1
                continue
            type_m = "directe" if m["statut"] == "APPARIEE" else ("inferee" if m["ancienne_region"] else "non resolue")
            accord = "oui" if m["ancienne_region"] and m["ancienne_region"] == o["ancienne_region"] else "non"
            stats[f"{type_m} / accord={accord}"] += 1
            if accord == "non":
                comp.append({"commune": o["commune"], "pcode_commune": pc, "nouvelle_province": o["nouvelle_province"],
                             "reconstruction": m["ancienne_region"] or "(aucune)", "officiel": o["ancienne_region"],
                             "type_reconstruction": type_m})
        ecrire_csv(sortie / f"{pre}_comparaison-reconstruction-officielle_v1.csv", comp,
                   ["commune", "pcode_commune", "nouvelle_province", "reconstruction", "officiel", "type_reconstruction"])

    # --- GeoJSON des 13 anciennes regions (communes regroupees) --------------------------------------------------
    geom = {}
    for ft in json.loads(Path(a.admin3).read_text(encoding="utf-8")).get("features", []):
        geom[ft.get("properties", {}).get("adm3_pcode", "")] = ft.get("geometry")
    groupes = defaultdict(list)
    for c in communes:
        groupes[c["ancienne_region"]].append(c)
    feats = [{"type": "Feature", "properties": {"ancienne_region": reg, "n_communes": len(cs),
                                                 "nouvelles_regions": sorted({c["nouvelle_region"] for c in cs})},
              "geometry": {"type": "MultiPolygon", "coordinates": [arrondir(p) for c in cs for p in polygones(geom.get(c["pcode_commune"]))]}}
             for reg, cs in sorted(groupes.items())]
    (sortie / f"{pre}_anciennes-regions-13-officiel_v1.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False), encoding="utf-8")

    # --- GeoJSON des anciennes provinces (communes regroupees par ancien code de province) ---------------------------
    gp = defaultdict(list)
    for c in communes:
        gp[c["ancienne_province_par_commune"]].append(c)
    feats_p = [{"type": "Feature", "properties": {"ancienne_province": nom, "ancienne_region": Counter(c["ancienne_region"] for c in cs).most_common(1)[0][0],
                                                   "n_communes": len(cs)},
                "geometry": {"type": "MultiPolygon", "coordinates": [arrondir(p) for c in cs for p in polygones(geom.get(c["pcode_commune"]))]}}
               for nom, cs in sorted(gp.items()) if nom]
    (sortie / f"{pre}_anciennes-provinces-officiel_v1.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": feats_p}, ensure_ascii=False), encoding="utf-8")
    print(f"anciennes provinces (GeoJSON) : {len(feats_p)} | communes sans ancienne province : {len(gp.get('', []))}")

    ecrire_csv(sortie / f"{pre}_liaison-officielle-communes_v1.csv", communes,
               ["commune", "pcode_commune", "pcode_ancien_commune", "nom_ancien_commune", "nouvelle_province",
                "pcode_nouvelle_province", "ancienne_province", "ancienne_province_par_commune", "nouvelle_region", "pcode_nouvelle_region",
                "ancienne_region", "origine", "a_cheval"])
    ecrire_csv(sortie / f"{pre}_liaison-officielle-regions_v1.csv", regions,
               ["nouvelle_region", "pcode_nouvelle_region", "ancienne_region", "pcode_ancienne_region"])
    ecrire_csv(sortie / f"{pre}_liaison-officielle-provinces_v1.csv", provinces,
               ["pcode_province", "nouvelle_province", "nouvelle_region", "ancienne_province", "pcode_ancien_province",
                "n_communes", "ancienne_region_majoritaire", "repartition_communes"])
    ecrire_csv(sortie / f"{pre}_correspondance-13-vers-17-officielle_v1.csv", corr,
               ["ancienne_region", "nouvelle_region", "n_communes", "part_de_l_ancienne_region", "ancienne_region_decoupee"])
    ecrire_csv(sortie / f"{pre}_anomalies-liaison-officielle_v1.csv", anomalies, ["type", "detail"])

    decoupees = sorted({c["ancienne_region"] for c in corr if c["ancienne_region_decoupee"] == "oui"})
    print(f"classeur COD-AB : {len(f1)} regions, {len(f2)} provinces, {len(f3)} communes | anciennes regions : {len(groupes)}")
    print(f"communes dont l'ancienne region differe de celle de leur nouvelle region (a cheval) : "
          f"{sum(1 for c in communes if c['a_cheval'] == 'oui')}")
    print(f"anciennes regions decoupees en plusieurs nouvelles : {len(decoupees)} ({', '.join(decoupees)})")
    if stats:
        print("comparaison avec la reconstruction par les noms :")
        for k, v in sorted(stats.items()):
            print(f"  {k} : {v}")
    print(f"-> {sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
