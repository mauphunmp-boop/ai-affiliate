import React from 'react';
import { render, screen, waitFor, cleanup, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import TemplatesPage from '../../pages/Affiliate/TemplatesPage.jsx';
import { ColorModeProvider } from '../../context/ColorModeContext.jsx';
import NotificationProvider from '../../components/NotificationProvider.jsx';
import { vi } from 'vitest';

// Mock DataTable tương tự test filter để tránh side-effects pagination/onState giữ tiến trình
vi.mock('../../components/DataTable.jsx', () => ({
  __esModule: true,
  default: ({ rows }) => <div data-testid="mock-datatable-shortcuts">{rows.map(r => <div key={r.id}>{r.template}</div>)}</div>
}));

vi.mock('../../api/affiliate', () => ({
  listAffiliateTemplates: vi.fn().mockResolvedValue({ data: [
    { id:1, network:'accesstrade', platform:null, template:'t1', default_params:null, enabled:true },
    { id:2, network:'accesstrade', platform:'shop', template:'t2', default_params:null, enabled:true }
  ] }),
  upsertAffiliateTemplate: vi.fn(),
  autoGenerateTemplates: vi.fn().mockResolvedValue({ data: { created:[], skipped:[] } }),
  deleteAffiliateTemplate: vi.fn().mockResolvedValue({}),
  updateAffiliateTemplate: vi.fn().mockResolvedValue({})
}));

function wrap(ui){
  return <MemoryRouter><ColorModeProvider><NotificationProvider>{ui}</NotificationProvider></ColorModeProvider></MemoryRouter>;
}

describe('TemplatesPage shortcuts', () => {
  afterEach(() => {
    cleanup();
  });
  test('Alt+A selects all, Alt+C clears', async () => {
    const { unmount } = render(wrap(<TemplatesPage />));
    // Đảm bảo dữ liệu đã load (mock rows xuất hiện) trước khi gọi shortcut
    await screen.findByText('t1');
    await screen.findByText('t2');

    // Gọi shortcut trong act để tránh cảnh báo
    await act(async () => { window.__TEST__templatesShortcut('KeyA'); });
    await waitFor(() => expect(screen.getByTestId('templates-bulk-actions')).toBeInTheDocument());

    await act(async () => { window.__TEST__templatesShortcut('KeyC'); });
    await waitFor(() => expect(screen.queryByTestId('templates-bulk-actions')).toBeNull());

    unmount();
  });
});
