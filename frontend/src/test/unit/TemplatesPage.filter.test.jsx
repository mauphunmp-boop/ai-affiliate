import React from 'react';
import { render, screen, act } from '@testing-library/react';
import TemplatesPage from '../../pages/Affiliate/TemplatesPage.jsx';
import { ColorModeProvider } from '../../context/ColorModeContext.jsx';
import NotificationProvider from '../../components/NotificationProvider.jsx';
import { vi } from 'vitest';

vi.mock('../../api/affiliate', () => ({
  listAffiliateTemplates: vi.fn().mockResolvedValue({ data: [
    { id:1, network:'accesstrade', platform:null, template:'t1', default_params:null, enabled:true },
    { id:2, network:'accesstrade', platform:'shop', template:'t2', default_params:null, enabled:false }
  ] }),
  upsertAffiliateTemplate: vi.fn(),
  autoGenerateTemplates: vi.fn().mockResolvedValue({ data: { created:[], skipped:[] } }),
  deleteAffiliateTemplate: vi.fn().mockResolvedValue({}),
  updateAffiliateTemplate: vi.fn().mockResolvedValue({})
}));

// Mock DataTable để loại bỏ effect onState liên tục (đủ cho kiểm tra filter logic)
vi.mock('../../components/DataTable.jsx', () => ({
  __esModule: true,
  default: ({ rows }) => <div data-testid="mock-datatable">{rows.map(r => <div key={r.id}>{r.template}</div>)}</div>
}));

function wrap(ui){
  return <ColorModeProvider><NotificationProvider>{ui}</NotificationProvider></ColorModeProvider>;
}

describe('TemplatesPage enabled filter', () => {
  test('filters ON/OFF', async () => {
    render(wrap(<TemplatesPage />));
    // Chờ dữ liệu load
    await screen.findByText('t1');
    expect(screen.getByText('t2')).toBeInTheDocument();
    // Đổi filter sang OFF bằng test hook gắn trên window
    const setter = window.__TEST__setTemplatesEnabledFilter;
    expect(typeof setter).toBe('function');
  await act(async () => { setter('off'); });
    // Sau thay đổi, hàng enabled=true (t1) biến mất, t2 còn
    expect(await screen.findByText('t2')).toBeInTheDocument();
    expect(screen.queryByText('t1')).not.toBeInTheDocument();
  });
});
