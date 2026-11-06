// Vite builds the React app into frontend/dist, which FastAPI serves under /app (app/main.py).
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/app/",                 // the pages live under /app until step 5.10 (the Jinja pages stay at /)
  server: {
    proxy: { "/api": "http://127.0.0.1:8000" },   // npm run dev: send /api to uvicorn
  },
});
