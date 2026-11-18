#!/usr/bin/env python3
"""LISEZ-MOI au format PDF : un document general (plan de la documentation et criteres du jury) et un document par etape (01 a 04).

Mise en page de rapport : page de garde, sommaire cliquable, signets, en-tetes et pieds de page numerotes, tableaux.
Les chiffres sont lus dans les sorties du pipeline ; rien n'est saisi a la main.
Sorties : LISEZ-MOI.pdf a la racine ; 05_interpretation/lisez-moi/<EQ>_0X-..._lisez-moi_v1.pdf (repris tels quels dans le depot).
Usage   : lisez_moi_pdf.py [--racine DOSSIER] [--equipe Burkina_Novation]
"""
import argparse, csv, glob, json, os, sys
from collections import Counter
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, NextPageTemplate, PageBreak, PageTemplate, Paragraph, Spacer, Table,
                                TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

BLEU, BLEU2, ROUGE, OR, VERT = colors.HexColor("#102B52"), colors.HexColor("#173D6D"), colors.HexColor("#E53935"), colors.HexColor("#F5B51B"), colors.HexColor("#159B65")
TEXTE, GRIS, GRILLE, FOND = colors.HexColor("#1E293B"), colors.HexColor("#64748B"), colors.HexColor("#DCE3EC"), colors.HexColor("#F3F6FA")

# ---------------------------------------------------------------- polices (Segoe UI sous Windows, sinon Helvetica)
POLICES = {"r": "Helvetica", "b": "Helvetica-Bold", "sb": "Helvetica-Bold", "l": "Helvetica", "i": "Helvetica-Oblique"}
_dossier = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
_ttf = {"r": "segoeui.ttf", "b": "segoeuib.ttf", "sb": "seguisb.ttf", "l": "segoeuil.ttf", "i": "segoeuii.ttf"}
if all(os.path.exists(os.path.join(_dossier, f)) for f in _ttf.values()):
    for k, f in _ttf.items():
        pdfmetrics.registerFont(TTFont(f"Segoe-{k}", os.path.join(_dossier, f)))
        POLICES[k] = f"Segoe-{k}"
    pdfmetrics.registerFontFamily("Segoe-r", normal="Segoe-r", bold="Segoe-b", italic="Segoe-i", boldItalic="Segoe-b")
SPECIAUX = POLICES["r"].startswith("Segoe")          # les caracteres ≈ ÷ ρ → n'existent pas dans Helvetica


def t(s):
    """Texte sur pour la police : remplace quelques signes si la police standard est utilisee."""
    if SPECIAUX:
        return s
    for a, b in (("≈", "env."), ("÷", "/"), ("ρ", "rho"), ("→", "->"), ("×", "x"), ("≥", ">="), ("≤", "<="), ("\u202f", " ")):
        s = s.replace(a, b)
    return s


ST = {
    "corps": ParagraphStyle("corps", fontName=POLICES["r"], fontSize=10.2, leading=15.2, textColor=TEXTE, spaceAfter=7, alignment=TA_LEFT),
    "puce": ParagraphStyle("puce", fontName=POLICES["r"], fontSize=10.2, leading=15, textColor=TEXTE, leftIndent=14, bulletIndent=3, spaceAfter=3),
    "h1": ParagraphStyle("h1", fontName=POLICES["b"], fontSize=17, leading=22, textColor=BLEU, spaceBefore=8, spaceAfter=10),
    "h2": ParagraphStyle("h2", fontName=POLICES["sb"], fontSize=12.5, leading=17, textColor=BLEU2, spaceBefore=10, spaceAfter=6),
    "cellule": ParagraphStyle("cellule", fontName=POLICES["r"], fontSize=9, leading=12.4, textColor=TEXTE),
    "cellule_t": ParagraphStyle("cellule_t", fontName=POLICES["sb"], fontSize=9, leading=12, textColor=colors.white),
    "code": ParagraphStyle("code", fontName="Courier", fontSize=8.6, leading=12, textColor=colors.HexColor("#E3EEF3"), leftIndent=8, rightIndent=8),
    "encadre": ParagraphStyle("encadre", fontName=POLICES["r"], fontSize=9.8, leading=14.4, textColor=TEXTE),
    "titre_sommaire": ParagraphStyle("titre_sommaire", fontName=POLICES["b"], fontSize=17, leading=22, textColor=BLEU, spaceAfter=12),
    "toc1": ParagraphStyle("toc1", fontName=POLICES["r"], fontSize=10.5, leading=19, textColor=TEXTE, leftIndent=4),
    "toc2": ParagraphStyle("toc2", fontName=POLICES["r"], fontSize=9.5, leading=15, textColor=GRIS, leftIndent=18),
}


def P(x, s="corps"):
    return Paragraph(t(x), ST[s])


def H1(x):
    return Paragraph(t(x), ST["h1"])


def H2(x):
    return Paragraph(t(x), ST["h2"])


def puces(items):
    return [Paragraph(t(x), ST["puce"], bulletText="•") for x in items]


def tableau(entetes, lignes, largeurs):
    data = [[Paragraph(t(h), ST["cellule_t"]) for h in entetes]] + [[Paragraph(t(str(c)), ST["cellule"]) for c in l] for l in lignes]
    tb = Table(data, colWidths=[w * mm for w in largeurs], repeatRows=1, hAlign="LEFT")
    style = [("BACKGROUND", (0, 0), (-1, 0), BLEU2), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 5),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
             ("LINEBELOW", (0, 0), (-1, -1), 0.5, GRILLE), ("BOX", (0, 0), (-1, -1), 0.6, GRILLE)]
    style += [("BACKGROUND", (0, i), (-1, i), FOND) for i in range(2, len(data), 2)]
    tb.setStyle(TableStyle(style))
    return [tb, Spacer(1, 8)]


def encadre(texte, couleur=OR):
    tb = Table([[Paragraph(t(texte), ST["encadre"])]], colWidths=[170 * mm], hAlign="LEFT")
    tb.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF8E6") if couleur == OR else colors.HexColor("#E8F6EF")),
                            ("LINEBEFORE", (0, 0), (0, -1), 3, couleur), ("LEFTPADDING", (0, 0), (-1, -1), 10),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return [tb, Spacer(1, 10)]


def code(lignes):
    tb = Table([[Paragraph("<br/>".join(l.replace("&", "&amp;").replace("<", "&lt;") for l in lignes), ST["code"])]], colWidths=[170 * mm], hAlign="LEFT")
    tb.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0F1A20")), ("TOPPADDING", (0, 0), (-1, -1), 8),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("LEFTPADDING", (0, 0), (-1, -1), 6)]))
    return [tb, Spacer(1, 10)]


