import { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { ScenarioConfig } from '../api/types';
import { Button } from '../components/ui/Button';

type RunState = {
  run_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  stage?: string | null;
  progress?: number;
  eta_seconds?: number | null;
  outcome_sentence?: string | null;
  error?: string | null;
  controller_type?: string;
};

const STATUS_COPY: Record<string, { glyph: string; label: string }> = {
  pending: { glyph: '…', label: 'Queued' },
  running: { glyph: '▶', label: 'Running' },
  completed: { glyph: '✓', label: 'Completed' },
  failed: { glyph: '✗', label: 'Failed' },
  cancelled: { glyph: '■', label: 'Cancelled' },
};

/** Scenario detail: the confirmed community, validated, then run - with the
 * lifecycle states the plan requires (queued / running / completed / failed /
 * cancelled), the reason and next step on failure, and the onward links to the
 * community canvas and the strategy comparison. */
export function ScenarioDetailPage() {
  const { scenarioId } = useParams<{ scenarioId: string }>();
  const navigate = useNavigate();
  const [config, setConfig] = useState<ScenarioConfig | null>(null);
  const [validation, setValidation] = useState<{ valid: boolean; errors: string[] } | null>(null);
  const [run, setRun] = useState<RunState | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [diagnostics, setDiagnostics] = useState<{
    findings: Array<any>;
    kpi_summary: Record<string, any>;
    interpretation: string;
  } | null>(null);

  const load = useCallback(async () => {
    if (!scenarioId) return;
    try {
      const scenario = await api.getScenario(scenarioId);
      setConfig(scenario);
      const v = await api.validateScenario(scenarioId);
      setValidation({ valid: v.valid, errors: v.errors || [] });
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message || 'Scenario not found');
    }
  }, [scenarioId]);

  useEffect(() => {
    load();
  }, [load]);

  // Poll the run to a terminal state: the lifecycle is real, never estimated.
  useEffect(() => {
    if (!run || ['completed', 'failed', 'cancelled'].includes(run.status)) return;
    let active = true;
    const t = setInterval(async () => {
      try {
        const r = await api.getSimulationRun(run.run_id);
        if (active) {
          setRun({
            run_id: r.run_id,
            status: r.status,
            stage: r.stage,
            progress: r.progress,
            eta_seconds: r.eta_seconds,
            outcome_sentence: r.outcome_sentence,
            error: r.error,
            controller_type: r.controller_type,
          });
        }
        if (r.status === 'completed') {
          try {
            const diag = await api.getRunDiagnostics(r.run_id);
            if (active) setDiagnostics(diag);
          } catch {
            /* diagnostics are best-effort: the run itself already reported */
          }
        }
      } catch {
        /* transient: the next tick retries */
      }
    }, 2000);
    return () => {
      active = false;
      clearInterval(t);
    };
  }, [run]);

  const handleRun = useCallback(async () => {
    if (!scenarioId || starting) return;
    setError(null);
    setStarting(true);
    try {
      const created = await api.startSimulation({ scenario_id: scenarioId });
      setRun({
        run_id: created.run_id,
        status: created.status || 'pending',
        stage: created.stage,
        progress: created.progress,
        controller_type: created.controller_type,
      });
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message || 'Could not start the simulation');
    } finally {
      setStarting(false);
    }
  }, [scenarioId, starting]);

  const handleCancel = useCallback(async () => {
    if (!run) return;
    try {
      await api.cancelSimulation(run.run_id);
      setRun({ ...run, status: 'cancelled' });
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message || 'Could not cancel');
    }
  }, [run]);

  if (!config) {
    return (
      <div className="h-full flex flex-col p-4">
        <h1 className="font-display font-semibold text-heading-1 text-text">Scenario</h1>
        <p className="text-caption text-text-muted mt-2">
          {error ? `Could not load this scenario: ${error}` : 'Loading scenario configuration…'}
        </p>
      </div>
    );
  }

  const status = run ? STATUS_COPY[run.status] || STATUS_COPY.pending : null;
  const buildings = config.buildings || [];

  return (
    <div className="h-full flex flex-col p-4 gap-4 overflow-y-auto">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-display font-semibold text-heading-1 text-text">
            {config.name || config.scenario_id}
          </h1>
          <p className="text-caption text-text-muted">
            {buildings.length} building{buildings.length === 1 ? '' : 's'} ·{' '}
            {config.timestep_minutes} min steps · seed {config.random_seed}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {!run && (
            <Button variant="primary" onClick={handleRun} disabled={starting || (validation ? !validation.valid : false)}>
              {starting ? 'Starting…' : 'Run simulation'}
            </Button>
          )}
          {run && run.status === 'running' && (
            <Button variant="ghost" onClick={handleCancel}>
              Cancel
            </Button>
          )}
        </div>
      </div>

      {validation && !validation.valid && (
        <div className="p-3 bg-violation/10 border border-violation/30 text-violation rounded-lg">
          <p className="text-caption font-medium">
            This scenario cannot run yet — fix these fields first:
          </p>
          <ul className="text-caption mt-1 list-disc list-inside">
            {validation.errors.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </div>
      )}
      {validation && validation.valid && !run && (
        <div className="p-3 bg-energy/10 border border-energy/30 text-energy rounded-lg">
          <p className="text-caption font-medium">
            <span aria-hidden="true">✓</span> Validated — ready to run.
          </p>
        </div>
      )}

      {run && status && (
        <div className="p-3 bg-surface/30 border border-border/30 rounded-lg">
          <p className="text-caption font-medium text-text flex items-center gap-1">
            <span aria-hidden="true">{status.glyph}</span>
            {status.label}
            {run.stage ? ` — ${run.stage}` : ''}
            {run.status === 'running' && typeof run.progress === 'number'
              ? ` (${Math.round(run.progress * 100)}%)`
              : ''}
          </p>
          {run.outcome_sentence && (
            <p className="text-caption text-text-muted mt-1">{run.outcome_sentence}</p>
          )}
          {run.status === 'failed' && run.error && (
            <p className="text-caption text-violation mt-1">
              {run.error} — check the scenario configuration and try again; the run is
              deduplicated by config and seed, so a retry reuses this run unless the config changed.
            </p>
          )}
        </div>
      )}

      {run && run.status === 'completed' && diagnostics && (
        <div className="p-3 bg-surface/30 border border-border/30 rounded-lg">
          <h2 className="font-body font-medium text-body text-text">Run diagnosis</h2>
          <p className="text-caption text-text-muted mt-1">{diagnostics.interpretation}</p>
          {diagnostics.kpi_summary && (
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2 text-caption">
              {Object.entries(diagnostics.kpi_summary).map(([k, v]) => (
                <div key={k} className="flex justify-between gap-2">
                  <dt className="text-text-muted">{k.replace(/_/g, ' ')}</dt>
                  <dd className="font-mono text-text">
                    {v == null ? 'no record' : String(v)}
                  </dd>
                </div>
              ))}
            </dl>
          )}
          {diagnostics.findings.length > 0 && (
            <ul className="mt-2 space-y-2">
              {diagnostics.findings.map((f, i) => (
                <li key={i} className="text-caption border border-violation/30 rounded p-2">
                  <p className="font-medium text-violation">
                    <span aria-hidden="true">✗</span> t{f.timestep}: {f.message} ({f.severity})
                  </p>
                  <p className="text-text-muted">{f.meaning}</p>
                  <p className="text-text">Next step: {f.recommended_action}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {run && run.status === 'completed' && (
        <div className="flex items-center gap-3">
          <Button variant="secondary" onClick={() => navigate(`/scenarios/probe/${run.run_id}`)}>
            View the community
          </Button>
          <Button variant="secondary" onClick={() => navigate(`/comparison/strategy/${config.scenario_id}`)}>
            Compare strategies
          </Button>
        </div>
      )}
      {error && !run && (
        <p className="text-caption text-violation">{error}</p>
      )}
    </div>
  );
}
