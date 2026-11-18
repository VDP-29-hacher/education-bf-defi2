#!/usr/bin/env python3
"""EXTRACTION par PROVINCE depuis l'extraction CSV d'un annuaire (ligne par ligne d'un PDF) - Defi 2.

A LANCER PAR L'EQUIPE, EN LOCAL : le script lit des valeurs brutes. La console n'affiche que des COMPTEURS.

Tableaux reconnus (par leur titre) :
  effectifs_province : "HISTORIQUE DES EFFECTIFS PAR PROVINCE"  - 10 annees AAAA/AAAA en colonnes ; region, puis par province
                       un trio Garcons / Filles / Total (le NOM de la province est dans la cellule de la ligne Filles)
  effectifs_region   : "HISTORIQUE DES EFFECTIFS PAR REGION"    - meme disposition, sans provinces (controle croise)
  classes_province   : "HISTORIQUE DES EFFECTIFS ET DES REDOUBLANTS" - region, province, annee, puis G/F/T :
                       14 valeurs = (CP1, CP2, CE1, CE2, CM1, CM2, Total) x (Total, dont R)
  repartition_niveau_sexe : "REPARTITION DES ELEVES ET DES REDOUBLANTS, PAR NIVEAU D'ETUDES ET SEXE", sous-tableaux
                       Public / Prive / Public + prive (dimension statut) et Urbain / Rural (dimension milieu) ;
                       region, province (ligne seule), trio G/F/T (libelle parfois repete), puis "Total Region"
Controles : G + F = T ; somme des provinces = region ; classes = effectifs ; urbain + rural = ensemble ; public + prive = ensemble ;
            somme des classes = Total ; province -> ancienne region (table de reference).
Sorties (DOSSIER_SORTIE) :
  <EQ>_02-nettoyage_D2_engineer_annuaire-<niveau>-<AAAA-AAAA>-provinces_v1.csv            table longue (une ligne = une valeur)
  <EQ>_02-nettoyage_D2_engineer_controles-annuaire-<niveau>-<AAAA-AAAA>-provinces_v1.csv  anomalies et ecarts
Usage : extraction_provinces.py ANNUAIRE.csv REFERENCE_PROVINCES.csv DOSSIER_SORTIE [--equipe Burkina_Novation] [--niveau primaire]
"""
import argparse, csv, io, os, re, sys, unicodedata
from collections import Counter

REGIONS = ["BOUCLE DU MOUHOUN", "CASCADES", "CENTRE", "CENTRE-EST", "CENTRE-NORD", "CENTRE-OUEST", "CENTRE-SUD", "EST",
           "HAUTS-BASSINS", "NORD", "PLATEAU-CENTRAL", "SAHEL", "SUD-OUEST"]
CLASSES = ["CP1", "CP2", "CE1", "CE2", "CM1", "CM2", "Total"]
SEXES = {"GARCONS": "garcons", "FILLES": "filles", "TOTAL": "total"}
RX_ANNEE = re.compile(r"^\s*(\d{4})\s*/\s*(\d{4})\s*$")
RX_ANNEE_SCOL = re.compile(r"Ann[ée]e\s+scolaire\s*(\d{4})\s*-\s*(\d{4})", re.I)
RX_TITRE = re.compile(r"^[IVX]+(\.\s*\d+)*\.?\s+\S")
RX_CHAP = re.compile(r"^([IVX]+)\s*[-.]?\s+([^\d]+)$")                  # chapitre : numeral romain + texte sans chiffre
RX_SOUS = re.compile(r"^[IVX]+\.?\s*\d+\s*\.\s*\d+\.?\s*(.+)$")          # sous-tableau : III.8.4 Urbain
NBSP = "  "
CATEGORIES = {"PUBLIC": ("statut", "public"), "PRIVE": ("statut", "prive"), "PUBLIC PRIVE": ("statut", "public_prive"),
              "URBAIN": ("milieu", "urbain"), "RURAL": ("milieu", "rural"), "URBAIN RURAL": ("milieu", "urbain_rural")}


