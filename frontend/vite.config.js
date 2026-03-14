import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: '/splash_links/',
  server: {
    proxy: {
      '/splash_links': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
});