# ---------------------------------------------------------------- dessin : symbole ÉDUCATION BF (livre, etoile, socle tricolore)
def symbole(c, x, y, taille):
    s = taille / 48.0
    X = lambda u: x + u * s
    Y = lambda v: y + (48 - v) * s
    c.saveState()
    c.setFillColor(BLEU2); c.setStrokeColor(colors.Color(1, 1, 1, alpha=0.15))
    c.roundRect(X(1), Y(47), 46 * s, 46 * s, 13 * s, fill=1, stroke=1)
    c.setStrokeColor(OR); c.setLineWidth(1.6 * s); c.setLineCap(1)
    p = c.beginPath(); p.moveTo(X(12.5), Y(21.5)); p.curveTo(X(15.5), Y(15.8), X(19.4), Y(12.6), X(22.6), Y(11.9)); c.drawPath(p, stroke=1, fill=0)
    etoile = [(27.5, 6.2), (28.95, 9.5), (32.53, 9.82), (29.82, 12.19), (30.62, 15.69), (27.5, 13.84), (24.38, 15.69), (25.18, 12.19), (22.47, 9.82), (26.05, 9.5)]
    p = c.beginPath(); p.moveTo(X(etoile[0][0]), Y(etoile[0][1]))
    for u, v in etoile[1:]:
        p.lineTo(X(u), Y(v))
    p.close(); c.setFillColor(OR); c.drawPath(p, stroke=0, fill=1)
    for pts, col in (([(9.5, 34.5), (23, 35.7), (23, 21.4), (9.5, 20.2)], colors.HexColor("#EAF0F8")), ([(25, 35.7), (38.5, 32.1), (38.5, 16.7), (25, 21.4)], colors.white)):
        p = c.beginPath(); p.moveTo(X(pts[0][0]), Y(pts[0][1]))
        for u, v in pts[1:]:
            p.lineTo(X(u), Y(v))
        p.close(); c.setFillColor(col); c.drawPath(p, stroke=0, fill=1)
    for x0, w, col in ((9.5, 12.4, ROUGE), (22.6, 2.8, OR), (26.1, 12.4, VERT)):
        c.setFillColor(col); c.roundRect(X(x0), Y(41.4), w * s, 2.8 * s, 1.4 * s, fill=1, stroke=0)
    c.restoreState()


# ---------------------------------------------------------------- gabarit de document
class Rapport(BaseDocTemplate):
    def __init__(self, chemin, titre, sous_titre, etiquette, meta, **kw):
        super().__init__(chemin, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=24 * mm, bottomMargin=20 * mm,
                         title=titre, author=meta["auteur"], subject=meta["sujet"], keywords=meta["mots"], creator=meta["createur"], **kw)
        self.titre, self.sous_titre, self.etiquette, self.meta = titre, sous_titre, etiquette, meta
        cadre = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="corps")
        self.addPageTemplates([PageTemplate(id="garde", frames=[cadre], onPage=self.garde), PageTemplate(id="page", frames=[cadre], onPage=self.page)])

    def garde(self, c, doc):
        W, H = A4
        c.saveState()
        c.setFillColor(BLEU); c.rect(0, H - 118 * mm, W, 118 * mm, fill=1, stroke=0)
        c.setFillColor(BLEU2); c.rect(0, H - 118 * mm, W, 4, fill=1, stroke=0)
        for i, col in enumerate((ROUGE, OR, VERT)):
            c.setFillColor(col); c.rect(i * W / 3, H - 121 * mm, W / 3, 3 * mm, fill=1, stroke=0)
        symbole(c, 20 * mm, H - 46 * mm, 26 * mm)
        c.setFillColor(colors.white); c.setFont(POLICES["b"], 15); c.drawString(50 * mm, H - 31 * mm, t("ÉDUCATION BF"))
        c.setFillColor(colors.HexColor("#AFC2D8")); c.setFont(POLICES["r"], 10); c.drawString(50 * mm, H - 37 * mm, t("Suivi et pilotage scolaire"))
        c.setFillColor(OR); c.setFont(POLICES["sb"], 10.5); c.drawString(20 * mm, H - 66 * mm, t(self.etiquette.upper()))
        c.setFillColor(colors.white); c.setFont(POLICES["b"], 25)
        y = H - 80 * mm
        for ligne in self.couper(self.titre, POLICES["b"], 25, W - 40 * mm):
            c.drawString(20 * mm, y, t(ligne)); y -= 10.5 * mm
        c.setFillColor(colors.HexColor("#D5E0EE")); c.setFont(POLICES["r"], 12)
        for ligne in self.couper(self.sous_titre, POLICES["r"], 12, W - 40 * mm):
            c.drawString(20 * mm, y + 2 * mm, t(ligne)); y -= 6 * mm
        infos = [("Challenge", "Data Challenge Burkina 2026, édition Éducation"), ("Défi", "Défi 2 : écarts d'accès à l'école (filles et garçons, ville et campagne)"),
                 ("Équipe", self.meta["auteur"]), ("Version", f"v1 du {date.today().strftime('%d/%m/%Y')}")]
        y = 92 * mm
        for k, v in infos:
            c.setFillColor(GRIS); c.setFont(POLICES["sb"], 9); c.drawString(20 * mm, y, t(k.upper()))
            c.setFillColor(TEXTE); c.setFont(POLICES["r"], 11); c.drawString(52 * mm, y, t(v)); y -= 9 * mm
        c.setStrokeColor(GRILLE); c.setLineWidth(0.6); c.line(20 * mm, 30 * mm, W - 20 * mm, 30 * mm)
        c.setFillColor(GRIS); c.setFont(POLICES["r"], 8.5)
        c.drawString(20 * mm, 24 * mm, t("Données agrégées et publiques : DGESS / MENAPLN, INSD, IGB / OCHA (COD-AB)."))
        c.drawString(20 * mm, 19.5 * mm, t("Les chiffres de ce document sont recalculés par le pipeline à chaque relance."))
        c.restoreState()

    def page(self, c, doc):
        W, H = A4
        c.saveState()
        symbole(c, 20 * mm, H - 17 * mm, 8 * mm)
        c.setFillColor(BLEU); c.setFont(POLICES["sb"], 8.5); c.drawString(30 * mm, H - 13 * mm, t("ÉDUCATION BF · Défi 2"))
        c.setFillColor(GRIS); c.setFont(POLICES["r"], 8.5); c.drawRightString(W - 20 * mm, H - 13 * mm, t(self.etiquette))
        for i, col in enumerate((ROUGE, OR, VERT)):
            c.setFillColor(col); c.rect(20 * mm + i * (W - 40 * mm) / 3, H - 19.5 * mm, (W - 40 * mm) / 3, 0.9 * mm, fill=1, stroke=0)
        c.setStrokeColor(GRILLE); c.setLineWidth(0.5); c.line(20 * mm, 13 * mm, W - 20 * mm, 13 * mm)
        c.setFillColor(GRIS); c.setFont(POLICES["r"], 8)
        c.drawString(20 * mm, 8.5 * mm, t(f"{self.meta['auteur']} · Data Challenge Burkina 2026"))
        c.restoreState()

    @staticmethod
    def couper(texte, police, taille, largeur):
        mots, lignes, cour = t(texte).split(), [], ""
        for m in mots:
            essai = (cour + " " + m).strip()
            if pdfmetrics.stringWidth(essai, police, taille) > largeur and cour:
                lignes.append(cour); cour = m
            else:
                cour = essai
        return lignes + ([cour] if cour else [])

    def afterFlowable(self, f):
        if isinstance(f, Paragraph) and f.style.name in ("h1", "h2"):
            niveau = 0 if f.style.name == "h1" else 1
            cle = f"s{id(f)}"
            self.canv.bookmarkPage(cle)
            self.canv.addOutlineEntry(f.getPlainText(), cle, level=niveau, closed=False)
            self.notify("TOCEntry", (niveau, f.getPlainText(), self.page, cle))


