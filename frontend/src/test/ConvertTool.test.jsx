import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ConvertTool from '../pages/Affiliate/ConvertTool.jsx';
import { NotificationProvider } from '../components/NotificationProvider.jsx';

vi.mock('../api/affiliate', () => ({
  convertAffiliateLink: vi.fn().mockResolvedValue({ data: { affiliate_url: 'http://aff', short_url: 'http://x/r/abc' } })
}));

function renderWithProviders(ui) {
  return render(<NotificationProvider>{ui}</NotificationProvider>);
}

describe('ConvertTool', () => {
  it('tự động nhận diện platform từ URL shopee', async () => {
    renderWithProviders(<ConvertTool />);
    const urlInput = screen.getByLabelText(/URL gốc/i);
    await userEvent.clear(urlInput);
    await userEvent.type(urlInput, 'https://shopee.vn/some-product-123');
    const platformSelect = screen.getByLabelText(/Platform/i);
    await waitFor(() => expect(platformSelect).toHaveValue('shopee'));
  });
});
