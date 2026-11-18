#!/usr/bin/env python3
"""ANALYSE DE L'ACCES (Defi 2) - taux d'acces par region et provinces prioritaires, puis LISEZ-MOI de l'etape 4.

Entrees (tables agregees uniquement) :
  03_transformation/*_parite-taux_v1.csv            taux publies par la DGESS (TBS, TBA, TAP, par sexe et par region)
  04_analyse/*_indicateurs-cles_v1.csv              IPS par region (analyse_template.py)
  04_analyse/*_ecart-urbain-rural_v1.csv            IPS urbain / rural national (analyse_template.py)
  04_analyse/*_indicateurs-provinces_v1.csv         IPS et acces par province (analyse_provinces.py)
Sorties (04_analyse) :
  <EQ>_04-analyse_D2_analyst_acces-regions_v1.csv          taux filles / garcons / ensemble, IPS du taux, ecart en points
  <EQ>_04-analyse_D2_analyst_provinces-prioritaires_v1.csv regle de ciblage transparente (parite x acces)
  <EQ>_04-analyse_D2_analyst_lisez-moi_v1.txt              LISEZ-MOI de l'etape 4 (remplace celui d'analyse_template.py)
Regle de priorite : critere parite = IPS de la derniere annee < SEUIL_IPS ; critere acces = effectif de la derniere annee
< SEUIL_ACCES de l'effectif maximum de la periode. Priorite 1 = les deux ; priorite 2 = un seul.
Usage : analyse_acces.py DOSSIER_03 DOSSIER_04 [--equipe Burkina_Novation]
"""
import argparse, glob, os, sys
import pandas as pd

SEUIL_IPS, SEUIL_ACCES = 0.95, 0.60
INDICATEURS = [("tbs", "primaire", "TBS primaire"), ("tba", "primaire", "TBA primaire (entree au CP1)"),
               ("tap", "primaire", "TAP (achevement du primaire)"), ("tbs", "prescolaire", "TBS prescolaire")]


def lire(d, cle):
    f = sorted(glob.glob(os.path.join(d, f"*_{cle}_v1.csv")))
    if not f:
        sys.exit(f"Introuvable : *_{cle}_v1.csv dans {d}")
    return pd.read_csv(f[0], sep=";", encoding="utf-8-sig", keep_default_na=False, dtype=str)


