import { useTranslation } from 'react-i18next';
import { Table, TableHeader, TableBody, TableRow, TableHeaderCell, TableCell } from '../ui/Table';
import type { ReportResponse } from '../../api/types';

interface CommunityLayerProps {
  report: ReportResponse;
}

export function CommunityLayer({ report }: CommunityLayerProps) {
  const { t } = useTranslation('report');

  const kpis = report.kpi_blocks;
  const energy = kpis.energy || {};
  const settlement = kpis.settlement || {};

  return (
    <div className="space-y-6">
      {/* Aggregate KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="glass-card p-4">
          <p className="text-caption text-text-muted">{t('communityLayer.totalConsumption')}</p>
          <p className="font-mono text-2xl font-semibold text-text mt-1">
            {(energy.grid_import_kwh || 0).toLocaleString()} kWh
          </p>
        </div>
        <div className="glass-card p-4">
          <p className="text-caption text-text-muted">{t('communityLayer.totalCost')}</p>
          <p className="font-mono text-2xl font-semibold text-text mt-1">
            ${(energy.total_cost || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </p>
        </div>
        <div className="glass-card p-4">
          <p className="text-caption text-text-muted">{t('communityLayer.totalSavings')}</p>
          <p className="font-mono text-2xl font-semibold text-energy mt-1">
            ${(settlement.total_community_revenue || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </p>
        </div>
        <div className="glass-card p-4">
          <p className="text-caption text-text-muted">{t('communityLayer.participation')}</p>
          <p className="font-mono text-2xl font-semibold text-text mt-1">
            {settlement.total_community_volume_kwh ? `${settlement.total_community_volume_kwh.toFixed(1)} kWh` : '—'}
          </p>
        </div>
      </div>

      {/* Community-level KPIs table */}
      <div className="glass-card p-4">
        <h3 className="font-body font-medium text-body text-text mb-4">{t('communityLayer.kpis')}</h3>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHeaderCell>{t('common.action.view')}</TableHeaderCell>
                <TableHeaderCell className="text-right">Value</TableHeaderCell>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow>
                <TableCell>{t('communityLayer.totalConsumption')}</TableCell>
                <TableCell className="text-right font-mono">
                  {(energy.grid_import_kwh || 0).toFixed(2)} kWh
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell>{t('communityLayer.totalCost')}</TableCell>
                <TableCell className="text-right font-mono">
                  ${(energy.total_cost || 0).toFixed(2)}
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell>Grid Export</TableCell>
                <TableCell className="text-right font-mono">
                  {(energy.grid_export_kwh || 0).toFixed(2)} kWh
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell>PV Self-Consumption</TableCell>
                <TableCell className="text-right font-mono">
                  {((energy.pv_self_consumption || 0) * 100).toFixed(1)}%
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell>Peak Demand</TableCell>
                <TableCell className="text-right font-mono">
                  {(energy.peak_demand_kw || 0).toFixed(1)} kW
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell>Carbon Emissions</TableCell>
                <TableCell className="text-right font-mono">
                  {(energy.carbon_emissions_kg || 0).toFixed(1)} kg CO₂
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell>Battery Throughput</TableCell>
                <TableCell className="text-right font-mono">
                  {(energy.battery_throughput_kwh || 0).toFixed(1)} kWh
                </TableCell>
              </TableRow>
              {settlement.total_community_volume_kwh && (
                <>
                  <TableRow>
                    <TableCell>Community Volume</TableCell>
                    <TableCell className="text-right font-mono">
                      {settlement.total_community_volume_kwh.toFixed(1)} kWh
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Community Revenue</TableCell>
                    <TableCell className="text-right font-mono">
                      ${settlement.total_community_revenue?.toFixed(2) || '0.00'}
                    </TableCell>
                  </TableRow>
                </>
              )}
            </TableBody>
          </Table>
        </div>
      </div>

      {/* Participation Summary */}
      {report.detail_sections?.settlement && (
        <div className="glass-card p-4">
          <h3 className="font-body font-medium text-body text-text mb-4">{t('communityLayer.participation')}</h3>
          <div className="text-text-muted">
            <p>Building-level settlement data available in Asset layer.</p>
          </div>
        </div>
      )}
    </div>
  );
}