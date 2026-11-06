// Vite builds the React app into frontend/dist, which FastAPI serves at / (app/main.py).
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/",                     // the pages live at / since step 5.10 (the Jinja pages are gone)
  server: {
    proxy: { "/api": "http://127.0.0.1:8000" },   // npm run dev: send /api to uvicorn
  },
});
