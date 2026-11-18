<#
.SYNOPSIS
  Lance le pipeline Data Challenge Burkina (Defi 2) dans le bon ordre.

.DESCRIPTION
  Etapes (dans cet ordre, quel que soit l'ordre passe) :
    collecte         01_collecte        copie les bruts, registre, couverture des annees
    annoter          01_collecte        sources, decisions et notes du registre / LISEZ-MOI
    nettoyage        02_nettoyage       table longue propre, journal, anomalies
    verification     02_nettoyage       cherche les totaux nationaux de la base dans les annuaires 2024-2025
    provinces        02_nettoyage       extraction par PROVINCE depuis l'annuaire primaire 2024-2025 (G/F, 10 annees, classes, redoublants)
    population_profil 02_nettoyage      projections INSD : profil de structure seulement (titres, annees, nombre de lignes), aucune valeur
    population_insd  02_nettoyage       projections INSD : population par province, annee, sexe (options -PopPages 120-135 -PopOrdre annee|sexe)
    transformation   03_transformation IPS, ecarts, classement, tendances, dictionnaire        (ETAPE 3)
    validation       03_transformation verifie la table des 45 provinces d'avant la reforme avec les fichiers PDI
    liaison_communes 03_transformation reconstruction par les NOMS de communes (PDI) : sert de controle
    liaison_officielle 03_transformation liaison 13/17 regions par les CODES COD-AB (methode du Guide du Data Pack), GeoJSON des 13 regions
    modele_commun    03_transformation modele commun region x annee (architect) : eleves, TBS, population implicite, eleves a ajouter
    analyse          04_analyse         indicateurs cles, figures, tableau de bord HTML (ETAPE 4, a partir de 03 seulement)
    analyse_provinces 04_analyse        45 provinces : IPS, urbain/rural, acces (effectifs / maximum), IPS non interpretables signales
    analyse_regions17 04_analyse        17 regions actuelles : agregation exacte des provinces (effectifs, IPS, eleves perdus)
    analyse_population 04_analyse       TBS par province et par sexe avec la population INSD (si extraite)
    liens_groupes    04_analyse         liens entre les ecarts (Spearman) et typologie des provinces (k-moyennes)
    analyse_acces    04_analyse         TBS/TBA/TAP par region et par sexe, provinces prioritaires, LISEZ-MOI de l'etape 4
    prevision        04_analyse         role scientist : projection de l'IPS par province, validation sur le passe
    dashboard        04_analyse         tableau de bord interactif (acces, parite, provinces, priorites) integre au zip
    lisez_moi        racine             LISEZ-MOI.md : les 7 parties du plan de documentation et les criteres du jury, chiffres recalcules
    plateforme       04_analyse         interface React compilee (page autonome) + API NestJS (plateforme/), si Node.js est installe
    interpretation   05_interpretation  fiche de synthese nationale (page 1) + une fiche par region actuelle (pages 2 a 18)
    documentation    05_interpretation  dossier technique complet (.docx) genere depuis les tables
    architecture     architecture/      livrable Architect (PDF 3 pages) genere depuis le dictionnaire
    depot            depot_final        paquets a deposer (donnees, code, documentation) + controle automatique avant depot

  Par defaut : nettoyage, verification, transformation, validation, liaison_communes, liaison_officielle (la collecte est deja faite).
  Regle du challenge : ces scripts sont lances PAR VOUS, en local. Les bruts ne sont jamais envoyes a une IA.

.EXAMPLE
  .\lancer_pipeline.ps1 -ApercuSeulement                 # affiche les commandes sans rien lancer
  .\lancer_pipeline.ps1 -AnneeNumerique fin              # annees numeriques du classeur = annees de FIN (confirme)
  .\lancer_pipeline.ps1 -Etapes liaison_communes         # une seule etape
  .\lancer_pipeline.ps1 -Etapes tout -AnneeNumerique fin # tout, de la collecte au paquet de depot
                                                         # (collecte sautee si le dossier des bruts est absent : 01_collecte fait foi)
  .\lancer_pipeline.ps1 -Etapes collecte -Brut D:\DataPack  # refaire la collecte depuis le Data Pack telecharge
#>
param(
    [string]$Equipe = "Burkina_Novation",
    [ValidateSet("debut", "fin")][string]$AnneeNumerique = "fin",
    [string[]]$Etapes = @("nettoyage", "verification", "transformation", "validation", "liaison_communes", "liaison_officielle"),
    [string]$Brut = "",
    [string]$PopPages = "",
    [ValidateSet("annee", "sexe")][string]$PopOrdre = "annee",
    [string]$PopSous = "",
    [switch]$ApercuSeulement
)
$ErrorActionPreference = "Stop"
$scripts = $PSScriptRoot
$racine = Split-Path $scripts -Parent
# Dossier du Data Pack telecharge (bruts) : utile seulement pour l'etape 'collecte'. Par defaut : <racine>\donnees_brutes.
$brut = if ($Brut) { $Brut } else { Join-Path $racine "donnees_brutes" }
$c01 = Join-Path $racine "01_collecte"
$c02 = Join-Path $racine "02_nettoyage"
$c03 = Join-Path $racine "03_transformation"
$refTable = Join-Path $scripts "reference\ancien_decoupage_13_a_valider.csv"
$ordre = @("collecte", "annoter", "nettoyage", "verification", "provinces", "population_profil", "population_insd", "transformation", "validation", "liaison_communes", "liaison_officielle", "modele_commun", "analyse", "analyse_provinces", "analyse_regions17", "analyse_population", "liens_groupes", "analyse_acces", "prevision", "dashboard", "plateforme", "interpretation", "documentation", "architecture", "lisez_moi", "depot")
$c04 = Join-Path $racine "04_analyse"
$c05 = Join-Path $racine "05_interpretation"
$Etapes = @($Etapes | ForEach-Object { $_ -split "[,;]" } | Where-Object { $_ })   # accepte "a,b,c" meme avec powershell -File
if ($Etapes -contains "tout") { $Etapes = $ordre }
foreach ($e in $Etapes) { if ($ordre -notcontains $e) { throw "Etape inconnue : $e (valeurs : $($ordre -join ', '), tout)" } }
# La numerotation [n/total] compte les LANCEMENTS de scripts : une etape peut en lancer plusieurs (verification = 2).
$lancementsParEtape = @{ "verification" = 2; "depot" = 2 }
$script:total = 0
foreach ($e in $ordre) { if ($Etapes -contains $e) { $script:total += $(if ($lancementsParEtape.ContainsKey($e)) { $lancementsParEtape[$e] } else { 1 }) } }
$script:num = 0

function Trouver([string]$dossier, [string]$motif) {
    $f = Get-ChildItem -Path $dossier -Filter $motif -File -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $f) { throw "Fichier introuvable : $motif dans $dossier" }
    return $f.FullName
}

