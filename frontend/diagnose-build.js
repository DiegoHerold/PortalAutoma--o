const { exec } = require('child_process');
const os = require('os');

console.log('=== Diagnóstico do Build ===\n');

// 1. Informações do sistema
console.log('Sistema:');
console.log(`- OS: ${os.platform()} ${os.release()}`);
console.log(`- CPU: ${os.cpus()[0].model} (${os.cpus().length} cores)`);
console.log(`- RAM Total: ${(os.totalmem() / 1024 / 1024 / 1024).toFixed(2)} GB`);
console.log(`- RAM Livre: ${(os.freemem() / 1024 / 1024 / 1024).toFixed(2)} GB`);
console.log(`- Node: ${process.version}`);
console.log();

// 2. Verificar espaço em disco
console.log('Verificando espaço em disco...');
exec('wmic logicaldisk get size,freespace,caption', (error, stdout) => {
  if (!error) {
    console.log(stdout);
  }
});

// 3. Testar build com verbose
console.log('\n=== Iniciando build com logs detalhados ===\n');
console.log('Pressione Ctrl+C se travar por mais de 2 minutos\n');

const buildProcess = exec('npx next build --debug', { 
  maxBuffer: 1024 * 1024 * 10,
  env: { ...process.env, SKIP_OPTIMIZE: '1' },
  shell: true
});

let lastOutput = Date.now();
const timeout = setInterval(() => {
  const elapsed = Math.floor((Date.now() - lastOutput) / 1000);
  if (elapsed > 10) {
    console.log(`⏱️  Sem output há ${elapsed}s...`);
  }
}, 5000);

buildProcess.stdout.on('data', (data) => {
  lastOutput = Date.now();
  console.log(data.toString());
});

buildProcess.stderr.on('data', (data) => {
  lastOutput = Date.now();
  console.error('STDERR:', data.toString());
});

buildProcess.on('close', (code) => {
  clearInterval(timeout);
  console.log(`\nBuild finalizado com código ${code}`);
  process.exit(code);
});

buildProcess.on('error', (error) => {
  clearInterval(timeout);
  console.error('Erro ao executar build:', error);
  process.exit(1);
});
