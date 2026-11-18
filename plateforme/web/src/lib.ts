/* Outils communs : formats francais, couleurs, regle de priorite, acces aux donnees. */
/* eslint-disable @typescript-eslint/no-explicit-any */
export type Num = number | null;
export type Donnees = any;

export const f2 = (v: Num | undefined) => (v == null ? 'n.d.' : v.toFixed(2).replace('.', ','));
export const f3 = (v: Num | undefined) => (v == null ? 'n.d.' : v.toFixed(3).replace('.', ','));
export const pc = (v: Num | undefined) => (v == null ? 'n.d.' : `${Math.round(v)} %`);
export const pc1 = (v: Num | undefined) => (v == null ? 'n.d.' : `${Math.round(v * 100)} %`);
export const nbf = (v: Num | undefined) => (v == null ? 'n.d.' : Math.round(v).toLocaleString('fr-FR'));
export const ya = (y: number) => `${y}/${String(y + 1).slice(2)}`;
export const signe = (v: number, f: (x: number) => string) => (v >= 0 ? '+' : '−') + f(Math.abs(v));

export interface Palette { bg: string; surface: string; text: string; text2: string; muted: string; grid: string; border: string;
  s1: string; s2: string; s3: string; dlow: string; dmid: string; dhigh: string; ok: string; brand: string; brand2: string; hover: string }
export const PALETTES: Record<'clair' | 'sombre', Palette> = {
  clair: { bg: '#f5f6f8', surface: '#ffffff', text: '#0f172a', text2: '#334155', muted: '#64748b', grid: '#e2e8f0', border: '#e2e8f0',
    s1: '#2a78d6', s2: '#e8743b', s3: '#1baf7a', dlow: '#d9413f', dmid: '#eef1f4', dhigh: '#2a78d6', ok: '#178a60', brand: '#0e4f5c', brand2: '#0f766e', hover: '#f1f5f4' },
  sombre: { bg: '#0b1015', surface: '#121a21', text: '#e6edf3', text2: '#c2ccd6', muted: '#8b98a5', grid: '#24303a', border: '#24303a',
    s1: '#4a93ea', s2: '#e5803f', s3: '#22b17f', dlow: '#e86563', dmid: '#2a343d', dhigh: '#4a93ea', ok: '#2fb47f', brand: '#0f3d47', brand2: '#2dd4bf', hover: '#22282c' },
};
export const PROFILS = ['#b2182b', '#e8743b', '#d9a426', '#5b9fd6', '#1d5fa8'];

const hex = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
export function melange(a: string, b: string, t: number) {
  const A = hex(a), B = hex(b);
  return `rgb(${A.map((x, i) => Math.round(x + (B[i] - x) * t)).join(',')})`;
}
/** Echelle divergente centree sur la parite (1,00) : rouge = moins de filles, bleu = plus de filles. */
export const couleurIps = (P: Palette, v: Num | undefined, amplitude = 0.15) => {
  if (v == null) return P.grid;
  const t = Math.max(-1, Math.min(1, (v - 1) / amplitude));
  return t < 0 ? melange(P.dmid, P.dlow, -t) : melange(P.dmid, P.dhigh, t);
};
/** Echelle sequentielle de perte d'acces : 100 % du maximum = neutre, 0 % = rouge fonce. */
export const couleurAcces = (P: Palette, v: Num | undefined) => (v == null ? P.grid : melange(P.dmid, P.dlow, Math.max(0, Math.min(1, (1 - v) / 0.8))));

/** Regle de priorite (identique a l'API et au dossier). */
export function priorites(D: Donnees, ips: number, acces: number) {
  const P = D.prov, n1 = D.years.length - 1;
  return (P.names as string[]).map((n) => {
    const i = P.ind[n], ip: Num = P.hist[n][n1], c1 = ip != null && ip < ips, c2 = i.effectif_dernier_sur_max != null && i.effectif_dernier_sur_max < acces;
    return { province: n, region: i.region as string, priorite: c1 && c2 ? 1 : c1 || c2 ? 2 : 0, ips: ip, effectifsSurMax: i.effectif_dernier_sur_max as Num,
      elevesPerdus: i.eleves_perdus_depuis_max as Num, fillesAInscrire: i.filles_manquantes_parite as Num };
  }).filter((o) => o.priorite).sort((a, b) => a.priorite - b.priorite || (a.ips ?? 9) - (b.ips ?? 9));
}
export type Priorite = ReturnType<typeof priorites>[number];

/** Telechargement CSV (separateur ;, virgule decimale, BOM pour Excel). */
export function telechargerCsv(nom: string, entetes: string[], lignes: unknown[][]) {
  const q = (v: unknown) => (v == null ? '' : typeof v === 'number' ? String(v).replace('.', ',') : `"${String(v).replace(/"/g, '""')}"`);
  const t = '﻿' + [entetes.join(';'), ...lignes.map((l) => l.map(q).join(';'))].join('\r\n');
  const u = URL.createObjectURL(new Blob([t], { type: 'text/csv;charset=utf-8' })), a = document.createElement('a');
  a.href = u; a.download = nom; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(u), 2000);
}

/** Chemin SVG lisse (interpolation cubique monotone de Fritsch-Carlson, comme la "ligne lissee" d'un tableur) :
 *  la courbe passe exactement par chaque point et ne depasse jamais les valeurs voisines (pas de faux pic). */
export function lisse(pts: [number, number][]): string {
  const n = pts.length;
  if (n === 0) return '';
  if (n < 3) return pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join('');
  const dx: number[] = [], m: number[] = [], t: number[] = new Array(n).fill(0);
  for (let i = 0; i < n - 1; i++) { dx.push(pts[i + 1][0] - pts[i][0]); m.push((pts[i + 1][1] - pts[i][1]) / (dx[i] || 1)); }
  t[0] = m[0]; t[n - 1] = m[n - 2];
  for (let i = 1; i < n - 1; i++) t[i] = m[i - 1] * m[i] <= 0 ? 0 : (m[i - 1] + m[i]) / 2;
  for (let i = 0; i < n - 1; i++) {
    if (m[i] === 0) { t[i] = 0; t[i + 1] = 0; continue; }
    const a = t[i] / m[i], b = t[i + 1] / m[i], h = a * a + b * b;
    if (h > 9) { const k = 3 / Math.sqrt(h); t[i] = k * a * m[i]; t[i + 1] = k * b * m[i]; }
  }
  let d = `M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
  for (let i = 0; i < n - 1; i++) {
    const [x0, y0] = pts[i], [x1, y1] = pts[i + 1], h = dx[i] / 3;
    d += `C${(x0 + h).toFixed(1)},${(y0 + t[i] * h).toFixed(1)} ${(x1 - h).toFixed(1)},${(y1 - t[i + 1] * h).toFixed(1)} ${x1.toFixed(1)},${y1.toFixed(1)}`;
  }
  return d;
}
/** Decoupe une serie avec des trous (null) en segments continus de points. */
export function segments(vals: (number | null)[], X: (i: number) => number, Y: (v: number) => number): [number, number][][] {
  const out: [number, number][][] = []; let cur: [number, number][] = [];
  vals.forEach((v, i) => { if (v == null) { if (cur.length) out.push(cur); cur = []; } else cur.push([X(i), Y(v)]); });
  if (cur.length) out.push(cur);
  return out;
}
