/* Barre laterale : logo, navigation principale, menu OUTILS deroulant, etat de l'API. Composants reutilisables. */
import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { ChevronDown, PanelLeftClose, PanelLeftOpen, X } from 'lucide-react';
import { ONGLETS, useApp, type Onglet } from './contexte';
import { Icone } from './icones';
import { LogoComplet, Symbole } from './Logo';

const lire = (k: string, d: boolean) => { try { const v = localStorage.getItem(k); return v == null ? d : v === '1'; } catch { return d; } };
const ecrire = (k: string, v: boolean) => { try { localStorage.setItem(k, v ? '1' : '0'); } catch { /* stockage indisponible */ } };

/** Une rubrique de navigation (onglet) ou une action. */
function Rubrique({ icone, libelle, actif, onClick, role = 'button', tabIndex }: {
  icone: string; libelle: string; actif?: boolean; onClick: () => void; role?: string; tabIndex?: number;
}) {
  return (
    <button type="button" role={role} aria-selected={role === 'tab' ? !!actif : undefined} aria-current={actif ? 'page' : undefined} tabIndex={tabIndex}
      className={`rubrique ${actif ? 'active' : ''}`} onClick={onClick} data-infobulle={libelle}>
      <span className="rubrique-indic" aria-hidden="true" /><Icone nom={icone} taille={20} /><span className="rubrique-texte">{libelle}</span>
    </button>
  );
}

/** Menu deroulant (hauteur et opacite animees, fleche pivotante, etat memorise). */
function Deroulant({ titre, ouvert, basculer, children }: { titre: string; ouvert: boolean; basculer: () => void; children: ReactNode }) {
  return (
    <div className={`deroulant ${ouvert ? 'ouvert' : ''}`}>
      <button type="button" className="deroulant-titre" aria-expanded={ouvert} aria-controls="outils-liste" onClick={basculer}>
        <span>{titre}</span><ChevronDown className="chevron" size={18} strokeWidth={2.2} aria-hidden="true" />
      </button>
      <div className="deroulant-corps" id="outils-liste" inert={!ouvert}><div className="deroulant-interieur">{children}</div></div>
    </div>
  );
}

/** Etat de l'API : verifie /api/sante toutes les 30 s quand l'interface est servie par l'API. */
function StatutApi() {
  const { D, source } = useApp();
  const [etat, setEtat] = useState<'ok' | 'perdu' | 'autonome'>(source === 'api' ? 'ok' : 'autonome');
  useEffect(() => {
    if (source !== 'api') return;
    const verifier = () => fetch('api/sante', { cache: 'no-store' }).then((r) => setEtat(r.ok ? 'ok' : 'perdu'), () => setEtat('perdu'));
    const t = setInterval(verifier, 30000); window.addEventListener('online', verifier); window.addEventListener('offline', verifier);
    return () => { clearInterval(t); window.removeEventListener('online', verifier); window.removeEventListener('offline', verifier); };
  }, [source]);
  const txt = etat === 'ok' ? 'API NestJS connectée' : etat === 'perdu' ? 'Connexion à l’API perdue' : 'Mode autonome (sans serveur)';
  return (
    <div className={`statut-api ${etat}`} role="status" data-infobulle={txt}>
      <span className="point" aria-hidden="true" />
      <div className="statut-texte"><b>{txt}</b><small>{etat === 'perdu' ? 'Les chiffres affichés restent ceux du dernier chargement.' : `Données du ${D.meta.date.split('-').reverse().join('/')}`}</small></div>
    </div>
  );
}

export default function Sidebar({ ouvert, fermer, compact, basculerCompact, partager }: {
  ouvert: boolean; fermer: () => void; compact: boolean; basculerCompact: () => void; partager: () => void;
}) {
  const { e, maj, basculerTheme, theme } = useApp();
  const [outils, setOutils] = useState(() => lire('outils-ouvert', true));
  const nav = useRef<HTMLElement>(null);
  const basculerOutils = () => setOutils((v) => { ecrire('outils-ouvert', !v); return !v; });
  const aller = (o: Onglet) => { maj({ o }); fermer(); };
  const clavier = (ev: KeyboardEvent) => {
    const i = ONGLETS.findIndex((o) => o.id === e.o), d = ({ ArrowDown: 1, ArrowUp: -1 } as Record<string, number>)[ev.key];
    if (!d) return;
    ev.preventDefault();
    const j = (i + d + ONGLETS.length) % ONGLETS.length;
    maj({ o: ONGLETS[j].id });
    (nav.current?.querySelectorAll('[role=tab]')[j] as HTMLButtonElement | undefined)?.focus();
  };
  return (
    <aside className="menu" aria-label="Menu principal">
      <div className="menu-tete">
        <span className="logo-large"><LogoComplet /></span>
        <span className="logo-compact"><Symbole taille={42} /></span>
        <button type="button" className="menu-fermer" onClick={fermer} aria-label="Fermer le menu"><X size={20} /></button>
      </div>
      <p className="menu-section">Navigation principale</p>
      <nav ref={nav} role="tablist" aria-orientation="vertical" aria-label="Parties de l'outil" onKeyDown={clavier} className="menu-nav">
        {ONGLETS.map((o) => <Rubrique key={o.id} role="tab" icone={o.id} libelle={o.id === 'methode' ? 'Méthodes et données' : o.lib} actif={e.o === o.id}
          tabIndex={e.o === o.id ? 0 : -1} onClick={() => aller(o.id)} />)}
      </nav>
      <div className="menu-sep" />
      <Deroulant titre="Outils" ouvert={outils || compact} basculer={basculerOutils}>
        <Rubrique icone="rapport" libelle="Rapport (PDF)" onClick={() => { fermer(); setTimeout(() => window.print(), 250); }} />
        <Rubrique icone="telecharger" libelle="Exports CSV" onClick={() => aller('methode')} />
        <Rubrique icone="partager" libelle="Partager la vue" onClick={partager} />
        <Rubrique icone={theme === 'clair' ? 'lune' : 'soleil'} libelle={theme === 'clair' ? 'Thème sombre' : 'Thème clair'} onClick={basculerTheme} />
      </Deroulant>
      <div className="menu-pied">
        <StatutApi />
        <button type="button" className="menu-reduire" onClick={basculerCompact} aria-label={compact ? 'Agrandir le menu' : 'Réduire le menu'} data-infobulle={compact ? 'Agrandir le menu' : 'Réduire le menu'}>
          {compact ? <PanelLeftOpen size={19} /> : <PanelLeftClose size={19} />}<span>{compact ? 'Agrandir' : 'Réduire le menu'}</span>
        </button>
      </div>
    </aside>
  );
}
