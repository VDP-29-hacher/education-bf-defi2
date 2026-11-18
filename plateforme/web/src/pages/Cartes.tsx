import { useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useApp } from '../contexte';
import { Bandeau, EnTete } from '../composants';
import { Classement, Courbes, Degrade, Carte as CarteSimple } from '../graphiques';
import { Icone } from '../icones';
import { couleurAcces, couleurIps, f2, f3, nbf, pc, pc1, priorites, PROFILS, ya, type Num, type Palette } from '../lib';

/* ---- classes de la carte : regle du dossier (P1, P2) puis deux classes de lecture pour le reste ---- */
const CLASSES = [
  { id: 1, lib: 'Priorité 1', regle: 'IPS sous le seuil et effectifs sous le seuil', c: '#d93a34' },
  { id: 2, lib: 'Priorité 2', regle: 'un seul des deux seuils franchi', c: '#f08a24' },
  { id: 3, lib: 'À surveiller', regle: 'IPS < 0,98 ou effectifs < 85 % du maximum', c: '#f2c230' },
  { id: 4, lib: 'Bonne situation', regle: 'IPS ≥ 0,98 et effectifs ≥ 85 %', c: '#43a047' },
];
const INDICATEURS: Record<string, string> = {
  priorite: 'Niveau de priorité', ips: 'Indice de parité (IPS)', acces: 'Accès : effectifs / meilleure année', tbs: 'Taux brut de scolarisation (INSD)',
  ecart: 'Écart entre ville et campagne', profil: 'Profil de province',
};

function echelle(P: Palette, m: string) {
  if (m === 'acces') return { col: (v: Num) => couleurAcces(P, v), leg: [couleurAcces(P, 0.2), couleurAcces(P, 0.6), couleurAcces(P, 1)], libs: ['20 %', '60 %', '100 % du max.'] };
  if (m === 'tbs') return { col: (v: Num) => couleurAcces(P, v == null ? null : Math.min(1, v / 100)), leg: [couleurAcces(P, 0.1), couleurAcces(P, 0.55), couleurAcces(P, 1)], libs: ['10 %', '55 %', '100 % et +'] };
  if (m === 'ecart') return { col: (v: Num) => couleurIps(P, v == null ? null : 1 - v), leg: [couleurIps(P, 0.85), couleurIps(P, 1), couleurIps(P, 1.15)], libs: ['campagne en retard', '0', 'en avance'] };
  return { col: (v: Num) => couleurIps(P, v), leg: [couleurIps(P, 0.85), couleurIps(P, 1), couleurIps(P, 1.15)], libs: ['0,85', '1,00', '1,15'] };
}

/** Pistes d'action deduites des chiffres de la province (regles simples et transparentes, pas une causalite). */
function pistes(ip: Num, acc: Num, ec: Num, tbs: Num, seuil: number): string[] {
  const p: string[] = [];
  if (acc != null && acc < 0.6) p.push("Rétablir l'offre scolaire : la province a perdu plus de 40 % de ses élèves (classes à rouvrir, accueil des élèves déplacés).");
  if (tbs != null && tbs < 60) p.push(`Créer des places : à peine ${Math.round(tbs)} % des enfants de 6 à 11 ans sont inscrits.`);
  if (ip != null && ip < seuil) p.push("Soutenir l'inscription et le maintien des filles (sensibilisation, cantines, kits scolaires).");
  if (ec != null && ec > 0.05) p.push('Cibler le milieu rural, où la parité est nettement plus faible qu’en ville.');
  if (!p.length) p.push('Situation proche de la parité : consolider et suivre chaque année.');
  return p;
}

