import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import { viteSingleFile } from 'vite-plugin-singlefile';
import fs from 'node:fs';
import path from 'node:path';

/** Mode "autonome" : les donnees du pipeline sont embarquees dans une seule page HTML qui marche sans serveur ni Internet. */
function donneesEmbarquees(): Plugin {
  return {
    name: 'donnees-embarquees',
    transformIndexHtml(html) {
      const dossier = path.resolve(__dirname, '..', '..', '04_analyse');
      const f = fs.readdirSync(dossier).filter((n) => n.endsWith('_donnees-plateforme_v1.json')).sort()[0];
      if (!f) throw new Error('Donnees introuvables dans 04_analyse : lancez le pipeline (etape dashboard).');
      const json = fs.readFileSync(path.join(dossier, f), 'utf-8').replace(/</g, '\\u003c');
      return html.replace('<!--DONNEES-->', `<script>window.__DONNEES__=${json}</script>`);
    },
  };
}

export default defineConfig(({ mode }) => ({
  base: './',
  plugins: mode === 'autonome' ? [react(), donneesEmbarquees(), viteSingleFile()] : [react()],
  build: { outDir: mode === 'autonome' ? 'dist-autonome' : 'dist', emptyOutDir: true, chunkSizeWarningLimit: 900 },
  server: { proxy: { '/api': 'http://127.0.0.1:3000' } },
}));
