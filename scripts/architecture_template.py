#!/usr/bin/env python3
"""LIVRABLE ARCHITECT (Defi 2) : architecture du pipeline, modele de donnees, decisions (PDF, 3 pages).

Entrees : 03_transformation/*_dictionnaire-variables_v1.csv (table;colonne;description) et, s'ils existent, les en-tetes
          des tables de 04_analyse (pour le modele de donnees de l'etape 4). Aucune donnee brute.
Sortie  : <dossier>/<EQ>_03-transformation_D2_architect_architecture-pipeline_v1.pdf
Usage   : architecture_template.py DOSSIER_03 DOSSIER_SORTIE [--equipe Burkina_Novation]
"""
import argparse, glob, os, sys, textwrap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch
import pandas as pd

BLEU, GRIS, VERT, ORANGE, VIOLET = "#dbe9f6", "#eeeeee", "#dff2e1", "#fde8cc", "#ebe3f5"


def boite(ax, x, y, w, h, titre, lignes, fond, taille=7.0):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.01,rounding_size=0.015", fc=fond, ec="#555", lw=1))
    ax.text(x + w / 2, y + h - 0.025, titre, ha="center", va="top", fontsize=9.2, fontweight="bold")
    ax.text(x + 0.01, y + h - 0.07, "\n".join(lignes), ha="left", va="top", fontsize=taille, linespacing=1.35)


def fleche(ax, x0, y0, x1, y1):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle="->", lw=1.3, color="#333"))


