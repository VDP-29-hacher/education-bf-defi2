/* Identite ÉDUCATION BF (SVG vectoriel, lisible des 24 px).
   Symbole : un livre ouvert (le savoir) dont la page de droite s'eleve (la progression), une etoile doree (l'excellence)
   reliee au livre par une trajectoire ascendante (l'avenir), posee sur un socle aux couleurs nationales (rouge, or, vert). */
import { useId } from 'react';

export function Symbole({ taille = 44, fond = true }: { taille?: number; fond?: boolean }) {
  const id = useId().replace(/:/g, '');
  return (
    <svg width={taille} height={taille} viewBox="0 0 48 48" role="img" aria-label="ÉDUCATION BF" className="logo-symbole">
      <defs>
        <linearGradient id={`f${id}`} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#244E86" /><stop offset="1" stopColor="#102B52" /></linearGradient>
        <linearGradient id={`p${id}`} x1="0" y1="1" x2="0" y2="0"><stop offset="0" stopColor="#DCE7F5" /><stop offset="1" stopColor="#FFFFFF" /></linearGradient>
      </defs>
      {fond && <rect x="1" y="1" width="46" height="46" rx="13" fill={`url(#f${id})`} stroke="rgba(255,255,255,.14)" />}
      {/* trajectoire ascendante vers l'etoile */}
      <path d="M12.5 21.5C15.5 15.8 19.4 12.6 22.6 11.9" fill="none" stroke="#F5B51B" strokeWidth="1.6" strokeLinecap="round" opacity=".75" />
      {/* etoile doree */}
      <path d="M27.5 6.2l1.45 3.3 3.58.32-2.71 2.37.8 3.5-3.12-1.85-3.12 1.85.8-3.5-2.71-2.37 3.58-.32z" fill="#F5B51B" />
      {/* livre ouvert : la page de droite monte */}
      <path d="M9.5 34.5c4.6-1.5 9.4-1.1 13.5 1.2V21.4c-4.1-2.3-8.9-2.7-13.5-1.2z" fill={`url(#p${id})`} />
      <path d="M25 35.7c4.1-2.3 8.9-3.9 13.5-3.6V16.7c-4.6-.4-9.4 1.2-13.5 4.7z" fill="#FFFFFF" />
      <path d="M24 21.6v14.6" stroke="#102B52" strokeWidth="1.2" strokeLinecap="round" opacity=".55" />
      <path d="M13 25.2c2.6-.6 5.2-.4 7.4.6M13 29c2.6-.6 5.2-.4 7.4.6M27.6 25.4c2.5-1.5 5.1-2.3 7.6-2.4M27.6 29.4c2.5-1.3 5.1-1.9 7.6-2" stroke="#9FB4D3" strokeWidth="1.1" strokeLinecap="round" fill="none" />
      {/* socle aux couleurs nationales */}
      <rect x="9.5" y="38.6" width="12.4" height="2.8" rx="1.4" fill="#E53935" />
      <rect x="22.6" y="38.6" width="2.8" height="2.8" rx="1.4" fill="#F5B51B" />
      <rect x="26.1" y="38.6" width="12.4" height="2.8" rx="1.4" fill="#159B65" />
    </svg>
  );
}

export function LogoComplet() {
  return (
    <div className="logo-complet">
      <Symbole taille={46} />
      <div className="logo-texte">
        <b>ÉDUCATION <span>BF</span></b>
        <small>Suivi &amp; pilotage scolaire</small>
      </div>
    </div>
  );
}
