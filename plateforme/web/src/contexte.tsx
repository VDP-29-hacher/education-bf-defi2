import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { PALETTES, type Donnees, type Palette } from './lib';

export const ONGLETS = [
  { id: 'accueil', lib: 'Accueil', n: '' },
  { id: 'analyse', lib: 'Analyse', n: '1' },
  { id: 'tdb', lib: 'Tableau de bord', n: '2' },
  { id: 'carte', lib: 'Carte', n: '3' },
  { id: 'decision', lib: 'Aide à la décision', n: '4' },
  { id: 'prevision', lib: 'Prévision', n: '5' },
  { id: 'methode', lib: 'Méthode et données', n: '' },
] as const;
export type Onglet = (typeof ONGLETS)[number]['id'];

/** Etat de la vue, garde dans l'adresse (#...) : un lien rouvre exactement la meme vue. */
export interface Etat { o: Onglet; p: string; ips: number; acc: number; niv: 'pri' | 'pre' | 'cp1'; a: number; r: string; m: string; r17: string }

interface Ctx { D: Donnees; P: Palette; theme: 'clair' | 'sombre'; basculerTheme: () => void; e: Etat; maj: (x: Partial<Etat>) => void;
  source: 'api' | 'autonome'; tip: (ev: { clientX: number; clientY: number } | null, contenu?: ReactNode) => void; tipNode: ReactNode;
  ouvrir: (province: string, onglet?: Onglet) => void }
const C = createContext<Ctx>(null as unknown as Ctx);
export const useApp = () => useContext(C);

function lireHash(D: Donnees): Etat {
  const [o0, qs = ''] = location.hash.replace(/^#\/?/, '').split('?'), q = new URLSearchParams(qs);
  const prio = (D.prov?.prio ?? [])[0]?.province ?? D.prov?.names?.[0] ?? '';
  const num = (k: string, d: number, lo: number, hi: number) => { const v = Number(q.get(k)); return q.get(k) != null && v >= lo && v <= hi ? v : d; };
  return {
    o: (ONGLETS.some((x) => x.id === o0) ? o0 : 'accueil') as Onglet,
    p: D.prov?.names?.includes(q.get('p')) ? (q.get('p') as string) : prio,
    ips: num('ips', 0.95, 0.85, 1), acc: num('acc', 0.6, 0.3, 0.9),
    niv: (['pri', 'pre', 'cp1'].includes(q.get('niv') ?? '') ? q.get('niv') : 'pri') as Etat['niv'],
    a: D.years.includes(Number(q.get('a'))) ? Number(q.get('a')) : D.years.at(-1),
    r: D.regions.includes(q.get('r')) ? (q.get('r') as string) : '',
    m: q.get('m') || 'effectif_dernier_sur_max', r17: q.get('r17') || 'effectif_dernier_sur_max',
  };
}

export function Fournisseur({ D, source, children }: { D: Donnees; source: 'api' | 'autonome'; children: ReactNode }) {
  const [e, setE] = useState<Etat>(() => lireHash(D));
  const [theme, setTheme] = useState<'clair' | 'sombre'>(() => {
    try { const t = localStorage.getItem('theme'); if (t === 'clair' || t === 'sombre') return t; } catch { /* stockage indisponible */ }
    return matchMedia('(prefers-color-scheme: dark)').matches ? 'sombre' : 'clair';
  });
  const [tipNode, setTip] = useState<ReactNode>(null);
  useEffect(() => {
    const q = new URLSearchParams({ p: e.p, ips: String(e.ips), acc: String(e.acc), niv: e.niv, a: String(e.a), r: e.r, m: e.m, r17: e.r17 });
    history.replaceState(null, '', `#/${e.o}?${q}`);
  }, [e]);
  useEffect(() => {                                   // lien colle dans la barre d'adresse, boutons precedent / suivant
    const lire = () => setE(lireHash(D));
    window.addEventListener('hashchange', lire); return () => window.removeEventListener('hashchange', lire);
  }, [D]);
  useEffect(() => { document.documentElement.dataset.theme = theme; try { localStorage.setItem('theme', theme); } catch { /* rien */ } }, [theme]);
  const v = useMemo<Ctx>(() => ({
    D, source, theme, P: PALETTES[theme], e, tipNode,
    basculerTheme: () => setTheme((t) => (t === 'clair' ? 'sombre' : 'clair')),
    maj: (x) => setE((s) => ({ ...s, ...x })),
    tip: (ev, contenu) => setTip(ev && contenu ? <Bulle x={ev.clientX} y={ev.clientY}>{contenu}</Bulle> : null),
    ouvrir: (p, o = 'decision') => { setE((s) => ({ ...s, p, o })); window.scrollTo({ top: 0, behavior: 'smooth' }); },
  }), [D, source, theme, e, tipNode]);
  return <C.Provider value={v}>{children}</C.Provider>;
}

function Bulle({ x, y, children }: { x: number; y: number; children: ReactNode }) {
  const l = Math.min(x + 14, window.innerWidth - 270);
  return <div className="bulle" role="tooltip" style={{ left: Math.max(4, l), top: y + 14 }}>{children}</div>;
}
