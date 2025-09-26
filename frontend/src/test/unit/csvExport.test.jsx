import { toCSV } from '../../utils/csvExport.js';

describe('csvExport toCSV', () => {
  test('escapes values with comma and quotes', () => {
    const rows = [ { id:1, name:'Alpha' }, { id:2, name:'B,"eta' } ];
    const cols = [ { key:'id', label:'ID' }, { key:'name', label:'Name' } ];
    const csv = toCSV(rows, cols);
    const lines = csv.split('\n');
    expect(lines[0]).toBe('ID,Name');
    expect(lines[1]).toBe('1,Alpha');
    expect(lines[2]).toMatch(/^2,"B,""eta"$/);
  });
});
