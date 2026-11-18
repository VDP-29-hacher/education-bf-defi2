/* Icones animees : bibliotheque Lucide (embarquee, aucun fichier externe).
   Chaque icone a deux couches superposees et centrees : l'icone de base et une variante. Au survol (ou au focus clavier) de
   l'element qui la contient, la base s'efface progressivement et la variante apparait avec une animation propre a la fonction
   de l'icone (styles.css, section "icones animees"). Aucune icone ne disparait definitivement : quand le curseur quitte la
   zone, tout revient a l'etat initial. */
import {
  ArrowDownToLine, ArrowRight, CalendarCheck, CalendarDays, ChartColumnBig, ChartColumnIncreasing, ChartSpline, CircleCheck, CircleCheckBig,
  CircleHelp, Compass, Crosshair, Database, DatabaseZap, Download, FileChartColumn, FileChartLine, FileCheck, FileText, GraduationCap, House,
  HousePlus, Layers, Layers2, LayoutDashboard, LayoutGrid, Lightbulb, Link, Link2, LocateFixed, Map, MapPin, MapPinned, Menu, MessageCircleQuestion,
  Minus, Moon, MoonStar, MoveRight, Navigation, Pause, Play, Plus, Printer, PrinterCheck, School, Search, SearchCheck, Settings, Settings2, Share,
  Share2, Sheet, Sun, SunMedium, Table2, Target, TrendingUp, Users, UsersRound, X, ZoomIn, ZoomOut, type LucideIcon,
} from 'lucide-react';

/** nom : [icone de base, variante au survol, famille d'animation] */
const ICONES: Record<string, [LucideIcon, LucideIcon, string]> = {
  accueil: [House, HousePlus, 'echelle'],
  analyse: [ChartColumnBig, ChartColumnIncreasing, 'barres'],
  tdb: [LayoutDashboard, LayoutGrid, 'echelle'],
  carte: [Map, MapPinned, 'marqueur'],
  decision: [Compass, Navigation, 'pivot'],
  prevision: [TrendingUp, ChartSpline, 'trace'],
  methode: [Database, DatabaseZap, 'pile'],
  recherche: [Search, SearchCheck, 'pivot'],
  lien: [Link2, Link, 'pivot'],
  partager: [Share2, Share, 'pivot'],
  imprimer: [Printer, PrinterCheck, 'pile'],
  telecharger: [Download, ArrowDownToLine, 'fleche-bas'],
  lune: [Moon, MoonStar, 'pivot'],
  soleil: [Sun, SunMedium, 'pivot'],
  menu: [Menu, Menu, 'echelle'],
  fermer: [X, X, 'echelle'],
  fleche: [ArrowRight, MoveRight, 'fleche-droite'],
  lecture: [Play, Play, 'echelle'],
  pause: [Pause, Pause, 'echelle'],
  fiche: [FileText, FileCheck, 'trace'],
  rapport: [FileChartColumn, FileChartLine, 'trace'],
  repere: [MapPin, LocateFixed, 'localise'],
  groupe: [Users, UsersRound, 'silhouettes'],
  diplome: [GraduationCap, GraduationCap, 'mortier'],
  ecole: [School, School, 'echelle'],
  couches: [Layers, Layers2, 'pile'],
  cible: [Target, Crosshair, 'pulse'],
  coche: [CircleCheck, CircleCheckBig, 'trace'],
  aide: [CircleHelp, MessageCircleQuestion, 'pivot'],
  reglages: [Settings, Settings2, 'engrenage'],
  plus: [Plus, ZoomIn, 'echelle'],
  moins: [Minus, ZoomOut, 'echelle'],
  recentrer: [LocateFixed, Crosshair, 'pulse'],
  grille: [Table2, Sheet, 'echelle'],
  calendrier: [CalendarDays, CalendarCheck, 'trace'],
  ampoule: [Lightbulb, Lightbulb, 'pulse'],
};

export function Icone({ nom, taille = 20 }: { nom: string; taille?: number }) {
  const [Base, Variante, anim] = ICONES[nom] ?? [CircleHelp, CircleHelp, 'echelle'];
  return (
    <span className={`ico a-${anim}`} style={{ width: taille, height: taille }} aria-hidden="true">
      <Base className="icone ico-base" size={taille} strokeWidth={1.9} />
      <Variante className="icone ico-var" size={taille} strokeWidth={2.1} />
    </span>
  );
}
