#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LIAISON PAR LES COMMUNES : ancienne region (13) de chaque nouvelle province / commune du fond de carte COD-AB 2026 (17 regions).

Probleme : le fond de carte 2026 a 47 provinces (dont des noms nouveaux) et 17 regions ; la base DGESS est en 13 anciennes
regions. On ne devine pas les nouveaux noms. On passe par les COMMUNES, dont les noms sont stables :
  - fichiers PDI/CONASUR 2020-2022 : pour chaque commune, sa province et sa region d'AVANT la reforme (vote majoritaire
    entre fichiers : un fichier mal saisi ne decide pas) ;
  - COD-AB niveau 3 : pour chaque commune, sa province et sa region ACTUELLES.
On en deduit, pour chaque nouvelle province, la repartition de ses communes par ancienne region (avec un taux de confiance).
Seul le nom de commune sert de cle ; les noms ambigus (meme nom dans plusieurs provinces) sont mis de cote puis infere.
Aucune valeur chiffree n'est lue. La console n'affiche que des compteurs.

Sorties (dans DOSSIER) :
  EQ_03-transformation_D2_engineer_liaison-communes_v1.csv                 une ligne par commune (COD-AB) : ancienne region
  EQ_03-transformation_D2_engineer_liaison-provinces-nouvelles_v1.csv       une ligne par nouvelle province : repartition par ancienne region
  EQ_03-transformation_D2_engineer_correspondance-13-vers-17-communes_v1.csv   ancienne x nouvelle region (nb de communes)
  EQ_03-transformation_D2_engineer_anciennes-regions-13-communes_v1.geojson    les 13 anciennes regions (communes regroupees)
  EQ_03-transformation_D2_engineer_anomalies-liaison-communes_v1.csv        communes non trouvees, ambigues, provinces a valider

Usage :
  python liaison_communes.py bfa_admin3.geojson DOSSIER_01_COLLECTE reference/ancien_decoupage_13_a_valider.csv DOSSIER_03 --equipe Burkina_Novation
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import load_workbook

SEUIL_CONFIANCE = 0.9        # part min. de communes appariees d'une province d'accord sur l'ancienne region
MIN_COMMUNES = 3             # nombre min. de communes appariees pour parler de "OK"


def norm(s) -> str:
    s = re.sub(r"[’‘ʼ'`´]", " ", str(s))
    t = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", t)).strip()


def cle(s) -> str:
    return norm(s).replace(" ", "")


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


