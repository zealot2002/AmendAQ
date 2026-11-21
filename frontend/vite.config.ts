import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    fs: {
      allow: [
        fileURLToPath(new URL(".", import.meta.url)),
        fileURLToPath(new URL("..", import.meta.url)),
      ],
    },
    port: Number(process.env.MYCS_WEB_PORT || 5180),
    proxy: {
      "/api": {
        target: `http://127.0.0.1:${process.env.MYCS_API_PORT || "8765"}`,
        changeOrigin: true,
      },
    },
  },
});
