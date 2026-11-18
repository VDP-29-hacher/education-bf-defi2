import { useState } from 'react';
import { useApp } from '../contexte';
import { EnTete } from '../composants';
import { Carte, Jauge, Tableau } from '../graphiques';
import { f2, f3, nbf, pc, pc1, PROFILS, ya, type Num } from '../lib';

export default function Analyse() {
  const { D, P, ouvrir } = useApp();
  const [survol, setSurvol] = useState('');
  const N1 = D.years.length - 1, y0 = ya(D.years[0]), y1 = ya(D.years[N1]), I = D.prov.ind, ns: string[] = D.prov.names;
  const H = (n: string) => D.prov.hist[n][N1] as Num;
  const K: [string, string, string?][] = [], k: string[] = [];
  const z = D.acc?.tbs_primaire?.z;
  let rsAcc: string[] = [];
  if (z) {
    rsAcc = (D.regions as string[]).filter((r) => z[r]?.t[N1] != null).sort((a, b) => z[a].t[N1] - z[b].t[N1]);
    K.push([pc(z.National.t[N1]), `TBS primaire national en ${y1} (${y0} : ${pc(z.National.t[0])})`]);
    k.push(`L'écart le plus fort est territorial : en ${y1}, le taux brut de scolarisation du primaire est de ${pc(z[rsAcc[0]].t[N1])} (${rsAcc[0]}) et ${pc(z[rsAcc[1]].t[N1])} (${rsAcc[1]}), contre ${pc(z[rsAcc.at(-1) as string].t[N1])} (${rsAcc.at(-1)}).`);
  }
  const mcN = D.mc?.find((x: any) => x.r === 'National'), mcR = (D.mc ?? []).filter((x: any) => x.r !== 'National' && x.plus > 0).sort((a: any, b: any) => b.plus - a.plus);
  if (mcN) {
    K.push([nbf(mcN.plus), `élèves à ajouter au primaire pour un TBS de 100 % (${nbf(mcN.pop)} enfants d'âge primaire)`, 'alerte']);
    k.push(`Il faudrait ${nbf(mcN.plus)} élèves de plus au primaire pour atteindre un taux brut de 100 %, dont ${mcR.slice(0, 3).map((x: any) => `${nbf(x.plus)} (${x.r})`).join(', ')}.`);
  }
  const acc = ns.filter((n) => I[n].effectif_dernier_sur_max < 0.6).sort((a, b) => I[a].effectif_dernier_sur_max - I[b].effectif_dernier_sur_max);
  const perdus = acc.reduce((t, n) => t + (I[n].eleves_perdus_depuis_max || 0), 0), fm = ns.reduce((t, n) => t + (I[n].filles_manquantes_parite || 0), 0);
  const ip = ns.filter((n) => H(n) != null).sort((a, b) => (H(a) as number) - (H(b) as number));
  const p1 = (D.prov.prio as any[]).filter((r) => r.priorite === 1).map((r) => r.province as string);
  K.push([nbf(perdus), `élèves en moins dans les ${acc.length} provinces sous 60 % de leur meilleur effectif`, 'alerte']);
  K.push([nbf(fm), 'filles à inscrire en plus pour atteindre la parité dans toutes les provinces']);
  K.push([String(p1.length), "provinces en priorité 1 : faible parité et perte d'élèves", 'alerte']);
  k.push(`Des provinces se vident : ${acc.length} sur ${ns.length} comptent moins de 60 % des élèves de leur meilleure année (${acc.slice(0, 4).map((n) => `${n} ${pc1(I[n].effectif_dernier_sur_max)}`).join(', ')}). Ensemble, elles ont perdu ${nbf(perdus)} élèves.`);
  k.push(`La parité progresse au primaire (IPS ${f2(D.nat.pri[0])} en ${y0}, ${f2(D.nat.pri[N1])} en ${y1}), mais l'écart se forme dès le CP1 (${f2(D.nat.cp1[N1])}). Par province, l'IPS va de ${f2(H(ip[0]))} (${ip[0]}) à ${f2(H(ip.at(-1) as string))} (${ip.at(-1)}).`);
  const ur = ns.filter((n) => I[n].ecart_urbain_moins_rural > 0).length;
  k.push(`Entre ville et campagne, l'écart d'IPS passe de ${f3(D.mil.urbain[0] - D.mil.rural[0])} à ${f3(D.mil.urbain[N1] - D.mil.rural[N1])}, mais l'IPS rural reste sous l'urbain dans ${ur} provinces sur ${ns.length}.`);
  const T: Record<string, any> = {}; (D.typo?.rows ?? []).forEach((x: any) => (T[x.p] = x));
  const groupes = [...new Map<number, string>((D.typo?.rows ?? []).map((x: any) => [x.g, x.nom])).entries()].sort((a, b) => a[0] - b[0]);
  const prov = (n: string) => <button type="button" className="lien" onClick={() => ouvrir(n)}>{n}</button>;

  return (
    <div className="page">
      <EnTete titre="Analyse des écarts d'accès" sousTitre={<>Les chiffres clés, les territoires les plus touchés, puis les liens entre les écarts et les profils de provinces qui en ressortent.</>} />
      <div className="kpis">{K.map(([v, l, t]) => <div key={l} className={`kpi ${t ?? ''}`}><b>{v}</b><span>{l}</span></div>)}</div>
      <section className="carte-bloc"><h3>Ce que montrent les données</h3><ul className="constats">{k.map((x) => <li key={x}>{x}</li>)}</ul></section>
      <div className="grille">
        {z && <section className="carte-bloc"><h3>Régions où l'accès est le plus faible</h3>
          <Tableau entetes={['Région', 'Garçons', 'Filles', 'Ensemble']} lignes={rsAcc.slice(0, 6).map((r) => [r, pc(z[r].g[N1]), pc(z[r].f[N1]), <Jauge v={z[r].t[N1]} max={120} txt={pc(z[r].t[N1])} couleur={P.dlow} />])} />
          <p className="note">Taux brut de scolarisation du primaire, {y1} (taux publiés par la DGESS).</p></section>}
        <section className="carte-bloc"><h3>Provinces qui ont perdu le plus d'élèves</h3>
          <Tableau gauche={2} entetes={['Province', 'Ancienne région', 'Effectifs / meilleur', 'Élèves en moins']}
            lignes={acc.slice(0, 8).map((n) => [prov(n), I[n].region, <Jauge v={I[n].effectif_dernier_sur_max} max={1} txt={pc1(I[n].effectif_dernier_sur_max)} couleur={P.dlow} />, nbf(I[n].eleves_perdus_depuis_max)])} />
          <p className="note">Effectif {y1} rapporté au meilleur effectif de la province depuis 2015.</p></section>
        <section className="carte-bloc"><h3>Provinces les plus éloignées de la parité</h3>
          <Tableau gauche={2} entetes={['Province', 'Ancienne région', 'IPS', 'Filles manquantes']}
            lignes={ip.slice(0, 8).map((n) => [prov(n), I[n].region, <Jauge v={1 - (H(n) as number)} max={0.25} txt={f2(H(n))} couleur={P.s2} />, nbf(I[n].filles_manquantes_parite)])} />
          <p className="note">IPS du primaire {y1} : il faudrait inscrire ces filles en plus pour atteindre un IPS de 1.</p></section>
        {mcN && <section className="carte-bloc"><h3>Élèves à ajouter pour un taux brut de 100 %</h3>
          <Tableau entetes={['Région', "Enfants d'âge primaire", 'Élèves', 'TBS', 'À ajouter']}
            lignes={mcR.map((x: any) => [x.r, nbf(x.pop), nbf(x.el), pc(x.tbs), <Jauge v={x.plus} max={mcR[0].plus} txt={nbf(x.plus)} couleur={P.dlow} />])} />
          <p className="note">Enfants d'âge primaire = élèves ÷ TBS, la population utilisée par la DGESS. Un TBS de 100 % compte aussi les élèves hors âge : ces chiffres sont un minimum.</p></section>}
        {D.ptbs && <section className="carte-bloc"><h3>Taux brut de scolarisation par province</h3>
          <Tableau gauche={2} entetes={['Province', 'Ancienne région', 'TBS', 'Filles', 'Garçons', 'Élèves en plus']}
            lignes={(D.ptbs.rows as any[]).slice(0, 10).map((x) => [prov(x.p), x.r, <Jauge v={x.t} max={120} txt={pc(x.t)} couleur={P.dlow} />, pc(x.f), pc(x.g), nbf(x.plus)])} />
          <p className="note">Population INSD {D.ptbs.annee} ; méthode : {D.ptbs.methode}. Les 10 provinces au taux le plus bas sur {D.ptbs.rows.length}.</p></section>}
        {D.typo && <section className="carte-bloc"><h3>Profils de provinces (typologie)</h3>
          <div className="legende colonne">{groupes.map(([g, nom]) => <span key={g} className={T[survol]?.g === g ? 'actif' : ''}><i className="carre" style={{ background: PROFILS[(g - 1) % 5] }} />{g}. {nom} ({D.typo.rows.filter((x: any) => x.g === g).length})</span>)}</div>
          <Carte geo={D.prov.geo} vb={D.prov.vb} label="Carte des profils de provinces" survol={survol} setSurvol={setSurvol} onPick={(n) => ouvrir(n)}
            fill={(n) => (T[n] ? PROFILS[(T[n].g - 1) % 5] : P.grid)}
            info={(n) => <><b>{n}</b>{T[n] && <><div>{T[n].g}. {T[n].nom}</div><div>TBS {pc(T[n].acc)} · IPS {f2(T[n].ips)} · écart V-C {f3(T[n].ec)}</div></>}</>} />
          <p className="note">Classification par k-moyennes sur trois mesures du Défi 2 : accès, parité entre filles et garçons, écart entre ville et campagne ({D.typo.k} groupes).</p></section>}
        {D.liens && <section className="carte-bloc"><h3>Les écarts se cumulent-ils ?</h3>
          <div className="liens">{(D.liens as any[]).map((x) => (
            <div key={x.q} className="lien-ligne">
              <span className="q">{x.q}</span>
              <span className="rho" title={`rho = ${f2(x.rho)}`}><i className="axe" /><i className="val" style={{ left: x.rho < 0 ? `${50 + x.rho * 50}%` : '50%', width: `${Math.abs(x.rho) * 50}%`, background: x.sig ? P.brand2 : P.grid }} /></span>
              <span className={`etiquette ${x.sig ? '' : 'neutre'}`}>{f2(x.rho)} {x.sig ? '· significatif' : '· non significatif'}</span>
            </div>))}</div>
          <p className="note">Corrélation de rang de Spearman sur les 45 provinces, de −1 (gauche) à +1 (droite). « Significatif » : p &lt; 0,05. Une corrélation n'est pas une cause.</p></section>}
      </div>
    </div>
  );
}
