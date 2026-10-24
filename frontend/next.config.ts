import type { NextConfig } from "next";

const dev = process.env.NODE_ENV === "development";

const config: NextConfig = {
  // production: plain static files served by Caddy; there is no Node server
  output: dev ? undefined : "export",
  trailingSlash: true,
  images: { unoptimized: true },
  // local development: the API runs separately on :8000 (in production Caddy does this)
  ...(dev ? { rewrites: async () => [{ source: "/api/:path*", destination: "http://127.0.0.1:8000/api/:path*" }] } : {}),
};

export default config;
