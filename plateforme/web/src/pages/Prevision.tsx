import { useApp } from '../contexte';
import { EnTete } from '../composants';
import { Courbes, Intervalles, Tableau } from '../graphiques';
import { f2, f3, ya, type Num } from '../lib';

const LIBM: Record<string, string> = { persistance: "Persistance (l'IPS ne bouge pas)", tendance_amortie: 'Tendance amortie', tendance_5ans: 'Tendance sur 5 ans', moyenne_3ans: 'Moyenne des 3 dernières années' };

export default function Prevision() {
  const { D, P, e, maj } = useApp();
  const Pv = D.prov.prev ?? {}, A: number[] = D.prov.prevAns ?? [];
  if (!A.length) return <div className="page"><p>Prévision non disponible.</p></div>;
  const n = Pv[e.p] ? e.p : Object.keys(Pv)[0], pv = Pv[n], hs: Num[] = D.prov.hist[n], nb = D.years.length;
  const der = hs[nb - 1] ?? hs.filter((v) => v != null).at(-1) ?? null, pont = (v: Num[]) => [...hs.map((x, i) => (i === nb - 1 ? der : null)), ...v];
  const couleur = (s: string) => (/^sous/.test(s) ? P.dlow : /^incertain/.test(s) ? P.s2 : P.dhigh);
  const ns = Object.keys(Pv).filter((q) => Pv[q].v.at(-1) != null).sort((a, b) => Pv[a].v.at(-1) - Pv[b].v.at(-1));
  const bt: any[] = D.bt ?? [], ret = (bt.find((b) => b.retenu === true || b.retenu === 'True') ?? {}).modele;
  const moy = (md: string) => { const r = bt.filter((b) => b.modele === md); return r.reduce((t, b) => t + b.mae, 0) / r.length; };
  const mods = [...new Set(bt.map((b) => b.modele as string))].sort((a, b) => moy(a) - moy(b)), q80 = (h: number) => bt.find((b) => b.modele === ret && b.horizon === h)?.q80 ?? null;
  const sous = ns.filter((q) => /^sous/.test(Pv[q].statut)), inc = ns.filter((q) => /^incertain/.test(Pv[q].statut));

  return (
    <div className="page">
      <EnTete titre={`Prévision de la parité d'ici ${ya(A.at(-1) as number)}`} sousTitre={`L'IPS de chaque province projeté jusqu'en ${ya(A.at(-1) as number)}, avec sa marge d'erreur mesurée sur le passé.`} />
      <div className="message">Modèle retenu : <b>{LIBM[ret] ?? ret}</b>, le plus fiable des quatre sur les années passées. Marge d'erreur, 8 fois sur 10 : ±{f3(q80(1))} à un an, ±{f3(q80(3))} à trois ans.
        En {ya(A.at(-1) as number)}, <b>{sous.length} provinces</b> resteraient sous 0,95 même dans le scénario haut ({sous.join(', ')}) et {inc.length} sont incertaines.</div>
      <div className="commandes"><label>Province<select value={n} onChange={(x) => maj({ p: x.target.value })}>{Object.keys(Pv).sort((a, b) => a.localeCompare(b, 'fr')).map((k) => <option key={k}>{k}</option>)}</select></label>
        <span className="sub">{n} : {f2(pv.v.at(-1))} projeté en {ya(A.at(-1) as number)}, entre {f2(pv.lo.at(-1))} et {f2(pv.hi.at(-1))}. {pv.statut}.</span></div>
      <div className="grille">
        <section className="carte-bloc"><h3>{n} : IPS observé puis projeté</h3>
          <Courbes labels={[...D.years, ...A].map(ya)} label="IPS observé et projeté" bande={[pont(pv.hi), pont(pv.lo)]}
            series={[{ nom: 'IPS observé', court: 'Observé', couleur: P.s1, vals: [...hs, ...A.map(() => null)], sansEtiquette: true }, { nom: 'Projection', court: 'Projeté', couleur: P.s2, vals: pont(pv.v), tirets: true }]} />
          <p className="note">Trait plein : IPS observé. Pointillés : projection si la situation actuelle se prolonge. Zone grisée : 8 fois sur 10, la valeur réelle tombera dans cette bande.</p></section>
        <section className="carte-bloc"><h3>IPS projeté en {ya(A.at(-1) as number)}, les 45 provinces</h3>
          <div className="legende"><span><i className="carre rond" style={{ background: P.dlow }} />Sous 0,95 même au mieux</span><span><i className="carre rond" style={{ background: P.s2 }} />Incertain</span><span><i className="carre rond" style={{ background: P.dhigh }} />Au-dessus de 0,95</span></div>
          <div className="defile"><Intervalles lo={0.7} hi={1.15} seuil={0.95} sel={n} onPick={(q) => maj({ p: q })} label="IPS projeté par province"
            lignes={ns.map((q) => { const r = Pv[q], k = r.v.length - 1; return { k: q, v: r.v[k], bas: r.lo[k], haut: r.hi[k], couleur: couleur(r.statut), info: <><b>{q}</b><div>projeté {f2(r.v[k])} ({f2(r.lo[k])} à {f2(r.hi[k])})</div><div>{r.statut}</div></> }; })} /></div></section>
      </div>
      <section className="carte-bloc"><h3>Fiabilité : quatre modèles testés sur le passé</h3>
        <Tableau entetes={['Modèle', 'Erreur moyenne à 1 an', 'à 2 ans', 'à 3 ans', 'Retenu']}
          lignes={mods.map((md) => [LIBM[md] ?? md, ...[1, 2, 3].map((h) => f3(bt.find((b) => b.modele === md && b.horizon === h)?.mae ?? null)), md === ret ? <b>oui</b> : ''])} />
        <p className="note">On se place en 2019, en 2020 puis en 2021, on prévoit les années suivantes avec les seules données antérieures et on mesure l'erreur. Le modèle retenu est celui qui se trompe le moins.</p></section>
    </div>
  );
}