def page(titre):
    f = plt.figure(figsize=(11.69, 8.27))  # A4 paysage
    ax = f.add_axes([0.03, 0.03, 0.94, 0.88]); ax.axis("off"); ax.set_xlim(-0.015, 1.015); ax.set_ylim(-0.02, 1)
    f.text(0.03, 0.95, titre, fontsize=15, fontweight="bold")
    return f, ax


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dossier03"); ap.add_argument("sortie"); ap.add_argument("--equipe", default="Burkina_Novation")
    a = ap.parse_args()
    f = glob.glob(os.path.join(a.dossier03, "*_dictionnaire-variables_v1.csv"))
    if not f:
        sys.exit("Dictionnaire introuvable : lancez d'abord l'etape 3.")
    dico = pd.read_csv(f[0], sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    d04 = os.path.join(os.path.dirname(os.path.abspath(a.dossier03)), "04_analyse")
    os.makedirs(a.sortie, exist_ok=True)
    cible = os.path.join(a.sortie, f"{a.equipe}_03-transformation_D2_architect_architecture-pipeline_v1.pdf")

    with PdfPages(cible) as pdf:
        # ---- page 1 : flux du pipeline et rôles ----
        fg, ax = page(f"Équipe {a.equipe} - Défi 2 : architecture du pipeline de données")
        etapes = [
            ("1 COLLECTE", "Engineer", ["Data Pack + base DGESS", "Copies en lecture seule", "Registre des sources", "Couverture des années"], BLEU),
            ("2 NETTOYAGE", "Engineer", ["« Tableau N » -> table longue", "Libellés harmonisés", "Journal + anomalies", "Totaux = annuaires",
                                        "Annuaire -> 45 provinces"], BLEU),
            ("3 TRANSFORMATION", "Engineer, Architect", ["IPS, écarts, classements", "Tendances, dictionnaire", "Liaison 13 -> 17 régions",
                                                          "(codes COD-AB, contrôle", " par noms de communes)"], BLEU),
            ("4 ANALYSE", "Analyst, Scientist", ["Accès : TBS, TBA, TAP par sexe", "45 provinces : IPS, urbain/rural,", " effectifs / maximum",
                                                  "17 régions actuelles (exact)", "Provinces prioritaires", "Prévision IPS (validée)",
                                                  "Liens et profils de provinces", "Plateforme React + API NestJS"], VERT),
            ("5 INTERPRÉTATION", "Analyst", ["Fiche d'une page", "Dossier technique (≤ 15 p.)", "Hypothèses ≠ conclusions",
                                             "Pistes d'action ciblées"], VERT),
        ]
        w, h, y = 0.175, 0.40, 0.47
        for i, (t, role, l, c) in enumerate(etapes):
            x = 0.005 + i * 0.199
            boite(ax, x, y, w, h, t, [f"Rôle : {role}", ""] + l, c)
            if i:
                fleche(ax, x - 0.024, y + h / 2, x, y + h / 2)
        boite(ax, 0.005, 0.15, 0.31, 0.24, "Contrôle qualité (transversal)",
              ["Somme des détails = totaux ; F + G = total", "Totaux nationaux = annuaires 2024-2025", "IPS recalculé vs IPS publié",
               "IPS sur effectif effondré : retiré et signalé", "Somme des provinces = national (0 écart)"], ORANGE)
        boite(ax, 0.335, 0.15, 0.31, 0.24, "Reproductibilité",
              ["lancer_pipeline.ps1 : une commande, ordre fixe", "Relance déterministe (CSV identiques)", "Manifeste sha256 des fichiers déposés",
               "Contrôle automatique avant dépôt", "Convention de nommage de la plateforme"], ORANGE)
        boite(ax, 0.665, 0.15, 0.33, 0.24, "Sécurité et règles du challenge",
              ["Bruts jamais modifiés ni envoyés à une IA", "Étapes 1-3 lancées en local par l'équipe", "Étapes 4-5 : tables agrégées seulement",
               "Textes d'injection détectés, retirés, signalés", "Pas de chemin personnel dans les sorties"], ORANGE)
        for x in (0.16, 0.49, 0.83):
            fleche(ax, x, 0.47, x, 0.39)
        ax.text(0.005, 0.10, "Principe : une étape = un dossier = un dépôt ; chaque étape lit uniquement la sortie de la précédente.\n"
                             "Modèle commun : zone (région, province ou région actuelle) × année scolaire × niveau × sexe (× milieu, statut).",
                fontsize=9, va="top")
        pdf.savefig(fg); plt.close(fg)

        # ---- page 2 : modèle de données (étape 3 : dictionnaire ; étape 4 : en-têtes des tables) ----
        fg, ax = page("Modèle de données")
        blocs = []
        fm = glob.glob(os.path.join(a.dossier03, "*_modele-commun-region-annee_v1.csv"))
        if fm:
            blocs.append(("Étape 3 - MODÈLE COMMUN région × année", list(pd.read_csv(fm[0], sep=";", encoding="utf-8-sig", nrows=0).columns), ORANGE))
        for t in list(dict.fromkeys(dico["table"]))[:4 - len(blocs)]:
            cols = list(dico[dico["table"] == t]["colonne"])
            blocs.append((f"Étape 3 - {t}", cols, GRIS))
        for cle in ("indicateurs-provinces", "acces-regions", "regions17-indicateurs", "provinces-prioritaires", "prevision-ips-provinces"):
            fx = glob.glob(os.path.join(d04, f"*_{cle}_v1.csv"))
            if fx:
                cols = list(pd.read_csv(fx[0], sep=";", encoding="utf-8-sig", nrows=0).columns)
                blocs.append((f"Étape 4 - {cle}", cols, VIOLET))
        blocs = blocs[:9]
        for i, (t, cols, c) in enumerate(blocs):
            court = cols[:14] + ([f"... (+{len(cols) - 14})"] if len(cols) > 14 else [])
            x, y0 = 0.005 + (i % 3) * 0.333, 0.645 - (i // 3) * 0.31
            boite(ax, x, y0, 0.32, 0.29, t[:48], ["\n".join(textwrap.wrap(", ".join(court), 62))], c, 6.8)
        ax.text(0.005, 0.0, "Clés de jointure : région ou province (noms harmonisés, codes COD-AB pour les liaisons) × année scolaire (annee_debut). "
                            "Séparateur « ; », UTF-8, décimales au point dans les CSV.", fontsize=8)
        pdf.savefig(fg); plt.close(fg)

        # ---- page 3 : décisions ----
        fg, ax = page("Décisions d'architecture")
        dec = [
            ("Table longue unique", "Une ligne = une valeur observée (feuille, bloc, région, milieu/statut/niveau, année, sexe) : un seul format pour une dizaine de mises en page."),
            ("Années numériques = années de fin", "Seule convention pour laquelle les totaux nationaux coïncident avec les annuaires 2024-2025."),
            ("Liaison 13/17 par codes COD-AB", "Méthode officielle (champs *_pcode_old) ; la reconstruction par noms de communes est gardée comme contrôle (349/351 identiques)."),
            ("17 régions actuelles par agrégation exacte", "Chaque ancienne province est entièrement dans une seule région actuelle : on additionne des effectifs, on n'estime rien."),
            ("Aucune correction silencieuse", "Anomalies listées ; IPS publié et recalculé comparés ; IPS sur effectif effondré (< 10 % du maximum) laissé vide et signalé."),
            ("Accès mesuré par deux sources", "Taux DGESS (TBS, TBA, TAP) par région ; effectifs rapportés au maximum depuis 2015 par province (pas de population provinciale)."),
            ("Prévision : le plus simple qui marche", "Quatre modèles comparés sur le passé ; la persistance l'emporte ; l'erreur mesurée est publiée avec chaque projection."),
            ("Règles de décision paramétrables", "Seuils de priorité (0,95 ; 60 %) déclarés dans les scripts et réglables dans le tableau de bord."),
            ("Limites assumées", "Régions DGESS sur 13 anciennes régions ; provinces pour le primaire seulement ; primaire 2017/18 non retrouvé dans les annuaires."),
        ]
        for i, (t, d) in enumerate(dec):
            yy = 0.95 - i * 0.104
            ax.text(0.005, yy, f"{i + 1}. {t}", fontsize=10, fontweight="bold", va="top")
            ax.text(0.03, yy - 0.033, "\n".join(textwrap.wrap(d, 135)), fontsize=8.6, va="top")
        pdf.savefig(fg); plt.close(fg)

        # ---- page 4 : modeles conceptuel, logique, physique et acces ----
        fg, ax = page("Du modèle conceptuel au stockage, et qui accède à quoi")
        boite(ax, 0.005, 0.50, 0.32, 0.44, "1. Modèle conceptuel", [
            "Dimensions :", "  ZONE : commune ⊂ province ⊂ région", "    (ancienne région 13 ou région actuelle 17)",
            "  PÉRIODE : année scolaire", "  NIVEAU : préscolaire, primaire, classe", "  SEXE · MILIEU · STATUT", "",
            "Faits mesurés pour une zone et une année :", "  ÉLÈVES (par sexe)", "  TAUX : TBS, TBA, TAP (par sexe)",
            "  POPULATION d'âge scolaire (par sexe)", "  ÉCART D'ACCÈS : élèves à ajouter",
            "    pour un TBS de 100 %"], BLEU)
        boite(ax, 0.34, 0.50, 0.32, 0.44, "2. Modèle logique", [
            "Clé commune : zone × année scolaire", "", "tableaux-long : feuille, bloc, région, statut,", "  milieu, niveau, sexe, année → valeur",
            "modele-commun : région, année → élèves, TBS,", "  population, élèves à ajouter (par sexe)",
            "indicateurs-provinces : province → IPS,", "  accès, élèves perdus, filles manquantes",
            "liaison-officielle-communes : code commune", "  → province ancienne → région actuelle",
            "regions17 : région actuelle → sommes", "  exactes de ses provinces"], VERT)
        boite(ax, 0.675, 0.50, 0.32, 0.44, "3. Modèle physique", [
            "Fichiers CSV « ; », UTF-8, point décimal", "Géométries en GeoJSON (codes COD-AB)",
            "Un dossier par étape : 01 à 05", "Regroupements en zip pour le dépôt",
            "Nommage : équipe_étape_défi_rôle_objet_vN", "Empreinte sha256 de chaque fichier déposé", "",
            "Pas de base de données : moins de 50 Mo,", "tout se relit sans serveur et sans Internet ;",
            "le tableau de bord embarque ses données", "dans un seul fichier HTML."], GRIS)
        ax.text(0.005, 0.44, "4. Qui accède à quoi", fontsize=11, fontweight="bold", va="top", color="#0b4f7a")
        acces = [["Données brutes (01_collecte)", "lecture seule (attribut fichier)", "Engineer, en local", "jamais envoyées à une IA"],
                 ["Table propre et journaux (02)", "Engineer", "Architect, Analyst, Scientist", "tables agrégées, sans donnée personnelle"],
                 ["Modèle commun, liaisons, dictionnaire (03)", "Architect, Engineer", "Analyst, Scientist", "source des étapes 4 et 5, avec la table des provinces (02)"],
                 ["Analyses, prévision (04)", "Analyst ; Scientist (prévision)", "toute l'équipe", "rejouables à l'identique"],
                 ["Fiches et dossier (05)", "Analyst", "décideurs, jury", "chiffres calculés, aucun saisi à la main"],
                 ["Dépôt (depot_final)", "script depot_final.py", "jury, plateforme", "contrôlé avant dépôt (noms, sha256)"],
                 ["Tableau de bord HTML", "script dashboard_template.py", "directions régionales, public", "données agrégées seulement"]]
        tb = ax.table(cellText=acces, colLabels=["Données", "Qui écrit", "Qui lit", "Règle"], cellLoc="left", colLoc="left",
                      colWidths=[0.27, 0.22, 0.22, 0.29], bbox=[0.005, 0.02, 0.99, 0.39])
        tb.auto_set_font_size(False); tb.set_fontsize(7.8)
        for (r_, c_), cel in tb.get_celld().items():
            cel.set_edgecolor("#c9cdd3")
            if r_ == 0:
                cel.set_facecolor("#0b4f7a"); cel.get_text().set_color("white"); cel.get_text().set_fontweight("bold")
            elif r_ % 2 == 0:
                cel.set_facecolor("#f4f6f8")
        pdf.savefig(fg); plt.close(fg)
    print(f"Architecture generee : {os.path.basename(cible)} (4 pages)")


if __name__ == "__main__":
    main()
