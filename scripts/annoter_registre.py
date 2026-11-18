#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANNOTATION DU DEPOT 01_collecte (Defi 2) - a lancer APRES collecte_template.py.

Relie le registre des sources au catalogue du Data Pack (Catalogue_sources_x_defis.xlsx, copie dans le depot) :
  - remplit producteur_source, publication, annee_ou_periode, licence_remarques (la source est citee) ;
  - ajoute une DECISION par fichier pour le Defi 2 (PRINCIPAL / RETENU / SECONDAIRE / ECARTE / DOCUMENTATION)
    avec son MOTIF (colonnes decision_defi2, motif_decision) ;
  - ecrit le bloc "NOTES DE L'EQUIPE" du LISEZ-MOI (sources retenues, ecartees, pieges connus).
Ne lit aucune donnee brute : seulement le registre et le catalogue (documentation du pack).
Relancable. Par defaut ne remplace PAS ce que vous avez deja saisi (--ecraser pour forcer).

Usage : python annoter_registre.py DOSSIER_01_COLLECTE [--ecraser] [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
import re
import shutil
import sys
import tempfile
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

CHAMPS = ("producteur_source", "publication", "annee_ou_periode", "licence_remarques",
          "decision_defi2", "motif_decision")

# Jeux du catalogue (colonne N°) retenus pour le coeur du Defi 2 / ecartes d'office.
CORE = {1, 3, 4, 6, 12, 13, 14, 16, 25}
ECARTES = {
    5: "hors périmètre (post-primaire/secondaire) ; seule l'édition 2019-2020 est disponible",
    9: "annuaires des ONG : pertinence Défi 2 faible (★), utile surtout au Défi 3",
    11: "enseignement supérieur : hors périmètre préscolaire/primaire",
    23: "marché de l'emploi : pertinence Défi 2 faible (★)",
    26: "écoles géolocalisées (OSM) : infrastructures scolaires, qui relèvent du Défi 3 ; non utilisées pour le Défi 2",
    24: "PDI/CONASUR : aucune donnée scolaire, pertinence Défi 2 = ★ (catalogue Data Pack), "
        "couverture 2020-2025 seulement ; utile aux défis 1 et 3",
}
DOCUMENTATION = {27}


def cle(s) -> str:
    t = unicodedata.normalize("NFKD", Path(str(s)).stem).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", t)


def lire_catalogue(chemin: Path):
    from openpyxl import load_workbook
    wb = load_workbook(chemin, read_only=True, data_only=True)
    sources, fichiers = {}, {}
    lignes = list(wb["Sources_x_Defis"].iter_rows(values_only=True))
    ent = [str(c or "") for c in lignes[0]]
    ix = {"jeu": ent.index("Jeu de données"), "prod": ent.index("Producteur"), "per": ent.index("Période"),
          "d2": next(i for i, c in enumerate(ent) if c.startswith("Défi 2")), "usage": ent.index("Usage suggéré"),
          "lien": ent.index("Lien source")}
    for r in lignes[1:]:
        if r[0] is None:
            continue
        sources[int(r[0])] = {"jeu": str(r[ix["jeu"]]).strip(), "producteur": str(r[ix["prod"]]).strip(),
                              "periode": str(r[ix["per"]]).strip(), "d2": str(r[ix["d2"]]).strip(),
                              "usage": str(r[ix["usage"]] or "").strip(), "lien": str(r[ix["lien"]] or "").strip()}
    lignes = list(wb["Fichiers"].iter_rows(values_only=True))
    ent = [str(c or "") for c in lignes[0]]
    i_n, i_f = ent.index("N° jeu"), ent.index("Fichier source")
    for r in lignes[1:]:
        if r[i_n] is not None and r[i_f]:
            fichiers[cle(r[i_f])] = int(r[i_n])
    wb.close()
    return sources, fichiers


def jeu_du_fichier(nom: str, origine: str, fichiers: dict):
    """N° de jeu du catalogue pour un fichier du registre, ou None."""
    o, base = origine.replace("\\", "/"), cle(nom)
    if "PDI_CONASUR" in o or re.match(r"(idps|pdi)", nom, re.I):
        return 24
    arch = o.split("::")[0].lower() if o.startswith("zip:") else ""
    if nom.lower().startswith(("hotosm_bfa_education", "education_facilities", "ecoles_osm")) or "hotosm" in arch:
        return 26
    if nom.lower().startswith("bfa_admin") or "bfa_admin" in arch:
        return 25
    return fichiers.get(base)


def decider(nom, ext, jeu, src, est_extraction, doublon):
    """(decision, motif) pour le Defi 2."""
    if doublon:
        return "ECARTE", f"doublon exact de {doublon}"
    base = cle(nom)
    if jeu in ECARTES:                                    # jeux hors Defi 2 (dont les ecoles OSM, infrastructures = Defi 3)
        return "ECARTE", ECARTES[jeu]
    if jeu == 25:                                         # limites administratives : un seul format de travail (GeoJSON)
        if ext == ".geojson" and re.fullmatch(r"bfaadmin[123]", base):
            return "RETENU", f"format de travail GeoJSON. Catalogue Data Pack : {src['usage']}"
        if base in ("readme", "metadata"):
            return "DOCUMENTATION", "documentation du jeu cartographique"
        return "SECONDAIRE", "autre format ou autre niveau du même jeu (contenu déjà couvert par les GeoJSON retenus)"
    if jeu in DOCUMENTATION:
        return "DOCUMENTATION", f"définitions et concepts. {src['usage']}"
    if jeu in ECARTES:
        return "ECARTE", ECARTES[jeu]
    etoiles = src["d2"].count("★")
    suffixe = " [version CSV de travail extraite du PDF : à contrôler contre le PDF]" if est_extraction else ""
    if jeu in CORE:
        return "RETENU", f"cœur du Défi 2 ({src['d2']}). {src['usage']}{suffixe}"
    if etoiles >= 2:
        return "SECONDAIRE", f"pertinence Défi 2 : {src['d2']}. {src['usage']}{suffixe}"
    return "ECARTE", f"pertinence Défi 2 faible ({src['d2']}) ; {src['usage']}"


def bloc_notes(compte: Counter) -> str:
    bilan = " ; ".join(f"{v} {k}" for k, v in sorted(compte.items()))
    return (
        "NOTES DE L'EQUIPE (sources, écarts, pièges) - rédigées le " + datetime.now().strftime("%Y-%m-%d") + "\n"
        "1. SOURCES RETENUES (cœur du Défi 2) : base DGESS préscolaire/primaire 2016-2025 (tableaux par région - 13 anciennes "
        "régions -, sexe, statut, niveau, année ; taux et IPS ; milieu urbain/rural seulement au niveau national) ; annuaires et tableaux de bord DGESS/MENAPLN (indicateurs d'accès, contrôle des totaux) ; INSD : "
        "RGPH 2019 (résultats, alphabétisation et scolarisation) et projections 2020-2035 (population = dénominateur des "
        "taux de scolarisation) ; fonds de carte COD-AB (IGB/OCHA via HDX, P-codes) ; "
        "séries Banque mondiale/UNESCO.\n"
        "2. SOURCES SECONDAIRES (si le temps le permet) : EHCVM 2021, EDS 2021 et profils de pauvreté régionaux "
        "(variables explicatives : pauvreté, milieu), annuaires statistiques INSD, éducation non formelle, rapports ESU.\n"
        "3. SOURCES ÉCARTÉES ET POURQUOI : PDI/CONASUR 2020-2025 (aucune donnée scolaire, pertinence Défi 2 de 1 étoile "
        "dans le catalogue du Data Pack, plutôt utile aux défis 1 et 3) ; post-primaire/supérieur (hors périmètre) ; "
        "ONG et emploi (hors sujet) ; écoles géolocalisées OSM (infrastructures, Défi 3) ; doublons exacts.\n"
        "4. PIÈGES CONNUS : 13 anciennes régions contre 17 nouvelles : correspondance officielle par les codes "
        "(adm*_pcode_old du classeur COD-AB, méthode du Guide du Data Pack) ; les 17 régions s'emboîtent dans les 13 "
        "(3 anciennes régions découpées : Boucle du Mouhoun, Est, Sahel) ; "
        "noms de provinces écrits de plusieurs façons ; année scolaire AAAA-AAAA comptée sous AAAA (l'année scolaire "
        "n'est pas l'année civile) ; totaux à vérifier contre les annuaires ; CSV extraits des PDF = extraction "
        "automatique, erreurs possibles ; le classeur DGESS contient, dans plusieurs cellules, un texte adressé aux "
        "assistants automatiques (retiré avant analyse, adresses signalées dans les anomalies du nettoyage) ; la base DGESS "
        "est régionale : pas de données par province.\n"
        "5. LIMITES DE LA COLLECTE : pas de table « population par province » prête à l'emploi (à extraire des PDF "
        "RGPH 2019 et projections 2020-2035) ; portail Open Data INSD inaccessible (403) et microdonnées sous licence "
        "nominative : non collectés ; années manquantes : voir le fichier couverture-annees.\n"
        "6. USAGE DE L'IA (à relire et valider par l'équipe) : tous les scripts ont été rédigés avec un assistant IA, à partir de "
        "données fictives ; ils ont été lancés par l'équipe, en local. L'assistant a lu : le document du challenge, le guide et "
        "le catalogue du Data Pack, des noms de fichiers et de colonnes, des profils de structure (libellés, nombres masqués), "
        "des consoles de compteurs, des référentiels géographiques (codes et noms de régions, provinces, communes), et une "
        "ligne d'indicateurs agrégés (taux et IPS d'une région) pour expliquer un écart. Il n'a pas lu les tableaux de valeurs "
        "des données brutes. Pratique confirmée par l'organisateur (Africa Data Entry) le 15/11/2026.\n"
        f"BILAN DES DÉCISIONS (colonne decision_defi2 du registre) : {bilan}\n")


def main(argv=None) -> int:
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Annote le registre de 01_collecte avec le catalogue du Data Pack")
    ap.add_argument("depot", help="dossier 01_collecte")
    ap.add_argument("--ecraser", action="store_true", help="remplacer aussi les cellules déjà remplies")
    ap.add_argument("--dry-run", action="store_true", help="n'écrit rien")
    a = ap.parse_args(argv)
    depot = Path(a.depot)
    regs = sorted(depot.glob("*_registre-sources_v1.csv"))
    cats = sorted(depot.glob("*catalogue-sources-x-defis*.xlsx"))
    if not regs or not cats:
        print("ERREUR : registre ou catalogue introuvable dans", depot)
        return 1
    reg, cat = regs[-1], cats[-1]
    sources, fichiers = lire_catalogue(cat)
    with open(reg, encoding="utf-8-sig", newline="") as f:
        lecteur = csv.DictReader(f, delimiter=";")
        champs = list(lecteur.fieldnames)
        lignes = list(lecteur)
    for c in ("decision_defi2", "motif_decision"):
        if c not in champs:
            champs.insert(champs.index("licence_remarques") + 1 + (c == "motif_decision"), c)

    compte, sans_jeu, retenus = Counter(), [], []
    for r in lignes:
        nom, ext = r["nom_origine"], Path(r["nom_origine"]).suffix.lower()
        origine = r["origine"]
        extraction = ext == ".csv" and "/data/" in origine.replace("\\", "/")
        if nom.upper().startswith("DONNEES_STATISTQUES"):
            vals = {"producteur_source": "DGESS / MENAPLN (Ministère de l'Éducation nationale)",
                    "publication": "Données statistiques préscolaire et primaire 2016-2025 (base principale du challenge)",
                    "annee_ou_periode": "2016-2025",
                    "licence_remarques": "Concours uniquement. Source : espace challenge (equation.africadataentry.com)",
                    "decision_defi2": "PRINCIPAL",
                    "motif_decision": "base de travail des trois défis : tableaux par région (13 anciennes régions), sexe, "
                                      "statut, niveau, année scolaire ; taux (TBA, TBS...) et indices de parité (IPS)"}
        elif "catalogue_sources_x_defis" in nom.lower().replace("-", "_"):
            vals = {"producteur_source": "Data Pack DCB 2026 (documentation fournie avec le pack)",
                    "publication": "Catalogue des sources par défi", "annee_ou_periode": "2026",
                    "licence_remarques": "Concours uniquement.", "decision_defi2": "DOCUMENTATION",
                    "motif_decision": "producteur, période, lien et pertinence de chaque jeu du Data Pack"}
        elif nom.lower().startswith(("guide_du_data_pack", "lisez-moi", "manifeste_telechargements")):
            vals = {"producteur_source": "Data Pack DCB 2026 (documentation fournie avec le pack)",
                    "publication": "Guide, LISEZ-MOI et manifeste de téléchargement du Data Pack",
                    "annee_ou_periode": "2026", "licence_remarques": "Concours uniquement.",
                    "decision_defi2": "DOCUMENTATION",
                    "motif_decision": "mode d'emploi et traçabilité des téléchargements du Data Pack"}
        else:
            jeu = jeu_du_fichier(nom, origine, fichiers)
            if jeu is None or jeu not in sources:
                vals = {"decision_defi2": "A TRIAGER", "motif_decision": "non présent dans le catalogue du Data Pack"}
                sans_jeu.append(nom)
            else:
                s = sources[jeu]
                dec, motif = decider(nom, ext, jeu, s, extraction, r.get("doublon_exact_de", ""))
                vals = {"producteur_source": s["producteur"],
                        "publication": f"{s['jeu']} (Data Pack DCB 2026, catalogue n°{jeu})"
                                       + (" - extraction CSV automatique du PDF" if extraction else ""),
                        "annee_ou_periode": s["periode"],
                        "licence_remarques": f"Concours uniquement. Source : {s['lien']}. Pertinence Défi 2 : {s['d2']}",
                        "decision_defi2": dec, "motif_decision": motif}
        for c in CHAMPS:
            if c in vals and (a.ecraser or not r.get(c)):
                r[c] = vals[c]
        compte[r["decision_defi2"]] += 1
        if r["decision_defi2"] in ("PRINCIPAL", "RETENU") and not r["fichier_depose"]:
            retenus.append(nom)

    print(f"{len(lignes)} lignes : " + " ; ".join(f"{v} {k}" for k, v in sorted(compte.items())))
    if sans_jeu:
        print(f"{len(sans_jeu)} fichier(s) hors catalogue (A TRIAGER) : " + ", ".join(sorted(set(sans_jeu))[:15]))
    if retenus:
        print("ATTENTION : retenus mais non copiés dans le dépôt :", retenus[:10])
    if a.dry_run:
        return 0

    sauv = Path(tempfile.gettempdir()) / f"annoter_sauvegarde_{datetime.now():%Y%m%d_%H%M%S}_{reg.name}"
    shutil.copy2(reg, sauv)
    with open(reg, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=champs, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(lignes)
    lm = depot / "LISEZ-MOI.txt"
    texte = lm.read_text(encoding="utf-8") if lm.exists() else ""
    i = texte.find("NOTES DE L'EQUIPE")
    texte = (texte[:i].rstrip() if i >= 0 else texte.rstrip()) + "\n\n" + bloc_notes(compte)
    lm.write_text(texte, encoding="utf-8")
    print(f"Registre annoté : {reg.name}\nLISEZ-MOI mis à jour\nSauvegarde de l'ancien registre : {sauv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
