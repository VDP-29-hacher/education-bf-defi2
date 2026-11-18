/* Elements d'identite et blocs communs : drapeau, embleme, illustration, en-tete de page, bandeau d'indicateurs. */
import type { ReactNode } from 'react';
import photoEleves from './images/eleves-burkina.jpg';
import { useApp, type Onglet } from './contexte';
import { Icone } from './icones';
import { f2, f3, lisse, nbf, pc, priorites, ya, type Num } from './lib';

/** Drapeau du Burkina Faso (rouge, vert, etoile jaune). */
export const Drapeau = ({ largeur = 36 }: { largeur?: number }) => (
  <svg width={largeur} height={largeur * 2 / 3} viewBox="0 0 30 20" aria-hidden="true" className="drapeau">
    <rect width="30" height="10" fill="#EF2B2D" /><rect y="10" width="30" height="10" fill="#009E49" />
    <path d="M15 5.2l1.18 3.62h3.8l-3.08 2.24 1.18 3.62L15 12.44l-3.08 2.24 1.18-3.62-3.08-2.24h3.8z" fill="#FCD116" />
  </svg>
);

/** Embleme : un livre ouvert sous l'etoile du drapeau. */
export const Embleme = () => (
  <svg width="56" height="44" viewBox="0 0 56 44" aria-hidden="true">
    <path d="M10 10c6-6 14-7 18-2 4-5 12-4 18 2" fill="none" stroke="#EF2B2D" strokeWidth="3.2" strokeLinecap="round" />
    <path d="M12 14c5-4 12-4.6 16-.6 4-4 11-3.4 16 .6" fill="none" stroke="#009E49" strokeWidth="3.2" strokeLinecap="round" />
    <path d="M28 2.2l1.4 4.2h4.4l-3.6 2.6 1.4 4.2-3.6-2.6-3.6 2.6 1.4-4.2-3.6-2.6h4.4z" fill="#FCD116" />
    <path d="M6 22c8-4 16-4 22 1 6-5 14-5 22-1v18c-8-4-16-4-22 1-6-5-14-5-22-1z" fill="#fff" />
    <path d="M28 23v18" stroke="#0b2a5b" strokeWidth="1.6" />
    <path d="M11 27c5-2 9-2 13 0M11 31.5c5-2 9-2 13 0M32 27c4-2 8-2 13 0M32 31.5c4-2 8-2 13 0" stroke="#9fb3d1" strokeWidth="1.3" fill="none" strokeLinecap="round" />
  </svg>
);

/** Illustration d'en-tete : une ecole, son drapeau, des arbres, le soleil. Dessinee, aucune photo. */
export const Illustration = () => (
  <svg className="illustration" viewBox="0 0 420 170" aria-hidden="true" preserveAspectRatio="xMaxYMax meet">
    <defs>
      <linearGradient id="ciel" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#fdf3d8" stopOpacity="0" /><stop offset="1" stopColor="#fbe3b3" stopOpacity=".55" /></linearGradient>
      <linearGradient id="mur" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#f6d9b0" /><stop offset="1" stopColor="#e9bf8a" /></linearGradient>
    </defs>
    <rect x="0" y="0" width="420" height="170" fill="url(#ciel)" />
    <circle cx="330" cy="46" r="26" fill="#fcd116" opacity=".55" />
    <path d="M0 150c70-14 140-16 210-6s140 8 210-8v34H0z" fill="#d9ecd0" />
    <g transform="translate(150 66)">
      <rect x="0" y="22" width="210" height="64" rx="3" fill="url(#mur)" />
      <path d="M-10 26 105-6 220 26z" fill="#c4512e" />
      {[16, 52, 140, 176].map((x) => <rect key={x} x={x} y="40" width="22" height="20" rx="2" fill="#7fb3d5" stroke="#fff" strokeWidth="2" />)}
      <rect x="92" y="44" width="26" height="42" rx="2" fill="#8a4b2a" />
      <text x="105" y="35" textAnchor="middle" style={{ font: '700 10px var(--police)', fill: '#7a3b1d' }}>ÉCOLE</text>
    </g>
    <g transform="translate(372 26)">
      <rect x="0" y="0" width="3" height="96" fill="#8b8f96" />
      <rect x="3" y="2" width="34" height="11" fill="#EF2B2D" /><rect x="3" y="13" width="34" height="11" fill="#009E49" />
      <path d="M20 8.4l1 2.9h3l-2.4 1.8.9 2.9-2.5-1.8-2.5 1.8.9-2.9-2.4-1.8h3z" fill="#FCD116" />
    </g>
    {[[70, 120, 30], [118, 128, 22], [404, 130, 18]].map(([x, y, r]) => (
      <g key={x}><rect x={x - 2.5} y={y} width="5" height={170 - y - 22} fill="#8a5a36" /><circle cx={x} cy={y - r * 0.4} r={r} fill="#5fae5a" /><circle cx={x - r * 0.5} cy={y - r * 0.1} r={r * 0.7} fill="#4c9b4a" /></g>))}
  </svg>
);

