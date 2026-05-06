import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, '.', '');
    return {
      server: {
        port: 3000,
        host: '0.0.0.0',
        watch: {
          ignored: ['**/.venv/**', '**/node_modules/**', '**/gunivox.db', '**/logs/**'],
        },
        // Proxy API calls to the Python backend during local dev
        proxy: {
          '/api': 'http://localhost:8000',
          '/vobiz-answer': 'http://localhost:8000',
          '/vobiz-respond': 'http://localhost:8000',
          '/vobiz-silent': 'http://localhost:8000',
          '/status': 'http://localhost:8000',
          '/static': 'http://localhost:8000',
        },
      },
      build: {
        outDir: 'dist',
        emptyOutDir: true,
      },
      plugins: [react()],
      define: {
        'process.env.API_KEY': JSON.stringify(env.GEMINI_API_KEY),
        'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY)
      },
      resolve: {
        alias: {
          '@': path.resolve(__dirname, '.'),
        }
      }
    };
});
