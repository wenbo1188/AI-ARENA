import { defineConfig } from 'vite';

export default defineConfig({
  root: '.',
  publicDir: 'public',
  // FILM_NO_HMR=1: no live reload (export renders must not reload mid-run when a file changes)
  server: { port: 5173, strictPort: false, hmr: process.env.FILM_NO_HMR ? false : undefined },
  build: { target: 'esnext', assetsInlineLimit: 0 },
});
