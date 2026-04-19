import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@forge-framework/ts": resolve(__dirname, "../../../../packages/forge-ts/src/index.ts"),
    },
  },
  server: {
    port: 5174,
    proxy: {
      "/api": "http://localhost:8000",
      "/endpoints": "http://localhost:8000",
    },
  },
});
