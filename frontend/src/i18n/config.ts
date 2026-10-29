import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

// Import locale files
import commonEn from './locales/en/common.json';
import commonZh from './locales/zh-TW/common.json';
import studioEn from './locales/en/studio.json';
import studioZh from './locales/zh-TW/studio.json';
import workspaceEn from './locales/en/workspace.json';
import workspaceZh from './locales/zh-TW/workspace.json';
import canvasEn from './locales/en/canvas.json';
import canvasZh from './locales/zh-TW/canvas.json';
import reportEn from './locales/en/report.json';
import reportZh from './locales/zh-TW/report.json';
import comparisonEn from './locales/en/comparison.json';
import comparisonZh from './locales/zh-TW/comparison.json';

const resources = {
  en: {
    common: commonEn,
    studio: studioEn,
    workspace: workspaceEn,
    canvas: canvasEn,
    report: reportEn,
    comparison: comparisonEn,
  },
  'zh-TW': {
    common: commonZh,
    studio: studioZh,
    workspace: workspaceZh,
    canvas: canvasZh,
    report: reportZh,
    comparison: comparisonZh,
  },
};

i18n
  .use(initReactI18next)
  .init({
    resources,
    lng: getInitialLanguage(),
    fallbackLng: 'en',
    defaultNS: 'common',
    ns: ['common', 'studio', 'workspace', 'canvas', 'report', 'comparison'],
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
      lookupLocalStorage: 'saea.lang',
    },
    react: {
      useSuspense: false,
    },
  });

function getInitialLanguage(): string {
  if (typeof window !== 'undefined') {
    const stored = localStorage.getItem('saea.lang');
    if (stored && ['en', 'zh-TW'].includes(stored)) {
      return stored;
    }
    const browserLang = navigator.language;
    if (browserLang.startsWith('zh')) {
      return 'zh-TW';
    }
  }
  return 'en';
}

export default i18n;
export { resources };