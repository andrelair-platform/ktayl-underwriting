import type { NextConfig } from "next";

// output: 'standalone' → a self-contained server.js (small runtime image, no node_modules copy).
// The backend API URL is read at RUNTIME (server-side only) via process.env.API_URL — never baked —
// so one image serves dev and prod (Kargo promotes the same artifact). The browser never calls the
// backend directly: it talks same-origin to this Next.js BFF (server components + server actions),
// which reaches the API server-side. That keeps the API off the public surface and the image env-agnostic.
const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
};

export default nextConfig;
