// CSV export utilities
export function toCSV(rows, columns) {
  if (!rows || !rows.length) return '';
  const headers = columns.map(c => escapeCsv(c.label || c.key));
  const lines = [headers.join(',')];
  for (const r of rows) {
    const line = columns.map(c => {
      const raw = c.exportValue ? c.exportValue(r) : r[c.key];
      return escapeCsv(raw);
    }).join(',');
    lines.push(line);
  }
  return lines.join('\n');
}

function escapeCsv(val) {
  if (val == null) return '';
  let s = String(val);
  if (/[",\n]/.test(s)) s = '"' + s.replace(/"/g, '""') + '"';
  return s;
}

export function downloadCSV(filename, csvText) {
  if (typeof document === 'undefined') return;
  const blob = new Blob([csvText], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename || 'export.csv';
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
