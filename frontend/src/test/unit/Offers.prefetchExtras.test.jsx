import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import OffersListPage from '../../pages/Offers/OffersListPage.jsx';

vi.mock('../../api/offers', () => {
  return {
    listOffers: vi.fn().mockResolvedValue({ data: [ { id: 1, title:'Item 1', merchant:'m1', price:10, currency:'VND' } ] }),
    getOfferExtras: vi.fn().mockResolvedValue({ data: { offer:{ id:1, title:'Item 1' }, promotions:[], commission_policies:[], counts:{} } })
  };
});

vi.mock('../../i18n/I18nProvider.jsx', () => ({ useT: () => ({ t: () => '' }) }));
vi.mock('../../hooks/usePersistedState.js', () => ({ __esModule:true, default:(k,d)=> [d, ()=>{}] }));

// Simplify DataTable (card/table rendering not important here)
vi.mock('../../components/DataTable.jsx', () => ({ __esModule:true, default: ({ rows, columns }) => (
  <table data-testid="offers-table"><tbody>{rows.map(r => (
    <tr key={r.id}><td>{r.title}</td><td>{columns.find(c=>c.key==='actions').render(r)}</td></tr>
  ))}</tbody></table>
)}));

import { getOfferExtras } from '../../api/offers';

describe('Offers prefetch extras', () => {
  test('hover triggers prefetch (getOfferExtras called before open)', async () => {
    render(<OffersListPage />);
    await waitFor(()=> screen.getByTestId('offers-table'));
    const infoBtn = screen.getByLabelText(/detail/);
    fireEvent.mouseEnter(infoBtn);
    await waitFor(()=> expect(getOfferExtras).toHaveBeenCalledTimes(1));
  });
});
