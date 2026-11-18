#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TRANSFORMATION - Etape 3 (depot 03_transformation) - Defi 2 (parite filles-garcons, ecart urbain-rural).

"Creer des variables (taux, ratios), appliquer des regles de calcul pour adapter les donnees a l'analyse" (PDF).
Entree : la table longue de 02_nettoyage (EQ_02-nettoyage_D2_engineer_tableaux-long_v1.csv).
La console n'affiche que des COMPTEURS ; les resultats sont dans les fichiers.

Sorties (dans DOSSIER_03) :
  EQ_03-transformation_D2_engineer_parite-effectifs_v1.csv      IPS et part de filles calcules sur les EFFECTIFS
  EQ_03-transformation_D2_engineer_parite-taux_v1.csv           IPS recalcule a partir des TAUX (TBA, TBS, achevement...)
                                                                 + IPS publie par la DGESS + ecart
  EQ_03-transformation_D2_engineer_controle-ips_v1.csv          IPS recalcule different de l'IPS publie (controle croise)
  EQ_03-transformation_D2_engineer_ecarts-par-dimension_v1.csv  ecarts par milieu / statut / region par rapport au national
  EQ_03-transformation_D2_engineer_classement-regions_v1.csv    rang des regions par annee (1 = parite la plus defavorable aux filles)
  EQ_03-transformation_D2_engineer_tendances_v1.csv             evolution de l'IPS sur la periode (variation, pente)
  EQ_03-transformation_D2_engineer_dictionnaire-variables_v1.csv  description de chaque colonne de chaque table
  EQ_03-transformation_D2_engineer_journal-transformation_v1.csv  ce qui a ete calcule, nombres de lignes
  LISEZ-MOI.txt

Definitions : IPS = filles / garcons (indice de parite). Parite si 0,97 <= IPS <= 1,03 (convention UNESCO, a ajuster).
Part de filles = filles / (garcons + filles).

Usage :
  python transformation_template.py TABLEAUX_LONG.csv DOSSIER_03 --equipe Burkina_Novation
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------------------------------
# A ADAPTER SI BESOIN
# --------------------------------------------------------------------------------------------------
PARITE_BASSE, PARITE_HAUTE = 0.97, 1.03      # bornes de la parite (IPS)
TOLERANCE_IPS = 0.02                          # ecart tolere IPS recalcule / IPS publie (arrondis des taux)
CLES = ["feuille", "bloc", "bloc_titre", "niveau_enseignement", "region", "statut", "milieu", "niveau_scolaire", "autre",
        "annee_scolaire", "annee_debut", "agregat"]
journal: list = []


def norm(s) -> str:
    s = re.sub(r"[’‘ʼ'`´]", " ", str(s))
    t = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", t)).strip()


def cle_indicateur(titre: str) -> str:
    n = norm(titre)
    for cle, rx in (("tba", r"\btba\b"), ("tbs", r"\btbs\b"), ("tap", r"\btap\b|achevement"), ("reussite", r"reussite"),
                    ("nouveaux_inscrits", r"nouveaux inscrits"), ("effectifs", r"effectif")):
        if re.search(rx, n):
            return cle
    return "autre"


def statut_parite(ips) -> str:
    if pd.isna(ips):
        return ""
    if ips < PARITE_BASSE:
        return "defavorable aux filles"
    if ips > PARITE_HAUTE:
        return "defavorable aux garcons"
    return "parite"


def dimension(r) -> str:
    for d in ("milieu", "statut", "region"):
        if r[d] not in ("", "total"):
            return d
    return "national"


def categorie(r) -> str:
    d = r["dimension"]
    return r[d] if d != "national" else "national"


def pivoter(df: pd.DataFrame, sexes) -> pd.DataFrame:
    p = df[df.sexe.isin(sexes)].pivot_table(index=CLES, columns="sexe", values="valeur", aggfunc="first").reset_index()
    p.columns.name = None
    return p


def log(table, lignes, detail=""):
    journal.append({"table": table, "lignes": lignes, "detail": detail})


