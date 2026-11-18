#!/usr/bin/env python3
"""TAUX BRUT DE SCOLARISATION PAR PROVINCE (etape 4, role Analyst) a partir des projections INSD extraites par l'equipe.

Entrees (tables agregees) :
  02_nettoyage/*_population-insd-provinces_v1.csv        (extraction_population_insd.py, lance par l'equipe)
  02_nettoyage/*_annuaire-primaire-2024-2025-provinces_v1.csv  eleves par province et par sexe
  03_transformation/*_modele-commun-region-annee_v1.csv   population d'age primaire implicite par ancienne region (controle / estimation)
Methode :
  - si les projections donnent les 6-11 ans par province : TBS province = eleves / population 6-11 ans (methode "INSD 6-11 ans") ;
  - sinon (population totale seulement) : population 6-11 ans de la province = population totale de la province x part des 6-11 ans
    de sa region (population implicite DGESS / population INSD de la region) : methode "estimation par la part regionale", signalee ;
  - controle : la somme des provinces d'une region est comparee a la population implicite de la DGESS pour cette region.
Annee : l'annee scolaire AAAA-(AAAA+1) est rapprochee de la population de l'annee AAAA (option --decalage 1 pour AAAA+1).
Sortie : 04_analyse/<EQ>_04-analyse_D2_analyst_population-tbs-provinces_v1.csv (si la table INSD existe ; sinon message et fin normale)
Usage  : analyse_population_provinces.py DOSSIER_02 DOSSIER_03 DOSSIER_04 [--equipe Burkina_Novation] [--decalage 0]
"""
import argparse, glob, os, sys
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dossier02"); ap.add_argument("dossier03"); ap.add_argument("dossier04")
    ap.add_argument("--equipe", default="Burkina_Novation"); ap.add_argument("--decalage", type=int, default=0)
    a = ap.parse_args()
    fp = glob.glob(os.path.join(a.dossier02, "*_population-insd-provinces_v1.csv"))
    if not fp:
        print("Population INSD par province absente : lancer d'abord l'etape 'population_insd' (extraction_population_insd.py). Rien a faire.")
        return
    pop = pd.read_csv(fp[0], sep=";", encoding="utf-8-sig")
    if pop.empty:
        print("Population INSD par province vide : relancer l'etape 'population_insd' avec les bonnes pages. Rien a faire.")
        return
    fe = [x for x in glob.glob(os.path.join(a.dossier02, "*_annuaire-primaire-*-provinces_v1.csv")) if "controles" not in os.path.basename(x)]
    df = pd.read_csv(fe[0], sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    df["effectif"] = pd.to_numeric(df.effectif, errors="coerce"); df["annee_debut"] = pd.to_numeric(df.annee_debut, errors="coerce")
    h = df[(df.table == "effectifs_province") & (df.niveau_geo == "province") & df.sexe.isin(["garcons", "filles"])]
    an = int(h.annee_debut.max()); ap_ = an + a.decalage
    el = h[h.annee_debut == an].pivot_table(index="province", columns="sexe", values="effectif", aggfunc="sum")
    el["total"] = el.garcons + el.filles
    mc = pd.read_csv(glob.glob(os.path.join(a.dossier03, "*_modele-commun-region-annee_v1.csv"))[0], sep=";", encoding="utf-8-sig")
    mc = mc[mc.annee_debut == an].set_index("region")

    annees = sorted(pop.annee.unique())
    if ap_ not in annees:
        ap_ = min(annees, key=lambda y: abs(y - ap_))
    p = pop[pop.annee == ap_]
    # une seule ligne 6-11 par province, annee et sexe : celle retenue par l'extraction ("6-11 ans"), jamais aussi la ligne brute "6-11"
    six = p[p.groupe_age == "6-11 ans"] if (p.groupe_age == "6-11 ans").any() else p[p.groupe_age.str.replace(" ", "") == "6-11"]
    dbl = six.groupby(["province", "sexe"]).size().max() if len(six) else 0
    if dbl > 1:
        sys.exit(f"ERREUR : {dbl} lignes 6-11 ans pour une meme province, annee et sexe : extraction a verifier.")
    if "tableau" in six.columns and six.tableau.nunique() > 1:
        print(f"Plusieurs sous-tableaux INSD contiennent les 6-11 ans ({sorted(six.tableau.unique())}) : relancer l'extraction "
              "en choisissant le tableau d'ensemble (option -PopSous du pipeline). Rien n'est calcule pour ne pas additionner des tableaux differents.")
        sys.exit(2)
    methode = "INSD 6-11 ans" if len(six) else "estimation par la part regionale"
    if len(six) and "source_6_11" in six.columns and six.source_6_11.fillna("").str.startswith("interpolation").any():
        methode = "INSD, 6-11 ans interpoles depuis les groupes 5-9 et 10-14 ans"
    elif len(six) and "source_6_11" in six.columns and six.source_6_11.fillna("").str.startswith("groupe 6-11").all():
        methode = "INSD 6-11 ans (groupe publie)"
    base = six if len(six) else p[p.groupe_age == "ensemble"]
    tab = base.pivot_table(index=["province", "ancienne_region"], columns="sexe", values="population", aggfunc="sum").reset_index()
    if "total" not in tab.columns:
        tab["total"] = tab.get("garcons", 0) + tab.get("filles", 0)
    for s in ("garcons", "filles"):
        if s not in tab.columns:
            tab[s] = float("nan")
    if methode != "INSD 6-11 ans":           # population totale -> part regionale des 6-11 ans (population implicite DGESS)
        som = tab.groupby("ancienne_region")[["total", "garcons", "filles"]].transform("sum")
        for s, c in (("total", "population_primaire_total"), ("garcons", "population_primaire_garcons"), ("filles", "population_primaire_filles")):
            tab[s] = tab[s] / som[s] * tab.ancienne_region.map(mc[c])
    tab = tab.set_index("province")
    out = pd.DataFrame(index=tab.index)
    out["ancienne_region"] = tab.ancienne_region
    out["annee_scolaire"] = f"{an}-{an + 1}"; out["annee_population"] = ap_; out["methode"] = methode
    for s in ("total", "garcons", "filles"):
        out[f"population_6_11_{s}"] = tab[s].round()
        out[f"eleves_{s}"] = el[s].reindex(out.index)
        out[f"tbs_{s}"] = (out[f"eleves_{s}"] / out[f"population_6_11_{s}"] * 100).round(1)
    out["ips_tbs"] = (out.tbs_filles / out.tbs_garcons).round(3)
    out["eleves_en_plus_pour_tbs100"] = (out.population_6_11_total - out.eleves_total).clip(lower=0).round()
    reg = out.groupby("ancienne_region").population_6_11_total.sum()
    out["coherence_region"] = out.ancienne_region.map((reg / mc.population_primaire_total).round(3))
    pre = os.path.join(a.dossier04, f"{a.equipe}_04-analyse_D2_analyst_")
    out.reset_index().to_csv(pre + "population-tbs-provinces_v1.csv", sep=";", index=False, encoding="utf-8-sig")
    o = out.dropna(subset=["tbs_total"]).sort_values("tbs_total")
    print(f"TBS par province ({methode}, eleves {an}-{an + 1}, population {ap_}) : {len(o)} provinces sur {len(out)}")
    print(f"Coherence avec la population implicite DGESS par region : {out.coherence_region.min():.2f} a {out.coherence_region.max():.2f} (1 = identique)")
    print("TBS le plus bas : " + ", ".join(f"{i} {r.tbs_total:.0f} %" for i, r in o.head(5).iterrows()))
    print(f"Sortie : {pre}population-tbs-provinces_v1.csv")


if __name__ == "__main__":
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    main()
