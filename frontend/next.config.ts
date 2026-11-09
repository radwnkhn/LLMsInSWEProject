import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Browser tests build separately so they do not overwrite a running dev server's files.
  distDir: process.env.NEXT_BUILD_DIR || ".next",
};

export default nextConfig;
