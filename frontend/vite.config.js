import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The dev server proxies /api to FastAPI so the HttpOnly session cookie is same-origin.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react(), tailwindcss()],
    build: { chunkSizeWarningLimit: 1200 },
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        "/api": { target: env.VITE_BACKEND_URL || "http://localhost:8000", changeOrigin: false },
      },
    },
  };
});
