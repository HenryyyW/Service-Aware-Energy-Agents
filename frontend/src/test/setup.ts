// Test bootstrap for the SAEA frontend (Vitest + jsdom).

import { vi, beforeEach } from 'vitest'
import '@testing-library/jest-dom'

// Initialise the real i18next instance (same singleton the app uses in main.tsx)
// so `useTranslation` works in rendered page components without a provider.
import '../i18n/config'

// jsdom does not implement matchMedia or scrollIntoView; stub both.
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn(() => ({
    matches: false,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})
HTMLElement.prototype.scrollIntoView = vi.fn()

// Keep storage clean between tests (zustand persist + any localStorage users).
beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
})
