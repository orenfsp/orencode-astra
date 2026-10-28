import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// API проксируется на backend, поэтому сайт и API живут на одном адресе и cookie сессии работают
// одинаково на localhost и 127.0.0.1. Адрес backend меняется переменной BACKEND_URL.
const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8002";

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": { target: backend, changeOrigin: true } } },
  preview: { proxy: { "/api": { target: backend, changeOrigin: true } } },
});
