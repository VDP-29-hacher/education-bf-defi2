#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
COLLECTEUR - Etape 1 du parcours (depot 01_collecte) - Data Challenge Burkina, Education 2026.

Role Data Engineer : rassembler les donnees brutes de PLUSIEURS sources (dossiers locaux, archives zip,
cartes, URL publiques/API) et les ranger de facon tracable, SANS JAMAIS MODIFIER LES BRUTS.

Ce que fait le script
  1. Inventorie les fichiers (CSV, Excel, JSON/GeoJSON, XML, shapefile, PDF, zip...).
  2. Lit uniquement la STRUCTURE (noms de feuilles, en-tetes, nb de lignes) - jamais les valeurs de donnees.
  3. Juge la qualite (illisible, vide, doublon exact, encodage) et la PERTINENCE pour le Defi 2
     (parite filles/garcons, ecart urbain-rural) : UTILISER / A VERIFIER / CARTE / IGNORER.
  4. Copie les bruts dans le depot avec le nom du challenge, verifie l'integrite (sha256), met en lecture seule.
  5. Ecrit le registre des sources, un journal d'execution et un LISEZ-MOI avec la synthese.
  6. Relancable : les colonnes remplies a la main dans le registre (producteur, publication...) sont conservees.

Usage
  python collecte_template.py DOSSIER_BRUT DOSSIER_SORTIE --equipe E12
  python collecte_template.py DOSSIER_BRUT DOSSIER_SORTIE --equipe E12 --urls urls.txt
  python collecte_template.py DOSSIER_BRUT DOSSIER_SORTIE --equipe E12 --copier utiles
  python collecte_template.py DOSSIER_BRUT DOSSIER_SORTIE --equipe E12 --dry-run

urls.txt : une URL http(s) par ligne, 'URL;description' possible, '#' = commentaire.
Nommage des depots : EQUIPE_01-collecte_DEFI_ROLE_description_vN.ext (pas d'espace ni d'accent).
Dependances : Python 3.8+ (standard). Optionnelles : openpyxl (.xlsx), pandas+xlrd (.xls), pypdf (pages PDF).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import logging
import re
import shutil
import stat
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

VERSION = "2.0"

# --------------------------------------------------------------------------------------------------
# CONFIGURATION (a ajuster si besoin)
# --------------------------------------------------------------------------------------------------
EXTENSIONS = {".csv", ".xlsx", ".xlsm", ".xls", ".json", ".geojson", ".xml", ".pdf", ".zip", ".txt",
              ".shp", ".dbf", ".shx", ".prj", ".cpg"}
