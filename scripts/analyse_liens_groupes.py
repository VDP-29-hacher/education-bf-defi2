#!/usr/bin/env python3
"""LIENS ET GROUPES (etape 4, Defi 2) : comment les ecarts d'acces se combinent, et quels profils de provinces en ressortent.

Le parcours du challenge demande, a l'etape 4, de "degager tendances, liens et groupes". Ici, uniquement avec les indicateurs du Defi 2,
au niveau des 45 anciennes provinces (primaire, derniere annee) :
  acces      : TBS calcule avec la population INSD 6-11 ans (si extraite), sinon effectif de la derniere annee / meilleur effectif
  parite     : IPS filles / garcons des effectifs ; IPS du TBS (si disponible)
  ville-campagne : ecart d'IPS urbain - rural ; part des eleves en milieu rural
  evolution  : variation de l'IPS depuis 2015/16 ; part du meilleur effectif (perte d'eleves)
LIENS  : correlation de rang de Spearman (robuste aux valeurs extremes), p-valeur, lecture en clair. Une correlation ne prouve pas une cause.
GROUPES: k-moyennes sur trois dimensions standardisees (acces, parite, ecart ville-campagne) ; k choisi entre 3 et 5 par le score de
         silhouette ; chaque groupe est nomme d'apres la moyenne de ses provinces.
Entrees : 04_analyse/*_indicateurs-provinces_v1.csv ; *_population-tbs-provinces_v1.csv (facultatif)
Sorties : 04_analyse/<EQ>_04-analyse_D2_analyst_liens-indicateurs_v1.csv ; <EQ>_04-analyse_D2_analyst_typologie-provinces_v1.csv
Usage   : analyse_liens_groupes.py DOSSIER_04 [--equipe Burkina_Novation]
"""
import argparse, glob, os, sys
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

LIB = {"acces": "accès (TBS)", "acces_effectifs": "effectifs / meilleur niveau", "ips": "IPS filles / garçons",
       "ips_tbs": "IPS du TBS", "ecart_ur": "écart d'IPS ville - campagne", "part_rurale": "part des élèves en milieu rural",
       "ips_rural": "IPS en milieu rural", "variation_ips": "variation de l'IPS depuis 2015/16"}
QUESTIONS = [  # (x, y, question posee)
    ("acces", "ips", "Les provinces où l'accès est faible ont-elles aussi moins de filles ?"),
    ("acces_effectifs", "ips", "Les provinces qui ont perdu des élèves ont-elles moins de filles ?"),
    ("acces", "ips_tbs", "L'accès faible va-t-il avec un accès plus faible pour les filles ?"),
    ("part_rurale", "ecart_ur", "Plus une province est rurale, plus l'écart ville-campagne est-il grand ?"),
    ("part_rurale", "ips", "Les provinces les plus rurales ont-elles moins de filles ?"),
    ("acces", "ecart_ur", "L'écart ville-campagne est-il plus grand là où l'accès est faible ?"),
    ("acces_effectifs", "variation_ips", "La parité a-t-elle moins progressé là où les élèves ont disparu ?"),
]


