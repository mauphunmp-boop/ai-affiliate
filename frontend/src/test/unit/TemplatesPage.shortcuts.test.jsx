import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TemplatesPage from '../../pages/Affiliate/TemplatesPage.jsx';
import { ColorModeProvider } from '../../context/ColorModeContext.jsx';
import NotificationProvider from '../../components/NotificationProvider.jsx';
import { vi } from 'vitest';

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
  return <ColorModeProvider><NotificationProvider>{ui}</NotificationProvider></ColorModeProvider>;
}

describe('TemplatesPage shortcuts', () => {
  test('Alt+A selects all, Alt+C clears', async () => {
    const user = userEvent.setup();
    render(wrap(<TemplatesPage />));
    await new Promise(r=>setTimeout(r, 5));
    // Use Alt+A
    await user.keyboard('{Alt>}a{/Alt}');
    // Expect Bulk action group visible (has button Xoá or Enable chọn)
    expect(screen.getByRole('button', { name:/Xoá/ })).toBeInTheDocument();
    // Clear with Alt+C
    await user.keyboard('{Alt>}c{/Alt}');
    // Bulk buttons disappear (Export CSV reappears)
    expect(screen.getByRole('button', { name:/Export CSV/i })).toBeInTheDocument();
  });
});
