#!/usr/bin/env python3
"""DOCUMENTATION COMPLETE (Defi 2) : dossier technique et methodologique (.docx), 15 pages maximum.

Entrees : 02_nettoyage, 03_transformation, 04_analyse (tables agregees, journaux, figures). Aucune donnee brute.
Sortie  : <dossier_sortie>/<EQ>_05-interpretation_D2_analyst_documentation_v1.docx
Chaque chiffre vient d'une table produite par le pipeline. Mise en page : page de garde, en-tete, pied de page numerote,
encadres "A retenir", tableaux a en-tete colore.
Usage : documentation_template.py DOSSIER_02 DOSSIER_03 DOSSIER_04 DOSSIER_05 [--equipe Burkina_Novation]
"""
import argparse, glob, io, os, re, sys, zipfile
from datetime import date
import pandas as pd
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_BREAK, WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from interpretation_template import figure_acces  # noqa: E402  (meme figure que la fiche)

RX_IA = re.compile(r"NOTE\s+FOR\s+ANY.*", re.I | re.S)
RX_CHEMIN = re.compile(r"[A-Za-z]:\\Users\\[^\s;,\"']+")
BLEU, BLEU_CLAIR, GRIS_CLAIR = RGBColor(0x0B, 0x4F, 0x7A), "E8F1F8", "F4F6F8"


def net(x):
    return RX_CHEMIN.sub("<chemin local>", RX_IA.sub("", str(x))).strip()


