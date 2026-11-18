#!/usr/bin/env python3
"""POPULATION INSD PAR PROVINCE (etape 2, role Engineer) : extraction des projections demographiques RGPH 2019 (2020-2035).

Entree : CSV du Data Pack extrait du PDF INSD (format : document;page;ligne;nb_cellules;c1...cN ; une ligne de tableau = une ligne CSV),
         ex. 01_collecte/*insd-rgph2019-vol4-projections-demographiques-2020-2035_v1.csv (ou *nada276*).
         Liste des 45 anciennes provinces : scripts/reference/ancien_decoupage_13_a_valider.csv (province;ancienne_region).
Mise en page reconnue ("province en titre", celle du rapport INSD d'apres le profil) : un tableau par province ; le nom de la
province est une ligne sans chiffre ; les lignes suivantes sont des groupes d'age ; les colonnes sont des annees (en-tete 20xx) x sexes
(Masculin / Feminin / Ensemble), un tableau pouvant s'etendre sur plusieurs pages (une page par groupe d'annees).
6-11 ans : somme des ages 6 a 11 si le tableau donne les ages simples ; sinon interpolation des groupes quinquennaux
           (4/5 des 5-9 ans + 2/5 des 10-14 ans, repartition uniforme dans le groupe), signalee dans la colonne source_6_11.
Modes :
  --mode profil      n'affiche QUE la structure (provinces trouvees ou manquantes, annees, libelles des lignes d'age, nombre de
                     colonnes), JAMAIS de valeur : c'est ce profil qui peut etre partage pour regler l'extraction.
  --mode extraction  ecrit la table longue + les controles dans 02_nettoyage ; la console n'affiche que des compteurs.
Options : --pages 227-511 (pages a lire) ; --ordre annee|sexe (colonnes rangees annee par annee ou par blocs de sexe, si l'en-tete
          ne permet pas de le deduire).
Sorties (mode extraction) :
  <EQ>_02-nettoyage_D2_engineer_population-insd-provinces_v1.csv     province, annee, sexe, groupe_age, population, source_6_11, page, ligne, tableau
  <EQ>_02-nettoyage_D2_engineer_controles-population-insd-provinces_v1.csv
Usage : extraction_population_insd.py PROJECTIONS.csv REFERENCE_PROVINCES.csv DOSSIER_02 [--mode profil|extraction] [--equipe ...]
"""
import argparse, csv, os, re, sys, unicodedata
from collections import Counter, defaultdict

ALIAS = {"KOURITTENGA": "KOURITENGA", "KOMANDJARI": "KOMONDJARI", "KOMONDJOARI": "KOMONDJARI", "BALES": "BALE",
         "BOULKIENDE": "BOULKIEMDE", "LORUM": "LOROUM"}   # orthographes du rapport INSD
RX_ANNEE = re.compile(r"^(20[1-4]\d)$")
RX_MILLIERS = re.compile(r"^\d{1,3}(?:[   .]\d{3})+$")
RX_AGE = re.compile(r"(\d{1,2})\s*(?:-|à|a)\s*(\d{1,2})\s*ans", re.I)
SEXES = {"MASCULIN": "garcons", "HOMMES": "garcons", "HOMME": "garcons", "M": "garcons", "FEMININ": "filles", "FEMMES": "filles",
         "FEMME": "filles", "F": "filles", "ENSEMBLE": "total", "TOTAL": "total", "LES DEUX SEXES": "total", "DEUX SEXES": "total"}


def norm(s):
    t = "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn").upper()
    t = re.sub(r"[^A-Z0-9 ]+", " ", t).strip()
    t = re.sub(r"^(PROVINCE DU|PROVINCE DE LA|PROVINCE DES|PROVINCE DE|PROVINCE D|PROVINCE)\s+", "", t)
    t = re.sub(r"^(LE|LA|LES|L)\s+", "", t)
    return ALIAS.get(t, t)


def nombres(cellule):
    """Nombres d'une cellule : '1 234 567' = un nombre ; '12 34' (pas des milliers) = deux nombres."""
    c = str(cellule).strip().replace(" ", " ").replace(" ", " ")
    if not c:
        return []
    if RX_MILLIERS.match(c):
        return [int(re.sub(r"[ .]", "", c))]
    out = []
    for tok in c.split():
        tok = tok.replace(",", ".")
        if re.fullmatch(r"\d+", tok):
            out.append(int(tok))
        elif re.fullmatch(r"\d+\.\d+", tok):
            out.append(float(tok))
    return out