export default function Cartes() {
  const { D, P, e, maj, ouvrir, tip } = useApp();
  const N1 = D.years.length - 1, I = D.prov.ind, ns: string[] = D.prov.names;
  const m = INDICATEURS[e.m] ? e.m : 'priorite', yi = Math.max(0, D.years.indexOf(e.a));
  const [vue, setVue] = useState<'carte' | 'tableau'>('carte');
  const [tri, setTri] = useState<{ k: string; asc: boolean }>({ k: 'classe', asc: true });
  const [survol, setSurvol] = useState('');
  const [plus, setPlus] = useState(false);
  const pr = useMemo(() => priorites(D, e.ips, e.acc), [D, e.ips, e.acc]);
  const PT: Record<string, any> = {}; (D.ptbs?.rows ?? []).forEach((x: any) => (PT[x.p] = x));
  const T: Record<string, any> = {}; (D.typo?.rows ?? []).forEach((x: any) => (T[x.p] = x));
  const prio: Record<string, number> = {}; pr.forEach((o) => (prio[o.province] = o.priorite));
  const ipsDe = (n: string) => D.prov.hist[n][yi] as Num;
  const classe = (n: string) => {
    if (prio[n]) return prio[n];
    const ip = D.prov.hist[n][N1] as Num, acc = I[n].effectif_dernier_sur_max as Num;
    return (ip != null && ip < 0.98) || (acc != null && acc < 0.85) ? 3 : 4;
  };
  const valeur = (n: string): Num => (m === 'ips' ? ipsDe(n) : m === 'acces' ? I[n].effectif_dernier_sur_max : m === 'tbs' ? PT[n]?.t ?? null : m === 'ecart' ? I[n].ecart_urbain_moins_rural : null);
  const E = echelle(P, m);
  const fill = (n: string) => (m === 'priorite' ? CLASSES[classe(n) - 1].c : m === 'profil' ? (T[n] ? PROFILS[(T[n].g - 1) % 5] : P.grid) : E.col(valeur(n)));
  const p = e.p, ip = D.prov.hist[p][N1] as Num, cl = classe(p), tb: Num = PT[p]?.t ?? null;
  const toutes = pistes(ip, I[p].effectif_dernier_sur_max, I[p].ecart_urbain_moins_rural, tb, e.ips);
  const comptes = CLASSES.map((c) => ns.filter((n) => classe(n) === c.id).length);
  const liste = pr.slice(0, 8);
  const infos = (n: string) => <><b>{n}</b> <span className="sub">({I[n].region})</span>
    <div>{CLASSES[classe(n) - 1].lib}</div><div>IPS {f2(ipsDe(n))} · accès {pc1(I[n].effectif_dernier_sur_max)}{PT[n] ? ` · TBS ${pc(PT[n].t)}` : ''}</div></>;

  const lignesTab = ns.map((n) => ({ n, r: I[n].region as string, classe: classe(n), ips: D.prov.hist[n][N1] as Num, acces: I[n].effectif_dernier_sur_max as Num, tbs: (PT[n]?.t ?? null) as Num, ecart: I[n].ecart_urbain_moins_rural as Num }))
    .sort((a: any, b: any) => { const x = a[tri.k], y = b[tri.k]; const c = typeof x === 'string' ? x.localeCompare(y, 'fr') : (x ?? 99) - (y ?? 99); return tri.asc ? c : -c; });
  const entete = (k: string, lib: string, g = false) => <th className={g ? 'g' : ''}><button type="button" className="tri" onClick={() => setTri((t) => ({ k, asc: t.k === k ? !t.asc : true }))}>{lib}{tri.k === k ? (tri.asc ? ' ▲' : ' ▼') : ''}</button></th>;

  return (
    <div className="page">
      <EnTete titre="Exploration géographique" sousTitre={`Analysez l'accès à l'école à l'échelle des ${ns.length} provinces du Burkina Faso (primaire, ${ya(D.years[N1])}).`} />
      <Bandeau />
      <div className="geo-grille">
        <section className="carte-bloc geo-carte">
          <h3>Carte des provinces : {INDICATEURS[m]}</h3>
          <div className="filtres">
            <label><span>Année scolaire</span><span className="champ"><Icone nom="calendrier" taille={17} />
              <select value={e.a} onChange={(x) => maj({ a: +x.target.value })} disabled={m !== 'ips'} title={m !== 'ips' ? "Seul l'IPS existe pour chaque année" : ''}>
                {(D.years as number[]).map((y) => <option key={y} value={y}>{ya(y)}</option>)}</select></span></label>
            <label><span>Indicateur</span><span className="champ"><Icone nom="analyse" taille={17} />
              <select value={m} onChange={(x) => maj({ m: x.target.value })}>{Object.entries(INDICATEURS).filter(([k]) => (k !== 'tbs' || D.ptbs) && (k !== 'profil' || D.typo)).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></span></label>
            <label><span>Région</span><span className="champ"><Icone nom="repere" taille={17} />
              <select value={e.r} onChange={(x) => maj({ r: x.target.value })}><option value="">Toutes les régions</option>{(D.regions as string[]).map((r) => <option key={r}>{r}</option>)}</select></span></label>
            <div className="bascule" role="group" aria-label="Affichage">
              <button type="button" aria-pressed={vue === 'carte'} onClick={() => setVue('carte')}><Icone nom="carte" taille={17} />Carte</button>
              <button type="button" aria-pressed={vue === 'tableau'} onClick={() => setVue('tableau')}><Icone nom="grille" taille={17} />Tableau</button>
            </div>
          </div>
          {vue === 'carte' ? (
            <div className="geo-zone">
              <CarteZoom geo={D.prov.geo} vb={D.prov.vb} fill={fill} sel={p} survol={survol} setSurvol={setSurvol} attenuer={(n) => !!e.r && I[n].region !== e.r}
                onPick={(n) => maj({ p: n })} info={infos} etiquette={<><b>{p}</b><span>IPS : {f2(ip)}</span><span>Accès : {pc1(I[p].effectif_dernier_sur_max)}</span></>} />
              <div className="legende-carte">
                {m === 'priorite' ? <><b>Niveau de priorité</b>{CLASSES.map((c, i) => (
                  <div key={c.id} className="leg-ligne"><i style={{ background: c.c }} /><div><span>{c.lib} ({comptes[i]})</span><small>{c.id === 1 ? `IPS < ${f2(e.ips)} et effectifs < ${pc1(e.acc)}` : c.regle}</small></div></div>))}</>
                  : m === 'profil' ? <><b>Profils</b>{[...new Map<number, string>((D.typo.rows as any[]).map((x) => [x.g, x.nom])).entries()].sort((a, b) => a[0] - b[0]).map(([g, nom]) => (
                    <div key={g} className="leg-ligne"><i style={{ background: PROFILS[(g - 1) % 5] }} /><div><span>{g}. {nom}</span></div></div>))}</>
                  : <><b>{INDICATEURS[m]}{m === 'ips' ? ` · ${ya(D.years[yi])}` : ''}</b><Degrade couleurs={E.leg} libs={E.libs} /></>}
              </div>
            </div>
          ) : (
            <div className="defile geo-tableau"><table className="cliquable">
              <thead><tr>{entete('n', 'Province', true)}{entete('r', 'Ancienne région', true)}{entete('classe', 'Niveau')}{entete('ips', 'IPS')}{entete('acces', 'Accès')}{D.ptbs && entete('tbs', 'TBS')}{entete('ecart', 'Écart V-C')}</tr></thead>
              <tbody>{lignesTab.map((l) => (
                <tr key={l.n} className={l.n === p ? 'choisi' : ''} onClick={() => maj({ p: l.n })} tabIndex={0} onKeyDown={(x) => { if (x.key === 'Enter') maj({ p: l.n }); }}>
                  <td className="g">{l.n}</td><td className="g sub">{l.r}</td>
                  <td><span className="pastille-texte" style={{ background: CLASSES[l.classe - 1].c }}>{l.classe <= 2 ? `P${l.classe}` : CLASSES[l.classe - 1].lib}</span></td>
                  <td>{f2(l.ips)}</td><td>{pc1(l.acces)}</td>{D.ptbs && <td>{pc(l.tbs)}</td>}<td>{f3(l.ecart)}</td></tr>))}</tbody>
            </table></div>
          )}
        </section>

        <section className="carte-bloc geo-fiche">
          <h3>Province sélectionnée</h3>
          <div className="fiche-bandeau" style={{ background: `linear-gradient(120deg, ${CLASSES[cl - 1].c}, ${CLASSES[cl - 1].c}c0)` }}>
            <Icone nom="repere" taille={30} />
            <div><b>{p}</b><span>Région : {I[p].region}</span><span className="fiche-niveau">{CLASSES[cl - 1].lib}</span></div>
          </div>
          <ul className="fiche-lignes">
            {tb != null && <li><Icone nom="groupe" taille={19} /><span>Taux brut de scolarisation</span><b className={tb < 60 ? 'rouge' : tb < 90 ? 'orange' : 'vert'}>{pc(tb)}</b></li>}
            <li><Icone nom="diplome" taille={19} /><span>Indice de parité (IPS)</span><b className={ip != null && ip < e.ips ? 'rouge' : ip != null && ip < 0.98 ? 'orange' : 'vert'}>{f2(ip)}</b></li>
            <li><Icone nom="ecole" taille={19} /><span>Écart entre ville et campagne</span><b>{f3(I[p].ecart_urbain_moins_rural)} pt</b></li>
            <li><Icone nom="prevision" taille={19} /><span>Effectifs / meilleure année</span><b className={I[p].effectif_dernier_sur_max < e.acc ? 'rouge' : 'vert'}>{pc1(I[p].effectif_dernier_sur_max)}</b></li>
            <li><Icone nom="groupe" taille={19} /><span>Élèves perdus</span><b>{nbf(I[p].eleves_perdus_depuis_max)}</b></li>
            <li><Icone nom="diplome" taille={19} /><span>Filles à inscrire (parité)</span><b>{nbf(I[p].filles_manquantes_parite)}</b></li>
          </ul>
          <div className="recommandation">
            <Icone nom="cible" taille={24} />
            <div><b>Pistes d'action</b>
              <ul>{toutes.slice(0, plus ? 9 : 2).map((x) => <li key={x}>{x}</li>)}</ul>
              {toutes.length > 2 && <button type="button" className="lien" onClick={() => setPlus((v) => !v)}>{plus ? 'Moins de pistes' : `${toutes.length - 2} autre${toutes.length > 3 ? 's' : ''} piste${toutes.length > 3 ? 's' : ''}`}</button>}
              <small>Déduites des chiffres de la province ; elles ne disent pas la cause des écarts.</small></div>
          </div>
          <button type="button" className="bouton fantome large" onClick={() => ouvrir(p, 'decision')}><Icone nom="fiche" taille={18} />Fiche complète et impression</button>
        </section>

        <section className="carte-bloc geo-liste">
          <h3>Provinces prioritaires <span className="sub">(IPS croissant)</span></h3>
          <table className="cliquable classement">
            <thead><tr><th className="g">Rang</th><th className="g">Province</th><th>IPS</th>{D.ptbs && <th>TBS</th>}<th>Priorité</th></tr></thead>
            <tbody>{liste.map((o, i) => (
              <tr key={o.province} className={o.province === p ? 'choisi' : ''} onClick={() => maj({ p: o.province })} onMouseEnter={() => setSurvol(o.province)} onMouseLeave={() => setSurvol('')}>
                <td className="g"><span className={`rang p${o.priorite}`}>{i + 1}</span></td><td className="g">{o.province}</td>
                <td className="rouge">{f2(o.ips)}</td>{D.ptbs && <td>{pc(PT[o.province]?.t ?? null)}</td>}
                <td><span className={`pill p${o.priorite}`}>P{o.priorite}</span></td></tr>))}</tbody>
          </table>
          <button type="button" className="bouton fantome large" onClick={() => { setVue('tableau'); window.scrollTo({ top: 300, behavior: 'smooth' }); }}>Voir les {ns.length} provinces<Icone nom="fleche" taille={17} /></button>
        </section>
      </div>

      <section className="synthese">
        <div className="synthese-titre"><span className="carre-icone"><Icone nom="analyse" taille={26} /></span><div><b>Synthèse géographique</b><span>Principaux constats sur les {ns.length} provinces</span></div></div>
        {[{ i: 'cible', c: 'rouge', n: comptes[0], t: 'provinces en priorité 1', d: 'Peu de filles et élèves perdus à la fois.' },
          { i: 'couches', c: 'orange', n: comptes[1], t: 'provinces en priorité 2', d: 'Un des deux seuils est franchi.' },
          { i: 'coche', c: 'vert', n: comptes[2] + comptes[3], t: 'provinces hors priorité', d: `dont ${comptes[3]} en bonne situation (IPS ≥ 0,98, effectifs ≥ 85 %).` }].map((x) => (
          <div key={x.t} className="synthese-item" onMouseMove={(ev) => tip(ev, <>{x.d}</>)} onMouseLeave={() => tip(null)}>
            <span className={`rond-icone ${x.c}`}><Icone nom={x.i} taille={24} /></span><div><b>{x.n} {x.t}</b><span>{x.d}</span></div></div>))}
      </section>

      <Regions17 />
      <div className="grille">
        <section className="carte-bloc"><h3>{p} : IPS de {ya(D.years[0])} à {ya(D.years[N1])}</h3>
          <Courbes labels={D.years.map(ya)} label={`IPS de ${p}`} series={[{ nom: 'National', couleur: P.s1, vals: D.nat.pri }, { nom: p, couleur: P.s2, vals: D.prov.hist[p] }]} /></section>
        {D.prov.eff?.[p] && <section className="carte-bloc"><h3>{p} : élèves en % de la meilleure année</h3>
          <Courbes labels={D.years.map(ya)} pas={0.1} fmt={pc1} ref={null} label="Effectifs en part du maximum" series={[{ nom: 'Total 45 provinces', couleur: P.s1, vals: D.prov.effNat }, { nom: p, couleur: P.dlow, vals: D.prov.eff[p] }]} />
          <p className="note">100 % = meilleure année de la province depuis 2015. Une chute brutale signale une perte d'accès, le plus souvent des fermetures d'écoles.</p></section>}
      </div>
    </div>
  );
}

/** Carte avec zoom, recentrage, attenuation hors region et etiquette sur la province choisie. */
function CarteZoom({ geo, vb, fill, sel, survol, setSurvol, onPick, info, etiquette, attenuer }: {
  geo: { name: string; d: string }[]; vb: number[]; fill: (n: string) => string; sel: string; survol: string; setSurvol: (n: string) => void;
  onPick: (n: string) => void; info: (n: string) => ReactNode; etiquette: ReactNode; attenuer: (n: string) => boolean;
}) {
  const { tip } = useApp();
  const [z, setZ] = useState({ k: 1, x: vb[2] / 2, y: vb[3] / 2 });
  const boite = useRef<HTMLDivElement>(null), chemins = useRef<Record<string, SVGPathElement | null>>({});
  const [pos, setPos] = useState<{ x: number; y: number; g: boolean } | null>(null);
  const centre = (n: string) => { const b = chemins.current[n]?.getBBox(); return b ? { x: b.x + b.width / 2, y: b.y + b.height / 2 } : null; };
  const zoomer = (f: number) => setZ((s) => { const k = Math.max(1, Math.min(6, s.k * f)), c = k > 1 ? centre(sel) ?? s : { x: vb[2] / 2, y: vb[3] / 2 }; return { k, x: c.x, y: c.y }; });
  useLayoutEffect(() => {
    const maj = () => {
      const el = chemins.current[sel], b = boite.current;
      if (!el || !b) { setPos(null); return; }
      const r = el.getBoundingClientRect(), rb = b.getBoundingClientRect();
      setPos({ x: r.left - rb.left + r.width / 2, y: r.top - rb.top + r.height / 2, g: r.left - rb.left + r.width / 2 > rb.width - 150 });
    };
    maj(); const t = setTimeout(maj, 320);
    window.addEventListener('resize', maj); return () => { clearTimeout(t); window.removeEventListener('resize', maj); };
  }, [sel, z]);
  const tr = `translate(${vb[2] / 2} ${vb[3] / 2}) scale(${z.k}) translate(${-z.x} ${-z.y})`;
  return (
    <div className="carte-zoom" ref={boite}>
      <div className="zoom-boutons">
        <button type="button" onClick={() => zoomer(1.5)} aria-label="Zoomer" data-infobulle="Zoomer" className="infobulle-droite"><Icone nom="plus" taille={18} /></button>
        <button type="button" onClick={() => zoomer(1 / 1.5)} aria-label="Dézoomer" data-infobulle="Dézoomer" className="infobulle-droite"><Icone nom="moins" taille={18} /></button>
        <button type="button" onClick={() => setZ({ k: 1, x: vb[2] / 2, y: vb[3] / 2 })} aria-label="Recentrer" data-infobulle="Recentrer" className="infobulle-droite"><Icone nom="recentrer" taille={18} /></button>
      </div>
      <svg viewBox={vb.join(' ')} role="img" aria-label="Carte des provinces" className="carte">
        <g transform={tr}>
          {geo.map((g) => (
            <path key={g.name} ref={(el) => { chemins.current[g.name] = el; }} d={g.d} fill={fill(g.name)} className={g.name === survol ? 'hl' : ''}
              style={{ opacity: attenuer(g.name) ? 0.22 : 1, strokeWidth: 0.6 / z.k }} tabIndex={0} aria-label={g.name}
              onMouseMove={(ev) => { tip(ev, info(g.name)); setSurvol(g.name); }} onMouseLeave={() => { tip(null); setSurvol(''); }}
              onClick={() => onPick(g.name)} onKeyDown={(ev) => { if (ev.key === 'Enter') onPick(g.name); }} />
          ))}
          {geo.filter((g) => g.name === sel).map((g) => <path key="s" d={g.d} className="contour" style={{ strokeWidth: 2.4 / z.k }} pointerEvents="none" />)}
        </g>
      </svg>
      {pos && <div className={`etiquette-carte ${pos.g ? 'gauche' : ''}`} style={{ left: pos.x, top: pos.y }}><span className="punaise"><Icone nom="repere" taille={26} /></span><div className="bulle-fixe">{etiquette}</div></div>}
    </div>
  );
}

/** Les 17 regions actuelles (agregation exacte des provinces). */
function Regions17() {
  const { D, P, e, maj } = useApp();
  const [s17, setS17] = useState('');
  const R = D.r17; if (!R) return null;
  const MES: Record<string, string> = { effectif_dernier_sur_max: 'Accès : effectifs en % du maximum', ips: 'IPS, ensemble', ips_rural: 'IPS, milieu rural', ecart_urbain_moins_rural: "Écart d'IPS entre ville et campagne",
    eleves_perdus_depuis_max: 'Élèves perdus depuis la meilleure année', filles_manquantes_parite: 'Filles à inscrire pour la parité' };
  const m = MES[e.r17] ? e.r17 : 'effectif_dernier_sur_max', max = Math.max(1, ...Object.values<any>(R.ind).map((x) => x[m] ?? 0));
  const E = m === 'effectif_dernier_sur_max' ? { col: (v: Num) => couleurAcces(P, v), fmt: pc1, lo: 0, hi: 1, ref: 1, t: [0, 0.25, 0.5, 0.75, 1] }
    : m === 'ecart_urbain_moins_rural' ? { col: (v: Num) => couleurIps(P, v == null ? null : 1 - v), fmt: f3, lo: -0.15, hi: 0.15, ref: 0, t: [-0.1, 0, 0.1] }
    : m.startsWith('ips') ? { col: (v: Num) => couleurIps(P, v), fmt: f2, lo: 0.75, hi: 1.15, ref: 1, t: [0.8, 0.9, 1, 1.1] }
    : { col: (v: Num) => couleurAcces(P, v == null ? null : 1 - (0.8 * v) / max), fmt: nbf, lo: 0, hi: max, ref: 0, t: [0, max / 2, max] };
  const desc = m === 'eleves_perdus_depuis_max' || m === 'filles_manquantes_parite';
  const l = (R.names as string[]).map((n) => ({ k: n, v: R.ind[n][m] as Num, sous: `ancienne région : ${R.ind[n].old}` })).sort((a, b) => (a.v ?? 0) - (b.v ?? 0));
  return (
    <>
      <h3 className="section">Les 17 régions actuelles</h3>
      <div className="commandes"><label>Mesure<select value={m} onChange={(x) => maj({ r17: x.target.value })}>{Object.entries(MES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        <span className="sub">Chaque ancienne province tombe entièrement dans une seule région actuelle (vérifié commune par commune avec les codes COD-AB) : les effectifs s'additionnent sans estimation.</span></div>
      <div className="grille">
        <section className="carte-bloc"><h3>{MES[m]}</h3>
          <CarteSimple geo={R.geo} vb={R.vb} label="Carte des 17 régions" survol={s17} setSurvol={setS17} fill={(n) => E.col(R.ind[n][m])}
            info={(n) => <><b>{n}</b><div>{MES[m]} : {E.fmt(R.ind[n][m])}</div><div className="sub">Provinces : {R.ind[n].prov}</div></>} /></section>
        <section className="carte-bloc"><h3>Classement des 17 régions</h3>
          <Classement lignes={desc ? l.reverse() : l} lo={E.lo} hi={E.hi} ref={E.ref} fmt={E.fmt} couleur={(v) => E.col(v)} survol={s17} setSurvol={setS17} ticks={E.t} label="Classement des 17 régions" hl={28} /></section>
      </div>
    </>
  );
}
