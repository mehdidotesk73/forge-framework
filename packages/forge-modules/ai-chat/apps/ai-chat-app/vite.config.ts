import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  server: {
    port: 3001,
    proxy: {
      // Proxy all API and endpoint calls to the Forge backend during dev
      "/endpoints": "http://localhost:8000",
      "/api": "http://localhost:8000",
    },
  },
  build:
    mode === "library"
      ? {
          lib: {
            entry: "src/index.ts",
            formats: ["es", "cjs"],
            fileName: (fmt) => `index.${fmt === "es" ? "mjs" : "cjs"}`,
          },
          rollupOptions: {
            // Exclude peer deps from the bundle
            external: ["react", "react-dom", "@forge-suite/ts"],
            output: {
              globals: {
                react: "React",
                "react-dom": "ReactDOM",
                "@forge-suite/ts": "ForgeSuiteTs",
              },
            },
          },
        }
      : {
          // Regular app build for standalone dev/testing
          outDir: "dist-app",
        },
}));
