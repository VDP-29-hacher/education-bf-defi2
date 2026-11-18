import { useEffect, useRef, useState } from 'react';
import { useApp } from './contexte';
import Sidebar from './Sidebar';
import { ChevronsLeft, ChevronsRight } from 'lucide-react';
import { Icone } from './icones';
import Accueil from './pages/Accueil';
import Analyse from './pages/Analyse';
import TableauDeBord from './pages/TableauDeBord';
import Cartes from './pages/Cartes';
import Decision from './pages/Decision';
import Prevision from './pages/Prevision';
import Methode from './pages/Methode';

const PAGES = { accueil: Accueil, analyse: Analyse, tdb: TableauDeBord, carte: Cartes, decision: Decision, prevision: Prevision, methode: Methode };

function Recherche() {
  const { D, ouvrir, maj } = useApp();
  const [q, setQ] = useState('');
  const [i, setI] = useState(0);
  const champ = useRef<HTMLInputElement>(null);
  const norm = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const provs = q.length < 1 ? [] : (D.prov.names as string[]).filter((n) => norm(n).includes(norm(q)) || norm(D.prov.ind[n].region).includes(norm(q))).slice(0, 7)
    .map((n) => ({ k: n, sous: D.prov.ind[n].region, go: () => ouvrir(n, 'carte') }));
  const regs = q.length < 2 ? [] : (D.regions as string[]).filter((r) => norm(r).includes(norm(q))).slice(0, 3)
    .map((r) => ({ k: r, sous: 'ancienne région', go: () => maj({ o: 'tdb', r }) }));
  const res = [...regs, ...provs].slice(0, 8);
  const choisir = (x: (typeof res)[number]) => { x.go(); setQ(''); champ.current?.blur(); };
  useEffect(() => {
    const raccourci = (e: globalThis.KeyboardEvent) => { if (e.key === '/' && document.activeElement?.tagName !== 'INPUT') { e.preventDefault(); champ.current?.focus(); } };
    window.addEventListener('keydown', raccourci); return () => window.removeEventListener('keydown', raccourci);
  }, []);
  return (
    <div className="recherche" role="search">
      <Icone nom="recherche" taille={19} />
      <input ref={champ} type="search" placeholder="Rechercher une province, une région…" aria-label="Rechercher une province ou une région" value={q}
        onChange={(e) => { setQ(e.target.value); setI(0); }}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') { e.preventDefault(); setI((x) => Math.min(res.length - 1, x + 1)); }
          if (e.key === 'ArrowUp') { e.preventDefault(); setI((x) => Math.max(0, x - 1)); }
          if (e.key === 'Enter' && res[i]) choisir(res[i]);
          if (e.key === 'Escape') setQ('');
        }} />
      <kbd>/</kbd>
      {res.length > 0 && <ul className="resultats" role="listbox">{res.map((x, k) => (
        <li key={x.k} role="option" aria-selected={k === i}><button type="button" className={k === i ? 'actif' : ''} onMouseEnter={() => setI(k)} onClick={() => choisir(x)}>
          <span><Icone nom={x.sous === 'ancienne région' ? 'carte' : 'repere'} taille={16} />{x.k}</span><span className="sub">{x.sous}</span></button></li>))}</ul>}
    </div>
  );
}

export default function App() {
  const { D, e, maj, tipNode } = useApp();
  const [ouvert, setOuvert] = useState(false);
  const [aide, setAide] = useState(false);
  const [toast, setToast] = useState('');
  const [compact, setCompact] = useState(() => { try { const v = localStorage.getItem('menu-compact'); if (v != null) return v === '1'; } catch { /* rien */ } return window.innerWidth >= 768 && window.innerWidth <= 1180; });
  const basculerCompact = () => setCompact((c) => { try { localStorage.setItem('menu-compact', c ? '0' : '1'); } catch { /* rien */ } return !c; });
  const Page = PAGES[e.o];
  useEffect(() => { setOuvert(false); window.scrollTo({ top: 0 }); }, [e.o]);
  const dire = (t: string) => { setToast(t); setTimeout(() => setToast(''), 1800); };
  const partager = () => navigator.clipboard?.writeText(location.href).then(() => dire('Lien de la vue copié'), () => prompt('Copiez ce lien :', location.href));
  const equipe = D.meta.equipe.replace('_', ' ');
  return (
    <div className={`app ${ouvert ? 'menu-ouvert' : ''} ${compact ? 'compact' : ''}`}>
      <a className="saut" href="#contenu">Aller au contenu</a>
      <Sidebar ouvert={ouvert} fermer={() => setOuvert(false)} compact={compact} basculerCompact={basculerCompact} partager={partager} />
      <button type="button" className="poignee" onClick={basculerCompact} aria-label={compact ? 'Agrandir la barre latérale' : 'Réduire la barre latérale'}
        aria-expanded={!compact} data-infobulle={compact ? 'Agrandir le menu' : 'Réduire le menu'}>
        {compact ? <ChevronsRight size={16} strokeWidth={2.4} /> : <ChevronsLeft size={16} strokeWidth={2.4} />}
      </button>
      <div className="voile" onClick={() => setOuvert(false)} aria-hidden="true" />
      <div className="principal">
        <header className="barre">
          <button type="button" className="bouton-icone seulement-mobile" data-infobulle="Menu" onClick={() => setOuvert(true)} aria-label="Ouvrir le menu"><Icone nom="menu" /></button>
          <Recherche />
          <div className="barre-droite">
            <div className="aide-boite">
              <button type="button" className="bouton-rond" data-infobulle="Aide et raccourcis" onClick={() => setAide((a) => !a)} aria-expanded={aide} aria-label="Aide"><Icone nom="aide" /></button>
              {aide && <div className="aide-pop" role="dialog" aria-label="Aide">
                <b>Utiliser l'outil</b>
                <ul><li><kbd>/</kbd> rechercher une province ou une région</li><li><kbd>↑</kbd> <kbd>↓</kbd> changer de partie dans le menu</li>
                  <li>Cliquer une province sur une carte ouvre sa fiche</li><li>« Partager la vue » copie un lien qui rouvre exactement cet écran</li></ul>
                <button type="button" className="lien" onClick={() => { setAide(false); maj({ o: 'methode' }); }}>Lexique et méthode</button>
              </div>}
            </div>
          </div>
          {toast && <span className="toast" role="status">{toast}</span>}
        </header>
        <main id="contenu" key={e.o} className="contenu apparition"><Page /></main>
        <footer className="pied">Data Challenge Burkina 2026 · Défi 2 · équipe {equipe} · données agrégées et publiques (DGESS, INSD, COD-AB) · un écart ne dit pas sa cause.</footer>
      </div>
      {tipNode}
    </div>
  );
}
