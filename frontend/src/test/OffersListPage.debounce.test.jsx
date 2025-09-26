import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import OffersListPage from '../pages/Offers/OffersListPage.jsx';
import { NotificationProvider } from '../components/NotificationProvider.jsx';

const listOffersMock = vi.fn().mockResolvedValue({ data: [] });

vi.mock('../api/offers', () => ({
  listOffers: (...args) => listOffersMock(...args)
}));

function renderWithProviders(ui) {
  return render(<NotificationProvider>{ui}</NotificationProvider>);
}

describe('OffersListPage debounce', () => {
  it('chỉ gọi thêm 1 lần sau khi debounce khi gõ merchant nhanh', async () => {
    renderWithProviders(<OffersListPage />);
    // chờ fetch đầu tiên
    await waitFor(() => expect(listOffersMock).toHaveBeenCalled());
    const initialCalls = listOffersMock.mock.calls.length;
    const input = screen.getByLabelText(/Merchant/i);
    await userEvent.clear(input);
    await userEvent.type(input, 'a');
    await userEvent.type(input, 'bc'); // tổng trở thành 'abc'
    // đợi debounce 420ms
    await new Promise(r => setTimeout(r, 500));
    const afterCalls = listOffersMock.mock.calls.length;
    expect(afterCalls - initialCalls).toBe(1); // chỉ thêm 1 lần
    // Tham số cuối cùng chứa merchant 'abc'
    const lastArg = listOffersMock.mock.calls.at(-1)[0];
    expect(lastArg.merchant).toBe('abc');
  });
});