def num(df, cols):
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dossier03"); ap.add_argument("dossier04"); ap.add_argument("--equipe", default="Burkina_Novation")
    a = ap.parse_args()
    pre = os.path.join(a.dossier04, f"{a.equipe}_04-analyse_D2_analyst_")
    ya = lambda y: f"{y}/{str(int(y) + 1)[2:]}"

    # ---------- 1. taux d'acces par region ----------
    t = num(lire(a.dossier03, "parite-taux"), ["tx_garcons", "tx_filles", "tx_total", "annee_debut"])
    t = t[t.agregat.isin(["detail", "national", "sous_total"]) | (t.region == "total")]
    lignes = []
    for ind, niv, lib in INDICATEURS:
        x = t[(t.indicateur == ind) & (t.niveau_enseignement == niv)]
        for _, r in x.iterrows():
            lignes.append({"indicateur": f"{ind}_{niv}", "libelle": lib,
                           "region": "National" if r.region == "total" else r.region, "annee_debut": int(r.annee_debut),
                           "taux_garcons": round(r.tx_garcons, 1), "taux_filles": round(r.tx_filles, 1), "taux_ensemble": round(r.tx_total, 1),
                           "ips_taux": round(r.tx_filles / r.tx_garcons, 3) if r.tx_garcons else None,
                           "ecart_filles_moins_garcons_points": round(r.tx_filles - r.tx_garcons, 1)})
    acc = pd.DataFrame(lignes).drop_duplicates(["indicateur", "region", "annee_debut"]).sort_values(["indicateur", "region", "annee_debut"])
    acc.to_csv(pre + "acces-regions_v1.csv", sep=";", index=False, encoding="utf-8-sig")
    a1 = int(acc.annee_debut.max()); a0 = int(acc.annee_debut.min())
    tbs = acc[(acc.indicateur == "tbs_primaire")]
    tbs1 = tbs[(tbs.annee_debut == a1) & (tbs.region != "National")].sort_values("taux_ensemble")
    tbs_nat = tbs[(tbs.region == "National")].set_index("annee_debut")

    # ---------- 2. provinces prioritaires ----------
    p = lire(a.dossier04, "indicateurs-provinces")
    pk = [c for c in p.columns if c.startswith("ips_20")]
    pk0, pk1 = pk[0], pk[-1]
    p = num(p, [pk0, pk1, "ips_urbain", "ips_rural", "ecart_urbain_moins_rural", "effectif_dernier_sur_max", "effectif_max_periode",
                "annee_effectif_max"])
    p["critere_parite"] = p[pk1] < SEUIL_IPS
    p["critere_acces"] = p.effectif_dernier_sur_max < SEUIL_ACCES
    p["priorite"] = (p.critere_parite & p.critere_acces).map({True: 1, False: None})
    p.loc[p.priorite.isna() & (p.critere_parite | p.critere_acces), "priorite"] = 2
    pr = p[p.priorite.notna()].copy()
    pr["motif"] = pr.apply(lambda r: " ; ".join(m for m, ok in (
        (f"IPS {r[pk1]:.3f} < {SEUIL_IPS}", r.critere_parite),
        (f"effectifs a {r.effectif_dernier_sur_max:.0%} du maximum ({int(r.annee_effectif_max)})", r.critere_acces)) if ok), axis=1)
    pr = pr.sort_values(["priorite", pk1])[["priorite", "province", "ancienne_region", pk1, "ips_urbain", "ips_rural", "ecart_urbain_moins_rural",
                                            "effectif_dernier_sur_max", "motif"]]
    pr["priorite"] = pr.priorite.astype(int)
    pr.round(3).to_csv(pre + "provinces-prioritaires_v1.csv", sep=";", index=False, encoding="utf-8-sig")
    p1, p2 = pr[pr.priorite == 1], pr[pr.priorite == 2]

    # ---------- 3. LISEZ-MOI de l'etape 4 (tous les chiffres sont calcules) ----------
    ind = num(lire(a.dossier04, "indicateurs-cles"), [])
    for c in ind.columns:
        if c.startswith(("ips_", "variation")):
            ind[c] = pd.to_numeric(ind[c], errors="coerce")
    mil = num(lire(a.dossier04, "ecart-urbain-rural"), ["rural", "urbain", "ecart_urbain_moins_rural"])
    c0 = [c for c in ind.columns if c.startswith("ips_primaire_")]
    k0, k1 = c0[0], c0[-1]
    nat = ind[ind.niveau_geographique == "national"].iloc[0]
    reg = ind[ind.niveau_geographique != "national"].sort_values(k1)
    sig = lire(a.dossier04, "ips-provinces-signalements")
    e0, e1 = mil.ecart_urbain_moins_rural.iloc[0], mil.ecart_urbain_moins_rural.iloc[-1]
    lo, hi = tbs1.iloc[0], tbs1.iloc[-1]
    msg = [
        f"ACCES - Le taux brut de scolarisation (TBS) du primaire va de {lo.taux_ensemble:.0f} % ({lo.region}) a {hi.taux_ensemble:.0f} % ({hi.region}) en {ya(a1)} "
        f"(national {tbs_nat.loc[a1, 'taux_ensemble']:.0f} %, contre {tbs_nat.loc[a0, 'taux_ensemble']:.0f} % en {ya(a0)}). L'ecart entre regions est bien plus grand que l'ecart filles-garcons.",
        f"ACCES - Par province, {int(p.critere_acces.sum())} provinces sur {len(p)} ont en {ya(pk1[-4:])} moins de {SEUIL_ACCES:.0%} de leur effectif maximum de la periode ; "
        "les plus touchees : " + ", ".join(f"{r.province} ({r.effectif_dernier_sur_max:.0%})" for _, r in p.sort_values("effectif_dernier_sur_max").head(5).iterrows()) + ".",
        f"PARITE - Au niveau national, l'IPS du primaire est passe de {nat[k0]:.2f} ({ya(k0[-4:])}) a {nat[k1]:.2f} ({ya(k1[-4:])}) ; "
        f"a l'entree au CP1 il est de {nat[f'ips_cp1_nouveaux_inscrits_{k1[-4:]}']:.2f}.",
        f"PARITE - Regions les plus basses : {reg.iloc[0].region} ({reg.iloc[0][k1]:.2f}), {reg.iloc[1].region} ({reg.iloc[1][k1]:.2f}) ; "
        f"provinces les plus basses : " + ", ".join(f"{r.province} ({r[pk1]:.2f})" for _, r in p.sort_values(pk1).head(3).iterrows()) + ".",
        f"URBAIN-RURAL - L'ecart d'IPS entre urbain et rural (primaire) est passe de {e0:.3f} a {e1:.3f} point ; il est positif dans "
        f"{int((p.ecart_urbain_moins_rural > 0).sum())} provinces sur {len(p)}.",
        f"CIBLAGE - {len(p1)} provinces en priorite 1 (parite ET acces) : {', '.join(p1.province)} ; {len(p2)} en priorite 2.",
    ]
    texte = f"""ETAPE 4 - ANALYSE (Defi 2 : disparites d'acces a l'education, parite filles-garcons, ecart urbain-rural) - equipe {a.equipe}

Entrees : tables agregees des etapes 2 et 3 uniquement. Aucun chiffre saisi a la main : tout est calcule par les scripts.
Scripts : analyse_template.py (regions, figures) ; analyse_provinces.py (45 provinces) ; analyse_regions17.py (17 regions actuelles) ; analyse_acces.py (acces, priorites) ;
prevision_provinces.py (role scientist, voir son propre zip) ; dashboard_template.py (tableau de bord interactif).

FICHIERS
- indicateurs-cles.csv : IPS par ancienne region (primaire 2015 et derniere annee, prescolaire, CP1), rang.
- ecart-urbain-rural.csv : IPS urbain et rural du primaire par annee (national).
- acces-regions.csv : TBS, TBA, TAP du primaire et TBS du prescolaire par region, sexe et annee ; IPS du taux ; ecart en points.
- indicateurs-provinces.csv : par province, IPS (debut, fin, urbain, rural), redoublement, effectif de la derniere annee en part du maximum.
- ips-provinces-historique.csv : IPS par province et par annee (les IPS non interpretables sont laisses vides).
- effectifs-provinces-historique.csv : effectif total par province et par annee.
- ips-provinces-signalements.csv : les {len(sig)} IPS laisses vides et pourquoi (effectif tombe sous 10 % du maximum de la province).
- ips-par-classe-et-milieu.csv : IPS et redoublement par classe, urbain / rural / public / prive (national).
- liens-indicateurs.csv : liens entre les ecarts du Defi 2 (correlation de Spearman, p-valeur, lecture en clair).
- typologie-provinces.csv : profils de provinces (k-moyennes sur acces, parite, ecart ville-campagne) et profil de chaque province.
- population-tbs-provinces.csv : TBS par province et par sexe avec la population INSD 6-11 ans (si extraite).
- regions17-indicateurs.csv : 17 regions actuelles (agregation exacte des 45 provinces) : effectifs, IPS, urbain/rural, eleves perdus, filles manquantes.
- indicateurs-provinces.csv contient aussi eleves_perdus_depuis_max et filles_manquantes_parite (indices traduits en eleves).
- provinces-prioritaires.csv : regle de ciblage (IPS < {SEUIL_IPS} ; effectifs < {SEUIL_ACCES:.0%} du maximum) et motif.
- tableau-de-bord.zip : tableau de bord HTML interactif autonome + figures PNG de secours.

MESSAGES CLES
""" + "\n".join(f"- {m}" for m in msg) + """

LIMITES
- Donnees regionales par ANCIENNE region (13) : la correspondance avec les 17 regions actuelles est documentee a l'etape 3.
- TBS / TBA / TAP sont publies par la DGESS (denominateur : population scolarisable) ; ils peuvent depasser 100 % (eleves hors age).
- Effectifs par province : la chute des effectifs signale une perte d'acces (fermetures d'ecoles probables), sans en prouver la cause.
- Un IPS calcule sur tres peu d'eleves n'est pas lisible : il est laisse vide et liste dans les signalements.
- Annees recentes possiblement provisoires ; primaire 2017/18 : total national non retrouve dans les annuaires (point ouvert).
"""
    with open(pre + "lisez-moi_v1.txt", "w", encoding="utf-8") as fh:
        fh.write(texte)
    print(f"Acces : {len(acc)} lignes ({acc.indicateur.nunique()} indicateurs, {acc.region.nunique()} zones, {a0}-{a1})")
    for m in msg:
        print(" -", m)


if __name__ == "__main__":
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    main()
