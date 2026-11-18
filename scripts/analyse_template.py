#!/usr/bin/env python3
"""ETAPE 4 - ANALYSE (Defi 2 : parite fille-garcon, ecarts urbain/rural).

Entrees : UNIQUEMENT les tables agregees de 03_transformation (aucune donnee brute).
Sorties (dossier 04_analyse) :
  <EQ>_04-analyse_D2_analyst_indicateurs-cles_v1.csv      une ligne par region + national
  <EQ>_04-analyse_D2_analyst_ecart-urbain-rural_v1.csv     serie nationale urbain/rural
  <EQ>_04-analyse_D2_analyst_tableau-de-bord_v1.zip        tableau-de-bord.html (autonome) + figures PNG
  <EQ>_04-analyse_D2_analyst_lisez-moi_v1.txt
Tous les chiffres du texte du tableau de bord sont CALCULES depuis les tables (rien n'est ecrit a la main).

Lecture de l'IPS = filles / garcons. 1,00 = parite ; < 1 = moins de filles que de garcons ;
> 1 = plus de filles. (Un IPS > 1 n'est pas un "probleme de filles" : c'est un ecart dans l'autre sens.)

Usage : analyse_template.py DOSSIER_03 DOSSIER_04 [--equipe Burkina_Novation]
"""
import argparse, base64, glob, io, json, os, sys, zipfile
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon
import pandas as pd

# Palette daltonien-compatible (Okabe-Ito), neutre au centre.
C_PRI, C_PRE, C_CP1, C_URB, C_RUR = "#0072b2", "#8c564b", "#7f7f7f", "#e69f00", "#009e73"
C_PUB, C_PRV = "#0072b2", "#d55e00"


def lire(dossier, cle):
    fs = glob.glob(os.path.join(dossier, f"*_{cle}_v1.csv"))
    if not fs:
        sys.exit(f"Fichier introuvable : *_{cle}_v1.csv dans {dossier} (lancez d'abord l'etape 3)")
    return pd.read_csv(fs[0], sep=";", encoding="utf-8-sig", keep_default_na=False, dtype=str)


def num(d, cols):
    for c in cols:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["annee_debut"] = pd.to_numeric(d["annee_debut"], errors="coerce").astype("Int64")
    return d


def lib_annee(a):  # 2024 -> "2024/25"
    return f"{int(a)}/{str(int(a) + 1)[2:]}"


def png_b64(fig, nom, zf):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    zf.writestr(nom, buf.getvalue())
    return base64.b64encode(buf.getvalue()).decode()


