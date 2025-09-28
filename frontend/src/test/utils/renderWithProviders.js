import React from 'react';
import { ColorModeProvider } from '../../context/ColorModeContext.jsx';
import { I18nProvider } from '../../i18n/I18nProvider.jsx';
import { NotificationProvider } from '../../components/NotificationProvider.jsx';
import { render } from '@testing-library/react';

export function renderWithProviders(ui, options) {
  return render(ui, {
    wrapper: ({ children }) => (
      <I18nProvider initial="vi">
        <ColorModeProvider>
          <NotificationProvider>{children}</NotificationProvider>
        </ColorModeProvider>
      </I18nProvider>
    ),
    ...options
  });
}

// Re-export for backward compatibility with tests using named import
export { renderWithProviders as default };