def age_label(cellule):
    """Libelle d'age normalise ('0-4 ans' -> '0-4', '80 ans et +' -> '80+', 'Total' -> 'ensemble'), sinon ''."""
    c = norm(cellule).replace("ANS", "").replace("ET PLUS", "+").strip()
    if c in ("TOTAL", "ENSEMBLE"):
        return "ensemble"
    m = re.fullmatch(r"(\d{1,2})\s*(?:A|-)?\s*(\d{1,2})?\s*(\+)?", c.replace(" ", " "))
    if not m:
        return ""
    d, f, plus = m.groups()
    return f"{d}+" if plus else (f"{d}-{f}" if f else d)


def lire_lignes(chemin, pages_ok):
    lignes = []
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            try:
                pg = int(r["page"])
            except (KeyError, ValueError):
                continue
            if pages_ok is None or pg in pages_ok:
                lignes.append((pg, r.get("ligne", ""), [r.get(f"c{i}", "") or "" for i in range(1, 60) if f"c{i}" in r]))
    return lignes


def entetes(cells):
    """(annees, sexes) si la ligne est un en-tete, sinon (None, None)."""
    toks = [t for c in cells for t in str(c).split()]
    ans = [int(t) for t in toks if RX_ANNEE.match(t)]
    nums = [t for t in toks if re.fullmatch(r"\d+", t)]
    if len(ans) >= 2 and len(ans) >= 0.6 * len(nums):
        return ans, None
    if len(ans) == 1 and len(nums) == 1 and len([c for c in cells if str(c).strip()]) <= 3:   # tableau d'une seule annee (ex. 2035)
        return ans, None
    sx = [SEXES[norm(c)] for c in cells if norm(c) in SEXES]
    if len(sx) >= 2 and len(sx) >= 0.6 * len([c for c in cells if str(c).strip()]):
        return None, sx
    return None, None


def blocs_province_en_titre(lignes, ref):
    """Format A : blocs (page, province en titre, sous-titre, annees, sexes bruts, lignes d'age).
    Un nouvel en-tete d'annees ou un nouveau sous-titre (ligne de texte sans chiffre, ex. 'Milieu urbain') ouvre un nouveau tableau ;
    l'en-tete de sexe est remis a zero a chaque nouvel en-tete d'annees (un tableau sans sexe = une colonne 'total' par annee)."""
    blocs, cur, prov = [], None, None

    def nouveau(pg, sous, annees=None):
        b = {"page": pg, "province": prov, "sous": sous, "annees": annees or [], "sexes": [], "rangees": []}
        blocs.append(b)
        return b

    for pg, li, cells in lignes:
        if cur is None or cur["page"] != pg:
            cur = nouveau(pg, "")
        ans, sx = entetes(cells)
        if ans:
            cur = nouveau(pg, cur["sous"], ans) if cur["rangees"] else cur
            cur["annees"], cur["sexes"] = ans, []
            continue
        if sx:
            cur["sexes"] = sx; continue
        noms = [norm(c) for c in cells if norm(c) in ref]
        vals_hors_nom = [v for c in cells if norm(c) not in ref for v in nombres(c)]
        if noms and not vals_hors_nom:                      # titre de province : nouveau tableau
            prov = noms[0]
            cur = nouveau(pg, "") if cur["rangees"] else cur
            cur["province"], cur["sous"] = prov, ""
            continue
        non_vides = [c for c in cells if str(c).strip()]
        if not non_vides or cur["province"] is None:
            continue
        lab = age_label(non_vides[0])
        vals = [v for c in non_vides[1:] for v in nombres(c)]
        if lab and vals:
            cur["rangees"].append((lab, li, vals))
        elif not vals_hors_nom and not lab:                 # ligne de texte sans chiffre : sous-titre
            texte = " ".join(str(c).strip() for c in non_vides)[:80]
            if norm(texte).startswith(("GROUPE", "AGE")):     # intitule de la colonne des ages, pas un sous-tableau
                continue
            if cur["rangees"]:
                cur = nouveau(pg, texte, cur["annees"])
            else:
                cur["sous"] = texte
    return [b for b in blocs if b["province"] and b["rangees"] and b["annees"]]


