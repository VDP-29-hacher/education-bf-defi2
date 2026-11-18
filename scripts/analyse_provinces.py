#!/usr/bin/env python3
"""ANALYSE PAR PROVINCE (Defi 2) - parite filles/garcons et ecart urbain/rural au niveau des 45 anciennes provinces.

Entree : la table propre produite par extraction_provinces.py (02_nettoyage, annuaire primaire) - donnees agregees et controlees.
Sorties (04_analyse) :
  <EQ>_04-analyse_D2_analyst_indicateurs-provinces_v1.csv            1 ligne par province (IPS 2015 et 2024, urbain, rural, ecart, redoublement)
  <EQ>_04-analyse_D2_analyst_ips-provinces-historique_v1.csv         IPS par province et par annee (effectifs, 10 annees)
  <EQ>_04-analyse_D2_analyst_ips-par-classe-et-milieu_v1.csv         national (somme des provinces) : classe x milieu/statut : IPS et redoublement
  <EQ>_04-analyse_D2_analyst_effectifs-provinces-historique_v1.csv   effectif total par province et par annee (acces)
  <EQ>_04-analyse_D2_analyst_ips-provinces-signalements_v1.csv       IPS non interpretables (effectif effondre) : laisses vides dans l'historique
Regles : IPS = filles / garcons ; taux de redoublement = redoublants / effectif de la meme sexe ; le tableau historique par classe n'est PAS utilise
(incoherent avec l'historique des effectifs : voir controles). Les lignes 'national' et 'region' de l'annuaire ne sont pas utilisees (somme des provinces).
Usage : analyse_provinces.py DOSSIER_02 DOSSIER_04 [--equipe Burkina_Novation] [--reference table.csv]
"""
import argparse, glob, os, sys
import pandas as pd

