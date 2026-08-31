import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig(({ mode }) => {
  const envDir = mode === "customer" ? false : undefined;
  const env = mode === "customer" ? {} : loadEnv(mode, ".", "");
  const proxyTarget = env.VITE_PROXY_TARGET || "http://127.0.0.1:8000";
  return {
    plugins: [vue()],
    envDir,
    server: {
      port: 5173,
      proxy: {
        "/api": proxyTarget,
        "/health": proxyTarget,
      },
    },
  };
});