# --------------------------------------------------------------------------------------------------
DICTIONNAIRE = [
    # (table, colonne, description)
    ("commun", "feuille", "feuille Excel d'origine du tableau"),
    ("commun", "bloc", "numero du tableau dans la feuille (Tableau N empiles)"),
    ("commun", "bloc_titre", "titre du tableau (120 caracteres max)"),
    ("commun", "niveau_enseignement", "prescolaire ou primaire (source : titre, sinon feuille ; TAP, CP1 et CEP relevent du primaire par definition)"),
    ("commun", "region", "region DGESS (13 anciennes regions), orthographe harmonisee ; 'total' = ligne de total"),
    ("commun", "statut", "public / prive / communautaire ; 'total' = tous statuts ; vide = non applicable au tableau"),
    ("commun", "milieu", "urbain / rural / indetermine ; 'total' = tous milieux ; vide = non applicable"),
    ("commun", "niveau_scolaire", "classe ou section (CP1..., Grande section...) ; 'total' = tous niveaux ; vide = non applicable"),
    ("commun", "annee_scolaire", "annee scolaire AAAA-AAAA (l'annee scolaire n'est pas l'annee civile)"),
    ("commun", "annee_debut", "annee civile de debut de l'annee scolaire (entier)"),
    ("commun", "agregat", "detail = ligne elementaire ; sous_total = total partiel ; national = total general"),
    ("parite-effectifs", "garcons", "effectif de garcons"),
    ("parite-effectifs", "filles", "effectif de filles"),
    ("parite-effectifs", "total", "effectif total publie"),
    ("parite-effectifs", "total_calcule", "garcons + filles"),
    ("parite-effectifs", "ips", "indice de parite filles/garcons = filles / garcons (>1 : plus de filles)"),
    ("parite-effectifs", "part_filles", "filles / (garcons + filles)"),
    ("parite-effectifs", "statut_parite", "defavorable aux filles (IPS<0,97) / parite / defavorable aux garcons (IPS>1,03)"),
    ("parite-taux", "tx_garcons", "taux publie pour les garcons (TBA, TBS, achevement... : voir indicateur)"),
    ("parite-taux", "tx_filles", "taux publie pour les filles"),
    ("parite-taux", "tx_total", "taux publie, ensemble"),
    ("parite-taux", "indicateur", "tba / tbs / tap (achevement) / reussite / autre"),
    ("parite-taux", "ips_recalcule", "tx_filles / tx_garcons"),
    ("parite-taux", "ips_publie", "IPS publie par la DGESS pour le meme indicateur, la meme region et la meme annee"),
    ("parite-taux", "ecart_ips", "ips_recalcule - ips_publie"),
    ("parite-taux", "controle_ips", "ok / ecart (|ecart| > tolerance) / sans_ips_publie"),
    ("ecarts-par-dimension", "dimension", "milieu / statut / region / national : dimension qui varie dans le tableau"),
    ("ecarts-par-dimension", "categorie", "valeur de la dimension (urbain, rural, public, prive, nom de region...)"),
    ("ecarts-par-dimension", "ips_national", "IPS de la ligne nationale du meme tableau et de la meme annee"),
    ("ecarts-par-dimension", "ecart_vs_national", "ips - ips_national (negatif : plus defavorable aux filles que le national)"),
    ("classement-regions", "rang", "1 = region ou la parite est la plus defavorable aux filles (IPS le plus bas) cette annee-la"),
    ("classement-regions", "ecart_vs_national", "ips de la region - ips national"),
    ("tendances", "ips_debut", "IPS de la premiere annee disponible"),
    ("tendances", "ips_fin", "IPS de la derniere annee disponible"),
    ("tendances", "variation", "ips_fin - ips_debut (positif : la parite s'ameliore pour les filles)"),
    ("tendances", "pente_par_an", "pente de la droite des moindres carres de l'IPS sur l'annee"),
    ("tendances", "n_annees", "nombre d'annees avec un IPS calculable"),
]