ORDRE = ["CP1", "CP2", "CE1", "CE2", "CM1", "CM2", "Total"]
SEUIL_EFFONDREMENT = 0.10   # sous 10 % de son effectif maximum, une province n'a plus assez d'eleves pour un IPS lisible


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dossier02"); ap.add_argument("dossier04")
    ap.add_argument("--equipe", default="Burkina_Novation")
    ap.add_argument("--reference", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "reference", "ancien_decoupage_13_a_valider.csv"))
    a = ap.parse_args()
    f = sorted(glob.glob(os.path.join(a.dossier02, "*_annuaire-primaire-*-provinces_v1.csv")))
    f = [x for x in f if "controles" not in os.path.basename(x)]
    if not f:
        sys.exit("Table des provinces introuvable : lancez d'abord l'etape 'provinces'.")
    df = pd.read_csv(f[-1], sep=";", encoding="utf-8-sig", keep_default_na=False, dtype=str)
    for c in ("effectif", "dont_redoublants", "annee_debut"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    ref = pd.read_csv(a.reference, sep=";", encoding="utf-8-sig", dtype=str).set_index("province")["ancienne_region"].to_dict()
    os.makedirs(a.dossier04, exist_ok=True)
    pre = os.path.join(a.dossier04, f"{a.equipe}_04-analyse_D2_analyst_")

    # ---- historique des effectifs par province (10 annees) ----
    h = df[(df.table == "effectifs_province") & (df.niveau_geo == "province") & df.sexe.isin(["garcons", "filles"])]
    hp = h.pivot_table(index=["province", "annee_debut"], columns="sexe", values="effectif", aggfunc="sum")
    hp["ips"] = hp.filles / hp.garcons
    hp["total"] = hp.filles + hp.garcons
    eff = hp.total.unstack("annee_debut")                                   # effectif total par province et par annee
    part_max = eff.div(eff.max(axis=1), axis=0)                             # effectif en part du maximum 2015-2024 de la province
    # IPS non interpretable : effectif effondre (< SEUIL_EFFONDREMENT du maximum de la province) -> IPS laisse vide et signale
    ips_brut = hp.ips.unstack("annee_debut")
    signal = (part_max < SEUIL_EFFONDREMENT) | (eff <= 0)
    sig_rows = []
    for p_, y_ in zip(*signal.values.nonzero(), strict=True):
        prov, an = signal.index[p_], signal.columns[y_]
        v = ips_brut.loc[prov, an]
        sig_rows.append({"province": prov, "ancienne_region": ref.get(prov, ""), "annee_debut": int(an),
                         "effectif_total": int(eff.loc[prov, an]) if eff.loc[prov, an] == eff.loc[prov, an] else None,
                         "effectif_max_periode": int(eff.loc[prov].max()), "part_du_max": round(float(part_max.loc[prov, an]), 4),
                         "ips_calcule": None if v != v or v in (float("inf"),) else round(float(v), 4),
                         "decision": f"IPS non interpretable (effectif < {SEUIL_EFFONDREMENT:.0%} du maximum de la province) : laisse vide dans l'historique"})
    pd.DataFrame(sig_rows, columns=["province", "ancienne_region", "annee_debut", "effectif_total", "effectif_max_periode", "part_du_max",
                                    "ips_calcule", "decision"]).to_csv(pre + "ips-provinces-signalements_v1.csv", sep=";", index=False, encoding="utf-8-sig")
    hist = ips_brut.mask(signal)
    hist.insert(0, "ancienne_region", [ref.get(p, "") for p in hist.index])
    hist.columns = [c if isinstance(c, str) else f"ips_{int(c)}" for c in hist.columns]
    hist.round(4).reset_index().to_csv(pre + "ips-provinces-historique_v1.csv", sep=";", index=False, encoding="utf-8-sig")
    eh = eff.copy()
    eh.columns = [f"effectif_{int(c)}" for c in eh.columns]
    eh.insert(0, "ancienne_region", [ref.get(p, "") for p in eh.index])
    eh.reset_index().to_csv(pre + "effectifs-provinces-historique_v1.csv", sep=";", index=False, encoding="utf-8-sig")
    ans = sorted(int(c.split("_")[1]) for c in hist.columns if c.startswith("ips_"))
    a0, a1 = ans[0], ans[-1]

    # ---- repartition 2024-2025 : par province, milieu et statut ----
    r = df[(df.table == "repartition_niveau_sexe") & (df.niveau_geo == "province") & df.sexe.isin(["garcons", "filles"])]
    def tab(cat, classe="Total"):
        x = r[(r.categorie == cat) & (r.classe == classe)]
        e = x.pivot_table(index="province", columns="sexe", values="effectif", aggfunc="sum")
        d = x.pivot_table(index="province", columns="sexe", values="dont_redoublants", aggfunc="sum")
        return e, d
    ens, red = tab("public_prive"); urb, _ = tab("urbain"); rur, _ = tab("rural")
    ind = pd.DataFrame(index=sorted(hist.index))
    ind["ancienne_region"] = [ref.get(p, "") for p in ind.index]
    ind[f"ips_{a0}"] = hist[f"ips_{a0}"]; ind[f"ips_{a1}"] = hist[f"ips_{a1}"]
    ind["variation"] = ind[f"ips_{a1}"] - ind[f"ips_{a0}"]
    ind["rang_du_plus_bas"] = ind[f"ips_{a1}"].rank(method="min")
    ind["effectif_total"] = ens.garcons + ens.filles
    ind["ips_ensemble"] = ens.filles / ens.garcons
    ind["ips_urbain"] = urb.filles / urb.garcons
    ind["ips_rural"] = rur.filles / rur.garcons
    ind["ecart_urbain_moins_rural"] = ind.ips_urbain - ind.ips_rural
    ind["part_effectifs_rural"] = (rur.garcons + rur.filles) / (ens.garcons + ens.filles)
    ind["taux_redoublement_filles"] = red.filles / ens.filles
    ind["taux_redoublement_garcons"] = red.garcons / ens.garcons
    ind["ecart_redoublement_filles_moins_garcons"] = ind.taux_redoublement_filles - ind.taux_redoublement_garcons
    # acces : effectif de la derniere annee rapporte au maximum de la periode (1 = jamais aussi haut ; 0,2 = 80 % des eleves perdus)
    ind["effectif_max_periode"] = eff.max(axis=1)
    ind["annee_effectif_max"] = eff.idxmax(axis=1).astype(int)
    ind["effectif_dernier_sur_max"] = eff[a1] / eff.max(axis=1)
    ind["nb_annees_ips_non_interpretable"] = signal.sum(axis=1)
    # traduire les indices en eleves (lecture directe pour un decideur)
    g1 = hp.garcons.unstack("annee_debut")[a1]; f1 = hp.filles.unstack("annee_debut")[a1]
    ind["eleves_perdus_depuis_max"] = (eff.max(axis=1) - eff[a1]).round().astype(int)
    ind["filles_manquantes_parite"] = (g1 - f1).clip(lower=0).round().astype(int)   # filles a inscrire en plus pour IPS = 1
    ind.index.name = "province"
    ind.round(4).reset_index().to_csv(pre + "indicateurs-provinces_v1.csv", sep=";", index=False, encoding="utf-8-sig")

    # ---- national (somme des provinces) : classe x milieu/statut ----
    lignes = []
    for cat in ("public_prive", "urbain", "rural", "public", "prive"):
        for cl in ORDRE:
            x = r[(r.categorie == cat) & (r.classe == cl)]
            g, fi = x[x.sexe == "garcons"], x[x.sexe == "filles"]
            eg, ef = g.effectif.sum(), fi.effectif.sum()
            rg, rf = g.dont_redoublants.sum(), fi.dont_redoublants.sum()
            lignes.append({"categorie": cat, "classe": cl, "garcons": eg, "filles": ef,
                           "ips": round(ef / eg, 4) if eg else None,
                           "redoublants_garcons": rg, "redoublants_filles": rf,
                           "taux_redoublement_garcons": round(rg / eg, 4) if eg else None,
                           "taux_redoublement_filles": round(rf / ef, 4) if ef else None})
    pd.DataFrame(lignes).to_csv(pre + "ips-par-classe-et-milieu_v1.csv", sep=";", index=False, encoding="utf-8-sig")

    # ---- console : compteurs et indicateurs agreges ----
    print(f"Provinces : {len(ind)} | annees d'historique : {a0}-{a1} | provinces sans ancienne region de reference : {sum(1 for v in ind.ancienne_region if not v)}")
    print(f"IPS provinces {a1} : min {ind[f'ips_{a1}'].min():.3f} ({ind[f'ips_{a1}'].idxmin()}), max {ind[f'ips_{a1}'].max():.3f} ({ind[f'ips_{a1}'].idxmax()})")
    print(f"Provinces sous 0,95 en {a1} : {(ind[f'ips_{a1}'] < 0.95).sum()} | sous 1,00 : {(ind[f'ips_{a1}'] < 1).sum()}")
    e = ind.ecart_urbain_moins_rural
    print(f"Ecart urbain - rural par province : mediane {e.median():.3f}, min {e.min():.3f}, max {e.max():.3f} | provinces ou l'IPS rural est plus bas que l'urbain : {(e > 0).sum()} / {e.notna().sum()}")
    pc = pd.DataFrame(lignes)
    for cat in ("urbain", "rural"):
        s = pc[(pc.categorie == cat)].set_index("classe").ips
        print(f"IPS national {cat} par classe : " + ", ".join(f"{k} {s[k]:.2f}" for k in ORDRE))
    t = pc[(pc.categorie == "public_prive") & (pc.classe == "Total")].iloc[0]
    print(f"Redoublement national : filles {t.taux_redoublement_filles:.3f}, garcons {t.taux_redoublement_garcons:.3f}")
    print(f"IPS non interpretables (effectif < {SEUIL_EFFONDREMENT:.0%} du max) : {len(sig_rows)} -> " + ", ".join(f"{r['province']} {r['annee_debut']}" for r in sig_rows))
    acc = ind.effectif_dernier_sur_max
    print(f"Acces {a1} : provinces sous 60 % de leur effectif maximum : {(acc < 0.6).sum()} ; plus basses : "
          + ", ".join(f"{p} {v:.0%}" for p, v in acc.sort_values().head(6).items()))
    print(f"Sorties : {pre}*")


if __name__ == "__main__":
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    main()
