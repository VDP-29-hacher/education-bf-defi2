import { useEffect, useMemo, useState } from 'react';
import { useApp } from '../contexte';
import { EnTete } from '../composants';
import { Icone } from '../icones';
import { Carte, Mini } from '../graphiques';
import { f2, nbf, pc, pc1, priorites, ya, type Num, type Priorite } from '../lib';

export default function Decision() {
  const { D, P, e, maj, source } = useApp();
  const local = useMemo(() => priorites(D, e.ips, e.acc), [D, e.ips, e.acc]);
  const [liste, setListe] = useState<Priorite[]>(local);
  const [origine, setOrigine] = useState<'api' | 'navigateur'>('navigateur');
  useEffect(() => {
    setListe(local); setOrigine('navigateur');
    if (source !== 'api') return;
    const ctl = new AbortController(), t = setTimeout(() => {
      fetch(`api/priorites?ips=${e.ips}&acces=${e.acc}`, { signal: ctl.signal }).then((r) => (r.ok ? r.json() : Promise.reject()))
        .then((j) => { setListe(j.provinces); setOrigine('api'); }).catch(() => { /* on garde le calcul local */ });
    }, 120);
    return () => { clearTimeout(t); ctl.abort(); };
  }, [local, source, e.ips, e.acc]);
  const N1 = D.years.length - 1, I = D.prov.ind, n = e.p, i = I[n], p1 = liste.filter((o) => o.priorite === 1);
  const som = (k: 'elevesPerdus' | 'fillesAInscrire') => p1.reduce((t, o) => t + ((o[k] as number) || 0), 0);
  const pr: Record<string, number> = {}; liste.forEach((o) => (pr[o.province] = o.priorite));
  const pv = D.prov.prev?.[n], k = pv ? pv.v.length - 1 : 0, sig = (D.prov.sig ?? []).filter((s: any) => s.province === n);
  const ty = (D.typo?.rows ?? []).find((x: any) => x.p === n), tb = (D.ptbs?.rows ?? []).find((x: any) => x.p === n);
  const moy = (c: string) => { const v = (D.prov.names as string[]).map((x) => I[x][c]).filter((x: Num) => x != null); return v.reduce((a: number, b: number) => a + b, 0) / v.length; };
  const lignesFiche: [string, string, string][] = [
    ['Priorité avec les seuils choisis', pr[n] ? String(pr[n]) : 'hors priorité', ''],
    ['Effectifs / meilleure année depuis 2015', pc1(i.effectif_dernier_sur_max), pc1(moy('effectif_dernier_sur_max'))],
    ['Élèves en moins', nbf(i.eleves_perdus_depuis_max), ''],
    [`IPS ${ya(D.years[N1])}`, f2(D.prov.hist[n][N1]), f2(D.nat.pri[N1])],
    ['IPS en ville / à la campagne', `${f2(i.ips_urbain)} / ${f2(i.ips_rural)}`, ''],
    ['Filles à inscrire pour la parité', nbf(i.filles_manquantes_parite), ''],
    ...(tb ? [['Taux brut de scolarisation (INSD)', pc(tb.t), D.acc?.tbs_primaire ? pc(D.acc.tbs_primaire.z.National.t[N1]) : '']] as [string, string, string][] : []),
    ...(ty ? [['Profil', `${ty.g}. ${ty.nom}`, '']] as [string, string, string][] : []),
    [`Projection ${D.prov.prevAns ? ya(D.prov.prevAns.at(-1)) : ''}`, pv && pv.v[k] != null ? `${f2(pv.v[k])} (entre ${f2(pv.lo[k])} et ${f2(pv.hi[k])})` : 'n.d.', ''],
  ];
  const imprimer = () => {
    const w = window.open('', '_blank'); if (!w) { window.print(); return; }
    const t = lignesFiche.map(([a, b, c]) => `<tr><td>${a}</td><td>${b}</td><td>${c}</td></tr>`).join('');
    w.document.write(`<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Fiche ${n}</title><style>body{font:14px/1.5 "Segoe UI",system-ui,sans-serif;margin:28px;max-width:760px;color:#111}
      h1{font-size:1.35rem;margin:0 0 4px}table{border-collapse:collapse;width:100%;margin-top:12px}td,th{border-bottom:1px solid #ddd;padding:6px 8px;text-align:right}td:first-child,th:first-child{text-align:left}
      th{font-size:.75rem;text-transform:uppercase;color:#666}.sub{color:#555;font-size:.8rem}.g{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:14px}svg{width:100%;height:auto}</style></head><body>
      <p class="sub">Data Challenge Burkina 2026 · Défi 2 · Équipe ${D.meta.equipe} · primaire ${ya(D.years[N1])}</p><h1>Fiche : ${n} (ancienne région ${i.region})</h1>
      <table><thead><tr><th>Indicateur</th><th>${n}</th><th>Repère</th></tr></thead><tbody>${t}</tbody></table>
      <div class="g">${document.getElementById('fiche-mini')?.innerHTML ?? ''}</div>
      <p class="sub" style="margin-top:18px">Seuils : IPS sous ${f2(e.ips)}, effectifs sous ${pc1(e.acc)} du maximum. Repère : moyenne des 45 provinces ou valeur nationale. Sources : DGESS, INSD. Un écart ne dit pas sa cause.</p></body></html>`);
    w.document.close(); w.focus(); setTimeout(() => w.print(), 300);
  };

  return (
    <div className="page">
      <EnTete titre="Aide à la décision" sousTitre={<>Réglez les deux seuils : la liste, la carte et les chiffres se mettent à jour. Cliquez une province pour afficher sa fiche, prête à imprimer.</>} />
      <div className="grille">
        <section className="carte-bloc">
          <h3>Simulateur de ciblage</h3>
          <div className="commandes interne">
            <label className="curseur">IPS sous : <b>{f2(e.ips)}</b><input type="range" min={0.85} max={1} step={0.01} value={e.ips} onChange={(x) => maj({ ips: +x.target.value })} /></label>
            <label className="curseur">Effectifs sous : <b>{pc1(e.acc)}</b> du maximum<input type="range" min={0.3} max={0.9} step={0.05} value={e.acc} onChange={(x) => maj({ acc: +x.target.value })} /></label>
            <button type="button" className="bouton petit fantome" onClick={() => maj({ ips: 0.95, acc: 0.6 })}>Règle du dossier</button>
          </div>
          <div className="message"><b>{p1.length}</b> province{p1.length > 1 ? 's' : ''} en priorité 1 et <b>{liste.length - p1.length}</b> en priorité 2.
            {p1.length ? <> Priorité 1 : <b>{nbf(som('elevesPerdus'))}</b> élèves perdus depuis leur meilleure année, <b>{nbf(som('fillesAInscrire'))}</b> filles à inscrire pour la parité.</> : ' Aucune province ne franchit les deux seuils à la fois.'}
            <span className={`etiquette ${origine === 'api' ? 'ok' : 'neutre'}`} style={{ marginLeft: 8 }}>{origine === 'api' ? 'calculé par l’API NestJS' : 'calculé dans le navigateur'}</span></div>
          <div className="defile court"><table className="cliquable">
            <thead><tr><th className="g">Province</th><th>Prio.</th><th>IPS</th><th>Effectifs</th><th>Élèves perdus</th></tr></thead>
            <tbody>{liste.map((o) => (
              <tr key={o.province} className={o.province === n ? 'choisi' : ''} onClick={() => maj({ p: o.province })} tabIndex={0} onKeyDown={(x) => { if (x.key === 'Enter') maj({ p: o.province }); }}>
                <td className="g"><i className="carre" style={{ background: o.priorite === 1 ? P.dlow : P.s2 }} />{o.province} <span className="sub">({o.region})</span></td>
                <td>{o.priorite}</td><td>{f2(o.ips)}</td><td>{pc1(o.effectifsSurMax)}</td><td>{nbf(o.elevesPerdus)}</td></tr>))}</tbody>
          </table></div>
          <p className="note">Priorité 1 = les deux seuils franchis ; priorité 2 = un seul. Réglages par défaut (0,95 et 60 %) = règle du dossier.</p>
        </section>
        <div className="pile">
          <section className="carte-bloc">
            <div className="titre-ligne"><h3>Fiche : {n} <span className="sub">(ancienne région {i.region})</span></h3><button type="button" className="bouton petit fantome" onClick={imprimer}><Icone nom="imprimer" taille={16} />Imprimer la fiche</button></div>
            <table><thead><tr><th className="g">Indicateur</th><th>{n}</th><th>Repère</th></tr></thead>
              <tbody>{lignesFiche.map(([a, b, c]) => <tr key={a}><td className="g">{a}</td><td><b>{b}</b></td><td className="sub">{c}</td></tr>)}</tbody></table>
            <div className="grille serre" id="fiche-mini">
              <div><p className="note">IPS, {ya(D.years[0])} → {ya(D.years[N1])} (pointillé : parité)</p><Mini vals={D.prov.hist[n]} couleur={P.s1} ref={1} /></div>
              {D.prov.eff?.[n] && <div><p className="note">Élèves en % de la meilleure année</p><Mini vals={D.prov.eff[n]} couleur={P.dlow} ref={1} /></div>}
            </div>
            {sig.length > 0 && <p className="note">IPS non interprétable en {sig.map((s: any) => ya(s.annee_debut)).join(', ')} : effectif effondré.</p>}
            <p className="note">Repère : moyenne des 45 provinces (effectifs) ou valeur nationale (IPS, TBS).</p>
          </section>
          <section className="carte-bloc"><h3>Carte des priorités</h3>
            <Carte geo={D.prov.geo} vb={D.prov.vb} label="Carte des provinces prioritaires" sel={n} onPick={(x) => maj({ p: x })} fill={(x) => (pr[x] === 1 ? P.dlow : pr[x] === 2 ? P.s2 : P.grid)}
              info={(x) => <><b>{x}</b><div>{pr[x] ? `Priorité ${pr[x]}` : 'Hors priorité'}</div></>} />
            <p className="note">Rouge : priorité 1 ; orange : priorité 2 ; gris : hors priorité, avec les seuils choisis.</p></section>
        </div>
      </div>
    </div>
  );
}
