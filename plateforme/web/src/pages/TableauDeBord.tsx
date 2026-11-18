import { useEffect, useState } from 'react';
import { useApp } from '../contexte';
import { EnTete } from '../composants';
import { Icone } from '../icones';
import { Carte, Classement, Courbes, Degrade, Halteres, Tableau } from '../graphiques';
import { couleurIps, f2, f3, pc, signe, ya, type Num } from '../lib';

const NOMS = { pri: 'Primaire', pre: 'Préscolaire', cp1: 'Nouveaux inscrits au CP1' } as const;

export default function TableauDeBord() {
  const { D, P, e, maj } = useApp();
  const [lecture, setLecture] = useState(false);
  const [survol, setSurvol] = useState('');
  const [ind, setInd] = useState('tbs_primaire');
  const i = D.years.indexOf(e.a), serie = D[e.niv], nat: Num[] = D.nat[e.niv], an = ya(e.a);
  useEffect(() => {
    if (!lecture) return;
    const t = setInterval(() => { const j = D.years.indexOf(e.a); if (j >= D.years.length - 1) { setLecture(false); return; } maj({ a: D.years[j + 1] }); }, 900);
    return () => clearInterval(t);
  }, [lecture, e.a, D.years, maj]);
  const rows = (D.regions as string[]).map((r) => ({ k: r, v: serie[r][i] as Num })).filter((o) => o.v != null).sort((a, b) => (a.v as number) - (b.v as number));
  const lo = rows[0], hi = rows.at(-1), sous = rows.filter((o) => (o.v as number) < 0.97).length;
  const gap = (j: number) => (D.mil.urbain[j] != null && D.mil.rural[j] != null ? D.mil.urbain[j] - D.mil.rural[j] : null);
  const choisir = (r: string) => maj({ r: r === e.r ? '' : r });
  const A = D.acc?.[ind], z = A?.z;
  const acc = z ? [...(D.regions as string[]).filter((r) => z[r]?.t[i] != null).sort((a, b) => z[a].t[i] - z[b].t[i]), 'National'] : [];
  const mx = z ? Math.max(120, ...acc.flatMap((r) => [z[r].g[i], z[r].f[i]]).filter((v: Num) => v != null)) : 120;

  return (
    <div className="page">
      <EnTete titre="Tableau de bord par région" sousTitre={<>IPS = filles ÷ garçons. 1,00 = parité ; sous 1, moins de filles ; au-dessus de 1, plus de filles. Lancez la lecture pour voir dix ans d'évolution.</>} />
      <div className="commandes">
        <label>Niveau<select value={e.niv} onChange={(x) => maj({ niv: x.target.value as never })}>{Object.entries(NOMS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        <label className="curseur">Année scolaire : <b>{an}</b>
          <span className="ligne"><button type="button" className="bouton petit" onClick={() => { if (i >= D.years.length - 1) maj({ a: D.years[0] }); setLecture((l) => !l); }} aria-label={lecture ? 'Pause' : 'Lire'}>{lecture ? <><Icone nom="pause" taille={16} />Pause</> : <><Icone nom="lecture" taille={16} />Lire</>}</button>
            <input type="range" min={0} max={D.years.length - 1} value={i} onChange={(x) => { setLecture(false); maj({ a: D.years[+x.target.value] }); }} /></span></label>
        <label>Région<select value={e.r} onChange={(x) => maj({ r: x.target.value })}><option value="">Toutes (national)</option>{(D.regions as string[]).map((r) => <option key={r}>{r}</option>)}</select></label>
      </div>
      <div className="kpis">
        <div className="kpi"><b>{f2(nat[i])}</b><span>IPS national, {NOMS[e.niv].toLowerCase()}, {an} ({ya(D.years[0])} : {f2(nat[0])})</span></div>
        <div className="kpi"><b>{f3(gap(i))}</b><span>écart d'IPS entre ville et campagne, primaire ({ya(D.years[0])} : {f3(gap(0))})</span></div>
        <div className={`kpi ${sous ? 'alerte' : 'ok'}`}><b>{sous} / {rows.length}</b><span>régions sous 0,97</span></div>
        <div className="kpi alerte"><b>{lo?.k}</b><span>région la plus basse : IPS {f2(lo?.v)}</span></div>
      </div>
      <div className="message">En {an}, l'IPS national ({NOMS[e.niv].toLowerCase()}) est de {f2(nat[i])}. La région la plus éloignée de la parité est {lo?.k} ({f2(lo?.v)}), la plus haute {hi?.k} ({f2(hi?.v)}).
        {e.r && ` ${e.r} : ${f2(serie[e.r][i])}, ${serie[e.r][i] >= (nat[i] ?? 0) ? 'au-dessus' : 'en dessous'} de la moyenne nationale.`}</div>
      <div className="grille">
        <section className="carte-bloc"><h3>{NOMS[e.niv]} {an} : IPS par ancienne région</h3>
          <Carte geo={D.geo.map((g: any) => ({ name: g.region, d: g.d }))} vb={D.vb} label="Carte des 13 anciennes régions" sel={e.r} survol={survol} setSurvol={setSurvol} onPick={choisir}
            fill={(r) => couleurIps(P, serie[r][i])}
            info={(r) => <><b>{r}</b><div>IPS {f2(serie[r][i])}</div><div>depuis {ya(D.years[0])} : {serie[r][i] != null && serie[r][0] != null ? signe(serie[r][i] - serie[r][0], f2) : 'n.d.'}</div></>} />
          <Degrade couleurs={[couleurIps(P, 0.85), couleurIps(P, 1), couleurIps(P, 1.15)]} libs={['0,85 moins de filles', '1,00', '1,15 plus de filles']} />
          <p className="note">Cliquer une région pour la comparer au national.</p></section>
        <section className="carte-bloc"><h3>Classement des régions, {an}</h3>
          <Classement lignes={[...rows].reverse()} lo={0.85} hi={1.15} ref={1} fmt={f2} couleur={(v) => (v < 1 ? P.dlow : P.dhigh)} sel={e.r} survol={survol} setSurvol={setSurvol} onPick={choisir}
            ticks={[0.85, 0.9, 0.95, 1, 1.05, 1.1, 1.15]} label="Classement des régions par IPS" />
          <p className="note">Barres ancrées sur la parité (1,00).</p></section>
        <section className="carte-bloc"><h3>{NOMS[e.niv]} : évolution de l'IPS</h3>
          <Courbes labels={D.years.map(ya)} label="Évolution de l'IPS" series={[{ nom: 'National', couleur: P.s1, vals: nat }, ...(e.r ? [{ nom: e.r, couleur: P.s2, vals: serie[e.r] }] : [])]} /></section>
        <section className="carte-bloc"><h3>Primaire : ville et campagne</h3>
          <Courbes labels={D.years.map(ya)} label="IPS urbain et rural" bande={[D.mil.urbain, D.mil.rural]} series={[{ nom: 'Urbain', couleur: P.s2, vals: D.mil.urbain }, { nom: 'Rural', couleur: P.s3, vals: D.mil.rural }]} />
          <p className="note">Données nationales ; l'écart est la zone entre les courbes.</p></section>
        <section className="carte-bloc"><h3>Primaire : public et privé</h3>
          <Courbes labels={D.years.map(ya)} label="IPS public et privé" series={[{ nom: 'Public', couleur: P.s1, vals: D.sta.public }, { nom: 'Privé', couleur: P.s2, vals: D.sta.prive }]} /></section>
        {z && <section className="carte-bloc"><h3>Accès : taux par région et par sexe, {an}</h3>
          <div className="commandes en-ligne"><label>Indicateur<select value={ind} onChange={(x) => setInd(x.target.value)}>{Object.entries<any>(D.acc).map(([k, v]) => <option key={k} value={k}>{v.lib}</option>)}</select></label></div>
          <div className="legende"><span><i className="carre rond" style={{ background: P.s1 }} />Garçons</span><span><i className="carre rond" style={{ background: P.s2 }} />Filles</span></div>
          <Halteres max={mx} sel={e.r || 'National'} onPick={(r) => r !== 'National' && choisir(r)} label="Taux par région et par sexe"
            lignes={acc.filter((r) => z[r].g[i] != null && z[r].f[i] != null).map((r) => ({ k: r, g: z[r].g[i], f: z[r].f[i], t: z[r].t[i], gras: r === 'National',
              info: <><b>{r}</b><div>Garçons {pc(z[r].g[i])} · Filles {pc(z[r].f[i])}</div><div>Écart {signe(z[r].f[i] - z[r].g[i], (v) => v.toFixed(1).replace('.', ','))} point</div></> }))} />
          <p className="note">{A.lib}. Chaque ligne relie le taux des garçons et celui des filles : sa position montre le niveau d'accès, sa longueur l'écart entre filles et garçons. L'écart entre régions dépasse de loin l'écart entre sexes.</p></section>}
      </div>
      <details className="details"><summary>Voir les données de {an} sous forme de tableau</summary>
        <Tableau entetes={['Ancienne région', `IPS ${an}`, `IPS ${ya(D.years[0])}`, 'Variation']}
          lignes={[...[...rows].reverse().map((o) => [o.k, f2(o.v), f2(serie[o.k][0]), serie[o.k][0] == null ? 'n.d.' : signe((o.v as number) - serie[o.k][0], f2)]),
            [<b>National</b>, f2(nat[i]), f2(nat[0]), nat[i] != null && nat[0] != null ? signe((nat[i] as number) - (nat[0] as number), f2) : 'n.d.']]} />
      </details>
    </div>
  );
}