def style(ax, titre, ylabel=None):
    ax.set_title(titre, loc="left", fontsize=11, fontweight="bold")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", alpha=.25)
    if ylabel:
        ax.set_ylabel(ylabel)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dossier03"); ap.add_argument("dossier04")
    ap.add_argument("--equipe", default="Burkina_Novation")
    a = ap.parse_args()
    os.makedirs(a.dossier04, exist_ok=True)
    pref = f"{a.equipe}_04-analyse_D2_analyst_"

    p = num(lire(a.dossier03, "parite-effectifs"), ["ips", "part_filles", "garcons", "filles", "total"])
    geo_f = glob.glob(os.path.join(a.dossier03, "*anciennes-regions-13-officiel_v1.geojson"))
    geo = json.load(open(geo_f[0], encoding="utf-8")) if geo_f else None
    annees = sorted(int(x) for x in p.annee_debut.dropna().unique())
    a0, a1 = annees[0], annees[-1]

    neutre = lambda x: x.niveau_scolaire.isin(["", "total"]) & x.milieu.isin(["", "total"]) & x.statut.isin(["", "total"])

    def reg(feuille, bloc):
        x = p[(p.feuille == feuille) & (p.bloc == bloc) & (p.agregat == "detail") & (p.region != "total")]
        return x[neutre(x)].pivot_table(index="region", columns="annee_debut", values="ips")

    def nat(feuille, bloc):
        x = p[(p.feuille == feuille) & (p.bloc == bloc) & (p.agregat == "national")]
        return x[neutre(x)].groupby("annee_debut").ips.mean()

    R_pri, R_pre, R_cp1 = reg("Feuil1", "1"), reg("PRESCOLAIRE", "1"), reg("Feuil5", "1")
    N_pri, N_pre, N_cp1 = nat("Feuil1", "1"), nat("PRESCOLAIRE", "1"), nat("Feuil5", "1")

    m = p[(p.feuille == "Feuil3") & p.milieu.isin(["urbain", "rural"]) & (p.agregat == "detail")
          & p.niveau_scolaire.isin(["", "total"])]
    mil = m.pivot_table(index="annee_debut", columns="milieu", values="ips")
    mil["ecart_urbain_moins_rural"] = mil["urbain"] - mil["rural"]
    s = p[(p.feuille == "Feuil2") & p.statut.isin(["public", "prive"]) & (p.agregat == "detail")
          & p.niveau_scolaire.isin(["", "total"])]
    sta = s.pivot_table(index="annee_debut", columns="statut", values="ips")
    if mil.empty or sta.empty or R_pri.empty:
        sys.exit("Tables attendues vides : verifier les filtres feuille/bloc/agregat (voir transformation).")

    # ---------- tableau des indicateurs cles ----------
    lignes = []
    for r in sorted(R_pri.index):
        lignes.append({
            "niveau_geographique": "ancienne_region_13", "region": r,
            f"ips_primaire_{a0}": R_pri.loc[r, a0], f"ips_primaire_{a1}": R_pri.loc[r, a1],
            "variation_primaire": R_pri.loc[r, a1] - R_pri.loc[r, a0],
            f"ips_prescolaire_{a1}": R_pre.loc[r, a1] if r in R_pre.index else None,
            f"ips_cp1_nouveaux_inscrits_{a1}": R_cp1.loc[r, a1] if r in R_cp1.index else None,
        })
    lignes.append({"niveau_geographique": "national", "region": "Burkina Faso",
                   f"ips_primaire_{a0}": N_pri.get(a0), f"ips_primaire_{a1}": N_pri.get(a1),
                   "variation_primaire": N_pri.get(a1) - N_pri.get(a0),
                   f"ips_prescolaire_{a1}": N_pre.get(a1), f"ips_cp1_nouveaux_inscrits_{a1}": N_cp1.get(a1)})
    ind = pd.DataFrame(lignes)
    ind["rang_primaire_du_plus_bas"] = ind[f"ips_primaire_{a1}"].where(ind.niveau_geographique != "national").rank()
    ind.round(4).to_csv(os.path.join(a.dossier04, pref + "indicateurs-cles_v1.csv"), sep=";", index=False, encoding="utf-8-sig")
    mil.reset_index().round(4).to_csv(os.path.join(a.dossier04, pref + "ecart-urbain-rural_v1.csv"), sep=";", index=False, encoding="utf-8-sig")

    # ---------- figures ----------
    html_png, zbuf = {}, io.BytesIO()
    zf = zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED)

    def axe_annees(ax, idx):
        ax.set_xticks([int(i) for i in idx]); ax.set_xticklabels([lib_annee(i) for i in idx], rotation=45, ha="right", fontsize=8)

    fig, ax = plt.subplots(figsize=(8, 4.2))
    for ser, c, lab in ((N_pri, C_PRI, "Primaire"), (N_pre, C_PRE, "Prescolaire"), (N_cp1, C_CP1, "Nouveaux inscrits CP1")):
        ax.plot([int(i) for i in ser.index], ser.values, marker="o", ms=4, color=c, label=lab)
        ax.annotate(f"{ser.iloc[-1]:.2f}", (int(ser.index[-1]), ser.iloc[-1]), textcoords="offset points", xytext=(6, -3), color=c, fontsize=9)
    ax.axhline(1, color="black", lw=1, ls="--"); ax.text(a0, 1.003, "parite (IPS = 1)", fontsize=8)
    axe_annees(ax, annees)
    style(ax, "Indice de parite filles/garcons, national (effectifs)", "IPS"); ax.legend(frameon=False, fontsize=8, loc="lower right")
    html_png["national"] = png_b64(fig, "fig1_ips_national.png", zf)

    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.plot(mil.index.astype(int), mil["urbain"], marker="o", ms=4, color=C_URB, label="Urbain")
    ax.plot(mil.index.astype(int), mil["rural"], marker="o", ms=4, color=C_RUR, label="Rural")
    ax.fill_between(mil.index.astype(int), mil["rural"], mil["urbain"], color="#cccccc", alpha=.4)
    ax.axhline(1, color="black", lw=1, ls="--")
    for k, c in (("urbain", C_URB), ("rural", C_RUR)):
        ax.annotate(f"{mil[k].iloc[-1]:.2f}", (int(mil.index[-1]), mil[k].iloc[-1]), textcoords="offset points", xytext=(6, -3), color=c, fontsize=9)
    axe_annees(ax, mil.index)
    style(ax, "Primaire : IPS en milieu urbain et rural (ecart ombre)", "IPS"); ax.legend(frameon=False, fontsize=8)
    html_png["milieu"] = png_b64(fig, "fig2_urbain_rural.png", zf)

    fig, ax = plt.subplots(figsize=(8, 5))
    o = R_pri.sort_values(a1)
    for i, r in enumerate(o.index):
        v0, v1 = o.loc[r, a0], o.loc[r, a1]
        ax.plot([v0, v1], [i, i], color="#bbbbbb", lw=2, zorder=1)
        ax.scatter(v0, i, color="#999999", s=28, zorder=2)
        ax.scatter(v1, i, color=C_PRI if v1 >= 1 else C_PRV, s=42, zorder=3)
        ax.text(v1 + (0.004 if v1 >= v0 else -0.004), i, f"{v1:.2f}", va="center", ha="left" if v1 >= v0 else "right", fontsize=8)
    ax.axvline(1, color="black", lw=1, ls="--")
    ax.set_yticks(range(len(o))); ax.set_yticklabels(o.index, fontsize=9)
    style(ax, f"Primaire : IPS par ancienne region, {lib_annee(a0)} (gris) -> {lib_annee(a1)} (couleur)", "")
    ax.grid(axis="x", alpha=.25); ax.grid(axis="y", alpha=0)
    html_png["regions"] = png_b64(fig, "fig3_regions.png", zf)

    if geo:
        fig, ax = plt.subplots(figsize=(6.6, 5.4))
        cmap = matplotlib.colormaps["RdBu"]; norm = matplotlib.colors.TwoSlopeNorm(vmin=0.85, vcenter=1.0, vmax=1.15)
        for f in geo["features"]:
            nom = f["properties"].get("ancienne_region"); v = R_pri[a1].get(nom)
            g = f["geometry"]; polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
            ok = v is not None and v == v
            ax.add_collection(PatchCollection([Polygon(pl[0], closed=True) for pl in polys],
                                              facecolor=cmap(norm(v)) if ok else "#dddddd", edgecolor="white", lw=.8))
            xs_ = [pt[0] for pl in polys for pt in pl[0]]; ys_ = [pt[1] for pl in polys for pt in pl[0]]
            dx, dy = {"Centre": (-0.05, -0.28), "Plateau-Central": (0.12, 0.22)}.get(nom, (0, 0))  # evite le chevauchement
            ax.text(sum(xs_) / len(xs_) + dx, sum(ys_) / len(ys_) + dy, f"{nom}\n{v:.2f}" if ok else str(nom), ha="center", va="center", fontsize=6.5)
        ax.autoscale_view(); ax.set_aspect("equal"); ax.axis("off")
        ax.set_title(f"Primaire {lib_annee(a1)} : IPS par ancienne region (13)", loc="left", fontsize=11, fontweight="bold")
        fig.colorbar(matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap), ax=ax, shrink=.6, label="IPS (1 = parite)")
        html_png["carte"] = png_b64(fig, "fig4_carte_13_regions.png", zf)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(sta.index.astype(int), sta["public"], marker="o", ms=4, color=C_PUB, label="Public")
    ax.plot(sta.index.astype(int), sta["prive"], marker="o", ms=4, color=C_PRV, label="Prive")
    ax.axhline(1, color="black", lw=1, ls="--")
    axe_annees(ax, sta.index)
    style(ax, "Primaire : IPS public / prive", "IPS"); ax.legend(frameon=False, fontsize=8)
    html_png["statut"] = png_b64(fig, "fig5_statut.png", zf)

    # ---------- textes calcules ----------
    bas = ind[ind.niveau_geographique != "national"].sort_values(f"ips_primaire_{a1}")
    b1, b2, h1 = bas.iloc[0], bas.iloc[1], bas.iloc[-1]
    e0, e1 = mil["ecart_urbain_moins_rural"].iloc[0], mil["ecart_urbain_moins_rural"].iloc[-1]
    nb_sous = int((bas[f"ips_primaire_{a1}"] < 0.97).sum())
    nb_cp1 = int((R_cp1[a1] < 1).sum())
    cles = [
        f"Au niveau national, l'IPS du primaire est passe de {N_pri[a0]:.2f} ({lib_annee(a0)}) a {N_pri[a1]:.2f} ({lib_annee(a1)}) ; "
        f"le prescolaire est a {N_pre[a1]:.2f} ; a l'entree au CP1 il est de {N_cp1[a1]:.2f}.",
        f"L'ecart urbain-rural en IPS (primaire) est passe de {e0:.3f} a {e1:.3f} point : il {'se reduit' if e1 < e0 else 'ne se reduit pas'} "
        f"(urbain {mil['urbain'].iloc[-1]:.2f}, rural {mil['rural'].iloc[-1]:.2f}).",
        f"Les ecarts regionaux restent marques : {b1['region']} ({b1[f'ips_primaire_{a1}']:.2f}) et {b2['region']} ({b2[f'ips_primaire_{a1}']:.2f}) "
        f"sont les plus bas, {h1['region']} ({h1[f'ips_primaire_{a1}']:.2f}) le plus haut ; {nb_sous} regions sur {len(bas)} sont sous 0,97.",
        f"A l'entree au CP1, l'IPS est sous 1 dans {nb_cp1} regions sur {len(R_cp1)} en {lib_annee(a1)} : "
        "l'ecart se forme des l'inscription, avant la progression dans le cycle.",
    ]
    limites = [
        "Donnees DGESS par ANCIENNE region (13) : la carte n'est pas faite sur les 17 regions actuelles (pas de donnee regionale par nouvelle region dans la base retenue).",
        "L'IPS d'effectifs mesure la presence des filles parmi les inscrits, pas leur scolarisation relative a la population (denominateurs de population non integres).",
        "Un IPS moyen cache des disparites infra-regionales (provinces, communes) et des retards d'age.",
        "Le classeur ne dit pas si les annees numeriques d'en-tete sont des annees de debut ou de fin : convention 'fin' controlee par les totaux des annuaires.",
        "Primaire 2017/18 : total national non retrouve dans les annuaires disponibles (controle manuel a faire).",
        "Les annees recentes peuvent etre provisoires.",
    ]

    def img(k, alt):
        return f'<figure><img alt="{alt}" src="data:image/png;base64,{html_png[k]}"></figure>' if k in html_png else ""
    li = lambda L: "".join(f"<li>{x}</li>" for x in L)
    html = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Parite filles-garcons - tableau de bord</title>
