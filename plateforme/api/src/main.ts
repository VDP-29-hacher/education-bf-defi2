import 'reflect-metadata';
import { Module } from '@nestjs/common';
import { NestFactory } from '@nestjs/core';
import type { NestExpressApplication } from '@nestjs/platform-express';
import * as fs from 'fs';
import * as path from 'path';
import { ApiController } from './api.controller';
import { DonneesService } from './donnees.service';

@Module({ controllers: [ApiController], providers: [DonneesService] })
class AppModule {}

async function demarrer() {
  const app = await NestFactory.create<NestExpressApplication>(AppModule, { logger: ['log', 'warn', 'error'] });
  app.enableCors({ origin: true, methods: ['GET'] });
  // L'interface React compilee (web/dist) est servie par la meme application : une seule commande, une seule adresse.
  const web = path.resolve(__dirname, '..', '..', 'web', 'dist');
  if (fs.existsSync(web)) {
    app.useStaticAssets(web);
    app.use((req: any, res: any, next: any) => (req.method === 'GET' && !req.path.startsWith('/api') && !path.extname(req.path) ? res.sendFile(path.join(web, 'index.html')) : next()));
  }
  const port = Number(process.env.PORT || 3000);
  await app.listen(port, '127.0.0.1');
  console.log(`\nPlateforme Defi 2 : http://localhost:${port}   (API : http://localhost:${port}/api/sante)`);
  if (!fs.existsSync(web)) console.log("Interface non compilee : lancez 'npm run build' dans plateforme/web (l'API fonctionne seule).");
}
demarrer();
