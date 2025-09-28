import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Dashboard from '../pages/Dashboard/Dashboard.jsx';
import { I18nProvider } from '../i18n/I18nProvider.jsx';

function wrap(ui) { return <I18nProvider initial="vi">{ui}</I18nProvider>; }

describe('Dashboard smoke', () => {
  it('renders KPI labels', () => {
  // Debug marker: có thể bật lại nếu cần theo dõi chạy test
  console.debug('[dashboard.smoke.test] start render');
    render(wrap(<Dashboard />));
    // Có thể xuất hiện nhiều phần tử chứa 'Offers' (nút nhanh, caption KPI) hoặc tiêu đề 'Tổng quan'
    const matches = screen.getAllByText(/Offers|Tổng quan/i);
    expect(matches.length).toBeGreaterThan(0);
  });
});
