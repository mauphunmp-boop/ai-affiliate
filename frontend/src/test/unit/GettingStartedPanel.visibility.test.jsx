import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import GettingStartedPanel from '../../components/GettingStartedPanel.jsx';

// Mock API modules
vi.mock('../../api.js', () => ({ listApiConfigs: () => Promise.resolve({ data: [] }), listAffiliateTemplates: () => Promise.resolve({ data: [] }) }));
vi.mock('../../api/affiliate', () => ({ listAffiliateTemplates: () => Promise.resolve({ data: [] }) }));

// Re-implement since component imports both listApiConfigs() & listAffiliateTemplates directly
vi.mock('../../components/NotificationProvider.jsx', () => ({ NotificationProvider: ({ children }) => children, useNotify: () => () => {} }));

describe('GettingStartedPanel', () => {
  test('renders when configs & templates empty', async () => {
    render(
      <MemoryRouter>
        <GettingStartedPanel />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText(/Bắt đầu nhanh|Tạo API Config/i)).toBeTruthy();
    });
  });
});
