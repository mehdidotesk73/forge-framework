import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5176,
    proxy: {
      "/api": `http://localhost:${process.env.VITE_API_PORT || "4176"}`,
      "/endpoints": `http://localhost:${process.env.VITE_API_PORT || "4176"}`,
    },
  },
});
