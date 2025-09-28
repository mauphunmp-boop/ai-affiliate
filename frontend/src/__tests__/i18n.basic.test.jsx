import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import NotFound from '../pages/NotFound.jsx';
import OfflineBanner from '../components/OfflineBanner.jsx';
import { I18nProvider } from '../i18n/I18nProvider.jsx';

function renderWithLocale(ui, locale) {
  return render(
    <MemoryRouter>
      <I18nProvider initial={locale}>{ui}</I18nProvider>
    </MemoryRouter>
  );
}

describe('i18n basic', () => {
  it('renders NotFound in Vietnamese', () => {
    renderWithLocale(<NotFound />, 'vi');
    expect(screen.getByText('Không tìm thấy trang')).toBeInTheDocument();
  });
  it('renders NotFound in English', () => {
    renderWithLocale(<NotFound />, 'en');
    expect(screen.getByText('Page not found')).toBeInTheDocument();
  });
  it('renders OfflineBanner message (vi)', () => {
    // Force offline state by mocking navigator.onLine
    Object.defineProperty(window.navigator, 'onLine', { value: false, configurable: true });
    renderWithLocale(<OfflineBanner />, 'vi');
    expect(screen.getByText(/Mất kết nối mạng/)).toBeInTheDocument();
  });
  it('renders OfflineBanner message (en)', () => {
    Object.defineProperty(window.navigator, 'onLine', { value: false, configurable: true });
    renderWithLocale(<OfflineBanner />, 'en');
    expect(screen.getByText(/Network offline/)).toBeInTheDocument();
  });
});
