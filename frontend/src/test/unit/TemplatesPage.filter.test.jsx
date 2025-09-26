import React from 'react';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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

function wrap(ui){
  return <ColorModeProvider><NotificationProvider>{ui}</NotificationProvider></ColorModeProvider>;
}

describe('TemplatesPage enabled filter', () => {
  test('filters ON/OFF', async () => {
    render(wrap(<TemplatesPage />));
    // Wait a tick for load
    await new Promise(r=>setTimeout(r, 5));
    // Both rows appear
    expect(screen.getByText('t1')).toBeInTheDocument();
    expect(screen.getByText('t2')).toBeInTheDocument();
    // Select OFF filter
    const select = screen.getByLabelText('Enabled');
    await userEvent.click(select);
    const listbox = within(screen.getByRole('listbox'));
    await userEvent.click(listbox.getByText('OFF'));
    expect(screen.queryByText('t1')).not.toBeInTheDocument();
    expect(screen.getByText('t2')).toBeInTheDocument();
  });
});
