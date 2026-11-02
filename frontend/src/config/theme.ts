/**
 * Visual-style (theme) switching with OS sync.
 *
 * Sets `<html data-theme>`; the CSS in `src/index.css` re-points the design
 * tokens per theme, so components never change. Preferences:
 *  - `system`     follow the OS colour scheme (light -> GE, dark -> canvas) — default
 *  - `ge`         GE Vernova enterprise (light, evergreen)
 *  - `schneider`  Schneider Electric enterprise (light, green)
 *  - `dark`       original dark canvas
 *
 * The preference is persisted in localStorage; when it is `system`, the applied
 * theme follows `prefers-color-scheme` and updates live on OS change.
 */
export type ThemeId = 'system' | 'ge' | 'schneider' | 'dark';
export type ResolvedTheme = 'ge' | 'schneider' | 'dark';

export const THEMES: { id: ThemeId; label: string }[] = [
  { id: 'system', label: 'System' },
  { id: 'ge', label: 'GE Vernova (light)' },
  { id: 'schneider', label: 'Schneider (light)' },
  { id: 'dark', label: 'Canvas (dark)' },
];

const STORAGE_KEY = 'saea.theme';
const DEFAULT_THEME: ThemeId = 'system';
const LIGHT_FALLBACK: ResolvedTheme = 'ge';
const DARK: ResolvedTheme = 'dark';

/** Browser chrome colour per resolved theme (mirrors index.html theme-color). */
const THEME_COLOR: Record<ResolvedTheme, string> = {
  ge: '#005e60',
  schneider: '#2e9e45',
  dark: '#0a0f1a',
};

function systemPrefersDark(): boolean {
  try {
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  } catch {
    return true; // no matchMedia: fall back to the dark canvas
  }
}

export function resolveTheme(id: ThemeId): ResolvedTheme {
  if (id === 'system') return systemPrefersDark() ? DARK : LIGHT_FALLBACK;
  return id;
}

export function getTheme(): ThemeId {
  try {
    const stored = localStorage.getItem(STORAGE_KEY) as ThemeId | null;
    return stored && THEMES.some((t) => t.id === stored) ? stored : DEFAULT_THEME;
  } catch {
    return DEFAULT_THEME;
  }
}

export function applyTheme(id: ThemeId): void {
  const resolved = resolveTheme(id);
  document.documentElement.dataset.theme = resolved;
  document.documentElement.dataset.themePref = id;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute('content', THEME_COLOR[resolved]);
  try {
    localStorage.setItem(STORAGE_KEY, id);
  } catch {
    /* storage unavailable — theme still applies for this session */
  }
}

let listenerBound = false;

export function initTheme(): void {
  applyTheme(getTheme());
  if (listenerBound) return;
  listenerBound = true;
  try {
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    media.addEventListener('change', () => {
      if (getTheme() === 'system') applyTheme('system');
    });
  } catch {
    /* no matchMedia support */
  }
}
