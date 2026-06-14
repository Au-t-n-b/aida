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
        // Manager（鉴权 / 项目 CRUD / 聊天）— 精确匹配，避免吞掉 agent 子路由
        '/api/v1/auth': { target: 'http://127.0.0.1:8000', changeOrigin: true },
        '^/api/v1/projects(/my)?$': { target: 'http://127.0.0.1:8000', changeOrigin: true },
        '/api/v1/chat': { target: 'http://127.0.0.1:8000', changeOrigin: true },
        // Agent（skill / 交付预案 / 交付计划 / 产物预览等）— 其余 /api/v1 全走 agent
        '/agent': { target: agentBase, changeOrigin: true },
        '/api/v1': { target: agentBase, changeOrigin: true },
      },
    },
  };
});
