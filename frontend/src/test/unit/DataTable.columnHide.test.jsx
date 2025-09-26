import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DataTable from '../../components/DataTable.jsx';

const columns = [
  { key:'id', label:'ID' },
  { key:'name', label:'Name' },
  { key:'value', label:'Value' }
];
const rows = [{ id:1, name:'Alpha', value:10 }];

describe('DataTable column hide', () => {
  test('hides and shows column', async () => {
    const user = userEvent.setup();
    render(<DataTable tableId="thide" columns={columns} rows={rows} enableColumnHide />);
    // Initially all headers present
    expect(screen.getByText('Name')).toBeInTheDocument();
    // Open menu
    await user.click(screen.getByRole('button', { name:/toggle columns/i }));
    const menu = await screen.findByRole('menu');
    const nameItem = within(menu).getByText('Name');
    await user.click(nameItem); // toggle hide
    // menu auto stays open; close by clicking body
    await user.click(document.body);
    expect(screen.queryByText('Name')).not.toBeInTheDocument();
    // Reopen and restore
    await user.click(screen.getByRole('button', { name:/toggle columns/i }));
    const menu2 = await screen.findByRole('menu');
    await user.click(within(menu2).getByText('Name'));
    await user.click(document.body);
    expect(screen.getByText('Name')).toBeInTheDocument();
  });
});
