#!/usr/bin/env python3
"""PREVISION (role Data Scientist, Defi 2) - IPS du primaire par province a horizon 3 ans, avec mesure de fiabilite.

Question : quelles provinces resteront eloignees de la parite si rien ne change ?
Entree  : 04_analyse/*_ips-provinces-historique_v1.csv (IPS par province et par annee ; les IPS non interpretables sont vides).
Methode :
  4 modeles simples et explicables, compares par validation sur le passe (origine glissante) :
    persistance      IPS de demain = dernier IPS observe
    moyenne_3ans     moyenne des 3 derniers IPS observes
    tendance_5ans    droite des moindres carres sur les 5 dernieres annees, prolongee
    tendance_amortie dernier IPS + pente 5 ans x (phi + phi^2 + ... + phi^h), phi = 0.8
  Validation : origines 2019, 2020, 2021 ; on n'utilise que les annees <= origine pour prevoir origine+1..+3 ;
  erreur = |prevu - observe| sur toutes les provinces. Modele retenu = plus petite erreur absolue moyenne (MAE).
  Intervalle a 80 % : +/- quantile 80 % des erreurs absolues du modele retenu, par horizon.
Sorties (04_analyse) :
  <EQ>_04-analyse_D2_scientist_prevision-backtest_v1.csv          MAE et quantile 80 % par modele et horizon
  <EQ>_04-analyse_D2_scientist_prevision-ips-provinces_v1.csv     prevision par province, intervalle, statut
  <EQ>_04-analyse_D2_scientist_prevision-ips-provinces_v1.zip     paquet du role : code + tables + LISEZ-MOI
Usage : prevision_provinces.py DOSSIER_04 [--equipe Burkina_Novation] [--horizon 3]
"""
import argparse, glob, os, sys, zipfile
import numpy as np
import pandas as pd

PHI, MIN_OBS, SEUIL = 0.8, 4, 0.95


def pente(xs, ys):
    return float(np.polyfit(xs, ys, 1)[0]) if len(xs) >= 2 else 0.0


def prevoir(serie, h, modele):
    """serie : pd.Series annee -> IPS (sans valeurs manquantes), triee. Renvoie la prevision a l'horizon h."""
    y, x = serie.values, serie.index.values.astype(float)
    der = y[-1]
    if modele == "persistance":
        return der
    if modele == "moyenne_3ans":
        return float(np.mean(y[-3:]))
    s = pente(x[-5:], y[-5:])
    if modele == "tendance_5ans":
        return float(np.polyval(np.polyfit(x[-5:], y[-5:], 1), x[-1] + h))
    if modele == "tendance_amortie":
        return float(der + s * sum(PHI ** k for k in range(1, h + 1)))
    raise ValueError(modele)


