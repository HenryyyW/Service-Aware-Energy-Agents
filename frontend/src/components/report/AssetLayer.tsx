import { useTranslation } from 'react-i18next';
import { Table, TableHeader, TableBody, TableRow, TableHeaderCell, TableCell } from '../ui/Table';
import type { ReportResponse } from '../../api/types';

interface AssetLayerProps {
  report: ReportResponse;
  selectedAsset?: string;
  onAssetSelect?: (assetId: string) => void;
}

export function AssetLayer({ report, selectedAsset, onAssetSelect }: AssetLayerProps) {
  const { t } = useTranslation('report');

  const settlement = report.kpi_blocks?.settlement;
  const settlementData = settlement?.building_contributions || settlement?.building_settlements || settlement;
  const entries = settlementData ? Object.entries(settlementData) : [];

  return (
    <div className="space-y-6">
      {/* Asset Selector / Detail Card */}
      {selectedAsset ? (
        <div className="glass-card p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-body font-medium text-body text-text">
              {t('assetLayer.title')}: {selectedAsset}
            </h3>
            <button
              onClick={() => onAssetSelect?.('')}
              className="text-text-muted hover:text-text text-sm"
            >
              ← {t('assetLayer.selectAsset')}
            </button>
          </div>
          <div className="space-y-3">
            {entries.find(([id]) => id === selectedAsset) && (
              <>
                {Object.entries(entries.find(([id]) => id === selectedAsset)?.[1] || {}).map(([key, value]) => (
                  <div key={key} className="flex justify-between py-2 border-b border-border/30 last:border-0">
                    <span className="text-text-muted capitalize">{key.replace(/_/g, ' ')}</span>
                    <span className="font-mono text-text">
                      {typeof value === 'number' ? value.toFixed(2) : value}
                    </span>
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
      ) : (
        <div className="glass-card p-8 text-center text-text-muted">
          <p className="text-body">{t('assetLayer.selectAsset')}</p>
          <p className="text-caption mt-2">Click a row in the table below to view asset details</p>
        </div>
      )}

      {/* Per-Asset Table */}
      {entries.length > 0 && (
        <div className="glass-card p-4">
          <h3 className="font-body font-medium text-body text-text mb-4">{t('assetLayer.perAssetTable')}</h3>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHeaderCell>Asset</TableHeaderCell>
                  <TableHeaderCell className="text-right">Net Settlement ($)</TableHeaderCell>
                  <TableHeaderCell className="text-right">Grid Import (kWh)</TableHeaderCell>
                  <TableHeaderCell className="text-right">Grid Export (kWh)</TableHeaderCell>
                  <TableHeaderCell className="text-right">Community Import (kWh)</TableHeaderCell>
                  <TableHeaderCell className="text-right">Community Export (kWh)</TableHeaderCell>
                  <TableHeaderCell className="text-right">Savings vs Baseline ($)</TableHeaderCell>
                </TableRow>
              </TableHeader>
              <TableBody>
                {entries.map(([assetId, data]) => (
                  <TableRow
                    key={assetId}
                    className={selectedAsset === assetId ? 'bg-surface/50' : 'hover:bg-surface/50 cursor-pointer'}
                    onClick={() => onAssetSelect?.(assetId)}
                  >
                    <TableCell className="font-mono">{assetId}</TableCell>
                    <TableCell className="text-right text-energy font-mono">
                      {typeof data === 'object' && data !== null && 'net_settlement' in data
                        ? (data.net_settlement as number).toFixed(2)
                        : typeof data === 'number' ? data.toFixed(2) : 'N/A'}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {typeof data === 'object' && data !== null && 'total_grid_import_kwh' in data
                        ? (data.total_grid_import_kwh as number).toFixed(2)
                        : 'N/A'}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {typeof data === 'object' && data !== null && 'total_grid_export_kwh' in data
                        ? (data.total_grid_export_kwh as number).toFixed(2)
                        : 'N/A'}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {typeof data === 'object' && data !== null && 'total_community_import_kwh' in data
                        ? (data.total_community_import_kwh as number).toFixed(2)
                        : 'N/A'}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {typeof data === 'object' && data !== null && 'total_community_export_kwh' in data
                        ? (data.total_community_export_kwh as number).toFixed(2)
                        : 'N/A'}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {typeof data === 'object' && data !== null && 'savings_vs_baseline' in data
                        ? (data.savings_vs_baseline as number).toFixed(2)
                        : typeof data === 'object' && data !== null && 'net_settlement' in data
                          ? (data.net_settlement as number).toFixed(2)
                          : 'N/A'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      {entries.length === 0 && !selectedAsset && (
        <div className="glass-card p-8 text-center text-text-muted">
          <p className="text-body">{t('empty.asset')}</p>
        </div>
      )}
    </div>
  );
}