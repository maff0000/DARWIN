import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// DARWIN ARENA — static production bundle only. Packaged into the
// DARWIN_core image at build time; served by the existing FastAPI app.
// No Node runtime in production (PID-002 §5).
export default defineConfig({
  plugins: [react()],
  base: "/",
  build: {
    outDir: "dist",
    assetsDir: "assets",
    sourcemap: false,
  },
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