def sans_accent(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def nrm(s):
    s = re.sub(r"[^A-Z0-9]+", " ", sans_accent(s).upper()).strip()
    return re.sub(r"^(LES|LE|LA|L)\s+", "", s)


ALIAS = {"KOURITTENGA": "KOURITENGA", "KOMANDJARI": "KOMONDJARI"}      # orthographes de l'annuaire -> reference


def cle(s):
    n = nrm(s)
    return ALIAS.get(n, n)


def sexe_of(s):
    """'Garcons' ou 'Garcons Garcons Garcons' (libelle repete par le PDF) -> 'garcons' ; sinon None."""
    toks = sans_accent(s).upper().split()
    return SEXES.get(toks[0]) if toks and all(t == toks[0] for t in toks) else None


def nombre(c):
    t = c.strip().translate({ord(x): None for x in NBSP}).replace(" ", "")
    if t in ("", "-", "–"):
        return None, t == ""
    return (int(t), False) if re.fullmatch(r"\d+", t) else (None, False)


def lire_csv(chemin):
    brut = open(chemin, "rb").read()
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return list(csv.reader(io.StringIO(brut.decode(enc)), delimiter=";"))
        except UnicodeDecodeError:
            continue
    sys.exit("Encodage illisible.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("annuaire"); ap.add_argument("reference"); ap.add_argument("sortie")
    ap.add_argument("--equipe", default="Burkina_Novation"); ap.add_argument("--niveau", default="primaire")
    a = ap.parse_args()
    lignes = lire_csv(a.annuaire)
    ref = {}                                           # province normalisee -> (nom canonique, ancienne region)
    with open(a.reference, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh, delimiter=";"):
            ref[cle(r["province"])] = (r["province"], r["ancienne_region"])
    reg_norm = {nrm(r): r for r in REGIONS}

    sortie, anom = [], []

    def anomalie(type_, ligne, detail):
        anom.append({"type": type_, "ligne_source": ligne, "detail": detail})

    def ajouter(table, num_ligne, reg, prov, geo, sexe, valeurs, dimension="", categorie="", an=None):
        base = dict(table=table, dimension=dimension, categorie=categorie, niveau_geo=geo, region=reg, province=prov, sexe=sexe,
                    ligne_source=num_ligne)
        if table in ("classes_province", "repartition_niveau_sexe"):
            for k, cl in enumerate(CLASSES):
                sortie.append({**base, "annee_debut": an, "annee_fin": an + 1 if an else None, "classe": cl,
                               "effectif": valeurs[2 * k], "dont_redoublants": valeurs[2 * k + 1]})
        else:
            for (d, f), v in zip(annees, valeurs, strict=False):   # une ligne de PDF peut avoir moins de valeurs que d annees
                sortie.append({**base, "annee_debut": d, "annee_fin": f, "classe": "", "effectif": v, "dont_redoublants": ""})

    def lire_valeurs(cells, debut, n, num_ligne):
        vals = []
        for j in range(debut, debut + n):
            v, vide = nombre(cells[j] if j < len(cells) else "")
            if v is None:
                anomalie("valeur_manquante" if vide else "valeur_non_numerique", num_ligne, f"colonne {j}")
            vals.append(v)
        return vals

    mode, chapitre, annees, annee_annuaire = None, None, [], None
    region = province = annee = geo = cat = None
    en_attente, nom_courant = [], None
    libelles_inconnus = Counter()

    def reset():
        nonlocal region, province, annee, geo, cat, en_attente, nom_courant
        region = province = annee = geo = cat = None
        en_attente, nom_courant = [], None

    for i, r in enumerate(lignes[1:], start=2):
        cells = r[:24] + [""] * max(0, 24 - len(r))          # la colonne 24 (remarque_collecte) n'est jamais lue
        c4 = cells[4].strip()
        autres = [c for c in cells[5:24] if c.strip()]
        if annee_annuaire is None and cells[5].strip():
            m = RX_ANNEE_SCOL.search(cells[5])
            if m:
                annee_annuaire = int(m.group(1))
        if c4 and not autres:
            t = sans_accent(c4).upper()
            # ---- sous-tableau (statut / milieu) a l'interieur de la repartition par niveau et sexe ----
            if mode == "repartition_niveau_sexe":
                ms = RX_SOUS.match(c4)
                if ms and CATEGORIES.get(nrm(ms.group(1))):
                    nouvelle = CATEGORIES[nrm(ms.group(1))]
                    if nouvelle != cat:                       # nouveau sous-tableau : on repart d'une region vierge
                        region = province = geo = None; en_attente, nom_courant = [], None
                    cat = nouvelle
                    continue
            # ---- chapitre (ex. "III. EFFECTIFS DES ELEVES", repete en haut de page) ----
            mc = RX_CHAP.match(c4)
            if mc:
                if mc.group(1) != chapitre:
                    chapitre = mc.group(1); mode = None; reset()
                continue
            # ---- titre de tableau ----
            if RX_TITRE.match(c4):
                if "REPARTITION DES ELEVES ET DES REDOUBLANTS" in t and "NIVEAU" in t:
                    nouveau = "repartition_niveau_sexe"
                elif "HISTORIQUE DES EFFECTIFS" in t:
                    # "ET DES REDOUBLANTS" d'abord : ce titre contient aussi "PAR PROVINCE"
                    nouveau = ("classes_province" if (" ET DES R" in t or "REDOUBLANT" in t) else "effectifs_province" if "PAR PROV" in t
                               else "effectifs_region" if "PAR REGI" in t else None)
                else:
                    nouveau = None
                if nouveau != mode:                           # titre repete en haut de page : on garde region/province/annee
                    reset()
                mode = nouveau
                continue
        if mode is None:
            continue
        # ---- en-tetes d'annees (effectifs) ----
        if mode in ("effectifs_province", "effectifs_region") and c4 and (c4.upper().startswith("REGIONS") or sans_accent(c4).upper().startswith("ANNEE SCOLAIRE")):
            ans = [(int(m.group(1)), int(m.group(2))) for j in range(5, 24) if (m := RX_ANNEE.match(cells[j]))]
            if ans:
                if any(f != d + 1 for d, f in ans):
                    anomalie("annee_incoherente", i, "annee de fin != debut + 1")
                annees = ans
            continue
        # ---- ligne a une seule cellule : region, province, annee, total region ----
        if c4 and not autres:
            if RX_ANNEE.match(c4):
                annee = int(RX_ANNEE.match(c4).group(1)); continue
            n4 = nrm(c4)
            if re.fullmatch(r"[ivxIVX]+", c4):             # numero de page romain (v, vi...)
                continue
            if n4 in reg_norm:
                region = reg_norm[n4]
                if mode == "classes_province":             # le nom de la region revient apres ses provinces : ce sont les totaux de region
                    province, geo = "", "region"
                else:
                    province = None; geo = "region" if mode == "effectifs_region" else None
                en_attente, nom_courant = [], None; continue
            if mode in ("classes_province", "repartition_niveau_sexe") and n4 == "TOTAL REGION":
                province, geo = "", "region"; continue
            if re.search(r"[A-Za-z]", c4) and not sexe_of(c4) and (n4.startswith("TOTAL") or "BURKINA" in n4 or "NATIONAL" in n4 or n4 == "ENSEMBLE"):
                region, province, geo = "", "", "national"; en_attente, nom_courant = [], None; continue
            if mode in ("classes_province", "repartition_niveau_sexe") and re.search(r"[A-Za-z]", c4) and not sexe_of(c4):
                if cle(c4) in ref:
                    province, geo = c4, "province"
                else:
                    libelles_inconnus[c4[:40]] += 1           # libelle isole non reconnu : on ne change PAS de province
            continue
        # ---- lignes de donnees : libelle sexe en colonne 4 (valeurs des colonnes 5..) ou en colonne 5 (nom en colonne 4) ----
        l4, l5 = sexe_of(c4), SEXES.get(sans_accent(cells[5]).upper())
        if l4:
            sexe, nom, debut = l4, None, 5
        elif l5 and c4:
            sexe, nom, debut = l5, c4, 6
        else:
            continue
        n = 14 if mode in ("classes_province", "repartition_niveau_sexe") else len(annees)
        if n == 0:
            anomalie("annees_inconnues", i, "ligne de donnees sans en-tete d'annees"); continue
        if any("dont" in c.lower() for c in cells[5:24]):
            continue                                      # en-tete 'Total / dont R'
        vals = lire_valeurs(cells, debut, n, i)
        extra = len([c for c in cells[debut + n:24] if c.strip()])
        if extra:
            anomalie("valeurs_en_trop", i, f"{extra} cellule(s) apres les {n} attendues")
        if region is None:
            anomalie("region_inconnue", i, "ligne de donnees avant toute region"); continue
        if mode == "effectifs_region":
            ajouter(mode, i, region, "", "national" if geo == "national" else "region", sexe, vals)
        elif mode == "effectifs_province":
            if sexe == "garcons":
                en_attente, nom_courant = [(sexe, vals, i)], None
            elif sexe == "filles":
                if nom:
                    nom_courant = nom
                    for s_, v_, l_ in en_attente:
                        ajouter(mode, l_, region, nom_courant, "province", s_, v_)
                    en_attente = []
                    ajouter(mode, i, region, nom_courant, "province", sexe, vals)
                else:
                    anomalie("nom_province_absent", i, "ligne Filles sans nom de province")
            else:
                if nom_courant:
                    ajouter(mode, i, region, nom_courant, "province", sexe, vals)
                else:
                    anomalie("total_sans_province", i, "ligne Total sans province connue")
                nom_courant = None
        elif mode == "classes_province":
            if province is None or annee is None or geo is None:
                anomalie("contexte_incomplet", i, "province ou annee inconnue"); continue
            ajouter(mode, i, region, province, geo, sexe, vals, an=annee)
        else:  # repartition_niveau_sexe
            if cat is None or geo is None or (geo == "province" and not province):
                anomalie("contexte_incomplet", i, "sous-tableau ou province inconnu"); continue
            ajouter(mode, i, region, province or "", geo, sexe, vals, dimension=cat[0], categorie=cat[1], an=annee_annuaire)

    # ---- canonisation des provinces + rattachement a l'ancienne region ----
    vus = set()
    for s in sortie:
        s["province_source"] = s["province"]
        if s["province"]:
            nom, reg_ref = ref.get(cle(s["province"]), (None, None))
            if nom is None:
                if ("hors", s["province"]) not in vus:
                    vus.add(("hors", s["province"]))
                    anomalie("province_hors_reference", s["ligne_source"], s["province"])
            else:
                if nrm(reg_ref) != nrm(s["region"]) and ("reg", nom) not in vus:
                    vus.add(("reg", nom))
                    anomalie("region_differente_reference", s["ligne_source"], f"{s['province']} : annuaire={s['region']} reference={reg_ref}")
                s["province"] = nom
    for lib, n in libelles_inconnus.items():
        anomalie("libelle_isole_ignore", "", f"{lib} (x{n})")

    # ---- controles croises ----
    import pandas as pd
    df = pd.DataFrame(sortie)
    cnt = {}

    def comparer(nom, a_, b_, na, nb):
        j = pd.concat([a_.rename(na), b_.rename(nb)], axis=1).dropna()
        ec = j[j[na] != j[nb]]
        cnt[f"{nom} : ecarts"] = len(ec); cnt[f"{nom} : comparaisons"] = len(j)
        if len(ec) and "sexe" in (a_.index.names or []) and "sexe" in (b_.index.names or []):
            try:                                            # inversion garcons/filles : memes valeurs mais echangees
                ja, jb = a_.unstack("sexe"), b_.unstack("sexe")
                idx = ja.index.intersection(jb.index)
                ja, jb = ja.loc[idx], jb.loc[idx]
                inv = (ja.garcons == jb.filles) & (ja.filles == jb.garcons) & (ja.garcons != jb.garcons)
                cnt[f"{nom} : dont inversions garcons/filles (groupes)"] = int(inv.sum())
                cnt[f"{nom} : groupes en ecart (garcons ou filles)"] = int(((ja.garcons != jb.garcons) | (ja.filles != jb.filles)).sum())
            except Exception:
                pass
            rel = (ec[na] - ec[nb]).abs() / ec[nb].abs().clip(lower=1)
            cnt[f"{nom} : ecart relatif < 1 %"] = int((rel < 0.01).sum())
            cnt[f"{nom} : ecart relatif >= 10 %"] = int((rel >= 0.10).sum())
        for k, row in ec.head(25).iterrows():
            anomalie("ecart_" + nom.replace(" ", "_")[:40], "", f"{k}: {na}={int(row[na])} {nb}={int(row[nb])}")

    if len(df):
        df["effectif"] = pd.to_numeric(df["effectif"], errors="coerce")
        p = df[df.table == "effectifs_province"]
        if len(p):
            pv = p.pivot_table(index=["province", "annee_debut"], columns="sexe", values="effectif", aggfunc="sum")
            if {"garcons", "filles", "total"} <= set(pv.columns):
                comparer("G+F = T (historique province)", (pv.garcons + pv.filles), pv.total, "G+F", "total")
            rg = df[df.table == "effectifs_region"]
            if len(rg):
                comparer("somme provinces = region (historique)", p.groupby(["region", "annee_debut", "sexe"]).effectif.sum(),
                         rg[rg.niveau_geo == "region"].groupby(["region", "annee_debut", "sexe"]).effectif.sum(), "provinces", "region")
                nat = rg[rg.niveau_geo == "national"].groupby(["annee_debut", "sexe"]).effectif.sum()
                if len(nat):
                    comparer("somme regions = national (historique)", rg[rg.niveau_geo == "region"].groupby(["annee_debut", "sexe"]).effectif.sum(),
                             nat, "regions", "national")
                surcharge = rg[rg.niveau_geo == "region"].groupby("region").size()
                for rname, k in surcharge[surcharge > 3 * len(annees)].items():
                    anomalie("region_surchargee", "", f"{rname}: {k} lignes (attendu {3 * len(annees)})")
        cl = df[df.table == "classes_province"]
        clr = cl[cl.niveau_geo == "region"]
        rgr = df[(df.table == "effectifs_region") & (df.niveau_geo == "region")]
        if len(clr) and len(rgr):
            comparer("classes region = effectifs region (historique)", clr[clr.classe == "Total"].groupby(["region", "annee_debut", "sexe"]).effectif.sum(),
                     rgr.groupby(["region", "annee_debut", "sexe"]).effectif.sum(), "classes", "region")
        cl = cl[cl.niveau_geo == "province"]
        if len(cl) and len(p):
            comparer("classes = effectifs (historique)", cl[cl.classe == "Total"].groupby(["province", "annee_debut", "sexe"]).effectif.sum(),
                     p.groupby(["province", "annee_debut", "sexe"]).effectif.sum(), "classes", "effectifs")
        rp = df[df.table == "repartition_niveau_sexe"]
        if len(rp):
            cles_pivot = ["dimension", "categorie", "niveau_geo", "region", "province", "classe"]
            pv = rp.pivot_table(index=cles_pivot, columns="sexe", values="effectif", aggfunc="sum")
            if {"garcons", "filles", "total"} <= set(pv.columns):
                comparer("G+F = T (repartition)", (pv.garcons + pv.filles), pv.total, "G+F", "total")
            prov = rp[(rp.niveau_geo == "province") & (rp.sexe == "total")]
            tr = rp[(rp.niveau_geo == "region") & (rp.sexe == "total")]
            if len(tr):
                comparer("somme provinces = Total Region", prov.groupby(["categorie", "region", "classe"]).effectif.sum(),
                         tr.groupby(["categorie", "region", "classe"]).effectif.sum(), "provinces", "total_region")
            k = ["province", "classe", "sexe"]
            sub = lambda c: rp[(rp.niveau_geo == "province") & (rp.categorie == c)].groupby(k).effectif.sum()
            comparer("urbain + rural = ensemble", sub("urbain") + sub("rural"), sub("public_prive"), "urbain+rural", "public_prive")
            comparer("public + prive = ensemble", sub("public") + sub("prive"), sub("public_prive"), "public+prive", "public_prive")
            cc = rp[(rp.niveau_geo == "province") & (rp.categorie == "public_prive")]
            comparer("somme des classes = Total", cc[cc.classe != "Total"].groupby(["province", "sexe"]).effectif.sum(),
                     cc[cc.classe == "Total"].groupby(["province", "sexe"]).effectif.sum(), "classes", "Total")
            if len(p) and annee_annuaire:
                comparer("repartition = historique (annee de l'annuaire)", cc[cc.classe == "Total"].groupby(["province", "sexe"]).effectif.sum(),
                         p[p.annee_debut == annee_annuaire].groupby(["province", "sexe"]).effectif.sum(), "repartition", "historique")

    suffixe = f"{annee_annuaire}-{annee_annuaire + 1}" if annee_annuaire else "annee-inconnue"
    base = f"{a.equipe}_02-nettoyage_D2_engineer_"
    os.makedirs(a.sortie, exist_ok=True)
    cols = ["table", "dimension", "categorie", "niveau_geo", "region", "province", "province_source", "annee_debut", "annee_fin",
            "classe", "sexe", "effectif", "dont_redoublants", "ligne_source"]
    with open(os.path.join(a.sortie, f"{base}annuaire-{a.niveau}-{suffixe}-provinces_v1.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter=";", extrasaction="ignore"); w.writeheader(); w.writerows(sortie)
    with open(os.path.join(a.sortie, f"{base}controles-annuaire-{a.niveau}-{suffixe}-provinces_v1.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["type", "ligne_source", "detail"], delimiter=";", extrasaction="ignore"); w.writeheader(); w.writerows(anom)

    # ---- console : COMPTEURS SEULEMENT ----
    print(f"=== Extraction par province ({a.niveau}, annuaire {suffixe}) : compteurs ===")
    for t in ("effectifs_province", "effectifs_region", "classes_province", "repartition_niveau_sexe"):
        sub_ = [s for s in sortie if s["table"] == t]
        if sub_:
            print(f"  {t:<24}: {len(sub_):>6} lignes | {len({s['province'] for s in sub_ if s['province']}):>3} provinces | "
                  f"{len({s['region'] for s in sub_ if s['region']}):>2} regions | {len({s['annee_debut'] for s in sub_ if s['annee_debut']})} annees")
        else:
            print(f"  {t:<24}: AUCUNE ligne (tableau non trouve)")
    for t in ("effectifs_province", "classes_province"):
        ans_ = sorted({s["annee_debut"] for s in sortie if s["table"] == t and s["annee_debut"]})
        if ans_:
            print(f"  annees {t} : {ans_}")
    rp_ = [s for s in sortie if s["table"] == "repartition_niveau_sexe"]
    if rp_:
        print("  repartition par sous-tableau :", dict(Counter(f"{s['dimension']}:{s['categorie']}" for s in rp_)))
    for k, v in cnt.items():
        print(f"  controle - {k} : {v}")
    print("  anomalies par type :", dict(Counter(x["type"] for x in anom)) or "aucune")
    # diagnostic : noms et numeros de ligne SEULEMENT, tous les chiffres des details masques en 9
    exemples = {}
    for x in anom:
        lst = exemples.setdefault(x["type"], [])
        if len(lst) < 6:
            lst.append(f"ligne {x['ligne_source']} : " + re.sub(r"\d", "9", str(x["detail"]))[:100])
    if exemples:
        print("  exemples par type (chiffres masques) :")
        for t_, lst in exemples.items():
            print(f"    - {t_} :")
            for e in lst:
                print(f"        {e}")
    print("  nombre de lignes par region (effectifs_region) :",
          dict(Counter(s['region'] or 'NATIONAL' for s in sortie if s['table'] == 'effectifs_region')))
    print(f"Sorties dans {a.sortie}")


if __name__ == "__main__":
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    main()
