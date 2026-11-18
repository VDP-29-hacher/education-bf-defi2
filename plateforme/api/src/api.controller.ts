import { Controller, Get, Param, Query, Res, Header } from '@nestjs/common';
import type { Response } from 'express';
import { DonneesService } from './donnees.service';

const nombre = (v?: string) => (v === undefined || v === '' ? undefined : Number(String(v).replace(',', '.')));

@Controller('api')
export class ApiController {
  constructor(private readonly s: DonneesService) {}

  /** Etat du service et fichier charge. */
  @Get('sante') sante() { return this.s.sante(); }

  /** Tout le paquet de donnees agregees (utilise par l'interface au demarrage). */
  @Get('donnees') @Header('Cache-Control', 'no-cache') donnees() { return this.s.tout; }

  /** IPS par ancienne region : ?niveau=pri|pre|cp1&annee=2024 */
  @Get('regions') regions(@Query('niveau') niveau?: string, @Query('annee') annee?: string) { return this.s.regions(niveau || 'pri', nombre(annee)); }

  /** Les 45 provinces avec leurs indicateurs. */
  @Get('provinces') provinces() { return this.s.provinces(); }

  /** Fiche d'une province (historique, projection, profil, signalements). */
  @Get('provinces/:nom') fiche(@Param('nom') nom: string) { return this.s.fiche(nom); }

  /** Simulateur de ciblage : ?ips=0.95&acces=0.6 */
  @Get('priorites') priorites(@Query('ips') ips?: string, @Query('acces') acces?: string) { return this.s.priorites(nombre(ips) ?? 0.95, nombre(acces) ?? 0.6); }

  /** Export CSV : provinces, priorites (?ips=&acces=), regions, prevision */
  @Get('export/:table') export(@Param('table') table: string, @Query('ips') ips: string, @Query('acces') acces: string, @Res() res: Response) {
    const t = table.replace(/\.csv$/, ''), corps = this.s.csv(t, nombre(ips) ?? 0.95, nombre(acces) ?? 0.6);
    res.setHeader('Content-Type', 'text/csv; charset=utf-8');
    res.setHeader('Content-Disposition', `attachment; filename="${this.s.tout.meta?.equipe ?? 'equipe'}_${t}.csv"`);
    res.send(corps);
  }
}
