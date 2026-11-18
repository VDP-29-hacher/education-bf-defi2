#!/usr/bin/env python3
"""PLATEFORME REACT + NESTJS (etape 4, livrable de visualisation) : compile l'interface React en page autonome et l'integre au depot.

- Lit les donnees produites par dashboard_template.py (04_analyse/*_donnees-plateforme_v1.json), aucune donnee brute.
- Compile plateforme/web en mode "autonome" (Vite + vite-plugin-singlefile) : une seule page HTML, donnees embarquees, sans serveur.
- Remplace tableau-de-bord.html dans le zip de l'etape 4 par cette page ; l'ancienne page (JavaScript simple) devient
  tableau-de-bord-leger.html, version de secours pour les navigateurs anciens.
- Si Node.js est absent, ne fait rien : la page legere reste le tableau de bord (le pipeline Python suffit).
Usage : integrer_plateforme.py DOSSIER_04 [--equipe Burkina_Novation] [--sans-compilation]
"""
import argparse, glob, os, shutil, subprocess, sys, zipfile
from pathlib import Path


def npm(args, cwd):
    exe = shutil.which("npm.cmd") or shutil.which("npm")
    r = subprocess.run([exe, *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        print(r.stdout[-1500:], r.stderr[-1500:], sep="\n")
        sys.exit(f"Echec : npm {' '.join(args)} (dans {cwd})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dossier04"); ap.add_argument("--equipe", default="Burkina_Novation"); ap.add_argument("--sans-compilation", action="store_true")
    a = ap.parse_args()
    racine = Path(__file__).resolve().parent.parent
    web, api = racine / "plateforme" / "web", racine / "plateforme" / "api"
    zp = sorted(glob.glob(os.path.join(a.dossier04, "*tableau-de-bord_v1.zip")))
    if not zp:
        sys.exit("Zip du tableau de bord introuvable : lancez d'abord l'etape dashboard.")
    if not (shutil.which("node") and (shutil.which("npm") or shutil.which("npm.cmd"))):
        print("INFO : Node.js absent : la plateforme React n'est pas compilee ; le tableau de bord leger reste en place.")
        return
    if not a.sans_compilation:
        for d in (web, api):
            if not (d / "node_modules").exists():
                print(f"Installation des dependances : {d.relative_to(racine)}")
                npm(["install", "--no-audit", "--no-fund"], d)
        npm(["run", "build:autonome"], web)          # page autonome (donnees embarquees)
        npm(["run", "build"], web)                   # interface servie par l'API
        npm(["run", "build"], api)                   # API NestJS
    page = web / "dist-autonome" / "index.html"
    if not page.exists():
        sys.exit("Page autonome absente : compilation non faite.")
    html = page.read_bytes()
    if b"window.__DONNEES__=" not in html:
        sys.exit("Page autonome sans donnees embarquees : verifier le fichier *_donnees-plateforme_v1.json.")
    with zipfile.ZipFile(zp[0]) as z:
        contenu = {n: z.read(n) for n in z.namelist()}
    if b"__DONNEES__" not in contenu.get("tableau-de-bord.html", b""):      # premiere integration : on garde la page legere
        contenu["tableau-de-bord-leger.html"] = contenu["tableau-de-bord.html"]
    contenu["tableau-de-bord.html"] = html
    lm = contenu.get("LISEZ-MOI.txt", b"").decode("utf-8")
    if "PLATEFORME REACT" not in lm:
        lm = ("PLATEFORME REACT + NESTJS. tableau-de-bord.html est l'interface React compilee en page autonome : elle s'ouvre dans un\n"
              "navigateur, sans serveur ni Internet (donnees agregees embarquees). La meme interface peut etre servie par l'API NestJS\n"
              "(code dans le zip du code, dossier plateforme/ : powershell -ExecutionPolicy Bypass -File plateforme\\lancer_plateforme.ps1,\n"
              "puis http://localhost:3000). tableau-de-bord-leger.html : version de secours en JavaScript simple, memes chiffres.\n\n") + lm
        contenu["LISEZ-MOI.txt"] = lm.encode("utf-8")
    tmp = zp[0] + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for n, b in contenu.items():
            z.writestr(n, b)
    os.replace(tmp, zp[0])
    print(f"Plateforme React integree : tableau-de-bord.html ({len(html) // 1024} Ko, autonome) + tableau-de-bord-leger.html (secours).")


if __name__ == "__main__":
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    main()
