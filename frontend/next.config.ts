import type { NextConfig } from "next";

const backendUrl = process.env.NEXT_PUBLIC_API_URL?.startsWith('http')
  ? process.env.NEXT_PUBLIC_API_URL
  : 'https://traffic-simulation-production.up.railway.app';

const nextConfig: NextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  eslint: {
    ignoreDuringBuilds: true,
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
