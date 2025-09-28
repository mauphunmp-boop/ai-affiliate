import '@testing-library/jest-dom';
import { afterEach } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import React from 'react';
import { I18nProvider } from '../i18n/I18nProvider.jsx';
import { MemoryRouter } from 'react-router-dom';
import { ColorModeProvider } from '../context/ColorModeContext.jsx';
import { NotificationProvider } from '../components/NotificationProvider.jsx';

// Polyfill matchMedia for MUI useMediaQuery & color-scheme detection
if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = function matchMedia(query) {
    return {
      matches: false,
      media: query,
      onchange: null,
      addListener: function () {},
      removeListener: function () {},
      addEventListener: function () {},
      removeEventListener: function () {},
      dispatchEvent: function () { return false; }
    };
  };
}

function AllProviders({ children }) {
  return (
    <MemoryRouter>
      <I18nProvider initial="vi">
        <ColorModeProvider>
          <NotificationProvider>
            {children}
          </NotificationProvider>
        </ColorModeProvider>
      </I18nProvider>
    </MemoryRouter>
  );
}

export function renderWithApp(ui, options) {
  return render(ui, { wrapper: AllProviders, ...options });
}

afterEach(() => {
  cleanup();
});

globalThis.renderWithApp = renderWithApp;
