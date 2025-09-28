import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Dashboard from '../pages/Dashboard/Dashboard.jsx';
import { I18nProvider } from '../i18n/I18nProvider.jsx';

function wrap(ui) { return <I18nProvider initial="vi">{ui}</I18nProvider>; }

describe('Dashboard smoke', () => {
  it('renders KPI labels', async () => {
    render(wrap(<Dashboard />));
    const first = await screen.findAllByText(/Offers|Tổng quan/i);
    expect(first.length).toBeGreaterThan(0);
  });
});
