import React from 'react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import OfferList from '../components/OfferList.jsx';
import * as api from '../api.js';
import { renderWithProviders, screen, fireEvent } from '../test/test-utils.jsx';

// Helper to build mock offers
function makeOffers(n, merchant='shop') {
  return Array.from({ length:n }).map((_,i)=>({ id:`${merchant}-${i}`, title:`Product ${i}`, merchant, price: i*10, currency:'VND' }));
}

describe('OfferList', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('load initial offers (page 1) and show rows', async () => {
    const mockData = makeOffers(5);
  vi.spyOn(api, 'getOffers').mockResolvedValueOnce({ data: mockData });
    renderWithProviders(<OfferList />);
    // Wait for first product title
  expect(await screen.findByText('Product 0')).toBeInTheDocument();
  // Ensure API called with default page/pageSize (merchant có thể undefined)
  expect(api.getOffers).toHaveBeenCalled();
  expect(api.getOffers.mock.calls[0][0]).toMatchObject({ page:1, pageSize:20 });
  });

  it('supports filtering by merchant then paginating', async () => {
    // First load (unfiltered)
    vi.spyOn(api, 'getOffers')
      .mockResolvedValueOnce({ data: makeOffers(20, 'all') }) // initial page 1
      .mockResolvedValueOnce({ data: makeOffers(20, 'tiki') }) // filter result page 1 tiki
      .mockResolvedValueOnce({ data: makeOffers(3, 'tiki') }); // page 2 tiki (smaller => end)

    renderWithProviders(<OfferList />);
    await screen.findByText('Product 0');

    const input = screen.getByLabelText(/Lọc merchant/i);
    fireEvent.change(input, { target:{ value:'tiki' } });
    const btn = screen.getByRole('button', { name:'Lọc' });
    fireEvent.click(btn);

  // Sau filter, hàng đầu tiên thuộc merchant tiki
  const tikiCellsPage1 = await screen.findAllByText('tiki');
  expect(tikiCellsPage1.length).toBeGreaterThan(0);
    // Go to next page (Pagination button with value=2)
    const page2 = screen.getByRole('button', { name:'Go to page 2' });
    fireEvent.click(page2);

  const tikiCellsPage2 = await screen.findAllByText('tiki');
  expect(tikiCellsPage2.length).toBeGreaterThan(0);

    // Verify calls
    expect(api.getOffers.mock.calls[1][0]).toMatchObject({ merchant:'tiki', page:1 });
    expect(api.getOffers.mock.calls[2][0]).toMatchObject({ merchant:'tiki', page:2 });
  });

  it('shows error panel on failure', async () => {
    vi.spyOn(api, 'getOffers').mockRejectedValueOnce({ normalized:{ message:'Server exploded'} });
    renderWithProviders(<OfferList />);
    await screen.findByText('Server exploded');
  });
});