def main(argv=None) -> int:
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Transformation etape 3 - Defi 2 (aucune valeur n'est affichee a l'ecran)")
    ap.add_argument("entree", help="table longue de 02_nettoyage (tableaux-long CSV)")
    ap.add_argument("sortie", help="dossier 03_transformation")
    ap.add_argument("--equipe", required=True)
    ap.add_argument("--defi", default="D2")
    ap.add_argument("--role", default="engineer")
    a = ap.parse_args(argv)
    entree, sortie = Path(a.entree), Path(a.sortie)
    if not entree.is_file():
        print("ERREUR : fichier d'entree introuvable")
        return 1
    sortie.mkdir(parents=True, exist_ok=True)
    pre = f"{a.equipe}_03-transformation_{a.defi}_{a.role}"
    ecrire = lambda df, nom: df.to_csv(sortie / f"{pre}_{nom}_v1.csv", sep=";", index=False, encoding="utf-8-sig")

    df = pd.read_csv(entree, sep=";", encoding="utf-8-sig", keep_default_na=False, dtype=str)
    for col in ("region", "statut", "milieu", "niveau_scolaire", "autre", "sexe", "agregat", "niveau_enseignement"):
        if col not in df:
            df[col] = df["region_brute"] if col == "region" and "region_brute" in df else ""
    df["valeur"] = pd.to_numeric(df["valeur"].str.replace(",", "."), errors="coerce")
    df["annee_debut"] = pd.to_numeric(df["annee_debut"], errors="coerce")
    df["bloc"] = df["bloc"].astype(str)
    print(f"{len(df)} lignes lues ; tableaux : {df.groupby(['feuille', 'bloc']).ngroups}")

    # ---------------- A. parite sur les effectifs ------------------------------------------------------
    eff = df[df.type_valeur == "effectif"]
    p = pivoter(eff, ["garcons", "filles", "total"])
    for c in ("garcons", "filles", "total"):
        if c not in p:
            p[c] = np.nan
    p["total_calcule"] = p.garcons + p.filles
    p["ips"] = (p.filles / p.garcons).where(p.garcons > 0).round(4)
    p["part_filles"] = (p.filles / p.total_calcule).where(p.total_calcule > 0).round(4)
    p["statut_parite"] = p.ips.map(statut_parite)
    p["indicateur"] = p.bloc_titre.map(cle_indicateur)
    p["dimension"] = p.apply(dimension, axis=1)
    p["categorie"] = p.apply(categorie, axis=1)
    p = p.sort_values(["feuille", "bloc", "annee_debut", "region", "statut", "milieu", "niveau_scolaire"])
    cols_a = CLES + ["indicateur", "dimension", "categorie", "garcons", "filles", "total", "total_calcule", "ips",
                     "part_filles", "statut_parite"]
    ecrire(p[cols_a], "parite-effectifs")
    log("parite-effectifs", len(p), f"{int(p.ips.notna().sum())} IPS calculables sur {len(p)} lignes")
    print(f"parite-effectifs : {len(p)} lignes, IPS calculables {int(p.ips.notna().sum())}")

    # ---------------- B. IPS recalcule a partir des taux, compare a l'IPS publie -----------------------------
    tx = pivoter(df[df.type_valeur == "taux"], ["garcons", "filles", "total"]).rename(
        columns={"garcons": "tx_garcons", "filles": "tx_filles", "total": "tx_total"})
    for c in ("tx_garcons", "tx_filles", "tx_total"):
        if c not in tx:
            tx[c] = np.nan
    tx["indicateur"] = tx.bloc_titre.map(cle_indicateur)
    tx["ips_recalcule"] = (tx.tx_filles / tx.tx_garcons).where(tx.tx_garcons > 0).round(4)
    pub = df[df.type_valeur == "indice_parite"].copy()
    pub["indicateur"] = pub.bloc_titre.map(cle_indicateur)
    pub = pub.groupby(["niveau_enseignement", "indicateur", "region", "annee_debut"], as_index=False)["valeur"].first().rename(
        columns={"valeur": "ips_publie"})
    tx = tx.merge(pub, on=["niveau_enseignement", "indicateur", "region", "annee_debut"], how="left")
    tx["ecart_ips"] = (tx.ips_recalcule - tx.ips_publie).round(4)
    tx["controle_ips"] = np.where(tx.ips_publie.isna(), "sans_ips_publie",
                                  np.where(tx.ecart_ips.abs() > TOLERANCE_IPS, "ecart", "ok"))
    tx["statut_parite"] = tx.ips_recalcule.map(statut_parite)
    tx = tx.sort_values(["feuille", "bloc", "annee_debut", "region"])
    cols_b = CLES + ["indicateur", "tx_garcons", "tx_filles", "tx_total", "ips_recalcule", "ips_publie", "ecart_ips",
                     "controle_ips", "statut_parite"]
    ecrire(tx[cols_b], "parite-taux")
    ecart = tx[tx.controle_ips == "ecart"]
    ecrire(ecart[cols_b], "controle-ips")
    n_ok, n_ec, n_sans = (int((tx.controle_ips == k).sum()) for k in ("ok", "ecart", "sans_ips_publie"))
    log("parite-taux", len(tx), f"controle IPS : ok={n_ok} ecart={n_ec} sans_ips_publie={n_sans}")
    print(f"parite-taux : {len(tx)} lignes ; controle IPS recalcule/publie : ok={n_ok} ecart={n_ec} sans_ips_publie={n_sans}")

    # ---------------- C. ecarts par dimension (par rapport au national du meme tableau) ---------------------
    nat = p[(p.agregat == "national") & (p.niveau_scolaire.isin(["", "total"]))][
        ["feuille", "bloc", "annee_scolaire", "ips"]].rename(columns={"ips": "ips_national"}).drop_duplicates(
        ["feuille", "bloc", "annee_scolaire"])
    ec = p[(p.dimension != "national")].merge(nat, on=["feuille", "bloc", "annee_scolaire"], how="left")
    ec["ecart_vs_national"] = (ec.ips - ec.ips_national).round(4)
    cols_c = ["feuille", "bloc", "bloc_titre", "niveau_enseignement", "indicateur", "dimension", "categorie", "niveau_scolaire",
              "agregat", "annee_scolaire", "annee_debut", "garcons", "filles", "ips", "part_filles", "statut_parite",
              "ips_national", "ecart_vs_national"]
    ecrire(ec[cols_c], "ecarts-par-dimension")
    par_dim = ec.groupby("dimension").size().to_dict()
    log("ecarts-par-dimension", len(ec), f"par dimension : {par_dim}")
    print(f"ecarts-par-dimension : {len(ec)} lignes {par_dim}")

    # ---------------- D. classement des regions (effectifs, lignes de detail) ------------------------------
    reg = ec[(ec.dimension == "region") & (ec.agregat == "detail") & ec.ips.notna()].copy()
    reg["rang"] = reg.groupby(["feuille", "bloc", "niveau_scolaire", "annee_scolaire"])["ips"].rank(method="min")
    cols_d = ["feuille", "bloc", "bloc_titre", "niveau_enseignement", "indicateur", "categorie", "annee_scolaire", "annee_debut",
              "ips", "part_filles", "statut_parite", "ips_national", "ecart_vs_national", "rang"]
    reg = reg.sort_values(["feuille", "bloc", "annee_debut", "rang"])
    ecrire(reg[cols_d].rename(columns={"categorie": "region"}), "classement-regions")
    log("classement-regions", len(reg), f"{reg.categorie.nunique()} regions")
    print(f"classement-regions : {len(reg)} lignes, {reg.categorie.nunique()} regions")

    # ---------------- E. tendances de l'IPS -----------------------------------------------------------------
    base = pd.concat([ec, p[p.dimension == "national"]])
    base = base[base.ips.notna() & base.agregat.isin(["detail", "national"])]
    lignes = []
    for cle, g in base.groupby(["feuille", "bloc", "niveau_enseignement", "indicateur", "dimension", "categorie", "niveau_scolaire"]):
        g = g.drop_duplicates("annee_debut").sort_values("annee_debut")
        if len(g) < 2:
            continue
        pente = float(np.polyfit(g.annee_debut.astype(float), g.ips.astype(float), 1)[0])
        lignes.append(dict(zip(["feuille", "bloc", "niveau_enseignement", "indicateur", "dimension", "categorie",
                                "niveau_scolaire"], cle, strict=False),
                           annee_debut_serie=int(g.annee_debut.iloc[0]), annee_fin_serie=int(g.annee_debut.iloc[-1]),
                           ips_debut=g.ips.iloc[0], ips_fin=g.ips.iloc[-1], variation=round(g.ips.iloc[-1] - g.ips.iloc[0], 4),
                           pente_par_an=round(pente, 5), n_annees=len(g)))
    td = pd.DataFrame(lignes)
    ecrire(td, "tendances")
    log("tendances", len(td), "series avec au moins 2 annees")
    print(f"tendances : {len(td)} series")

    # ---------------- dictionnaire, journal, LISEZ-MOI ------------------------------------------------------
    dico = pd.DataFrame(DICTIONNAIRE, columns=["table", "colonne", "description"])
    ecrire(dico, "dictionnaire-variables")
    ecrire(pd.DataFrame(journal), "journal-transformation")
    (sortie / "LISEZ-MOI.txt").write_text(
        f"DEPOT 03_transformation - equipe {a.equipe}, defi {a.defi}, role {a.role}\n"
        f"Genere le {datetime.now():%Y-%m-%d %H:%M} par transformation_template.py\n"
        f"Entree : {entree.name} (sortie de 02_nettoyage)\n\n"
        "- parite-effectifs : IPS (filles/garcons) et part de filles calcules sur les effectifs, par region, statut, milieu, niveau\n"
        "- parite-taux : IPS recalcule a partir des taux (TBA, TBS, achevement) compare a l'IPS publie par la DGESS\n"
        "- controle-ips : lignes ou l'IPS recalcule differe de l'IPS publie (tolerance " + str(TOLERANCE_IPS) + ")\n"
        "- ecarts-par-dimension : ecarts par milieu / statut / region par rapport au national du meme tableau\n"
        "- classement-regions : rang des regions par annee (1 = parite la plus defavorable aux filles)\n"
        "- tendances : evolution de l'IPS (variation, pente par an)\n- dictionnaire-variables : description de chaque colonne\n\n"
        f"Parite : {PARITE_BASSE} <= IPS <= {PARITE_HAUTE} (convention a ajuster). Les ratios sont calcules sur des valeurs\n"
        "publiees et arrondies : un IPS ne doit pas etre lu avec plus de 2 decimales.\n"
        "Limites : milieu urbain/rural disponible seulement au niveau national (et de 2018 a 2025 pour le prescolaire) ;\n"
        "regions = 13 anciennes regions, non assimilables aux 17 nouvelles ; la convention des annees numeriques\n"
        "(--annee-numerique du nettoyage) doit etre confirmee.\n", encoding="utf-8")
    print(f"\ntables ecrites dans {sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
