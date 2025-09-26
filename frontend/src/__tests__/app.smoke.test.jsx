import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import App from '../App.jsx';
import { I18nProvider } from '../i18n/I18nProvider.jsx';

function renderApp() {
  return render(
    <I18nProvider>
      <App />
    </I18nProvider>
  );
}

describe('App smoke', () => {
  it('renders navigation items', () => {
    renderApp();
    // Kiểm tra một số item điều hướng chính (vi/en key fallback)
    expect(screen.getByText(/Offers/i)).toBeInTheDocument();
    expect(screen.getByText(/Campaigns/i)).toBeInTheDocument();
  });
});
