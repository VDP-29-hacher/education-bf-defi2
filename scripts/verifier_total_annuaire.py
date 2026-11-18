#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VERIFICATION DES TOTAUX - "Verifiez vos totaux : comparez vos chiffres aux publications d'origine" (regle d'or du PDF).

Cherche les TOTAUX NATIONAUX de la base nettoyee (02_nettoyage) parmi TOUS les nombres d'un annuaire de reference
(CSV d'extraction du Data Pack, ou PDF), sans rien supposer de la mise en page. Pour chaque annee de la base, il compte
combien de totaux nationaux (garcons / filles / total) apparaissent dans l'annuaire.

L'annee de l'annuaire est la PLUS RECENTE annee de la base dont les totaux s'y retrouvent (un annuaire 2024-2025 cite aussi
des annees precedentes pour comparer). On la compare a l'annee attendue pour trancher la convention des annees
numeriques du classeur (2025 = 2024-2025 ?  -> --annee-numerique fin).

Deux usages :
  - prescolaire : annuaire preescolaire 2024-2025 (CNS528) contre les tableaux PRESCOLAIRE (annees numeriques)
  - primaire    : annuaire primaire 2024-2025 (CNS530) contre Feuil1... (annees explicites 2024-2025) : verifie la lecture

La console n'affiche que des compteurs ; les valeurs et les pages sont dans le fichier CSV de sortie.

Usage :
  python verifier_total_annuaire.py TABLEAUX_LONG.csv ANNUAIRE.csv|pdf DOSSIER_02 --equipe Burkina_Novation --niveau prescolaire
         [--annee-annuaire 2024]
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

SEUIL_VALEUR = 1000          # on ignore les petits nombres (trop de coincidences)
SEUIL_TAUX = 0.5             # part minimale de totaux retrouves pour dire qu'une annee figure dans l'annuaire
RX_NOMBRE = re.compile(r"(?<![\d.,])(\d{1,3}(?:[   .,]\d{3})+|\d{4,})(?![\d])")


def nombres_du_texte(texte: str):
    """Entiers (>= SEUIL_VALEUR) cites dans un texte : '123 456', '123.456', '123,456', '123456'."""
    for m in RX_NOMBRE.finditer(texte):
        v = int(re.sub(r"[   .,]", "", m.group(1)))
        if v >= SEUIL_VALEUR:
            yield v


def lire_annuaire(chemin: Path):
    """dict nombre -> ensemble de pages ; (n_pages, n_nombres)."""
    pages = defaultdict(set)
    n_pages = set()
    if chemin.suffix.lower() == ".csv":
        with open(chemin, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f, delimiter=";"):
                page = row.get("page", "")
                n_pages.add(page)
                for k, v in row.items():
                    if k and re.fullmatch(r"c\d+", k) and v:
                        for n in nombres_du_texte(v):
                            pages[n].add(page)
    else:
        try:
            from pypdf import PdfReader
            lecteur = PdfReader(str(chemin))
            textes = [(i + 1, p.extract_text() or "") for i, p in enumerate(lecteur.pages)]
        except ImportError:
            import fitz
            doc = fitz.open(str(chemin))
            textes = [(i + 1, p.get_text()) for i, p in enumerate(doc)]
        for i, t in textes:
            n_pages.add(str(i))
            for n in nombres_du_texte(t):
                pages[n].add(str(i))
    return pages, (len(n_pages), len(pages))


