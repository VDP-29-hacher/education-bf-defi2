#!/usr/bin/env python3
"""ETAPE 5 - INTERPRETATION : fiche de synthese nationale (page 1) + une fiche d'une page par region actuelle (pages 2 a 18).

Entrees : 04_analyse (indicateurs-cles, ecart-urbain-rural, acces-regions, indicateurs-provinces, effectifs-provinces-historique,
regions17-indicateurs, provinces-prioritaires, prevision scientist, zip des figures). Aucune donnee brute.
Sortie  : <EQ>_05-interpretation_D2_analyst_fiche-synthese_v1.pdf
Principe : chaque chiffre est calcule ; les causes ne sont jamais affirmees ; les recommandations sont des pistes.
Usage : interpretation_template.py DOSSIER_04 DOSSIER_05 [--equipe Burkina_Novation]
"""
import argparse, glob, io, os, sys, zipfile
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak

BLEU = colors.HexColor("#0b4f7a")


def lire(d, cle):
    f = glob.glob(os.path.join(d, f"*_{cle}_v1.csv"))
    if not f:
        sys.exit(f"Introuvable : *_{cle}_v1.csv dans {d} (lancez d'abord l'etape 4)")
    return pd.read_csv(f[0], sep=";", encoding="utf-8-sig")


def v2(x):
    return "n.d." if x != x else f"{x:.2f}".replace(".", ",")


def pct(x):
    return f"{x:.0f} %"   # espace insecable : le % ne part jamais seul a la ligne


def nbf(v):
    return f"{int(round(v)):,}".replace(",", " ")


def figure_acces(acc, annee):
    """TBS primaire par region : garcons et filles (points relies), annee donnee."""
    t = acc[(acc.indicateur == "tbs_primaire") & (acc.annee_debut == annee)].sort_values("taux_ensemble")
    fig, ax = plt.subplots(figsize=(5.2, 3.6), dpi=200)
    y = range(len(t))
    ax.hlines(y, t.taux_garcons, t.taux_filles, color="#9a9a96", lw=2.5)
    ax.scatter(t.taux_garcons, y, color="#2a78d6", s=22, label="Garçons", zorder=3)
    ax.scatter(t.taux_filles, y, color="#eb6834", s=22, label="Filles", zorder=3)
    for yy, (_, r) in zip(y, t.iterrows(), strict=True):
        ax.text(max(r.taux_garcons, r.taux_filles) + 3, yy, f"{r.taux_ensemble:.0f} %", va="center", fontsize=6.5)
    ax.set_yticks(list(y)); ax.set_yticklabels([("National" if r == "National" else r) for r in t.region], fontsize=6.8)
    ax.axvline(100, color="black", lw=0.8, ls="--")
    ax.set_xlim(0, max(130, t[["taux_garcons", "taux_filles"]].max().max() + 15)); ax.tick_params(axis="x", labelsize=6.5)
    ax.set_xlabel("Taux brut de scolarisation (%)", fontsize=7)
    ax.set_title(f"Accès : TBS du primaire par région, {annee}/{str(annee + 1)[2:]}", fontsize=8, fontweight="bold")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(frameon=False, fontsize=6.5, loc="lower right")
    fig.tight_layout()
    b = io.BytesIO(); fig.savefig(b, format="png"); plt.close(fig)
    return b.getvalue()


