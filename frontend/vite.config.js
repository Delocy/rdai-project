import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/search": "http://localhost:8000",
      "/ingest": "http://localhost:8000",
      "/images": "http://localhost:8000",
    },
  },
});
