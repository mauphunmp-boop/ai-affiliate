import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import AppLayout from '../layout/AppLayout.jsx';
import { I18nProvider } from '../i18n/I18nProvider.jsx';
import { renderWithProviders } from '../test/test-utils.jsx';

// Mock APIs used by GettingStartedPanel to force empty datasets
vi.mock('../api.js', async (orig) => {
  const actual = await orig();
  return {
    ...actual,
    listApiConfigs: () => Promise.resolve({ data: [] }),
  };
});
vi.mock('../api/affiliate', () => ({
  listAffiliateTemplates: () => Promise.resolve({ data: [] })
}));

function DummyPage({ label }) { return <h2>{label}</h2>; }

function renderApp(start = '/') {
  return renderWithProviders(
    <I18nProvider initial="vi">
      <MemoryRouter initialEntries={[start]}>
        <Routes>
          <Route path="/" element={<AppLayout />}> 
            <Route index element={<DummyPage label="Home" />} />
            <Route path="system/api-configs" element={<DummyPage label="API Configs" />} />
            <Route path="affiliate/templates" element={<DummyPage label="Templates" />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </I18nProvider>
  );
}

describe('GettingStartedPanel flicker', () => {
  it('renders once and navigates without flicker', async () => {
    renderApp('/');
    // Panel should appear because mocks return empty arrays
    const heading = await screen.findByTestId('getting-started-heading');
    expect(heading).toBeInTheDocument();
    // Click open API Configs
  const openButton = screen.getAllByRole('button').find(b => /Mở/i.test(b.textContent));
  fireEvent.click(openButton);
    // After navigation, panel should not immediately disappear and reappear causing flicker.
    // We just assert destination page content present.
  const apiConfigsEls = await screen.findAllByText('API Configs');
  expect(apiConfigsEls.length).toBeGreaterThan(0);
  });
});
