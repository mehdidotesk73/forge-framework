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
    port: 5176,
    proxy: {
      "/api": "http://localhost:4176",
      "/endpoints": "http://localhost:4176",
    },
  },
});
