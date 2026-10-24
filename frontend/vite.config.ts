import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8001',
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: (id: string) => {
          if (id.includes('node_modules')) {
            if (id.includes('react') || id.includes('react-dom') || id.includes('react-router')) {
              return 'vendor';
            }
            if (id.includes('maplibre') || id.includes('deck.gl') || id.includes('@deck.gl')) {
              return 'map';
            }
            if (id.includes('plotly') || id.includes('react-plotly')) {
              return 'charts';
            }
            if (id.includes('zustand') || id.includes('@tanstack')) {
              return 'state';
            }
            if (id.includes('lucide') || id.includes('clsx') || id.includes('tailwind-merge')) {
              return 'ui';
            }
            return 'vendor';
          }
        },
      },
    },
  },
  define: {
    'process.env': {},
  },
})