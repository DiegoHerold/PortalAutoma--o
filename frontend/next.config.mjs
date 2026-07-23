/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  
  // Otimizações para desenvolvimento
  experimental: {
    // Usa compilação otimizada
    optimizePackageImports: ['lucide-react'],
  },
};

export default nextConfig;
