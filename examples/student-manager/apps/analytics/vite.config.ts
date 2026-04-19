import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": `http://localhost:${process.env.VITE_API_PORT || "8000"}`,
      "/endpoints": `http://localhost:${process.env.VITE_API_PORT || "8000"}`,
    },
  },
});
