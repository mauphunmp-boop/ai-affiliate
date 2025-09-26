import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DataTable from '../../components/DataTable.jsx';

function setup(extraProps={}) {
  const rows = [ { id:1, name:'Alpha', value:2 }, { id:2, name:'Beta', value:1 } ];
  const columns = [
    { key:'name', label:'Name', sortable:true },
    { key:'value', label:'Value', sortable:true }
  ];
  render(<DataTable columns={columns} rows={rows} loading={false} enableQuickFilter enablePagination tableId="t1" initialPageSize={10} {...extraProps} />);
}

describe('DataTable basic', () => {
  it('sort asc/desc và filter hoạt động', async () => {
    setup();
    // Click sort Name -> asc (Alpha,Beta) giữ nguyên
    const nameHeader = screen.getByText('Name');
    await userEvent.click(nameHeader);
    // Click lần 2 -> desc
    await userEvent.click(nameHeader);
    // Filter nhanh với "beta"
    const filterInput = screen.getByPlaceholderText(/Lọc nhanh/i);
    await userEvent.type(filterInput, 'beta');
    await waitFor(()=> expect(screen.getByText('Beta')).toBeInTheDocument());
  });
});
