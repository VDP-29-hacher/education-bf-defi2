/* Graphiques SVG faits main. Chaque graphique est dessine a la largeur reelle de son conteneur (ResizeObserver) :
   le texte garde donc sa vraie taille en pixels, sur grand ecran comme sur telephone. */
import { useId, useLayoutEffect, useRef, useState, type MouseEvent, type ReactNode } from 'react';
import { useApp } from './contexte';
import { f2, lisse, segments, type Num } from './lib';

export function useLargeur(defaut = 560) {
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(defaut);
  useLayoutEffect(() => {
    const el = ref.current; if (!el) return;
    setW(Math.max(280, Math.round(el.getBoundingClientRect().width)));
    const ro = new ResizeObserver(([e]) => setW(Math.max(280, Math.round(e.contentRect.width))));
    ro.observe(el); return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}
const tronquer = (s: string, n: number) => (s.length > n ? s.slice(0, n - 1) + '…' : s);

export interface Zone { name: string; d: string }

export function Carte({ geo, vb, fill, info, sel, survol, setSurvol, onPick, label }: {
  geo: Zone[]; vb: number[]; fill: (n: string) => string; info: (n: string) => ReactNode; sel?: string; survol?: string;
  setSurvol?: (n: string) => void; onPick?: (n: string) => void; label: string;
}) {
  const { tip } = useApp();
  return (
    <svg viewBox={vb.join(' ')} role="img" aria-label={label} className="carte">
      <g>
        {geo.map((g) => (
          <path key={g.name} d={g.d} fill={fill(g.name)} className={g.name === survol ? 'hl' : ''}
            tabIndex={onPick ? 0 : -1} aria-label={g.name}
            onMouseMove={(e) => { tip(e, info(g.name)); setSurvol?.(g.name); }}
            onMouseLeave={() => { tip(null); setSurvol?.(''); }}
            onClick={() => onPick?.(g.name)} onKeyDown={(e) => { if (e.key === 'Enter') onPick?.(g.name); }} />
        ))}
        {sel && geo.filter((g) => g.name === sel).map((g) => <path key="s" d={g.d} className="contour" pointerEvents="none" />)}
      </g>
    </svg>
  );
}

export function Degrade({ couleurs, libs }: { couleurs: string[]; libs: string[] }) {
  return (
    <div className="degrade">
      <div className="barre" style={{ background: `linear-gradient(90deg,${couleurs.join(',')})` }} />
      <div className="libs">{libs.map((l) => <span key={l}>{l}</span>)}</div>
    </div>
  );
}

export interface Serie { nom: string; couleur: string; vals: Num[]; tirets?: boolean; court?: string; sansEtiquette?: boolean }

export function Courbes({ series, labels, ref = 1, pas = 0.02, fmt = f2, bande, label, hauteur = 260 }: {
  series: Serie[]; labels: string[]; ref?: number | null; pas?: number; fmt?: (v: Num) => string; bande?: [Num[], Num[]]; label: string; hauteur?: number;
}) {
  const { P, tip } = useApp();
  const [boite, W] = useLargeur();
  const [h, setH] = useState<number | null>(null);
  const uid = useId().replace(/:/g, '');
  const etroit = W < 460, H = hauteur, m = { l: 46, r: etroit ? 16 : 124, t: 14, b: 32 }, n = labels.length;
  const vs = [...series.flatMap((s) => s.vals), ...(bande ? bande.flat() : [])].filter((v): v is number => v != null);
  let lo = Math.min(...vs, ...(ref == null ? [] : [ref])) - pas / 2, hi = Math.max(...vs, ...(ref == null ? [] : [ref])) + pas / 2;
  lo = Math.floor(lo / pas) * pas; hi = Math.ceil(hi / pas) * pas;
  const ng = Math.round((hi - lo) / pas), X = (i: number) => m.l + (i * (W - m.l - m.r)) / Math.max(1, n - 1), Y = (v: number) => m.t + ((hi - v) / (hi - lo)) * (H - m.t - m.b);
  const chemin = (vals: Num[]) => segments(vals, X, Y).map(lisse).join('');
  const base = H - m.b;
  const aire = (vals: Num[]) => segments(vals, X, Y).filter((sg) => sg.length > 1).map((sg) => `${lisse(sg)}L${sg[sg.length - 1][0].toFixed(1)},${base.toFixed(1)}L${sg[0][0].toFixed(1)},${base.toFixed(1)}Z`).join('');
  const avecAire = !bande && series.length <= 2;
  const etiq = etroit ? [] : series.filter((s) => !s.sansEtiquette).map((s) => { let k = n - 1; while (k > 0 && s.vals[k] == null) k--; return { s, k, y: s.vals[k] != null ? Y(s.vals[k] as number) : -99 }; })
    .filter((x) => x.y > -99).sort((a, b) => a.y - b.y);
  for (let i = 1; i < etiq.length; i++) if (etiq[i].y - etiq[i - 1].y < 16) etiq[i].y = etiq[i - 1].y + 16;
  let zone = '';
  if (bande) {
    const [a, b] = bande; let haut = '', bas = '';
    const ha = segments(a.map((v, i) => (v != null && b[i] != null ? v : null)), X, Y)[0] ?? [], ba = segments(b.map((v, i) => (v != null && a[i] != null ? v : null)), X, Y)[0] ?? [];
    haut = lisse(ha); bas = lisse([...ba].reverse()).replace(/^M/, 'L');
    zone = haut && bas ? haut + bas + 'Z' : '';
  }
  const pasX = Math.max(1, Math.ceil(n / Math.max(2, Math.floor((W - m.l - m.r) / 64))));
  const bouger = (e: MouseEvent<SVGSVGElement>) => {
    const bb = e.currentTarget.getBoundingClientRect(), x = e.clientX - bb.left, i = Math.max(0, Math.min(n - 1, Math.round(((x - m.l) / (W - m.l - m.r)) * (n - 1))));
    setH(i);
    tip(e, <><b>{labels[i]}</b>{series.map((s) => <div key={s.nom}><i className="pastille" style={{ background: s.couleur }} />{s.nom} : <b>{fmt(s.vals[i])}</b></div>)}</>);
  };
  return (
    <div ref={boite} className="graphe">
      {(series.length > 1 || etroit) && <div className="legende">{series.map((s) => <span key={s.nom}><i className="trait" style={{ background: s.couleur }} />{s.nom}</span>)}</div>}
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} onMouseMove={bouger} onMouseLeave={() => { setH(null); tip(null); }}>
        {Array.from({ length: ng + 1 }, (_, k) => lo + k * pas).filter((_, k) => ng <= 8 || k % Math.ceil(ng / 8) === 0).map((t) => (
          <g key={t}><line x1={m.l} x2={W - m.r} y1={Y(t)} y2={Y(t)} stroke={P.grid} strokeDasharray="3 4" /><text x={m.l - 8} y={Y(t) + 4} textAnchor="end">{fmt(t)}</text></g>))}
        <line x1={m.l} x2={W - m.r} y1={H - m.b} y2={H - m.b} stroke={P.muted} strokeOpacity={0.5} />
        <defs>{series.map((s, j) => <linearGradient key={s.nom} id={`deg${uid}${j}`} x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor={s.couleur} stopOpacity={0.22} /><stop offset="1" stopColor={s.couleur} stopOpacity={0} /></linearGradient>)}</defs>
        {ref != null && <line x1={m.l} x2={W - m.r} y1={Y(ref)} y2={Y(ref)} stroke={P.muted} strokeDasharray="4 4" />}
        {labels.map((lb, i) => ((i % pasX === 0 && n - 1 - i >= Math.max(1, pasX * 0.7)) || i === n - 1) && <text key={lb} x={X(i)} y={H - 10} textAnchor="middle">{lb}</text>)}
        {zone && <path d={zone} fill={P.grid} opacity={0.9} />}
        {avecAire && series.map((s, j) => !s.tirets && <path key={s.nom} d={aire(s.vals)} fill={`url(#deg${uid}${j})`} stroke="none" />)}
        {series.map((s) => <path key={s.nom} d={chemin(s.vals)} fill="none" stroke={s.couleur} strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round" strokeDasharray={s.tirets ? '7 5' : undefined} />)}
        {series.map((s) => s.vals.map((v, i) => v != null && <circle key={s.nom + i} cx={X(i)} cy={Y(v)} r={3.6} fill={P.surface} stroke={s.couleur} strokeWidth={2} />))}
        {etiq.map(({ s, k, y }) => (
          <g key={s.nom}><circle cx={X(k)} cy={Y(s.vals[k] as number)} r={4.5} fill={s.couleur} stroke={P.surface} strokeWidth={2} />
            <text x={X(k) + 10} y={y + 4} className="fort">{`${tronquer(s.court ?? s.nom, 12)} ${fmt(s.vals[k])}`}</text></g>))}
        {h != null && <line x1={X(h)} x2={X(h)} y1={m.t} y2={H - m.b} stroke={P.muted} opacity={0.6} />}
        {h != null && series.map((s) => s.vals[h] != null && <circle key={s.nom} cx={X(h)} cy={Y(s.vals[h] as number)} r={4} fill={s.couleur} stroke={P.surface} strokeWidth={1.5} />)}
      </svg>
    </div>
  );
}

/** Classement en barres ancrees sur une reference (parite = 1,00, ou 0). */
export function Classement({ lignes, lo, hi, ref, fmt, couleur, sel, survol, setSurvol, onPick, label, ticks, hl = 30 }: {
  lignes: { k: string; v: Num; sous?: string }[]; lo: number; hi: number; ref: number; fmt: (v: Num) => string; couleur: (v: number) => string;
  sel?: string; survol?: string; setSurvol?: (n: string) => void; onPick?: (k: string) => void; label: string; ticks: number[]; hl?: number;
}) {
  const { P, tip } = useApp();
  const [boite, W] = useLargeur();
  const L = lignes.filter((x) => x.v != null), m = { l: W < 420 ? 112 : 146, r: 60, t: 4, b: 26 }, H = m.t + m.b + L.length * hl;
  const x = (v: number) => m.l + ((Math.max(lo, Math.min(hi, v)) - lo) / (hi - lo)) * (W - m.l - m.r);
  return (
    <div ref={boite} className="graphe">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
        {ticks.map((t) => <g key={t}><line x1={x(t)} x2={x(t)} y1={m.t} y2={H - m.b} stroke={t === ref ? P.muted : P.grid} />
          <text x={x(t)} y={H - 8} textAnchor="middle">{fmt(t)}</text></g>)}
        {L.map((o, i) => {
          const y = m.t + i * hl, v = o.v as number, x0 = x(ref), x1 = x(v), actif = o.k === sel || o.k === survol;
          return (
            <g key={o.k} className="barre-ligne" onMouseMove={(e) => { tip(e, <><b>{o.k}</b>{o.sous && <div className="sub">{o.sous}</div>}<div>{fmt(o.v)}</div></>); setSurvol?.(o.k); }}
              onMouseLeave={() => { tip(null); setSurvol?.(''); }} onClick={() => onPick?.(o.k)}>
              <rect x={0} y={y} width={W} height={hl} rx={6} fill={actif ? P.hover : 'transparent'} />
              <rect x={Math.min(x0, x1)} y={y + hl * 0.22} width={Math.max(2, Math.abs(x1 - x0))} height={hl * 0.56} rx={4} fill={couleur(v)}
                stroke={o.k === sel ? P.text : 'none'} strokeWidth={1.5} />
              <text x={m.l - 10} y={y + hl / 2 + 4.5} textAnchor="end" className={actif ? 'fort' : ''}>{tronquer(o.k, W < 420 ? 14 : 20)}</text>
              <text x={v < ref ? Math.min(x0, x1) - 6 : Math.max(x0, x1) + 6} y={y + hl / 2 + 4.5} textAnchor={v < ref ? 'end' : 'start'} className="fort">{fmt(o.v)}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

/** Points et intervalles (projection avec marge d'erreur). */
export function Intervalles({ lignes, lo, hi, seuil, sel, onPick, label }: {
  lignes: { k: string; v: number; bas: number; haut: number; couleur: string; info: ReactNode }[]; lo: number; hi: number; seuil: number; sel?: string; onPick?: (k: string) => void; label: string;
}) {
  const { P, tip } = useApp();
  const [boite, W] = useLargeur();
  const rh = 24, m = { l: W < 420 ? 112 : 146, r: 52, t: 4, b: 26 }, H = m.t + m.b + lignes.length * rh;
  const x = (v: number) => m.l + ((Math.max(lo, Math.min(hi, v)) - lo) / (hi - lo)) * (W - m.l - m.r);
  const ticks = [0.7, 0.8, 0.9, 0.95, 1, 1.1].filter((t) => t >= lo && t <= hi);
  return (
    <div ref={boite} className="graphe">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
        {ticks.map((t) => <g key={t}><line x1={x(t)} x2={x(t)} y1={m.t} y2={H - m.b} stroke={t === seuil ? P.dlow : P.grid} strokeDasharray={t === seuil ? '4 4' : undefined} />
          <text x={x(t)} y={H - 8} textAnchor="middle">{f2(t)}</text></g>)}
        {lignes.map((o, i) => {
          const y = m.t + i * rh + rh / 2, s = o.k === sel;
          return (
            <g key={o.k} className="barre-ligne" onMouseMove={(e) => tip(e, o.info)} onMouseLeave={() => tip(null)} onClick={() => onPick?.(o.k)}>
              <rect x={0} y={y - rh / 2} width={W} height={rh} rx={6} fill={s ? P.hover : 'transparent'} />
              <line x1={x(o.bas)} x2={x(o.haut)} y1={y} y2={y} stroke={o.couleur} strokeWidth={3} strokeLinecap="round" opacity={0.55} />
              <circle cx={x(o.v)} cy={y} r={s ? 6 : 4.5} fill={o.couleur} stroke={s ? P.text : P.surface} strokeWidth={1.5} />
              <text x={m.l - 10} y={y + 4.5} textAnchor="end" className={s ? 'fort' : ''}>{tronquer(o.k, W < 420 ? 14 : 20)}</text>
              <text x={x(o.haut) + 7} y={y + 4.5} className="fort">{f2(o.v)}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

/** Haltere : taux des garcons et des filles par zone. */
export function Halteres({ lignes, max, sel, onPick, label }: {
  lignes: { k: string; g: number; f: number; t: number; gras?: boolean; info: ReactNode }[]; max: number; sel?: string; onPick?: (k: string) => void; label: string;
}) {
  const { P, tip } = useApp();
  const [boite, W] = useLargeur();
  const rh = 30, m = { l: W < 420 ? 112 : 146, r: 56, t: 4, b: 26 }, H = m.t + m.b + lignes.length * rh, x = (v: number) => m.l + (v / max) * (W - m.l - m.r);
  return (
    <div ref={boite} className="graphe">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
        {[0, 25, 50, 75, 100].map((t) => <g key={t}><line x1={x(t)} x2={x(t)} y1={m.t} y2={H - m.b} stroke={t === 100 ? P.muted : P.grid} strokeDasharray={t === 100 ? '4 4' : undefined} />
          <text x={x(t)} y={H - 8} textAnchor="middle">{t} %</text></g>)}
        {lignes.map((o, j) => {
          const y = m.t + j * rh + rh / 2, s = o.k === sel;
          return (
            <g key={o.k} className="barre-ligne" onMouseMove={(e) => tip(e, o.info)} onMouseLeave={() => tip(null)} onClick={() => onPick?.(o.k)}>
              <rect x={0} y={y - rh / 2} width={W} height={rh} rx={6} fill={s ? P.hover : 'transparent'} />
              <text x={m.l - 10} y={y + 4.5} textAnchor="end" className={s || o.gras ? 'fort' : ''}>{tronquer(o.k, W < 420 ? 14 : 20)}</text>
              <line x1={x(Math.min(o.g, o.f))} x2={x(Math.max(o.g, o.f))} y1={y} y2={y} stroke={P.muted} strokeWidth={2.5} />
              <circle cx={x(o.g)} cy={y} r={6} fill={P.s1} stroke={P.surface} strokeWidth={1.5} /><circle cx={x(o.f)} cy={y} r={6} fill={P.s2} stroke={P.surface} strokeWidth={1.5} />
              <text x={x(Math.max(o.g, o.f)) + 11} y={y + 4.5} className="fort">{Math.round(o.t)} %</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export function Mini({ vals, couleur, ref }: { vals: Num[]; couleur: string; ref?: number }) {
  const { P } = useApp();
  const w = 240, h = 48, v = vals.map((x, i) => [i, x] as const).filter((p): p is readonly [number, number] => p[1] != null);
  if (v.length < 2) return null;
  let lo = Math.min(...v.map((p) => p[1])), hi = Math.max(...v.map((p) => p[1]));
  if (ref != null) { lo = Math.min(lo, ref); hi = Math.max(hi, ref); }
  if (hi - lo < 1e-9) { hi += 1e-3; lo -= 1e-3; }
  const X = (i: number) => 5 + (i * (w - 10)) / (vals.length - 1), Y = (x: number) => h - 6 - ((x - lo) / (hi - lo)) * (h - 12), l = v[v.length - 1];
  const d = lisse(v.map((p) => [X(p[0]), Y(p[1])] as [number, number]));
  return (
    <svg viewBox={`0 0 ${w} ${h}`} aria-hidden="true" className="mini">
      {ref != null && <line x1={5} x2={w - 5} y1={Y(ref)} y2={Y(ref)} stroke={P.grid} strokeDasharray="3 3" />}
      <path d={`${d}L${X(l[0])},${h}L${X(v[0][0])},${h}Z`} fill={couleur} opacity={0.08} />
      <path d={d} fill="none" stroke={couleur} strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
      <circle cx={X(l[0])} cy={Y(l[1])} r={4} fill={couleur} />
    </svg>
  );
}

/** Barre dans une cellule de tableau. */
export const Jauge = ({ v, max, txt, couleur }: { v: Num; max: number; txt: string; couleur: string }) =>
  v == null ? <>n.d.</> : <span className="jauge"><i style={{ width: `${Math.max(3, Math.min(100, (v / max) * 100))}%`, background: couleur }} /><b>{txt}</b></span>;

export function Tableau({ entetes, lignes, gauche = 1 }: { entetes: string[]; lignes: ReactNode[][]; gauche?: number }) {
  return (
    <div className="tableau"><table>
      <thead><tr>{entetes.map((h, i) => <th key={h} className={i < gauche ? 'g' : ''}>{h}</th>)}</tr></thead>
      <tbody>{lignes.map((l, j) => <tr key={j}>{l.map((c, i) => <td key={i} className={i < gauche ? 'g' : ''}>{c}</td>)}</tr>)}</tbody>
    </table></div>
  );
}
