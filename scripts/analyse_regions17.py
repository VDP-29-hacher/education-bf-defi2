#!/usr/bin/env python3
"""LES 17 REGIONS ACTUELLES (Defi 2) - indicateurs du primaire sur le decoupage en vigueur, par agregation EXACTE des provinces.

Pourquoi c'est exact : chacune des 45 anciennes provinces est entierement comprise dans une seule des 17 nouvelles regions
(verifie commune par commune avec les codes COD-AB, table liaison-officielle-communes de l'etape 3). Les effectifs par sexe
des provinces s'additionnent donc sans approximation ; aucun chiffre n'est reparti ni estime.
Entrees : 02_nettoyage/*_annuaire-primaire-*-provinces_v1.csv (effectifs par province, sexe, annee ; urbain/rural 2024)
          03_transformation/*_liaison-officielle-communes_v1.csv (ancienne province -> nouvelle region)
Sortie  : 04_analyse/<EQ>_04-analyse_D2_analyst_regions17-indicateurs_v1.csv
Usage   : analyse_regions17.py DOSSIER_02 DOSSIER_03 DOSSIER_04 [--equipe Burkina_Novation]
"""
import argparse, glob, os, sys
import pandas as pd

ALIAS = {"Komandjari": "Komondjari", "Kourittenga": "Kouritenga"}   # orthographes COD-AB -> annuaire DGESS (documentees a l'etape 2)
SEUIL_EFFONDREMENT = 0.10


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dossier02"); ap.add_argument("dossier03"); ap.add_argument("dossier04"); ap.add_argument("--equipe", default="Burkina_Novation")
    a = ap.parse_args()
    f = [x for x in sorted(glob.glob(os.path.join(a.dossier02, "*_annuaire-primaire-*-provinces_v1.csv"))) if "controles" not in os.path.basename(x)]
    fl = glob.glob(os.path.join(a.dossier03, "*_liaison-officielle-communes_v1.csv"))
    if not f or not fl:
        sys.exit("Tables provinces (etape 2) ou liaison officielle (etape 3) introuvables.")
    df = pd.read_csv(f[-1], sep=";", encoding="utf-8-sig", keep_default_na=False, dtype=str)
    df["effectif"] = pd.to_numeric(df.effectif, errors="coerce"); df["annee_debut"] = pd.to_numeric(df.annee_debut, errors="coerce")
    li = pd.read_csv(fl[0], sep=";", encoding="utf-8-sig", dtype=str)
    li["province"] = li.ancienne_province_par_commune.replace(ALIAS)
    m = li.groupby("province").nouvelle_region.agg(lambda s: sorted(set(s)))
    if (m.map(len) != 1).any():
        sys.exit("Une ancienne province est a cheval sur deux nouvelles regions : agregation exacte impossible.")
    p2r = m.map(lambda s: s[0]).to_dict()
    p2old = li.groupby("province").ancienne_region.first().to_dict()

    h = df[(df.table == "effectifs_province") & (df.niveau_geo == "province") & df.sexe.isin(["garcons", "filles"])].copy()
    h["region17"] = h.province.map(p2r)
    manq = sorted(set(h.province) - set(p2r))
    if manq:
        sys.exit(f"Provinces sans nouvelle region : {manq}")
    hp = h.pivot_table(index=["region17", "annee_debut"], columns="sexe", values="effectif", aggfunc="sum")
    tot = (hp.garcons + hp.filles).unstack("annee_debut")
    ips = (hp.filles / hp.garcons).unstack("annee_debut")
    part = tot.div(tot.max(axis=1), axis=0)
    ips = ips.mask(part < SEUIL_EFFONDREMENT)
    a0, a1 = int(tot.columns.min()), int(tot.columns.max())
    r = df[(df.table == "repartition_niveau_sexe") & (df.niveau_geo == "province") & df.sexe.isin(["garcons", "filles"]) & (df.classe == "Total")].copy()
    r["region17"] = r.province.map(p2r)
    mil = r[r.categorie.isin(["urbain", "rural"])].pivot_table(index=["region17", "categorie"], columns="sexe", values="effectif", aggfunc="sum")
    mil = (mil.filles / mil.garcons).unstack("categorie")

    out = pd.DataFrame(index=sorted(tot.index))
    out.index.name = "nouvelle_region"
    out["anciennes_regions"] = [", ".join(sorted({p2old[p] for p, rg in p2r.items() if rg == x})) for x in out.index]
    out["provinces"] = [", ".join(sorted(p for p, rg in p2r.items() if rg == x)) for x in out.index]
    out["n_provinces"] = [sum(1 for rg in p2r.values() if rg == x) for x in out.index]
    for y in tot.columns:
        out[f"effectif_{int(y)}"] = tot[y].round().astype(int)
    out[f"ips_{a0}"] = ips[a0]; out[f"ips_{a1}"] = ips[a1]
    out["ips_urbain"] = mil.get("urbain"); out["ips_rural"] = mil.get("rural")
    out["ecart_urbain_moins_rural"] = out.ips_urbain - out.ips_rural
    out["effectif_dernier_sur_max"] = tot[a1] / tot.max(axis=1)
    out["eleves_perdus_depuis_max"] = (tot.max(axis=1) - tot[a1]).round().astype(int)
    g1, f1 = hp.garcons.unstack("annee_debut")[a1], hp.filles.unstack("annee_debut")[a1]
    out["filles_manquantes_parite"] = (g1 - f1).clip(lower=0).round().astype(int)
    pre = os.path.join(a.dossier04, f"{a.equipe}_04-analyse_D2_analyst_")
    out.round(4).reset_index().to_csv(pre + "regions17-indicateurs_v1.csv", sep=";", index=False, encoding="utf-8-sig")
    o = out.sort_values("effectif_dernier_sur_max")
    print(f"17 regions actuelles : {len(out)} regions, {len(p2r)} provinces agregees, total {a1} = {int(tot[a1].sum()):,} eleves")
    print("Acces (effectif / max) le plus bas : " + ", ".join(f"{x} {v:.0%}" for x, v in o.effectif_dernier_sur_max.head(4).items()))
    print("IPS le plus bas : " + ", ".join(f"{x} {v:.2f}" for x, v in out[f'ips_{a1}'].sort_values().head(4).items()))


if __name__ == "__main__":
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    main()
