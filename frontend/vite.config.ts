import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The SPA is served from the site root by default (FastAPI mounts the build
// at "/"). Set VITE_BASE_PATH (e.g. "/threatlens/") only when hosting it
// under a sub-path. Routing is hash-based, so no server rewrites are needed.
export default defineConfig(({ mode }) => {
  // Reads frontend/.env* files plus VITE_* variables from the shell.
  const env = loadEnv(mode, ".", "VITE_");
  return {
    base: env.VITE_BASE_PATH || "/",
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: "http://127.0.0.1:8000",
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: "dist",
      sourcemap: false,
      chunkSizeWarningLimit: 1200,
    },
  };
});
