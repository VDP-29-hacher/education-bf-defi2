import { useMemo, useState } from 'react';
import { useApp } from '../contexte';
import { Icone } from '../icones';
import { Carte } from '../graphiques';
import { Bandeau, EnTete } from '../composants';
import { f2, f3, pc, pc1, priorites, ya, type Num } from '../lib';

export default function Accueil() {
  const { D, P, e, maj, ouvrir } = useApp();
  const [survol, setSurvol] = useState('');
  const N1 = D.years.length - 1, y0 = ya(D.years[0]), y1 = ya(D.years[N1]);
  const prio = useMemo(() => priorites(D, e.ips, e.acc), [D, e.ips, e.acc]);
  const pr: Record<string, number> = {}; prio.forEach((o) => (pr[o.province] = o.priorite));
  const p1 = prio.filter((o) => o.priorite === 1), p2 = prio.filter((o) => o.priorite === 2);

  const reps: { q: string; tag: [string, string]; big: string; txt: string; spark?: { v: Num[]; c: string; ref: number }; go: () => void; bt: string }[] = [];
  const phrases: string[] = [];
  const z = D.acc?.tbs_primaire?.z;
  if (z) {
    const rs = (D.regions as string[]).filter((r) => z[r]?.t[N1] != null).sort((a, b) => z[a].t[N1] - z[b].t[N1]), lo = rs[0], hi = rs.at(-1) as string;
    reps.push({ q: 'Où ?', tag: ['Écart territorial', 'alerte'], big: `${pc(z[lo].t[N1])} à ${pc(z[hi].t[N1])}`,
      txt: `Taux brut de scolarisation du primaire en ${y1} : ${lo} contre ${hi}. National : ${pc(z.National.t[N1])} (${pc(z.National.t[0])} en ${y0}).`,
      spark: { v: z.National.t, c: P.dlow, ref: 100 }, go: () => maj({ o: 'carte' }), bt: 'Voir la carte' });
    phrases.push(`Les écarts les plus grands sont territoriaux : ${pc(z[lo].t[N1])} d'enfants scolarisés au ${lo}, ${pc(z[hi].t[N1])} au ${hi}.`);
  }
  const n0 = D.nat.pri[0], n1 = D.nat.pri[N1], H = (n: string) => D.prov.hist[n][N1] as Num;
  const pire = (D.prov.names as string[]).filter((n) => H(n) != null).sort((a, b) => (H(a) as number) - (H(b) as number))[0];
  reps.push({ q: 'Filles-garçons', tag: n1 >= 0.97 ? ['Presque à parité', 'ok'] : ['Écart persistant', 'alerte'], big: `IPS ${f2(n1)}`,
    txt: `Au primaire en ${y1}, contre ${f2(n0)} en ${y0}. Province la plus éloignée : ${pire} (${f2(H(pire))}).`,
    spark: { v: D.nat.pri, c: P.s1, ref: 1 }, go: () => maj({ o: 'tdb' }), bt: "Voir l'évolution" });
  phrases.push(`L'écart filles-garçons se réduit au niveau national (IPS ${f2(n0)} → ${f2(n1)}) mais reste fort dans plusieurs provinces.`);
  const gap: Num[] = D.mil.urbain.map((u: Num, i: number) => (u != null && D.mil.rural[i] != null ? u - D.mil.rural[i] : null));
  const g1 = (gap[N1] ?? gap.filter((x) => x != null).at(-1)) as number, g0 = gap[0] as number;
  const ur = (D.prov.names as string[]).filter((n) => D.prov.ind[n].ecart_urbain_moins_rural > 0).length;
  reps.push({ q: 'Ville-campagne', tag: g1 < g0 ? ['Se resserre', 'ok'] : ["S'élargit", 'alerte'], big: `${f3(g1)} pt`,
    txt: `Écart d'IPS entre ville et campagne (${f3(g0)} en ${y0}). La parité est plus faible à la campagne dans ${ur} provinces sur ${D.prov.names.length}.`,
    spark: { v: gap, c: P.s3, ref: 0 }, go: () => maj({ o: 'carte', m: 'ecart_urbain_moins_rural' }), bt: 'Voir par province' });
  phrases.push(`Entre ville et campagne, l'écart se resserre (${f3(g0)} → ${f3(g1)}), mais la campagne reste en retard presque partout.`);
  const Pv = D.prov.prev ?? {}, sous = Object.keys(Pv).filter((n) => /^sous/.test(Pv[n].statut)), an = D.prov.prevAns ? ya(D.prov.prevAns.at(-1)) : '';
  if (an) {
    reps.push({ q: 'Et demain ?', tag: ['Projection', 'alerte'], big: `${sous.length} provinces`, txt: `resteraient sous un IPS de 0,95 en ${an} si rien ne change, même dans le scénario haut.`,
      go: () => maj({ o: 'prevision' }), bt: 'Voir la prévision' });
    phrases.push(`Sans action, ${sous.length} provinces resteraient loin de la parité en ${an}.`);
  }

  return (
    <div className="page">
      <EnTete titre="Vue d'ensemble de l'accès à l'école" sousTitre="Où les écarts d'accès à l'école sont-ils les plus grands, entre filles et garçons et entre ville et campagne, et comment évoluent-ils ?" />
      <Bandeau />
      <section className="reponse-bref"><span className="rond-icone bleu"><Icone nom="ampoule" taille={24} /></span><div><b>La réponse en bref</b><p>{phrases.join(' ')}</p></div></section>
      <div className="grille">
        <section className="carte-bloc">
          <h3>Où agir d'abord</h3>
          <div className="legende"><span><i className="carre" style={{ background: P.dlow }} />Priorité 1 : peu de filles et élèves perdus</span>
            <span><i className="carre" style={{ background: P.s2 }} />Priorité 2 : un des deux</span><span><i className="carre" style={{ background: P.grid }} />Hors priorité</span></div>
          <Carte geo={D.prov.geo} vb={D.prov.vb} label="Carte des provinces prioritaires" survol={survol} setSurvol={setSurvol} onPick={(n) => ouvrir(n)}
            fill={(n) => (pr[n] === 1 ? P.dlow : pr[n] === 2 ? P.s2 : P.grid)}
            info={(n) => <><b>{n}</b> ({D.prov.ind[n].region})<div>{pr[n] ? `Priorité ${pr[n]}` : 'Hors priorité'}</div>
              <div>IPS {f2(H(n))} · effectifs {pc1(D.prov.ind[n].effectif_dernier_sur_max)} du maximum</div><div className="sub">Cliquer pour la fiche</div></>} />
          <p className="note">Seuils : IPS sous {f2(e.ips)} et effectifs sous {pc1(e.acc)} de la meilleure année (réglables dans l'aide à la décision). Cliquer une province ouvre sa fiche.</p>
        </section>
        <div className="pile">
          <section className="carte-bloc">
            <h3>Provinces en priorité</h3>
            <div className="puces">
              {p1.map((o) => <button key={o.province} type="button" className={`puce p1 ${survol === o.province ? 'hl' : ''}`} onMouseEnter={() => setSurvol(o.province)} onMouseLeave={() => setSurvol('')} onClick={() => ouvrir(o.province)}>{o.province}</button>)}
              {p2.map((o) => <button key={o.province} type="button" className={`puce p2 ${survol === o.province ? 'hl' : ''}`} onMouseEnter={() => setSurvol(o.province)} onMouseLeave={() => setSurvol('')} onClick={() => ouvrir(o.province)}>{o.province}</button>)}
            </div>
            <p className="note">En plein, les {p1.length} provinces en priorité 1 ; en contour, les {p2.length} en priorité 2. Survoler une province la montre sur la carte.</p>
          </section>
          <section className="carte-bloc">
            <h3>Comment utiliser l'outil</h3>
            <ol className="guide">
              {[['analyse', 'Analyse', 'Les constats chiffrés, les liens entre les écarts et les profils de provinces.'],
                ['tdb', 'Tableau de bord', `La parité et l'accès par région, année par année (${D.meta.periode}).`],
                ['carte', 'Carte', 'Les 17 régions actuelles et les 45 provinces, selon la mesure choisie.'],
                ['decision', 'Aide à la décision', 'Réglez deux seuils : la liste des provinces à cibler et leur fiche se mettent à jour.'],
                ['prevision', 'Prévision', `L'IPS de chaque province d'ici ${an}, avec sa marge d'erreur.`]].map(([o, t, d]) => (
                <li key={o}><button type="button" onClick={() => maj({ o: o as never })}><b>{t}</b><span>{d}</span></button></li>))}
            </ol>
          </section>
        </div>
      </div>
      <section className="carte-bloc">
        <h3>À qui sert cet outil</h3>
        <div className="grille3">
          <div className="usage"><h4>Ministère et DGESS</h4><p>Choisir les provinces où rouvrir des classes et soutenir la scolarisation des filles, avec une règle transparente et réglable.</p></div>
          <div className="usage"><h4>Directions régionales</h4><p>Imprimer la fiche d'une province : effectifs perdus, parité en ville et à la campagne, projection, filles à inscrire.</p></div>
          <div className="usage"><h4>Partenaires et ONG</h4><p>Repérer les zones où les écarts se cumulent (accès faible et peu de filles) et suivre leur évolution chaque année.</p></div>
        </div>
      </section>
    </div>
  );
}
