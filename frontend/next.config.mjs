/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // Os testes de tela (Playwright) usam outra pasta: um `next dev` em `.next`
  // apaga o build de produção (`.next/standalone`) de onde o portal roda.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  // ...e outro tsconfig, para o `next dev` de teste não reescrever o tsconfig.json.
  typescript: { tsconfigPath: process.env.NEXT_TSCONFIG || "tsconfig.json" },
  
  // Otimizações para desenvolvimento
  // NEXT_SEM_CACHE=1: build sem o cache do webpack (centenas de MB), para disco quase cheio.
  webpack: (config, { isServer }) => {
    if (process.env.NEXT_SEM_CACHE) config.cache = false;
    
    // Reduz paralelismo para evitar travamento
    config.parallelism = 1;
    
    return config;
  },

  experimental: {
    // Desabilitado: causa travamento no build em algumas máquinas
    // optimizePackageImports: ['lucide-react'],
  },
};

export default nextConfig;