/** En-tete de page : liseré aux couleurs nationales, titre, sous-titre, illustration. */
export function EnTete({ titre, sousTitre, action }: { titre: string; sousTitre: ReactNode; action?: ReactNode }) {
  return (
    <header className="entete">
      <span className="lisere" aria-hidden="true"><i /><i /><i /></span>
      <div className="entete-texte"><h1>{titre}</h1><p>{sousTitre}</p>{action}</div>
      <figure className="entete-photo"><img src={photoEleves} alt="" /><figcaption>Illustration générée par IA</figcaption></figure>
    </header>
  );
}

/** Bandeau des cinq indicateurs cles (fonds pastel), chacun ouvre la partie de l'outil qui le detaille. */
export function Bandeau() {
  const { D, P, e, maj } = useApp();
  const N1 = D.years.length - 1, z = D.acc?.tbs_primaire?.z;
  const cartes: { teinte: string; icone: string; titre: string; valeur: string; sous: string; vals?: Num[]; couleur: string; o: Onglet; barres?: number[] }[] = [];
  if (z) {
    const rs = (D.regions as string[]).filter((r) => z[r]?.t[N1] != null).sort((a, b) => z[a].t[N1] - z[b].t[N1]);
    cartes.push({ teinte: 'rose', icone: 'groupe', titre: 'Écart territorial', valeur: `${pc(z[rs[0]].t[N1])} à ${pc(z[rs.at(-1) as string].t[N1])}`,
      sous: `TBS primaire : ${rs[0]} → ${rs.at(-1)}`, vals: z.National.t, couleur: P.dlow, o: 'carte' });
  }
  cartes.push({ teinte: 'bleu', icone: 'diplome', titre: 'Filles et garçons', valeur: `IPS ${f2(D.nat.pri[N1])}`, sous: `${f2(D.nat.pri[0])} en ${ya(D.years[0])}`, vals: D.nat.pri, couleur: P.s1, o: 'tdb' });
  const gap: Num[] = D.mil.urbain.map((u: Num, i: number) => (u != null && D.mil.rural[i] != null ? u - D.mil.rural[i] : null));
  cartes.push({ teinte: 'vert', icone: 'ecole', titre: 'Ville et campagne', valeur: `${f3(gap[N1] ?? null)} pt`, sous: `${f3(gap[0])} pt en ${ya(D.years[0])}`, vals: gap, couleur: P.s3, o: 'carte' });
  const pr = priorites(D, e.ips, e.acc), p1 = pr.filter((o) => o.priorite === 1).length;
  cartes.push({ teinte: 'jaune', icone: 'couches', titre: 'Provinces prioritaires', valeur: `${p1} / ${D.prov.names.length}`, sous: `+ ${pr.length - p1} en priorité 2`, couleur: '#f0a020', o: 'decision',
    barres: [p1, pr.length - p1, D.prov.names.length - pr.length] });
  const mc = (D.mc ?? []).find((x: any) => x.r === 'National');
  if (mc) cartes.push({ teinte: 'violet', icone: 'groupe', titre: 'Enfants à scolariser', valeur: `≈ ${nbf(Math.round(mc.plus / 1000) * 1000)}`, sous: 'élèves à ajouter pour un TBS de 100 %', couleur: '#7c5cd6', o: 'analyse' });
  return (
    <div className="bandeau-kpi">
      {cartes.map((c) => (
        <button key={c.titre} type="button" className={`kpi-carte ${c.teinte}`} onClick={() => maj({ o: c.o })} title="Voir le détail">
          <span className="kpi-icone"><Icone nom={c.icone} taille={24} /></span>
          <span className="kpi-corps">
            <span className="kpi-titre">{c.titre}</span>
            <span className="kpi-valeur">{c.valeur}</span>
            {c.vals ? <Trace vals={c.vals} couleur={c.couleur} /> : c.barres ? <Barres v={c.barres} /> : null}
            <span className="kpi-sous">{c.sous}</span>
          </span>
        </button>
      ))}
    </div>
  );
}

function Trace({ vals, couleur }: { vals: Num[]; couleur: string }) {
  const v = vals.map((x, i) => [i, x] as const).filter((p): p is readonly [number, number] => p[1] != null);
  if (v.length < 2) return null;
  const lo = Math.min(...v.map((p) => p[1])), hi = Math.max(...v.map((p) => p[1])) + 1e-9, w = 150, h = 26;
  const d = lisse(v.map((p) => [4 + (p[0] * (w - 8)) / (vals.length - 1), h - 4 - ((p[1] - lo) / (hi - lo)) * (h - 8)] as [number, number]));
  return <svg className="kpi-trace" viewBox={`0 0 ${w} ${h}`} aria-hidden="true"><path d={d} fill="none" stroke={couleur} strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}
function Barres({ v }: { v: number[] }) {
  const m = Math.max(...v), c = ['#d9413f', '#f0a020', '#43a047'];
  return <svg className="kpi-trace" viewBox="0 0 150 26" aria-hidden="true">{v.map((x, i) => <rect key={i} x={4 + i * 22} y={26 - (x / m) * 22 - 2} width="14" height={(x / m) * 22} rx="2" fill={c[i]} />)}</svg>;
}