def main(argv=None) -> int:
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Cherche les totaux nationaux de la base dans un annuaire de reference")
    ap.add_argument("tableaux_long", help="table longue de 02_nettoyage")
    ap.add_argument("annuaire", help="CSV d'extraction ou PDF de l'annuaire de reference")
    ap.add_argument("sortie", help="dossier 02_nettoyage")
    ap.add_argument("--equipe", required=True)
    ap.add_argument("--niveau", choices=["prescolaire", "primaire"], required=True)
    ap.add_argument("--annee-annuaire", type=int, default=2024,
                    help="annee de DEBUT de l'annee scolaire de l'annuaire (2024 pour 2024-2025)")
    ap.add_argument("--defi", default="D2")
    ap.add_argument("--role", default="engineer")
    a = ap.parse_args(argv)
    for p in (a.tableaux_long, a.annuaire):
        if not Path(p).is_file():
            print(f"ERREUR : fichier introuvable : {Path(p).name}")
            return 1
    sortie = Path(a.sortie)
    sortie.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(a.tableaux_long, sep=";", encoding="utf-8-sig", keep_default_na=False, dtype=str)
    df["valeur"] = pd.to_numeric(df["valeur"], errors="coerce")
    df["annee_debut"] = pd.to_numeric(df["annee_debut"], errors="coerce")
    conv = df["annee_numerique_convention"].iloc[0] if "annee_numerique_convention" in df and len(df) else "debut (suppose)"
    sel = df[(df.niveau_enseignement == a.niveau) & (df.type_valeur == "effectif") & (df.agregat == "national")
             & df.sexe.isin(["garcons", "filles", "total"]) & (df.valeur >= SEUIL_VALEUR)]
    if sel.empty:
        print(f"ERREUR : aucun total national d'effectifs pour le niveau '{a.niveau}' dans la table.")
        return 1
    tot = sel.groupby(["annee_debut", "annee_scolaire", "annee_source", "sexe"], as_index=False)["valeur"].first()

    pages, (n_pages, n_nombres) = lire_annuaire(Path(a.annuaire))
    if n_nombres == 0:
        print("ERREUR : aucun nombre lu dans l'annuaire (PDF scanne ? essayez le CSV d'extraction du Data Pack).")
        return 1
    tot["valeur_entiere"] = tot.valeur.round().astype(int)
    tot["pages"] = tot.valeur_entiere.map(lambda v: "; ".join(sorted(pages.get(v, []), key=lambda x: (len(x), x))[:6]))
    tot["trouve"] = tot.pages.map(lambda s: "oui" if s else "non")
    pre = f"{a.equipe}_02-nettoyage_{a.defi}_{a.role}"
    tot[["annee_debut", "annee_scolaire", "annee_source", "sexe", "valeur", "trouve", "pages"]].to_csv(
        sortie / f"{pre}_verification-total-annuaire-{a.niveau}-{a.annee_annuaire}-{a.annee_annuaire + 1}_v1.csv",
        sep=";", index=False, encoding="utf-8-sig")

    par_an = tot.groupby("annee_debut").agg(testes=("trouve", "size"), trouves=("trouve", lambda s: int((s == "oui").sum())))
    par_an["taux"] = par_an.trouves / par_an.testes
    print(f"annuaire : {Path(a.annuaire).name[:70]} | {n_pages} pages, {n_nombres} nombres distincts >= {SEUIL_VALEUR}")
    print(f"totaux nationaux testes (niveau {a.niveau}) : {len(tot)} ; convention d'annee de la base : {conv}")
    for an, r in par_an.sort_index().iterrows():
        print(f"  annee_debut {int(an)} : {int(r.trouves)}/{int(r.testes)} totaux retrouves dans l'annuaire")
    ok = par_an[(par_an.taux >= SEUIL_TAUX) & (par_an.testes >= 2)]
    if ok.empty:
        print("CONCLUSION : aucun total national de la base n'est retrouve dans l'annuaire. Pas concluant : verifiez a la main "
              "(autre annuaire ? annee non publiee ? valeurs differentes ?).")
        return 0
    recent = int(ok.index.max())
    attendu = a.annee_annuaire
    print(f"annee la plus recente retrouvee : annee_debut {recent} (attendu pour l'annuaire {attendu}-{attendu + 1} : {attendu})")
    sources = set(sel[sel.annee_debut == recent].annee_source)
    if recent == attendu:
        print(f"CONCLUSION : COHERENT. Les libelles d'annee actuels de la base correspondent a l'annuaire "
              f"(convention des annees numeriques : {conv}).")
    elif recent == attendu + 1 and "numerique" in sources and str(conv).startswith("debut"):
        print("CONCLUSION : DECALAGE d'un an. Les annees numeriques du classeur sont des annees de FIN "
              "(2025 = 2024-2025). Relancez le nettoyage avec --annee-numerique fin.")
    elif recent == attendu - 1 and "numerique" in sources and str(conv).startswith("fin"):
        print("CONCLUSION : DECALAGE d'un an dans l'autre sens. Les annees numeriques sont des annees de DEBUT. "
              "Relancez le nettoyage avec --annee-numerique debut.")
    else:
        print(f"CONCLUSION : ecart de {recent - attendu:+d} an(s) non explique par la convention des annees numeriques "
              f"(source des annees : {sorted(sources)}). Verifiez a la main.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
