import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  outputFileTracingRoot: __dirname,
  allowedDevOrigins: ["http://192.168.68.101:3000"],
};

export default nextConfig;
