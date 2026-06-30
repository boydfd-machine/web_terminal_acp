import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { readFileSync } from "node:fs";
import { pageAnnotationPlugin } from "./vite-plugin-page-annotation";

const packageJson = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf8")) as {
  version?: string;
};
const clientVersion = (packageJson.version ?? "dev").replace(/[^0-9A-Za-z._-]/g, "_");

export default defineConfig({
  plugins: [react(), pageAnnotationPlugin()],
  // Absolute base so /clients/.../terminals/... deep links load static assets from the app root.
  // Version the app-specific directory so stale gateway cache entries cannot poison a new client build.
  base: "/",
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/minio": {
        target: "http://127.0.0.1:19000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/minio/, ""),
      },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    assetsDir: `web-terminal-assets/v${clientVersion}`,
  },
});
