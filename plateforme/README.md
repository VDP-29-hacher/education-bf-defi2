# Plateforme du Défi 2 : API NestJS et interface React

Cette plateforme répond à la question du Défi 2 : *où les écarts d'accès à l'école sont-ils les plus grands (filles-garçons, ville-campagne), et comment évoluent-ils ?*

Elle affiche les chiffres produits par le pipeline Python du projet (`scripts/`). Elle ne lit que des tables agrégées et publiques, jamais de données brutes ni individuelles.

```
Pipeline Python ──> 04_analyse/<EQUIPE>_04-analyse_D2_analyst_donnees-plateforme_v1.json
                        │
                        ├──> API NestJS (plateforme/api)     http://localhost:3000/api/...
                        │         └── sert aussi l'interface compilée
                        └──> Interface React (plateforme/web)
                                  ├── mode API       : données lues sur /api/donnees
                                  └── mode autonome  : une seule page HTML, données embarquées, sans serveur
```

## Lancer

Il faut Node.js 20 ou plus.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\lancer_pipeline.ps1                 # refait les chiffres (Python)
powershell -ExecutionPolicy Bypass -File plateforme\lancer_plateforme.ps1           # ouvre http://localhost:3000
```

L'API surveille le fichier de données. Quand le pipeline est relancé, elle recharge les chiffres sans redémarrer.

## Routes de l'API

| Route | Rôle |
|---|---|
| `GET /api/sante` | état du service, fichier chargé, date |
| `GET /api/donnees` | tout le paquet agrégé (utilisé par l'interface) |
| `GET /api/regions?niveau=pri\|pre\|cp1&annee=2024` | IPS des 13 anciennes régions pour une année |
| `GET /api/provinces` | les 45 provinces et leurs indicateurs |
| `GET /api/provinces/:nom` | fiche d'une province : historique, projection, profil, signalements |
| `GET /api/priorites?ips=0.95&acces=0.6` | simulateur de ciblage (priorité 1 : les deux seuils ; priorité 2 : un seul) |
| `GET /api/export/:table` | CSV pour Excel : `provinces`, `priorites`, `regions`, `prevision` |

Un paramètre hors bornes renvoie une erreur 400, une province inconnue une erreur 404.

## Interface

L'interface a sept onglets : Accueil, Analyse, Tableau de bord, Carte, Aide à la décision, Prévision, Méthode et données.

- **Recherche de province** dans l'en-tête.
- **Lien partageable** : l'onglet et les réglages sont gardés dans l'adresse.
- **Lecture animée** des dix années dans le tableau de bord.
- **Liens entre la carte et les classements** : survoler l'un met en évidence l'autre.
- **Fiche de province imprimable**.
- Thème clair ou sombre, navigation au clavier, affichage sur téléphone.

Les graphiques sont des SVG écrits à la main, sans bibliothèque de graphiques.

Pour développer :

```powershell
cd plateforme\api; npm install; npm run build; npm start                # API sur le port 3000
cd plateforme\web; npm install; npm run dev                             # Vite sur le port 5173, /api redirigé vers l'API
cd plateforme\web; npm run build:autonome                               # page autonome dans web\dist-autonome\index.html
```
