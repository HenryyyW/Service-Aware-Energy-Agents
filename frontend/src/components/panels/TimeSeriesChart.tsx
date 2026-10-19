import { useMemo, useRef } from 'react';
import Plot from 'react-plotly.js';

interface TimeSeriesChartProps {
  data: Record<string, any>[];
  metrics: string[];
  height?: number;
  showLegend?: boolean;
  xAxisKey?: string;
}

const metricColors: Record<string, string> = {
  net_electricity_consumption: '#F43F5E',
  solar_generation: '#F59E0B',
  electrical_storage_soc: '#8B5CF6',
  battery_power_kw: '#10B981',
  ev_charge_kw: '#06B6D4',
  flexible_load_kw: '#F97316',
  indoor_temperature: '#22D3EE',
  cooling_demand: '#06B6D4',
  heating_demand: '#F43F5E',
  capacity_factor: '#F59E0B',
  available_capacity_kwh: '#8B5CF6',
  connected_electric_vehicle_at_charger_soc: '#8B5CF6',
  departure_time: '#06B6D4',
  target_soc: '#06B6D4',
  deadline: '#22D3EE',
  status: '#22D3EE',
};

const metricNames: Record<string, string> = {
  net_electricity_consumption: 'Net Load',
  solar_generation: 'PV Gen',
  electrical_storage_soc: 'Battery SOC',
  battery_power_kw: 'Battery Power',
  ev_charge_kw: 'EV Charging',
  flexible_load_kw: 'Flex Load',
  indoor_temperature: 'Indoor Temp',
  cooling_demand: 'Cooling',
  heating_demand: 'Heating',
  capacity_factor: 'Capacity Factor',
  available_capacity_kwh: 'Available Cap',
  connected_electric_vehicle_at_charger_soc: 'EV SOC',
  departure_time: 'Departure',
  target_soc: 'Target SOC',
  deadline: 'Deadline',
  status: 'Status',
};

export function TimeSeriesChart({
  data,
  metrics,
  height = 200,
  showLegend = true,
  xAxisKey = 'timestep'
}: TimeSeriesChartProps) {
  const plotRef = useRef<any>(null);

  const layout = useMemo(() => ({
    margin: { t: 10, r: 10, b: 40, l: 50 },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { family: 'IBM Plex Sans, sans-serif', color: '#E8EBF0', size: 11 },
    xaxis: {
      title: 'Timestep',
      gridcolor: 'rgba(255,255,255,0.05)',
      zerolinecolor: 'rgba(255,255,255,0.1)',
      showgrid: true,
      tickfont: { size: 10 },
    },
    yaxis: {
      title: 'Value',
      gridcolor: 'rgba(255,255,255,0.05)',
      zerolinecolor: 'rgba(255,255,255,0.1)',
      showgrid: true,
      tickfont: { size: 10 },
    },
    showlegend: showLegend,
    legend: {
      orientation: 'h',
      y: -0.25,
      x: 0,
      font: { size: 10 },
      bgcolor: 'rgba(17,24,39,0.8)',
      bordercolor: 'rgba(255,255,255,0.1)',
      borderwidth: 1,
    },
    hovermode: 'x unified',
    hoverlabel: {
      bgcolor: 'rgba(17,24,39,0.95)',
      bordercolor: 'rgba(255,255,255,0.1)',
      font: { family: 'IBM Plex Sans, sans-serif', size: 11 },
    },
    dragmode: 'zoom',
    uirevision: 'true',
  }), [showLegend]);

  const traces = useMemo(() => {
    if (!data.length || !metrics.length) return [];

    return metrics.map((metric, index) => {
      const values = data.map(d => d[metric]);
      const hasValidData = values.some(v => v !== undefined && v !== null);

      if (!hasValidData) return null;

      const color = metricColors[metric] || `hsl(${(index * 137) % 360}, 70%, 50%)`;

      return {
        x: data.map(d => d[xAxisKey]),
        y: values,
        name: metricNames[metric] || metric,
        type: 'scatter',
        mode: 'lines',
        line: {
          color,
          width: 2,
          shape: 'spline',
          smoothing: 0.3,
        },
        connectgaps: false,
        hovertemplate: `%{y:.2f}<extra>${metricNames[metric] || metric}</extra>`,
        showlegend: showLegend,
      };
    }).filter(Boolean);
  }, [data, metrics, xAxisKey, showLegend]);

  const config = useMemo(() => ({
    displayModeBar: false,
    responsive: true,
    staticPlot: false,
  }), []);

  return (
    <div className="w-full" style={{ height }}>
      <Plot
        ref={plotRef}
        data={traces}
        layout={layout}
        config={config}
        useResizeHandler={true}
        className="w-full h-full"
      />
    </div>
  );
}