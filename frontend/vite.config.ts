import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const agentBase = env.VITE_AGENT_BASE || 'http://127.0.0.1:7401';
  console.log(`[vite] /api/v1 proxy → ${agentBase}`);

  return {
    base: './',
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 5173,
      proxy: {
        '/api/v1': {
          target: agentBase,
          changeOrigin: true,
        },
      },
    },
  };
});
