import { Injectable, Logger, NotFoundException, BadRequestException } from '@nestjs/common';
import * as fs from 'fs';
import * as path from 'path';

/**
 * Charge le fichier de donnees agregees produit par le pipeline Python
 * (04_analyse/<EQUIPE>_04-analyse_D2_analyst_donnees-plateforme_v1.json) et le recharge a chaque relance du pipeline.
 * Aucune donnee brute ni individuelle : uniquement des tables agregees par region et par province.
 */
type Num = number | null;
export interface Fiche {
  province: string; region: string; priorite: 0 | 1 | 2; ips: Num; ipsUrbain: Num; ipsRural: Num; ecartUrbainRural: Num;
  effectifsSurMax: Num; elevesPerdus: Num; fillesAInscrire: Num; tbs: Num; profil: string | null;
  historiqueIps: Num[]; historiqueEffectifs: Num[] | null; prevision: unknown; signalements: unknown[];
}

@Injectable()
export class DonneesService {
  private readonly log = new Logger('Donnees');
  private d: any = null;
  fichier = '';
  chargeLe = '';

  constructor() {
    this.fichier = this.trouver();
    this.charger();
    fs.watchFile(this.fichier, { interval: 2000 }, () => { this.log.log('Fichier modifie par le pipeline : rechargement'); this.charger(); });
  }

  private trouver(): string {
    if (process.env.DONNEES) return path.resolve(process.env.DONNEES);
    const candidats = [path.resolve(__dirname, '..', '..', '..', '04_analyse'), path.resolve(process.cwd(), '..', '..', '04_analyse'), path.resolve(process.cwd(), '04_analyse')];
    for (const dossier of candidats) {
      if (!fs.existsSync(dossier)) continue;
      const f = fs.readdirSync(dossier).filter((n) => n.endsWith('_donnees-plateforme_v1.json')).sort();
      if (f.length) return path.join(dossier, f[0]);
    }
    throw new Error("Donnees introuvables : lancez d'abord le pipeline (etape dashboard) ou definissez DONNEES=chemin du JSON");
  }

  private charger() {
    this.d = JSON.parse(fs.readFileSync(this.fichier, 'utf-8'));
    this.chargeLe = new Date().toISOString();
    this.log.log(`${path.basename(this.fichier)} : ${this.d.prov?.names?.length ?? 0} provinces, ${this.d.regions.length} regions, ${this.d.years.length} annees`);
  }

  get tout() { return this.d; }
  private get N() { return this.d.years.length; }

  sante() {
    return { ok: true, fichier: path.basename(this.fichier), chargeLe: this.chargeLe, genereLe: this.d.meta?.date, equipe: this.d.meta?.equipe,
      provinces: this.d.prov?.names?.length ?? 0, regions: this.d.regions.length, annees: this.d.years };
  }

  regions(niveau = 'pri', annee?: number) {
    if (!['pri', 'pre', 'cp1'].includes(niveau)) throw new BadRequestException("niveau : pri, pre ou cp1");
    const i = annee === undefined ? this.N - 1 : this.d.years.indexOf(annee);
    if (i < 0) throw new BadRequestException(`annee inconnue ; disponibles : ${this.d.years.join(', ')}`);
    const s = this.d[niveau];
    return {
      niveau, annee: this.d.years[i], national: this.d.nat[niveau][i],
      regions: this.d.regions.map((r: string) => ({ region: r, ips: s[r][i], ips2015: s[r][0], variation: s[r][i] != null && s[r][0] != null ? +(s[r][i] - s[r][0]).toFixed(4) : null }))
        .sort((a: any, b: any) => (a.ips ?? 9) - (b.ips ?? 9)),
    };
  }

  private profils(): Record<string, any> { const t: Record<string, any> = {}; (this.d.typo?.rows ?? []).forEach((x: any) => (t[x.p] = x)); return t; }
  private tbs(): Record<string, any> { const t: Record<string, any> = {}; (this.d.ptbs?.rows ?? []).forEach((x: any) => (t[x.p] = x)); return t; }

