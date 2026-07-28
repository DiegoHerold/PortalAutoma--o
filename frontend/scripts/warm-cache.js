// Script para pré-compilar rotas comuns
const http = require('http');

const routes = [
  '/',
  '/dashboard',
  '/login',
  '/automations',
  '/jobs',
  '/executions',
  '/workers',
  '/triggers',
  '/schedules',
  '/categories',
  '/users',
];

async function warmRoute(route) {
  return new Promise((resolve) => {
    const options = {
      hostname: 'localhost',
      port: 3000,
      path: route,
      method: 'GET',
    };

    const req = http.request(options, (res) => {
      console.log(`✓ Warmed ${route}`);
      resolve();
    });

    req.on('error', () => {
      console.log(`✗ Failed to warm ${route}`);
      resolve();
    });

    req.setTimeout(30000, () => {
      req.destroy();
      resolve();
    });

    req.end();
  });
}

async function warmCache() {
  console.log('🔥 Warming up cache for all routes...\n');
  
  for (const route of routes) {
    await warmRoute(route);
    await new Promise(r => setTimeout(r, 1000)); // Espera 1s entre requests
  }
  
  console.log('\n✨ Cache warming complete!');
}

// Espera o servidor estar pronto
setTimeout(() => {
  warmCache().catch(console.error);
}, 15000); // 15s após o servidor iniciar
