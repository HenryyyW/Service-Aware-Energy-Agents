import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import path from 'path'
import type { Plugin } from 'vite'

function localResultsApi(): Plugin {
  const resultsRoot = path.resolve(__dirname, '..', 'results')
  const runFiles = new Map<string, string>()

  const indexRuns = (directory: string) => {
    if (!existsSync(directory)) return
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const entryPath = path.join(directory, entry.name)
      if (entry.isDirectory()) {
        indexRuns(entryPath)
      } else if (entry.name === 'result.json') {
        try {
          const result = JSON.parse(readFileSync(entryPath, 'utf8'))
          if (result.run_id) runFiles.set(result.run_id, entryPath)
        } catch {
          // Ignore incomplete result files while an experiment is writing.
        }
      }
    }
  }

  return {
    name: 'local-results-api',
    configureServer(server) {
      indexRuns(resultsRoot)
      server.middlewares.use((request, response, next) => {
        const pathname = new URL(request.url || '/', 'http://localhost').pathname
        if (request.method !== 'GET' || !pathname.startsWith('/api/simulations')) {
          next()
          return
        }

        const sendJson = (status: number, value: unknown) => {
          response.statusCode = status
          response.setHeader('Content-Type', 'application/json; charset=utf-8')
          response.end(JSON.stringify(value))
        }

        try {
          if (pathname === '/api/simulations' || pathname === '/api/simulations/') {
            const runs = [...runFiles.values()]
              .map((filePath) => JSON.parse(readFileSync(filePath, 'utf8')))
              .sort((left, right) => Date.parse(right.start_time) - Date.parse(left.start_time))
              .map((result) => ({
                run_id: result.run_id,
                scenario_id: result.scenario_id,
                controller_type: result.controller_type,
                status: result.status,
                start_time: result.start_time,
                end_time: result.end_time,
                random_seed: result.random_seed,
                energy_metrics: {
                  ...result.energy,
                  pv_self_consumption: result.energy?.pv_self_consumption_kwh,
                  pv_curtailment: result.energy?.pv_curtailment_kwh,
                },
                service_metrics: {
                  ...result.service,
                  avg_ev_soc_at_departure: result.service?.ev_avg_soc_at_departure,
                },
                grid_metrics: result.grid,
              }))
            sendJson(200, runs)
            return
          }

          const trajectoryMatch = pathname.match(/^\/api\/simulations\/([^/]+)\/trajectories$/)
          if (trajectoryMatch) {
            const runId = decodeURIComponent(trajectoryMatch[1])
            const resultPath = runFiles.get(runId)
            if (!resultPath) {
              sendJson(404, { detail: `Unknown simulation run: ${runId}` })
              return
            }
            const trajectoryPath = path.join(path.dirname(resultPath), 'trajectories.jsonl')
            if (!existsSync(trajectoryPath)) {
              sendJson(404, { detail: `Trajectory data is missing for ${runId}` })
              return
            }
            const trajectory = readFileSync(trajectoryPath, 'utf8')
              .split(/\r?\n/)
              .filter(Boolean)
              .map((line) => JSON.parse(line))
            sendJson(200, trajectory)
            return
          }

          next()
        } catch (error) {
          sendJson(500, { detail: error instanceof Error ? error.message : 'Failed to read local results' })
        }
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), localResultsApi()],
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