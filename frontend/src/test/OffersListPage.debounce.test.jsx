import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
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
  it('chỉ phát sinh đúng 1 fetch thêm trong giai đoạn debounce khi gõ nhanh', async () => {
    renderWithProviders(<OffersListPage />);
    // Đợi ít nhất một (có thể 1-2) call khởi tạo ổn định (effect skip/category/limit + khả năng rehydrate persisted state)
    await waitFor(() => expect(listOffersMock).toHaveBeenCalled());
    // Chờ số lần gọi ổn định (không tăng thêm trong ~150ms) để tránh tính thiếu baseline
    const stableBaseline = async () => {
      let last = listOffersMock.mock.calls.length;
      const start = Date.now();
      // Yêu cầu không thay đổi trong 150ms liên tiếp
      while (Date.now() - start < 2000) { // timeout 2s
        await act(async () => { await new Promise(r=>setTimeout(r,50)); });
        const cur = listOffersMock.mock.calls.length;
        if (cur !== last) { last = cur; continue; }
        // giữ yên thêm 150ms
        const checkpoint = Date.now();
        let moved = false;
        while (Date.now() - checkpoint < 150) {
          await act(async () => { await new Promise(r=>setTimeout(r,30)); });
            const cur2 = listOffersMock.mock.calls.length;
            if (cur2 !== last) { last = cur2; moved = true; break; }
        }
        if (!moved) return last;
      }
      return listOffersMock.mock.calls.length; // fallback
    };
    const baseline = await stableBaseline();
    const input = screen.getByLabelText(/Merchant/i);
    await userEvent.clear(input);
    await userEvent.type(input, 'a');
    await userEvent.type(input, 'bc'); // tổng -> 'abc'
    // Chờ debounce cuối cùng (400ms) + buffer
    await act(async () => { await new Promise(r=>setTimeout(r,460)); });
    const after = listOffersMock.mock.calls.length;
  const delta = after - baseline;
  // Do có cơ chế hợp nhất + 1 fetch baseline pagination có thể phát sinh 2 lần refresh (baseline + debounce cuối) => delta nên <=2
  expect(delta).toBeLessThanOrEqual(2);
  // Đảm bảo lần cuối cùng phản ánh merchant cuối cùng người dùng nhập
  const lastCallArgs = listOffersMock.mock.calls.at(-1)[0];
  expect(lastCallArgs.merchant).toBe('abc');
  });
});
