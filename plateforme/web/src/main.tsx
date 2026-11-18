import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { Fournisseur } from './contexte';
import type { Donnees } from './lib';
import './styles.css';

declare global { interface Window { __DONNEES__?: Donnees } }

/** Les donnees viennent de l'API NestJS ; a defaut (page autonome ouverte sans serveur), des donnees embarquees. */
async function charger(): Promise<{ D: Donnees; source: 'api' | 'autonome' }> {
  if (window.__DONNEES__) return { D: window.__DONNEES__, source: 'autonome' };   // page autonome : donnees deja embarquees
  if (location.protocol.startsWith('http')) {
    try {
      const r = await fetch('api/donnees', { headers: { Accept: 'application/json' } });
      if (r.ok) return { D: await r.json(), source: 'api' };
    } catch { /* pas d'API : mode autonome */ }
  }
  if (window.__DONNEES__) return { D: window.__DONNEES__, source: 'autonome' };
  throw new Error("Aucune donnée : lancez l'API (plateforme/lancer_plateforme.ps1) ou ouvrez la page autonome.");
}

const racine = createRoot(document.getElementById('racine')!);
charger().then(({ D, source }) => racine.render(
  <StrictMode><Fournisseur D={D} source={source}><App /></Fournisseur></StrictMode>,
)).catch((e: Error) => racine.render(<div className="erreur"><h1>Données indisponibles</h1><p>{e.message}</p></div>));