def construire(chemin, titre, sous_titre, etiquette, contenu, meta):
    toc = TableOfContents(levelStyles=[ST["toc1"], ST["toc2"]], dotsMinLevel=0)
    histoire = [NextPageTemplate("page"), PageBreak(), Paragraph("Sommaire", ST["titre_sommaire"]), toc, PageBreak()] + contenu
    doc = Rapport(chemin, titre, sous_titre, etiquette, meta)
    doc.multiBuild(histoire, canvasmaker=CanevasNumerote)
    return doc.page


from reportlab.pdfgen.canvas import Canvas  # noqa: E402


class CanevasNumerote(Canvas):
    """Ouvre le panneau des signets et ecrit « Page X sur Y » une fois le nombre total de pages connu (sauf en page de garde)."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.showOutline()
        self._pages = []

    def showPage(self):
        self._pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._pages)
        for etat in self._pages:
            self.__dict__.update(etat)
            if self._pageNumber > 1:
                self.saveState(); self.setFont(POLICES["r"], 8); self.setFillColor(GRIS)
                self.drawRightString(A4[0] - 20 * mm, 8.5 * mm, t(f"Page {self._pageNumber} sur {total}")); self.restoreState()
            super().showPage()
        super().save()


# ---------------------------------------------------------------- donnees du pipeline
def un(motif):
    f = sorted(glob.glob(motif))
    if not f:
        sys.exit(f"Introuvable : {motif} (lancez d'abord le pipeline)")
    return f[0]


def lire_csv(motif):
    with open(un(motif), encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


f2 = lambda v: "n.d." if v is None else f"{v:.2f}".replace(".", ",")
f3 = lambda v: "n.d." if v is None else f"{v:.3f}".replace(".", ",")
pc = lambda v: "n.d." if v is None else f"{round(v)} %"
nb = lambda v: "n.d." if v is None else f"{round(v):,}".replace(",", "\u202f")
ya = lambda y: f"{y}/{str(y + 1)[2:]}"


def chiffres(R):
    D = json.load(open(un(os.path.join(R, "04_analyse", "*_donnees-plateforme_v1.json")), encoding="utf-8"))
    reg = lire_csv(os.path.join(R, "01_collecte", "*_registre-sources_v1.csv"))
    sig = lire_csv(os.path.join(R, "04_analyse", "*_ips-provinces-signalements_v1.csv"))
    Y = D["years"]; n1 = len(Y) - 1
    I, Pv = D["prov"]["ind"], D["prov"]
    z = D["acc"]["tbs_primaire"]["z"]
    rs = sorted([r for r in D["regions"] if z.get(r) and z[r]["t"][n1] is not None], key=lambda r: z[r]["t"][n1])
    ips = {n: Pv["hist"][n][n1] for n in Pv["names"] if Pv["hist"][n][n1] is not None}
    acc60 = sorted([n for n in Pv["names"] if (I[n]["effectif_dernier_sur_max"] or 1) < 0.6], key=lambda n: I[n]["effectif_dernier_sur_max"])
    reg_ips = sorted([(r, D["pri"][r][n1]) for r in D["regions"] if D["pri"][r][n1] is not None], key=lambda x: x[1])
    bt = D["bt"]; ret = next(b["modele"] for b in bt if b["retenu"] in (True, "True"))
    return dict(
        D=D, reg=reg, dec=Counter(r["decision_defi2"] for r in reg), sig=sig, Y=Y, n1=n1, y0=ya(Y[0]), y1=ya(Y[n1]), I=I, Pv=Pv, z=z, rs=rs,
        gap=[None if u is None or r is None else u - r for u, r in zip(D["mil"]["urbain"], D["mil"]["rural"], strict=True)],
        rural_bas=sum(1 for n in Pv["names"] if (I[n]["ecart_urbain_moins_rural"] or 0) > 0), acc60=acc60,
        perdus=sum(I[n]["eleves_perdus_depuis_max"] or 0 for n in acc60), filles=sum(I[n]["filles_manquantes_parite"] or 0 for n in Pv["names"]),
        ips=ips, ips_bas=sorted(ips, key=ips.get), p1=[r["province"] for r in Pv["prio"] if r["priorite"] == 1],
        p2=[r["province"] for r in Pv["prio"] if r["priorite"] == 2], mc=next(x for x in D["mc"] if x["r"] == "National"),
        pt=sorted(D["ptbs"]["rows"], key=lambda x: x["t"]) if D.get("ptbs") else [], sous=sorted(n for n, v in Pv["prev"].items() if v["statut"].startswith("sous")),
        an_prev=ya(Pv["prevAns"][-1]), ret=ret, q={b["horizon"]: b for b in bt if b["modele"] == ret}, mods=sorted({b["modele"] for b in bt}),
        liens=D.get("liens") or [], typo=D.get("typo"), reg_ips=reg_ips)


# ---------------------------------------------------------------- contenus
def general(C, eq):
    D, z, rs, n1 = C["D"], C["z"], C["rs"], C["n1"]
    lo, hi = rs[0], rs[-1]
    sig_l = [l for l in C["liens"] if l["sig"]]
    groupes = Counter((r["g"], r["nom"]) for r in C["typo"]["rows"]) if C["typo"] else Counter()
    x = []
    x += [H1("1. Le défi"),
          P("La question posée par le Défi 2 est la suivante : où les écarts d'accès à l'école sont-ils les plus grands, entre filles et garçons "
            "et entre ville et campagne, et ces écarts évoluent-ils ?"),
          P(f"Nous l'avons reformulée ainsi. Dans quelles régions et quelles provinces les enfants vont-ils le moins à l'école ? Où les filles "
            f"ont-elles le plus de retard sur les garçons, et la campagne sur la ville ? Ces écarts se réduisent-ils depuis {C['y0']}, et où "
            "faut-il agir en premier ?"),
          P(f"Trois écarts sont suivis ensemble, au primaire et au préscolaire, de {C['y0']} à {C['y1']}. L'écart entre territoires se lit dans le "
            "taux brut de scolarisation (TBS) et dans la perte d'élèves d'une province. L'écart entre filles et garçons se lit dans l'indice de "
            "parité (IPS, filles ÷ garçons, 1,00 étant la parité). L'écart entre ville et campagne est la différence entre l'IPS urbain et l'IPS rural."),
          P("Le travail est réparti entre quatre rôles : l'Engineer pour la collecte et le nettoyage, l'Architect pour le modèle commun et la liaison "
            "des territoires, l'Analyst pour les indicateurs, le tableau de bord et l'interprétation, le Scientist pour les liens, les profils et la prévision.")]
    x += [H1("2. Les données"),
          P(f"Le registre des sources recense {len(C['reg'])} fichiers. Chacun porte son empreinte sha256 et une décision motivée pour le Défi 2 : "
            f"{C['dec']['PRINCIPAL']} source principale, {C['dec']['RETENU']} retenues, {C['dec']['SECONDAIRE']} secondaires, "
            f"{C['dec']['DOCUMENTATION']} de documentation et {C['dec']['ECARTE']} écartées."),
          *tableau(["Source", "Producteur", "Contenu utilisé", "Niveau"], [
              [f"Base préscolaire et primaire, {C['y0']} à {C['y1']}", "DGESS / MENAPLN", "élèves par sexe, statut, milieu et niveau ; TBS, TBA et TAP publiés", "13 anciennes régions"],
              [f"Annuaire statistique du primaire {C['y1']}", "DGESS", "élèves par province, sexe, milieu et classe", "45 anciennes provinces"],
              ["Projections de population 2020-2035 (RGPH 2019)", "INSD", f"enfants de 6 à 11 ans par province et par sexe ({D['ptbs']['annee'] if D.get('ptbs') else 'n.d.'})", "45 provinces"],
              ["Limites administratives COD-AB", "IGB / OCHA (HDX)", "cartes et codes des anciennes et nouvelles entités", "communes, provinces, régions"]], [46, 30, 62, 32]),
          H2("Limites des données"), *puces(D["meta"]["limites"] + ["Les données sont agrégées et publiques ; aucune information individuelle n'est utilisée."])]
    x += [H1("3. La préparation"),
          P("Le tableau suivant reprend chaque correction apportée aux données, avec sa raison. Le journal de nettoyage garde la trace de chaque règle, "
            "et chaque anomalie est listée dans un fichier à part."),
          *tableau(["Correction", "Raison"], [
              ["Tableaux Excel de la DGESS remis en format long, avec l'adresse de la cellule d'origine", "filtrer, contrôler et retrouver chaque chiffre"],
              ["Sous-totaux et totaux conservés mais marqués", "ne jamais les additionner deux fois"],
              ["Année seule lue comme année de fin (2025 = 2024-2025), vérifiée contre l'annuaire", "éviter un décalage d'un an sur toute la série"],
              ["Contrôle filles + garçons = total, et totaux nationaux comparés aux annuaires", "repérer les erreurs de saisie"],
              ["Noms de provinces harmonisés (Kouritenga, Komondjari, Balé, Boulkiemdé, Loroum)", "relier annuaire, population et carte"],
              [f"{len(C['sig'])} IPS de province laissés vides et signalés (effectif tombé sous 10 % du maximum)", "un IPS calculé sur quelques élèves ne se lit pas"],
              [f"Liaison exacte des 45 anciennes provinces aux {len(D['r17']['names'])} régions actuelles, commune par commune, par les codes COD-AB", "chiffrer le découpage actuel sans estimation"],
              ["Population de 6 à 11 ans extraite des tableaux PDF de l'INSD, comparée à celle qu'utilise la DGESS", "calculer un TBS fiable par province"],
              ["Sources hors sujet écartées : écoles géolocalisées, enseignants, post-primaire", "rester sur le Défi 2"],
              ["Valeurs manquantes jamais remplacées par zéro", "ne pas créer de données"]], [100, 70])]
    q = C["q"]
    x += [H1("4. La méthode"),
          *tableau(["Méthode", "Ce qu'elle fait", "Raison du choix"], [
              ["Indicateurs d'écart", "IPS, TBS par sexe, écart d'IPS entre ville et campagne, élèves de la dernière année ÷ meilleure année depuis 2015", "lisibles par un décideur et comparables d'un territoire à l'autre"],
              ["Règle de priorité", "priorité 1 : IPS < 0,95 et effectifs < 60 % du maximum ; priorité 2 : un seul des deux seuils", "transparente et réglable dans l'outil"],
              ["Corrélation de Spearman", f"{len(C['liens'])} questions testées sur les 45 provinces, avec leur p-valeur", "peu sensible aux valeurs extrêmes ; dit si deux écarts vont ensemble"],
              ["k-moyennes", f"{C['typo']['k'] if C['typo'] else 'n.d.'} profils de provinces selon l'accès, la parité et l'écart ville-campagne ; nombre de groupes fixé par le score de silhouette", "regrouper les provinces qui appellent la même réponse"],
              ["Prévision de l'IPS à trois ans", f"{len(C['mods'])} modèles comparés en se plaçant en 2019, 2020 et 2021 ; le plus fiable est retenu ({C['ret']})", "une projection testée sur le passé, avec sa marge d'erreur"]], [34, 76, 60]),
          P(f"Le modèle retenu se trompe en moyenne de {f3(q[1]['mae'])} à un an et de {f3(q[3]['mae'])} à trois ans. Huit fois sur dix, la valeur "
            f"réelle reste à moins de {f3(q[1]['q80'])} de la projection à un an, et à moins de {f3(q[3]['q80'])} à trois ans. Une projection "
            "prolonge la situation actuelle : elle ne mesure pas l'effet d'une politique.")]
    res = [f"L'écart le plus fort est territorial. En {C['y1']}, le TBS du primaire va de {pc(z[lo]['t'][n1])} au {lo} à {pc(z[hi]['t'][n1])} au {hi}. "
           f"Au niveau national, il passe de {pc(z['National']['t'][0])} en {C['y0']} à {pc(z['National']['t'][n1])}.",
           f"Il manque {nb(C['mc']['plus'])} élèves au primaire pour atteindre un TBS de 100 %, sur {nb(C['mc']['pop'])} enfants d'âge primaire."]
    if C["pt"]:
        res.append(f"Par province, le TBS va de {pc(C['pt'][0]['t'])} ({C['pt'][0]['p']}) à {pc(C['pt'][-1]['t'])} ({C['pt'][-1]['p']}).")
    b = C["ips_bas"]
    res += [f"{len(C['acc60'])} provinces sur 45 comptent moins de 60 % des élèves de leur meilleure année. Ensemble, elles ont perdu {nb(C['perdus'])} élèves.",
            f"L'IPS national du primaire passe de {f2(D['nat']['pri'][0])} à {f2(D['nat']['pri'][n1])}. Selon la province, il va de {f2(C['ips'][b[0]])} "
            f"({b[0]}) à {f2(C['ips'][b[-1]])} ({b[-1]}). La parité partout demanderait d'inscrire {nb(C['filles'])} filles de plus.",
            f"L'écart d'IPS entre ville et campagne passe de {f3(C['gap'][0])} à {f3(C['gap'][n1])}. La parité reste plus faible à la campagne dans {C['rural_bas']} provinces sur 45.",
            f"{len(C['p1'])} provinces sont en priorité 1 ({', '.join(C['p1'])}) et {len(C['p2'])} en priorité 2.",
            f"Si rien ne change, {len(C['sous'])} provinces resteraient sous un IPS de 0,95 en {C['an_prev']}, même dans le scénario haut."]
    x += [H1("5. Les résultats"), *puces(res)]
    if sig_l:
        x += [H2("Les écarts se cumulent"),
              P(f"Sur {len(C['liens'])} liens testés, {len(sig_l)} sont significatifs au seuil de 5 % :"),
              *tableau(["Question", "Corrélation"], [[l["q"], f2(l["rho"])] for l in sig_l], [140, 30])]
    if groupes:
        x += [H2("Profils de provinces"), *tableau(["Profil", "Provinces"], [[f"{g}. {n}", c] for (g, n), c in sorted(groupes.items())], [140, 30])]
    x += [H2("Visualisations livrées"), *puces([
        "La plateforme : une interface React servie par une API NestJS, ou une page autonome qui s'ouvre sans serveur (tableau-de-bord.html, dans le zip de l'étape 4). "
        "Elle compte sept onglets : Accueil, Analyse, Tableau de bord, Carte, Aide à la décision, Prévision, Méthodes et données.",
        "La fiche de synthèse : une page nationale et 17 fiches régionales, en PDF.",
        "Le dossier technique, de 15 pages au plus, avec cartes, courbes et tableaux."])]
    x += [H1("6. La réponse au défi"), H2("Ce que la solution apporte à un décideur"), *puces([
        "Au ministère et à la DGESS, elle désigne les provinces où rouvrir des classes et soutenir la scolarisation des filles. La règle est transparente, "
        "et ses deux seuils se règlent dans l'onglet Aide à la décision.",
        "Une direction régionale peut imprimer la fiche d'une province : effectifs perdus, parité en ville et à la campagne, projection, filles à inscrire.",
        "Les partenaires et les ONG repèrent les zones où les écarts se cumulent, suivent leur évolution chaque année et exportent les tables en CSV."]),
          H2("Limites"),
          P("Un écart ne dit pas sa cause. La chute des effectifs signale une perte d'accès, le plus souvent des fermetures d'écoles, sans le démontrer. "
            "Le niveau province ne couvre que la dernière année, et il n'existe pas de niveau commune."),
          H2("Suite possible"),
          P("Le croisement avec les fermetures d'écoles et les déplacements de population permettrait de tester l'hypothèse sécuritaire. Viendraient ensuite "
            "le niveau communal, le post-primaire, et une mise à jour annuelle avec le nouvel annuaire : le pipeline se relance tel quel.")]
    x += [H1("7. La reproduction"),
          P("Il faut Windows avec PowerShell et Python 3.12 ou plus. Node.js 20 ou plus n'est nécessaire que pour la plateforme."),
          *code(["pip install -r requirements.txt",
                 f"powershell -ExecutionPolicy Bypass -File scripts\\lancer_pipeline.ps1 -Equipe {eq.replace(' ', '_')} -AnneeNumerique fin",
                 "powershell -ExecutionPolicy Bypass -File plateforme\\lancer_plateforme.ps1   (puis http://localhost:3000)"]),
          *tableau(["Étape", "Dossier", "Contenu"], [
              ["01 Collecte", "01_collecte", "inventaire du Data Pack, registre des sources, empreintes sha256"],
              ["02 Nettoyage", "02_nettoyage", "format long, contrôle des totaux, journal, anomalies, population INSD par province"],
              ["03 Transformation", "03_transformation", "parité, modèle commun région × année, liaison des 45 provinces aux 17 régions"],
              ["04 Analyse", "04_analyse", "indicateurs, liens, profils, priorités, prévision, tableau de bord"],
              ["05 Interprétation", "05_interpretation", "dossier technique, fiche de synthèse, LISEZ-MOI"],
              ["Dépôt", "A_DEPOSER", "20 fichiers nommés selon la convention, contrôlés et vérifiés par sha256"]], [32, 36, 102]),
          P("Une étape se relance seule avec l'option -Etapes, par exemple -Etapes analyse,dashboard. Les données brutes restent sur la machine de l'équipe ; "
            "les étapes qui les lisent sont lancées en local et la console n'affiche que des compteurs.")]
    x += [H1("Ce que le jury regarde"),
          P("Pour chaque critère d'évaluation, le tableau indique ce que la solution apporte et l'endroit où le vérifier."),
          *tableau(["Critère", "Ce que nous apportons", "Où le vérifier"], [
              ["Caractère innovant", "premiers chiffres du primaire sur les 17 régions actuelles ; TBS par province avec la population INSD ; écarts traduits en nombre "
               "d'enfants ; simulateur de ciblage ; profils de provinces ; prévision testée sur le passé", "onglets Carte, Aide à la décision et Prévision ; dossier, partie 11"],
              ["Pertinence et rigueur de l'analyse", f"{len(C['liens'])} liens testés avec leur p-valeur ; {len(C['mods'])} modèles de prévision comparés ; contrôle des totaux ; "
               f"{len(C['sig'])} IPS non interprétables écartés et signalés ; aucune causalité affirmée", "04_analyse ; dossier, parties 6 et 9"],
              ["Visualisation et expérience utilisateur", "sept onglets, cartes avec zoom, courbes lissées, recherche de province, lien partageable, thème sombre, "
               "téléphone et tablette, navigation au clavier", "tableau-de-bord.html (zip de l'étape 4) ou http://localhost:3000"],
              ["Impact possible", f"{len(C['p1'])} provinces prioritaires nommées ; {nb(C['perdus'])} élèves perdus et {nb(C['filles'])} filles à inscrire chiffrés ; "
               "fiches par province et par région prêtes à imprimer", "onglets Accueil et Aide à la décision ; fiche de synthèse"],
              ["Faisabilité technique et opérationnelle", "outils libres (Python, React, NestJS) ; page autonome sans serveur ni Internet ; exports CSV ; mise à jour "
               "annuelle en une commande", "partie 7 ; plateforme/README.md"],
              ["Reproductibilité et documentation", "pipeline en une commande ; fichiers nommés et vérifiés par sha256 ; un LISEZ-MOI par étape ; dossier de 15 pages ; "
               "documents régénérés à chaque relance", "dossier scripts ; A_DEPOSER/GUIDE_DE_DEPOT.txt"]], [38, 82, 50])]
    return x


def etape01(C):
    d = C["dec"]
    return [H1("Contenu du paquet"),
            P("Ce paquet est un extrait léger du dossier de travail de la collecte, qui pèse environ 1 Go. Il contient :"),
            *puces(["le registre des sources, avec pour chaque fichier son producteur, sa publication, sa période, son lien, la décision prise pour le Défi 2, "
                    "le motif de cette décision et son empreinte sha256 ;",
                    "le fichier de couverture des années ;", "la base principale de la DGESS, au format Excel ;",
                    "le zip des sources retenues qui ne sont pas des PDF : extractions CSV de travail et fonds de carte COD-AB."]),
            P("Les PDF retenus (annuaires de la DGESS, rapports de l'INSD) ne sont pas renvoyés. Ils viennent du Data Pack de l'organisateur et sont "
              "référencés dans le registre par leur producteur, leur lien et leur empreinte. Les CSV tirés de ces PDF sont des extractions automatiques, "
              "à contrôler contre le document d'origine. Le manifeste du zip donne l'empreinte de chaque fichier."),
            H1("Décisions du registre"),
            *tableau(["Décision", "Fichiers", "Signification"], [
                ["Principal", d["PRINCIPAL"], "la base DGESS du préscolaire et du primaire"], ["Retenu", d["RETENU"], "source utilisée pour le Défi 2"],
                ["Secondaire", d["SECONDAIRE"], "utile si le temps le permet, ou autre format d'une source retenue"],
                ["Documentation", d["DOCUMENTATION"], "définitions, concepts, notices"], ["Écarté", d["ECARTE"], "hors sujet, doublon exact ou hors périmètre"]], [32, 22, 116]),
            H1("Les sources"),
            H2("Sources retenues"),
            P("La base de la DGESS couvre le préscolaire et le primaire par région (les 13 anciennes régions), sexe, statut, niveau et année, avec les taux "
              "et les indices de parité ; le milieu urbain ou rural n'y figure qu'au niveau national. S'y ajoutent les annuaires et tableaux de bord de la "
              "DGESS pour les indicateurs d'accès et le contrôle des totaux, le RGPH 2019 et les projections 2020-2035 de l'INSD pour la population qui sert "
              "de dénominateur aux taux, les fonds de carte COD-AB et les séries de la Banque mondiale et de l'UNESCO."),
            H2("Sources secondaires"),
            P("EHCVM 2021, EDS 2021 et profils de pauvreté régionaux (pauvreté et milieu comme variables explicatives), annuaires statistiques de l'INSD, "
              "éducation non formelle et rapports sur l'enseignement supérieur."),
            H2("Sources écartées"),
            P("Les données PDI du CONASUR (2020-2025) ne contiennent aucune donnée scolaire et sont classées à une étoile pour le Défi 2 dans le catalogue du "
              "Data Pack. Le post-primaire et le supérieur sont hors périmètre ; les ONG et l'emploi sont hors sujet ; les écoles géolocalisées d'OSM relèvent "
              "des infrastructures, donc du Défi 3. Les doublons exacts sont écartés."),
            H1("Pièges connus"),
            *puces(["Les 13 anciennes régions ne se confondent pas avec les 17 nouvelles. La correspondance officielle passe par les codes du classeur COD-AB "
                    "(adm*_pcode_old), selon la méthode du guide du Data Pack ; trois anciennes régions ont été découpées (Boucle du Mouhoun, Est, Sahel).",
                    "Les noms de provinces s'écrivent de plusieurs façons selon les sources.",
                    "L'année scolaire n'est pas l'année civile.", "Les totaux doivent être vérifiés contre les annuaires.",
                    "Plusieurs cellules du classeur de la DGESS contiennent un texte adressé aux assistants automatiques ; il est retiré avant l'analyse et chaque "
                    "adresse est signalée dans les anomalies du nettoyage.",
                    "La base de la DGESS est régionale : elle ne donne pas de chiffres par province."]),
            H1("Limites de la collecte"),
            P("Aucune table de population par province n'était prête à l'emploi : elle a été extraite des PDF du RGPH 2019 et des projections 2020-2035. Le "
              "portail Open Data de l'INSD était inaccessible (erreur 403) et les microdonnées sont sous licence nominative ; elles n'ont pas été collectées. "
              "Les années manquantes figurent dans le fichier de couverture."),
            H1("Usage de l'IA"),
            *encadre("Les scripts ont été rédigés avec un assistant IA, à partir de données fictives, puis lancés par l'équipe en local. L'assistant a lu le "
                     "document du challenge, le guide et le catalogue du Data Pack, des noms de fichiers et de colonnes, des profils de structure (libellés, "
                     "nombres masqués), des consoles de compteurs, les référentiels géographiques (codes et noms des régions, provinces et communes) et une "
                     "ligne d'indicateurs agrégés pour expliquer un écart. Il n'a lu aucun tableau de valeurs des données brutes. L'organisateur (Africa Data "
                     "Entry) a confirmé cette pratique le 15/11/2026.")]


def etape02(C):
    return [H1("Entrée"),
            P("Le nettoyage part de la base de la DGESS déposée à l'étape 01, copiée telle quelle et jamais modifiée."),
            H1("Fichiers produits"),
            *tableau(["Fichier", "Contenu"], [
                ["tableaux-long", "une ligne par valeur (région × statut × milieu × niveau × sexe × année scolaire), avec son type (effectif, nombre, taux, indice "
                 "de parité), son niveau d'agrégation et l'adresse de la cellule Excel d'origine"],
                ["journal-nettoyage", "chaque règle appliquée, avec le nombre de lignes avant et après"],
                ["anomalies", "les cellules à vérifier : valeurs suspectes, filles + garçons différent du total, sommes différentes des totaux, libellés inconnus, valeurs non numériques"],
                ["correspondance-regions", "chaque région de la DGESS reliée au fond de carte, avec un statut OK, À VALIDER ou INCONNU"],
                ["population-insd-provinces", "population de 6 à 11 ans par province et par sexe, extraite des projections de l'INSD"]], [44, 126]),
            H1("Pièges traités"),
            *puces(["Les 13 anciennes régions ne sont jamais assimilées d'office aux 17 nouvelles.",
                    "Les sous-totaux et les totaux sont gardés mais marqués ; pour additionner, on filtre le niveau « détail ».",
                    "Les taux et les indices de parité ne s'additionnent pas.", "Une valeur manquante n'est jamais remplacée par zéro.",
                    "Le texte adressé aux assistants automatiques est retiré des cellules et signalé."]),
            H1("Contrôle des totaux"),
            P(f"Les totaux nationaux de la base ont été recherchés dans les annuaires 2024-2025 (préscolaire et primaire) et 2017-2018 (primaire). Au "
              "préscolaire, les dix années sont retrouvées. Au primaire, l'année 2017-2018 reste introuvable dans les annuaires ; c'est un point ouvert."),
            H1("Convention des années"),
            *encadre("Quand l'en-tête d'une colonne ne donne qu'une année, c'est une année de fin : 2025 désigne l'année scolaire 2024-2025. La convention a "
                     "été vérifiée en comparant la base à l'annuaire 2024-2025 (option --annee-numerique fin du nettoyage).", VERT),
            H1("Limites et format"),
            P("Le milieu urbain ou rural n'est disponible qu'au niveau national dans cette base. Les fichiers sont au format CSV, séparateur point-virgule, "
              "encodage UTF-8, décimales au point.")]


def etape03(C):
    D = C["D"]
    return [H1("Entrée"), P("La transformation part de la table longue produite par le nettoyage (étape 02)."),
            H1("Tables produites"),
            *tableau(["Table", "Contenu"], [
                ["parite-effectifs", "IPS (filles ÷ garçons) et part des filles calculés sur les effectifs, par région, statut, milieu et niveau"],
                ["parite-taux", "IPS recalculé à partir des taux (TBA, TBS, achèvement), comparé à l'IPS publié par la DGESS"],
                ["controle-ips", "lignes où l'IPS recalculé s'écarte de l'IPS publié de plus de 0,02"],
                ["ecarts-par-dimension", "écarts par milieu, statut et région par rapport au national du même tableau"],
                ["classement-regions", "rang des régions par année, le rang 1 étant la parité la plus défavorable aux filles"],
                ["tendances", "évolution de l'IPS : variation et pente par an"],
                ["modele-commun-region-annee", "une ligne par région et par année : élèves, taux de scolarisation et population d'âge scolaire, par sexe"],
                ["dictionnaire-variables", "description de chaque colonne"]], [48, 122]),
            H1("Convention de parité"),
            P("La parité est atteinte quand l'IPS se situe entre 0,97 et 1,03. Les ratios sont calculés sur des valeurs publiées et arrondies : un IPS ne se lit "
              "pas avec plus de deux décimales."),
            H1("Liaison des territoires"),
            P(f"Les 13 anciennes régions sont reliées aux {len(D['r17']['names'])} nouvelles par la méthode officielle, celle des codes du classeur COD-AB "
              "(adm*_pcode_old) décrite dans le guide du Data Pack. Aucune commune n'est à cheval sur deux régions, et trois anciennes régions ont été découpées "
              "(Boucle du Mouhoun, Est, Sahel). La reconstruction par les noms de communes, à partir des fichiers PDI, sert de contrôle : 349 communes sur 351 "
              "concordent avec l'officiel, les deux autres étant des homonymes."),
            P("La table des 45 provinces d'avant la réforme est validée contre le champ adm2_name_old."),
            H1("Limites et format"),
            *puces(["Le milieu urbain ou rural n'est disponible qu'au niveau national, et seulement de 2018 à 2025 pour le préscolaire.",
                    "Les chiffres régionaux portent sur les 13 anciennes régions ; le passage aux 17 nouvelles se fait par la liaison décrite plus haut.",
                    "La convention des années est confirmée : une année seule est une année de fin (2025 = 2024-2025).",
                    "Format : CSV, séparateur point-virgule, encodage UTF-8, décimales au point."])]


def etape04(C):
    D, z, rs, n1 = C["D"], C["z"], C["rs"], C["n1"]
    b, ri = C["ips_bas"], C["reg_ips"]
    return [H1("Principes"),
            P("L'analyse ne lit que les tables agrégées des étapes 2 et 3. Aucun chiffre n'est saisi à la main : les scripts calculent tout."),
            *tableau(["Script", "Rôle"], [
                ["analyse_template.py", "indicateurs par région et figures"], ["analyse_provinces.py", "indicateurs des 45 provinces"],
                ["analyse_regions17.py", "les 17 régions actuelles, par addition exacte des provinces"], ["analyse_population_provinces.py", "TBS par province avec la population INSD"],
                ["analyse_liens_groupes.py", "liens entre les écarts et profils de provinces"], ["analyse_acces.py", "accès et provinces prioritaires"],
                ["prevision_provinces.py", "prévision de l'IPS (rôle Scientist, paquet séparé)"], ["dashboard_template.py et integrer_plateforme.py", "tableau de bord et plateforme"]], [62, 108]),
            H1("Fichiers"),
            *tableau(["Fichier", "Contenu"], [
                ["indicateurs-cles", "IPS par ancienne région : primaire au début et à la fin de la période, préscolaire, CP1, rang"],
                ["ecart-urbain-rural", "IPS urbain et rural du primaire par année, au niveau national"],
                ["acces-regions", "TBS, TBA et TAP du primaire et TBS du préscolaire par région, sexe et année"],
                ["indicateurs-provinces", "par province : IPS (début, fin, urbain, rural), redoublement, effectifs en part du maximum, élèves perdus, filles à inscrire"],
                ["ips-provinces-historique", "IPS par province et par année ; les valeurs non interprétables sont laissées vides"],
                ["effectifs-provinces-historique", "effectif total par province et par année"],
                ["ips-provinces-signalements", f"les {len(C['sig'])} IPS laissés vides et leur raison"],
                ["ips-par-classe-et-milieu", "IPS et redoublement par classe, en ville et à la campagne, dans le public et le privé"],
                ["liens-indicateurs", "liens entre les écarts : corrélation de Spearman, p-valeur, lecture en clair"],
                ["typologie-provinces", "profils de provinces (k-moyennes) et profil de chaque province"],
                ["population-tbs-provinces", "TBS par province et par sexe avec la population INSD de 6 à 11 ans"],
                ["regions17-indicateurs", "les 17 régions actuelles : effectifs, IPS, ville et campagne, élèves perdus, filles à inscrire"],
                ["provinces-prioritaires", "règle de ciblage (IPS < 0,95 ; effectifs < 60 % du maximum) et motif"],
                ["tableau-de-bord.zip", "la plateforme en page autonome, une version légère de secours et les figures"]], [52, 118]),
            H1("Messages clés"),
            *puces([f"Accès : en {C['y1']}, le TBS du primaire va de {pc(z[rs[0]]['t'][n1])} ({rs[0]}) à {pc(z[rs[-1]]['t'][n1])} ({rs[-1]}) ; au niveau national, "
                    f"{pc(z['National']['t'][n1])}, contre {pc(z['National']['t'][0])} en {C['y0']}. L'écart entre régions dépasse de loin l'écart entre filles et garçons.",
                    f"Accès : {len(C['acc60'])} provinces sur 45 ont moins de 60 % de leur effectif maximum. Les plus touchées sont "
                    + ", ".join(f"{n} ({pc(C['I'][n]['effectif_dernier_sur_max'] * 100)})" for n in C['acc60'][:5]) + ".",
                    f"Parité : l'IPS national du primaire passe de {f2(D['nat']['pri'][0])} en {C['y0']} à {f2(D['nat']['pri'][n1])} en {C['y1']} ; il est de "
                    f"{f2(D['nat']['cp1'][n1])} à l'entrée au CP1.",
                    f"Parité : les régions les plus basses sont {ri[0][0]} ({f2(ri[0][1])}) et {ri[1][0]} ({f2(ri[1][1])}) ; les provinces les plus basses, "
                    f"{b[0]} ({f2(C['ips'][b[0]])}), {b[1]} ({f2(C['ips'][b[1]])}) et {b[2]} ({f2(C['ips'][b[2]])}).",
                    f"Ville et campagne : l'écart d'IPS passe de {f3(C['gap'][0])} à {f3(C['gap'][n1])} ; il reste en défaveur de la campagne dans {C['rural_bas']} provinces sur 45.",
                    f"Ciblage : {len(C['p1'])} provinces en priorité 1 ({', '.join(C['p1'])}) et {len(C['p2'])} en priorité 2."]),
            H1("Limites"),
            *puces(["Les données régionales portent sur les 13 anciennes régions ; leur correspondance avec les 17 régions actuelles est décrite à l'étape 3.",
                    "Les TBS, TBA et TAP sont publiés par la DGESS ; leur dénominateur est la population d'âge scolaire, et ils peuvent dépasser 100 % à cause des élèves hors âge.",
                    "La chute des effectifs d'une province signale une perte d'accès, le plus souvent des fermetures d'écoles, sans en prouver la cause.",
                    "Un IPS calculé sur très peu d'élèves ne se lit pas : il est laissé vide et listé dans les signalements.",
                    "Les années récentes peuvent être provisoires, et le total national du primaire 2017/18 reste introuvable dans les annuaires."])]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--racine", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--equipe", default="Burkina_Novation")
    a = ap.parse_args()
    R, EQ = a.racine, a.equipe
    eq = EQ.replace("_", " ")
    C = chiffres(R)
    meta = lambda sujet: {"auteur": f"Équipe {eq}", "sujet": sujet, "createur": "Pipeline Défi 2 (scripts/lisez_moi_pdf.py)",
                          "mots": "Burkina Faso, éducation, accès à l'école, parité, IPS, TBS, Défi 2"}
    sortie = os.path.join(R, "05_interpretation", "lisez-moi"); os.makedirs(sortie, exist_ok=True)
    docs = [
        (os.path.join(R, "LISEZ-MOI.pdf"), "Lisez-moi", "Disparités d'accès à l'école au Burkina Faso : le défi, les données, la méthode, les résultats et la reproduction",
         "Document général", general(C, eq), "LISEZ-MOI général du projet Défi 2"),
        (os.path.join(sortie, f"{EQ}_01-collecte_D2_engineer_lisez-moi_v1.pdf"), "Étape 01 : collecte", "Registre des sources, décisions pour le Défi 2, pièges et limites",
         "Étape 01 · rôle Engineer", etape01(C), "LISEZ-MOI de l'étape 01 (collecte)"),
        (os.path.join(sortie, f"{EQ}_02-nettoyage_D2_engineer_lisez-moi_v1.pdf"), "Étape 02 : nettoyage", "Mise en forme, contrôles et convention des années",
         "Étape 02 · rôle Engineer", etape02(C), "LISEZ-MOI de l'étape 02 (nettoyage)"),
        (os.path.join(sortie, f"{EQ}_03-transformation_D2_engineer_lisez-moi_v1.pdf"), "Étape 03 : transformation", "Indicateurs de parité, modèle commun et liaison des territoires",
         "Étape 03 · rôles Engineer et Architect", etape03(C), "LISEZ-MOI de l'étape 03 (transformation)"),
        (os.path.join(sortie, f"{EQ}_04-analyse_D2_analyst_lisez-moi_v1.pdf"), "Étape 04 : analyse", "Indicateurs, liens, profils, priorités et messages clés",
         "Étape 04 · rôles Analyst et Scientist", etape04(C), "LISEZ-MOI de l'étape 04 (analyse)")]
    for chemin, titre, sous, etiq, contenu, sujet in docs:
        n = construire(chemin, titre, sous, etiq, contenu, meta(sujet))
        print(f"{os.path.relpath(chemin, R)} : {n} pages")


if __name__ == "__main__":
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    main()
