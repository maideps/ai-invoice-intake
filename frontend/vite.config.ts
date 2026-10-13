/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";

// The app calls the API under /api; in development Vite forwards those calls to FastAPI,
// so the browser sees one origin and no CORS setup is needed.
const API_TARGET = process.env.INVOICE_INTAKE_API_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  build: {
    rollupOptions: {
      output: {
        // Libraries change less often than the app: separate chunks stay cached across deploys.
        // Matched by path so sub-entries such as react-dom/client land in the right chunk.
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (/node_modules\/(react|react-dom|react-router|scheduler)\//.test(id)) return "react";
          if (/node_modules\/(@tanstack|openapi-fetch)\//.test(id)) return "data";
          if (/node_modules\/(motion|motion-dom|motion-utils|framer-motion)\//.test(id)) return "motion";
          return "vendor";
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: API_TARGET,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
        // When FastAPI is not running, answer like a production proxy would (502) instead of
        // Vite's default 500, so the app can say "can't reach the API" rather than "server error".
        configure: (proxy) => {
          proxy.on("error", (_error, _request, response) => {
            if (!("writeHead" in response) || response.headersSent) return;
            response.writeHead(502, { "Content-Type": "application/json" });
            response.end(JSON.stringify({ detail: "The API is not running" }));
          });
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    restoreMocks: true,
  },
});