COMPAGNONS = {".dbf", ".shx", ".prj", ".cpg"}           # fichiers d'un shapefile : jamais dedoublonnes
DEFAUT_TELECHARGE = {"text/csv": ".csv", "application/json": ".json", "application/geo+json": ".geojson",
                     "application/pdf": ".pdf", "application/zip": ".zip", "text/xml": ".xml",
                     "application/xml": ".xml", "application/vnd.ms-excel": ".xls",
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx"}
MAX_TELECHARGEMENT = 300 * 1024 * 1024                   # octets par URL
MAX_ZIP_FICHIERS, MAX_ZIP_OCTETS = 5000, 2 * 1024 ** 3   # garde-fous contre les archives piegees
MAX_FEUILLES, MAX_JSON = 30, 50 * 1024 * 1024
TIMEOUT_HTTP, ESSAIS_HTTP = 30, 3
UA = "collecte-challenge/2.0"

# Criteres de pertinence Defi 2 (parite F/G, urbain-rural). Appliques au nom + feuilles + en-tetes.
CRITERES = {
    "sexe": r"\b(fille|filles|garcon|garcons|feminin\w*|masculin\w*|sexe|genre|parite|femme|femmes|homme|hommes)\b",
    "geo": r"\b(province|provinces|region|regions|commune|communes|departement|departements|localite|dren|ceb)\b",
    "temps": r"\b(annee|annees|19[89]\d|20[0-3]\d)\b",
    "milieu": r"\b(urbain|urbaine|rural|rurale|milieu|zone)\b",
    "education": r"\b(eleve|eleves|effectif|effectifs|ecole|ecoles|scolaire|scolarisation|primaire|prescolaire|"
                 r"inscrit|inscrits|enseignant|enseignants|alphabetisation|education|abandon)\b",
    "population": r"\b(population|habitant|habitants|recensement|rgph)\b",
}
CARTE_RX = r"(limite|admin|boundar|shape|contour|osm|openstreetmap|geojson)"
# Themes hors coeur du Defi 2 : facteurs explicatifs possibles, pas des sources principales.
CONTEXTE_RX = r"\b(pdi|deplace\w*|conasur|refugie\w*|humanitaire\w*|securite|conflit\w*|paludisme|nutrition|vaccin\w*|sante)\b"

CHAMPS_MANUELS = ("producteur_source", "publication", "annee_ou_periode", "licence_remarques",
                  "decision_defi2", "motif_decision")
COLONNES_REGISTRE = [
    "fichier_depose", "nom_origine", "origine", "mode", "taille_octets", "sha256", "doublon_exact_de",
    "date_collecte", "score_defi2", "recommandation", "criteres_trouves", "annees_detectees", "qualite",
    "encodage", "separateur", "nb_lignes", "nb_colonnes", "feuilles", "colonnes",
    *CHAMPS_MANUELS, "remarques_collecte"]

log = logging.getLogger("collecte")


# --------------------------------------------------------------------------------------------------
# OUTILS
# --------------------------------------------------------------------------------------------------
def slug(nom: str) -> str:
    s = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "fichier"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def _numerique(s: str) -> bool:
    return bool(re.fullmatch(r"[-+]?[\d\s.,%]+", s))


def normtxt(s) -> str:
    t = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[_\-./\\]+", " ", t)).strip()


RX_ANNEE_SCOL = re.compile(r"(?<!\d)(19[89]\d|20[0-3]\d)\s*[-/_]\s*(19[89]\d|20[0-3]\d)(?!\d)")
RX_ANNEE = re.compile(r"(?<!\d)(19[89]\d|20[0-3]\d)(?!\d)")
RX_COL_ANNEE = re.compile(r"^(annee|year|millesime|rentree|periode|exercice)\b")


def annees_depuis_texte(t) -> set:
    """Annees citees dans un texte. 'Annee scolaire' 2016-2017 -> 2016 (l'annee scolaire n'est pas civile)."""
    out = set()

    def paire(m):
        a, b = int(m.group(1)), int(m.group(2))
        if b == a + 1:
            out.add(a)
            return " "
        return m.group(0)

    reste = RX_ANNEE_SCOL.sub(paire, str(t))
    out |= {int(y) for y in RX_ANNEE.findall(reste)}
    return out


def compacter(annees) -> str:
    ys = sorted(annees)
    morceaux, i = [], 0
    while i < len(ys):
        j = i
        while j + 1 < len(ys) and ys[j + 1] == ys[j] + 1:
            j += 1
        morceaux.append(str(ys[i]) if i == j else f"{ys[i]}-{ys[j]}")
        i = j + 1
    return ",".join(morceaux)


def meilleure_ligne(lignes):
    """(indice, [(col, texte)]) de la ligne la plus 'texte' = en-tete probable (les classeurs ont des titres)."""
    best_i, best = -1, []
    for i, ligne in enumerate(lignes):
        cells = [(j, str(c).strip()) for j, c in enumerate(ligne)
                 if c is not None and c == c and str(c).strip() and not _numerique(str(c).strip())]
        if len(cells) > len(best):
            best_i, best = i, cells
    return best_i, best


def entete(lignes) -> list:
    return [t for _, t in meilleure_ligne(lignes)[1]]


def annees_feuille(haut, hidx, cells, reste, plafond=50000) -> set:
    """Annees d'une feuille : zone titre+en-tete, puis valeurs de la/les colonne(s) 'annee' (jamais d'autres valeurs)."""
    annees = set()
    for ligne in haut[:max(hidx, 0) + 2]:
        for c in ligne:
            if c is not None and c == c:
                annees |= annees_depuis_texte(c)
    idx = [j for j, t in cells if RX_COL_ANNEE.match(normtxt(t))]
    if idx:
        vus = {}
        suite = itertools.chain(haut[hidx + 1:], itertools.islice(reste, plafond))
        for ligne in suite:
            for j in idx:
                if j < len(ligne) and ligne[j] is not None and ligne[j] == ligne[j]:
                    v = str(ligne[j])
                    if v not in vus:
                        vus[v] = annees_depuis_texte(v)
                    annees |= vus[v]
    return annees


def vide_info() -> dict:
    return {"encodage": "", "separateur": "", "nb_lignes": "", "nb_colonnes": "", "feuilles": "",
            "colonnes": "", "_texte": "", "_annees": set(), "qualite": "NON_ANALYSE", "remarque": ""}


# --------------------------------------------------------------------------------------------------
# APERCUS DE STRUCTURE (aucune valeur de donnees n'est conservee)
# --------------------------------------------------------------------------------------------------
def apercu_csv(p: Path) -> dict:
    info = vide_info()
    try:
        csv.field_size_limit(sys.maxsize)
    except OverflowError:
        csv.field_size_limit(2 ** 31 - 1)
    derniere = None
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(p, "r", encoding=enc, newline="") as f:
                debut = f.read(65536)
                f.seek(0)
                try:
                    sep = csv.Sniffer().sniff(debut, delimiters=";,\t|").delimiter
                except csv.Error:
                    sep = max(";,\t|", key=debut.count)
                cols, n, vides, idx_an, annees, cache = None, 0, 0, [], set(), {}
                for ligne in csv.reader(f, delimiter=sep):
                    if cols is None:
                        if any(c.strip() for c in ligne):
                            cols = [c.strip() for c in ligne]
                            idx_an = [j for j, c in enumerate(cols) if RX_COL_ANNEE.match(normtxt(c))]
                        continue
                    if any(c.strip() for c in ligne):
                        n += 1
                        for j in idx_an:               # seulement la colonne 'annee' : on ne retient que des annees
                            if j < len(ligne) and ligne[j] not in cache:
                                cache[ligne[j]] = annees_depuis_texte(ligne[j])
                            if j < len(ligne):
                                annees |= cache[ligne[j]]
                    else:
                        vides += 1
            info.update(encodage=enc, separateur=sep, nb_lignes=n, nb_colonnes=len(cols or []),
                        colonnes=" | ".join(cols or []), _texte=" ".join(cols or []),
                        _annees=annees, qualite="VIDE" if not cols or n == 0 else "OK",
                        remarque=f"{vides} ligne(s) vide(s)" if vides else "")
            return info
        except UnicodeDecodeError as e:
            derniere = e
    info.update(qualite="ILLISIBLE", remarque=f"encodage non reconnu : {derniere}")
    return info


def apercu_excel(p: Path) -> dict:
    info = vide_info()
    feuilles = []                                        # (titre, nb_lignes, nb_colonnes, en-tete)
    erreurs = []
    annees = set()
    if p.suffix.lower() in (".xlsx", ".xlsm"):
        try:
            from openpyxl import load_workbook
            wb = load_workbook(p, read_only=True, data_only=True)
            try:
                for ws in wb.worksheets[:MAX_FEUILLES]:
                    it = ws.iter_rows(values_only=True)
                    haut = list(itertools.islice(it, 15))
                    hidx, cells = meilleure_ligne(haut)
                    feuilles.append((ws.title, ws.max_row, ws.max_column, [t for _, t in cells]))
                    annees |= annees_feuille(haut, hidx, cells, it)
            finally:
                wb.close()
        except ImportError:
            erreurs.append("openpyxl absent")
        except Exception as e:                           # classeur corrompu, protege, etc.
            erreurs.append(f"openpyxl : {e}")
            feuilles.clear()
            annees.clear()
    if not feuilles:
        try:
            import pandas as pd
            xl = pd.ExcelFile(p)
            for nom in xl.sheet_names[:MAX_FEUILLES]:
                lignes_df = xl.parse(nom, header=None, nrows=50000).values.tolist()
                haut = lignes_df[:15]
                hidx, cells = meilleure_ligne(haut)
                feuilles.append((nom, None, len(haut[0]) if haut else 0, [t for _, t in cells]))
                annees |= annees_feuille(haut, hidx, cells, iter(lignes_df[15:]))
        except Exception as e:
            erreurs.append(f"pandas : {e}")
    if not feuilles:
        info.update(qualite="ILLISIBLE", remarque=" ; ".join(erreurs)[:300])
        return info
    morceaux = [f"[{t}] " + " | ".join(h[:25]) for t, _, _, h in feuilles[:6]]
    info.update(feuilles=" | ".join(str(f[0]) for f in feuilles),
                nb_lignes=feuilles[0][1] if feuilles[0][1] else "", nb_colonnes=feuilles[0][2] or "",
                colonnes="; ".join(morceaux)[:1500],
                _texte=" ".join(str(f[0]) for f in feuilles) + " " + " ".join(" ".join(f[3]) for f in feuilles),
                _annees=annees, qualite="OK" if any(f[3] for f in feuilles) else "A_VERIFIER_ENTETE",
                remarque=f"{len(feuilles)} feuille(s) ; en-tete detecte parmi les 15 premieres lignes")
    return info


def apercu_json(p: Path) -> dict:
    info = vide_info()
    if p.stat().st_size > MAX_JSON:
        info.update(remarque="JSON volumineux : structure non lue")
        return info
    try:
        with open(p, "r", encoding="utf-8-sig") as f:
            d = json.load(f)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        info.update(qualite="ILLISIBLE", remarque=f"JSON invalide : {e}")
        return info
    cles, n = [], ""
    if isinstance(d, dict) and isinstance(d.get("features"), list):          # GeoJSON
        feats = d["features"]
        n = len(feats)
        for ft in feats[:20]:
            for k in (ft.get("properties") or {}):
                if k not in cles:
                    cles.append(k)
        info["remarque"] = "GeoJSON"
    elif isinstance(d, list):
        n = len(d)
        for el in d[:20]:
            if isinstance(el, dict):
                cles += [k for k in el if k not in cles]
    elif isinstance(d, dict):
        cles = list(d)[:40]
        n = len(d)
    info.update(nb_lignes=n, nb_colonnes=len(cles), colonnes=" | ".join(map(str, cles)),
                _texte=" ".join(map(str, cles)), qualite="OK" if n != 0 else "VIDE")
    return info


def apercu_xml(p: Path) -> dict:
    """Pas de parsing XML complet (evite les entites piegees) : on releve les premieres balises."""
    info = vide_info()
    try:
        debut = p.read_bytes()[:65536].decode("utf-8", errors="replace")
    except OSError as e:
        info.update(qualite="ILLISIBLE", remarque=str(e))
        return info
    balises = []
    for b in re.findall(r"<([A-Za-z_][\w:.\-]*)", debut):
        if b not in balises:
            balises.append(b)
    info.update(colonnes=" | ".join(balises[:40]), _texte=" ".join(balises[:40]),
                qualite="OK" if balises else "A_VERIFIER_ENTETE", remarque="balises des 64 premiers Ko")
    return info


def champs_dbf(p: Path):
    with open(p, "rb") as f:
        h = f.read(32)
        nb = int.from_bytes(h[4:8], "little")
        champs = []
        while True:
            d = f.read(32)
            if len(d) < 32 or d[0] == 0x0D:
                break
            champs.append(d[:11].split(b"\x00")[0].decode("latin-1"))
    return nb, champs


def apercu_carte(p: Path) -> dict:
    info = vide_info()
    dbf = p if p.suffix.lower() == ".dbf" else p.with_suffix(".dbf")
    manquants = [e for e in (".shx", ".dbf", ".prj") if not p.with_suffix(e).exists()] if p.suffix.lower() == ".shp" else []
    if dbf.exists():
        try:
            nb, champs = champs_dbf(dbf)
            info.update(nb_lignes=nb, nb_colonnes=len(champs), colonnes=" | ".join(champs), _texte=" ".join(champs),
                        qualite="OK")
        except Exception as e:
            info.update(qualite="ILLISIBLE", remarque=f"dbf illisible : {e}")
    if manquants:
        info["remarque"] = ("shapefile incomplet, manque : " + ", ".join(manquants)).strip()
    return info


def apercu_pdf(p: Path) -> dict:
    info = vide_info()
    try:
        from pypdf import PdfReader
        info["remarque"] = f"{len(PdfReader(str(p)).pages)} page(s) ; contenu non analyse"
    except Exception:
        info["remarque"] = "PDF : contenu non analyse (installer pypdf pour le nombre de pages)"
    return info


def apercu_zip(p: Path) -> dict:
    info = vide_info()
    try:
        with zipfile.ZipFile(p) as z:
            noms = [i.filename for i in z.infolist() if not i.is_dir()]
        info.update(nb_lignes=len(noms), colonnes=" | ".join(noms[:30]), _texte=" ".join(noms[:200]),
                    qualite="OK", remarque=f"{len(noms)} fichier(s) dans l'archive")
    except Exception as e:
        info.update(qualite="ILLISIBLE", remarque=f"zip invalide : {e}")
    return info


def apercu(p: Path) -> dict:
    ext = p.suffix.lower()
    try:
        if ext == ".csv":
            return apercu_csv(p)
        if ext in (".xlsx", ".xlsm", ".xls"):
            return apercu_excel(p)
        if ext in (".json", ".geojson"):
            return apercu_json(p)
        if ext == ".xml":
            return apercu_xml(p)
        if ext in (".shp", ".dbf"):
            return apercu_carte(p)
        if ext == ".pdf":
            return apercu_pdf(p)
        if ext == ".zip":
            return apercu_zip(p)
    except Exception as e:          # un fichier problematique ne doit jamais arreter la collecte
        info = vide_info()
        info.update(qualite="ILLISIBLE", remarque=f"erreur d'analyse : {e}"[:300])
        return info
    return vide_info()


# --------------------------------------------------------------------------------------------------
# JUGEMENT DE PERTINENCE (Defi 2)
# --------------------------------------------------------------------------------------------------
def evaluer(nom: str, ext: str, texte: str, qualite: str):
    t = unicodedata.normalize("NFKD", f"{nom} {texte}").encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[_\-./\\]+", " ", t)
    trouves = [k for k, rx in CRITERES.items() if re.search(rx, t)]
    annees = sorted(set(re.findall(r"\b(19[89]\d|20[0-3]\d)\b", t)))
    plage = f"{annees[0]}-{annees[-1]}" if len(annees) > 1 else (annees[0] if annees else "")
    carte = ext in (".shp", ".dbf", ".shx", ".prj", ".cpg", ".geojson") or (
        ext in (".json", ".zip") and re.search(CARTE_RX, t))
    if qualite in ("ILLISIBLE", "VIDE"):
        reco = f"A VERIFIER A LA MAIN ({qualite.lower()})"
    elif carte:
        reco = "CARTE (limites / fonds de carte)"
    elif ext in (".pdf", ".txt", ".zip"):
        reco = "A VERIFIER A LA MAIN (contenu non lisible par le script)"
    elif re.search(CONTEXTE_RX, t) and "education" not in trouves:
        reco = "CONTEXTE (facteur explicatif possible ; pas une source principale du defi 2)"
    elif "sexe" in trouves and "geo" in trouves and ({"education", "population"} & set(trouves)):
        if "milieu" in trouves:
            reco = "UTILISER (priorite : contient aussi le milieu urbain/rural)"
        else:
            reco = "UTILISER (sexe + lieu + education/population)"
    elif "sexe" in trouves and "geo" in trouves and "temps" in trouves:
        reco = "A VERIFIER (sexe + lieu + annee, theme non confirme)"
    elif len(trouves) >= 2:
        reco = "A VERIFIER (pertinence partielle)"
    else:
        reco = "IGNORER (hors sujet probable)"
    return len(trouves), trouves, plage, reco


# --------------------------------------------------------------------------------------------------
# ACQUISITION : telechargement, zip, parcours local
# --------------------------------------------------------------------------------------------------
def nom_depuis_reponse(url: str, rep) -> str:
    cd = rep.headers.get("Content-Disposition", "")
    m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", cd, re.I)
    nom = urllib.parse.unquote(m.group(1)) if m else Path(urllib.parse.urlparse(url).path).name
    if not nom:
        nom = slug(urllib.parse.urlparse(url).netloc)
    if Path(nom).suffix.lower() not in EXTENSIONS:
        ctype = rep.headers.get_content_type() if hasattr(rep.headers, "get_content_type") else ""
        nom += DEFAUT_TELECHARGE.get(ctype, ".bin")
    return nom


def telecharger(fichier_urls: Path, dossier: Path) -> list:
    sources = []
    for brut in fichier_urls.read_text(encoding="utf-8-sig").splitlines():
        ligne = brut.strip()
        if not ligne or ligne.startswith("#"):
            continue
        url, _, desc = (x.strip() for x in ligne.partition(";"))
        if urllib.parse.urlparse(url).scheme not in ("http", "https"):
            log.error("URL ignoree (schema non autorise) : %s", url)
            continue
        for essai in range(1, ESSAIS_HTTP + 1):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=TIMEOUT_HTTP) as rep:
                    taille = int(rep.headers.get("Content-Length") or 0)
                    if taille > MAX_TELECHARGEMENT:
                        raise ValueError(f"fichier trop volumineux ({taille} octets)")
                    nom_dl = nom_depuis_reponse(url, rep)
                    cible = dossier / f"dl{len(sources):03d}_{slug(Path(nom_dl).stem)}{Path(nom_dl).suffix.lower()}"
                    total = 0
                    with open(cible, "wb") as f:
                        for bloc in iter(lambda: rep.read(1 << 20), b""):
                            total += len(bloc)
                            if total > MAX_TELECHARGEMENT:
                                raise ValueError("depassement de la taille maximale")
                            f.write(bloc)
                sources.append({"path": cible, "origine": url, "mode": "telecharge", "nom": nom_dl,
                                "desc": desc, "http": getattr(rep, "status", "")})
                log.info("TELECHARGE %s (%d octets)", url, total)
                break
            except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError, TimeoutError) as e:
                log.warning("Essai %d/%d echoue pour %s : %s", essai, ESSAIS_HTTP, url, e)
                permanent = isinstance(e, ValueError) or (
                    isinstance(e, urllib.error.HTTPError) and 400 <= e.code < 500 and e.code not in (408, 429))
                if permanent:                      # 404, 403... : inutile de reessayer
                    log.error("Erreur permanente, abandon : %s", url)
                    break
                time.sleep(1.5 * essai)
        else:
            log.error("ECHEC definitif : %s", url)
    return sources


