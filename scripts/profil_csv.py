#!/usr/bin/env python3
"""Profil de STRUCTURE d'un CSV (extraction d'annuaire) - sans montrer aucune valeur numerique.

Ce que le script affiche : encodage, separateur, nombre de lignes/colonnes, regularite des lignes, type apparent de chaque colonne
(numerique / texte / vide), nombre de valeurs distinctes des colonnes texte, et les N premieres lignes avec TOUS LES CHIFFRES REMPLACES PAR '9'.
Les libelles texte (noms de regions, provinces, intitules) sont visibles : ce sont des etiquettes, pas des mesures.
Usage : python profil_csv.py FICHIER.csv [--lignes 25] [--cherche MOT ...] [--sortie profil.txt]
  --cherche : affiche le numero des lignes dont un libelle contient ce mot (ex. province, milieu, urbain, garcons)
"""
import argparse, csv, io, re, sys
from collections import Counter

NUM = re.compile(r"^[\s\-+]*[\d\s.,%]+$")


def lire(chemin):
    brut = open(chemin, "rb").read()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return brut.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return brut.decode("latin-1", "replace"), "latin-1?"


def masque(s):
    return re.sub(r"\d", "9", s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fichier")
    ap.add_argument("--lignes", type=int, default=25)
    ap.add_argument("--cherche", nargs="*", default=[])
    ap.add_argument("--sortie")
    ap.add_argument("--plage", nargs=2, type=int, metavar=("DEBUT", "FIN"), help="afficher les lignes DEBUT a FIN (numeros 1-based), chiffres masques")
    ap.add_argument("--largeur", type=int, default=40, help="largeur max affichee par cellule (defaut 40 ; 150 pour lire un titre en entier)")
    ap.add_argument("--texte", nargs="*", default=[], help="afficher (max 30) les lignes dont un libelle contient ce mot, chiffres masques")
    a = ap.parse_args()
    texte, enc = lire(a.fichier)
    try:
        dialecte = csv.Sniffer().sniff(texte[:20000], delimiters=";,\t|")
        sep = dialecte.delimiter
    except csv.Error:
        sep = ";"
    lignes = list(csv.reader(io.StringIO(texte), delimiter=sep))
    out = [f"Fichier : {a.fichier.split(chr(92))[-1].split('/')[-1]}", f"Encodage : {enc} | separateur : {sep!r} | lignes : {len(lignes)}"]
    larg = Counter(len(r) for r in lignes)
    out.append("Largeurs de ligne (colonnes: nombre de lignes) : " + ", ".join(f"{k}: {v}" for k, v in sorted(larg.items())))
    ncol = max(larg) if larg else 0
    out.append("\nColonnes (type apparent sur les lignes non vides) :")
    for j in range(ncol):
        vals = [r[j].strip() for r in lignes if j < len(r) and r[j].strip()]
        nn = sum(1 for v in vals if NUM.match(v))
        txt = [v for v in vals if not NUM.match(v)]
        out.append(f"  col {j:>2} : {len(vals):>5} non vides | {nn:>5} numeriques | {len(txt):>5} texte ({len(set(txt))} distincts)")
    out.append(f"\n{a.lignes} premieres lignes (chiffres -> 9) :")
    for i, r in enumerate(lignes[: a.lignes]):
        out.append(f"  {i + 1:>4} | " + " | ".join(masque(c.strip())[:28] for c in r))
    for mot in a.cherche:
        trouves = [i + 1 for i, r in enumerate(lignes) if any(mot.lower() in c.lower() for c in r if not NUM.match(c.strip() or "0"))]
        out.append(f"\nLignes contenant '{mot}' ({len(trouves)}) : {trouves[:40]}{' ...' if len(trouves) > 40 else ''}")
    def court(r):  # cellules non vides de la zone de donnees (col. 3 et suivantes), chiffres -> 9, avec position
        return " | ".join(f"[{j}]{masque(c.strip())[:a.largeur]}" for j, c in enumerate(r) if j >= 3 and c.strip())[:a.largeur * 8]
    if a.plage:
        d, f = a.plage
        out.append(f"\nLignes {d} a {f} (cellules non vides avec leur colonne [n], chiffres -> 9) :")
        for i in range(max(1, d), min(f, len(lignes)) + 1):
            r = lignes[i - 1]
            out.append(f"  {i:>5} p{masque(r[1]) if len(r) > 1 else ''} | {court(r)}")
    for mot in a.texte:
        out.append(f"\nLignes contenant '{mot}' (30 premieres) :")
        n = 0
        for i, r in enumerate(lignes):
            if any(mot.lower() in c.lower() for c in r[3:24] if not NUM.match(c.strip() or "0")):
                out.append(f"  {i + 1:>5} | {court(r)}")
                n += 1
                if n >= 30:
                    break
    res = "\n".join(out)
    print(res)
    if a.sortie:
        with open(a.sortie, "w", encoding="utf-8") as fh:
            fh.write(res + "\n")


if __name__ == "__main__":
    for flux in (sys.stdout,):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    main()
