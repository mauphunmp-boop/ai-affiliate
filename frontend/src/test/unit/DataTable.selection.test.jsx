import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';
import DataTable from '../../components/DataTable.jsx';

describe('DataTable selection', () => {
  test('select single and all', async () => {
    const rows = [ { id:1, name:'Alpha' }, { id:2, name:'Beta' } ];
    const cols = [ { key:'id', label:'ID', sortable:true }, { key:'name', label:'Name' } ];
    const spy = vi.fn();
    render(<DataTable tableId="sel" rows={rows} columns={cols} enableSelection onSelectionChange={spy} />);
    const user = userEvent.setup();
    const rowCb = screen.getByLabelText('select row 1');
    await user.click(rowCb);
    expect(spy).toHaveBeenLastCalledWith([1]);
    const selectAll = screen.getByLabelText('select all rows');
    await user.click(selectAll);
    expect(spy).toHaveBeenLastCalledWith([1,2]);
    await user.click(selectAll); // unselect
    expect(spy).toHaveBeenLastCalledWith([]);
  });
});
