import React from 'react';
import { describe, it, expect } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { I18nProvider } from '../i18n/I18nProvider.jsx';
import AppLayout from '../layout/AppLayout.jsx';
import { renderWithProviders, screen } from '../test/test-utils.jsx';

function Dummy({ label }) { return <h2>{label}</h2>; }

function renderRoute(initial) {
  return renderWithProviders(
    <I18nProvider initial="en">
      <MemoryRouter initialEntries={[initial]}>
        <Routes>
          <Route path="/" element={<AppLayout />}> 
            <Route path="offers" element={<Dummy label="Offers Root" />} />
            <Route path="offers/excel/import" element={<Dummy label="Offers Import" />} />
            <Route path="offers/excel/export" element={<Dummy label="Offers Export" />} />
            <Route path="campaigns" element={<Dummy label="Campaigns" />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </I18nProvider>
  );
}

describe('Offers nav active state', () => {
  it('is active on /offers only', () => {
    const first = renderRoute('/offers');
  const offersCandidates = screen.getAllByText(/offers/i);
  const offersNav = offersCandidates.map(el => el.closest('a')).find(a => a && a.getAttribute('data-nav-item') === '/offers');
    expect(offersNav).toHaveClass('active');
    // unmount then render at different route to avoid duplicate trees
    first.unmount();
    renderRoute('/offers/excel/import');
  const offersCandidates2 = screen.getAllByText(/offers/i);
  const offersNavInactive = offersCandidates2.map(el => el.closest('a')).find(a => a && a.getAttribute('data-nav-item') === '/offers');
    expect(offersNavInactive).not.toHaveClass('active');
  });
});