def figure_effectifs(serie, titre):
    """Effectifs du primaire d'une region par annee scolaire (barres, la meilleure annee en bleu fonce)."""
    fig, ax = plt.subplots(figsize=(5.0, 2.3), dpi=200)
    ans = list(serie.index); vals = list(serie.values); imax = vals.index(max(vals))
    ax.bar(range(len(ans)), vals, color=["#0b4f7a" if i == imax else "#9cc3e0" for i in range(len(ans))], width=0.7)
    ax.set_xticks(range(len(ans))); ax.set_xticklabels([f"{a}/{str(a + 1)[2:]}" for a in ans], fontsize=6, rotation=45)
    ax.tick_params(axis="y", labelsize=6); ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):,}".replace(",", " ")))
    ax.set_title(titre, fontsize=7.5, fontweight="bold")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    b = io.BytesIO(); fig.savefig(b, format="png"); plt.close(fig)
    return b.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dossier04"); ap.add_argument("dossier05"); ap.add_argument("--equipe", default="Burkina_Novation")
    a = ap.parse_args()
    os.makedirs(a.dossier05, exist_ok=True)
    pref = f"{a.equipe}_05-interpretation_D2_analyst_"
    ind, mil = lire(a.dossier04, "indicateurs-cles"), lire(a.dossier04, "ecart-urbain-rural")
    acc, pind = lire(a.dossier04, "acces-regions"), lire(a.dossier04, "indicateurs-provinces")
    prio, prev = lire(a.dossier04, "provinces-prioritaires"), lire(a.dossier04, "prevision-ips-provinces")
    r17, effh = lire(a.dossier04, "regions17-indicateurs"), lire(a.dossier04, "effectifs-provinces-historique")
    bt = lire(a.dossier04, "prevision-backtest")
    fmc = glob.glob(os.path.join(os.path.dirname(os.path.abspath(a.dossier04)), "03_transformation", "*_modele-commun-region-annee_v1.csv"))
    plus100 = ""
    if fmc:
        mc = pd.read_csv(fmc[0], sep=";", encoding="utf-8-sig")
        mcn = mc[(mc.region == "National") & (mc.annee_debut == mc.annee_debut.max())].iloc[0]
        plus100 = f" Il faudrait {nbf(mcn.eleves_en_plus_pour_tbs100_primaire)} élèves de plus pour atteindre un taux brut de 100 %."
    q80_h = bt[bt.retenu.astype(str) == "True"].sort_values("horizon").q80.iloc[-1]   # marge a 80 % au dernier horizon
    zp = glob.glob(os.path.join(a.dossier04, "*tableau-de-bord_v1.zip"))
    if not zp:
        sys.exit("Zip de l'etape 4 introuvable.")
    fig = {n: zipfile.ZipFile(zp[0]).read(n) for n in zipfile.ZipFile(zp[0]).namelist() if n.endswith(".png")}

    c0 = [c for c in ind.columns if c.startswith("ips_primaire_")]
    y0, y1 = c0[0][-4:], c0[-1][-4:]
    k0, k1 = f"ips_primaire_{y0}", f"ips_primaire_{y1}"
    reg = ind[ind.niveau_geographique != "national"].sort_values(k1)
    nat = ind[ind.niveau_geographique == "national"].iloc[0]
    ya = lambda y: f"{y}/{str(int(y) + 1)[2:]}"
    e0, e1 = mil.ecart_urbain_moins_rural.iloc[0], mil.ecart_urbain_moins_rural.iloc[-1]
    a1 = int(acc.annee_debut.max()); a0 = int(acc.annee_debut.min())
    tbs = acc[acc.indicateur == "tbs_primaire"]
    tn = tbs[tbs.region == "National"].set_index("annee_debut")
    tr = tbs[(tbs.annee_debut == a1) & (tbs.region != "National")].sort_values("taux_ensemble")
    pk = [c for c in pind.columns if c.startswith("ips_20")][-1]
    pa = pind.sort_values("effectif_dernier_sur_max")
    pacc = pind[pind.effectif_dernier_sur_max < 0.6]
    p1 = prio[prio.priorite == 1]
    pcol = [c for c in prev.columns if c.startswith("ips_prevu_")][-1]
    sous = prev[prev.statut_horizon.str.startswith("sous")]
    n_ur = int((pind.ecart_urbain_moins_rural > 0).sum())

    # ---------------- page 1 : synthese nationale ----------------
    fl_ = glob.glob(os.path.join(a.dossier04, "*_liens-indicateurs_v1.csv"))
    lien_txt = ""
    if fl_:
        Lk = pd.read_csv(fl_[0], sep=";", encoding="utf-8-sig")
        s0 = Lk[Lk.question.str.startswith("Les provinces où l'accès est faible")]
        if len(s0) and str(s0.significatif_5pc.iloc[0]) == "True":
            lien_txt = (f" Les écarts se cumulent : là où l'accès est faible, il y a aussi moins de filles (corrélation de "
                        f"{v2(s0.rho_spearman.iloc[0])}, significative).")
    constats = [
        f"<b>L'accès est le premier écart.</b> En {ya(a1)}, le taux brut de scolarisation (TBS) du primaire est de {pct(tr.iloc[0].taux_ensemble)} "
        f"au {tr.iloc[0].region} et de {pct(tr.iloc[1].taux_ensemble)} à l'{tr.iloc[1].region}, contre {pct(tr.iloc[-1].taux_ensemble)} au "
        f"{tr.iloc[-1].region}. Au niveau national, il est passé de {pct(tn.loc[a0, 'taux_ensemble'])} en {ya(a0)} à {pct(tn.loc[a1, 'taux_ensemble'])}."
        + plus100,
        f"<b>Des provinces se vident.</b> {len(pacc)} provinces sur {len(pind)} comptent moins de 60 % des élèves de leur meilleure année : "
        + ", ".join(f"{r.province} ({r.effectif_dernier_sur_max:.0%})".replace("%", " %") for _, r in pa.head(5).iterrows())
        + f". Ensemble, elles ont perdu {nbf(pacc.eleves_perdus_depuis_max.sum())} élèves.",
        f"<b>La parité progresse, mais pas partout.</b> L'indice de parité (IPS) du primaire passe de {v2(nat[k0])} à {v2(nat[k1])}. "
        f"L'écart se forme dès l'entrée au CP1 ({v2(nat[f'ips_cp1_nouveaux_inscrits_{y1}'])}) et reste net au {reg.iloc[0].region} "
        f"({v2(reg.iloc[0][k1])}) et au {reg.iloc[1].region} ({v2(reg.iloc[1][k1])}). Il faudrait inscrire {nbf(pind.filles_manquantes_parite.sum())} "
        "filles de plus pour atteindre la parité dans toutes les provinces." + lien_txt,
        f"<b>Ville et campagne.</b> L'écart d'IPS a été divisé par {f'{e0 / e1:.1f}'.replace('.', ',')}, mais l'IPS rural reste plus bas que "
        f"l'urbain dans {n_ur} provinces sur {len(pind)}.",
    ]
    ou = [f"<b>Priorité 1</b>, avec une parité sous 0,95 et des effectifs sous 60 % de leur meilleur niveau : {', '.join(p1.province)}.",
          f"<b>Si rien ne change</b>, {len(sous)} provinces resteront sous 0,95 en {ya(pcol[-4:])} : {', '.join(sous.province)}. "
          "Cette projection a été testée sur les années passées ; sa marge d'erreur est indiquée dans le dossier."]
    pistes = [
        "Rétablir une offre scolaire là où les effectifs se sont effondrés : réouverture, classes temporaires, accueil des élèves déplacés.",
        "Dans les provinces de priorité 1, se fixer un objectif d'inscription des filles au CP1.",
        "Suivre chaque année, par province et par sexe, les effectifs, l'IPS et le TBS, avec le tableau de bord et les fiches régionales qui suivent.",
    ]
    limites = [
        "Les statistiques régionales publiées restent sur les 13 anciennes régions ; les fiches régionales (17 régions actuelles) ne couvrent que le primaire.",
        "Nous n'affirmons aucune cause : l'insécurité est l'explication la plus plausible de la chute des effectifs, mais elle n'est pas testée ici.",
        "Quatre IPS calculés sur des effectifs effondrés sont retirés et signalés ; le total national du primaire 2017/18 manque.",
    ]

    st = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=st["Heading1"], fontSize=14.5, spaceAfter=2, leading=17, textColor=BLEU)
    h2 = ParagraphStyle("h2", parent=st["Heading2"], fontSize=10, spaceBefore=5, spaceAfter=2, textColor=BLEU)
    bd = ParagraphStyle("bd", parent=st["BodyText"], fontSize=8.3, leading=10.4, spaceAfter=2)
    sm = ParagraphStyle("sm", parent=bd, fontSize=7, textColor=colors.grey)
    kpi_v = ParagraphStyle("kv", parent=bd, fontSize=13, leading=15, textColor=BLEU, fontName="Helvetica-Bold")
    kpi_l = ParagraphStyle("kl", parent=bd, fontSize=7, leading=8.5, textColor=colors.HexColor("#52514e"))
    tab = ParagraphStyle("tb", parent=bd, fontSize=7.2, leading=8.6, spaceAfter=0)
    li = lambda L: [Paragraph("• " + x, bd) for x in L]

    def img(data, w, h):
        iw, ih = ImageReader(io.BytesIO(data)).getSize()
        k = min(w / iw, h / ih)
        return Image(io.BytesIO(data), width=iw * k, height=ih * k)

    S = [Paragraph("Disparités d'accès à l'école au Burkina Faso : où agir en priorité ?", h1),
         Paragraph(f"Équipe {a.equipe} · Défi 2 · préscolaire et primaire, {ya(y0)} à {ya(y1)} · "
                   "IPS = filles ÷ garçons (1 = parité) · TBS = élèves rapportés à la population d'âge scolaire", sm),
         Paragraph("Ce que disent les données", h2)] + li(constats)
    carte = fig.get("fig4_carte_13_regions.png")
    S += [Spacer(1, 3), Table([[img(figure_acces(acc, a1), 8.8 * cm, 5.8 * cm), img(carte, 8.8 * cm, 5.8 * cm) if carte else Spacer(1, 1)]],
                              colWidths=[9 * cm, 9 * cm], style=TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))]
    S += [Paragraph("Où agir", h2)] + li(ou)
    S += [Paragraph("Nos pistes d'action", h2)] + li(pistes)
    S += [Paragraph("Limites", h2)] + li(limites)
    S += [Spacer(1, 3), Paragraph("Sources : annuaires statistiques DGESS (préscolaire, primaire 2024-2025) et taux publiés par la DGESS ; "
                                  "découpage COD-AB (IGB/OCHA). Tous les chiffres sont calculés par le pipeline. Les pages suivantes "
                                  "donnent une fiche par région actuelle.", sm)]

    # ---------------- pages 2 a 18 : une fiche par region actuelle ----------------
    an = int(pk[-4:])
    ecols = [c for c in r17.columns if c.startswith("effectif_20")]
    pr_map = dict(zip(prio.province, prio.priorite, strict=True))
    pv = prev.set_index("province")
    ef = effh.set_index("province")
    pi = pind.set_index("province")
    for _, R in r17.sort_values("effectif_dernier_sur_max").iterrows():
        provs = [p.strip() for p in str(R.provinces).split(",")]
        serie = pd.Series([R[c] for c in ecols], index=[int(c[-4:]) for c in ecols])
        amax = int(serie.idxmax()); part = R.effectif_dernier_sur_max
        S += [PageBreak(), Paragraph(f"Région {R.nouvelle_region}", h1),
              Paragraph(f"Fiche régionale · primaire {ya(an)} · ancienne région : {R.anciennes_regions} · provinces : {', '.join(provs)}", sm),
              Spacer(1, 6)]
        kpis = [(nbf(R[f'effectif_{an}']), f"élèves au primaire en {ya(an)}"),
                (f"{part:.0%}".replace("%", " %"), f"du meilleur effectif ({ya(amax)})"),
                (v2(R[f'ips_{an}']), "indice de parité filles ÷ garçons"),
                (nbf(R.filles_manquantes_parite), "filles à inscrire pour la parité")]
        S += [Table([[Paragraph(v, kpi_v) for v, _ in kpis], [Paragraph(l_, kpi_l) for _, l_ in kpis]], colWidths=[4.5 * cm] * 4,
                    style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#e8f1f8")), ("LEFTPADDING", (0, 0), (-1, -1), 7),
                                      ("TOPPADDING", (0, 0), (-1, 0), 6), ("BOTTOMPADDING", (0, -1), (-1, -1), 6),
                                      ("LINEAFTER", (0, 0), (-2, -1), 1.5, colors.white)]))]
        # texte redige a partir des chiffres de la region
        if part >= 0.995:
            t_acc = f"La région n'a jamais compté autant d'élèves au primaire : {nbf(R[f'effectif_{an}'])} en {ya(an)}."
        else:
            t_acc = (f"La région compte {nbf(R[f'effectif_{an}'])} élèves au primaire en {ya(an)}, soit {part:.0%} de son niveau de {ya(amax)}. "
                     f"Elle a perdu {nbf(R.eleves_perdus_depuis_max)} élèves depuis cette année-là.").replace("%", " %")
        ips = R[f"ips_{an}"]
        if ips >= 1:
            t_par = f"Les filles sont au moins aussi nombreuses que les garçons (IPS {v2(ips)})."
        else:
            t_par = (f"Il y a {v2(ips)} fille pour un garçon ; il faudrait inscrire {nbf(R.filles_manquantes_parite)} filles de plus pour atteindre "
                     "la parité.")
        if R.ecart_urbain_moins_rural == R.ecart_urbain_moins_rural:
            t_par += (f" À la campagne, l'IPS est de {v2(R.ips_rural)}, " +
                      ("plus bas qu'en ville." if R.ecart_urbain_moins_rural > 0.005 else "proche de celui de la ville."))
        pp = [p for p in provs if pr_map.get(p) == 1]
        p2 = [p for p in provs if pr_map.get(p) == 2]
        t_pri = (f"À suivre en priorité : {', '.join(pp)}." if pp else "Aucune province de la région n'est en priorité 1.") + \
                (f" En priorité 2 : {', '.join(p2)}." if p2 else "")
        S += [Spacer(1, 8), Paragraph(t_acc, bd), Paragraph(t_par, bd), Paragraph(t_pri, bd), Spacer(1, 4),
              img(figure_effectifs(serie, f"Élèves du primaire, région {R.nouvelle_region}"), 15 * cm, 6.5 * cm), Spacer(1, 6),
              Paragraph("Les provinces de la région", h2)]
        lignes = [["Province", f"Élèves {ya(an)}", "Part du meilleur", "IPS", "IPS rural", "Écart ville-campagne", "Priorité", f"Projection {ya(pcol[-4:])}"]]
        for p in sorted(provs, key=lambda x: pi.loc[x, "effectif_dernier_sur_max"] if x in pi.index else 9):
            if p not in pi.index:
                continue
            i_ = pi.loc[p]
            lignes.append([p, nbf(ef.loc[p, f"effectif_{an}"]) if p in ef.index else "", f"{i_.effectif_dernier_sur_max:.0%}".replace("%", " %"),
                           v2(i_[pk]), v2(i_.ips_rural), v2(i_.ecart_urbain_moins_rural).replace("n.d.", ""),
                           {1: "1", 2: "2"}.get(pr_map.get(p), ""), v2(pv.loc[p, pcol]) if p in pv.index else ""])
        S += [Table([[Paragraph(str(c), tab) for c in l_] for l_ in lignes], repeatRows=1,
                    colWidths=[2.9 * cm, 2.1 * cm, 2.1 * cm, 1.4 * cm, 1.6 * cm, 2.6 * cm, 1.6 * cm, 2.4 * cm],
                    style=TableStyle([("BACKGROUND", (0, 0), (-1, 0), BLEU), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                                      ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f8")]),
                                      ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c9cdd3")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))]
        S += [Spacer(1, 6), Paragraph("Priorité 1 : IPS sous 0,95 et effectifs sous 60 % du meilleur niveau depuis 2015 ; priorité 2 : un seul des deux. "
                                      f"La projection suppose que la situation actuelle se prolonge (marge d'erreur de ±{f'{q80_h:.2f}'.replace('.', ',')} "
                                      "à trois ans, 8 fois sur 10).", sm)]

    def pied(canvas, doc):
        canvas.saveState(); canvas.setFont("Helvetica", 7); canvas.setFillColor(colors.grey)
        canvas.drawString(1.4 * cm, 0.6 * cm, f"Équipe {a.equipe} · Défi 2 · Data Challenge Burkina 2026")
        canvas.drawRightString(A4[0] - 1.4 * cm, 0.6 * cm, f"Page {doc.page}")
        canvas.restoreState()

    SimpleDocTemplate(os.path.join(a.dossier05, pref + "fiche-synthese_v1.pdf"), pagesize=A4, leftMargin=1.4 * cm, rightMargin=1.4 * cm,
                      topMargin=1.1 * cm, bottomMargin=1.2 * cm, title="Fiche de synthèse et fiches régionales - Défi 2",
                      author=f"Équipe {a.equipe}").build(S, onFirstPage=pied, onLaterPages=pied)
    print(f"Fiche de synthese generee : 1 page nationale + {len(r17)} fiches regionales.")


if __name__ == "__main__":
    main()
