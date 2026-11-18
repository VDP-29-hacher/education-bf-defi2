import { useState } from 'react';
import { useApp } from '../contexte';
import { EnTete } from '../composants';
import { Icone } from '../icones';
import { priorites, telechargerCsv, ya } from '../lib';

export default function Methode() {
  const { D, e, source } = useApp();
  const [copie, setCopie] = useState('');
  const EQ = D.meta.equipe, N1 = D.years.length - 1;
  const copier = (t: string) => navigator.clipboard?.writeText(t).then(() => { setCopie(t); setTimeout(() => setCopie(''), 1800); }, () => prompt('Copiez :', t));
  const T: Record<string, any> = {}; (D.typo?.rows ?? []).forEach((x: any) => (T[x.p] = x));
  const PT: Record<string, any> = {}; (D.ptbs?.rows ?? []).forEach((x: any) => (PT[x.p] = x));
  const dl = (k: string) => {
    if (source === 'api') { window.location.href = `api/export/${k}${k === 'priorites' ? `?ips=${e.ips}&acces=${e.acc}` : ''}`; return; }
    const I = D.prov.ind;
    if (k === 'provinces') telechargerCsv(`${EQ}_provinces.csv`, ['province', 'ancienne_region', 'ips', 'ips_urbain', 'ips_rural', 'ecart_urbain_moins_rural', 'effectifs_sur_max', 'eleves_perdus', 'filles_a_inscrire', 'tbs_insd', 'profil'],
      (D.prov.names as string[]).map((n) => [n, I[n].region, D.prov.hist[n][N1], I[n].ips_urbain, I[n].ips_rural, I[n].ecart_urbain_moins_rural, I[n].effectif_dernier_sur_max, I[n].eleves_perdus_depuis_max, I[n].filles_manquantes_parite, PT[n]?.t ?? null, T[n] ? `${T[n].g}. ${T[n].nom}` : null]));
    if (k === 'priorites') telechargerCsv(`${EQ}_priorites.csv`, ['province', 'ancienne_region', 'priorite', 'ips', 'effectifs_sur_max', 'eleves_perdus', 'filles_a_inscrire', 'seuil_ips', 'seuil_acces'],
      priorites(D, e.ips, e.acc).map((o) => [o.province, o.region, o.priorite, o.ips, o.effectifsSurMax, o.elevesPerdus, o.fillesAInscrire, e.ips, e.acc]));
    if (k === 'regions') telechargerCsv(`${EQ}_regions.csv`, ['region', 'niveau', ...D.years.map(ya)], ['pri', 'pre', 'cp1'].flatMap((nv) => [...(D.regions as string[]).map((r) => [r, nv, ...D[nv][r]]), ['National', nv, ...D.nat[nv]]]));
    if (k === 'prevision') { const A: number[] = D.prov.prevAns; telechargerCsv(`${EQ}_prevision.csv`, ['province', 'modele', 'statut', ...A.flatMap((y) => [`ips_${y}`, `bas80_${y}`, `haut80_${y}`])],
      Object.entries<any>(D.prov.prev).map(([n, p]) => [n, p.modele, p.statut, ...A.flatMap((_, i) => [p.v[i], p.lo[i], p.hi[i]])])); }
  };
  const cmd1 = 'powershell -ExecutionPolicy Bypass -File scripts\\lancer_pipeline.ps1';
  const cmd2 = 'powershell -ExecutionPolicy Bypass -File plateforme\\lancer_plateforme.ps1';

  return (
    <div className="page">
      <EnTete titre="Méthodes et données" sousTitre={<>Chaque chiffre vient de tables agrégées et publiques. La chaîne complète se relance par une seule commande et reproduit les mêmes fichiers.</>} />
      <section className="carte-bloc"><h3>Le parcours des données, en cinq étapes</h3>
        <div className="parcours">{[
          ['Engineer', '01 Collecte', 'Inventaire du Data Pack et des sources en ligne, registre des sources avec empreinte sha256 et décision pour le Défi 2.'],
          ['Engineer', '02 Nettoyage', 'Tableaux DGESS remis en format long, noms harmonisés, doublons retirés, projections INSD extraites par province.'],
          ['Architect', '03 Transformation', 'Indicateurs de parité, modèle commun région × année, correspondance exacte 45 provinces → 17 régions par les codes COD-AB.'],
          ['Analyst · Scientist', '04 Analyse', 'Tendances, liens (Spearman), profils (k-moyennes), règle de priorité, prévision testée sur le passé.'],
          ['Analyst', '05 Interprétation', 'Dossier technique, fiche nationale, 17 fiches régionales et cette plateforme.']].map(([r, t, d]) => (
          <div key={t} className="etape"><span className="role">{r}</span><b>{t}</b>{d}</div>))}</div></section>
      <section className="carte-bloc"><h3>Architecture de la plateforme</h3>
        <div className="archi">
          <div><b>Pipeline Python</b><span>pandas, scipy, scikit-learn</span><span>tables agrégées → JSON</span></div><i><Icone nom="fleche" /></i>
          <div><b>API NestJS</b><span>/api/donnees, /api/priorites</span><span>/api/provinces/:nom, /api/export</span></div><i><Icone nom="fleche" /></i>
          <div><b>Interface React</b><span>Vite + TypeScript</span><span>graphiques SVG faits main</span></div>
        </div>
        <p className="note">Mode actuel : <b>{source === 'api' ? 'connecté à l’API NestJS' : 'page autonome (données embarquées, sans serveur)'}</b>. Les deux modes affichent les mêmes chiffres, issus du même fichier produit par le pipeline.</p></section>
      <div className="grille">
        <section className="carte-bloc"><h3>Lexique</h3><dl className="lexique">{[
          ['IPS', 'Indice de parité entre les sexes : filles ÷ garçons. 1,00 = parité ; sous 1, moins de filles.'],
          ['TBS', 'Taux brut de scolarisation : élèves du primaire ÷ enfants de 6 à 11 ans. Peut dépasser 100 % (élèves hors âge).'],
          ['TBA', "Taux brut d'admission : nouveaux inscrits au CP1 ÷ enfants de 6 ans."],
          ['TAP', "Taux d'achèvement du primaire : nouveaux élèves de CM2 ÷ enfants de 11 ans."],
          ['Effectifs / meilleur', "Élèves de la dernière année ÷ meilleure année depuis 2015 : mesure la perte d'accès."],
          ['Écart ville-campagne', 'IPS urbain − IPS rural. Positif : moins de filles à la campagne.'],
          ['Priorité 1 / 2', 'Province qui franchit les deux seuils (parité et effectifs) ou un seul.'],
          ['Spearman (rho)', 'Corrélation de rang entre deux mesures, de −1 à 1 ; « significatif » si p < 0,05.'],
          ['Marge à 80 %', 'Bande où la valeur réelle est tombée 8 fois sur 10 lors des tests sur le passé.']].map(([t, d]) => <div key={t}><dt>{t}</dt><dd>{d}</dd></div>)}</dl></section>
        <section className="carte-bloc"><h3>Sources</h3><ul>
          <li>DGESS / MENAPLN : annuaires statistiques du préscolaire et du primaire, {D.meta.periode}.</li>
          <li>INSD : projections de population 2020-2035 par province, sexe et âge.</li>
          <li>OCHA / IGB (HDX) : limites administratives COD-AB.</li></ul>
          <h3 className="espace">Contrôles faits à chaque relance</h3><ul>
          <li>Filles + garçons = total, pour chaque région et chaque année.</li>
          <li>Somme des 45 provinces = national ; chaque province tombe dans une seule des 17 régions.</li>
          <li>Population INSD par province : sa somme retrouve la population utilisée par la DGESS.</li>
          <li>Prévision : quatre modèles testés en 2019, 2020 et 2021 ; le plus fiable est retenu.</li></ul></section>
        <section className="carte-bloc"><h3>Refaire tous les chiffres</h3>
          <p className="sub">Depuis le dossier du projet, sous Windows (Python 3 avec pandas, scipy, scikit-learn) :</p>
          <pre className="code">{cmd1}</pre><button type="button" className="bouton petit fantome" onClick={() => copier(cmd1)}>{copie === cmd1 ? 'Commande copiée' : 'Copier'}</button>
          <p className="sub">Puis lancer la plateforme (Node.js 20 ou plus) :</p>
          <pre className="code">{cmd2}</pre><button type="button" className="bouton petit fantome" onClick={() => copier(cmd2)}>{copie === cmd2 ? 'Commande copiée' : 'Copier'}</button>
          <p className="note">La plateforme s'ouvre sur http://localhost:3000. Quand le pipeline est relancé, l'API recharge les données toute seule.</p></section>
        <section className="carte-bloc"><h3>Télécharger les données</h3><p className="sub">Fichiers CSV (point-virgule), lisibles dans Excel{source === 'api' ? ', servis par l’API' : ''}.</p>
          <div className="boutons">
            <button type="button" className="bouton" onClick={() => dl('provinces')}>45 provinces : indicateurs</button>
            <button type="button" className="bouton" onClick={() => dl('priorites')}>Provinces prioritaires (seuils actuels)</button>
            <button type="button" className="bouton" onClick={() => dl('regions')}>Régions : IPS par année</button>
            <button type="button" className="bouton" onClick={() => dl('prevision')}>Prévision par province</button></div></section>
      </div>
      <section className="carte-bloc"><h3>Limites à garder en tête</h3><ul>{(D.meta.limites as string[]).map((l) => <li key={l}>{l}</li>)}</ul></section>
    </div>
  );
}