def triplets(chemin: Path):
    """Triplets (region, province, commune) d'un classeur PDI : colonnes dont l'en-tete commence par region/province/commune."""
    out = set()
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
                jc = next((j for j, n in enumerate(noms) if n.startswith("commune")), None)
                if None not in (jr, jp, jc):
                    ent = (jr, jp, jc)
                    break
            if ent is None:
                continue
            for row in it:
                if len(row) <= max(ent):
                    continue
                r, p, c = (row[j] for j in ent)
                if any(v is None or not str(v).strip() for v in (r, p, c)):
                    continue
                if any(norm(v).startswith("total") for v in (r, p, c)):
                    continue
                out.add((str(r).strip(), str(p).strip(), str(c).strip()))
    finally:
        wb.close()
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
    ap = argparse.ArgumentParser(description="Ancienne region (13) de chaque nouvelle commune/province, par les communes")
    ap.add_argument("admin3", help="GeoJSON COD-AB niveau 3 (communes)")
    ap.add_argument("depot", help="dossier 01_collecte (fichiers PDI)")
    ap.add_argument("table", help="CSV province;ancienne_region (provinces d'avant la reforme, validee)")
    ap.add_argument("sortie", help="dossier 03_transformation")
    ap.add_argument("--equipe", required=True)
    ap.add_argument("--defi", default="D2")
    ap.add_argument("--role", default="engineer")
    ap.add_argument("--motif", default="*pdi*.xlsx")
    a = ap.parse_args(argv)
    sortie = Path(a.sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    pre = f"{a.equipe}_03-transformation_{a.defi}_{a.role}"

    # --- ancienne region de chaque ancienne province (table validee par les PDI) -----------------------
    with open(a.table, encoding="utf-8-sig", newline="") as f:
        region_de_prov = {cle(r["province"]): r["ancienne_region"].strip() for r in csv.DictReader(f, delimiter=";")}

    # --- PDI : pour chaque commune, vote des fichiers sur (province, region) ------------------------------
    votes = defaultdict(Counter)                      # cle commune -> Counter((province_brute, region_brute))
    n_fichiers = 0
    for f in sorted(Path(a.depot).glob(a.motif)):
        try:
            t = triplets(f)
        except Exception:
            continue
        if not t:
            continue
        n_fichiers += 1
        vus = {(cle(c), p, r) for r, p, c in t}     # une commune compte une fois par fichier
        for kc, p, r in vus:
            votes[kc][(p, r)] += 1
    pdi = {}                                          # cle commune -> dict ancienne province / region (majoritaires)
    ambigus = set()
    for kc, cnt in votes.items():
        provs = Counter()
        for (p, _r), n in cnt.items():
            provs[cle(p)] += n
        if len(provs) > 1 and provs.most_common(2)[1][1] >= 0.4 * provs.most_common(1)[0][1]:
            ambigus.add(kc)                          # meme nom de commune dans plusieurs provinces anciennes
            continue
        kp = provs.most_common(1)[0][0]
        regs = Counter()
        for (p, _r), n in cnt.items():
            if cle(p) == kp:
                regs[r] += n
        nom_p = next(p for (p, r) in cnt if cle(p) == kp)
        reg_table = region_de_prov.get(kp, "")
        pdi[kc] = {"ancienne_province": nom_p, "ancienne_region_pdi": regs.most_common(1)[0][0],
                   "ancienne_region_table": reg_table, "n_fichiers": sum(regs.values())}

    # --- COD-AB niveau 3 --------------------------------------------------------------------------------
    feats = json.loads(Path(a.admin3).read_text(encoding="utf-8")).get("features", [])
    communes, anomalies = [], []
    for ft in feats:
        p = ft.get("properties", {})
        nom = p.get("adm3_name")
        if not nom:
            continue
        noms = [p.get(k) for k in ("adm3_name", "adm3_name1", "adm3_name2", "adm3_name3") if p.get(k)]
        c = {"commune": nom, "pcode_commune": p.get("adm3_pcode", ""), "nouvelle_province": p.get("adm2_name", ""),
             "pcode_nouvelle_province": p.get("adm2_pcode", ""), "nouvelle_region": p.get("adm1_name", ""),
             "pcode_nouvelle_region": p.get("adm1_pcode", ""), "geometry": ft.get("geometry"),
             "statut": "", "ancienne_province_pdi": "", "ancienne_region": "", "origine_ancienne_region": "", "n_fichiers_pdi": ""}
        kc = next((cle(n) for n in noms if cle(n) in pdi), None)
        if kc:
            d = pdi[kc]
            reg = d["ancienne_region_table"] or d["ancienne_region_pdi"]
            c.update(statut="APPARIEE", ancienne_province_pdi=d["ancienne_province"], ancienne_region=reg,
                     origine_ancienne_region="pdi" + (" + table" if d["ancienne_region_table"] else " (region PDI)"),
                     n_fichiers_pdi=d["n_fichiers"])
            if d["ancienne_region_table"] and cle(d["ancienne_region_pdi"]) != cle(d["ancienne_region_table"]):
                anomalies.append({"type": "region_pdi_differente_de_la_table",
                                  "detail": f"{nom} : PDI dit {d['ancienne_region_pdi']}, la table de {d['ancienne_province']} dit {d['ancienne_region_table']}"})
        elif any(cle(n) in ambigus for n in noms):
            c["statut"] = "AMBIGUE"
        else:
            c["statut"] = "NON_TROUVEE_DANS_PDI"
        communes.append(c)

    # --- par nouvelle province : repartition par ancienne region --------------------------------------
    par_prov = defaultdict(list)
    for c in communes:
        par_prov[(c["pcode_nouvelle_province"], c["nouvelle_province"], c["nouvelle_region"])].append(c)
    provinces = []
    maj = {}
    for (pc, nom, reg), cs in sorted(par_prov.items()):
        app = [c for c in cs if c["statut"] == "APPARIEE"]
        rep = Counter(c["ancienne_region"] for c in app)
        top, n_top = (rep.most_common(1)[0] if rep else ("", 0))
        part = n_top / len(app) if app else 0.0
        ok = bool(app) and part >= SEUIL_CONFIANCE and len(app) >= MIN_COMMUNES
        maj[pc] = top
        provinces.append({"pcode_province": pc, "nouvelle_province": nom, "nouvelle_region": reg, "n_communes": len(cs),
                          "n_communes_appariees": len(app), "ancienne_region_majoritaire": top,
                          "part_majoritaire": round(part, 3),
                          "repartition": "; ".join(f"{r} ({n})" for r, n in rep.most_common()),
                          "statut": "OK" if ok else ("A VALIDER" if app else "AUCUNE COMMUNE APPARIEE")})
        if not ok:
            anomalies.append({"type": "province_a_valider",
                              "detail": f"{nom} ({pc}) : {len(app)}/{len(cs)} communes appariees ; {'; '.join(f'{r} ({n})' for r, n in rep.most_common()) or 'aucune'}"})
        elif len(rep) > 1:
            anomalies.append({"type": "province_a_cheval_sur_plusieurs_anciennes_regions",
                              "detail": f"{nom} : {'; '.join(f'{r} ({n})' for r, n in rep.most_common())}"})
    # --- communes non appariees : inferees depuis la majorite de leur nouvelle province ------------------
    for c in communes:
        if c["statut"] != "APPARIEE":
            c["ancienne_region"] = maj.get(c["pcode_nouvelle_province"], "")
            c["origine_ancienne_region"] = "inferee (majorite de la province)" if c["ancienne_region"] else "inconnue"
            anomalies.append({"type": "commune_" + c["statut"].lower(),
                              "detail": f"{c['commune']} ({c['nouvelle_province']}) -> {c['ancienne_region'] or 'inconnue'} [{c['origine_ancienne_region']}]"})

    # --- correspondance 13 -> 17 et GeoJSON ----------------------------------------------------------------
    croise = Counter((c["ancienne_region"], c["nouvelle_region"]) for c in communes if c["ancienne_region"])
    tot_anc = Counter()
    for (anc, _), n in croise.items():
        tot_anc[anc] += n
    corr = [{"ancienne_region": anc, "nouvelle_region": nou, "n_communes": n,
             "part_de_l_ancienne_region": round(n / tot_anc[anc], 3)} for (anc, nou), n in sorted(croise.items())]
    groupes = defaultdict(list)
    for c in communes:
        if c["ancienne_region"]:
            groupes[c["ancienne_region"]].append(c)
    feats_out = []
    for reg, cs in sorted(groupes.items()):
        polys = [arrondir(p) for c in cs for p in polygones(c["geometry"])]
        feats_out.append({"type": "Feature", "properties": {
            "ancienne_region": reg, "n_communes": len(cs),
            "n_communes_inferees": sum(1 for c in cs if c["statut"] != "APPARIEE")},
            "geometry": {"type": "MultiPolygon", "coordinates": polys}})
    (sortie / f"{pre}_anciennes-regions-13-communes_v1.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": feats_out}, ensure_ascii=False), encoding="utf-8")
    champs_c = ["commune", "pcode_commune", "nouvelle_province", "pcode_nouvelle_province", "nouvelle_region",
                "pcode_nouvelle_region", "statut", "ancienne_province_pdi", "ancienne_region", "origine_ancienne_region",
                "n_fichiers_pdi"]
    ecrire_csv(sortie / f"{pre}_liaison-communes_v1.csv", communes, champs_c)
    ecrire_csv(sortie / f"{pre}_liaison-provinces-nouvelles_v1.csv", provinces,
               ["pcode_province", "nouvelle_province", "nouvelle_region", "n_communes", "n_communes_appariees",
                "ancienne_region_majoritaire", "part_majoritaire", "repartition", "statut"])
    ecrire_csv(sortie / f"{pre}_correspondance-13-vers-17-communes_v1.csv", corr,
               ["ancienne_region", "nouvelle_region", "n_communes", "part_de_l_ancienne_region"])
    ecrire_csv(sortie / f"{pre}_anomalies-liaison-communes_v1.csv", anomalies, ["type", "detail"])

    st = Counter(c["statut"] for c in communes)
    sp = Counter(p["statut"] for p in provinces)
    print(f"fichiers PDI exploites : {n_fichiers} | communes distinctes dans les PDI : {len(votes)} (ambigues : {len(ambigus)})")
    print(f"communes COD-AB : {len(communes)} | " + " ; ".join(f"{k}={v}" for k, v in sorted(st.items())))
    print(f"nouvelles provinces : {len(provinces)} | " + " ; ".join(f"{k}={v}" for k, v in sorted(sp.items())))
    print(f"anciennes regions reconstituees : {len(groupes)} | nouvelles regions : {len({c['nouvelle_region'] for c in communes})}")
    print(f"anomalies : {len(anomalies)} -> {sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
