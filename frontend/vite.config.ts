import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Statyczne demo (npm run build:demo) trafia do repo, więc ma stałe nazwy plików: diff pokazuje tylko realne zmiany kodu.
const demo = process.env.VITE_DEMO === "true";
const stable = { entryFileNames: "assets/[name].js", chunkFileNames: "assets/[name].js", assetFileNames: "assets/[name][extname]" };

export default defineConfig({
  plugins: [react()],
  build: demo ? { rollupOptions: { output: stable } } : {},
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