  /** Regle de priorite du dossier, avec des seuils reglables : P1 = les deux seuils franchis, P2 = un seul. */
  priorites(seuilIps = 0.95, seuilAcces = 0.6) {
    if (!(seuilIps >= 0.5 && seuilIps <= 1.2) || !(seuilAcces >= 0 && seuilAcces <= 1)) throw new BadRequestException('ips entre 0,5 et 1,2 ; acces entre 0 et 1');
    const P = this.d.prov, n1 = this.N - 1;
    const liste = P.names.map((n: string) => {
      const i = P.ind[n], ip = P.hist[n][n1], c1 = ip != null && ip < seuilIps, c2 = i.effectif_dernier_sur_max != null && i.effectif_dernier_sur_max < seuilAcces;
      return { province: n, region: i.region, priorite: c1 && c2 ? 1 : c1 || c2 ? 2 : 0, ips: ip, effectifsSurMax: i.effectif_dernier_sur_max,
        elevesPerdus: i.eleves_perdus_depuis_max, fillesAInscrire: i.filles_manquantes_parite };
    }).filter((o: any) => o.priorite).sort((a: any, b: any) => a.priorite - b.priorite || (a.ips ?? 9) - (b.ips ?? 9));
    const p1 = liste.filter((o: any) => o.priorite === 1), som = (k: string) => p1.reduce((t: number, o: any) => t + (o[k] || 0), 0);
    return { seuils: { ips: seuilIps, acces: seuilAcces }, priorite1: p1.length, priorite2: liste.length - p1.length,
      elevesPerdusP1: som('elevesPerdus'), fillesAInscrireP1: som('fillesAInscrire'), provinces: liste };
  }

  provinces(): Fiche[] { return this.d.prov.names.map((n: string) => this.fiche(n)); }

  fiche(nom: string): Fiche {
    const P = this.d.prov, n = P.names.find((x: string) => x.localeCompare(nom, 'fr', { sensitivity: 'base' }) === 0);
    if (!n) throw new NotFoundException(`Province inconnue : ${nom}`);
    const i = P.ind[n], ip = P.hist[n][this.N - 1], pr = this.priorites().provinces.find((o: any) => o.province === n), ty = this.profils()[n], tb = this.tbs()[n];
    return { province: n, region: i.region, priorite: (pr?.priorite ?? 0) as 0 | 1 | 2, ips: ip, ipsUrbain: i.ips_urbain, ipsRural: i.ips_rural,
      ecartUrbainRural: i.ecart_urbain_moins_rural, effectifsSurMax: i.effectif_dernier_sur_max, elevesPerdus: i.eleves_perdus_depuis_max,
      fillesAInscrire: i.filles_manquantes_parite, tbs: tb ? tb.t : null, profil: ty ? `${ty.g}. ${ty.nom}` : null, historiqueIps: P.hist[n],
      historiqueEffectifs: P.eff?.[n] ?? null, prevision: P.prev?.[n] ? { annees: P.prevAns, ...P.prev[n] } : null,
      signalements: (P.sig ?? []).filter((s: any) => s.province === n) };
  }

  /** Exports CSV (separateur ; , virgule decimale, BOM UTF-8 pour Excel). */
  csv(table: string, seuilIps?: number, seuilAcces?: number): string {
    const q = (v: unknown) => v == null ? '' : typeof v === 'number' ? String(v).replace('.', ',') : `"${String(v).replace(/"/g, '""')}"`;
    const out = (ent: string[], lig: unknown[][]) => '﻿' + [ent.join(';'), ...lig.map((l) => l.map(q).join(';'))].join('\r\n');
    const ya = (y: number) => `${y}/${String(y + 1).slice(2)}`;
    if (table === 'provinces') return out(['province', 'ancienne_region', 'priorite', 'ips', 'ips_urbain', 'ips_rural', 'ecart_urbain_moins_rural', 'effectifs_sur_max', 'eleves_perdus', 'filles_a_inscrire', 'tbs_insd', 'profil'],
      this.provinces().map((f) => [f.province, f.region, f.priorite, f.ips, f.ipsUrbain, f.ipsRural, f.ecartUrbainRural, f.effectifsSurMax, f.elevesPerdus, f.fillesAInscrire, f.tbs, f.profil]));
    if (table === 'priorites') { const p = this.priorites(seuilIps, seuilAcces); return out(['province', 'ancienne_region', 'priorite', 'ips', 'effectifs_sur_max', 'eleves_perdus', 'filles_a_inscrire', 'seuil_ips', 'seuil_acces'],
      p.provinces.map((o: any) => [o.province, o.region, o.priorite, o.ips, o.effectifsSurMax, o.elevesPerdus, o.fillesAInscrire, p.seuils.ips, p.seuils.acces])); }
    if (table === 'regions') return out(['region', 'niveau', ...this.d.years.map(ya)], ['pri', 'pre', 'cp1'].flatMap((nv) =>
      [...this.d.regions.map((r: string) => [r, nv, ...this.d[nv][r]]), ['National', nv, ...this.d.nat[nv]]]));
    if (table === 'prevision') { const A: number[] = this.d.prov.prevAns ?? []; return out(['province', 'modele', 'statut', ...A.flatMap((y) => [`ips_${y}`, `bas80_${y}`, `haut80_${y}`])],
      Object.entries<any>(this.d.prov.prev ?? {}).map(([n, p]) => [n, p.modele, p.statut, ...A.flatMap((_, k) => [p.v[k], p.lo[k], p.hi[k]])])); }
    throw new NotFoundException('Tables : provinces, priorites, regions, prevision');
  }
}
