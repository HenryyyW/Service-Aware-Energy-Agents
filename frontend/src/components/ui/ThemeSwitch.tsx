import { useState } from 'react';
import { THEMES, applyTheme, getTheme, type ThemeId } from '../../config/theme';

/**
 * Visual-style switcher. Reads/writes the persisted theme and applies it to
 * <html data-theme>. Drop it into the top bar next to the run selector.
 */
export function ThemeSwitch() {
  const [theme, setTheme] = useState<ThemeId>(() => getTheme());

  const onChange = (id: ThemeId) => {
    setTheme(id);
    applyTheme(id);
  };

  return (
    <select
      className="theme-switch"
      aria-label="Visual style"
      title="Visual style"
      value={theme}
      onChange={(e) => onChange(e.target.value as ThemeId)}
    >
      {THEMES.map((t) => (
        <option key={t.id} value={t.id}>
          {t.label}
        </option>
      ))}
    </select>
  );
}
