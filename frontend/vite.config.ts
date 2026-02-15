import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    cors: true,
    origin: "http://localhost:5173",
    proxy: {
      "/api": "http://localhost:8150",
      "/report": "http://localhost:8150",
    },
  },
  build: {
    outDir: path.resolve(__dirname, "../bristlenose/server/static"),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: path.resolve(__dirname, "index.html"),
        "visual-diff": path.resolve(__dirname, "visual-diff.html"),
      },
    },
  },
});