function Lancer([string]$titre, [string[]]$arguments) {
    $script:num++
    Write-Host ""
    Write-Host "==> [$($script:num)/$($script:total)] $titre" -ForegroundColor Cyan
    Write-Host ("python " + (($arguments | ForEach-Object { if ($_ -match "\s") { "`"$_`"" } else { $_ } }) -join " "))
    if ($ApercuSeulement) { return }
    & python @arguments
    if ($LASTEXITCODE -ne 0) { throw "Echec de l'etape '$titre' (code $LASTEXITCODE). Lisez le message ci-dessus." }
}

foreach ($e in $ordre) {
    if ($Etapes -notcontains $e) { continue }
    switch ($e) {
        "collecte" {
            if (-not (Test-Path $brut)) {
                # 01_collecte contient deja les copies en lecture seule et le registre : il fait foi. On ne casse pas toute la chaine.
                $script:num++
                Write-Host ""
                Write-Host "==> [$($script:num)/$($script:total)] collecte : SAUTEE" -ForegroundColor Yellow
                Write-Host "    Dossier des bruts introuvable : $brut"
                Write-Host "    01_collecte (copies en lecture seule + registre) est utilise tel quel. Pour refaire la collecte :"
                Write-Host "    .\lancer_pipeline.ps1 -Etapes collecte -Brut <dossier du Data Pack telecharge>"
            } else {
                Lancer "collecte -> 01_collecte" @("$scripts\collecte_template.py", $brut, $c01, "--equipe", $Equipe)
            }
        }
        "annoter" {
            Lancer "annotation du registre (sources, decisions, notes)" @("$scripts\annoter_registre.py", $c01)
        }
        "nettoyage" {
            $xlsx = Trouver $c01 "*donnees-statistques-prescolaire-et-primaire*.xlsx"
            Lancer "nettoyage -> 02_nettoyage (annees numeriques : $AnneeNumerique)" @(
                "$scripts\nettoyage_template.py", $xlsx, $c02, "--equipe", $Equipe, "--annee-numerique", $AnneeNumerique)
        }
        "verification" {
            $long = Join-Path $c02 "${Equipe}_02-nettoyage_D2_engineer_tableaux-long_v1.csv"
            if (-not $ApercuSeulement -and -not (Test-Path $long)) { throw "Table propre introuvable : lancez d'abord l'etape nettoyage ($long)" }
            $annPre = Trouver $c01 "*cns528*prescolaire-2024-2025*.csv"
            $annPri = Trouver $c01 "*cns530*primaire-2024-2025*.csv"
            Lancer "verification des totaux : PRESCOLAIRE contre l'annuaire prescolaire 2024-2025" @(
                "$scripts\verifier_total_annuaire.py", $long, $annPre, $c02, "--equipe", $Equipe, "--niveau", "prescolaire")
            Lancer "verification des totaux : primaire contre l'annuaire primaire 2024-2025" @(
                "$scripts\verifier_total_annuaire.py", $long, $annPri, $c02, "--equipe", $Equipe, "--niveau", "primaire")
        }
        "provinces" {
            $annPri = Trouver $c01 "*cns530*primaire-2024-2025*.csv"
            Lancer "extraction par province (annuaire primaire 2024-2025) -> 02_nettoyage" @(
                "$scripts\extraction_provinces.py", $annPri, $refTable, $c02, "--equipe", $Equipe, "--niveau", "primaire")
        }
        "population_profil" {
            $proj = Trouver $c01 "*projections-demographiques-2020-2035_v1.csv"
            $popArgs = @("$scripts\extraction_population_insd.py", $proj, $refTable, $c02, "--equipe", $Equipe, "--mode", "profil")
            if ($PopPages) { $popArgs += @("--pages", $PopPages) }
            Lancer "population INSD : PROFIL de structure (aucune valeur affichee)" $popArgs
        }
        "population_insd" {
            $proj = Trouver $c01 "*projections-demographiques-2020-2035_v1.csv"
            $popArgs = @("$scripts\extraction_population_insd.py", $proj, $refTable, $c02, "--equipe", $Equipe, "--mode", "extraction", "--ordre", $PopOrdre)
            if ($PopPages) { $popArgs += @("--pages", $PopPages) }
            if ($PopSous) { $popArgs += @("--sous", $PopSous) }
            Lancer "population INSD par province (projections RGPH 2019) -> 02_nettoyage" $popArgs
        }
        "transformation" {
            $long = Join-Path $c02 "${Equipe}_02-nettoyage_D2_engineer_tableaux-long_v1.csv"
            if (-not $ApercuSeulement -and -not (Test-Path $long)) { throw "Table propre introuvable : lancez d'abord l'etape nettoyage ($long)" }
            Lancer "transformation (ETAPE 3) -> 03_transformation" @("$scripts\transformation_template.py", $long, $c03, "--equipe", $Equipe)
        }
        "validation" {
            Lancer "validation de la table des provinces (fichiers PDI)" @("$scripts\valider_decoupage.py", $c01, $refTable, $c03, "--equipe", $Equipe)
        }
        "liaison_communes" {
            $admin3 = Trouver $c01 "*admin3*.geojson"
            Lancer "liaison par les communes : ancienne region (13) de chaque nouvelle province (17 regions)" @(
                "$scripts\liaison_communes.py", $admin3, $c01, $refTable, $c03, "--equipe", $Equipe)
        }
        "liaison_officielle" {
            $classeur = Trouver $c01 "*bfa-admin-boundaries_v1.xlsx"
            $admin3 = Trouver $c01 "*admin3*.geojson"
            $reconstruction = Join-Path $c03 "${Equipe}_03-transformation_D2_engineer_liaison-communes_v1.csv"
            Lancer "liaison OFFICIELLE 13/17 regions par les codes COD-AB (compare a la reconstruction par les noms)" @(
                "$scripts\liaison_officielle.py", $classeur, $admin3, $c03, "--equipe", $Equipe, "--reconstruction", $reconstruction)
        }
        "modele_commun" {
            Lancer "modele commun region x annee (role architect) : eleves, taux d'acces, population -> 03_transformation" @(
                "$scripts\modele_commun.py", $c02, $c03, "--equipe", $Equipe)
        }
        "analyse" {
            Lancer "analyse (ETAPE 4) -> 04_analyse : indicateurs, figures, tableau de bord (tables agregees seulement)" @(
                "$scripts\analyse_template.py", $c03, $c04, "--equipe", $Equipe)
        }
        "analyse_provinces" {
            Lancer "analyse par province (45 anciennes provinces) -> 04_analyse" @(
                "$scripts\analyse_provinces.py", $c02, $c04, "--equipe", $Equipe)
        }
        "analyse_regions17" {
            Lancer "17 regions actuelles : agregation exacte des 45 anciennes provinces -> 04_analyse" @(
                "$scripts\analyse_regions17.py", $c02, $c03, $c04, "--equipe", $Equipe)
        }
        "analyse_population" {
            Lancer "TBS par province avec la population INSD -> 04_analyse (rien si la population n'est pas extraite)" @(
                "$scripts\analyse_population_provinces.py", $c02, $c03, $c04, "--equipe", $Equipe)
        }
        "liens_groupes" {
            Lancer "liens et groupes (Defi 2) : correlations entre ecarts, typologie des 45 provinces -> 04_analyse" @(
                "$scripts\analyse_liens_groupes.py", $c04, "--equipe", $Equipe)
        }
        "analyse_acces" {
            Lancer "acces (TBS, TBA, TAP par region) et provinces prioritaires -> 04_analyse (+ LISEZ-MOI de l'etape 4)" @(
                "$scripts\analyse_acces.py", $c03, $c04, "--equipe", $Equipe)
        }
        "prevision" {
            Lancer "prevision de l'IPS par province (role scientist, validation sur le passe) -> 04_analyse" @(
                "$scripts\prevision_provinces.py", $c04, "--equipe", $Equipe)
        }
        "dashboard" {
            Lancer "dashboard interactif -> integre au zip de 04_analyse" @(
                "$scripts\dashboard_template.py", $c03, $c04, "--equipe", $Equipe)
        }
        "plateforme" {
            Lancer "plateforme React + NestJS : page autonome compilee et integree au zip de 04_analyse (rien si Node.js absent)" @(
                "$scripts\integrer_plateforme.py", $c04, "--equipe", $Equipe)
        }
        "interpretation" {
            Lancer "interpretation (ETAPE 5) -> 05_interpretation : fiche de synthese nationale + 17 fiches regionales" @(
                "$scripts\interpretation_template.py", $c04, $c05, "--equipe", $Equipe)
        }
        "documentation" {
            Lancer "documentation complete -> 05_interpretation (dossier technique .docx)" @(
                "$scripts\documentation_template.py", $c02, $c03, $c04, $c05, "--equipe", $Equipe)
        }
        "architecture" {
            Lancer "architecture (livrable Architect) -> architecture/ : schema du pipeline, modele de donnees, decisions" @(
                "$scripts\architecture_template.py", $c03, (Join-Path $racine "architecture"), "--equipe", $Equipe)
        }
        "lisez_moi" {
            Lancer "LISEZ-MOI general (plan de la documentation + criteres du jury) -> LISEZ-MOI.md a la racine" @(
                "$scripts\lisez_moi.py", "--equipe", $Equipe)
        }
        "depot" {
            Lancer "paquets de depot (donnees, code, documentation) + controle avant depot" @("$scripts\depot_final.py", "preparer", "--equipe", $Equipe)
            Lancer "rangement pour la plateforme -> A_DEPOSER (une etape = un dossier, categorie, guide de depot)" @("$scripts\organiser_depot.py", $racine)
        }
    }
}
Write-Host ""
if ($ApercuSeulement) { Write-Host "Apercu termine : rien n'a ete lance." -ForegroundColor Yellow }
else { Write-Host "Termine. Collez les consoles (compteurs seulement) pour verification." -ForegroundColor Green }
