#!/usr/bin/env python3
"""MODELE COMMUN (role Data Architect, Defi 2) : une table region x annee qui relie eleves, taux d'acces et population d'age scolaire.

Defi 2 : ou les ecarts d'acces a l'ecole sont-ils les plus grands (filles-garcons, ville-campagne) et evoluent-ils ?
Variables gardees (niveau region, 13 anciennes regions + national, 2015/16 a 2024/25), toutes par sexe :
  - eleves du primaire et du prescolaire ......................... parite-effectifs (etape 3)
  - taux bruts de scolarisation (TBS) ............................ parite-taux (etape 3)
  - population d'age scolaire = eleves / TBS ..................... "population implicite" : la DGESS calcule le TBS en divisant les
                                                                    eleves par la population de l'age (projections INSD) ; on retrouve
                                                                    donc exactement son denominateur, sans estimation de notre part
  - eleves a ajouter pour atteindre un TBS de 100 % ............. population - eleves (mesure de l'ecart d'acces en nombre d'enfants)
Les infrastructures et le personnel (ecoles, salles, enseignants) relevent du Defi 3 et ne sont pas repris ici.
Entrees : 03_transformation/*_parite-effectifs_v1.csv, *_parite-taux_v1.csv (tables agregees)
Sortie  : 03_transformation/<EQ>_03-transformation_D2_architect_modele-commun-region-annee_v1.csv
Usage   : modele_commun.py DOSSIER_02 DOSSIER_03 [--equipe Burkina_Novation]
"""
import argparse, glob, os, sys
import pandas as pd


def lire(d, cle, **kw):
    f = sorted(glob.glob(os.path.join(d, f"*_{cle}_v1.csv")))
    if not f:
        sys.exit(f"Introuvable : *_{cle}_v1.csv dans {d}")
    return pd.read_csv(f[0], sep=";", encoding="utf-8-sig", **kw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dossier02"); ap.add_argument("dossier03"); ap.add_argument("--equipe", default="Burkina_Novation")
    a = ap.parse_args()
    pe, pt = lire(a.dossier03, "parite-effectifs"), lire(a.dossier03, "parite-taux")
    zone = lambda r: "National" if r in ("total", "") else r
    cle = ["region", "annee_debut"]

    def eleves(feuille, bloc, pref):
        x = pe[(pe.feuille == feuille) & (pe.bloc == bloc) & pe.agregat.isin(["detail", "national"])]
        x = x[x.statut.fillna("").isin(["", "total"]) & x.milieu.fillna("").isin(["", "total"]) & x.niveau_scolaire.fillna("").isin(["", "total"])]
        x = x.assign(region=x.region.map(zone)).groupby(cle)[["garcons", "filles"]].sum()
        x[f"{pref}_total"] = x.garcons + x.filles
        return x.rename(columns={"garcons": f"{pref}_garcons", "filles": f"{pref}_filles"})

    def taux(niveau, pref):
        x = pt[(pt.indicateur == "tbs") & (pt.niveau_enseignement == niveau)].assign(region=lambda d: d.region.map(zone))
        return x.groupby(cle)[["tx_garcons", "tx_filles", "tx_total"]].first().rename(
            columns={"tx_garcons": f"{pref}_garcons", "tx_filles": f"{pref}_filles", "tx_total": f"{pref}_total"})

    m = pd.concat([eleves("Feuil1", 1, "eleves_primaire"), taux("primaire", "tbs_primaire"),
                   eleves("PRESCOLAIRE", 1, "eleves_prescolaire"), taux("prescolaire", "tbs_prescolaire")], axis=1)
    for niv in ("primaire", "prescolaire"):
        for s in ("garcons", "filles", "total"):
            m[f"population_{niv}_{s}"] = (m[f"eleves_{niv}_{s}"] / (m[f"tbs_{niv}_{s}"] / 100)).round()
        m[f"eleves_en_plus_pour_tbs100_{niv}"] = (m[f"population_{niv}_total"] - m[f"eleves_{niv}_total"]).clip(lower=0).round()
    m = m.reset_index()
    m.insert(2, "annee_scolaire", m.annee_debut.map(lambda y: f"{int(y)}-{int(y) + 1}"))
    sortie = os.path.join(a.dossier03, f"{a.equipe}_03-transformation_D2_architect_modele-commun-region-annee_v1.csv")
    m.to_csv(sortie, sep=";", index=False, encoding="utf-8-sig")
    # controle : la population implicite filles + garcons doit retrouver la population totale (meme denominateur DGESS)
    coh = ((m.population_primaire_garcons + m.population_primaire_filles) / m.population_primaire_total).dropna()
    n = m[(m.region == "National") & (m.annee_debut == m.annee_debut.max())].iloc[0]
    print(f"Modele commun : {len(m)} lignes ({m.region.nunique()} zones x {m.annee_debut.nunique()} annees), {m.shape[1]} colonnes")
    print(f"Controle population : (filles + garcons) / total entre {coh.min():.3f} et {coh.max():.3f}")
    print(f"National {int(n.annee_debut)} : {n.population_primaire_total:,.0f} enfants d'age du primaire, {n.eleves_primaire_total:,.0f} eleves, "
          f"{n.eleves_en_plus_pour_tbs100_primaire:,.0f} eleves en plus pour un TBS de 100 %")


if __name__ == "__main__":
    main()
