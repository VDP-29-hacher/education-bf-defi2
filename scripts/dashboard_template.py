#!/usr/bin/env python3
"""DASHBOARD INTERACTIF (Defi 2) - une seule page HTML autonome (aucun CDN, fonctionne hors ligne).

Entrees : tables agregees de 03_transformation (parite-effectifs, GeoJSON des 13 anciennes regions). Aucune donnee brute.
Sortie  : remplace tableau-de-bord.html dans le zip de l'etape 4 (04_analyse/*tableau-de-bord_v1.zip) par la version interactive ;
          les figures PNG restent dans le zip comme version de secours.
Fonctions de la page : choix du niveau (primaire / prescolaire / CP1), curseur d'annee, choix de region, carte, classement,
courbes (national vs region, urbain/rural, public/prive), tooltips, vue en tableau, theme clair/sombre.
Usage : dashboard_template.py DOSSIER_03 DOSSIER_04 [--equipe Burkina_Novation]
"""
import argparse, glob, json, math, os, sys, zipfile
from datetime import date
import pandas as pd


def lire(d, cle):
    f = glob.glob(os.path.join(d, f"*_{cle}_v1.csv"))
    if not f:
        sys.exit(f"Introuvable : *_{cle}_v1.csv dans {d} (lancez d'abord l'etape 3)")
    return pd.read_csv(f[0], sep=";", encoding="utf-8-sig", keep_default_na=False, dtype=str)


def simplifier(pts, eps):
    """Douglas-Peucker iteratif (pure Python)."""
    n = len(pts)
    if n < 5:
        return pts
    garde = [False] * n
    garde[0] = garde[-1] = True
    pile = [(0, n - 1)]
    while pile:
        i, j = pile.pop()
        (x1, y1), (x2, y2) = pts[i], pts[j]
        dx, dy = x2 - x1, y2 - y1
        L2 = dx * dx + dy * dy
        dmax, k = 0.0, -1
        for m in range(i + 1, j):
            x, y = pts[m]
            if L2 == 0:
                d = (x - x1) ** 2 + (y - y1) ** 2
            else:
                t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / L2))
                d = (x - (x1 + t * dx)) ** 2 + (y - (y1 + t * dy)) ** 2
            if d > dmax:
                dmax, k = d, m
        if dmax > eps * eps:
            garde[k] = True
            pile += [(i, k), (k, j)]
    return [p for p, g in zip(pts, garde, strict=True) if g]


ALIAS = {"KOURITTENGA": "KOURITENGA", "KOMANDJARI": "KOMONDJARI"}


def cle(s):
    """Cle de jointure de noms de provinces (sans accents, majuscules, sans article) + orthographes connues."""
    import re, unicodedata
    t = "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn").upper()
    t = re.sub(r"^(LES|LE|LA|L)\s+", "", re.sub(r"[^A-Z0-9]+", " ", t).strip())
    return ALIAS.get(t, t)


def charger_provinces(d03, d04, annees):
    gf = glob.glob(os.path.join(d03, "*anciennes-provinces-officiel_v1.geojson"))
    fi = glob.glob(os.path.join(d04, "*_indicateurs-provinces_v1.csv"))
    fh = glob.glob(os.path.join(d04, "*_ips-provinces-historique_v1.csv"))
    fc = glob.glob(os.path.join(d04, "*_ips-par-classe-et-milieu_v1.csv"))
    if not (gf and fi and fh and fc):
        print("INFO : niveau province absent (lancez provinces puis analyse_provinces) : section province non incluse.")
        return None
    nb = lambda x: None if x != x else round(float(x), 4)
    ind = pd.read_csv(fi[0], sep=";", encoding="utf-8-sig"); hist = pd.read_csv(fh[0], sep=";", encoding="utf-8-sig")
    cls = pd.read_csv(fc[0], sep=";", encoding="utf-8-sig")
    champs = ["ips_ensemble", "ips_urbain", "ips_rural", "ecart_urbain_moins_rural", "part_effectifs_rural", "taux_redoublement_filles",
              "taux_redoublement_garcons", "ecart_redoublement_filles_moins_garcons", "effectif_dernier_sur_max",
              "eleves_perdus_depuis_max", "filles_manquantes_parite"]
    d = {"names": sorted(ind.province), "ind": {}, "hist": {}, "classes": {}, "eff": {}, "prio": [], "sig": [], "prev": {}}
    for _, r in ind.iterrows():
        d["ind"][r.province] = {"region": r.ancienne_region, **{c: nb(r[c]) if c in r else None for c in champs}}
    for _, r in hist.iterrows():
        d["hist"][r.province] = [nb(r.get(f"ips_{y}")) for y in annees]
    # acces (effectifs en part du maximum), priorites, signalements, prevision : facultatifs
    fe = glob.glob(os.path.join(d04, "*_effectifs-provinces-historique_v1.csv"))
    if fe:
        eh = pd.read_csv(fe[0], sep=";", encoding="utf-8-sig")
        for _, r in eh.iterrows():
            v = [r.get(f"effectif_{y}") for y in annees]
            mx = max(x for x in v if x == x)
            d["eff"][r.province] = [None if x != x else round(float(x) / mx, 4) for x in v]
        tot = eh[[f"effectif_{y}" for y in annees]].sum()
        d["effNat"] = [round(float(x) / tot.max(), 4) for x in tot]
    fp = glob.glob(os.path.join(d04, "*_provinces-prioritaires_v1.csv"))
    if fp:
        d["prio"] = pd.read_csv(fp[0], sep=";", encoding="utf-8-sig").astype(object).where(lambda x: x.notna(), None).to_dict("records")
    fs = glob.glob(os.path.join(d04, "*_ips-provinces-signalements_v1.csv"))
    if fs:
        d["sig"] = pd.read_csv(fs[0], sep=";", encoding="utf-8-sig").astype(object).where(lambda x: x.notna(), None).to_dict("records")
    fv = glob.glob(os.path.join(d04, "*_prevision-ips-provinces_v1.csv"))
    if fv:
        pv = pd.read_csv(fv[0], sep=";", encoding="utf-8-sig")
        ys = sorted(int(c[-4:]) for c in pv.columns if c.startswith("ips_prevu_"))
        d["prevAns"] = ys
        for _, r in pv.iterrows():
            d["prev"][r.province] = {"v": [nb(r[f"ips_prevu_{y}"]) for y in ys], "lo": [nb(r[f"bas80_{y}"]) for y in ys],
                                     "hi": [nb(r[f"haut80_{y}"]) for y in ys], "statut": r.statut_horizon, "modele": r.modele}
    for _, r in cls.iterrows():
        d["classes"].setdefault(r.categorie, {})[r.classe] = {"ips": nb(r.ips), "trg": nb(r.taux_redoublement_garcons), "trf": nb(r.taux_redoublement_filles)}
    d["ordre"] = ["CP1", "CP2", "CE1", "CE2", "CM1", "CM2", "Total"]
    geo, vb = geo_paths(gf[0], cle_nom="ancienne_province")
    k2n = {cle(n): n for n in d["names"]}
    d["geo"], non = [], []
    for g in geo:
        nom = k2n.get(cle(g["region"]))
        (d["geo"].append({"name": nom, "d": g["d"]}) if nom else non.append(g["region"]))
    d["vb"] = vb
    print(f"Provinces : {len(d['names'])} dans les tables, {len(d['geo'])} polygones relies, polygones non relies : {non or 'aucun'}")
    return d


def _aire(r):
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(r, r[1:] + r[:1], strict=True)) / 2


def fusionner(anneaux, nd=6):
    """Fusionne des polygones voisins (communes d'une meme province) en supprimant les aretes partagees.
    Retourne les contours exterieurs (et trous) ; None si la topologie ne se referme pas (on garde alors les communes)."""
    from collections import defaultdict
    aretes = set()
    for r in anneaux:
        r = [(round(x, nd), round(y, nd)) for x, y in r]
        if r[0] == r[-1]:
            r = r[:-1]
        if _aire(r) < 0:
            r = r[::-1]
        aretes.update((a, b) for a, b in zip(r, r[1:] + r[:1], strict=True) if a != b)
    suiv = defaultdict(list)
    for a, b in aretes:
        if (b, a) not in aretes:
            suiv[a].append(b)
    out = []
    while suiv:
        a0 = next(iter(suiv)); ring = [a0]; a = a0
        while True:
            b = suiv[a].pop()
            if not suiv[a]:
                del suiv[a]
            if b == a0:
                break
            ring.append(b); a = b
            if a not in suiv:
                return None
        out.append(ring)
    grand = max(abs(_aire(r)) for r in out)
    return [r for r in out if abs(_aire(r)) > 0.004 * grand]      # retire les eclats dus aux petits defauts de topologie


def geo_paths(chemin, eps=0.012, cle_nom="ancienne_region"):
    g = json.load(open(chemin, encoding="utf-8"))
    pol = []
    for f in g["features"]:
        nom = f["properties"].get(cle_nom)
        geom = f["geometry"]
        parts = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        anneaux = [[tuple(p[:2]) for p in pl[0]] for pl in parts]
        fus = fusionner(anneaux) if len(anneaux) > 1 else None
        for r in (fus or anneaux):
            pol.append((nom, r))
    lons = [p[0] for _, r in pol for p in r]; lats = [p[1] for _, r in pol for p in r]
    mnx, mxx, mny, mxy = min(lons), max(lons), min(lats), max(lats)
    k = math.cos(math.radians((mny + mxy) / 2)); S = 100.0
    par = {}
    for nom, ring in pol:
        s = simplifier(ring, eps)
        if len(s) < 4:
            continue
        if s[0] != s[-1]:
            s = s + [s[0]]
        d = "M" + "L".join(f"{(x - mnx) * k * S:.1f},{(mxy - y) * S:.1f}" for x, y in s) + "Z"
        par.setdefault(nom, []).append(d)
    vb = [0, 0, round((mxx - mnx) * k * S, 1), round((mxy - mny) * S, 1)]
    return [{"region": n, "d": "".join(v)} for n, v in sorted(par.items())], vb


