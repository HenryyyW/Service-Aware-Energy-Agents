import { clsx } from 'clsx';
import {
  Building2,
  Sun,
  Battery,
  Car,
  AlertCircle,
} from '../../utils/lucide';

interface CommunityTableProps {
  buildings: Array<{ building_id: string; building_type?: string; location?: { lat: number; lon: number } }>;
  pvAssets: Array<{ asset_id: string; building_id: string; capacity_kw?: number; orientation?: number }>;
  batteryAssets: Array<{ asset_id: string; building_id: string; capacity_kwh?: number; power_kw?: number }>;
  evAssets: Array<{ asset_id: string; building_id: string; capacity_kwh?: number; charger_power_kw?: number }>;
  violations: Array<{ element: string; elementType: string; value: number; limit: number; type: 'voltage' | 'loading' }>;
}

export function CommunityTable({ buildings, pvAssets, batteryAssets, evAssets, violations }: CommunityTableProps) {
  const violationMap = new Map<string, { value: number; limit: number; type: string }>();
  violations.forEach((v) => violationMap.set(v.element, v));

  return (
    <div className="glass-card overflow-hidden flex flex-col h-full">
      {/* Buildings table */}
      <div className="p-3 bg-surface/50 border-b border-border/30">
        <h4 className="font-body font-medium text-body-sm text-text">Buildings ({buildings.length})</h4>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-surface/50 border-b border-border/30">
            <tr>
              <th className="px-4 py-2.5 text-left font-medium text-text-muted text-xs">Building ID</th>
              <th className="px-4 py-2.5 text-left font-medium text-text-muted text-xs">Type</th>
              <th className="px-4 py-2.5 text-left font-medium text-text-muted text-xs">Location</th>
              <th className="px-4 py-2.5 text-right font-medium text-text-muted text-xs">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/30">
            {buildings.map((b) => (
              <tr key={b.building_id} className="group">
                <td className="px-4 py-2.5 text-text font-body-sm">
                  <span className="flex items-center gap-1.5">
                    <Building2 className="w-3 h-3 text-text-muted" />
                    {b.building_id}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-text font-body-sm">{b.building_type ?? '—'}</td>
                <td className="px-4 py-2.5 text-text font-body-sm">
                  {b.location ? `${b.location.lat}, ${b.location.lon}` : '—'}
                </td>
                <td className="px-4 py-2.5 text-right">
                  <span className={clsx('font-mono text-data text-xs', 'text-energy')}>
                    OK
                  </span>
                </td>
              </tr>
            ))}
            {buildings.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-4 text-center text-text-muted">
                  No buildings in scenario
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Assets table */}
      <div className="p-3 bg-surface/50 border-b border-border/30">
        <h4 className="font-body font-medium text-body-sm text-text">Assets</h4>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-surface/50 border-b border-border/30">
            <tr>
              <th className="px-4 py-2.5 text-left font-medium text-text-muted text-xs">Asset</th>
              <th className="px-4 py-2.5 text-left font-medium text-text-muted text-xs">Building</th>
              <th className="px-4 py-2.5 text-left font-medium text-text-muted text-xs">Type</th>
              <th className="px-4 py-2.5 text-left font-medium text-text-muted text-xs">Capacity</th>
              <th className="px-4 py-2.5 text-right font-medium text-text-muted text-xs">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/30">
            {pvAssets.map((pv) => (
              <tr key={pv.asset_id} className="group">
                <td className="px-4 py-2.5 text-text font-body-sm">
                  <span className="flex items-center gap-1.5">
                    <Sun className="w-3 h-3 text-text-muted" />
                    {pv.asset_id}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-text font-body-sm">{pv.building_id}</td>
                <td className="px-4 py-2.5 text-text font-body-sm">PV</td>
                <td className="px-4 py-2.5 text-text font-body-sm">
                  {pv.capacity_kw ?? '—'} kW
                </td>
                <td className="px-4 py-2.5 text-right">
                  <span className={clsx('font-mono text-data text-xs', 'text-energy')}>OK</span>
                </td>
              </tr>
            ))}
            {batteryAssets.map((bat) => (
              <tr key={bat.asset_id} className="group">
                <td className="px-4 py-2.5 text-text font-body-sm">
                  <span className="flex items-center gap-1.5">
                    <Battery className="w-3 h-3 text-text-muted" />
                    {bat.asset_id}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-text font-body-sm">{bat.building_id}</td>
                <td className="px-4 py-2.5 text-text font-body-sm">Battery</td>
                <td className="px-4 py-2.5 text-text font-body-sm">
                  {bat.capacity_kwh ?? '—'} kWh
                </td>
                <td className="px-4 py-2.5 text-right">
                  <span className={clsx('font-mono text-data text-xs', 'text-energy')}>OK</span>
                </td>
              </tr>
            ))}
            {evAssets.map((ev) => (
              <tr key={ev.asset_id} className="group">
                <td className="px-4 py-2.5 text-text font-body-sm">
                  <span className="flex items-center gap-1.5">
                    <Car className="w-3 h-3 text-text-muted" />
                    {ev.asset_id}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-text font-body-sm">{ev.building_id}</td>
                <td className="px-4 py-2.5 text-text font-body-sm">EV</td>
                <td className="px-4 py-2.5 text-text font-body-sm">
                  {ev.capacity_kwh ?? '—'} kWh
                </td>
                <td className="px-4 py-2.5 text-right">
                  <span className={clsx('font-mono text-data text-xs', 'text-energy')}>OK</span>
                </td>
              </tr>
            ))}
            {pvAssets.length === 0 && batteryAssets.length === 0 && evAssets.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-4 text-center text-text-muted">
                  No on-site assets
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Violations table */}
      <div className="p-3 bg-surface/50 border-b border-border/30">
        <h4 className="font-body font-medium text-body-sm text-text">Grid Violations ({violations.length})</h4>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-surface/50 border-b border-border/30">
            <tr>
              <th className="px-4 py-2.5 text-left font-medium text-text-muted text-xs">Element</th>
              <th className="px-4 py-2.5 text-left font-medium text-text-muted text-xs">Type</th>
              <th className="px-4 py-2.5 text-right font-medium text-text-muted text-xs">Value</th>
              <th className="px-4 py-2.5 text-right font-medium text-text-muted text-xs">Limit</th>
              <th className="px-4 py-2.5 text-right font-medium text-text-muted text-xs">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/30">
            {violations.map((v) => {
              const isCritical = v.type === 'voltage' && v.value > v.limit * 1.02;
              return (
                <tr key={`${v.element}-${v.type}`} className="group">
                  <td className="px-4 py-2.5 text-text font-body-sm">
                    <span className="flex items-center gap-1.5">
                      <AlertCircle className="w-3 h-3 text-violation" />
                      {v.element}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-text font-body-sm">{v.elementType}</td>
                  <td className="px-4 py-2.5 text-right text-body-sm">
                    <span className={clsx('font-mono text-data', isCritical ? 'text-violation' : 'text-text')}>
                      {v.value.toFixed(2)}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right text-body-sm">
                    <span className="font-mono text-data text-text-muted">{v.limit}</span>
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <span className={clsx('font-mono text-data text-xs', isCritical ? 'text-violation' : 'text-sun')}>
                      {isCritical ? 'CRITICAL' : 'WARNING'}
                    </span>
                  </td>
                </tr>
              );
            })}
            {violations.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-4 text-center text-text-muted">
                  No grid violations
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
