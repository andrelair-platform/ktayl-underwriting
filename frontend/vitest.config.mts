import { fileURLToPath } from "url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  // Override PostCSS inline so vite does NOT load the project's Tailwind v4 postcss.config.mjs
  // (its string-plugin form isn't a valid vite PostCSS plugin). Tests don't need styles.
  css: { postcss: { plugins: [] } },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/**/*.test.{ts,tsx}"],
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
});
