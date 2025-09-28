import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import IngestOpsPage from '../pages/Ingest/IngestOpsPage.jsx';
import * as ingestApi from '../api/ingest.js';
import { I18nProvider } from '../i18n/I18nProvider.jsx';

// Mock API layer to avoid real HTTP
vi.mock('../api/ingest.js', () => ({
  setIngestPolicy: vi.fn(()=>Promise.resolve({ data:{ ok:true }})),
  setCheckUrlsPolicy: vi.fn(()=>Promise.resolve({ data:{ ok:true }})),
  ingestCampaignsSync: vi.fn(()=>Promise.resolve({ data:{ ok:true, imported:0 }})),
  ingestPromotions: vi.fn(()=>Promise.resolve({ data:{ ok:true, promotions:1 }})),
  ingestTopProducts: vi.fn(()=>Promise.resolve({ data:{ ok:true, imported:2 }})),
  ingestDatafeedsAll: vi.fn(()=>Promise.resolve({ data:{ ok:true, imported:0 }})),
  ingestProducts: vi.fn(()=>Promise.resolve({ data:{ ok:true, imported:0 }})),
  ingestCommissions: vi.fn(()=>Promise.resolve({ data:{ ok:true, policies_imported:0 }})),
}));

function wrap(ui){ return <MemoryRouter><I18nProvider initial="vi">{ui}</I18nProvider></MemoryRouter>; }

describe('IngestOpsPage dynamic forms', () => {
  it('renders all task forms and runs one', async () => {
    render(wrap(<IngestOpsPage />));
    // Expect some form titles (VN i18n keys)
    expect(screen.getByText(/Đồng bộ Campaigns/i)).toBeTruthy();
    expect(screen.getByText(/Ingest Khuyến mãi/i)).toBeTruthy();
    // Run campaigns_sync
    const runBtn = screen.getByTestId('ingest-run-campaigns_sync');
    await userEvent.click(runBtn);
    // Log chip hiển thị id tác vụ (campaigns_sync)
    await waitFor(() => {
      const logs = window.__TEST__getIngestLogs?.();
      // Debug if failing
      if (!logs || logs.length === 0) {
        // eslint-disable-next-line no-console
        console.log('DEBUG current logs', logs);
      }
      expect(logs && logs.length > 0).toBeTruthy();
      expect(logs.some(l => l.action === 'campaigns_sync')).toBe(true);
    });
  });

  it('validates required list statuses not empty', async () => {
    render(wrap(<IngestOpsPage />));
    // Mở accordion campaigns_sync nếu cần (nút chạy đã có testId)
    const statusesInput = screen.getAllByLabelText(/Trạng thái|Statuses/i)[0];
    // Xoá hết nội dung
    await userEvent.clear(statusesInput);
    const runBtn = screen.getByTestId('ingest-run-campaigns_sync');
    await userEvent.click(runBtn);
    await waitFor(() => {
      const err = screen.getByTestId('ingest-json-error');
      expect(err.textContent).toMatch(/Thiếu: .*statuses/i);
    });
  });
});
