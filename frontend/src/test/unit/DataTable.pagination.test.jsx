import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DataTable from '../../components/DataTable.jsx';

function makeRows(n){
  return Array.from({length:n}).map((_,i)=>({ id:i+1, name:`Row ${i+1}`, value:i+1 }));
}

const columns = [
  { key:'id', label:'ID', sortable:true },
  { key:'name', label:'Name', sortable:true },
  { key:'value', label:'Value', sortable:true }
];

describe('DataTable pagination', () => {
  test('navigates pages and respects page size', async () => {
    const user = userEvent.setup();
    render(<DataTable tableId="tpg" columns={columns} rows={makeRows(60)} enablePagination initialPageSize={25} />);
    // header + 25 rows
    expect(screen.getAllByRole('row')).toHaveLength(1 + 25);
    // Go next page
    await user.click(screen.getByRole('button', { name:/Sau/i }));
    expect(screen.getByText(/Trang 2\/3/)).toBeInTheDocument();
    // Still 25 rows second page
    expect(screen.getAllByRole('row')).toHaveLength(1 + 25);
    // Last page
    await user.click(screen.getByRole('button', { name:/Sau/i }));
    expect(screen.getByText(/Trang 3\/3/)).toBeInTheDocument();
    // 10 rows remain
    expect(screen.getAllByRole('row')).toHaveLength(1 + 10);
  });
});
