/**
 * Visual-style (theme) switching.
 *
 * Sets `data-theme` on <html>; the CSS in `src/index.css` re-points the design
 * tokens per theme, so components never change. Themes:
 *  - `ge`         GE Vernova enterprise (light, evergreen) — default
 *  - `schneider`  Schneider Electric enterprise (light, green)
 *  - `dark`       the original dark canvas (@theme defaults)
 */
export type ThemeId = 'ge' | 'schneider' | 'dark';

export const THEMES: { id: ThemeId; label: string }[] = [
  { id: 'ge', label: 'GE Vernova' },
  { id: 'schneider', label: 'Schneider' },
  { id: 'dark', label: 'Canvas (dark)' },
];

const STORAGE_KEY = 'saea.theme';
const DEFAULT_THEME: ThemeId = 'ge';

export function getTheme(): ThemeId {
  try {
    const stored = localStorage.getItem(STORAGE_KEY) as ThemeId | null;
    return stored && THEMES.some((t) => t.id === stored) ? stored : DEFAULT_THEME;
  } catch {
    return DEFAULT_THEME;
  }
}

export function applyTheme(id: ThemeId): void {
  document.documentElement.dataset.theme = id;
  try {
    localStorage.setItem(STORAGE_KEY, id);
  } catch {
    /* storage unavailable — theme still applies for this session */
  }
}

export function initTheme(): void {
  applyTheme(getTheme());
}
