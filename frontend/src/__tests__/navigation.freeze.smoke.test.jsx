import React from 'react';
import { describe, it, expect } from 'vitest';
import { MemoryRouter, Routes, Route, useNavigate } from 'react-router-dom';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../test/test-utils.jsx';
import AppLayout from '../layout/AppLayout.jsx';
import { I18nProvider } from '../i18n/I18nProvider.jsx';

function Page({ name }) { return <h2>{name}</h2>; }

// Helper component to drive imperative navigation for freeze detection
function NavDriver({ targets, delay = 0 }) {
  const navigate = useNavigate();
  React.useEffect(() => {
    let i = 0;
    const id = setInterval(() => {
      if (i >= targets.length) { clearInterval(id); return; }
      navigate(targets[i]);
      i += 1;
    }, delay);
    return () => clearInterval(id);
  }, [targets, navigate, delay]);
  return null;
}

function renderAt(path) {
  return renderWithProviders(
    <I18nProvider initial="en">
      <MemoryRouter initialEntries={[ path ]}>
        <Routes>
          <Route path="/" element={<AppLayout />}> 
            <Route path="affiliate/templates" element={<Page name="Templates" />} />
            <Route path="campaigns" element={<Page name="Campaigns" />} />
            <Route path="offers" element={<Page name="Offers" />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </I18nProvider>
  );
}

describe('Navigation freeze smoke', () => {
  it('navigates across routes without hanging', async () => {
    const r1 = renderAt('/affiliate/templates');
    expect((await screen.findAllByText('Templates')).length).toBeGreaterThan(0);
    r1.unmount();
    const r2 = renderAt('/campaigns');
    expect((await screen.findAllByText('Campaigns')).length).toBeGreaterThan(0);
    r2.unmount();
    renderAt('/offers');
    expect((await screen.findAllByText('Offers')).length).toBeGreaterThan(0);
  });
});