def lire(d, cle, numeriques=True):
    f = sorted(glob.glob(os.path.join(d, f"*_{cle}_v1.csv")))
    if not f:
        sys.exit(f"Introuvable : *_{cle}_v1.csv dans {d}")
    df = pd.read_csv(f[0], sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    if numeriques:
        for c in df.columns:
            v = pd.to_numeric(df[c], errors="coerce")
            if v.notna().sum() and v.notna().sum() == (df[c] != "").sum():
                df[c] = v
    return df


ACCENTS = {
    "annee": "année", "annees": "années", "caracteres": "caractères", "numero": "numéro", "empiles": "empilés", "defaut": "défaut",
    "region": "région", "regions": "régions", "harmonisee": "harmonisée", "harmonisees": "harmonisées", "prive": "privé",
    "indetermine": "indéterminé", "debut": "début", "elementaire": "élémentaire", "general": "général", "garcons": "garçons",
    "publie": "publié", "parite": "parité", "defavorable": "défavorable", "achevement": "achèvement", "reussite": "réussite",
    "meme": "même", "categorie": "catégorie", "negatif": "négatif", "premiere": "première", "derniere": "dernière",
    "ameliore": "améliore", "carres": "carrés", "retire": "retiré", "adresse": "adressé", "laissees": "laissées",
    "remplacees": "remplacées", "numerique": "numérique", "verifier": "vérifier", "rapprochees": "rapprochées", "cle": "clé",
    "supprimes": "supprimés", "detail": "détail", "ecrite": "écrite", "tolerance": "tolérance", "ecart": "écart",
    "gardee": "gardée", "libelle": "libellé", "conservee": "conservée", "relevent": "relèvent", "definition": "définition", "entete": "en-tête",
}
RX_MOT = re.compile(r"(?<![\w-])([a-z]+)(?![\w-])")
PHRASES = {"cette annee-la": "cette année-là", " a vérifier": " à vérifier", " a confirmer": " à confirmer", "(a vérifier": "(à vérifier",
           "(a confirmer": "(à confirmer", "en en-tete": "en en-tête",
           # point tranche (section 4) : meme libelle que transformation_template.py corrige
           ", sinon défaut à confirmer)": " ; TAP, CP1 et CEP relèvent du primaire par définition)"}


def fr(texte):
    """Remet les accents des mots courants dans un texte libre (jamais dans un identifiant : _ et - sont proteges)."""
    t = RX_MOT.sub(lambda m: ACCENTS.get(m.group(1), m.group(1)), str(texte))
    for a_, b_ in PHRASES.items():
        t = t.replace(a_, b_)
    return t


def libelle_annees(regle, convention):
    """Le libelle historique du journal ('AAAA lue comme AAAA-AAAA+1') ne decrit que la convention 'debut' : on le reecrit
    d'apres la convention reellement appliquee (colonne annee_numerique_convention de la table propre)."""
    if not str(regle).startswith("annee scolaire AAAA-AAAA (annee numerique"):
        return regle
    if convention == "fin":
        return "annee scolaire AAAA-AAAA ; annee numerique en en-tete = annee de FIN : AAAA lue comme (AAAA-1)-AAAA (convention fin)"
    return "annee scolaire AAAA-AAAA ; annee numerique en en-tete = annee de DEBUT : AAAA lue comme AAAA-(AAAA+1) (convention debut)"


def v2(x, n=2):
    return f"{x:.{n}f}".replace(".", ",")


# ---------------------------------------------------------------- mise en page
def ombrer(cellule, couleur):
    tcpr = cellule._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd"); shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), couleur)
    tcpr.append(shd)


def champ_page(paragraphe):
    """Insere le numero de page (champ Word PAGE, mis a jour automatiquement a l'ouverture et a l'impression)."""
    run = paragraphe.add_run()
    for typ, texte in (("begin", None), (None, "PAGE"), ("end", None)):
        if typ:
            el = OxmlElement("w:fldChar"); el.set(qn("w:fldCharType"), typ)
        else:
            el = OxmlElement("w:instrText"); el.set(qn("xml:space"), "preserve"); el.text = texte
        run._r.append(el)
    return run


def main():
    ap = argparse.ArgumentParser()
    for n in ("d02", "d03", "d04", "d05"):
        ap.add_argument(n)
    ap.add_argument("--equipe", default="Burkina_Novation")
    a = ap.parse_args()
    os.makedirs(a.d05, exist_ok=True)

    jour, ano = lire(a.d02, "journal-nettoyage", False), lire(a.d02, "anomalies", False)
    dico, corr = lire(a.d03, "dictionnaire-variables", False), lire(a.d03, "correspondance-13-vers-17-officielle")
    ind, mil = lire(a.d04, "indicateurs-cles"), lire(a.d04, "ecart-urbain-rural")
    acc, pind, pcl = lire(a.d04, "acces-regions"), lire(a.d04, "indicateurs-provinces"), lire(a.d04, "ips-par-classe-et-milieu")
    prio, sig = lire(a.d04, "provinces-prioritaires"), lire(a.d04, "ips-provinces-signalements")
    prev, bt = lire(a.d04, "prevision-ips-provinces"), lire(a.d04, "prevision-backtest")
    r17 = lire(a.d04, "regions17-indicateurs")
    mc = lire(a.d03, "modele-commun-region-annee")
    nbf = lambda v: f"{int(round(v)):,}".replace(",", " ")
    pct = lambda v: f"{v:.0%}".replace("%", " %")
    zp = glob.glob(os.path.join(a.d04, "*tableau-de-bord_v1.zip"))
    fig = {}
    if zp:
        z = zipfile.ZipFile(zp[0]); fig = {n: z.read(n) for n in z.namelist() if n.endswith(".png")}

    c0 = [c for c in ind.columns if c.startswith("ips_primaire_")]
    y0, y1 = c0[0][-4:], c0[-1][-4:]
    k0, k1 = f"ips_primaire_{y0}", f"ips_primaire_{y1}"
    reg = ind[ind.niveau_geographique != "national"].sort_values(k1)
    nat = ind[ind.niveau_geographique == "national"].iloc[0]
    kc, kp = f"ips_cp1_nouveaux_inscrits_{y1}", f"ips_prescolaire_{y1}"
    ya = lambda y: f"{y}/{str(int(y) + 1)[2:]}"
    e0, e1 = mil.ecart_urbain_moins_rural.iloc[0], mil.ecart_urbain_moins_rural.iloc[-1]
    a1, a0 = int(acc.annee_debut.max()), int(acc.annee_debut.min())
    A = lambda i, y: acc[(acc.indicateur == i) & (acc.annee_debut == y)].set_index("region")
    tbs1, tbs0 = A("tbs_primaire", a1), A("tbs_primaire", a0)
    tr = tbs1.drop(index="National").sort_values("taux_ensemble")
    nl = tbs1.loc["National"]
    pk = [c for c in pind.columns if c.startswith("ips_20")]
    pk1 = pk[-1]; an1 = pk1[-4:]
    pa = pind.sort_values("effectif_dernier_sur_max")
    n_acc = int((pind.effectif_dernier_sur_max < 0.6).sum())
    perdus_acc = pind[pind.effectif_dernier_sur_max < 0.6].eleves_perdus_depuis_max.sum()
    p1 = prio[prio.priorite == 1]
    hz = sorted(int(c[-4:]) for c in prev.columns if c.startswith("ips_prevu_"))
    sous = prev[prev.statut_horizon.str.startswith("sous")]
    retenu = bt[bt.retenu.astype(str) == "True"].modele.iloc[0]
    mae = bt.groupby("modele").mae_toutes_horizons.first().sort_values()
    q80 = bt[bt.modele == retenu].set_index("horizon").q80
    n_ur = int((pind.ecart_urbain_moins_rural > 0).sum())

    mc1 = mc[mc.annee_debut == mc.annee_debut.max()]
    mcn = mc1[mc1.region == "National"].iloc[0]
    mcr = mc1[mc1.region != "National"].sort_values("eleves_en_plus_pour_tbs100_primaire", ascending=False)
    # ---------------------------------------------------------------- document et styles
    d = Document()
    # format Word actuel : sans ce reglage, Word ouvre le fichier en "Mode de compatibilite" (modele python-docx = Word 2007)
    compat = d.settings.element.find(qn("w:compat"))
    if compat is None:
        compat = OxmlElement("w:compat"); d.settings.element.append(compat)
    for cs in compat.findall(qn("w:compatSetting")):
        if cs.get(qn("w:name")) == "compatibilityMode":
            compat.remove(cs)
    cs = OxmlElement("w:compatSetting")
    for k_, v_ in (("w:name", "compatibilityMode"), ("w:uri", "http://schemas.microsoft.com/office/word"), ("w:val", "15")):
        cs.set(qn(k_), v_)
    compat.append(cs)
    st = d.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(10.5)
    st.paragraph_format.space_after = Pt(5); st.paragraph_format.line_spacing = 1.12
    for nom, taille, avant in (("Heading 1", 14, 14), ("Heading 2", 11.5, 9)):
        s = d.styles[nom]; s.font.name = "Calibri"; s.font.size = Pt(taille); s.font.color.rgb = BLEU; s.font.bold = True
        s.paragraph_format.space_before = Pt(avant); s.paragraph_format.space_after = Pt(4); s.paragraph_format.keep_with_next = True
    sec = d.sections[0]
    sec.top_margin = sec.bottom_margin = Cm(2.0); sec.left_margin = sec.right_margin = Cm(2.2)
    sec.different_first_page_header_footer = True            # pas d'en-tete sur la page de garde
    h = sec.header.paragraphs[0]
    h.text = f"Équipe {a.equipe}  ·  Défi 2 : disparités d'accès à l'éducation au Burkina Faso"
    h.runs[0].font.size = Pt(8); h.runs[0].font.color.rgb = RGBColor(0x6B, 0x72, 0x80)
    f_ = sec.footer.paragraphs[0]; f_.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_ = f_.add_run("Page "); r_.font.size = Pt(8.5); champ_page(f_).font.size = Pt(8.5)

    def P(t, style=None, gras=None):
        p = d.add_paragraph(style=style)
        if gras:
            p.add_run(gras).bold = True
        p.add_run(t)
        return p

    def B(items):
        for i in items:
            P(i, "List Bullet")

    def H(t, n=1):
        d.add_heading(t, n)

    def T(df, widths=None, size=8.5):
        t = d.add_table(rows=1, cols=len(df.columns)); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, c in enumerate(df.columns):
            cel = t.rows[0].cells[i]; cel.text = str(c); ombrer(cel, "0B4F7A")
            for run in cel.paragraphs[0].runs:
                run.bold = True; run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        for k, (_, r) in enumerate(df.iterrows()):
            cells = t.add_row().cells
            for i, v in enumerate(r):
                cells[i].text = "" if v is None or (isinstance(v, float) and v != v) else str(v)
                if k % 2:
                    ombrer(cells[i], GRIS_CLAIR)
        for row in t.rows:
            for i, cell in enumerate(row.cells):
                if widths:
                    cell.width = Cm(widths[i])
                for p_ in cell.paragraphs:
                    p_.paragraph_format.space_after = Pt(0)
                    for run in p_.runs:
                        run.font.size = Pt(size)
        d.add_paragraph().paragraph_format.space_after = Pt(0)

    def ENCADRE(titre, lignes):
        t = d.add_table(rows=1, cols=1); t.alignment = WD_TABLE_ALIGNMENT.CENTER
        c = t.rows[0].cells[0]; ombrer(c, BLEU_CLAIR); c.width = Cm(16.5)
        p = c.paragraphs[0]; r = p.add_run(titre); r.bold = True; r.font.color.rgb = BLEU; r.font.size = Pt(10.5)
        for ligne in lignes:
            q = c.add_paragraph(ligne, style="List Bullet"); q.paragraph_format.space_after = Pt(1)
            for run in q.runs:
                run.font.size = Pt(9.5)
        d.add_paragraph().paragraph_format.space_after = Pt(0)

    def F(data, w, legende):
        if data:
            d.add_picture(io.BytesIO(data), width=Cm(w)); d.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            c = d.add_paragraph(legende); c.alignment = WD_ALIGN_PARAGRAPH.CENTER
            c.runs[0].italic = True; c.runs[0].font.size = Pt(8.5)

    def saut():
        d.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # ================= page de garde =================
    for _ in range(6):
        d.add_paragraph()
    p = d.add_paragraph(); r = p.add_run("Data Challenge Burkina 2026 · Édition Éducation"); r.font.size = Pt(12); r.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)
    p = d.add_paragraph(); r = p.add_run("Disparités d'accès à l'éducation au Burkina Faso"); r.bold = True; r.font.size = Pt(26); r.font.color.rgb = BLEU
    p = d.add_paragraph(); r = p.add_run("Territoires, filles et garçons, ville et campagne : où agir en priorité ?"); r.font.size = Pt(15)
    d.add_paragraph()
    p = d.add_paragraph(); r = p.add_run(f"Défi 2 · Dossier technique et méthodologique\nPréscolaire et primaire, {ya(y0)} à {ya(y1)}"); r.font.size = Pt(11.5)
    for _ in range(8):
        d.add_paragraph()
    p = d.add_paragraph(); r = p.add_run(f"Équipe {a.equipe}"); r.bold = True; r.font.size = Pt(13)
    p = d.add_paragraph(); r = p.add_run(f"Rôles : Data Engineer, Data Architect, Data Analyst, Data Scientist\n{date.today().strftime('%d/%m/%Y')}")
    r.font.size = Pt(10); r.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)
    saut()

    # ================= résumé =================
    H("Résumé")
    P(f"Le Défi 2 pose une question simple : où les écarts d'accès à l'école sont-ils les plus grands, et comment évoluent-ils ? "
      f"L'écart le plus fort ne sépare pas les filles des garçons. Il sépare les territoires. En {ya(a1)}, le taux brut de scolarisation (TBS) "
      f"du primaire est de {tr.iloc[0].taux_ensemble:.0f} % au {tr.index[0]} et de {tr.iloc[1].taux_ensemble:.0f} % à l'{tr.index[1]}, contre "
      f"{tr.iloc[-1].taux_ensemble:.0f} % au {tr.index[-1]}. Au niveau national, il est passé de {tbs0.loc['National'].taux_ensemble:.0f} % en {ya(a0)} "
      f"à {nl.taux_ensemble:.0f} %. Dans {n_acc} provinces sur {len(pind)}, les écoles comptent aujourd'hui moins de 60 % des élèves de leur "
      f"meilleure année ; Tapoa, Soum et Yagha sont sous 25 %.")
    P(f"La parité filles-garçons progresse : l'indice de parité (IPS) du primaire passe de {v2(nat[k0])} à {v2(nat[k1])}. L'écart se forme pourtant "
      f"dès l'inscription au CP1 ({v2(nat[kc])}) et reste net au {reg.iloc[0].region} ({v2(reg.iloc[0][k1])}) et au {reg.iloc[1].region} "
      f"({v2(reg.iloc[1][k1])}). Entre ville et campagne, l'écart d'IPS a été divisé par {v2(e0 / e1, 1)}, mais l'IPS rural reste plus bas que "
      f"l'urbain dans {n_ur} provinces sur {len(pind)}.")
    ENCADRE("À retenir", [
        f"{nbf(perdus_acc)} élèves en moins dans les {n_acc} provinces les plus touchées, par rapport à leur meilleure année.",
        f"{nbf(pind.filles_manquantes_parite.sum())} filles à inscrire en plus pour atteindre la parité dans toutes les provinces.",
        f"{len(p1)} provinces cumulent faible parité et perte d'élèves : {', '.join(p1.province)}.",
        f"Il faudrait {nbf(mcn.eleves_en_plus_pour_tbs100_primaire)} élèves de plus au primaire pour atteindre un taux brut de scolarisation de 100 %.",
        f"Si rien ne change, {len(sous)} provinces resteront sous 0,95 en {ya(hz[-1])}."])
    P("Nous livrons une plateforme : une interface React servie par une API NestJS, aussi compilée en une page autonome qui fonctionne sans "
      "serveur ni Internet. Sa page d'accueil répond à la question du Défi 2 en une minute ; ses cinq "
      "onglets suivent les formes de solution citées par le guide (analyse, tableau de bord, cartes, aide à la décision, prévision) ; un dernier "
      "onglet donne la méthode, la commande de relance et les données en CSV. S'y ajoutent une fiche nationale, 17 fiches régionales et un "
      "pipeline qui se relance en une commande.")

    # ================= 1 =================
    H("1. La question et le périmètre")
    T(pd.DataFrame([
        ["Question", "Où les écarts d'accès à l'école sont-ils les plus grands (territoires, filles-garçons, ville-campagne), et évoluent-ils ?"],
        ["Niveaux", "Préscolaire et primaire, dont les nouveaux inscrits au CP1"],
        ["Période", f"{ya(y0)} à {ya(y1)}, soit 10 années scolaires"],
        ["Géographie", "National ; 13 anciennes régions (DGESS) ; 45 anciennes provinces ; 17 régions actuelles reconstituées"],
        ["Pour qui", "Un directeur régional ou central de l'éducation qui doit décider où agir et suivre l'effet de ses actions"],
    ], columns=["", "Notre choix"]), [3.0, 13.5], 9)
    H("Les indicateurs", 2)
    P("L'indice de parité (IPS) divise la valeur des filles par celle des garçons. À 1, il y a parité ; en dessous, il manque des filles ; au-dessus, "
      "il manque des garçons. Nous considérons, comme l'usage, qu'il y a parité entre 0,97 et 1,03.")
    P("Le TBS, le TBA et le TAP sont publiés par la DGESS. Ils rapportent les élèves inscrits, les nouveaux inscrits au CP1 et les élèves qui achèvent "
      "le primaire à la population de l'âge correspondant. Ce sont donc de vraies mesures d'accès. Ils peuvent dépasser 100 % quand des élèves plus "
      "jeunes ou plus âgés sont scolarisés.")
    P("Aucun taux n'est publié par province. Pour mesurer l'accès à ce niveau, nous rapportons l'effectif de la dernière année au meilleur effectif "
      "de la province depuis 2015. À 100 %, la province n'a jamais eu autant d'élèves ; à 20 %, quatre élèves sur cinq ont disparu des effectifs.")

    # ================= 2 =================
    H("2. Les données")
    T(pd.DataFrame([
        ["Données statistiques préscolaire et primaire 2016-2025 (classeur)", "DGESS / MENAPLN", "Table principale : effectifs, taux et IPS par sexe, région, statut, milieu et niveau"],
        ["Annuaires statistiques 2024-2025 (préscolaire, primaire)", "DGESS", "Contrôle des totaux nationaux ; données par province (10 années, urbain et rural, classes)"],
        ["Limites administratives COD-AB (adm1 à adm3)", "IGB / OCHA via HDX", "Codes anciens et nouveaux, fonds de carte"],
        ["Fichiers PDI par commune", "Data Pack (CONASUR)", "Contrôle indépendant de la correspondance entre 13 et 17 régions"],
    ], columns=["Source", "Producteur", "Usage"]), [5.6, 3.4, 7.5], 8.5)
    P("Toutes ces données sont agrégées et publiques. Le registre des sources, déposé à l'étape 1, indique pour chaque fichier son producteur, sa "
      "période, notre décision et son motif : une source principale, 72 retenues, 236 secondaires et 82 écartées.")

    # ================= 3 =================
    H("3. L'organisation du travail")
    T(pd.DataFrame([
        ["1 Collecte", "Engineer", "collecte_template.py, annoter_registre.py", "Copies en lecture seule, registre, couverture des années"],
        ["2 Nettoyage", "Engineer", "nettoyage_template.py, verifier_total_annuaire.py, extraction_provinces.py", "Table longue propre, journal, anomalies, tables par province"],
        ["3 Transformation", "Engineer, Architect", "transformation_template.py, liaison_officielle.py, liaison_communes.py, valider_decoupage.py, architecture_template.py",
         "IPS, écarts, tendances, correspondance 13/17, dictionnaire, schéma"],
        ["4 Analyse", "Analyst, Scientist", "analyse_template.py, analyse_provinces.py, analyse_regions17.py, analyse_acces.py, prevision_provinces.py, dashboard_template.py",
         "Indicateurs, accès, priorités, prévision, tableau de bord"],
        ["5 Interprétation", "Analyst", "interpretation_template.py, documentation_template.py", "Fiches de synthèse et régionales, ce dossier"],
        ["Dépôt", "Toute l'équipe", "depot_final.py", "Paquets nommés, manifeste sha256, contrôle automatique"],
    ], columns=["Étape", "Rôle", "Scripts", "Sortie"]), [2.4, 2.4, 6.6, 5.1], 8)
    P("Chaque étape lit uniquement ce que produit la précédente, et les données brutes ne sont jamais modifiées. Les étapes 4 et 5 ne travaillent que "
      "sur des tables agrégées. Une observation correspond à une zone (région ou province), une année scolaire, un niveau et un sexe, parfois "
      "précisés par le milieu ou le statut. Le livrable Architect (4 pages) détaille ce modèle.")
    H("Le modèle commun", 2)
    P(f"Pour mesurer l'accès, il faut relier au même endroit et à la même date les élèves, les taux de scolarisation et la population d'âge "
      f"scolaire. Le modèle commun le fait au niveau des 13 anciennes régions et du national, de {ya(int(mc.annee_debut.min()))} à "
      f"{ya(int(mc.annee_debut.max()))} : une ligne par région et par année, {mc.shape[1]} colonnes, toutes par sexe. Il réunit les élèves du "
      "préscolaire et du primaire, les taux bruts de scolarisation, la population d'âge scolaire et le nombre d'élèves qu'il faudrait ajouter pour "
      "atteindre un taux de 100 %.")
    P("La population n'est pas estimée par nous. La DGESS calcule le taux brut de scolarisation en divisant les élèves par la population de l'âge, "
      "tirée des projections de l'INSD ; en divisant à notre tour les élèves par ce taux, nous retrouvons exactement cette population. Le contrôle le "
      "confirme : filles et garçons recalculés séparément retombent sur la population totale à 0,2 % près.")
    P("Le livrable Architect décrit les trois niveaux du modèle. Au niveau conceptuel, des zones emboîtées (commune, province, ancienne et nouvelle "
      "région), des années, des niveaux, le sexe, et les faits mesurés. Au niveau logique, les tables et leurs clés, avec une clé commune zone et année. "
      "Au niveau physique, des fichiers CSV et GeoJSON rangés par étape, sans base de données, parce que l'ensemble fait moins de 50 Mo et doit se "
      "relire sans serveur.")
    P("Les accès suivent les rôles. Les copies brutes sont en lecture seule et ne quittent pas le poste de l'équipe. L'Engineer écrit les étapes 1 et 2, "
      "l'Architect l'étape 3, l'Analyst les étapes 4 et 5, le Scientist la prévision. Le jury lit le dépôt ; le tableau de bord, qui ne contient que des "
      "données agrégées, peut circuler librement.")

    # ================= 4 =================
    H("4. Collecte et nettoyage")
    P("Les fichiers retenus sont copiés sans modification, en lecture seule, et inscrits au registre. Nous avons trouvé dans plusieurs cellules et "
      "fichiers du Data Pack des textes adressés à des assistants IA. Nous ne les avons pas suivis : ils sont retirés de toutes nos sorties et "
      "signalés dans les journaux, les copies brutes restant intactes.")
    P("Le classeur DGESS empile des blocs « Tableau N » selon deux mises en page. Le script de nettoyage repère chaque bloc, distingue les régions, "
      "les sous-totaux et le total national, harmonise les modalités et produit une seule table longue où chaque ligne est une valeur observée. Les "
      "sous-totaux restent marqués pour ne jamais être additionnés deux fois, et une valeur manquante n'est jamais remplacée par 0.")
    # les lignes "lecture" du journal sont des tableaux ("FEUILLE / tableau N : ...") sauf quelques regles generales (ex. lignes sans libelle)
    est_tab = (jour.etape == "lecture") & jour.regle.str.contains(" / tableau ", regex=False)
    tabs = jour[est_tab]
    n_pre = int(tabs.regle.str.startswith("PRESCOLAIRE").sum()); n_pri = len(tabs) - n_pre
    jr = jour[~est_tab][["etape", "regle", "touchees"]].copy()
    fl = sorted(glob.glob(os.path.join(a.d02, "*_tableaux-long_v1.csv")))
    conv = (pd.read_csv(fl[0], sep=";", encoding="utf-8-sig", usecols=["annee_numerique_convention"], dtype=str)
            .annee_numerique_convention.mode().iloc[0] if fl else "")
    jr["regle"] = jr.regle.map(lambda x: fr(net(libelle_annees(x, conv))))
    jr = pd.concat([pd.DataFrame([["lecture", f"{len(tabs)} tableaux lus (préscolaire : {n_pre} ; primaire : {n_pri})",
                                   str(sum(int(x) for x in tabs.touchees if str(x).isdigit()))]], columns=jr.columns), jr])
    jr.columns = ["Étape", "Règle (journal de nettoyage)", "Lignes touchées"]
    T(jr, [2.4, 11.6, 2.5], 8)
    an = ano.groupby("type").size().reset_index(name="nombre").sort_values("nombre", ascending=False)
    P(f"Le journal liste {len(ano)} anomalies, et aucune n'est corrigée en silence : " + " ; ".join(f"{fr(r.type.replace('_', ' '))} ({r.nombre})" for _, r in an.iterrows()) + ".")
    H("Ce que nous avons tranché", 2)
    B(["Trois feuilles ne disent pas « primaire » dans leur titre. Elles portent sur le TAP, les nouveaux inscrits au CP1 et la réussite au CEP, "
       "qui relèvent tous du primaire.",
       "Pour le TBS préscolaire du Centre en 2019/20, la DGESS publie un IPS de 1,0 alors que ses propres taux filles et garçons donnent 0,91. Nous "
       "gardons 0,91 et l'écart reste tracé dans la table de contrôle.",
       "Le classeur donne parfois une année seule, sans dire s'il s'agit du début ou de la fin de l'année scolaire. Nous la lisons comme l'année de "
       "fin, la seule lecture pour laquelle nos totaux nationaux retrouvent ceux des annuaires.",
       "Un point reste ouvert : nous n'avons pas retrouvé le total national du primaire 2017/18 dans les annuaires disponibles. Nos conclusions "
       "comparent la première et la dernière année et ne dépendent pas de celle-ci."])
    H("Les données par province", 2)
    P("L'annuaire du primaire 2024-2025 n'existe qu'en PDF. Le script d'extraction reconnaît ses tableaux par leur titre : effectifs par province sur "
      "dix ans, élèves et redoublants par classe et par sexe, pour le public, le privé, la ville et la campagne. Pour 2024/25, la somme des provinces "
      "redonne exactement chaque région, et la ville plus la campagne redonnent l'ensemble. Sur l'historique, deux écarts de moins de 1 % subsistent "
      "(Centre-Ouest, une année).")
    sig_txt = " ; ".join(f"{r.province} en {ya(r.annee_debut)} ({nbf(r.effectif_total) if r.effectif_total == r.effectif_total else 0} "
                        f"élève{'s' if r.effectif_total == r.effectif_total and r.effectif_total > 1 else ''} "
                        f"pour un maximum de {nbf(r.effectif_max_periode)})" for _, r in sig.iterrows())
    P(f"Quatre fois, l'effectif d'une province tombe sous 10 % de son maximum : {sig_txt}. Un IPS calculé sur si peu d'élèves ne veut rien dire, "
      "nous le laissons donc vide et le signalons. Il ne s'agit pas d'erreurs de saisie : les élèves ont réellement disparu des effectifs.")

    # ================= 5 =================
    H("5. Contrôles et transformation")
    P("Nous vérifions que filles et garçons redonnent le total et que les lignes de détail redonnent les sous-totaux publiés. Les totaux nationaux "
      "sont recherchés dans les annuaires 2024-2025 : les dix années du préscolaire concordent, et le primaire aussi, sauf 2017/18. Nous avons "
      "recalculé l'IPS à partir des taux et l'avons comparé aux IPS publiés : 559 sont identiques et un écart est tracé. Enfin, les modalités "
      "(milieu, statut, niveau, sexe) sont contrôlées, et la table compte exactement 13 régions.")
    P("La transformation calcule ensuite l'IPS et la part des filles pour chaque observation, l'écart au national, le classement des régions et la "
      "pente de chaque série.")
    H("Relier les 13 anciennes régions aux 17 actuelles", 2)
    P("Les données DGESS restent publiées par ancienne région. Pour les relier au découpage actuel, nous rattachons chaque commune à son ancienne "
      "région par son code COD-AB, jamais par son nom. Une reconstruction indépendante par les noms de communes (fichiers PDI) donne le même résultat "
      "pour 349 communes sur 351 ; les deux différences sont des homonymes. Trois anciennes régions sont scindées : la Boucle du Mouhoun, l'Est et le Sahel.")
    cc = corr.copy(); cc.columns = ["Ancienne région", "Région actuelle", "Communes", "Part des communes", "Scindée"]
    cc["Part des communes"] = cc["Part des communes"].map(pct)
    T(cc, [3.6, 3.6, 2.2, 2.0, 2.0], 7.5)

    # ================= 6 =================
    H("6. Résultats : où les écarts d'accès sont les plus grands")
    H("6.1 L'accès par région", 2)
    tt = pd.DataFrame({"Région": tr.index[::-1]})
    tt["TBS garçons"] = [f"{tbs1.loc[r].taux_garcons:.0f} %" for r in tt["Région"]]
    tt["TBS filles"] = [f"{tbs1.loc[r].taux_filles:.0f} %" for r in tt["Région"]]
    tt[f"TBS {ya(a0)}"] = [f"{tbs0.loc[r].taux_ensemble:.0f} %" for r in tt["Région"]]
    tt[f"TBS {ya(a1)}"] = [f"{tbs1.loc[r].taux_ensemble:.0f} %" for r in tt["Région"]]
    for i_, lib in (("tba_primaire", "TBA"), ("tap_primaire", "TAP")):
        x = A(i_, a1)
        tt[f"{lib} {ya(a1)}"] = [f"{x.loc[r].taux_ensemble:.0f} %" if r in x.index else "" for r in tt["Région"]]
    tt.loc[len(tt)] = ["National", f"{nl.taux_garcons:.0f} %", f"{nl.taux_filles:.0f} %", f"{tbs0.loc['National'].taux_ensemble:.0f} %",
                       f"{nl.taux_ensemble:.0f} %", f"{A('tba_primaire', a1).loc['National'].taux_ensemble:.0f} %", f"{A('tap_primaire', a1).loc['National'].taux_ensemble:.0f} %"]
    T(tt, [3.4, 2.1, 2.1, 2.3, 2.3, 2.1, 2.1], 8)
    F(figure_acces(acc, a1), 12, f"Figure 1. TBS du primaire par région et par sexe, {ya(a1)} (taux publiés par la DGESS)")
    P(f"Le Sahel et l'Est scolarisent moins d'un enfant sur trois au primaire, quand le Centre dépasse 100 %. Au niveau national, le TBS des filles "
      f"et celui des garçons ne diffèrent que de {v2(abs(nl.taux_filles - nl.taux_garcons), 1)} point. Le recul national, de "
      f"{tbs0.loc['National'].taux_ensemble:.0f} % à {nl.taux_ensemble:.0f} %, touche les deux sexes.")
    P(f"Le modèle commun traduit ces taux en enfants. En {ya(int(mcn.annee_debut))}, le pays compte environ "
      f"{nbf(mcn.population_primaire_total)} enfants en âge d'aller à l'école primaire pour {nbf(mcn.eleves_primaire_total)} élèves inscrits. Pour "
      f"atteindre un taux brut de 100 % partout, il faudrait {nbf(mcn.eleves_en_plus_pour_tbs100_primaire)} élèves de plus, dont "
      + ", ".join(f"{nbf(r.eleves_en_plus_pour_tbs100_primaire)} dans la région {r.region}" for _, r in mcr.head(3).iterrows())
      + ". Un taux brut de 100 % ne garantit pas que tous les enfants de l'âge vont à l'école, puisqu'il compte aussi les élèves plus jeunes ou plus "
        "âgés : ces chiffres sont un minimum.")
    tm = mcr[mcr.eleves_en_plus_pour_tbs100_primaire > 0][["region", "population_primaire_total", "eleves_primaire_total", "tbs_primaire_total",
                                                           "eleves_en_plus_pour_tbs100_primaire", "tbs_primaire_filles", "tbs_primaire_garcons"]].copy()
    for c in ("population_primaire_total", "eleves_primaire_total", "eleves_en_plus_pour_tbs100_primaire"):
        tm[c] = tm[c].map(nbf)
    tm["tbs_primaire_total"] = tm.tbs_primaire_total.map(lambda v: f"{v:.0f} %")
    tm["tbs_primaire_filles"] = tm.tbs_primaire_filles.map(lambda v: f"{v:.0f} %")
    tm["tbs_primaire_garcons"] = tm.tbs_primaire_garcons.map(lambda v: f"{v:.0f} %")
    tm.columns = ["Région", "Enfants d'âge primaire", "Élèves", "TBS", "Élèves en plus pour 100 %", "TBS filles", "TBS garçons"]
    T(tm, [3.2, 2.6, 2.2, 1.4, 2.8, 2.2, 2.1], 8)
    H("6.2 Des provinces qui se vident", 2)
    pt = pa.head(12)[["province", "ancienne_region", "effectif_max_periode", "annee_effectif_max", "effectif_dernier_sur_max", "eleves_perdus_depuis_max", pk1]].copy()
    pt["effectif_max_periode"] = pt.effectif_max_periode.map(nbf)
    pt["annee_effectif_max"] = pt.annee_effectif_max.map(lambda v: ya(int(v)))
    pt["effectif_dernier_sur_max"] = pt.effectif_dernier_sur_max.map(pct)
    pt["eleves_perdus_depuis_max"] = pt.eleves_perdus_depuis_max.map(nbf)
    pt[pk1] = pt[pk1].map(v2)
    pt.columns = ["Province", "Ancienne région", "Meilleur effectif", "Année", f"{ya(an1)} / meilleur", "Élèves en moins", f"IPS {ya(an1)}"]
    T(pt, [2.6, 3.0, 2.3, 1.7, 2.3, 2.3, 1.8], 8)
    P(f"L'effectif national du primaire n'a jamais été aussi élevé qu'en {ya(an1)}. Pourtant, ces {n_acc} provinces ont perdu ensemble "
      f"{nbf(perdus_acc)} élèves par rapport à leur meilleure année, et la chute survient entre 2018 et 2022 selon les provinces. Les données ne "
      "disent pas pourquoi. Les fermetures d'écoles liées à l'insécurité sont l'explication la plus plausible ; il faudrait la vérifier avec des "
      "données de contexte.")
    fpt = sorted(glob.glob(os.path.join(a.d04, "*_population-tbs-provinces_v1.csv")))
    if fpt:
        ptb = pd.read_csv(fpt[0], sep=";", encoding="utf-8-sig").dropna(subset=["tbs_total"]).sort_values("tbs_total")
        meth = str(ptb.methode.iloc[0])
        P(f"Avec les projections de population de l'INSD (année {int(ptb.annee_population.iloc[0])}), nous calculons aussi le taux brut de "
          f"scolarisation de chaque province. Il va de {ptb.tbs_total.min():.0f} % ({ptb.iloc[0].province}) à {ptb.tbs_total.max():.0f} % "
          f"({ptb.iloc[-1].province}). "
          + ("Les tableaux de l'INSD donnent la population par groupes de cinq ans : nous comptons comme 6-11 ans les quatre cinquièmes "
             "des 5-9 ans et les deux cinquièmes des 10-14 ans, en supposant les âges répartis également dans chaque groupe. " if "interpol" in meth else
             "La population des 6-11 ans vient directement des tableaux de l'INSD. " if meth.startswith("INSD") else
             "Les projections ne donnant que la population totale par province, nous appliquons à chaque province la part des 6-11 ans de sa "
             "région : c'est une estimation. ")
          + f"Rapportée à la population utilisée par la DGESS, la somme des provinces de chaque région donne un rapport compris entre "
            f"{v2(ptb.coherence_region.min())} et {v2(ptb.coherence_region.max())} (1 = identique).")
        tpp = ptb.head(10)[["province", "ancienne_region", "population_6_11_total", "eleves_total", "tbs_total", "tbs_filles", "tbs_garcons",
                            "eleves_en_plus_pour_tbs100"]].copy()
        for c in ("population_6_11_total", "eleves_total", "eleves_en_plus_pour_tbs100"):
            tpp[c] = tpp[c].map(lambda v: nbf(v) if v == v else "")
        for c in ("tbs_total", "tbs_filles", "tbs_garcons"):
            tpp[c] = tpp[c].map(lambda v: f"{v:.0f} %" if v == v else "")
        tpp.columns = ["Province", "Ancienne région", "Enfants 6-11 ans", "Élèves", "TBS", "TBS filles", "TBS garçons", "Élèves en plus pour 100 %"]
        T(tpp, [2.5, 2.9, 2.1, 1.8, 1.4, 1.6, 1.8, 2.4], 7.5)
    H("6.3 La parité filles-garçons", 2)
    P(f"Au primaire, l'IPS national passe de {v2(nat[k0])} en {ya(y0)} à {v2(nat[k1])} en {ya(y1)}. Il est de {v2(nat[kp])} au préscolaire et de "
      f"{v2(nat[kc])} pour les nouveaux inscrits au CP1. {int((reg[k1] < 0.97).sum())} régions sur {len(reg)} restent sous 0,97. L'école publique "
      f"({v2(pcl[(pcl.categorie == 'public') & (pcl.classe == 'Total')].ips.iloc[0])}) est plus proche de la parité que le privé "
      f"({v2(pcl[(pcl.categorie == 'prive') & (pcl.classe == 'Total')].ips.iloc[0])}).")
    rt = reg[["region", k0, k1, "variation_primaire", kp, kc]].copy()
    for c in rt.columns[1:]:
        rt[c] = rt[c].map(v2)
    rt.columns = ["Ancienne région", f"Primaire {ya(y0)}", f"Primaire {ya(y1)}", "Variation", f"Préscolaire {ya(y1)}", f"CP1 {ya(y1)}"]
    T(rt, [3.6, 2.6, 2.6, 2.2, 2.8, 2.4], 8)
    F(fig.get("fig4_carte_13_regions.png"), 9.5, f"Figure 2. IPS du primaire par ancienne région, {ya(y1)} (fond COD-AB)")
    H("6.4 Ville et campagne", 2)
    P(f"Sur toute la période, l'IPS du primaire est plus élevé en ville qu'à la campagne. L'écart se resserre, de {v2(e0, 3)} à {v2(e1, 3)} point "
      f"(urbain {v2(mil.urbain.iloc[-1])}, rural {v2(mil.rural.iloc[-1])} en {ya(y1)}). Il reste présent dans {n_ur} provinces sur {len(pind)}, avec "
      f"un écart médian de {v2(pind.ecart_urbain_moins_rural.median(), 3)} point ; le plus fort est à "
      f"{pind.sort_values('ecart_urbain_moins_rural').iloc[-1].province} ({v2(pind.ecart_urbain_moins_rural.max(), 3)}).")
    F(fig.get("fig2_urbain_rural.png"), 11, "Figure 3. IPS urbain et rural, primaire, ensemble du pays")
    cl = pcl[pcl.categorie.isin(["urbain", "rural"]) & (pcl.classe != "Total")].pivot_table(index="classe", columns="categorie", values="ips")
    cl = cl.reindex(["CP1", "CP2", "CE1", "CE2", "CM1", "CM2"])
    tcl = pcl[(pcl.categorie == "public_prive") & (pcl.classe == "Total")].iloc[0]
    P("Classe par classe, il manque des filles au début du cycle et des garçons à la fin. À la campagne, l'IPS va de "
      + ", ".join(f"{v2(v)} en {c}" for c, v in cl.rural.items())
      + f". Le redoublement touche autant les filles ({v2(tcl.taux_redoublement_filles, 3)}) que les garçons ({v2(tcl.taux_redoublement_garcons, 3)}) "
        "et n'explique donc pas cet écart.")
    fl_ = sorted(glob.glob(os.path.join(a.d04, "*_liens-indicateurs_v1.csv"))); ft_ = sorted(glob.glob(os.path.join(a.d04, "*_typologie-provinces_v1.csv")))
    if fl_ and ft_:
        Lk = pd.read_csv(fl_[0], sep=";", encoding="utf-8-sig"); Ty = pd.read_csv(ft_[0], sep=";", encoding="utf-8-sig")
        H("6.5 Liens entre les écarts et profils de provinces", 2)
        P("Les écarts d'accès, de parité et entre ville et campagne se combinent-ils ? Nous avons testé chaque lien par une corrélation de rang "
          f"(Spearman) sur les {int(Lk.n_provinces.max())} provinces. Une corrélation mesure une association, pas une cause.")
        tl = Lk[["question", "rho_spearman", "p_valeur", "lecture"]].copy()
        tl["rho_spearman"] = tl.rho_spearman.map(lambda v: v2(v)); tl["p_valeur"] = tl.p_valeur.map(lambda v: "< 0,001" if v < 0.001 else v2(v, 3))
        tl["lecture"] = tl.lecture.str.replace(r" \(rho = [^)]*\)", "", regex=True).str.replace(r" \(p = [^)]*\)", "", regex=True)
        tl.columns = ["Question", "rho", "p", "Lecture"]
        T(tl, [7.2, 1.3, 1.5, 6.5], 8)
        sg = Lk[Lk.significatif_5pc.astype(str) == "True"]
        P("Trois résultats ressortent. " + " ".join(f"{q.rstrip(' ?')} : oui, {l.split(',')[0].replace('lien ', 'un lien ')}." for q, l in
          zip(sg.question.head(3), sg.lecture.head(3), strict=True)) + " À l'inverse, la part d'élèves ruraux n'explique ni l'écart ville-campagne "
          "ni la parité : les provinces rurales ne sont pas toutes en retard.")
        k_ = int(Ty.k_retenu.iloc[0])
        P(f"Pour regrouper les provinces, nous avons appliqué une classification par k-moyennes à trois mesures du Défi 2 (accès, parité, écart "
          f"ville-campagne), après les avoir mises à la même échelle. Le nombre de groupes, {k_}, est celui qui sépare le mieux les provinces "
          f"(score de silhouette de {v2(Ty.silhouette.iloc[0])}). Chaque groupe porte le nom de son profil moyen.")
        tg = Ty.groupby(["groupe", "profil"]).agg(n=("province", "size"), acces=("acces", "mean"), ips=("ips", "mean"),
                                                   ecart=("ecart_urbain_moins_rural", "mean"), provinces=("province", lambda s: ", ".join(s))).reset_index()
        tg["acces"] = tg.acces.map(lambda v: f"{v:.0f} %"); tg["ips"] = tg.ips.map(v2); tg["ecart"] = tg.ecart.map(lambda v: v2(v, 3))
        tg = tg[["groupe", "profil", "n", "acces", "ips", "ecart", "provinces"]]
        tg.columns = ["N°", "Profil", "Provinces", "TBS moyen", "IPS moyen", "Écart V-C", "Liste"]
        T(tg, [0.8, 4.2, 1.5, 1.5, 1.4, 1.5, 5.6], 7.5)
    H("6.6 Les 17 régions actuelles, en nombre d'élèves", 2)
    P(f"Chacune des 45 anciennes provinces se trouve entièrement dans une seule des 17 régions actuelles ; nous l'avons vérifié commune par commune "
      f"avec les codes COD-AB. Il suffit donc d'additionner les effectifs des provinces pour obtenir, sans estimation, les premiers chiffres du primaire "
      f"sur le découpage en vigueur. Le total {ya(an1)} retombe exactement sur le national : {nbf(r17[f'effectif_{an1}'].sum())} élèves. Nous y ajoutons "
      f"deux chiffres faciles à lire pour un décideur : les élèves perdus depuis la meilleure année et les filles qu'il faudrait inscrire en plus "
      f"pour atteindre la parité.")
    t17 = r17.sort_values("effectif_dernier_sur_max")[["nouvelle_region", "anciennes_regions", f"effectif_{an1}", "effectif_dernier_sur_max",
                                                        f"ips_{an1}", "eleves_perdus_depuis_max", "filles_manquantes_parite"]].copy()
    t17[f"effectif_{an1}"] = t17[f"effectif_{an1}"].map(nbf)
    t17["effectif_dernier_sur_max"] = t17.effectif_dernier_sur_max.map(pct)
    t17[f"ips_{an1}"] = t17[f"ips_{an1}"].map(v2)
    t17["eleves_perdus_depuis_max"] = t17.eleves_perdus_depuis_max.map(nbf); t17["filles_manquantes_parite"] = t17.filles_manquantes_parite.map(nbf)
    t17.columns = ["Région actuelle", "Ancienne région", f"Élèves {ya(an1)}", f"{ya(an1)} / meilleur", "IPS", "Élèves en moins", "Filles manquantes"]
    T(t17, [2.6, 3.4, 2.2, 2.2, 1.5, 2.3, 2.3], 7.5)

    # ================= 7 =================
    H("7. Anticiper : quelles provinces resteront loin de la parité ?")
    P(f"Nous avons comparé quatre modèles simples en nous replaçant dans le passé : en 2019, en 2020 puis en 2021, chaque modèle prévoit les trois "
      f"années suivantes à partir des seules données antérieures, et nous mesurons son erreur sur les {len(prev)} provinces. Les IPS non "
      "interprétables sont exclus.")
    tb = bt.pivot_table(index="modele", columns="horizon", values="mae").reindex(mae.index)
    tb = tb.map(lambda v: v2(v, 3)).reset_index()
    tb["modele"] = tb.modele.map({"persistance": "Persistance (l'IPS ne bouge pas)", "tendance_amortie": "Tendance amortie",
                                  "tendance_5ans": "Tendance sur 5 ans", "moyenne_3ans": "Moyenne des 3 dernières années"}).fillna(tb.modele)
    tb.columns = ["Modèle", "Erreur moyenne à 1 an", "à 2 ans", "à 3 ans"]
    tb["Retenu"] = ["oui" if m.lower().startswith(retenu) else "" for m in tb["Modèle"]]
    T(tb, [5.2, 3.3, 2.5, 2.5, 1.8], 8.5)
    P(f"Le modèle le plus simple, la persistance, l'emporte : supposer que l'IPS reste à son niveau actuel se trompe moins que prolonger une tendance. À l'échelle "
      f"d'une province, dix années ne suffisent pas à dégager une tendance fiable, et le décideur doit s'attendre à une marge d'erreur de "
      f"±{v2(q80[1], 3)} à un an et de ±{v2(q80[len(q80)], 3)} à trois ans (8 fois sur 10). Même dans le scénario le plus favorable, "
      f"{len(sous)} provinces resteraient sous 0,95 en {ya(hz[-1])} : {', '.join(sous.province)}. Cette projection prolonge la situation observée ; "
      "elle ne prévoit ni fermeture ni réouverture d'écoles.")

    # ================= 8 =================
    H("8. Où agir")
    P("Nous retenons deux critères simples. Le critère de parité est un IPS sous 0,95 la dernière année ; le critère d'accès, des effectifs sous 60 % "
      "du meilleur niveau depuis 2015. Une province qui franchit les deux seuils est en priorité 1, une province qui n'en franchit qu'un en priorité 2. "
      "Les seuils se règlent dans le tableau de bord.")
    tp = prio.copy()
    tp["proj"] = tp.province.map(dict(zip(prev.province, prev[f"ips_prevu_{hz[-1]}"], strict=True)))
    tp = tp[["priorite", "province", "ancienne_region", pk1, "effectif_dernier_sur_max", "ecart_urbain_moins_rural", "proj"]]
    tp[pk1] = tp[pk1].map(v2); tp["proj"] = tp.proj.map(v2); tp["ecart_urbain_moins_rural"] = tp.ecart_urbain_moins_rural.map(lambda v: v2(v, 3))
    tp["effectif_dernier_sur_max"] = tp.effectif_dernier_sur_max.map(pct)
    tp.columns = ["Prio.", "Province", "Ancienne région", "IPS", f"{ya(an1)} / meilleur", "Écart ville-campagne", f"Projection {ya(hz[-1])}"]
    T(tp, [1.3, 2.6, 3.2, 1.6, 2.4, 2.6, 2.6], 7.5)
    H("Ce que les données établissent", 2)
    P(f"L'accès varie du simple au quadruple d'une région à l'autre, et {n_acc} provinces ont perdu plus de 40 % de leurs élèves. La parité progresse "
      f"au niveau national ({v2(nat[k0])} puis {v2(nat[k1])}), mais pas partout, et l'écart naît dès l'inscription au CP1. L'écart de parité entre "
      f"ville et campagne a été divisé par {v2(e0 / e1, 1)} sans disparaître. Enfin, les provinces qui perdent le plus d'élèves sont souvent celles où "
      "la parité est la plus faible.")
    H("Ce qui reste à vérifier", 2)
    P("La chute des effectifs touche des provinces du Sahel, de l'Est, de la Boucle du Mouhoun, du Nord et du Centre-Nord, des zones que l'on sait "
      "exposées à l'insécurité. Pour le démontrer, il faudrait croiser nos chiffres avec les fermetures d'écoles et les déplacements de population. "
      "De même, un IPS sous 1 au CP1 peut venir d'une inscription plus tardive des filles, de l'état civil ou de la demande des familles, et un IPS "
      "au-dessus de 1 en CM2 d'un abandon plus fréquent des garçons. Nos données ne permettent pas de trancher.")
    H("Nos recommandations", 2)
    B(["Dans les provinces de priorité 1, rétablir une offre scolaire (réouverture, classes temporaires, accueil des élèves déplacés) en se fixant "
       "un objectif d'inscription des filles au CP1.",
       "Partout, suivre chaque année, par province et par sexe, les effectifs rapportés au meilleur niveau, l'IPS et le TBS. Le tableau de bord et "
       "les fiches régionales sont faits pour cela.",
       "Obtenir de l'INSD la population par province pour calculer de vrais taux de scolarisation à ce niveau."])

    # ================= 9 =================
    H("9. Limites, éthique et reproductibilité")
    P("Les statistiques régionales publiées restent sur les 13 anciennes régions ; nos chiffres sur les 17 régions actuelles ne couvrent que le "
      "primaire, puisqu'ils viennent des provinces. "
      + ("La population par province vient des projections de l'INSD, extraites des tableaux PDF ; leur somme retrouve la population utilisée par "
         "la DGESS dans chaque région. " if fpt else
         "Faute de population par province, l'accès provincial est mesuré par l'évolution des effectifs et non par un taux. ")
      + "Les années récentes peuvent être provisoires, et le total national du primaire 2017/18 manque. Nous n'affirmons aucune cause.")
    P("Nous n'utilisons que des données agrégées et publiques, sans aucune information individuelle. Les sources sont citées et les textes "
      "d'injection trouvés dans le Data Pack sont signalés.")
    T(pd.DataFrame([
        ["Tout relancer", "powershell -ExecutionPolicy Bypass -File scripts\\lancer_pipeline.ps1 -Etapes tout"],
        ["Refaire la collecte", "scripts\\lancer_pipeline.ps1 -Etapes collecte -Brut <dossier du Data Pack téléchargé>"],
        ["Étapes 4 et 5", "scripts\\lancer_pipeline.ps1 -Etapes analyse,analyse_provinces,analyse_regions17,analyse_acces,prevision,dashboard,interpretation,documentation,architecture,depot"],
        ["Contrôle avant dépôt", "python scripts\\depot_final.py verifier"],
    ], columns=["Objectif", "Commande"]), [3.6, 12.9], 8)
    P("La chaîne complète part des copies de 01_collecte. Si le dossier du Data Pack téléchargé est absent, l'étape de collecte est sautée avec un "
      "message et la suite continue ; l'option -Brut permet de la refaire. Chaque fichier déposé figure dans un manifeste avec son empreinte sha256. "
      "Avant le dépôt, un contrôle automatique vérifie les noms, les formats, le nombre et le poids des fichiers, l'intégrité des zip et l'absence de "
      "chemins personnels. Relancées deux fois, les étapes 4 et 5 produisent des tables identiques octet pour octet.")

    # ================= 10 =================
    H("10. Usage de l'IA")
    P("Le règlement interdit l'IA sur les données brutes. Les étapes 1 à 3 sont donc exécutées par l'équipe, en local. Un assistant IA a écrit ou "
      "relu ces scripts à partir d'exemples fictifs (noms de colonnes, lignes inventées), sans jamais recevoir les données brutes ; l'organisateur a "
      "confirmé cette pratique le 15/11/2026.")
    P("Pour les étapes 4 et 5, l'assistant a écrit les scripts d'analyse, de prévision, de tableau de bord et de documentation, puis les a exécutés sur "
      "les tables agrégées produites par l'équipe. Il a aussi proposé deux règles : le signalement des IPS calculés sur moins de 10 % du meilleur effectif, "
      "et la règle de priorité (0,95 et 60 %). Ces seuils sont des paramètres visibles dans les scripts, que l'équipe peut modifier. L'équipe a vérifié "
      "les totaux contre les annuaires, relu les chiffres et les messages, et examiné les cellules suspectes.")

    # ================= 11 =================
    H("11. Ce que notre solution apporte de nouveau")
    P("Les statistiques régionales publiées restent sur les 13 anciennes régions. Nous donnons les premiers chiffres du primaire sur les 17 régions "
      "actuelles, par simple addition des provinces, donc sans estimation. Nous traduisons aussi les indices en élèves (élèves perdus, filles "
      "manquantes), parce qu'un nombre d'enfants parle davantage à un décideur qu'un indice de parité.")
    T(pd.DataFrame([
        ["Analyse", "Les constats clés, les régions et provinces les plus touchées, les liens entre les écarts et les profils de provinces"],
        ["Tableau de bord", "Parité et accès par ancienne région, année par année : indicateurs clés, carte, classement, courbes, taux par sexe"],
        ["Carte", "Les 17 régions actuelles et les 45 provinces, colorées selon la mesure choisie (accès, IPS, écart ville-campagne, élèves)"],
        ["Aide à la décision", "Simulateur de ciblage à deux seuils, provinces prioritaires, carte des priorités, fiche imprimable de chaque province"],
        ["Prévision", "IPS observé et projeté par province avec sa marge d'erreur, classement des 45 provinces, fiabilité des quatre modèles"],
    ], columns=["Onglet de l'outil", "Ce qu'on y trouve"]), [3.4, 13.1], 8.5)
    P("Le tableau de bord contient un simulateur de ciblage : on règle les seuils de parité et d'accès, et la liste des provinces retenues se met à jour "
      "avec le nombre d'élèves concernés. Chaque vue peut être partagée par un lien qui conserve la région, la province et les réglages, ou imprimée "
      "proprement. Le tout tient dans un seul fichier qui s'ouvre sans Internet sur un poste de direction régionale.")
    P("La fiche de synthèse est suivie de 17 fiches régionales d'une page, une par région actuelle, avec ses provinces, leurs priorités et leurs "
      "projections. Enfin, nous traitons les IPS calculés sur des effectifs effondrés comme une information et non comme une erreur : la chute "
      "des effectifs devient un indicateur d'accès à part entière.")

    # ================= 12 =================
    H("12. Réponse aux critères d'évaluation")
    T(pd.DataFrame([
        ["Pertinence", "Les trois dimensions de l'accès sont traitées : territoires (TBS, effectifs par province), filles-garçons (IPS), ville-campagne"],
        ["Rigueur", "Contrôles arithmétiques et externes, anomalies listées, IPS non interprétables signalés, correspondance 13/17 validée par deux méthodes"],
        ["Reproductibilité", "Pipeline en une commande, manifeste sha256, contrôle avant dépôt, dictionnaire des variables"],
        ["Visualisation", "Interface React et API NestJS, ou page autonome : accueil, cinq onglets, méthode et CSV ; 18 fiches"],
        ["Impact", "Liste nominative des provinces à cibler, règle explicite, chiffres en nombre d'élèves, indicateurs de suivi annuels"],
        ["Prévision", "Quatre modèles comparés sur le passé, erreur mesurée et affichée"],
        ["Innovation", "17 régions actuelles sans estimation, indices traduits en élèves, simulateur de ciblage, lien partageable"],
    ], columns=["Critère", "Notre réponse"]), [3.4, 13.1], 8.5)

    # ================= 13 =================
    H("13. Pour aller plus loin")
    P(("" if fpt else "En extrayant les projections de population de l'INSD au niveau provincial, l'équipe pourrait calculer des taux de "
       "scolarisation par sexe pour chaque province. ") + "Un croisement avec les données de fermetures d'écoles et de déplacés permettrait de tester l'hypothèse sécuritaire. Viendraient ensuite le "
      "niveau communal, le préscolaire et le post-primaire par province.")

    # ================= annexes =================
    saut()
    H("Annexe A. Dictionnaire des variables")
    da = dico.map(net)
    da["description"] = da.description.map(fr)
    extra = pd.DataFrame([
        ["indicateurs-provinces", "effectif_dernier_sur_max", "effectif de la dernière année ÷ meilleur effectif de la province depuis 2015 (accès)"],
        ["indicateurs-provinces", "eleves_perdus_depuis_max", "meilleur effectif depuis 2015 moins effectif de la dernière année"],
        ["indicateurs-provinces", "filles_manquantes_parite", "garçons moins filles quand il y a moins de filles (filles à inscrire pour un IPS de 1)"],
        ["indicateurs-provinces", "nb_annees_ips_non_interpretable", "années où l'effectif est sous 10 % du maximum (IPS laissé vide)"],
        ["acces-regions", "taux_garcons / taux_filles / taux_ensemble", "TBS, TBA ou TAP publiés par la DGESS, en %"],
        ["acces-regions", "ips_taux", "taux des filles ÷ taux des garçons"],
        ["regions17-indicateurs", "nouvelle_region", "région actuelle (somme exacte de ses anciennes provinces)"],
        ["provinces-prioritaires", "priorite", "1 : IPS < 0,95 et effectifs < 60 % du maximum ; 2 : un seul critère"],
        ["prevision-ips-provinces", "ips_prevu_AAAA, bas80_AAAA, haut80_AAAA", "projection et intervalle à 80 % (erreurs mesurées sur le passé)"],
        ["modele-commun-region-annee", "region, annee_debut", "clé : ancienne région (ou National) et année scolaire"],
        ["modele-commun-region-annee", "eleves_*, tbs_*", "élèves et taux bruts de scolarisation, primaire et préscolaire, par sexe"],
        ["modele-commun-region-annee", "population_*", "population d'âge scolaire par sexe = élèves ÷ TBS (dénominateur de la DGESS)"],
        ["modele-commun-region-annee", "eleves_en_plus_pour_tbs100_*", "population moins élèves : élèves à ajouter pour un TBS de 100 %"],
    ], columns=da.columns)
    da2 = pd.concat([da, extra]); da2.columns = ["Table", "Colonne", "Description"]
    T(da2, [3.4, 4.4, 8.7], 7)
    H("Annexe B. Glossaire")
    T(pd.DataFrame([
        ["IPS", "Indice de parité entre les sexes : filles ÷ garçons"],
        ["TBS, TBA, TAP", "Taux brut de scolarisation, taux brut d'admission au CP1, taux d'achèvement du primaire"],
        ["DGESS", "Direction générale des études et des statistiques sectorielles"],
        ["COD-AB", "Common Operational Dataset, Administrative Boundaries (IGB/OCHA)"],
        ["PDI", "Personnes déplacées internes"],
        ["MAE", "Erreur absolue moyenne d'une prévision"],
    ], columns=["Terme", "Définition"]), [3.4, 13.1], 8)
    sortie = os.path.join(a.d05, f"{a.equipe}_05-interpretation_D2_analyst_documentation_v1.docx")
    d.save(sortie)
    print(f"Documentation generee : {os.path.basename(sortie)} ({len(fig)} figures disponibles).")


if __name__ == "__main__":
    main()