def colonnes(b, ordre):
    """Liste (annee, sexe) de chaque colonne de valeurs du bloc."""
    A, S = b["annees"], b["sexes"] or ["total"]
    ns = len(dict.fromkeys(S)); uniq = list(dict.fromkeys(S))
    if len(S) == len(A) * ns:                          # en-tete des sexes repete sous chaque annee (ou chaque sexe sous les annees)
        if S[:ns] == uniq:                              # M F E M F E ... -> annee par annee
            return [(A[i // ns], S[i]) for i in range(len(S))]
        return [(A[i % len(A)], S[i]) for i in range(len(S))]
    if ordre == "annee":
        return [(A[i // ns], uniq[i % ns]) for i in range(len(A) * ns)]
    return [(A[i % len(A)], uniq[i // len(A)]) for i in range(len(A) * ns)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("projections"); ap.add_argument("reference"); ap.add_argument("dossier02")
    ap.add_argument("--mode", choices=["profil", "extraction"], default="profil")
    ap.add_argument("--equipe", default="Burkina_Novation"); ap.add_argument("--pages", default="")
    ap.add_argument("--ordre", choices=["annee", "sexe"], default="annee")
    ap.add_argument("--sous", default="", help="ne garder que les sous-tableaux dont le sous-titre contient ce texte (voir --mode profil)")
    a = ap.parse_args()

    ref = {}
    with open(a.reference, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            ref[norm(r["province"])] = (r["province"], r.get("ancienne_region", ""))
    pages_ok = None
    if a.pages:
        pages_ok = set()
        for part in a.pages.split(","):
            d, _, fn = part.partition("-")
            pages_ok |= set(range(int(d), int(fn or d) + 1))
    lignes = lire_lignes(a.projections, pages_ok)
    blocs = blocs_province_en_titre(lignes, ref)
    if a.sous:
        blocs = [b for b in blocs if a.sous.lower() in (b["sous"] or "(sans sous-titre)").lower()]

    if a.mode == "profil":
        provs = Counter(b["province"] for b in blocs)
        manq = sorted(ref[k][0] for k in ref if k not in provs)
        ans = sorted({y for b in blocs for y in b["annees"]})
        labs = list(dict.fromkeys(l for b in blocs for l, _, _ in b["rangees"]))
        bons = sum(1 for b in blocs for _, _, v in b["rangees"] if len(v) == len(colonnes(b, a.ordre)))
        tot = sum(len(b["rangees"]) for b in blocs)
        rep = Counter((len(b["annees"]), len(b["sexes"])) for b in blocs)
        print(f"PROFIL (structure seulement, aucune valeur) : {len(lignes)} lignes lues")
        print(f"Format 'province en titre' : {len(blocs)} blocs, {len(provs)}/{len(ref)} provinces, pages {min((b['page'] for b in blocs), default='-')}"
              f"-{max((b['page'] for b in blocs), default='-')}")
        print(f"Provinces absentes : {', '.join(manq) or 'aucune'}")
        print(f"Blocs par province : {dict(Counter(provs.values()))} (nombre de blocs -> nombre de provinces)")
        print(f"Annees couvertes : {ans}")
        print(f"En-tetes (nb annees, nb libelles de sexe) -> nombre de blocs : {dict(rep)}")
        print(f"Libelles des lignes d'age ({len(labs)}) : {labs}")
        sous = Counter(b["sous"] or "(sans sous-titre)" for b in blocs)
        print(f"Sous-tableaux ({len(sous)}) -> nombre de blocs, colonnes par ligne :")
        for st_, n_ in sous.most_common(12):
            bl = [b for b in blocs if (b["sous"] or "(sans sous-titre)") == st_]
            nv = Counter(len(v) for b in bl for _, _, v in b["rangees"]).most_common(2)
            print(f"   {n_:>4} blocs | valeurs par ligne {nv} | colonnes attendues {Counter(len(colonnes(b, a.ordre)) for b in bl).most_common(1)} | {st_}")
        print(f"Lignes d'age dont le nombre de valeurs = annees x sexes : {bons}/{tot}")
        print("6-11 ans : " + ("groupe 6-11 donne par l'INSD" if "6-11" in labs else "ages simples 6 a 11 presents" if all(str(x) in labs for x in range(6, 12)) else
                               "groupes 5-9 et 10-14 presents -> interpolation" if {"5-9", "10-14"} <= set(labs) else "NON CALCULABLE avec ces libelles"))
        print("\nPour extraire : relancer avec --mode extraction (ajouter --pages et --ordre si besoin).")
        return

    # ---------------- extraction (format A) ----------------
    sortie, ctrl = [], []
    for b in blocs:
        cols = colonnes(b, a.ordre)
        nom, region = ref[b["province"]]
        for lab, li, vals in b["rangees"]:
            if len(vals) != len(cols):
                ctrl.append({"type": "nombre_de_valeurs_inattendu", "page": b["page"], "detail": f"{nom} age {lab} : {len(vals)} valeurs pour {len(cols)} colonnes"})
                continue
            for (y, s), v in zip(cols, vals, strict=True):
                sortie.append({"province": nom, "ancienne_region": region, "annee": y, "sexe": s, "groupe_age": lab, "population": v,
                               "source_6_11": "", "page": b["page"], "ligne": li, "tableau": b["sous"] or "(sans sous-titre)"})
    # doublons (meme province, annee, sexe, age) : premier garde
    vus, final = set(), []
    for r in sortie:
        k = (r["province"], r["tableau"], r["annee"], r["sexe"], r["groupe_age"])
        if k in vus:
            ctrl.append({"type": "doublon_garde_premier", "page": r["page"], "detail": " ".join(map(str, k))}); continue
        vus.add(k); final.append(r)
    # 6-11 ans
    idx = defaultdict(dict)
    for r in final:
        idx[(r["province"], r["ancienne_region"], r["annee"], r["sexe"], r["tableau"])][r["groupe_age"]] = r["population"]
    ajout = []
    for (p, rg, y, s, tb), d in idx.items():
        if "6-11" in d:
            v, src = d["6-11"], "groupe 6-11 ans publie par l'INSD"
        elif all(str(x) in d for x in range(6, 12)):
            v, src = sum(d[str(x)] for x in range(6, 12)), "somme des ages 6 a 11"
        elif "5-9" in d and "10-14" in d:
            v, src = round(0.8 * d["5-9"] + 0.4 * d["10-14"]), "interpolation : 4/5 des 5-9 ans + 2/5 des 10-14 ans"
        else:
            continue
        ajout.append({"province": p, "ancienne_region": rg, "annee": y, "sexe": s, "groupe_age": "6-11 ans", "population": v,
                      "source_6_11": src, "page": "", "ligne": "", "tableau": tb})
    final += ajout
    # controles : M + F = Ensemble, couverture des provinces
    for (p, rg, y, s, tb), d in idx.items():
        if s != "total":
            continue
        for lab, tot in d.items():
            g, f_ = idx.get((p, rg, y, "garcons", tb), {}).get(lab), idx.get((p, rg, y, "filles", tb), {}).get(lab)
            if g is not None and f_ is not None and abs(g + f_ - tot) > 1:
                ctrl.append({"type": "M+F<>Ensemble", "page": "", "detail": f"{p} {y} age {lab}"})
    couv = defaultdict(set)
    for r in final:
        if r["groupe_age"] == "6-11 ans":
            couv[(r["annee"], r["sexe"], r["tableau"])].add(r["province"])
    for k, provs in sorted(couv.items()):
        if len(provs) != len(ref):
            ctrl.append({"type": "provinces_manquantes_6_11", "page": "", "detail": f"{k} : {len(provs)}/{len(ref)}"})
    if not final:
        print(f"AUCUNE VALEUR EXTRAITE ({len(lignes)} lignes lues, {len(blocs)} tableaux par province reconnus) : rien n'est ecrit.")
        print("Verifier --pages (les tableaux par province sont indiques par --mode profil) ; les anciennes sorties eventuelles sont conservees.")
        sys.exit(2)
    os.makedirs(a.dossier02, exist_ok=True)
    pre = os.path.join(a.dossier02, f"{a.equipe}_02-nettoyage_D2_engineer_")
    champs = ["province", "ancienne_region", "annee", "sexe", "groupe_age", "population", "source_6_11", "page", "ligne", "tableau"]
    with open(pre + "population-insd-provinces_v1.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=champs, delimiter=";"); w.writeheader(); w.writerows(final)
    with open(pre + "controles-population-insd-provinces_v1.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["type", "page", "detail"], delimiter=";"); w.writeheader(); w.writerows(ctrl)
    print(f"Extraction : {len(final) - len(ajout)} valeurs lues, {len({r['province'] for r in final})}/{len(ref)} provinces, "
          f"annees {sorted({r['annee'] for r in final})}")
    print(f"6-11 ans : {len(ajout)} valeurs calculees ({dict(Counter(r['source_6_11'] for r in ajout))}) ; "
          f"couverture complete ({len(ref)} provinces) pour {sum(1 for v in couv.values() if len(v) == len(ref))}/{len(couv)} annee x sexe")
    print(f"Controles : {dict(Counter(c['type'] for c in ctrl)) or 'aucune anomalie'}")
    print(f"Sorties : {pre}population-insd-provinces_v1.csv et controles")


if __name__ == "__main__":
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    main()
