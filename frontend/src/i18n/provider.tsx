import { createContext, useContext, type ReactNode } from 'react';
import { useTranslation as useTranslationHook } from 'react-i18next';

const I18nContext = createContext<{
  changeLanguage: (lng: string) => Promise<void>;
  language: string;
  languages: { code: string; name: string; nativeName: string }[];
} | null>(null);

interface I18nProviderProps {
  children: ReactNode;
}

export function I18nProvider({ children }: I18nProviderProps) {
  const { i18n: i18nInstance } = useTranslationHook();

  const changeLanguage = async (lng: string) => {
    await i18nInstance.changeLanguage(lng);
    if (typeof window !== 'undefined') {
      localStorage.setItem('saea.lang', lng);
    }
  };

  const languages = [
    { code: 'en', name: 'English', nativeName: 'English' },
    { code: 'zh-TW', name: 'Traditional Chinese', nativeName: '繁體中文' },
  ];

  return (
    <I18nContext.Provider value={{ changeLanguage, language: i18nInstance.language, languages }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error('useI18n must be used within an I18nProvider');
  }
  const { t } = useTranslationHook();
  return { ...context, t };
}

// Re-export useTranslation for components that need multiple namespaces
export { useTranslationHook as useTranslation };