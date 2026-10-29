/**
 * Feature Flags for production gating
 * All experimental/unfinished features should be behind flags
 */
export const featureFlags = {
  // Scenario Editor
  yamlExport: false,
  
  // Agent Workspace
  codeSyntaxHighlighting: false,
  
  // Comparison
  radarChart: false,
  validatedMetricsOnly: true,
  
  // Reports
  reportLayerSwitcher: false,
  jsonReportExport: false,
  
  // WebSocket
  staleDataBanner: true,
  reconnectUIState: true,
  
  // i18n
  i18nEnabled: false,
} as const;

export type FeatureFlag = keyof typeof featureFlags;

export function isFeatureEnabled(flag: FeatureFlag): boolean {
  return featureFlags[flag];
}

export function getFeatureFlags() {
  return { ...featureFlags };
}