def force(r):
    a = abs(r)
    return "très faible" if a < 0.2 else "faible" if a < 0.4 else "modéré" if a < 0.6 else "fort"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dossier04"); ap.add_argument("--equipe", default="Burkina_Novation")
    a = ap.parse_args()
    lire = lambda cle: (pd.read_csv(f[0], sep=";", encoding="utf-8-sig") if (f := sorted(glob.glob(os.path.join(a.dossier04, f"*_{cle}_v1.csv")))) else None)
    ind = lire("indicateurs-provinces")
    if ind is None:
        sys.exit("indicateurs-provinces introuvable : lancer d'abord analyse_provinces.py")
    pk = [c for c in ind.columns if c.startswith("ips_20")][-1]
    d = pd.DataFrame({"province": ind.province, "ancienne_region": ind.ancienne_region, "ips": ind[pk], "ips_rural": ind.ips_rural,
                      "ecart_ur": ind.ecart_urbain_moins_rural, "part_rurale": ind.part_effectifs_rural,
                      "acces_effectifs": ind.effectif_dernier_sur_max, "variation_ips": ind.variation}).set_index("province")
    pt = lire("population-tbs-provinces")
    source_acces = "effectifs / meilleur niveau (population par province absente)"
    if pt is not None and pt.tbs_total.notna().sum() >= 40:
        pt = pt.set_index("province")
        d["acces"] = pt.tbs_total.reindex(d.index); d["ips_tbs"] = pt.ips_tbs.reindex(d.index)
        source_acces = "TBS du primaire avec la population INSD 6-11 ans"
    else:
        d["acces"] = d.acces_effectifs * 100; d["ips_tbs"] = np.nan

    # ---------------- liens ----------------
    liens = []
    for x, y, q in QUESTIONS:
        s = d[[x, y]].dropna()
        if len(s) < 10 or (x == "acces" and y == "ips_tbs" and d.ips_tbs.isna().all()):
            continue
        r, p = spearmanr(s[x], s[y])
        sens = "positif" if r > 0 else "négatif"
        lec = (f"lien {sens} {force(r)} (rho = {r:.2f}), " + ("significatif" if p < 0.05 else "non significatif") + f" (p = {p:.3f})")
        liens.append({"question": q, "variable_x": LIB[x], "variable_y": LIB[y], "n_provinces": len(s), "rho_spearman": round(r, 3),
                      "p_valeur": round(p, 4), "significatif_5pc": p < 0.05, "lecture": lec})
    L = pd.DataFrame(liens)

    # ---------------- groupes ----------------
    X = d[["acces", "ips", "ecart_ur"]].dropna()
    Z = (X - X.mean()) / X.std(ddof=0)
    meilleurs = []
    for k in (3, 4, 5):
        km = KMeans(n_clusters=k, n_init=50, random_state=0).fit(Z)
        meilleurs.append((silhouette_score(Z, km.labels_), k, km))
    sil, k, km = max(meilleurs, key=lambda t: t[0])
    X = X.assign(groupe=km.labels_)
    moy = X.groupby("groupe").mean()
    seuil_acces = 50 if "TBS" in source_acces else 50   # TBS en % ou effectifs en % du meilleur niveau

    def nom(g):
        c = moy.loc[g]
        acc = "accès très faible" if c.acces < seuil_acces else "accès moyen" if c.acces < 85 else "accès élevé"
        par = "peu de filles" if c.ips < 0.93 else "parité presque atteinte" if c.ips < 0.98 else "parité atteinte"
        ur = ", fort écart ville-campagne" if c.ecart_ur > 0.06 else ""
        return f"{acc[0].upper() + acc[1:]}, {par}{ur}"

    noms = {g: nom(g) for g in moy.index}
    vus = {}
    for g in sorted(noms, key=lambda g: moy.loc[g, "acces"]):         # noms uniques ; ordre : du plus faible acces au plus eleve
        n_ = noms[g]; vus[n_] = vus.get(n_, 0) + 1
        if vus[n_] > 1:
            noms[g] = f"{n_} ({vus[n_]})"
    ordre = {g: i + 1 for i, g in enumerate(sorted(noms, key=lambda g: moy.loc[g, "acces"]))}
    T = X.join(d[["ancienne_region", "part_rurale", "acces_effectifs", "variation_ips"]])
    T["groupe"] = T.groupe.map(ordre); T["profil"] = X.groupe.map(noms)
    T = T.reset_index().sort_values(["groupe", "acces"])
    T = T[["province", "ancienne_region", "groupe", "profil", "acces", "ips", "ecart_ur", "part_rurale", "acces_effectifs", "variation_ips"]]
    T.columns = ["province", "ancienne_region", "groupe", "profil", "acces", "ips", "ecart_urbain_moins_rural", "part_effectifs_rural",
                 "effectif_dernier_sur_max", "variation_ips"]
    pre = os.path.join(a.dossier04, f"{a.equipe}_04-analyse_D2_analyst_")
    L.to_csv(pre + "liens-indicateurs_v1.csv", sep=";", index=False, encoding="utf-8-sig")
    T.round(4).assign(mesure_acces=source_acces, k_retenu=k, silhouette=round(sil, 3)).to_csv(pre + "typologie-provinces_v1.csv", sep=";", index=False, encoding="utf-8-sig")
    print(f"Liens : {len(L)} questions testees, {int(L.significatif_5pc.sum())} liens significatifs (p < 0,05)")
    for r in L.itertuples():
        print(f"  - {r.question} -> {r.lecture}")
    print(f"Groupes : k = {k} (silhouette {sil:.2f}) sur {len(T)} provinces ; acces mesure par : {source_acces}")
    for g, s in T.groupby("groupe"):
        print(f"  {g}. {s.profil.iloc[0]} : {len(s)} provinces ({', '.join(s.province.head(6))}{'...' if len(s) > 6 else ''})")


if __name__ == "__main__":
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    main()