def extraire_zip(zpath: Path, dest: Path) -> list:
    """Extraction securisee : pas de chemin hors dossier (zip-slip), limites de nombre et de taille."""
    sorties = []
    dest = dest.resolve()
    try:
        with zipfile.ZipFile(zpath) as z:
            infos = [i for i in z.infolist() if not i.is_dir()]
            if len(infos) > MAX_ZIP_FICHIERS or sum(i.file_size for i in infos) > MAX_ZIP_OCTETS:
                log.warning("Archive %s trop grosse : non extraite", zpath.name)
                return sorties
            for i in infos:
                ext = Path(i.filename).suffix.lower()
                cible = (dest / i.filename).resolve()
                if dest not in cible.parents:
                    log.warning("Chemin suspect ignore dans %s : %s", zpath.name, i.filename)
                    continue
                if ext not in EXTENSIONS or ext == ".zip":
                    continue
                cible.parent.mkdir(parents=True, exist_ok=True)
                with z.open(i) as src, open(cible, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                sorties.append({"path": cible, "origine": f"zip:{zpath.name}::{i.filename}", "mode": "zip",
                                "nom": Path(i.filename).name, "desc": "", "http": ""})
    except Exception as e:
        log.warning("Archive %s illisible : %s", zpath.name, e)
    return sorties


def parcourir_local(brut: Path, exclus: list) -> list:
    sources = []
    for p in sorted(brut.rglob("*")):
        if not p.is_file() or p.name.startswith(("~$", ".")) or p.suffix.lower() not in EXTENSIONS:
            continue
        if any(e == p.resolve() or e in p.resolve().parents for e in exclus):
            continue
        sources.append({"path": p, "origine": str(p), "mode": "local", "nom": p.name, "desc": "", "http": ""})
    return sources


# --------------------------------------------------------------------------------------------------
# DEPOT : copie verifiee, lecture seule
# --------------------------------------------------------------------------------------------------
def copier_verifie(src: Path, sortie: Path, base: str, ext: str, h: str):
    """Copie en bruts/ avec nom versionne. Meme contenu deja la -> rien ; contenu different -> v+1."""
    for n in range(1, 100):
        dest = sortie / f"{base}_v{n}{ext}"
        if not dest.exists():
            shutil.copy2(src, dest)
            if sha256(dest) != h:
                dest.unlink()
                raise IOError("controle d'integrite sha256 echoue apres copie")
            dest.chmod(stat.S_IREAD)
            return dest.name, "copie"
        if sha256(dest) == h:
            return dest.name, "deja_present"
    raise IOError("trop de versions pour ce nom")


def charger_registre_existant(chemin: Path) -> dict:
    """Retient les colonnes saisies a la main, par sha256, pour ne pas les perdre a la relance."""
    manuels = {}
    if chemin.exists():
        with open(chemin, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f, delimiter=";"):
                if r.get("sha256") and any(r.get(c) for c in CHAMPS_MANUELS):
                    # cle = (empreinte, nom) : des fichiers compagnons de contenu identique (.prj) restent distincts
                    manuels[(r["sha256"], r.get("nom_origine", ""))] = {c: r.get(c, "") for c in CHAMPS_MANUELS}
    return manuels


# --------------------------------------------------------------------------------------------------
# PROGRAMME PRINCIPAL
# --------------------------------------------------------------------------------------------------
def construire_couverture(lignes, amin: int, amax: int) -> dict:
    """Matrice fichier x annee (X = annee detectee) + annees MANQUANTES sur la fenetre amin..amax."""
    fen = list(range(amin, amax + 1))
    utiles = [r for r in lignes if r["recommandation"].startswith("UTILISER")]
    possibles = [r for r in lignes if r["recommandation"].startswith(("UTILISER", "A VERIFIER ("))]
    entetes = ["fichier", "recommandation", *map(str, fen), "hors_fenetre"]

    def ligne_x(r):
        ys = r.get("_annees_set", set())
        return [r["fichier_depose"] or r["nom_origine"], r["recommandation"].split(" (")[0],
                *["X" if y in ys else "" for y in fen], compacter(y for y in ys if y not in fen)]

    def union(rs):
        return set().union(*[r.get("_annees_set", set()) for r in rs]) & set(fen)

    groupes = [("UNION (UTILISER)", utiles),
               ("UNION (UTILISER + education = annuaires scolaires)",
                [r for r in utiles if "education" in r["criteres_trouves"]]),
               ("UNION (UTILISER + A VERIFIER)", possibles)]
    rows = [ligne_x(r) for r in possibles]
    resumes = []
    for titre, rs in groupes:
        u = union(rs)
        rows.append([titre, f"{len(rs)} fichier(s)", *["X" if y in u else "" for y in fen], ""])
        rows.append([f"MANQUANTES ({titre[7:-1]})", "", *["MANQUE" if y not in u else "" for y in fen], ""])
        resumes.append((titre, rs, u))
    titre, rs, u = resumes[1] if resumes[1][1] else resumes[0]
    if not rs:
        resume = f"COUVERTURE {amin}-{amax} : aucun fichier UTILISER, couverture non evaluable"
    else:
        manque = [y for y in fen if y not in u]
        resume = (f"COUVERTURE {amin}-{amax} [{titre[7:-1]}] : presentes {compacter(u) or 'aucune'} ; "
                  f"MANQUANTES {compacter(manque) or 'aucune'}")
    return {"entetes": entetes, "rows": rows, "resume": resume}


def configurer_logs(fichier_log: Path | None):
    log.setLevel(logging.INFO)
    log.handlers.clear()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    log.addHandler(sh)
    if fichier_log:
        fh = logging.FileHandler(fichier_log, encoding="utf-8")
        fh.setFormatter(fmt)
        log.addHandler(fh)


def main(argv=None) -> int:
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Collecteur Data Challenge Burkina - etape 1 (01_collecte)")
    ap.add_argument("brut", help="dossier des donnees brutes (lecture seule)")
    ap.add_argument("sortie", help="dossier du depot 01_collecte")
    ap.add_argument("--equipe", required=True, help="numero d'equipe, ex. E12")
    ap.add_argument("--defi", default="D2")
    ap.add_argument("--role", default="engineer")
    ap.add_argument("--urls", help="fichier texte d'URL publiques a telecharger")
    ap.add_argument("--copier", choices=["tout", "utiles"], default="tout",
                    help="tout (defaut) ou utiles = UTILISER / CARTE / A VERIFIER seulement")
    ap.add_argument("--sans-zip", action="store_true", help="ne pas extraire les archives zip")
    ap.add_argument("--annee-min", type=int, default=2016, help="debut de la fenetre de couverture (defaut 2016)")
    ap.add_argument("--annee-max", type=int, default=2025, help="fin de la fenetre de couverture (defaut 2025)")
    ap.add_argument("--dry-run", action="store_true", help="analyse sans rien ecrire dans la sortie")
    a = ap.parse_args(argv)

    if not re.fullmatch(r"[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*", a.equipe):
        ap.error("--equipe : lettres/chiffres (tiret bas autorise), sans espace ni accent (ex. Burkina_Novation)")
    brut, sortie = Path(a.brut), Path(a.sortie)
    if not brut.is_dir() and not a.urls:
        ap.error(f"dossier brut introuvable : {brut}")
    prefixe = f"{a.equipe}_01-collecte_{a.defi}_{a.role}"

    if not a.dry_run:
        sortie.mkdir(parents=True, exist_ok=True)
    configurer_logs(None if a.dry_run else sortie / f"{prefixe}_journal-collecte_v1.log")
    log.info("Collecteur v%s - equipe %s, defi %s%s", VERSION, a.equipe, a.defi, " [DRY-RUN]" if a.dry_run else "")

    tmp = Path(tempfile.mkdtemp(prefix="collecte_"))
    erreurs = 0
    try:
        # --- 1. ACQUISITION -------------------------------------------------------------------
        sources = parcourir_local(brut, [sortie.resolve()]) if brut.is_dir() else []
        if a.urls:
            u = Path(a.urls)
            if u.is_file():
                (tmp / "dl").mkdir()
                sources += telecharger(u, tmp / "dl")
            else:
                log.error("fichier d'URL introuvable : %s", u)
                erreurs += 1
        if not a.sans_zip:
            for s in [x for x in sources if x["path"].suffix.lower() == ".zip"]:
                (tmp / "zip").mkdir(exist_ok=True)
                sources += extraire_zip(s["path"], tmp / "zip" / slug(s["path"].stem))
        if not sources:
            log.error("Aucun fichier a collecter (extensions retenues : %s)", ", ".join(sorted(EXTENSIONS)))
            return 1
        log.info("%d fichier(s) a inventorier", len(sources))

        # --- 2. INVENTAIRE, JUGEMENT, DEPOT ------------------------------------------------------
        reg_chemin = sortie / f"{prefixe}_registre-sources_v1.csv"
        manuels = charger_registre_existant(reg_chemin)
        lignes, vus, noms_run = [], {}, {}
        for s in sources:
            p, ext = s["path"], s["path"].suffix.lower()
            ligne = {c: "" for c in COLONNES_REGISTRE}
            ligne.update(nom_origine=s["nom"], origine=s["origine"], mode=s["mode"],
                         date_collecte=datetime.now().strftime("%Y-%m-%d"))
            try:
                h, taille = sha256(p), p.stat().st_size
            except OSError as e:
                log.error("Lecture impossible %s : %s", s["origine"], e)
                ligne.update(qualite="ERREUR_LECTURE", recommandation="A VERIFIER A LA MAIN (lecture impossible)",
                             remarques_collecte=str(e)[:200])
                lignes.append(ligne)
                erreurs += 1
                continue
            ligne.update(sha256=h, taille_octets=taille)
            doublon = "" if ext in COMPAGNONS else vus.get(h, "")
            if ext not in COMPAGNONS:
                vus.setdefault(h, s["nom"])
            remarques = [s["desc"]] if s["desc"] else []

            if doublon:
                ligne.update(doublon_exact_de=doublon, qualite="DOUBLON", score_defi2=0,
                             recommandation="DOUBLON (deja inventorie)")
                lignes.append(ligne)
                continue

            info = apercu(p)
            score, crit, _plage, reco = evaluer(s["nom"], ext, info["_texte"], info["qualite"])
            annees_f = set(info["_annees"]) | annees_depuis_texte(f'{s["nom"]} {info["_texte"]}')
            ligne["_annees_set"] = annees_f
            ligne.update(score_defi2=score, recommandation=reco, criteres_trouves=",".join(crit),
                         annees_detectees=compacter(annees_f), qualite=info["qualite"], encodage=info["encodage"],
                         separateur=info["separateur"], nb_lignes=info["nb_lignes"],
                         nb_colonnes=info["nb_colonnes"], feuilles=info["feuilles"], colonnes=info["colonnes"])
            if info["remarque"]:
                remarques.append(info["remarque"])

            copier = (not a.dry_run) and (
                a.copier == "tout" or reco.startswith(("UTILISER", "CARTE", "A VERIFIER", "CONTEXTE")))
            if copier:
                cle = (slug(Path(s["nom"]).stem), ext)
                nom_slug = cle[0]
                if s["mode"] == "zip":
                    nom_slug = slug(s["origine"].split("::")[0][4:].rsplit(".", 1)[0] + "-" + Path(s["nom"]).stem)
                k, n = (nom_slug, ext), 1
                while k in noms_run and noms_run[k] != h:
                    n += 1
                    k = (f"{nom_slug}-{n}", ext)
                noms_run[k] = h
                try:
                    nom_final, statut = copier_verifie(p, sortie, f"{prefixe}_{k[0]}", ext, h)
                    ligne["fichier_depose"] = nom_final
                    log.info("%-12s %s -> %s", statut.upper(), s["nom"], nom_final)
                except Exception as e:
                    log.error("Copie echouee %s : %s", s["nom"], e)
                    remarques.append(f"ERREUR_COPIE : {e}")
                    erreurs += 1
            elif not a.dry_run:
                remarques.append("non copie (--copier utiles)")
            ligne.update(manuels.get((h, s["nom"]), {}))
            ligne["remarques_collecte"] = " ; ".join(remarques)
            lignes.append(ligne)

        lignes.sort(key=lambda r: (-int(r["score_defi2"] or 0), r["nom_origine"]))

        # --- 3. REGISTRE, LISEZ-MOI, SYNTHESE ----------------------------------------------------
        comptes = {}
        for r in lignes:
            cle = r["recommandation"].split(" (")[0] or "?"
            comptes[cle] = comptes.get(cle, 0) + 1
        annees = sorted({y for r in lignes for y in r.get("_annees_set", ())})
        synthese = [f"{v} x {k}" for k, v in sorted(comptes.items())]
        log.info("SYNTHESE : %s | annees detectees : %s | erreurs : %d", " ; ".join(synthese),
                 f"{annees[0]}..{annees[-1]}" if annees else "aucune", erreurs)
        couv = construire_couverture(lignes, a.annee_min, a.annee_max)
        log.info(couv["resume"])

        if a.dry_run:
            for r in lignes[:40]:
                log.info("%s | %-45s | %s", r["score_defi2"], r["nom_origine"][:45], r["recommandation"])
            return 2 if erreurs else 0

        with open(reg_chemin, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLONNES_REGISTRE, delimiter=";", extrasaction="ignore")
            w.writeheader()
            w.writerows(lignes)
        with open(sortie / f"{prefixe}_couverture-annees_v1.csv", "w", encoding="utf-8-sig", newline="") as f:
            w2 = csv.writer(f, delimiter=";")
            w2.writerow(couv["entetes"])
            w2.writerows(couv["rows"])
        utiles = [r["fichier_depose"] for r in lignes if r["recommandation"].startswith("UTILISER") and r["fichier_depose"]]
        # Le bloc "NOTES DE L'EQUIPE" (ecrit a la main ou par annoter_registre.py) survit a une relance.
        notes_equipe, lm = "", sortie / "LISEZ-MOI.txt"
        if lm.exists():
            ancien = lm.read_text(encoding="utf-8")
            i = ancien.find("NOTES DE L'EQUIPE")
            if i >= 0:
                notes_equipe = "\n" + ancien[i:]
        lm.write_text(
            f"DEPOT 01_collecte - equipe {a.equipe}, defi {a.defi}, role {a.role}\n"
            f"Genere le {datetime.now():%Y-%m-%d %H:%M} par collecte_template.py v{VERSION}\n\n"
            f"Fichiers inventories : {len(lignes)}   |   erreurs : {erreurs}\n"
            f"Synthese : {' ; '.join(synthese)}\n"
            f"Annees detectees (noms, en-tetes, colonne annee) : {f'{annees[0]}..{annees[-1]}' if annees else 'aucune'}\n"
            f"{couv['resume']}\n"
            "(annee scolaire AAAA-AAAA comptee sous AAAA ; a confirmer sur les donnees)\n\n"
            f"CONTENU\n- {prefixe}_registre-sources_v1.csv : inventaire (structure, qualite, pertinence, sha256)\n"
            f"- {prefixe}_couverture-annees_v1.csv : matrice fichier x annee, annees MANQUANTES\n"
            f"- {prefixe}_journal-collecte_v1.log : journal d'execution\n"
            "- fichiers bruts copies SANS modification, en lecture seule (integrite verifiee par sha256)\n\n"
            "A COMPLETER A LA MAIN dans le registre : producteur_source, publication, annee_ou_periode,\n"
            "licence_remarques (la source de chaque donnee doit etre citee). Ces colonnes sont conservees\n"
            "si le script est relance.\n\n"
            "FICHIERS RECOMMANDES POUR LE DEFI 2 (UTILISER) :\n" + ("".join(f"- {x}\n" for x in utiles) or "- aucun\n")
            + notes_equipe,
            encoding="utf-8")
        log.info("Depot ecrit dans %s", sortie)
        return 2 if erreurs else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