<style>:root{{--bg:#fff;--fg:#1a1a1a;--mut:#555;--card:#f5f6f8}}@media(prefers-color-scheme:dark){{:root{{--bg:#16181c;--fg:#eee;--mut:#aaa;--card:#22252b}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif}}main{{max-width:980px;margin:auto;padding:16px}}
h1{{font-size:1.5rem}}h2{{font-size:1.15rem;margin-top:2rem}}.card{{background:var(--card);border-radius:10px;padding:12px 18px}}
figure{{margin:12px 0}}img{{max-width:100%;height:auto;background:#fff;border-radius:8px}}small{{color:var(--mut)}}</style></head><body><main>
<h1>Parite filles-garcons et ecart urbain-rural au Burkina Faso</h1>
<small>Equipe {a.equipe} - Defi 2 - Source : annuaires statistiques DGESS, prescolaire et primaire {lib_annee(a0)} a {lib_annee(a1)} - genere le {date.today().isoformat()}</small>
<p><b>Lecture :</b> IPS = filles / garcons. 1,00 = parite ; sous 1 = moins de filles ; au-dessus de 1 = plus de filles.</p>
<h2>Ce qu'il faut retenir</h2><div class="card"><ul>{li(cles)}</ul></div>
<h2>Evolution nationale</h2>{img("national", "IPS national par niveau")}
<h2>Urbain / rural</h2>{img("milieu", "IPS urbain et rural")}
<h2>Ecarts entre regions</h2>{img("regions", "IPS par ancienne region")}{img("carte", "Carte des 13 anciennes regions")}
<h2>Public / prive</h2>{img("statut", "IPS public et prive")}
<h2>Limites</h2><div class="card"><ul>{li(limites)}</ul></div>
</main></body></html>"""
    zf.writestr("tableau-de-bord.html", html)
    zf.writestr("LISEZ-MOI.txt", "Ouvrir tableau-de-bord.html dans un navigateur (autonome, sans connexion). Figures PNG a part.\n"
                "Genere par scripts/analyse_template.py a partir de 03_transformation.\n")
    zf.close()
    with open(os.path.join(a.dossier04, pref + "tableau-de-bord_v1.zip"), "wb") as fh:
        fh.write(zbuf.getvalue())

    with open(os.path.join(a.dossier04, pref + "lisez-moi_v1.txt"), "w", encoding="utf-8") as fh:
        fh.write("ETAPE 4 - ANALYSE (Defi 2)\n\nEntrees : tables agregees de 03_transformation uniquement (parite-effectifs, GeoJSON 13 regions).\n"
                 "Sorties : indicateurs-cles.csv, ecart-urbain-rural.csv, tableau-de-bord.zip (html autonome + figures PNG).\n"
                 "Methode : IPS = filles/garcons ; tous les chiffres du texte sont calcules par le script.\n\nMessages cles :\n"
                 + "\n".join(f"- {x}" for x in cles) + "\n\nLimites :\n" + "\n".join(f"- {x}" for x in limites) + "\n")
    print("Messages cles :")
    for x in cles:
        print(" -", x)
    print(f"Figures : {len(html_png)} | regions : {len(bas)} | annees : {a0}-{a1}")


if __name__ == "__main__":
    main()
