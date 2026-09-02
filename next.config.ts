import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Uploaded spreadsheets can be a few MB; raise the default body size limit
  // for Server Actions / route handlers that receive the file directly.
  experimental: {
    serverActions: {
      bodySizeLimit: "10mb",
    },
  },
};

export default nextConfig;
