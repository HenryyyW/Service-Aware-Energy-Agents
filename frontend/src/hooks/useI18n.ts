import { useContext } from 'react';
import { useTranslation } from 'react-i18next';
import { I18nContext } from '../i18n/provider';

export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error('useI18n must be used within an I18nProvider');
  }
  const { t } = useTranslation();
  return { ...context, t };
}

export { useTranslation } from 'react-i18next';