/** @type {import('next').NextConfig} */
const nextConfig = {
  // 开发态：把 /api/* 代理到 FastAPI（默认 http://localhost:8000），避免 CORS
  async rewrites() {
    const backend = process.env.BACKEND_URL || "http://localhost:8000";
    return [
      { source: "/api/:path*", destination: `${backend}/api/:path*` },
    ];
  },
};

module.exports = nextConfig;