MODELE = r"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Disparités d'accès à l'école</title>
<style>
:root{color-scheme:light;--bg:#f2f3ef;--surface:#ffffff;--surface2:#f6f7f3;--text:#15171a;--text2:#474c53;--muted:#6b7077;--grid:#e3e5df;--border:#dadcd5;
--brand:#0e4f5c;--brand2:#18839a;--soft:#e3f1f3;--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--dlow:#d9413f;--dmid:#eeede9;--dhigh:#2a78d6;--ok:#178a60;--warn:#c9781a;
--shadow:0 1px 2px rgba(16,24,40,.05),0 2px 6px rgba(16,24,40,.05)}
@media(prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;--bg:#101214;--surface:#191c1f;--surface2:#1f2326;--text:#eef0f2;--text2:#c3c8ce;--muted:#969ca3;--grid:#2b2f33;--border:#353a3f;
--brand:#0f3d47;--brand2:#2aa3ba;--soft:#15343a;--s1:#3987e5;--s2:#e06a35;--s3:#22b17f;--dlow:#e86563;--dmid:#33373a;--dhigh:#3987e5;--ok:#2fb47f;--warn:#e09a3d;--shadow:none}}
:root[data-theme="dark"]{color-scheme:dark;--bg:#101214;--surface:#191c1f;--surface2:#1f2326;--text:#eef0f2;--text2:#c3c8ce;--muted:#969ca3;--grid:#2b2f33;--border:#353a3f;
--brand:#0f3d47;--brand2:#2aa3ba;--soft:#15343a;--s1:#3987e5;--s2:#e06a35;--s3:#22b17f;--dlow:#e86563;--dmid:#33373a;--dhigh:#3987e5;--ok:#2fb47f;--warn:#e09a3d;--shadow:none}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 "Segoe UI",system-ui,-apple-system,Roboto,sans-serif}
main{max-width:1180px;margin:0 auto;padding:16px}
:focus-visible{outline:3px solid var(--brand2);outline-offset:2px;border-radius:6px}
h1{font-size:1.5rem;margin:0 0 4px;line-height:1.25}h2{font-size:1rem;margin:0 0 8px;font-weight:650}
.sub{color:var(--muted);font-size:.84rem}
.hero{background:linear-gradient(120deg,var(--brand),var(--brand2));color:#fff;border-radius:16px;padding:18px 22px;display:flex;flex-wrap:wrap;gap:12px;justify-content:space-between;align-items:flex-start;box-shadow:var(--shadow)}
.hero .eyebrow{font-size:.75rem;letter-spacing:.08em;text-transform:uppercase;opacity:.85;margin:0 0 4px}
.hero .sub{color:rgba(255,255,255,.85)}.hero .actions{display:flex;gap:6px;flex-wrap:wrap}
.hero button{background:rgba(255,255,255,.14);border-color:rgba(255,255,255,.4);color:#fff}.hero button:hover{background:rgba(255,255,255,.26)}
button,select,input[type=range]{font:inherit;color:var(--text)}
button,select{background:var(--surface);border:1px solid var(--border);border-radius:9px;padding:6px 11px;cursor:pointer}
button:hover{border-color:var(--brand2)}
.btn{background:var(--brand2);border-color:var(--brand2);color:#fff;font-weight:600}.btn:hover{filter:brightness(1.08)}
.btn.ghost{background:transparent;color:var(--brand2)}
.controls{display:flex;flex-wrap:wrap;gap:14px;align-items:end;margin:14px 0;padding:10px 14px;background:var(--surface);border:1px solid var(--border);border-radius:12px;box-shadow:var(--shadow)}
.controls label{display:flex;flex-direction:column;font-size:.78rem;color:var(--text2);gap:3px;max-width:100%;min-width:0;font-weight:600}
select{max-width:100%}input[type=range]{max-width:100%;accent-color:var(--brand2)}
#tab,#ptab,#pprio{overflow-x:auto;max-width:100%}
.onglets{display:flex;gap:4px;margin:12px 0 8px;position:sticky;top:0;z-index:5;background:var(--bg);padding:8px 0;border-bottom:1px solid var(--border);overflow-x:auto;scrollbar-width:thin}
.onglets button{font-weight:600;border:1px solid transparent;background:transparent;border-radius:999px;padding:7px 14px;white-space:nowrap;color:var(--text2)}
.onglets button:hover{background:var(--surface);border-color:var(--border)}
.onglets button[aria-selected="true"]{background:var(--brand);border-color:var(--brand);color:#fff}
.onglets .n{display:inline-block;min-width:1.35em;height:1.35em;line-height:1.35em;border-radius:999px;background:var(--soft);color:var(--brand2);font-size:.72rem;margin-right:6px;text-align:center}
.onglets button[aria-selected="true"] .n{background:rgba(255,255,255,.22);color:#fff}
.titreOng{font-size:1.25rem;margin:12px 0 4px}.chapo{color:var(--text2);margin:0 0 12px;max-width:820px}
table.mini td,table.mini th{padding:4px 7px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:10px;margin-bottom:12px}
.kpi{background:var(--surface);border:1px solid var(--border);border-left:4px solid var(--brand2);border-radius:12px;padding:10px 14px;box-shadow:var(--shadow)}
.kpi.alerte{border-left-color:var(--dlow)}.kpi.ok{border-left-color:var(--ok)}
.kpi b{display:block;font-size:1.65rem;line-height:1.15;font-variant-numeric:tabular-nums}.kpi span{font-size:.78rem;color:var(--text2)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
@media(max-width:820px){.grid,.grid3{grid-template-columns:1fr}}
.card{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:14px 16px;min-width:0;box-shadow:var(--shadow)}
.card p.note{font-size:.78rem;color:var(--muted);margin:6px 0 0}
svg{width:100%;height:auto;display:block}svg text{fill:var(--text2);font:11px "Segoe UI",system-ui,sans-serif}
.legend{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:.8rem;color:var(--text2);margin:0 0 6px}
.sw{display:inline-block;width:14px;height:3px;border-radius:2px;margin-right:5px;vertical-align:middle}.sw.bloc{height:11px;width:11px;border-radius:3px}
#tip{position:fixed;pointer-events:none;background:var(--surface);color:var(--text);border:1px solid var(--border);border-radius:9px;padding:7px 10px;font-size:.8rem;
box-shadow:0 4px 14px rgba(0,0,0,.18);display:none;z-index:9;max-width:260px}
table{border-collapse:collapse;width:100%;font-size:.83rem;font-variant-numeric:tabular-nums}
th,td{padding:5px 8px;border-bottom:1px solid var(--grid);text-align:right}th:first-child,td:first-child{text-align:left}
th{font-size:.74rem;text-transform:uppercase;letter-spacing:.03em;color:var(--muted);font-weight:650;background:var(--surface)}
tbody tr:hover{background:var(--surface2)}.scroll th{position:sticky;top:0;z-index:1}
.db{position:relative;display:inline-block;min-width:74px;padding:0 4px;text-align:right}.db i{position:absolute;left:0;top:18%;height:64%;border-radius:3px;opacity:.22}
.db b{position:relative}
.msg{background:var(--soft);border:1px solid var(--border);border-left:4px solid var(--brand2);border-radius:12px;padding:10px 14px;margin-bottom:12px}
details{margin-top:12px}summary{cursor:pointer;color:var(--brand2);font-weight:600}ul,ol{margin:6px 0 0 18px;padding:0}li{margin:3px 0}
.reg path{stroke:var(--surface);stroke-width:.45;cursor:pointer;transition:opacity .15s}.reg path:hover{opacity:.82}.reg path.sel{stroke:var(--text);stroke-width:1.8}
.bar{cursor:pointer}.scroll{max-height:660px;overflow:auto}
/* accueil */
.question{font-size:1.35rem;line-height:1.3;margin:2px 0 10px;font-weight:700}
.eyebrow{font-size:.74rem;letter-spacing:.08em;text-transform:uppercase;color:var(--brand2);font-weight:700;margin:0 0 4px}
.lead{font-size:1rem;color:var(--text2);margin:0;max-width:900px}
.reps{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:12px 0}
@media(max-width:980px){.reps{grid-template-columns:1fr 1fr}}@media(max-width:560px){.reps{grid-template-columns:1fr}}
.rep{display:flex;flex-direction:column;gap:4px}.rep .big{font-size:1.9rem;font-weight:700;line-height:1.1;font-variant-numeric:tabular-nums}
.rep .txt{font-size:.85rem;color:var(--text2);flex:1}.rep .tag{align-self:flex-start}.rep svg{margin:6px 0 4px}.rep .go{align-self:flex-start;margin-top:6px}
.tag{display:inline-block;font-size:.7rem;font-weight:700;padding:2px 8px;border-radius:999px;background:var(--soft);color:var(--brand2)}
.tag.alerte{background:rgba(217,65,63,.12);color:var(--dlow)}.tag.ok{background:rgba(23,138,96,.12);color:var(--ok)}
.chips{display:flex;flex-wrap:wrap;gap:6px}.chip{border-radius:999px;padding:4px 11px;font-size:.84rem;border:1px solid var(--border);background:var(--surface2)}
.chip.p1{border-color:var(--dlow);background:var(--dlow);color:#fff;font-weight:600}.chip:hover{filter:brightness(1.08);border-color:var(--text2)}.chip.p2{border-color:var(--s2);color:var(--s2)}
.guide{list-style:none;margin:6px 0 0;padding:0;counter-reset:g}.guide li{counter-increment:g;display:flex;gap:10px;align-items:flex-start;padding:7px 0;border-bottom:1px solid var(--grid);cursor:pointer}
.guide li::before{content:counter(g);flex:none;width:24px;height:24px;border-radius:999px;background:var(--brand2);color:#fff;font-size:.78rem;font-weight:700;display:grid;place-items:center}
.guide li:hover b{color:var(--brand2)}.guide li span{display:block;font-size:.82rem;color:var(--text2)}
.use h3{font-size:.95rem;margin:0 0 4px}.use p{margin:0;font-size:.86rem;color:var(--text2)}
.hero .eyebrow{color:rgba(255,255,255,.88)}
/* methode */
.pipe{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;counter-reset:e}
@media(max-width:820px){.pipe{grid-template-columns:1fr}}
.etape{background:var(--surface2);border:1px solid var(--border);border-top:4px solid var(--brand2);border-radius:12px;padding:10px 12px;font-size:.83rem}
.etape b{display:block;font-size:.92rem}.etape .role{color:var(--brand2);font-size:.74rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em}
dl.lex{display:grid;grid-template-columns:max-content 1fr;gap:6px 14px;margin:0;font-size:.86rem}dl.lex dt{font-weight:700}dl.lex dd{margin:0;color:var(--text2)}
@media(max-width:560px){dl.lex{grid-template-columns:1fr}dl.lex dd{margin-bottom:6px}}
pre.code{background:#0f1a20;color:#e3eef3;padding:12px 14px;border-radius:10px;overflow-x:auto;font:13px/1.5 Consolas,ui-monospace,monospace;margin:6px 0;white-space:pre-wrap;word-break:break-all}
.dls{display:flex;flex-wrap:wrap;gap:8px}
@media(max-width:600px){h1{font-size:1.2rem}.question{font-size:1.1rem}.kpi b{font-size:1.35rem}.hero{padding:14px}main{padding:10px}}
@media print{:root{color-scheme:light}body{background:#fff}.hero{background:#fff;color:#000;border:1px solid #ccc;box-shadow:none}.hero .sub{color:#444}
.hero .actions,.controls input,.controls select,#tip,.go,.dls{display:none!important}
.card,.kpi,.msg,.rep{break-inside:avoid;border-color:#ccc;box-shadow:none}.scroll{max-height:none!important;overflow:visible!important}details{display:none}
.grid{grid-template-columns:1fr 1fr}main{max-width:none;padding:0}.onglets{display:none!important}
[data-onglet][hidden]{display:block!important}[data-onglet]{break-before:page}[data-onglet]:first-of-type{break-before:auto}}
</style></head><body><main>
<header class="hero"><div><p class="eyebrow">Data Challenge Burkina 2026 · Éducation · Défi 2 · Équipe __EQUIPE__</p>
<h1>Disparités d'accès à l'école : territoires, filles-garçons, ville-campagne</h1>
<div class="sub">Burkina Faso, préscolaire et primaire, __PERIODE__. Sources : annuaires DGESS, projections INSD, limites COD-AB. Mis à jour le __DATE__.</div></div>
<div class="actions"><button id="dlTop" type="button" title="Télécharger les tables de l'outil au format CSV">Données (CSV)</button><button id="lien" type="button" title="Copie un lien qui rouvre exactement cette vue">Copier le lien de cette vue</button><button id="imprimer" type="button" title="Imprimer ou enregistrer en PDF">Imprimer / PDF</button><button id="theme" type="button" aria-label="Changer de thème clair ou sombre">Thème</button></div></header>
<nav class="onglets" id="onglets" role="tablist" aria-label="Parties de l'outil">
<button type="button" role="tab" data-o="accueil">Accueil</button><button type="button" role="tab" data-o="analyse"><span class="n">1</span>Analyse</button><button type="button" role="tab" data-o="tdb"><span class="n">2</span>Tableau de bord</button><button type="button" role="tab" data-o="carte"><span class="n">3</span>Carte</button><button type="button" role="tab" data-o="decision"><span class="n">4</span>Aide à la décision</button><button type="button" role="tab" data-o="prevision"><span class="n">5</span>Prévision</button><button type="button" role="tab" data-o="methode">Méthode et données</button></nav>
<div data-onglet="accueil">
<section class="card"><p class="eyebrow">La question du Défi 2</p><p class="question">Où les écarts d'accès à l'école sont-ils les plus grands, entre filles et garçons et entre ville et campagne, et comment évoluent-ils ?</p>
<p class="lead" id="hRep"></p></section>
<div class="reps" id="hReps"></div>
<div class="grid">
<section class="card"><h2>Où agir d'abord</h2><div class="legend"><span><i class="sw bloc" style="background:var(--dlow)"></i>Priorité 1 : peu de filles et élèves perdus</span><span><i class="sw bloc" style="background:var(--s2)"></i>Priorité 2 : un des deux</span><span><i class="sw bloc" style="background:var(--grid)"></i>Hors priorité</span></div>
<div id="hCarte"></div><p class="note">Règle par défaut : IPS sous 0,95 et effectifs sous 60 % de la meilleure année. Cliquer une province ouvre sa fiche dans l'aide à la décision.</p></section>
<div style="display:flex;flex-direction:column;gap:12px">
<section class="card"><h2>Provinces en priorité 1</h2><div class="chips" id="hP1"></div><p class="note" id="hP1n"></p></section>
<section class="card"><h2>Comment utiliser l'outil</h2><ol class="guide">
<li data-go="analyse"><div><b>Analyse</b><span>Les constats chiffrés, les liens entre les écarts et les profils de provinces.</span></div></li>
<li data-go="tdb"><div><b>Tableau de bord</b><span>La parité et l'accès par région, année par année, de __PERIODE__.</span></div></li>
<li data-go="carte"><div><b>Carte</b><span>Les 17 régions actuelles et les 45 provinces, selon la mesure choisie.</span></div></li>
<li data-go="decision"><div><b>Aide à la décision</b><span>Réglez deux seuils : la liste des provinces à cibler et leur fiche se mettent à jour.</span></div></li>
<li data-go="prevision"><div><b>Prévision</b><span>L'IPS de chaque province d'ici __ANNEE_PREV__, avec sa marge d'erreur.</span></div></li>
</ol></section></div></div>
<section class="card" style="margin-top:12px"><h2>À qui sert cet outil</h2><div class="grid3">
<div class="use"><h3>Ministère et DGESS</h3><p>Choisir les provinces où rouvrir des classes et soutenir la scolarisation des filles, avec une règle transparente et réglable.</p></div>
<div class="use"><h3>Directions régionales</h3><p>Imprimer la fiche d'une province : effectifs perdus, parité en ville et à la campagne, projection, filles à inscrire.</p></div>
<div class="use"><h3>Partenaires et ONG</h3><p>Repérer les zones où les écarts se cumulent (accès faible et peu de filles) et suivre leur évolution chaque année.</p></div>
</div></section>
</div>
<div data-onglet="analyse" hidden>
<h2 class="titreOng">Analyse : où les écarts d'accès sont les plus grands</h2>
<p class="chapo">Les chiffres clés, les territoires les plus touchés, puis les liens entre les écarts et les profils de provinces qui en ressortent.</p>
<div class="kpis" id="anaKpis"></div>
<section class="card"><h2>Ce que montrent les données</h2><ul id="anaConstats"></ul></section>
<div class="grid" style="margin-top:12px">
<section class="card"><h2>Régions où l'accès est le plus faible</h2><div id="anaReg"></div><p class="note">Taux brut de scolarisation du primaire, __ANNEE_PROV__ (taux publiés par la DGESS).</p></section>
<section class="card"><h2>Provinces qui ont perdu le plus d'élèves</h2><div id="anaProvAcc"></div><p class="note">Effectif __ANNEE_PROV__ rapporté au meilleur effectif de la province depuis 2015.</p></section>
<section class="card"><h2>Provinces les plus éloignées de la parité</h2><div id="anaProvIps"></div><p class="note">IPS du primaire __ANNEE_PROV__ ; il faudrait inscrire ces filles en plus pour atteindre un IPS de 1.</p></section>
<section class="card"><h2>Élèves à ajouter pour un taux brut de 100 %</h2><div id="anaPop"></div><p class="note">Enfants d'âge primaire = élèves ÷ TBS, c'est-à-dire la population utilisée par la DGESS. Un TBS de 100 % compte aussi les élèves hors âge : ces chiffres sont un minimum.</p></section>
<section class="card" id="anaTbsCard" hidden><h2>Taux brut de scolarisation par province</h2><div id="anaTbs"></div><p class="note" id="anaTbsNote"></p></section>
<section class="card" id="anaTypoCard" hidden><h2>Profils de provinces (typologie)</h2><div class="legend" id="lgTypo"></div><div id="anaTypo"></div><p class="note">Classification par k-moyennes sur trois mesures du Défi 2 : accès, parité filles-garçons, écart ville-campagne. Survoler une province pour son profil.</p></section>
<section class="card" id="anaLiensCard" hidden><h2>Les écarts se cumulent-ils ?</h2><div id="anaLiens"></div><p class="note">Corrélation de rang de Spearman sur les 45 provinces ; « significatif » : p &lt; 0,05. Une corrélation n'est pas une cause.</p></section>
</div></div>
<div data-onglet="tdb" hidden>
<h2 class="titreOng">Tableau de bord : parité et accès par région, année par année</h2>
<p class="sub"><b>Lecture :</b> IPS = filles ÷ garçons. 1,00 = parité ; sous 1 = moins de filles ; au-dessus de 1 = plus de filles (ce n'est pas un « problème de filles »).</p>
<div class="controls">
<label>Niveau<select id="niveau"><option value="pri">Primaire (effectifs)</option><option value="pre">Préscolaire (effectifs)</option><option value="cp1">Nouveaux inscrits au CP1</option></select></label>
<label>Année scolaire : <span id="anneeLib"></span><input id="annee" type="range" min="0" max="0" step="1" style="width:200px"></label>
<label>Région<select id="region"></select></label>
</div>
<div class="kpis" id="kpis"></div>
<div class="msg" id="msg" aria-live="polite"></div>
<div class="grid">
<section class="card"><h2 id="tCarte"></h2><div id="carte"></div><p class="note">Cliquer une région pour la sélectionner. Rouge : moins de filles que de garçons ; bleu : plus de filles ; gris : parité.</p></section>
<section class="card"><h2 id="tRang"></h2><div id="rang"></div><p class="note">Barres ancrées sur la parité (1,00).</p></section>
<section class="card"><h2 id="tEvo"></h2><div class="legend" id="lgEvo"></div><div id="evo"></div></section>
<section class="card"><h2>Primaire : urbain et rural</h2><div class="legend" id="lgMil"></div><div id="mil"></div><p class="note">Données nationales ; l'écart est la zone entre les courbes.</p></section>
<section class="card"><h2>Primaire : public et privé</h2><div class="legend" id="lgSta"></div><div id="sta"></div></section>
</div>
<div id="accSec" hidden>
<h2 style="font-size:1.15rem;margin:28px 0 8px">Accès à l'école : taux de scolarisation par région et par sexe</h2>
<div class="controls">
<label>Indicateur<select id="aind"></select></label>
<span class="sub" style="max-width:560px">Taux publiés par la DGESS, rapportés à la population d'âge scolaire. Ils peuvent dépasser 100 % (élèves plus jeunes ou plus âgés). L'année et la région suivent les choix du haut de page.</span>
</div>
<div class="msg" id="amsg" aria-live="polite"></div>
<div class="grid">
<section class="card"><h2 id="taRang"></h2><div class="legend" id="lgARang"></div><div id="arang"></div><p class="note">Chaque ligne relie le taux des garçons et celui des filles ; la longueur du trait est l'écart filles-garçons, la position est le niveau d'accès.</p></section>
<section class="card"><h2 id="taEvo"></h2><div class="legend" id="lgAEvo"></div><div id="aevo"></div></section>
</div></div>
<details><summary>Voir les données de l'année choisie sous forme de tableau</summary><div id="tab"></div><div id="ptab"></div></details>
</div>
<div data-onglet="carte" hidden>
<h2 class="titreOng">Carte : les 17 régions actuelles et les 45 provinces</h2>
<div id="r17Sec" hidden>
<h2 style="font-size:1.15rem;margin:28px 0 8px">Les 17 régions actuelles : primaire __ANNEE_PROV__, agrégation exacte des 45 anciennes provinces</h2>
<div class="controls">
<label>Mesure<select id="rmes"></select></label>
<span class="sub" style="max-width:560px">Chaque ancienne province est entièrement comprise dans une seule région actuelle (vérifié commune par commune avec les codes COD-AB) : les effectifs s'additionnent sans estimation.</span>
</div>
<div class="msg" id="rmsg" aria-live="polite"></div>
<div class="grid">
<section class="card"><h2 id="trCarte"></h2><div id="rcarte"></div></section>
<section class="card"><h2 id="trRang"></h2><div id="rrang"></div></section>
</div></div>
<div id="provSec" hidden>
<h2 style="font-size:1.15rem;margin:28px 0 8px">Niveau province : 45 anciennes provinces, primaire __ANNEE_PROV__</h2>
<div class="controls">
<label>Mesure<select id="pmes"><option value="effectif_dernier_sur_max">Accès : effectifs __ANNEE_PROV__ en % du maximum depuis 2015</option><option value="ips_ensemble">IPS, ensemble des élèves</option><option value="ips_urbain">IPS, milieu urbain</option><option value="ips_rural">IPS, milieu rural</option><option value="ecart_urbain_moins_rural">Écart d'IPS urbain − rural</option></select></label>
<label>Province<select id="pprov"></select></label>
</div>
<div class="msg" id="pmsg" aria-live="polite"></div>
<div class="grid">
<section class="card"><h2 id="tpCarte"></h2><div id="pcarte"></div><p class="note">Cliquer une province pour la sélectionner. Source : annuaire statistique du primaire __ANNEE_PROV__ (DGESS), 45 provinces d'avant la réforme.</p></section>
<section class="card"><h2 id="tpRang"></h2><div class="scroll" id="prang"></div></section>
<section class="card"><h2 id="tpEvo"></h2><div class="legend" id="lgPEvo"></div><div id="pevo"></div></section>
<section class="card"><h2>IPS par classe, national : urbain et rural</h2><div class="legend" id="lgPCl"></div><div id="pcl"></div><p class="note">Somme des 45 provinces, __ANNEE_PROV__ ; l'écart est la zone entre les courbes. L'IPS reste sous 1 dans les premières classes (CP1 à CE1) puis dépasse 1 en CM1 et CM2 : à interpréter avec prudence, aucune cause n'est démontrée par ces données.</p></section>
<section class="card"><h2 id="tpEff"></h2><div class="legend" id="lgPEff"></div><div id="peff"></div><p class="note">Effectif total du primaire rapporté à la meilleure année de la province depuis 2015 (100 % = maximum). Une chute brutale signale une perte d'accès, le plus souvent des fermetures d'écoles.</p></section>
</div>
<p class="sub" id="psig"></p></div>
</div>
<div data-onglet="decision" hidden>
<h2 class="titreOng">Aide à la décision : quelles provinces cibler en priorité ?</h2>
<p class="sub">Réglez les deux seuils : la liste, la carte et les chiffres se mettent à jour. Cliquez une province dans la liste ou sur la carte pour afficher sa fiche.</p>
<div class="grid">
<section class="card"><h2>Simulateur de ciblage : provinces prioritaires</h2>
<div class="controls" style="margin:0 0 8px;padding:8px 10px"><label>IPS sous : <b id="sIpsL"></b><input id="sIps" type="range" min="0.85" max="1" step="0.01" value="0.95" style="width:150px"></label>
<label>Effectifs sous : <b id="sAccL"></b> du maximum<input id="sAcc" type="range" min="0.3" max="0.9" step="0.05" value="0.6" style="width:150px"></label></div>
<div class="msg" id="sMsg" style="margin-bottom:8px"></div>
<div class="scroll" id="pprio" style="max-height:360px"></div><p class="note">Priorité 1 = les deux seuils franchis ; priorité 2 = un seul. Réglages par défaut (0,95 et 60 %) = règle du dossier. Cliquer une ligne pour afficher la province.</p></section>
<div><section class="card"><div style="display:flex;justify-content:space-between;gap:8px;align-items:flex-start"><h2 id="dTitre">Fiche de la province</h2><button type="button" class="btn ghost" id="dImpr" title="Ouvre la fiche seule, prête à imprimer ou à enregistrer en PDF">Imprimer la fiche</button></div><div id="dFiche"></div><div id="dSpark"></div></section>
<section class="card" style="margin-top:12px"><h2>Carte des priorités</h2><div id="dCarte"></div><p class="note">Rouge : priorité 1 ; orange : priorité 2 ; gris : hors priorité, avec les seuils choisis à gauche.</p></section></div>
</div>
</div>
<div data-onglet="prevision" hidden>
<h2 class="titreOng">Prévision : l'IPS des provinces d'ici __ANNEE_PREV__</h2>
<div class="msg" id="fMsg"></div>
<div class="controls"><label>Province<select id="fprov"></select></label></div>
<div class="grid">
<section class="card"><h2 id="tfEvo"></h2><div class="legend" id="lgFEvo"></div><div id="fevo"></div><p class="note">Trait plein : IPS observé. Pointillés : projection si la situation actuelle se prolonge. Zone grisée : 8 fois sur 10, la valeur réelle tombera dans cette bande (erreur mesurée sur les années passées).</p></section>
<section class="card"><h2 id="tfRang"></h2><div class="scroll" id="frang"></div><p class="note">Point : IPS projeté ; trait : marge à 80 %. Rouge : sous 0,95 même dans le scénario haut ; orange : incertain ; bleu : au-dessus de 0,95.</p></section>
</div>
<section class="card" style="margin-top:12px"><h2>Fiabilité : quatre modèles testés sur le passé</h2><div id="fbt"></div><p class="note">On se place en 2019, en 2020 puis en 2021, on prévoit les années suivantes avec les seules données antérieures et on mesure l'erreur. Le modèle retenu est celui qui se trompe le moins.</p></section>
</div>
<div data-onglet="methode" hidden>
<h2 class="titreOng">Méthode et données : d'où viennent les chiffres, et comment les refaire</h2>
<p class="chapo">Chaque chiffre de l'outil vient de tables agrégées et publiques. La chaîne complète se relance par une seule commande et reproduit les mêmes fichiers.</p>
<section class="card"><h2>Le parcours des données, en cinq étapes</h2><div class="pipe">
<div class="etape"><span class="role">Engineer</span><b>01 Collecte</b>Inventaire du Data Pack et des sources en ligne, registre des sources avec empreinte sha256 et décision pour le Défi 2.</div>
<div class="etape"><span class="role">Engineer</span><b>02 Nettoyage</b>Tableaux DGESS remis en format long, noms harmonisés, doublons retirés, extraction des projections INSD par province.</div>
<div class="etape"><span class="role">Architect</span><b>03 Transformation</b>Indicateurs de parité, modèle commun région × année, correspondance exacte 45 provinces → 17 régions par les codes COD-AB.</div>
<div class="etape"><span class="role">Analyst · Scientist</span><b>04 Analyse</b>Tendances, liens (Spearman), profils (k-moyennes), règle de priorité, prévision testée sur le passé.</div>
<div class="etape"><span class="role">Analyst</span><b>05 Interprétation</b>Dossier technique, fiche nationale et 17 fiches régionales, ce tableau de bord.</div>
</div></section>
<div class="grid" style="margin-top:12px">
<section class="card"><h2>Lexique</h2><dl class="lex">
<dt>IPS</dt><dd>Indice de parité entre les sexes : filles ÷ garçons. 1,00 = parité ; sous 1, moins de filles.</dd>
<dt>TBS</dt><dd>Taux brut de scolarisation : élèves du primaire ÷ enfants de 6 à 11 ans. Peut dépasser 100 % (élèves hors âge).</dd>
<dt>TBA</dt><dd>Taux brut d'admission : nouveaux inscrits au CP1 ÷ enfants de 6 ans.</dd>
<dt>TAP</dt><dd>Taux d'achèvement du primaire : nouveaux élèves de CM2 ÷ enfants de 11 ans.</dd>
<dt>Effectifs / meilleur</dt><dd>Élèves de la dernière année ÷ meilleure année depuis 2015 : mesure la perte d'accès d'une province.</dd>
<dt>Écart ville-campagne</dt><dd>IPS urbain − IPS rural. Positif : moins de filles à la campagne qu'en ville.</dd>
<dt>Priorité 1 / 2</dt><dd>Province qui franchit les deux seuils (parité et effectifs) ou un seul.</dd>
<dt>Spearman (rho)</dt><dd>Corrélation de rang entre deux mesures, de −1 à 1 ; « significatif » si p &lt; 0,05.</dd>
<dt>Marge à 80 %</dt><dd>Bande dans laquelle la valeur réelle est tombée 8 fois sur 10 lors des tests sur les années passées.</dd>
</dl></section>
<section class="card"><h2>Sources</h2><ul>
<li>DGESS / MENAPLN : annuaires statistiques du préscolaire et du primaire, __PERIODE__ (13 anciennes régions, 45 provinces pour la dernière année).</li>
<li>INSD : projections de population 2020-2035 par province, sexe et âge (enfants de 6 à 11 ans).</li>
<li>OCHA / IGB (HDX) : limites administratives COD-AB et codes des anciennes et nouvelles entités.</li>
</ul><h2 style="margin-top:14px">Contrôles faits à chaque relance</h2><ul>
<li>Filles + garçons = total, pour chaque région et chaque année.</li>
<li>Somme des 45 provinces = national ; chaque province tombe dans une seule des 17 régions actuelles, commune par commune.</li>
<li>Population INSD par province : sa somme retrouve la population utilisée par la DGESS dans chaque région.</li>
<li>Prévision : quatre modèles testés en se plaçant en 2019, 2020 et 2021 ; le plus fiable est retenu.</li>
</ul></section>
<section class="card"><h2>Refaire tous les chiffres</h2><p class="sub" style="margin:0 0 6px">Depuis le dossier du projet, sous Windows (Python 3 avec pandas, scipy, scikit-learn) :</p>
<pre class="code" id="cmd">powershell -ExecutionPolicy Bypass -File scripts\lancer_pipeline.ps1</pre>
<button type="button" class="btn ghost" id="cmdCopie">Copier la commande</button>
<p class="note">Une étape seule : ajouter <code>-Etapes dashboard</code> (ou analyse, prevision…). Les fichiers sont renommés selon la convention du challenge et contrôlés avant le dépôt.</p></section>
<section class="card" id="telech"><h2>Télécharger les données de l'outil</h2><p class="sub" style="margin:0 0 8px">Fichiers CSV (séparateur point-virgule), lisibles dans Excel.</p><div class="dls">
<button type="button" class="btn" data-dl="provinces">45 provinces : indicateurs</button><button type="button" class="btn" data-dl="priorites">Provinces prioritaires (seuils actuels)</button>
<button type="button" class="btn" data-dl="regions">Régions : IPS par année</button><button type="button" class="btn" data-dl="prevision">Prévision par province</button></div>
<p class="note">Les priorités suivent les seuils réglés dans l'onglet « Aide à la décision ».</p></section>
</div>
<section class="card" style="margin-top:12px"><h2>Limites à garder en tête</h2><ul>__LIMITES__</ul></section>
</div>
<div id="tip" role="tooltip"></div>
</main>
<script>
const D=__DATA__;
const N=D.years.length, $=id=>document.getElementById(id);
const NOMS={pri:"Primaire",pre:"Préscolaire",cp1:"Nouveaux inscrits au CP1"};
const st={niv:"pri",yi:N-1,reg:""};
const f2=v=>v==null?"n.d.":v.toFixed(2).replace(".",","), f3=v=>v==null?"n.d.":v.toFixed(3).replace(".",",");
const pc=v=>v==null?"n.d.":Math.round(v)+" %", pc1=v=>v==null?"n.d.":Math.round(v*100)+" %";
const ya=y=>y+"/"+String(y+1).slice(2);
const cv=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const hex=h=>[1,3,5].map(i=>parseInt(h.slice(i,i+2),16));
function mix(a,b,t){const A=hex(a),B=hex(b);return "rgb("+A.map((x,i)=>Math.round(x+(B[i]-x)*t)).join(",")+")"}
function colorFor(v){if(v==null)return cv("--grid");const t=Math.max(-1,Math.min(1,(v-1)/0.15));return t<0?mix(cv("--dmid"),cv("--dlow"),-t):mix(cv("--dmid"),cv("--dhigh"),t)}
const tip=$("tip");
function showTip(e,h){tip.innerHTML=h;tip.style.display="block";const w=tip.offsetWidth,x=Math.min(e.clientX+14,innerWidth-w-8);tip.style.left=Math.max(4,x)+"px";tip.style.top=(e.clientY+14)+"px"}
function hideTip(){tip.style.display="none"}
const serie=()=>D[st.niv];               // {region:[...]}
const natS=()=>D.nat[st.niv];
const valReg=(r,i)=>serie()[r][i];
function rows(i){return D.regions.map(r=>({r,v:valReg(r,i)})).filter(o=>o.v!=null).sort((a,b)=>a.v-b.v)}

function kpis(){
  const i=st.yi,n=natS()[i],n0=natS()[0],rs=rows(i),low=rs[0],sous=rs.filter(o=>o.v<0.97).length;
  const m=D.mil.urbain[i]!=null&&D.mil.rural[i]!=null?D.mil.urbain[i]-D.mil.rural[i]:null,m0=D.mil.urbain[0]-D.mil.rural[0];
  $("kpis").innerHTML=
   `<div class="kpi"><b>${f2(n)}</b><span>IPS national, ${NOMS[st.niv].toLowerCase()}, ${ya(D.years[i])} (${ya(D.years[0])} : ${f2(n0)})</span></div>`+
   `<div class="kpi"><b>${m==null?"n.d.":f3(m)}</b><span>Écart urbain - rural en IPS, primaire (${ya(D.years[0])} : ${f3(m0)})</span></div>`+
   `<div class="kpi"><b>${sous} / ${rs.length}</b><span>régions sous 0,97, ${NOMS[st.niv].toLowerCase()}</span></div>`+
   `<div class="kpi"><b>${low?low.r:"n.d."}</b><span>région la plus basse : IPS ${low?f2(low.v):"n.d."}</span></div>`+
   (D.acc&&D.acc.tbs_primaire?(()=>{const z=D.acc.tbs_primaire.z,nt=z.National.t,rs2=D.regions.filter(r=>z[r]&&z[r].t[i]!=null).sort((a,b)=>z[a].t[i]-z[b].t[i]),lo2=rs2[0];
     return `<div class="kpi"><b>${pc(nt[i])}</b><span>TBS primaire national, ${ya(D.years[i])} (${ya(D.years[0])} : ${pc(nt[0])}) ; le plus bas : ${lo2} ${pc(z[lo2].t[i])}</span></div>`})():"");
  const hi=rs[rs.length-1];
  $("msg").textContent=`En ${ya(D.years[i])}, l'IPS national (${NOMS[st.niv].toLowerCase()}) est de ${f2(n)}. La région la plus éloignée de la parité est ${low.r} (${f2(low.v)}), la plus haute ${hi.r} (${f2(hi.v)}). `+
   (st.reg?`${st.reg} : ${f2(valReg(st.reg,i))}, soit ${valReg(st.reg,i)>=n?"au-dessus":"en dessous"} de la moyenne nationale.`:"");
}

function carte(){
  $("tCarte").textContent=`${NOMS[st.niv]} ${ya(D.years[st.yi])} : IPS par ancienne région`;
  let h=`<svg viewBox="${D.vb.join(" ")}" role="img" aria-label="Carte des 13 anciennes régions colorée par IPS"><g class="reg">`;
  D.geo.forEach(g=>{const v=valReg(g.region,st.yi);h+=`<path data-r="${g.region}" class="${g.region===st.reg?"sel":""}" d="${g.d}" fill="${colorFor(v)}"/>`});
  h+="</g></svg>";
  // legende continue
  h+=`<svg viewBox="0 0 300 36" role="img" aria-label="Légende de la carte"><defs><linearGradient id="lg"><stop offset="0" stop-color="${colorFor(0.85)}"/><stop offset=".5" stop-color="${colorFor(1)}"/><stop offset="1" stop-color="${colorFor(1.15)}"/></linearGradient></defs>
  <rect x="10" y="4" width="280" height="10" rx="3" fill="url(#lg)"/><text x="10" y="30">0,85 (moins de filles)</text><text x="150" y="30" text-anchor="middle">1,00</text><text x="290" y="30" text-anchor="end">1,15 (plus de filles)</text></svg>`;
  $("carte").innerHTML=h;
  $("carte").querySelectorAll("path").forEach(p=>{
    p.onmousemove=e=>{const r=p.dataset.r,v=valReg(r,st.yi);showTip(e,`<b>${r}</b><br>IPS ${f2(v)}<br>variation depuis ${ya(D.years[0])} : ${v==null||valReg(r,0)==null?"n.d.":(v-valReg(r,0)>=0?"+":"")+f2(v-valReg(r,0))}`)};
    p.onmouseleave=hideTip;p.onclick=()=>{st.reg=p.dataset.r===st.reg?"":p.dataset.r;$("region").value=st.reg;draw()};
  });
}

function rang(){
  $("tRang").textContent=`Classement des régions, ${ya(D.years[st.yi])}`;
  const rs=rows(st.yi).reverse(),W=520,rh=24,m={l:118,r:44,t:6,b:22},H=m.t+m.b+rs.length*rh,lo=0.85,hi=1.15;
  const x=v=>m.l+(Math.max(lo,Math.min(hi,v))-lo)/(hi-lo)*(W-m.l-m.r);
  let h=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Classement des régions par IPS">`;
  [0.85,0.9,0.95,1,1.05,1.1,1.15].forEach(t=>{h+=`<line x1="${x(t)}" x2="${x(t)}" y1="${m.t}" y2="${H-m.b}" stroke="${cv("--grid")}" stroke-width="${t===1?1.5:1}"/><text x="${x(t)}" y="${H-6}" text-anchor="middle">${f2(t)}</text>`});
  rs.forEach((o,i)=>{const y=m.t+i*rh,sel=o.r===st.reg,c=o.v<1?cv("--dlow"):cv("--dhigh"),x0=x(1),x1=x(o.v);
    h+=`<g class="bar" data-r="${o.r}"><rect x="0" y="${y}" width="${W}" height="${rh}" fill="transparent"/>
    <rect x="${Math.min(x0,x1)}" y="${y+5}" width="${Math.max(1,Math.abs(x1-x0))}" height="${rh-10}" rx="3" fill="${c}" ${sel?`stroke="${cv("--text")}" stroke-width="1.5"`:""}/>
    <text x="${m.l-8}" y="${y+rh/2+4}" text-anchor="end" ${sel?`style="font-weight:700;fill:${cv("--text")}"`:""}>${o.r}</text>
    <text x="${o.v<1?x1-4:x1+4}" y="${y+rh/2+4}" text-anchor="${o.v<1?"end":"start"}" style="fill:${cv("--text")}">${f2(o.v)}</text></g>`});
  $("rang").innerHTML=h+"</svg>";
  $("rang").querySelectorAll(".bar").forEach(g=>{g.onmousemove=e=>showTip(e,`<b>${g.dataset.r}</b><br>IPS ${f2(valReg(g.dataset.r,st.yi))}`);g.onmouseleave=hideTip;
    g.onclick=()=>{st.reg=g.dataset.r===st.reg?"":g.dataset.r;$("region").value=st.reg;draw()}});
}

function ligne(elId,lgId,series,opts){
  opts=opts||{};const W=520,H=250,m={l:40,r:112,t:12,b:30},labs=opts.labels||D.years.map(ya),n=labs.length;
  const step=opts.step||0.02,fmt=opts.fmt||f2,ref=opts.ref===undefined?1:opts.ref;
  const vs=series.flatMap(s=>s.vals).filter(v=>v!=null);
  let lo=Math.min(...vs,...(ref==null?[]:[ref]))-step/2,hi=Math.max(...vs,...(ref==null?[]:[ref]))+step/2;lo=Math.floor(lo/step)*step;hi=Math.ceil(hi/step)*step;
  const ng=Math.round((hi-lo)/step);
  const X=i=>m.l+i*(W-m.l-m.r)/(n-1),Y=v=>m.t+(hi-v)/(hi-lo)*(H-m.t-m.b);
  let h=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${opts.label||"Courbes d'IPS"}">`;
  for(let k=0;k<=ng;k++){const t=lo+k*step;if(ng>12&&k%2)continue;h+=`<line x1="${m.l}" x2="${W-m.r}" y1="${Y(t)}" y2="${Y(t)}" stroke="${cv("--grid")}"/><text x="${m.l-6}" y="${Y(t)+4}" text-anchor="end">${fmt(t)}</text>`}
  if(ref!=null)h+=`<line x1="${m.l}" x2="${W-m.r}" y1="${Y(ref)}" y2="${Y(ref)}" stroke="${cv("--text2")}" stroke-dasharray="4 3"/>`;
  labs.forEach((lb,i)=>{if(opts.pas?(i%opts.pas===0||i===n-1):(opts.labels||i%3===0))h+=`<text x="${X(i)}" y="${H-10}" text-anchor="middle">${lb}</text>`});
  if(opts.fill){const a=opts.fill[0],b=opts.fill[1];let top="",bot="";
    for(let i=0;i<n;i++){if(a[i]!=null&&b[i]!=null){top+=(top?"L":"M")+X(i)+","+Y(a[i]);}}
    for(let i=n-1;i>=0;i--){if(a[i]!=null&&b[i]!=null){bot+="L"+X(i)+","+Y(b[i]);}}
    h+=`<path d="${top}${bot}Z" fill="${cv("--grid")}" opacity=".8"/>`}
  const lab=[];
  series.forEach(s=>{let d="";s.vals.forEach((v,i)=>{if(v!=null)d+=(d?"L":"M")+X(i)+","+Y(v)});
    h+=`<path d="${d}" fill="none" stroke="${s.color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" ${s.dash?'stroke-dasharray="6 4"':""}/>`;
    let k=n-1;while(k>0&&s.vals[k]==null)k--;if(s.vals[k]!=null){h+=`<circle cx="${X(k)}" cy="${Y(s.vals[k])}" r="4" fill="${s.color}" stroke="${cv("--surface")}" stroke-width="2"/>`;if(!s.nolab)lab.push({y:Y(s.vals[k]),t:`${s.short||s.name} ${fmt(s.vals[k])}`,x:X(k)})}});
  lab.sort((a,b)=>a.y-b.y);for(let i=1;i<lab.length;i++)if(lab[i].y-lab[i-1].y<13)lab[i].y=lab[i-1].y+13;
  lab.forEach(l=>h+=`<text x="${l.x+8}" y="${l.y+4}" style="fill:${cv("--text")}">${l.t}</text>`);
  h+=`<line id="${elId}x" y1="${m.t}" y2="${H-m.b}" stroke="${cv("--text2")}" opacity="0" /><rect id="${elId}h" x="${m.l}" y="${m.t}" width="${W-m.l-m.r}" height="${H-m.t-m.b}" fill="transparent"/></svg>`;
  $(elId).innerHTML=h;
  $(lgId).innerHTML=series.length>1?series.map(s=>`<span><i class="sw" style="background:${s.color}"></i>${s.name}</span>`).join(""):"";
  const hit=$(elId+"h"),xl=$(elId+"x");
  hit.onmousemove=e=>{const bb=hit.getBoundingClientRect(),i=Math.max(0,Math.min(n-1,Math.round((e.clientX-bb.left)/bb.width*(n-1))));
    xl.setAttribute("x1",X(i));xl.setAttribute("x2",X(i));xl.setAttribute("opacity",".6");
    showTip(e,`<b>${labs[i]}</b>`+series.map(s=>`<br><i class="sw" style="background:${s.color}"></i>${s.name} : ${fmt(s.vals[i])}`).join(""))};
  hit.onmouseleave=()=>{hideTip();xl.setAttribute("opacity","0")};
}

function courbes(){
  $("tEvo").textContent=`${NOMS[st.niv]} : évolution de l'IPS`;
  const s=[{name:"National",short:"National",color:cv("--s1"),vals:natS()}];
  if(st.reg)s.push({name:st.reg,short:st.reg,color:cv("--s2"),vals:serie()[st.reg],dash:false});
  ligne("evo","lgEvo",s,{label:"Évolution de l'IPS national et de la région choisie"});
  ligne("mil","lgMil",[{name:"Urbain",color:cv("--s2"),vals:D.mil.urbain},{name:"Rural",color:cv("--s3"),vals:D.mil.rural}],{fill:[D.mil.urbain,D.mil.rural],label:"IPS urbain et rural"});
  ligne("sta","lgSta",[{name:"Public",color:cv("--s1"),vals:D.sta.public},{name:"Privé",color:cv("--s2"),vals:D.sta.prive}],{label:"IPS public et privé"});
}

function tableau(){
  const rs=rows(st.yi).reverse();
  $("tab").innerHTML=`<table><thead><tr><th>Ancienne région</th><th>IPS ${ya(D.years[st.yi])}</th><th>IPS ${ya(D.years[0])}</th><th>Variation</th></tr></thead><tbody>`+
   rs.map(o=>{const v0=valReg(o.r,0);return `<tr><td>${o.r}</td><td>${f2(o.v)}</td><td>${f2(v0)}</td><td>${v0==null?"n.d.":(o.v-v0>=0?"+":"")+f2(o.v-v0)}</td></tr>`}).join("")+
   `<tr><td><b>National</b></td><td>${f2(natS()[st.yi])}</td><td>${f2(natS()[0])}</td><td>${(natS()[st.yi]-natS()[0]>=0?"+":"")+f2(natS()[st.yi]-natS()[0])}</td></tr></tbody></table>`;
}
/* ---------- niveau province ---------- */
const pst={m:"effectif_dernier_sur_max",p:""};
const MES={effectif_dernier_sur_max:"Accès : effectifs en % du maximum depuis 2015",ips_ensemble:"IPS, ensemble des élèves",ips_urbain:"IPS, milieu urbain",ips_rural:"IPS, milieu rural",ecart_urbain_moins_rural:"Écart d'IPS urbain − rural"};
const isEc=()=>pst.m==="ecart_urbain_moins_rural", isAcc=()=>pst.m==="effectif_dernier_sur_max";
const pval=n=>D.prov.ind[n][pst.m];
const pcol=v=>v==null?cv("--grid"):(isAcc()?colorFor(0.85+0.15*Math.min(1,v)):isEc()?colorFor(1-v):colorFor(v));
const pfmt=v=>isAcc()?pc1(v):isEc()?f3(v):f2(v);
const pSel=n=>{pst.p=n;$("pprov").value=n;provDraw()};
function provMap(){
  $("tpCarte").textContent=`${MES[pst.m]}, par ancienne province`;
  let h=`<svg viewBox="${D.prov.vb.join(" ")}" role="img" aria-label="Carte des anciennes provinces colorée par ${MES[pst.m]}"><g class="reg">`;
  D.prov.geo.forEach(g=>{h+=`<path data-p="${g.name}" class="${g.name===pst.p?"sel":""}" d="${g.d}" fill="${pcol(pval(g.name))}"/>`});
  h+="</g></svg>";
  const L=isAcc()?["0 % (élèves perdus)","50 %","100 % (maximum)"]:isEc()?["+0,15 (rural moins paritaire)","0","−0,15 (rural plus paritaire)"]:["0,85 (moins de filles)","1,00","1,15 (plus de filles)"];
  const G=isAcc()?[colorFor(0.85),colorFor(0.925),colorFor(1)]:[colorFor(0.85),colorFor(1),colorFor(1.15)];
  h+=`<svg viewBox="0 0 300 36" role="img" aria-label="Légende"><defs><linearGradient id="lgp"><stop offset="0" stop-color="${G[0]}"/><stop offset=".5" stop-color="${G[1]}"/><stop offset="1" stop-color="${G[2]}"/></linearGradient></defs>
  <rect x="10" y="4" width="280" height="10" rx="3" fill="url(#lgp)"/><text x="10" y="30">${L[0]}</text><text x="150" y="30" text-anchor="middle">${L[1]}</text><text x="290" y="30" text-anchor="end">${L[2]}</text></svg>`;
  $("pcarte").innerHTML=h;
  $("pcarte").querySelectorAll("path").forEach(p=>{
    p.onmousemove=e=>{const n=p.dataset.p,i=D.prov.ind[n];showTip(e,`<b>${n}</b> (${i.region})<br>effectifs : ${pc1(i.effectif_dernier_sur_max)} du maximum<br>IPS ensemble ${f2(i.ips_ensemble)}<br>urbain ${f2(i.ips_urbain)} · rural ${f2(i.ips_rural)}<br>écart urbain − rural ${f3(i.ecart_urbain_moins_rural)}`)};
    p.onmouseleave=hideTip;p.onclick=()=>pSel(p.dataset.p)});
}
function provRank(){
  $("tpRang").textContent=`Classement des provinces : ${MES[pst.m]}`;
  const ns=D.prov.names.filter(n=>pval(n)!=null).sort((a,b)=>pval(a)-pval(b));if(isEc())ns.reverse();
  const A=isAcc(),W=520,rh=17,m={l:132,r:44,t:6,b:22},H=m.t+m.b+ns.length*rh,c=A?0:isEc()?0:1,lo=A?0:isEc()?-0.1:0.75,hi=A?1:isEc()?0.15:1.15;
  const x=v=>m.l+(Math.max(lo,Math.min(hi,v))-lo)/(hi-lo)*(W-m.l-m.r);
  let h=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Classement des provinces">`;
  const ticks=A?[0,0.2,0.4,0.6,0.8,1]:isEc()?[-0.1,-0.05,0,0.05,0.1,0.15]:[0.75,0.85,0.95,1,1.05,1.15];
  ticks.forEach(t=>{h+=`<line x1="${x(t)}" x2="${x(t)}" y1="${m.t}" y2="${H-m.b}" stroke="${cv("--grid")}" stroke-width="${t===c||(A&&t===0.6)?1.5:1}"/><text x="${x(t)}" y="${H-6}" text-anchor="middle">${A?pc1(t):f2(t)}</text>`});
  ns.forEach((n,i)=>{const v=pval(n),y=m.t+i*rh,sel=n===pst.p,bad=A?v<0.6:isEc()?v>0:v<1,col=bad?cv("--dlow"):(A?cv("--muted"):cv("--dhigh")),x0=x(c),x1=x(v),left=!A&&(bad&&!isEc()||(isEc()&&v<0));
    h+=`<g class="bar" data-p="${n}"><rect x="0" y="${y}" width="${W}" height="${rh}" fill="transparent"/>
    <rect x="${Math.min(x0,x1)}" y="${y+3}" width="${Math.max(1,Math.abs(x1-x0))}" height="${rh-6}" rx="2" fill="${col}" ${sel?`stroke="${cv("--text")}" stroke-width="1.5"`:""}/>
    <text x="${m.l-6}" y="${y+rh/2+4}" text-anchor="end" style="font-size:10.5px;${sel?`font-weight:700;fill:${cv("--text")}`:""}">${n}</text>
    <text x="${left?x1-3:x1+3}" y="${y+rh/2+4}" text-anchor="${left?"end":"start"}" style="font-size:10px;fill:${cv("--text")}">${pfmt(v)}</text></g>`});
  $("prang").innerHTML=h+"</svg>";
  $("prang").querySelectorAll(".bar").forEach(g=>{g.onmousemove=e=>{const i=D.prov.ind[g.dataset.p];showTip(e,`<b>${g.dataset.p}</b> (${i.region})<br>effectifs : ${pc1(i.effectif_dernier_sur_max)} du maximum<br>IPS ensemble ${f2(i.ips_ensemble)}<br>urbain ${f2(i.ips_urbain)} · rural ${f2(i.ips_rural)}`)};g.onmouseleave=hideTip;g.onclick=()=>pSel(g.dataset.p)});
}
function provLines(){
  const n=pst.p,rg=D.prov.ind[n].region;
  $("tpEvo").textContent=`IPS du primaire : ${n}, sa région et le national`;
  ligne("pevo","lgPEvo",[{name:"National",short:"National",color:cv("--s1"),vals:D.nat.pri},{name:"Région "+rg,short:rg,color:cv("--s3"),vals:D.pri[rg]||[]},{name:n,short:n,color:cv("--s2"),vals:D.prov.hist[n]}],{label:"IPS de la province, de sa région et du national"});
  const O=D.prov.ordre.slice(0,6),u=O.map(c=>D.prov.classes.urbain[c].ips),r=O.map(c=>D.prov.classes.rural[c].ips);
  ligne("pcl","lgPCl",[{name:"Urbain",color:cv("--s2"),vals:u},{name:"Rural",color:cv("--s3"),vals:r}],{labels:O,fill:[u,r],label:"IPS par classe, urbain et rural"});
  if(D.prov.eff[n]){$("tpEff").textContent=`Accès : effectifs du primaire, ${n} (% du maximum)`;
    const se=[{name:n,short:n,color:cv("--s2"),vals:D.prov.eff[n]}];if(D.prov.effNat)se.unshift({name:"Burkina Faso",short:"National",color:cv("--s1"),vals:D.prov.effNat});
    ligne("peff","lgPEff",se,{step:0.1,fmt:pc1,ref:null,label:"Effectifs du primaire en part du maximum"})}
}
const nbf=v=>v==null?"n.d.":Math.round(v).toLocaleString("fr-FR");
const sim={ips:0.95,acc:0.6};
function prioCalc(){   // regle de priorite recalculee en direct avec les seuils du simulateur
  return D.prov.names.map(n=>{const i=D.prov.ind[n],ip=D.prov.hist[n][N-1],c1=ip!=null&&ip<sim.ips,c2=i.effectif_dernier_sur_max!=null&&i.effectif_dernier_sur_max<sim.acc;
    return {n,i,ip,p:c1&&c2?1:(c1||c2?2:0)}}).filter(o=>o.p).sort((a,b)=>a.p-b.p||a.ip-b.ip);
}
function provPrio(){
  $("sIpsL").textContent=f2(sim.ips);$("sAccL").textContent=pc1(sim.acc);
  const L=prioCalc(),p1=L.filter(o=>o.p===1),s=(arr,k)=>arr.reduce((t,o)=>t+(o.i[k]||0),0);
  const pl=(n,mot)=>`<b>${nbf(n)}</b> ${mot}${n>1?"s":""}`;
  $("sMsg").innerHTML=`${pl(p1.length,"province")} en priorité 1 et ${pl(L.length-p1.length,"province")} en priorité 2. `+
    (p1.length?`Priorité 1 : ${pl(s(p1,"eleves_perdus_depuis_max"),"élève")} perdu${s(p1,"eleves_perdus_depuis_max")>1?"s":""} depuis leur meilleure année, ${pl(s(p1,"filles_manquantes_parite"),"fille")} à inscrire en plus pour atteindre la parité.`
     :"Aucune province ne franchit les deux seuils à la fois.");
  $("pprio").innerHTML=`<table><thead><tr><th>Province</th><th>Prio.</th><th>IPS</th><th>Effectifs</th><th>Élèves perdus</th><th>Projection ${D.prov.prevAns?ya(D.prov.prevAns.at(-1)):""}</th></tr></thead><tbody>`+
   L.map(o=>{const pv=D.prov.prev[o.n],k=pv?pv.v.length-1:0;return `<tr data-p="${o.n}" style="cursor:pointer${o.n===pst.p?";font-weight:700":""}"><td>${o.n} <span class="sub">(${o.i.region})</span></td><td>${o.p}</td><td>${f2(o.ip)}</td><td>${pc1(o.i.effectif_dernier_sur_max)}</td><td>${nbf(o.i.eleves_perdus_depuis_max)}</td><td>${pv&&pv.v[k]!=null?f2(pv.v[k])+" ["+f2(pv.lo[k])+" ; "+f2(pv.hi[k])+"]":"n.d."}</td></tr>`}).join("")+"</tbody></table>";
  $("pprio").querySelectorAll("tr[data-p]").forEach(t=>t.onclick=()=>pSel(t.dataset.p));
  dCarteDraw(L);dFicheDraw();
  majLien();
}
/* ---------- 17 regions actuelles ---------- */
const rst={m:"effectif_dernier_sur_max",r:""};
function RMcfg(){const vs=D.r17.names.map(n=>D.r17.ind[n][rst.m]).filter(v=>v!=null),mx=Math.max(1,...vs);return {
  effectif_dernier_sur_max:{lib:"Accès : effectifs en % du maximum depuis 2015",fmt:pc1,col:v=>colorFor(0.85+0.15*Math.min(1,v)),lo:0,hi:1,ref:0,bad:v=>v<0.6,asc:true},
  ips:{lib:"IPS, ensemble des élèves",fmt:f2,col:colorFor,lo:0.8,hi:1.1,ref:1,bad:v=>v<1,asc:true},
  ips_rural:{lib:"IPS, milieu rural",fmt:f2,col:colorFor,lo:0.8,hi:1.1,ref:1,bad:v=>v<1,asc:true},
  ecart_urbain_moins_rural:{lib:"Écart d'IPS urbain − rural",fmt:f3,col:v=>colorFor(1-v),lo:-0.05,hi:0.15,ref:0,bad:v=>v>0,asc:false},
  eleves_perdus_depuis_max:{lib:"Élèves perdus depuis la meilleure année",fmt:nbf,col:v=>colorFor(1-0.15*v/mx),lo:0,hi:mx,ref:0,bad:v=>v>0,asc:false},
  filles_manquantes_parite:{lib:"Filles à inscrire en plus pour la parité",fmt:nbf,col:v=>colorFor(1-0.15*v/mx),lo:0,hi:mx,ref:0,bad:v=>v>0,asc:false}}[rst.m]}
function r17Draw(){
  const C=RMcfg(),R=D.r17,val=n=>R.ind[n][rst.m];
  $("trCarte").textContent=`${C.lib}, par région actuelle`;
  let h=`<svg viewBox="${R.vb.join(" ")}" role="img" aria-label="Carte des 17 régions actuelles"><g class="reg">`;
  R.geo.forEach(g=>{const v=R.ind[g.name]?val(g.name):null;h+=`<path data-r="${g.name}" class="${g.name===rst.r?"sel":""}" d="${g.d}" fill="${v==null?cv("--grid"):C.col(v)}"/>`});
  $("rcarte").innerHTML=h+"</g></svg>";
  const ns=R.names.filter(n=>val(n)!=null).sort((a,b)=>C.asc?val(a)-val(b):val(b)-val(a));
  const W=520,rh=22,m={l:100,r:60,t:6,b:22},H=m.t+m.b+ns.length*rh,x=v=>m.l+(Math.max(C.lo,Math.min(C.hi,v))-C.lo)/(C.hi-C.lo)*(W-m.l-m.r);
  $("trRang").textContent=`Classement des 17 régions : ${C.lib.toLowerCase()}`;
  let b=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Classement des régions actuelles"><line x1="${x(C.ref)}" x2="${x(C.ref)}" y1="${m.t}" y2="${H-m.b}" stroke="${cv("--text2")}"/>`;
  ns.forEach((n,i)=>{const v=val(n),y=m.t+i*rh,x0=x(C.ref),x1=x(v),sel=n===rst.r;
    b+=`<g class="bar" data-r="${n}"><rect x="0" y="${y}" width="${W}" height="${rh}" fill="transparent"/><rect x="${Math.min(x0,x1)}" y="${y+5}" width="${Math.max(1,Math.abs(x1-x0))}" height="${rh-10}" rx="3" fill="${C.bad(v)?cv("--dlow"):cv("--dhigh")}" ${sel?`stroke="${cv("--text")}" stroke-width="1.5"`:""}/>
    <text x="${m.l-6}" y="${y+rh/2+4}" text-anchor="end" style="${sel?`font-weight:700;fill:${cv("--text")}`:""}">${n}</text><text x="${Math.max(x0,x1)+4}" y="${y+rh/2+4}" style="fill:${cv("--text")}">${C.fmt(v)}</text></g>`});
  $("rrang").innerHTML=b+"</svg>";
  const tipR=(e,n)=>{const i=R.ind[n];showTip(e,`<b>${n}</b> (ancienne région : ${i.old})<br>provinces : ${i.prov}<br>${nbf(i.eff)} élèves · effectifs ${pc1(i.effectif_dernier_sur_max)} du maximum<br>IPS ${f2(i.ips)} · rural ${f2(i.ips_rural)}<br>élèves perdus ${nbf(i.eleves_perdus_depuis_max)} · filles manquantes ${nbf(i.filles_manquantes_parite)}`)};
  document.querySelectorAll("#rcarte path,#rrang .bar").forEach(el=>{el.onmousemove=e=>tipR(e,el.dataset.r);el.onmouseleave=hideTip;el.onclick=()=>{rst.r=el.dataset.r===rst.r?"":el.dataset.r;r17Draw()}});
  const tot=k=>R.names.reduce((t,n)=>t+(R.ind[n][k]||0),0),w=ns[0];
  $("rmsg").textContent=`${C.lib} : la situation la plus défavorable est ${w} (${C.fmt(val(w))}). Sur les 17 régions : ${nbf(tot("eleves_perdus_depuis_max"))} élèves perdus depuis la meilleure année de chaque région, ${nbf(tot("filles_manquantes_parite"))} filles à inscrire en plus pour atteindre la parité.`+
    (rst.r?` ${rst.r} : ${R.ind[rst.r].prov} (ancienne région ${R.ind[rst.r].old}).`:"");
  majLien();
}
function provMsg(){
  const arr=D.prov.names.map(n=>[n,pval(n)]).filter(x=>x[1]!=null).sort((a,b)=>a[1]-b[1]);
  const ec=D.prov.names.map(n=>D.prov.ind[n].ecart_urbain_moins_rural).filter(v=>v!=null).sort((a,b)=>a-b),med=ec[Math.floor(ec.length/2)];
  const t=D.prov.classes.public_prive.Total;
  const p0=pst.p,ip=D.prov.ind[p0],pv=D.prov.prev[p0],k=pv?pv.v.length-1:0,sg=D.prov.sig.filter(s=>s.province===p0);
  const ps=`${p0} : effectifs à ${pc1(ip.effectif_dernier_sur_max)} de leur maximum (${nbf(ip.eleves_perdus_depuis_max)} élèves perdus), IPS ${f2(ip.ips_ensemble)} (${nbf(ip.filles_manquantes_parite)} filles à inscrire en plus pour la parité)`+
    (pv&&pv.v[k]!=null?` ; projection ${ya(D.prov.prevAns[k])} si la situation actuelle se prolonge : ${f2(pv.v[k])} (8 fois sur 10 entre ${f2(pv.lo[k])} et ${f2(pv.hi[k])}) - ${pv.statut}.`:".")+
    (sg.length?` IPS non interprétable en ${sg.map(s=>ya(s.annee_debut)+" ("+s.effectif_total+" élèves)").join(", ")} : point retiré de la courbe.`:"");
  if(isAcc()){$("pmsg").textContent=`${arr.filter(x=>x[1]<0.6).length} provinces sur ${arr.length} ont moins de 60 % de leur effectif maximum ; les plus touchées : ${arr.slice(0,4).map(x=>x[0]+" "+pc1(x[1])).join(", ")}. `+ps;return}
  const a=isEc()?`Écart urbain − rural : médiane ${f3(med)} ; l'IPS rural est plus bas que l'urbain dans ${ec.filter(v=>v>0).length} provinces sur ${ec.length}. Plus fort écart : ${arr[arr.length-1][0]} (${f3(arr[arr.length-1][1])}).`
    :`${MES[pst.m]} : de ${f2(arr[0][1])} (${arr[0][0]}) à ${f2(arr[arr.length-1][1])} (${arr[arr.length-1][0]}) ; ${arr.filter(x=>x[1]<1).length} provinces sur ${arr.length} sont sous la parité, ${arr.filter(x=>x[1]<0.95).length} sous 0,95.`;
  $("pmsg").textContent=a+` Taux de redoublement national : filles ${f3(t.trf)}, garçons ${f3(t.trg)}. `+ps;
}
function provTab(){
  const rows=D.prov.names.slice().sort((a,b)=>(D.prov.ind[a].ips_ensemble??9)-(D.prov.ind[b].ips_ensemble??9));
  $("ptab").innerHTML=`<h2 style="margin-top:16px">Provinces (primaire, ${D.prov.annee})</h2><table><thead><tr><th>Province</th><th>Ancienne région</th><th>IPS ${ya(D.years[0])}</th><th>IPS ${ya(D.years[N-1])}</th><th>IPS urbain</th><th>IPS rural</th><th>Écart U − R</th><th>Redoublt F − G</th></tr></thead><tbody>`+
   rows.map(n=>{const i=D.prov.ind[n],h=D.prov.hist[n];return `<tr><td>${n}</td><td>${i.region}</td><td>${f2(h[0])}</td><td>${f2(h[N-1])}</td><td>${f2(i.ips_urbain)}</td><td>${f2(i.ips_rural)}</td><td>${f3(i.ecart_urbain_moins_rural)}</td><td>${f3(i.ecart_redoublement_filles_moins_garcons)}</td></tr>`}).join("")+"</tbody></table>";
}
function provDraw(){provMap();provRank();provLines();provMsg();provTab();provPrio();majLien()}
/* ---------- acces (taux DGESS par region) ---------- */
const ast={i:"tbs_primaire"};
function accDraw(){
  const A=D.acc[ast.i],z=A.z,i=st.yi,yr=ya(D.years[i]);
  const rs=D.regions.filter(r=>z[r]&&z[r].t[i]!=null).sort((a,b)=>z[a].t[i]-z[b].t[i]);
  const all=["National",...rs.slice().reverse()],W=520,rh=22,m={l:118,r:40,t:6,b:22},H=m.t+m.b+all.length*rh;
  const mx=Math.max(120,...all.flatMap(r=>[z[r].g[i],z[r].f[i]]).filter(v=>v!=null)),x=v=>m.l+v/mx*(W-m.l-m.r);
  $("taRang").textContent=`${A.lib}, ${yr} : garçons et filles par région`;
  $("lgARang").innerHTML=`<span><i class="sw" style="background:${cv("--s1")}"></i>Garçons</span><span><i class="sw" style="background:${cv("--s2")}"></i>Filles</span>`;
  let h=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${A.lib} par région, garçons et filles">`;
  for(let t=0;t<=mx;t+=20)h+=`<line x1="${x(t)}" x2="${x(t)}" y1="${m.t}" y2="${H-m.b}" stroke="${cv("--grid")}" stroke-width="${t===100?1.5:1}"/><text x="${x(t)}" y="${H-6}" text-anchor="middle">${t} %</text>`;
  all.forEach((r,j)=>{const y=m.t+j*rh+rh/2,g=z[r].g[i],f=z[r].f[i],sel=r===st.reg||(r==="National"&&!st.reg),b=r==="National";if(g==null||f==null)return;
    h+=`<g class="bar" data-r="${r}"><rect x="0" y="${y-rh/2}" width="${W}" height="${rh}" fill="transparent"/><line x1="${x(g)}" x2="${x(f)}" y1="${y}" y2="${y}" stroke="${cv("--muted")}" stroke-width="3"/>
    <circle cx="${x(g)}" cy="${y}" r="5" fill="${cv("--s1")}"/><circle cx="${x(f)}" cy="${y}" r="5" fill="${cv("--s2")}"/>
    <text x="${m.l-8}" y="${y+4}" text-anchor="end" style="${b||sel?`font-weight:700;fill:${cv("--text")}`:""}">${r}</text>
    <text x="${x(Math.max(g,f))+9}" y="${y+4}" style="fill:${cv("--text")}">${pc(z[r].t[i])}</text></g>`});
  $("arang").innerHTML=h+"</svg>";
  $("arang").querySelectorAll(".bar").forEach(gq=>{const r=gq.dataset.r;gq.onmousemove=e=>showTip(e,`<b>${r}</b><br>garçons ${pc(z[r].g[i])} · filles ${pc(z[r].f[i])}<br>ensemble ${pc(z[r].t[i])} · écart F − G ${(z[r].f[i]-z[r].g[i]>=0?"+":"")+Math.round(z[r].f[i]-z[r].g[i])} pts`);gq.onmouseleave=hideTip;
    gq.onclick=()=>{if(r==="National")return;st.reg=r===st.reg?"":r;$("region").value=st.reg;draw()}});
  const zr=st.reg&&z[st.reg]?st.reg:"National";
  $("taEvo").textContent=`${A.lib} : évolution, ${zr}`;
  const se=[{name:"Garçons "+zr,short:"Garçons",color:cv("--s1"),vals:z[zr].g},{name:"Filles "+zr,short:"Filles",color:cv("--s2"),vals:z[zr].f}];
  if(zr!=="National")se.push({name:"Ensemble national",short:"National",color:cv("--muted"),vals:z.National.t});
  ligne("aevo","lgAEvo",se,{step:10,fmt:pc,ref:null,label:"Évolution du taux, garçons et filles"});
  const lo=rs[0],hi=rs[rs.length-1],n=z.National;
  $("amsg").textContent=`${A.lib}, ${yr} : de ${pc(z[lo].t[i])} (${lo}) à ${pc(z[hi].t[i])} (${hi}) ; national ${pc(n.t[i])} (${ya(D.years[0])} : ${pc(n.t[0])}). `+
    `Écart filles − garçons au niveau national : ${(n.f[i]-n.g[i]>=0?"+":"")+(n.f[i]-n.g[i]).toFixed(1).replace(".",",")} point(s). L'écart entre régions dépasse de loin l'écart entre filles et garçons.`;
  majLien();
}
/* ---------- onglets : Analyse, Tableau de bord, Carte, Aide a la decision, Prevision ---------- */
const ONG=["accueil","analyse","tdb","carte","decision","prevision","methode"];let ong="accueil";
function montrer(o){if(!ONG.includes(o))o="accueil";ong=o;document.querySelectorAll("[data-onglet]").forEach(d=>d.hidden=d.dataset.onglet!==o);
  document.querySelectorAll("#onglets button").forEach(b=>{const on=b.dataset.o===o;b.setAttribute("aria-selected",on?"true":"false");b.tabIndex=on?0:-1;if(on)b.scrollIntoView({block:"nearest",inline:"nearest"})});majLien()}
const aller=(o,id)=>{montrer(o);const el=id&&$(id);if(el)el.scrollIntoView({behavior:"smooth",block:"start"});else window.scrollTo({top:0})};
document.querySelectorAll("#onglets button").forEach(b=>b.onclick=()=>aller(b.dataset.o));
$("onglets").addEventListener("keydown",e=>{const i=ONG.indexOf(ong),k={ArrowRight:1,ArrowLeft:-1}[e.key];if(e.key==="Home"||e.key==="End"||k){e.preventDefault();
  const j=e.key==="Home"?0:e.key==="End"?ONG.length-1:(i+k+ONG.length)%ONG.length;montrer(ONG[j]);document.querySelector(`#onglets [data-o="${ONG[j]}"]`).focus()}});
document.querySelectorAll(".guide li").forEach(li=>{li.tabIndex=0;li.onclick=()=>aller(li.dataset.go);li.onkeydown=e=>{if(e.key==="Enter")aller(li.dataset.go)}});
const dbar=(v,max,txt,col)=>v==null?"n.d.":`<span class="db"><i style="width:${Math.max(2,Math.min(100,v/max*100))}%;background:${col||cv("--dlow")}"></i><b>${txt}</b></span>`;
function spark(vals,col,ref){const w=220,h=40,v=vals.map((x,i)=>[i,x]).filter(p=>p[1]!=null);if(v.length<2)return "";
  let lo=Math.min(...v.map(p=>p[1])),hi=Math.max(...v.map(p=>p[1]));if(ref!=null){lo=Math.min(lo,ref);hi=Math.max(hi,ref)}if(hi-lo<1e-9){hi+=1e-3;lo-=1e-3}
  const X=i=>4+i*(w-8)/(vals.length-1),Y=x=>h-5-(x-lo)/(hi-lo)*(h-10),d=v.map((p,k)=>(k?"L":"M")+X(p[0]).toFixed(1)+","+Y(p[1]).toFixed(1)).join(""),l=v.at(-1);
  return `<svg viewBox="0 0 ${w} ${h}" aria-hidden="true">${ref!=null?`<line x1="4" x2="${w-4}" y1="${Y(ref)}" y2="${Y(ref)}" stroke="${cv("--grid")}" stroke-dasharray="3 3"/>`:""}<path d="${d}" fill="none" stroke="${col}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/><circle cx="${X(l[0])}" cy="${Y(l[1])}" r="3.5" fill="${col}"/></svg>`}
/* ----- Accueil : la reponse au Defi 2 en une page ----- */
function homeDraw(){const N1=N-1,y0=ya(D.years[0]),y1=ya(D.years[N1]),R=[];let lead=[];
  if(D.acc&&D.acc.tbs_primaire){const z=D.acc.tbs_primaire.z,rs=D.regions.filter(r=>z[r]&&z[r].t[N1]!=null).sort((a,b)=>z[a].t[N1]-z[b].t[N1]),lo=rs[0],hi=rs.at(-1);
    R.push({q:"Où ?",tag:["Écart territorial","alerte"],big:`${pc(z[lo].t[N1])} à ${pc(z[hi].t[N1])}`,txt:`Taux brut de scolarisation du primaire en ${y1} : ${lo} contre ${hi}. National : ${pc(z.National.t[N1])} (${pc(z.National.t[0])} en ${y0}).`,
      sp:spark(z.National.t,cv("--dlow"),100),go:["carte","r17Sec"],bt:"Voir la carte"});
    lead.push(`Les écarts les plus grands sont territoriaux : ${pc(z[lo].t[N1])} d'enfants scolarisés au ${lo}, ${pc(z[hi].t[N1])} au ${hi}.`)}
  const n0=D.nat.pri[0],n1=D.nat.pri[N1];let pire="";
  if(D.prov){const H=n=>D.prov.hist[n][N1],ip=D.prov.names.filter(n=>H(n)!=null).sort((a,b)=>H(a)-H(b));pire=` Province la plus éloignée : ${ip[0]} (${f2(H(ip[0]))}).`}
  R.push({q:"Filles-garçons",tag:[n1>=0.97?"Presque à parité":"Écart persistant",n1>=0.97?"ok":"alerte"],big:`IPS ${f2(n1)}`,txt:`Au primaire en ${y1}, contre ${f2(n0)} en ${y0}.${pire}`,sp:spark(D.nat.pri,cv("--s1"),1),go:["tdb"],bt:"Voir l'évolution"});
  lead.push(`L'écart filles-garçons se réduit au niveau national (IPS ${f2(n0)} → ${f2(n1)}) mais reste fort dans plusieurs provinces.`);
  const gap=D.mil.urbain.map((u,i)=>u!=null&&D.mil.rural[i]!=null?u-D.mil.rural[i]:null),g1=gap[N1]!=null?gap[N1]:gap.filter(x=>x!=null).at(-1);
  const ur=D.prov?D.prov.names.filter(n=>D.prov.ind[n].ecart_urbain_moins_rural>0).length:null;
  R.push({q:"Ville-campagne",tag:[g1<gap[0]?"Se resserre":"S'élargit",g1<gap[0]?"ok":"alerte"],big:`${f3(g1)} pt`,txt:`Écart d'IPS entre ville et campagne (${f3(gap[0])} en ${y0}).`+(ur!=null?` À la campagne, la parité est plus faible dans ${ur} provinces sur ${D.prov.names.length}.`:""),
    sp:spark(gap,cv("--s3"),0),go:["carte","provSec"],bt:"Voir par province",pm:"ecart_urbain_moins_rural"});
  lead.push(`Entre ville et campagne, l'écart se resserre (${f3(gap[0])} → ${f3(g1)}), mais la campagne reste en retard presque partout.`);
  if(D.prov&&D.prov.prevAns){const P=D.prov.prev,so=Object.keys(P).filter(n=>/^sous/.test(P[n].statut)),an=ya(D.prov.prevAns.at(-1));
    R.push({q:"Et demain ?",tag:["Projection","alerte"],big:`${so.length} provinces`,txt:`resteraient sous un IPS de 0,95 en ${an} si rien ne change, même dans le scénario haut.`,sp:"",go:["prevision"],bt:"Voir la prévision"});
    lead.push(`Sans action, ${so.length} provinces resteraient loin de la parité en ${an}.`)}
  $("hRep").textContent=lead.join(" ");
  $("hReps").innerHTML=R.map((r,i)=>`<section class="card rep"><p class="eyebrow" style="margin:0">${r.q}</p><span class="tag ${r.tag[1]}">${r.tag[0]}</span><div class="big">${r.big}</div>${r.sp}<div class="txt">${r.txt}</div><button type="button" class="btn ghost go" data-i="${i}">${r.bt} →</button></section>`).join("");
  $("hReps").querySelectorAll(".go").forEach(b=>b.onclick=()=>{const r=R[+b.dataset.i];if(r.pm&&D.prov){pst.m=r.pm;$("pmes").value=r.pm;provDraw()}aller(r.go[0],r.go[1])});
  if(!D.prov)return;
  const pr={};D.prov.prio.forEach(r=>pr[r.province]=r.priorite);
  let h=`<svg viewBox="${D.prov.vb.join(" ")}" role="img" aria-label="Carte des provinces prioritaires"><g class="reg">`;
  D.prov.geo.forEach(g=>{const p=pr[g.name]||0;h+=`<path data-p="${g.name}" d="${g.d}" fill="${p===1?cv("--dlow"):p===2?cv("--s2"):cv("--grid")}"/>`});
  $("hCarte").innerHTML=h+"</g></svg>";
  const ouvrir=n=>{pSel(n);aller("decision")};
  $("hCarte").querySelectorAll("path").forEach(el=>{const n=el.dataset.p,i=D.prov.ind[n];el.onmousemove=e=>showTip(e,`<b>${n}</b> (${i.region})<br>${pr[n]?"Priorité "+pr[n]:"Hors priorité"}<br>IPS ${f2(D.prov.hist[n][N1])} · effectifs ${pc1(i.effectif_dernier_sur_max)} du maximum<br><i>Cliquer pour la fiche</i>`);el.onmouseleave=hideTip;el.onclick=()=>ouvrir(n)});
  const p1=D.prov.prio.filter(r=>r.priorite===1).map(r=>r.province),p2=D.prov.prio.filter(r=>r.priorite===2).map(r=>r.province);
  $("hP1").innerHTML=p1.map(n=>`<button type="button" class="chip p1" data-p="${n}">${n}</button>`).join("")+p2.slice(0,12).map(n=>`<button type="button" class="chip p2" data-p="${n}">${n}</button>`).join("");
  $("hP1").querySelectorAll(".chip").forEach(b=>b.onclick=()=>ouvrir(b.dataset.p));
  $("hP1n").textContent=`En rouge, les ${p1.length} provinces en priorité 1 ; en orange, ${Math.min(12,p2.length)} des ${p2.length} provinces en priorité 2. Cliquer une province pour sa fiche.`;
}
/* ----- telechargements CSV ----- */
function csv(nom,ent,lig){const q=v=>v==null?"":(typeof v==="number"?String(v).replace(".",","):`"${String(v).replace(/"/g,'""')}"`);
  const t="\ufeff"+[ent.join(";"),...lig.map(l=>l.map(q).join(";"))].join("\r\n"),u=URL.createObjectURL(new Blob([t],{type:"text/csv;charset=utf-8"})),a=document.createElement("a");
  a.href=u;a.download=nom;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),2000)}
const EQ="__EQUIPE__";
function telecharger(k){const N1=N-1;
  if(k==="regions"){csv(`${EQ}_IPS-regions.csv`,["region","niveau",...D.years.map(ya)],["pri","pre","cp1"].flatMap(nv=>[...D.regions.map(r=>[r,NOMS[nv],...D[nv][r]]),["National",NOMS[nv],...D.nat[nv]]]));return}
  if(!D.prov)return;const I=D.prov.ind,T={},PT={};(D.typo?D.typo.rows:[]).forEach(x=>T[x.p]=x);(D.ptbs?D.ptbs.rows:[]).forEach(x=>PT[x.p]=x);
  if(k==="provinces")csv(`${EQ}_provinces-indicateurs.csv`,["province","ancienne_region",`ips_${D.years[N1]}`,"ips_urbain","ips_rural","ecart_urbain_moins_rural","effectifs_sur_max","eleves_perdus","filles_a_inscrire_parite","tbs_insd","profil"],
    D.prov.names.map(n=>[n,I[n].region,D.prov.hist[n][N1],I[n].ips_urbain,I[n].ips_rural,I[n].ecart_urbain_moins_rural,I[n].effectif_dernier_sur_max,I[n].eleves_perdus_depuis_max,I[n].filles_manquantes_parite,PT[n]?PT[n].t:null,T[n]?T[n].g+". "+T[n].nom:null]));
  if(k==="priorites")csv(`${EQ}_provinces-prioritaires_IPS${sim.ips}_eff${sim.acc}.csv`,["province","ancienne_region","priorite","ips","effectifs_sur_max","eleves_perdus","filles_a_inscrire_parite","seuil_ips","seuil_effectifs"],
    prioCalc().map(o=>[o.n,o.i.region,o.p,o.ip,o.i.effectif_dernier_sur_max,o.i.eleves_perdus_depuis_max,o.i.filles_manquantes_parite,sim.ips,sim.acc]));
  if(k==="prevision"&&D.prov.prevAns){const A=D.prov.prevAns;csv(`${EQ}_prevision-ips.csv`,["province","modele","statut",...A.flatMap(y=>[`ips_${y}`,`bas80_${y}`,`haut80_${y}`])],
    Object.keys(D.prov.prev).map(n=>{const p=D.prov.prev[n];return [n,p.modele,p.statut,...A.flatMap((y,i)=>[p.v[i],p.lo[i],p.hi[i]])]}))}
}
document.querySelectorAll("[data-dl]").forEach(b=>b.onclick=()=>telecharger(b.dataset.dl));
$("dlTop").onclick=()=>aller("methode","telech");
$("cmdCopie").onclick=()=>{const t=$("cmd").textContent;(navigator.clipboard?navigator.clipboard.writeText(t):Promise.reject()).then(()=>{$("cmdCopie").textContent="Commande copiée";setTimeout(()=>$("cmdCopie").textContent="Copier la commande",1800)},()=>prompt("Copiez la commande :",t))};
const mini=(ent,lig,nG=1)=>{const G=i=>i<nG?' style="text-align:left"':"";return `<table class="mini"><thead><tr>${ent.map((h,i)=>`<th${G(i)}>${h}</th>`).join("")}</tr></thead><tbody>${lig.map(l=>`<tr>${l.map((c,i)=>`<td${G(i)}>${c}</td>`).join("")}</tr>`).join("")}</tbody></table>`};
/* ----- Analyse : constats calcules a partir des donnees ----- */
function anaDraw(){
  const N1=N-1,y0=ya(D.years[0]),y1=ya(D.years[N1]),k=[],K=[];
  if(D.acc&&D.acc.tbs_primaire){const z=D.acc.tbs_primaire.z,rs=D.regions.filter(r=>z[r]&&z[r].t[N1]!=null).sort((a,b)=>z[a].t[N1]-z[b].t[N1]),nt=z.National.t;
    K.push([pc(nt[N1]),`TBS primaire national en ${y1} (${y0} : ${pc(nt[0])})`]);
    k.push(`L'écart le plus fort est territorial. En ${y1}, le taux brut de scolarisation du primaire est de ${pc(z[rs[0]].t[N1])} (${rs[0]}) et ${pc(z[rs[1]].t[N1])} (${rs[1]}), contre ${pc(z[rs.at(-1)].t[N1])} (${rs.at(-1)}). Au niveau national, il est passé de ${pc(nt[0])} à ${pc(nt[N1])}.`);
    $("anaReg").innerHTML=mini(["Région","Garçons","Filles","Ensemble"],rs.slice(0,6).map(r=>[r,pc(z[r].g[N1]),pc(z[r].f[N1]),dbar(z[r].t[N1],120,pc(z[r].t[N1]))]));}
  if(D.prov){const I=D.prov.ind,ns=D.prov.names,H=n=>D.prov.hist[n][N1],
      acc=ns.filter(n=>I[n].effectif_dernier_sur_max<0.6).sort((a,b)=>I[a].effectif_dernier_sur_max-I[b].effectif_dernier_sur_max),
      perdus=acc.reduce((t,n)=>t+(I[n].eleves_perdus_depuis_max||0),0),fm=ns.reduce((t,n)=>t+(I[n].filles_manquantes_parite||0),0),
      ip=ns.filter(n=>H(n)!=null).sort((a,b)=>H(a)-H(b)),p1=D.prov.prio.filter(r=>r.priorite===1).map(r=>r.province),
      ur=ns.filter(n=>I[n].ecart_urbain_moins_rural>0).length;
    K.push([nbf(perdus),`élèves en moins dans les ${acc.length} provinces sous 60 % de leur meilleur effectif`,"alerte"]);
    K.push([nbf(fm),"filles à inscrire en plus pour atteindre la parité dans toutes les provinces"]);
    K.push([String(p1.length),"provinces en priorité 1 : faible parité et perte d'élèves","alerte"]);
    k.push(`Des provinces se vident : ${acc.length} sur ${ns.length} comptent moins de 60 % des élèves de leur meilleure année (${acc.slice(0,4).map(n=>n+" "+pc1(I[n].effectif_dernier_sur_max)).join(", ")}). Ensemble, elles ont perdu ${nbf(perdus)} élèves.`);
    const n0=D.nat.pri[0],n1=D.nat.pri[N1],sous=D.regions.filter(r=>D.pri[r][N1]!=null&&D.pri[r][N1]<0.97).length;
    k.push(`La parité filles-garçons progresse au primaire (IPS ${f2(n0)} en ${y0}, ${f2(n1)} en ${y1}), mais l'écart se forme dès le CP1 (${f2(D.nat.cp1[N1])}) et ${sous} régions sur ${D.regions.length} restent sous 0,97. Par province, l'IPS va de ${f2(H(ip[0]))} (${ip[0]}) à ${f2(H(ip.at(-1)))} (${ip.at(-1)}).`);
    k.push(`Entre ville et campagne, l'écart d'IPS passe de ${f3(D.mil.urbain[0]-D.mil.rural[0])} à ${f3(D.mil.urbain[N1]-D.mil.rural[N1])} point, mais l'IPS rural reste plus bas que l'urbain dans ${ur} provinces sur ${ns.length}.`);
    k.push(`À cibler en priorité : ${p1.join(", ")}. L'onglet « Aide à la décision » permet de régler les seuils.`);
    const P=D.prov.prev,so=Object.keys(P).filter(n=>/^sous/.test(P[n].statut));
    if(so.length&&D.prov.prevAns)k.push(`Si rien ne change, ${so.length} provinces resteront sous 0,95 en ${ya(D.prov.prevAns.at(-1))} (onglet « Prévision »).`);
    $("anaProvAcc").innerHTML=mini(["Province","Ancienne région","Effectifs / meilleur","Élèves en moins"],acc.slice(0,8).map(n=>[n,I[n].region,dbar(I[n].effectif_dernier_sur_max,1,pc1(I[n].effectif_dernier_sur_max)),nbf(I[n].eleves_perdus_depuis_max)]),2);
    $("anaProvIps").innerHTML=mini(["Province","Ancienne région","IPS","Filles manquantes"],ip.slice(0,8).map(n=>[n,I[n].region,dbar(1-H(n),0.25,f2(H(n)),cv("--s2")),nbf(I[n].filles_manquantes_parite)]),2);}
  if(D.mc){const nm=D.mc.find(x=>x.r==="National"),rg=D.mc.filter(x=>x.r!=="National").sort((a,b)=>b.plus-a.plus);
    K.splice(1,0,[nbf(nm.plus),`élèves à ajouter au primaire pour atteindre un TBS de 100 % (${nbf(nm.pop)} enfants d'âge primaire)`,"alerte"]);
    k.splice(1,0,`Il faudrait ${nbf(nm.plus)} élèves de plus au primaire pour atteindre un taux brut de 100 %, dont ${rg.slice(0,3).map(x=>nbf(x.plus)+" ("+x.r+")").join(", ")}.`);
    $("anaPop").innerHTML=mini(["Région","Enfants d'âge primaire","Élèves","TBS","À ajouter"],rg.filter(x=>x.plus>0).map(x=>[x.r,nbf(x.pop),nbf(x.el),pc(x.tbs),`<b>${nbf(x.plus)}</b>`]));}
  if(D.ptbs){$("anaTbsCard").hidden=false;const R=D.ptbs.rows;
    $("anaTbs").innerHTML=mini(["Province","Ancienne région","TBS","Filles","Garçons","Élèves en plus"],R.slice(0,10).map(x=>[x.p,x.r,dbar(x.t,120,pc(x.t)),pc(x.f),pc(x.g),nbf(x.plus)]),2);
    $("anaTbsNote").textContent=`Population INSD ${D.ptbs.annee} ; méthode : ${D.ptbs.methode}. Les 10 provinces au taux le plus bas sur ${R.length}.`;}
  if(D.liens){$("anaLiensCard").hidden=false;
    $("anaLiens").innerHTML=mini(["Question","rho","Lien"],D.liens.map(x=>[x.q,f2(x.rho),x.sig?`<b>significatif</b>`:"non significatif"]));}
  if(D.typo&&D.prov){$("anaTypoCard").hidden=false;const pal=["#b2182b","#e8743b","#d9a426","#5b9fd6","#1d5fa8"],G={};D.typo.rows.forEach(x=>G[x.p]=x);
    const noms=[...new Map(D.typo.rows.map(x=>[x.g,x.nom])).entries()].sort((a,b)=>a[0]-b[0]);
    $("lgTypo").innerHTML=noms.map(([g,n])=>`<span><i class="sw bloc" style="background:${pal[(g-1)%5]}"></i>${g}. ${n} (${D.typo.rows.filter(x=>x.g===g).length})</span>`).join("");
    let h=`<svg viewBox="${D.prov.vb.join(" ")}" role="img" aria-label="Carte des profils de provinces"><g class="reg">`;
    D.prov.geo.forEach(g=>{const x=G[g.name];h+=`<path data-p="${g.name}" d="${g.d}" fill="${x?pal[(x.g-1)%5]:cv("--grid")}"/>`});
    $("anaTypo").innerHTML=h+"</g></svg>";
    $("anaTypo").querySelectorAll("path").forEach(el=>{el.onmousemove=e=>{const x=G[el.dataset.p];showTip(e,`<b>${el.dataset.p}</b><br>${x?x.g+". "+x.nom+"<br>TBS "+pc(x.acc)+" · IPS "+f2(x.ips)+" · écart V-C "+f3(x.ec):"n.d."}`)};el.onmouseleave=hideTip});}
  $("anaKpis").innerHTML=K.map(([v,l,t])=>`<div class="kpi ${t||""}"><b>${v}</b><span>${l}</span></div>`).join("");
  $("anaConstats").innerHTML=k.map(x=>`<li>${x}</li>`).join("");
}
/* ----- Aide a la decision : carte des priorites et fiche de la province ----- */
function dCarteDraw(L){const pr={};L.forEach(o=>pr[o.n]=o.p);
  let h=`<svg viewBox="${D.prov.vb.join(" ")}" role="img" aria-label="Carte des provinces prioritaires"><g class="reg">`;
  D.prov.geo.forEach(g=>{const p=pr[g.name]||0;h+=`<path data-p="${g.name}" class="${g.name===pst.p?"sel":""}" d="${g.d}" fill="${p===1?cv("--dlow"):p===2?cv("--s2"):cv("--grid")}"/>`});
  $("dCarte").innerHTML=h+"</g></svg>";
  $("dCarte").querySelectorAll("path").forEach(el=>{el.onmousemove=e=>{const n=el.dataset.p;showTip(e,`<b>${n}</b><br>${pr[n]?"priorité "+pr[n]:"hors priorité"}`)};el.onmouseleave=hideTip;el.onclick=()=>pSel(el.dataset.p)});
}
function dFicheDraw(){const n=pst.p,i=D.prov.ind[n],ip=D.prov.hist[n][N-1],pv=D.prov.prev[n],k=pv?pv.v.length-1:0,o=prioCalc().find(x=>x.n===n),sg=D.prov.sig.filter(s=>s.province===n);
  $("dTitre").textContent=`Fiche : ${n} (ancienne région ${i.region})`;
  $("dFiche").innerHTML=mini(["Indicateur","Valeur"],[
    ["Priorité avec les seuils choisis",o?`<b>${o.p}</b>`:"hors priorité"],
    ["Effectifs / meilleur niveau depuis 2015",pc1(i.effectif_dernier_sur_max)],["Élèves en moins",nbf(i.eleves_perdus_depuis_max)],
    [`IPS ${ya(D.years[N-1])}`,f2(ip)],["IPS en ville / à la campagne",`${f2(i.ips_urbain)} / ${f2(i.ips_rural)}`],
    ["Filles à inscrire pour la parité",nbf(i.filles_manquantes_parite)],
    [`Projection ${D.prov.prevAns?ya(D.prov.prevAns.at(-1)):""}`,pv&&pv.v[k]!=null?`${f2(pv.v[k])} (entre ${f2(pv.lo[k])} et ${f2(pv.hi[k])})`:"n.d."]])+
    (sg.length?`<p class="note">IPS non interprétable en ${sg.map(s=>ya(s.annee_debut)).join(", ")} : effectif effondré.</p>`:"");
  const ef=D.prov.eff[n];
  $("dSpark").innerHTML=`<div class="grid" style="gap:10px;margin-top:8px"><div><p class="note" style="margin:0">IPS, ${ya(D.years[0])} → ${ya(D.years[N-1])} (pointillé : parité)</p>${spark(D.prov.hist[n],cv("--s1"),1)}</div>`+
    (ef?`<div><p class="note" style="margin:0">Effectifs en % de la meilleure année</p>${spark(ef,cv("--dlow"),1)}</div>`:"")+`</div>`;
}
$("dImpr").onclick=()=>{const w=window.open("","_blank");if(!w){window.print();return}
  w.document.write(`<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>${$("dTitre").textContent}</title><style>body{font:14px/1.5 "Segoe UI",system-ui,sans-serif;color:#111;margin:28px;max-width:760px}h1{font-size:1.3rem;margin:0 0 4px}
  table{border-collapse:collapse;width:100%;margin-top:12px}td,th{border-bottom:1px solid #ddd;padding:6px 8px;text-align:right}td:first-child,th:first-child{text-align:left}th{font-size:.75rem;text-transform:uppercase;color:#666}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:14px}svg{width:100%;height:auto}p.note,.sub{color:#555;font-size:.8rem}svg text{font:11px sans-serif}</style></head><body>
  <p class="sub">Data Challenge Burkina 2026 · Défi 2 · Équipe ${EQ} · primaire ${ya(D.years[N-1])}</p><h1>${$("dTitre").textContent}</h1>${$("dFiche").innerHTML}${$("dSpark").innerHTML}
  <p class="sub" style="margin-top:18px">Seuils : IPS sous ${f2(sim.ips)}, effectifs sous ${pc1(sim.acc)} du maximum. Sources : annuaires DGESS, projections INSD. Un écart ne dit pas sa cause.</p></body></html>`);
  w.document.close();w.focus();setTimeout(()=>w.print(),300)};
/* ----- Prevision : IPS observe et projete, classement, fiabilite des modeles ----- */
const fst={p:""};
const LIBM={persistance:"Persistance (l'IPS ne bouge pas)",tendance_amortie:"Tendance amortie",tendance_5ans:"Tendance sur 5 ans",moyenne_3ans:"Moyenne des 3 dernières années"};
function fDraw(){if(!D.prov||!D.prov.prevAns||!D.prov.prev[fst.p])return;
  const P=D.prov.prev,A=D.prov.prevAns,n=fst.p,pv=P[n],hs=D.prov.hist[n],nb=D.years.length,lab=[...D.years,...A].map(ya),
    der=hs[nb-1]!=null?hs[nb-1]:hs.filter(v=>v!=null).at(-1),pont=v=>[...hs.map((x,i)=>i===nb-1?der:null),...v];
  $("tfEvo").textContent=`${n} : IPS observé puis projeté jusqu'en ${ya(A.at(-1))}`;
  ligne("fevo","lgFEvo",[{name:"IPS observé",short:"Observé",color:cv("--s1"),vals:[...hs,...A.map(()=>null)],nolab:true},
    {name:"Projection",short:"Projeté",color:cv("--s2"),vals:pont(pv.v),dash:true}],{labels:lab,pas:3,fill:[pont(pv.hi),pont(pv.lo)],label:"IPS observé et projeté"});
  const ns=Object.keys(P).filter(q=>P[q].v.at(-1)!=null).sort((a,b)=>P[a].v.at(-1)-P[b].v.at(-1)),W=520,rh=16,m={l:132,r:50,t:6,b:22},H=m.t+m.b+ns.length*rh,
    lo=0.7,hi=1.15,x=v=>m.l+(Math.max(lo,Math.min(hi,v))-lo)/(hi-lo)*(W-m.l-m.r);
  $("tfRang").textContent=`IPS projeté en ${ya(A.at(-1))}, les 45 provinces`;
  let s=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="IPS projeté par province">`;
  [0.7,0.8,0.9,0.95,1,1.1].forEach(t=>{s+=`<line x1="${x(t)}" x2="${x(t)}" y1="${m.t}" y2="${H-m.b}" stroke="${t===0.95?cv("--dlow"):cv("--grid")}" stroke-width="${t===0.95||t===1?1.5:1}" ${t===0.95?'stroke-dasharray="4 3"':""}/><text x="${x(t)}" y="${H-6}" text-anchor="middle">${f2(t)}</text>`});
  ns.forEach((q,i)=>{const r=P[q],k=r.v.length-1,y=m.t+i*rh+rh/2,c=/^sous/.test(r.statut)?cv("--dlow"):/^incertain/.test(r.statut)?cv("--s2"):cv("--dhigh"),sel=q===n;
    s+=`<g class="bar" data-p="${q}"><rect x="0" y="${y-rh/2}" width="${W}" height="${rh}" fill="transparent"/><line x1="${x(r.lo[k])}" x2="${x(r.hi[k])}" y1="${y}" y2="${y}" stroke="${c}" stroke-width="2"/><circle cx="${x(r.v[k])}" cy="${y}" r="${sel?5:3.5}" fill="${c}" ${sel?`stroke="${cv("--text")}" stroke-width="1.5"`:""}/>
    <text x="${m.l-6}" y="${y+4}" text-anchor="end" style="font-size:10.5px;${sel?`font-weight:700;fill:${cv("--text")}`:""}">${q}</text><text x="${x(r.hi[k])+4}" y="${y+4}" style="font-size:10px;fill:${cv("--text")}">${f2(r.v[k])}</text></g>`});
  $("frang").innerHTML=s+"</svg>";
  $("frang").querySelectorAll(".bar").forEach(g=>{g.onmousemove=e=>{const r=P[g.dataset.p],k=r.v.length-1;showTip(e,`<b>${g.dataset.p}</b><br>projeté ${f2(r.v[k])} (${f2(r.lo[k])} à ${f2(r.hi[k])})<br>${r.statut}`)};g.onmouseleave=hideTip;
    g.onclick=()=>{fst.p=g.dataset.p;$("fprov").value=fst.p;fDraw()}});
  const bt=D.bt||[],ret=(bt.find(b=>b.retenu===true||b.retenu==="True")||{}).modele,moy=md=>{const r=bt.filter(b=>b.modele===md);return r.reduce((t,b)=>t+b.mae,0)/r.length},
    mods=[...new Set(bt.map(b=>b.modele))].sort((a,b)=>moy(a)-moy(b)),q80=hz=>{const b=bt.find(b=>b.modele===ret&&b.horizon===hz);return b?b.q80:null};
  $("fbt").innerHTML=mini(["Modèle","Erreur moyenne à 1 an","à 2 ans","à 3 ans","Retenu"],mods.map(md=>[LIBM[md]||md,...[1,2,3].map(hz=>{const b=bt.find(b=>b.modele===md&&b.horizon===hz);return b?f3(b.mae):"n.d."}),md===ret?"<b>oui</b>":""]));
  const so=ns.filter(q=>/^sous/.test(P[q].statut)),inc=ns.filter(q=>/^incertain/.test(P[q].statut));
  $("fMsg").innerHTML=`Modèle retenu : <b>${LIBM[ret]||ret}</b>, le plus fiable des quatre sur les années passées. Marge d'erreur, 8 fois sur 10 : ±${f3(q80(1))} à un an, ±${f3(q80(3))} à trois ans. `+
    `En ${ya(A.at(-1))}, <b>${so.length} provinces</b> resteraient sous 0,95 même dans le scénario haut (${so.join(", ")}) et ${inc.length} sont incertaines. `+
    `${n} : ${f2(pv.v.at(-1))} projeté, entre ${f2(pv.lo.at(-1))} et ${f2(pv.hi.at(-1))}.`;
  majLien();
}
/* ---------- lien partageable : l'etat de la vue est garde dans l'adresse (#...) ---------- */
function majLien(){try{const p=new URLSearchParams({o:ong,n:st.niv,a:D.years[st.yi],r:st.reg,ai:ast.i,rm:rst.m,rr:rst.r,pm:pst.m,p:pst.p,si:sim.ips,sa:sim.acc,fp:fst.p});
  history.replaceState(null,"","#"+p.toString())}catch(e){}}
function lireLien(){const p=new URLSearchParams(location.hash.slice(1)),g=k=>p.get(k);if(!location.hash)return;
  if(ONG.includes(g("o")))ong=g("o");if(D.prov&&D.prov.prev[g("fp")]){fst.p=g("fp");$("fprov").value=fst.p}
  if(NOMS[g("n")])st.niv=g("n");const yi=D.years.indexOf(+g("a"));if(yi>=0)st.yi=yi;if(D.regions.includes(g("r")))st.reg=g("r");
  if(D.acc&&D.acc[g("ai")])ast.i=g("ai");if(D.r17&&["effectif_dernier_sur_max","ips","ips_rural","ecart_urbain_moins_rural","eleves_perdus_depuis_max","filles_manquantes_parite"].includes(g("rm")))rst.m=g("rm");
  if(D.r17&&D.r17.names.includes(g("rr")))rst.r=g("rr");if(MES[g("pm")])pst.m=g("pm");if(D.prov&&D.prov.names.includes(g("p")))pst.p=g("p");
  const si=+g("si"),sa=+g("sa");if(si>=0.85&&si<=1)sim.ips=si;if(sa>=0.3&&sa<=0.9)sim.acc=sa;
  $("niveau").value=st.niv;$("annee").value=st.yi;$("region").value=st.reg;if(D.acc)$("aind").value=ast.i;if(D.r17)$("rmes").value=rst.m;
  if(D.prov){$("pmes").value=pst.m;$("pprov").value=pst.p;$("sIps").value=sim.ips;$("sAcc").value=sim.acc}}
$("lien").onclick=()=>{majLien();const u=location.href,ok=()=>{$("lien").textContent="Lien copié";setTimeout(()=>$("lien").textContent="Copier le lien de cette vue",1800)};
  if(navigator.clipboard&&navigator.clipboard.writeText)navigator.clipboard.writeText(u).then(ok,()=>prompt("Copiez ce lien :",u));else prompt("Copiez ce lien :",u)};
$("imprimer").onclick=()=>window.print();
function draw(){$("anneeLib").textContent=ya(D.years[st.yi]);kpis();carte();rang();courbes();tableau();if(D.acc)accDraw();if(D.r17)r17Draw();if(D.prov)provDraw();anaDraw();fDraw();homeDraw();majLien()}

$("region").innerHTML='<option value="">Toutes (national)</option>'+D.regions.map(r=>`<option>${r}</option>`).join("");
$("annee").max=N-1;$("annee").value=st.yi;
$("niveau").onchange=e=>{st.niv=e.target.value;draw()};
$("annee").oninput=e=>{st.yi=+e.target.value;draw()};
$("region").onchange=e=>{st.reg=e.target.value;draw()};
$("theme").onclick=()=>{const r=document.documentElement,dark=r.dataset.theme?r.dataset.theme==="dark":matchMedia("(prefers-color-scheme: dark)").matches;r.dataset.theme=dark?"light":"dark";draw()};
matchMedia("(prefers-color-scheme: dark)").addEventListener("change",draw);
if(D.prov){
  $("provSec").hidden=false;D.prov.annee=ya(D.years[N-1]);
  $("pprov").innerHTML=D.prov.names.map(n=>`<option>${n}</option>`).join("");
  pst.p=D.prov.prio.length?D.prov.prio[0].province:D.prov.names.slice().sort((a,b)=>D.prov.ind[a].ips_ensemble-D.prov.ind[b].ips_ensemble)[0];$("pprov").value=pst.p;
  if(D.prov.ind[D.prov.names[0]].effectif_dernier_sur_max==null){pst.m="ips_ensemble";$("pmes").value=pst.m}
  $("pmes").onchange=e=>{pst.m=e.target.value;provDraw()};$("pprov").onchange=e=>{pst.p=e.target.value;provDraw()};
  if(D.prov.sig.length)$("psig").textContent=`IPS retirés car non interprétables (effectif tombé sous 10 % du maximum de la province) : `+
    D.prov.sig.map(s=>`${s.province} ${ya(s.annee_debut)} (${s.effectif_total} élèves sur ${s.effectif_max_periode} au maximum)`).join(" ; ")+". Ils restent listés dans le fichier des signalements.";
}
if(D.prov){$("sIps").oninput=e=>{sim.ips=+e.target.value;provPrio()};$("sAcc").oninput=e=>{sim.acc=+e.target.value;provPrio()}}
if(D.r17){$("r17Sec").hidden=false;$("rmes").innerHTML=[["effectif_dernier_sur_max","Accès : effectifs en % du maximum"],["ips","IPS, ensemble"],["ips_rural","IPS, milieu rural"],
  ["ecart_urbain_moins_rural","Écart d'IPS urbain − rural"],["eleves_perdus_depuis_max","Élèves perdus depuis la meilleure année"],["filles_manquantes_parite","Filles à inscrire pour la parité"]].map(([k,v])=>`<option value="${k}">${v}</option>`).join("");
  $("rmes").onchange=e=>{rst.m=e.target.value;r17Draw()}}
if(D.acc){$("accSec").hidden=false;$("aind").innerHTML=Object.entries(D.acc).map(([k,v])=>`<option value="${k}">${v.lib}</option>`).join("");$("aind").value=ast.i;$("aind").onchange=e=>{ast.i=e.target.value;accDraw()}}
if(D.prov&&D.prov.prevAns){const ks=Object.keys(D.prov.prev).sort((a,b)=>a.localeCompare(b,"fr"));$("fprov").innerHTML=ks.map(k=>`<option>${k}</option>`).join("");
  fst.p=(D.prov.prio[0]||{}).province||ks[0];$("fprov").value=fst.p;$("fprov").onchange=e=>{fst.p=e.target.value;fDraw()}}
lireLien();
draw();
montrer(ong);
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dossier03"); ap.add_argument("dossier04"); ap.add_argument("--equipe", default="Burkina_Novation")
    a = ap.parse_args()
    p = lire(a.dossier03, "parite-effectifs")
    for c in ("ips",):
        p[c] = pd.to_numeric(p[c], errors="coerce")
    p["annee_debut"] = pd.to_numeric(p["annee_debut"], errors="coerce")
    annees = sorted(int(x) for x in p.annee_debut.dropna().unique())
    neutre = lambda x: x.niveau_scolaire.isin(["", "total"]) & x.milieu.isin(["", "total"]) & x.statut.isin(["", "total"])
    cl = lambda s: [None if (v != v) else round(float(v), 4) for v in s.reindex(annees)]

    def reg(feuille, bloc):
        x = p[(p.feuille == feuille) & (p.bloc == bloc) & (p.agregat == "detail") & (p.region != "total")]
        return x[neutre(x)].pivot_table(index="region", columns="annee_debut", values="ips")

    def nat(feuille, bloc):
        x = p[(p.feuille == feuille) & (p.bloc == bloc) & (p.agregat == "national")]
        return x[neutre(x)].groupby("annee_debut").ips.mean()

    R = {"pri": reg("Feuil1", "1"), "pre": reg("PRESCOLAIRE", "1"), "cp1": reg("Feuil5", "1")}
    regions = sorted(R["pri"].index)
    data = {"years": annees, "regions": regions}
    for k, df in R.items():
        data[k] = {r: cl(df.loc[r]) if r in df.index else [None] * len(annees) for r in regions}
    data["nat"] = {"pri": cl(nat("Feuil1", "1")), "pre": cl(nat("PRESCOLAIRE", "1")), "cp1": cl(nat("Feuil5", "1"))}
    m = p[(p.feuille == "Feuil3") & p.milieu.isin(["urbain", "rural"]) & (p.agregat == "detail") & p.niveau_scolaire.isin(["", "total"])]
    mil = m.pivot_table(index="annee_debut", columns="milieu", values="ips")
    s = p[(p.feuille == "Feuil2") & p.statut.isin(["public", "prive"]) & (p.agregat == "detail") & p.niveau_scolaire.isin(["", "total"])]
    sta = s.pivot_table(index="annee_debut", columns="statut", values="ips")
    data["mil"] = {"urbain": cl(mil["urbain"]), "rural": cl(mil["rural"])}
    data["sta"] = {"public": cl(sta["public"]), "prive": cl(sta["prive"])}
    gf = glob.glob(os.path.join(a.dossier03, "*anciennes-regions-13-officiel_v1.geojson"))
    if not gf:
        sys.exit("GeoJSON des 13 regions introuvable (etape liaison_officielle).")
    data["geo"], data["vb"] = geo_paths(gf[0])
    data["prov"] = charger_provinces(a.dossier03, a.dossier04, annees)
    # acces : taux publies par la DGESS (TBS, TBA, TAP) par region et par sexe
    fa = glob.glob(os.path.join(a.dossier04, "*_acces-regions_v1.csv"))
    data["acc"] = None
    if fa:
        ac = pd.read_csv(fa[0], sep=";", encoding="utf-8-sig")
        data["acc"] = {}
        for (ind_, lib), g in ac.groupby(["indicateur", "libelle"], sort=False):
            z = {}
            for rg, gg in g.groupby("region"):
                gg = gg.set_index("annee_debut").reindex(annees)
                z[rg] = {k: [None if v != v else round(float(v), 1) for v in gg[c]] for k, c in
                         (("g", "taux_garcons"), ("f", "taux_filles"), ("t", "taux_ensemble"))}
            data["acc"][ind_] = {"lib": lib, "z": z}
    # 17 regions actuelles : indicateurs agreges exactement depuis les provinces + fond COD-AB adm1 (etape 1)
    data["r17"] = None
    fr17 = glob.glob(os.path.join(a.dossier04, "*_regions17-indicateurs_v1.csv"))
    g17 = glob.glob(os.path.join(os.path.dirname(os.path.abspath(a.dossier03)), "01_collecte", "*bfa-admin1_v1.geojson"))
    if fr17 and g17:
        r17 = pd.read_csv(fr17[0], sep=";", encoding="utf-8-sig")
        a1_ = max(annees)
        nb = lambda x: None if x != x else round(float(x), 4)
        cols17 = [f"ips_{a1_}", "ips_rural", "ecart_urbain_moins_rural", "effectif_dernier_sur_max", "eleves_perdus_depuis_max", "filles_manquantes_parite"]
        geo17, vb17 = geo_paths(g17[0], cle_nom="adm1_name")
        data["r17"] = {"names": sorted(r17.nouvelle_region), "geo": [{"name": x["region"], "d": x["d"]} for x in geo17], "vb": vb17,
                       "ind": {r.nouvelle_region: {"old": r.anciennes_regions, "prov": r.provinces, "eff": int(r[f"effectif_{a1_}"]),
                                                   **{("ips" if c.startswith("ips_20") else c): nb(r[c]) for c in cols17}} for _, r in r17.iterrows()}}
        print(f"17 regions actuelles : {len(data['r17']['names'])} dans la table, {len(geo17)} polygones")
    # modele commun (architect) : population d'age scolaire et eleves a ajouter pour un TBS de 100 %, derniere annee
    fmc = glob.glob(os.path.join(a.dossier03, "*_modele-commun-region-annee_v1.csv"))
    data["mc"] = None
    if fmc:
        mc = pd.read_csv(fmc[0], sep=";", encoding="utf-8-sig")
        mc = mc[mc.annee_debut == mc.annee_debut.max()]
        data["mc"] = [{"r": r.region, "pop": float(r.population_primaire_total), "el": float(r.eleves_primaire_total), "tbs": float(r.tbs_primaire_total),
                       "plus": float(r.eleves_en_plus_pour_tbs100_primaire)} for r in mc.itertuples()]
    # TBS par province avec la population INSD (seulement si l'equipe a extrait les projections)
    fpt = glob.glob(os.path.join(a.dossier04, "*_population-tbs-provinces_v1.csv"))
    data["ptbs"] = None
    if fpt:
        pz = pd.read_csv(fpt[0], sep=";", encoding="utf-8-sig").dropna(subset=["tbs_total"]).sort_values("tbs_total")
        data["ptbs"] = {"methode": str(pz.methode.iloc[0]), "annee": int(pz.annee_population.iloc[0]),
                        "rows": [{"p": r.province, "r": r.ancienne_region, "t": float(r.tbs_total), "f": None if r.tbs_filles != r.tbs_filles else float(r.tbs_filles),
                                  "g": None if r.tbs_garcons != r.tbs_garcons else float(r.tbs_garcons),
                                  "plus": None if r.eleves_en_plus_pour_tbs100 != r.eleves_en_plus_pour_tbs100 else float(r.eleves_en_plus_pour_tbs100)} for r in pz.itertuples()]}
    # liens et groupes (Defi 2)
    fli, fty = glob.glob(os.path.join(a.dossier04, "*_liens-indicateurs_v1.csv")), glob.glob(os.path.join(a.dossier04, "*_typologie-provinces_v1.csv"))
    data["liens"] = data["typo"] = None
    if fli and fty:
        li_ = pd.read_csv(fli[0], sep=";", encoding="utf-8-sig"); ty_ = pd.read_csv(fty[0], sep=";", encoding="utf-8-sig")
        data["liens"] = [{"q": r.question, "rho": float(r.rho_spearman), "p": float(r.p_valeur), "sig": str(r.significatif_5pc) == "True"} for r in li_.itertuples()]
        data["typo"] = {"k": int(ty_.k_retenu.iloc[0]), "rows": [{"p": r.province, "g": int(r.groupe), "nom": r.profil, "acc": float(r.acces),
                        "ips": float(r.ips), "ec": float(r.ecart_urbain_moins_rural)} for r in ty_.itertuples()]}
    # prevision : fiabilite des modeles (validation sur le passe), pour l'onglet Prevision
    fbt = glob.glob(os.path.join(a.dossier04, "*_prevision-backtest_v1.csv"))
    data["bt"] = (pd.read_csv(fbt[0], sep=";", encoding="utf-8-sig")[["modele", "horizon", "mae", "q80", "retenu"]]
                  .astype(object).where(lambda x: x.notna(), None).to_dict("records") if fbt else [])
    ya = lambda y: f"{y}/{str(y + 1)[2:]}"
    an_prev = ya(max(data["prov"]["prevAns"])) if data["prov"] and data["prov"].get("prevAns") else ""
    limites = [
        "Données régionales par ancienne région (13) ; la correspondance avec les 17 régions actuelles est documentée à l'étape 3.",
        "Le niveau province (45 anciennes provinces) ne couvre que le primaire (annuaire 2024-2025) ; pas de niveau commune.",
        "L'IPS d'effectifs décrit la composition des inscrits ; les taux TBS, TBA et TAP (DGESS) mesurent l'accès rapporté à la population.",
        "Un IPS calculé sur un effectif effondré (moins de 10 % du maximum de la province) est laissé vide et signalé.",
        "La chute des effectifs signale une perte d'accès (fermetures d'écoles probables) sans en prouver la cause.",
        "Primaire 2017/18 : total national non retrouvé dans les annuaires ; années récentes possiblement provisoires.",
        "Aucune causalité : un écart ne dit pas sa cause. Les projections prolongent la situation actuelle, elles ne la prédisent pas.",
    ]
    # donnees de la plateforme React + NestJS (meme contenu que la page autonome, une seule source de verite)
    data["meta"] = {"equipe": a.equipe, "date": date.today().isoformat(), "periode": f"{ya(annees[0])} à {ya(annees[-1])}",
                    "annee": ya(annees[-1]), "anneePrev": an_prev, "limites": limites}
    fj = os.path.join(a.dossier04, f"{a.equipe}_04-analyse_D2_analyst_donnees-plateforme_v1.json")
    with open(fj, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    print(f"Donnees de la plateforme React/NestJS : {os.path.basename(fj)} ({os.path.getsize(fj) // 1024} Ko)")
    html = (MODELE.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
            .replace("__EQUIPE__", a.equipe).replace("__DATE__", date.today().isoformat())
            .replace("__PERIODE__", f"{ya(annees[0])} à {ya(annees[-1])}").replace("__ANNEE_PROV__", ya(annees[-1]))
            .replace("__ANNEE_PREV__", an_prev)
            .replace("__LIMITES__", "".join(f"<li>{x}</li>" for x in limites)))

    zp = sorted(glob.glob(os.path.join(a.dossier04, "*tableau-de-bord_v1.zip")))
    if not zp:
        sys.exit("Zip de l'etape 4 introuvable : lancez d'abord l'etape analyse.")
    with zipfile.ZipFile(zp[0]) as z:
        contenu = {n: z.read(n) for n in z.namelist()}
    contenu["tableau-de-bord.html"] = html.encode("utf-8")
    contenu["LISEZ-MOI.txt"] = ("Ouvrir tableau-de-bord.html dans un navigateur (page interactive autonome, sans connexion). Sept onglets :\n"
                                "  Accueil            la reponse au Defi 2 en une page : ou, filles-garcons, ville-campagne, demain ; carte des priorites\n"
                                "  Analyse            constats cles, regions et provinces les plus touchees, liens entre les ecarts, profils de provinces\n"
                                "  Tableau de bord    parite et acces par ancienne region, annee par annee (carte, classement, courbes, taux par sexe)\n"
                                "  Carte              17 regions actuelles et 45 provinces, selon la mesure choisie\n"
                                "  Aide a la decision simulateur de ciblage a deux seuils, provinces prioritaires, carte des priorites, fiche par province\n"
                                "  Prevision          IPS observe et projete par province, marge d'erreur, classement, fiabilite des modeles\n"
                                "  Methode et donnees parcours des donnees, lexique, sources, controles, commande de relance, telechargement CSV, limites\n"
                                "Boutons : donnees CSV, copier le lien de la vue (l'onglet et les reglages sont gardes dans l'adresse), imprimer / PDF, theme clair/sombre.\n"
                                "Clavier : fleches gauche/droite pour changer d'onglet.\n"
                                "Les figures PNG sont la version statique de secours.\n"
                                "Genere par scripts/analyse_template.py puis scripts/dashboard_template.py a partir de 03_transformation (tables agregees).\n").encode("utf-8")
    tmp = zp[0] + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for n, b in contenu.items():
            z.writestr(n, b)
    os.replace(tmp, zp[0])
    print(f"Dashboard interactif integre ({len(html) // 1024} Ko, {len(data['geo'])} regions cartographiees, {len(annees)} annees).")


if __name__ == "__main__":
    main()
