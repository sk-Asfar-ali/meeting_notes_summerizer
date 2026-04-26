/* Vite config for the React frontend. */

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // During development, forward /api calls to the FastAPI backend.
      "/api": "http://127.0.0.1:8000"
    }
  }
});
