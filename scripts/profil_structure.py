#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PROFIL DE STRUCTURE d'un classeur Excel - SANS AUCUNE VALEUR CHIFFREE.

But : decrire la forme d'un fichier (feuilles, en-tetes sur plusieurs niveaux, cellules fusionnees, types de
colonnes, lignes de total) pour pouvoir ecrire un script de nettoyage, sans montrer les donnees brutes
(regle du challenge : l'IA ne nettoie pas les donnees brutes).

Ce qui est affiche : noms de feuilles, dimensions, libelles TEXTE des premieres lignes (en-tetes), les nombres
remplaces par <nombre>, plages de cellules fusionnees, type dominant de chaque colonne, NOMBRE de lignes de total.
Ce qui n'est JAMAIS affiche : aucune valeur numerique.

Usage : python profil_structure.py FICHIER.xlsx [--lignes 10] [--sortie profil.txt]
Relisez le resultat avant de le partager : reduisez --lignes si des libelles de donnees apparaissent.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RX_TOTAL = re.compile(r"^\s*(total|ensemble|burkina( faso)?|sous[- ]total)\b", re.I)


def lettre(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def typer(v) -> str:
    if v is None or v == "":
        return "vide"
    if isinstance(v, bool):
        return "texte"
    if isinstance(v, (int, float)):
        return "nombre"
    return "texte"


def squelette_lignes(ws, cap: int) -> list:
    """Une ligne par ligne non vide : libelles des 3 premieres colonnes + NOMBRE de nombres (jamais leur valeur)."""
    out, n = [], 0
    for i, r in enumerate(ws.iter_rows(values_only=True), start=1):
        non_vides = [(j, v) for j, v in enumerate(r) if typer(v) != "vide"]
        if not non_vides:
            continue
        # un nombre stocke comme texte ('1 234') est compte comme nombre, jamais affiche
        def est_nombre(v):
            return typer(v) == "nombre" or (typer(v) == "texte" and re.fullmatch(r"[-+]?[\d\s.,%]+", str(v).strip()) is not None)
        textes = [(j, str(v).strip().replace("\n", " ")) for j, v in non_vides if not est_nombre(v)]
        nb = sum(1 for _, v in non_vides if est_nombre(v))
        tete = " ".join(f"{lettre(j)}:{t[:30]}" for j, t in textes if j < 3)
        reste = [t for j, t in textes if j >= 3]
        extra = f" | autres textes ({len(reste)}): " + ", ".join(x[:12] for x in reste[:6]) if reste else ""
        n += 1
        if n <= cap:
            out.append(f"  L{i:<4}{tete}  [{nb} nombres]{extra}")
    if n > cap:
        out.append(f"  ... {n - cap} lignes non vides de plus (augmentez --cap)")
    return out


def profil(chemin: Path, n_lignes: int, echantillon: int = 400, squelette: bool = False, feuilles=None,
           cap: int = 60) -> str:
    from openpyxl import load_workbook
    gros = chemin.stat().st_size > 25 * 1024 * 1024        # gros fichier : mode lecture seule (pas de fusions)
    wb = load_workbook(chemin, read_only=gros, data_only=True)
    out = [f"FICHIER : {chemin.name}  ({chemin.stat().st_size // 1024} Ko)  |  {len(wb.worksheets)} feuille(s)"]
    if gros:
        out.append("(gros fichier : cellules fusionnees non listees)")
    for ws in wb.worksheets:
        if feuilles and ws.title not in feuilles:
            continue
        out.append("\n" + "=" * 78)
        out.append(f"FEUILLE « {ws.title} »  |  {ws.max_row} lignes x {ws.max_column} colonnes")
        if squelette:
            out.extend(squelette_lignes(ws, cap))
            continue
        lignes = [r for _, r in zip(range(echantillon), ws.iter_rows(values_only=True), strict=False)]   # troncature voulue
        if not lignes:
            out.append("  (vide)")
            continue
        if not gros and ws.merged_cells.ranges:
            fus = [str(m) for m in ws.merged_cells.ranges if m.min_row <= n_lignes]
            out.append(f"  Fusions dans les {n_lignes} premieres lignes ({len(fus)}) : " + ", ".join(fus[:40]))
        out.append(f"  --- {n_lignes} premieres lignes (texte tel quel, nombres masques) ---")
        for i, r in enumerate(lignes[:n_lignes], start=1):
            cell = [f"{lettre(j)}:{str(v).strip()[:38]}" if typer(v) == "texte" else f"{lettre(j)}:<nombre>"
                    for j, v in enumerate(r) if typer(v) != "vide"]
            out.append(f"  L{i:<3}" + (" | ".join(cell[:45]) + (" ..." if len(cell) > 45 else "") if cell else "(ligne vide)"))
        # type dominant par colonne sur l'echantillon (hors lignes d'en-tete)
        corps = lignes[n_lignes:] or lignes
        debut = n_lignes + 1 if lignes[n_lignes:] else 1
        nb_col = max(len(r) for r in lignes)
        out.append(f"  --- type dominant par colonne (lignes {debut}..{len(lignes)}) ---")
        resume = []
        for j in range(nb_col):
            types = [typer(r[j]) if j < len(r) else "vide" for r in corps]
            n = len(types)
            t = max(("texte", "nombre", "vide"), key=types.count)
            resume.append(f"{lettre(j)}={t[:3]}{100 * types.count(t) // n}%")
        out.append("  " + "  ".join(resume))
        totaux = sum(1 for r in lignes for v in r[:3] if isinstance(v, str) and RX_TOTAL.match(v))
        vides = sum(1 for r in lignes if all(typer(v) == "vide" for v in r))
        out.append(f"  Lignes 'total/ensemble/burkina' reperees (3 premieres colonnes, echantillon) : {totaux}")
        out.append(f"  Lignes entierement vides (echantillon de {len(lignes)} lignes) : {vides}")
    wb.close()
    return "\n".join(out)


def main(argv=None) -> int:
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Profil de structure d'un .xlsx, sans valeurs chiffrees")
    ap.add_argument("fichier")
    ap.add_argument("--lignes", type=int, default=10, help="nombre de lignes d'en-tete a afficher (defaut 10)")
    ap.add_argument("--sortie", help="ecrire le profil dans ce fichier texte en plus de l'afficher")
    ap.add_argument("--squelette", action="store_true",
                    help="une ligne par ligne non vide (libelles + nombre de nombres) : montre les tableaux empiles")
    ap.add_argument("--feuilles", nargs="*", help="limiter a ces feuilles (ex. PRESCOLAIRE)")
    ap.add_argument("--cap", type=int, default=60, help="lignes max par feuille en mode --squelette (defaut 60)")
    a = ap.parse_args(argv)
    p = Path(a.fichier)
    if not p.is_file() or p.suffix.lower() not in (".xlsx", ".xlsm"):
        print("ERREUR : fournir un fichier .xlsx existant")
        return 1
    texte = profil(p, a.lignes, squelette=a.squelette, feuilles=a.feuilles, cap=a.cap)
    print(texte)
    if a.sortie:
        Path(a.sortie).write_text(texte, encoding="utf-8")
        print(f"\n[profil ecrit dans {a.sortie}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