MODELES = ["persistance", "moyenne_3ans", "tendance_5ans", "tendance_amortie"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dossier04"); ap.add_argument("--equipe", default="Burkina_Novation"); ap.add_argument("--horizon", type=int, default=3)
    a = ap.parse_args()
    f = sorted(glob.glob(os.path.join(a.dossier04, "*_ips-provinces-historique_v1.csv")))
    if not f:
        sys.exit("Historique des IPS par province introuvable : lancez d'abord analyse_provinces.py")
    h = pd.read_csv(f[0], sep=";", encoding="utf-8-sig")
    cols = [c for c in h.columns if c.startswith("ips_")]
    ans = [int(c[4:]) for c in cols]
    series = {r.province: pd.Series([r[c] for c in cols], index=ans).dropna() for _, r in h.iterrows()}
    region = dict(zip(h.province, h.ancienne_region, strict=True))
    H = a.horizon

    # ---------- validation sur le passe ----------
    err = []
    for orig in (2019, 2020, 2021):
        for p, s in series.items():
            tr = s[s.index <= orig]
            if len(tr) < MIN_OBS:
                continue
            for k in range(1, H + 1):
                cible = orig + k
                if cible not in s.index:
                    continue
                for m in MODELES:
                    err.append({"modele": m, "origine": orig, "horizon": k, "province": p, "erreur_abs": abs(prevoir(tr, k, m) - s[cible])})
    E = pd.DataFrame(err)
    bt = (E.groupby(["modele", "horizon"]).erreur_abs.agg(mae="mean", q80=lambda v: v.quantile(0.8), n="size").reset_index())
    glob_mae = E.groupby("modele").erreur_abs.mean().sort_values()
    retenu = glob_mae.index[0]
    bt["mae_toutes_horizons"] = bt.modele.map(glob_mae)
    bt["retenu"] = bt.modele == retenu
    pre = os.path.join(a.dossier04, f"{a.equipe}_04-analyse_D2_scientist_")
    bt.round(4).to_csv(pre + "prevision-backtest_v1.csv", sep=";", index=False, encoding="utf-8-sig")
    q80 = bt[bt.modele == retenu].set_index("horizon").q80

    # ---------- prevision ----------
    a1 = max(ans)
    lignes = []
    for p, s in series.items():
        row = {"province": p, "ancienne_region": region.get(p, ""), "modele": retenu, f"ips_observe_{a1}": round(float(s.iloc[-1]), 4) if len(s) else None}
        for k in range(1, H + 1):
            v = prevoir(s, k, retenu) if len(s) >= MIN_OBS else None
            row[f"ips_prevu_{a1 + k}"] = None if v is None else round(v, 3)
            row[f"bas80_{a1 + k}"] = None if v is None else round(v - q80[k], 3)
            row[f"haut80_{a1 + k}"] = None if v is None else round(v + q80[k], 3)
        hk = f"haut80_{a1 + H}"; bk = f"bas80_{a1 + H}"
        row["statut_horizon"] = ("sous 0,95 même dans le scénario haut" if row[hk] is not None and row[hk] < SEUIL else
                                 "incertain (l'intervalle contient 0,95)" if row[bk] is not None and row[bk] < SEUIL else
                                 "au-dessus de 0,95")
        lignes.append(row)
    P = pd.DataFrame(lignes).sort_values(f"ips_prevu_{a1 + H}")
    P.to_csv(pre + "prevision-ips-provinces_v1.csv", sep=";", index=False, encoding="utf-8-sig")
    sous = P[P.statut_horizon.str.startswith("sous")]

    lm = f"""PREVISION DE L'IPS DU PRIMAIRE PAR PROVINCE - role Data Scientist - equipe {a.equipe} - Defi 2

Question : quelles provinces resteront eloignees de la parite (IPS < {SEUIL}) d'ici {a1 + H}/{str(a1 + H + 1)[2:]} si rien ne change ?
Donnees : IPS du primaire par province, {min(ans)} a {a1} (annuaire DGESS 2024-2025) ; IPS non interpretables exclus.
Modeles compares (validation sur le passe, origines 2019-2021, horizons 1 a {H}) - erreur absolue moyenne (MAE) :
""" + "\n".join(f"  {m:17s} MAE = {v:.4f}" + ("   <- retenu" if m == retenu else "") for m, v in glob_mae.items()) + f"""

Fiabilite du modele retenu ({retenu}) : erreur absolue a 80 % = """ + ", ".join(f"h{k} : +/-{q80[k]:.3f}" for k in range(1, H + 1)) + f""".
Lecture : un IPS prevu de 0,90 a l'horizon {H} signifie qu'il se situera, 8 fois sur 10, entre {0.90 - q80[H]:.2f} et {0.90 + q80[H]:.2f}.

Resultat : {len(sous)} provinces resteraient sous {SEUIL} meme dans le scenario haut : {', '.join(sous.province)}.

Fichiers : prevision-backtest.csv (erreurs par modele et horizon) ; prevision-ips-provinces.csv (prevision, intervalle, statut) ;
prevision_provinces.py (code, relancable : python prevision_provinces.py 04_analyse --equipe {a.equipe}).
Limites : 10 points par province, ruptures liees a l'insecurite (fermetures d'ecoles) impossibles a anticiper par un modele de tendance ;
la prevision dit ce qui se passe si la dynamique observee continue, pas ce qui va se passer. Aucune variable explicative n'est utilisee.
"""
    with zipfile.ZipFile(pre + "prevision-ips-provinces_v1.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.write(pre + "prevision-backtest_v1.csv", os.path.basename(pre + "prevision-backtest_v1.csv"))
        z.write(pre + "prevision-ips-provinces_v1.csv", os.path.basename(pre + "prevision-ips-provinces_v1.csv"))
        z.write(os.path.abspath(__file__), "prevision_provinces.py")
        z.writestr("LISEZ-MOI.txt", lm)
    print(lm)


if __name__ == "__main__":
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    main()
