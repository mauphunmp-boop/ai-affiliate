import React from 'react';
import { useT } from '../i18n/I18nProvider.jsx';
import {
  Paper, Table, TableHead, TableRow, TableCell, TableBody, Box, LinearProgress, Typography,
  IconButton, TextField, InputAdornment, Menu, MenuItem, Checkbox, ListItemText,
  TableSortLabel, Tooltip, Select, FormControl, FormHelperText, Stack, Button, Skeleton, useMediaQuery, Chip
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import ViewColumnIcon from '@mui/icons-material/ViewColumn';
import RefreshIcon from '@mui/icons-material/Refresh';

// Cấu trúc cột: { key, label, render?: (row)=>node, sx?, headerSx?, sortable?, sortKey? }
// Các khả năng: sort client, quick filter, column hide, pagination client.
export default function DataTable({
  columns,
  rows,
  loading,
  empty = 'Không có dữ liệu',
  size = 'small',
  paperProps = {},
  tableProps = {},
  stickyHeader = true,
  dense = false,
  maxHeight = 550,
  striped = true,
  tableId,
  enableQuickFilter = false,
  enableColumnHide = false,
  enablePagination = false,
  initialPageSize = 25,
  pageSizes = [10, 20, 25, 50, 100],
  onRefresh,
  emptyComponent,
  toolbarExtras, // React node đặt bên phải toolbar
  responsiveHiddenBreakpoints, // { columnKey: 'sm'|'md'|'lg' }
  enableSelection = false,
  selectionKey = 'id',
  onSelectionChange,
  onState, // callback: { processed, visibleColumns, filter, sort, page, pageSize, selection }
  responsiveCards = true, // bật chế độ hiển thị dạng thẻ ở màn hình nhỏ
  cardBreakpoint = 'sm', // ngưỡng breakpoint
  skeletonRows = 8, // số dòng skeleton khi loading
  cardTitleKey, // nếu cung cấp key, hiển thị nổi bật làm tiêu đề card
  cardSubtitleKeys // mảng key phụ hiển thị cạnh nhau nhỏ
}) {
  const storageColsKey = tableId ? `table_cols_${tableId}_hidden_v1` : null;
  const storagePageSizeKey = tableId ? `table_ps_${tableId}_v1` : null;

  const [hidden, setHidden] = React.useState(() => {
    if (!storageColsKey) return [];
    try { const raw = localStorage.getItem(storageColsKey); return raw ? JSON.parse(raw) : []; } catch { return []; }
  });
  const [filter, setFilter] = React.useState('');
  const [anchor, setAnchor] = React.useState(null);
  const [sort, setSort] = React.useState(null); // { key, direction }
  const [page, setPage] = React.useState(0);
  const [pageSize, setPageSize] = React.useState(() => {
    if (!storagePageSizeKey) return initialPageSize;
    try { const raw = parseInt(localStorage.getItem(storagePageSizeKey),10); return raw || initialPageSize; } catch { return initialPageSize; }
  });
  const [selection, setSelection] = React.useState([]); // selected row ids

  // Persist hidden + pageSize
  React.useEffect(() => {
    if (storageColsKey) { try { localStorage.setItem(storageColsKey, JSON.stringify(hidden)); } catch {} }
  }, [hidden, storageColsKey]);
  React.useEffect(() => {
    if (storagePageSizeKey) { try { localStorage.setItem(storagePageSizeKey, String(pageSize)); } catch {} }
  }, [pageSize, storagePageSizeKey]);

  const mqlRef = React.useRef({});
  const [, setForce] = React.useState(0); // internal rerender trigger for media query listeners
  const isBpHidden = (key) => {
    if (!responsiveHiddenBreakpoints || !responsiveHiddenBreakpoints[key]) return false;
    if (typeof window === 'undefined') return false;
    const map = { sm:600, md:900, lg:1200 };
    const max = map[responsiveHiddenBreakpoints[key]];
    if (!max) return false;
    const q = `(max-width:${max}px)`;
    let entry = mqlRef.current[q];
    if (!entry) {
      const m = window.matchMedia(q);
      entry = { m, matches: m.matches };
  m.addEventListener('change', e => { entry.matches = e.matches; setForce(v=>v+1); });
      mqlRef.current[q] = entry;
    }
    return entry.matches;
  };
  const visibleColumns = columns.filter(c => !hidden.includes(c.key) && !isBpHidden(c.key));
  const allSelectableIds = React.useMemo(() => enableSelection ? rows.map(r => r[selectionKey]).filter(v => v != null) : [], [rows, selectionKey, enableSelection]);
  const isAllSelected = enableSelection && allSelectableIds.length > 0 && selection.length === allSelectableIds.length;
  const toggleSelectAll = () => {
    setSelection(() => isAllSelected ? [] : [...allSelectableIds]);
  };
  const toggleRow = (row) => {
    const id = row[selectionKey];
    if (id == null) return;
  setSelection(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  };

  const toggleHide = (key) => {
    setHidden(h => h.includes(key) ? h.filter(x => x !== key) : [...h, key]);
  };

  const handleSort = (col) => {
    if (!col.sortable) return;
    setSort(prev => {
      if (!prev || prev.key !== col.key) return { key: col.key, direction: 'asc' };
      if (prev.direction === 'asc') return { key: col.key, direction: 'desc' };
      return null; // remove sort
    });
  };

  // Filtering
  const processed = React.useMemo(() => {
    let out = rows;
    if (enableQuickFilter && filter.trim()) {
      const needle = filter.trim().toLowerCase();
      out = out.filter(r => visibleColumns.some(c => {
        if (c.renderFilter) return c.renderFilter(r, needle);
        const val = r[c.sortKey || c.key];
        return val != null && String(val).toLowerCase().includes(needle);
      }));
    }
    if (sort) {
      const col = columns.find(c => c.key === sort.key);
      if (col) {
        const key = col.sortKey || col.key;
        out = [...out].sort((a,b) => {
          const va = a[key];
          const vb = b[key];
          if (va == null && vb == null) return 0;
          if (va == null) return -1;
          if (vb == null) return 1;
          if (typeof va === 'number' && typeof vb === 'number') return sort.direction === 'asc' ? va - vb : vb - va;
          return sort.direction === 'asc' ? String(va).localeCompare(String(vb)) : String(vb).localeCompare(String(va));
        });
      }
    }
    return out;
  }, [rows, enableQuickFilter, filter, visibleColumns, sort, columns]);

  // Pagination
  const total = processed.length;
  const originalTotal = rows.length;
  let paged = processed;
  const pageCount = enablePagination ? Math.ceil(total / pageSize) : 1;
  if (enablePagination) {
    const start = page * pageSize;
    paged = processed.slice(start, start + pageSize);
  }

  React.useEffect(() => { setPage(0); }, [filter, pageSize, sort, rows]);
  React.useEffect(() => { if (onSelectionChange) onSelectionChange(selection); }, [selection, onSelectionChange]);
  React.useEffect(() => { if (onState) onState({ processed, visibleColumns, filter, sort, page, pageSize, selection }); }, [processed, visibleColumns, filter, sort, page, pageSize, selection, onState]);

  // useT is always defined (imported), call unconditionally to satisfy React Hooks rules
  const { t } = useT();
  const tKey = React.useCallback((key, fallback, params) => {
    try {
      const val = t(key, params);
      if (!val || val === key) return fallback;
      return val;
    } catch { return fallback; }
  }, [t]);
  const liveRef = React.useRef(null);

  // Announce pagination & filter changes for screen readers
  React.useEffect(() => {
    if (!enablePagination) return;
    const msg = t('table_a11y_page_change', { page: page+1, pages: pageCount||1, total });
    if (liveRef.current) {
      liveRef.current.textContent = msg;
    }
  }, [page, pageSize, total, pageCount, enablePagination, t]);

  React.useEffect(() => {
    if (!enableQuickFilter || !filter.trim()) return;
    if (liveRef.current) {
      liveRef.current.textContent = t('table_a11y_filter_applied', { count: total });
    }
  }, [filter, total, enableQuickFilter, t]);
  // Build media query string deterministically then call hook once (avoid conditional hook calls)
  const cardQuery = React.useMemo(() => {
    if (!responsiveCards) return null;
    const map = { xs:0, sm:600, md:900, lg:1200, xl:1536 };
    if (typeof cardBreakpoint === 'string' && map[cardBreakpoint] != null) return `(max-width:${map[cardBreakpoint]}px)`;
    if (typeof cardBreakpoint === 'number') return `(max-width:${cardBreakpoint}px)`;
    if (typeof cardBreakpoint === 'string') return cardBreakpoint; // raw query string
    return null;
  }, [responsiveCards, cardBreakpoint]);
  const isNarrow = useMediaQuery(cardQuery || '(max-width:0px)') && !!cardQuery;
  const useCards = !!responsiveCards && isNarrow;

  const renderSkeletonTable = () => (
    <Table size={size} stickyHeader={stickyHeader} {...tableProps}>
      <TableHead>
        <TableRow>
          {enableSelection && <TableCell />}
          {visibleColumns.map(c => <TableCell key={c.key}>{c.label}</TableCell>)}
        </TableRow>
      </TableHead>
      <TableBody>
        {Array.from({ length: skeletonRows }).map((_,i) => (
          <TableRow key={i}>
            {enableSelection && <TableCell><Skeleton variant="rectangular" width={18} height={18} /></TableCell>}
            {visibleColumns.map(c => <TableCell key={c.key}><Skeleton height={16} /></TableCell>)}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );

  const renderCardSkeleton = () => (
    <Stack spacing={1} sx={{ py:1 }}>
      {Array.from({ length: skeletonRows }).map((_,i)=>(
        <Box key={i} sx={{ border:'1px solid', borderColor:'divider', borderRadius:2, p:1.2 }}>
          <Skeleton width="40%" height={18} />
          <Skeleton width="65%" height={14} />
          <Skeleton width="80%" height={12} />
        </Box>
      ))}
    </Stack>
  );

  const cardContent = () => {
    if (loading && rows.length === 0) return renderCardSkeleton();
    if (!paged.length) return <Typography variant="body2" color="text.secondary" sx={{ py:3, textAlign:'center' }}>{empty}</Typography>;
    return (
      <Stack spacing={1} sx={{ py:0.5 }}>
        {paged.map((r, idx) => {
          const rowId = r[selectionKey];
            const selected = enableSelection && selection.includes(rowId);
          return (
            <Box key={r.id || rowId || idx} sx={{ position:'relative', border:'1px solid', borderColor:'divider', borderRadius:2, p:1.1, bgcolor: selected ? 'action.selected' : 'background.paper' }}>
              {enableSelection && (
                <Checkbox
                  size="small"
                  checked={selected}
                  onChange={() => toggleRow(r)}
                  sx={{ position:'absolute', top:4, right:4 }}
                />
              )}
              <Stack spacing={0.5}>
                {cardTitleKey && (
                  <Typography variant="subtitle2" sx={{ fontWeight:600, pr:4, wordBreak:'break-word' }}>{r[cardTitleKey]}</Typography>
                )}
                {Array.isArray(cardSubtitleKeys) && cardSubtitleKeys.length>0 && (
                  <Stack direction="row" spacing={1} flexWrap="wrap">
                    {cardSubtitleKeys.map(k => r[k] != null && <Chip key={k} size="small" label={String(r[k])} />)}
                  </Stack>
                )}
                <Box sx={{ display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(120px,1fr))', gap:0.5, mt:0.5 }}>
                  {visibleColumns.map(c => {
                    if (c.key === cardTitleKey) return null; // đã hiển thị
                    if (cardSubtitleKeys && cardSubtitleKeys.includes(c.key)) return null;
                    return (
                      <Box key={c.key} sx={{ minWidth:0 }}>
                        <Typography variant="caption" sx={{ opacity:0.7 }}>{c.label}</Typography>
                        <Typography variant="body2" sx={{ fontSize:13, wordBreak:'break-word' }}>
                          {c.render ? c.render(r) : (r[c.key] == null ? '—' : String(r[c.key]))}
                        </Typography>
                      </Box>
                    );
                  })}
                </Box>
              </Stack>
            </Box>
          );
        })}
      </Stack>
    );
  };

  return (
  <Paper data-testid="datatable" sx={{ position: 'relative', overflow: 'hidden', ...paperProps.sx }} {...paperProps}>
      {/* aria-live region for announcements */}
      <Box sx={{ position:'absolute', width:1, height:1, overflow:'hidden', clip:'rect(1px,1px,1px,1px)', whiteSpace:'nowrap' }} aria-live="polite" aria-atomic="true" ref={liveRef} />
      { (enableQuickFilter || enableColumnHide || onRefresh || toolbarExtras) && (
        <Box sx={{ p:1.5, pb:1, display:'flex', gap:1, alignItems:'center', flexWrap:'wrap' }}>
          {enableQuickFilter && (
            <TextField
              size="small"
              placeholder={tKey('table_quick_filter_placeholder','Lọc nhanh...')}
              value={filter}
              onChange={e=>setFilter(e.target.value)}
              InputProps={{ startAdornment:<InputAdornment position="start"><SearchIcon fontSize="small"/></InputAdornment> }}
              sx={{ minWidth:200 }}
            />
          )}
          {onRefresh && (
            <Tooltip title={t('table_refresh')}><span><IconButton aria-label="refresh" size="small" disabled={loading} onClick={onRefresh}><RefreshIcon fontSize="inherit" /></IconButton></span></Tooltip>
          )}
          {enableColumnHide && (
            <Tooltip title={t('table_toggle_columns')}><IconButton aria-label="toggle columns" size="small" onClick={e=>setAnchor(e.currentTarget)}><ViewColumnIcon fontSize="inherit" /></IconButton></Tooltip>
          )}
          <Box sx={{ flexGrow:1 }} />
          <Tooltip title={t('table_reset')}><span><IconButton aria-label="reset table" size="small" onClick={()=>{ setHidden([]); setSort(null); setFilter(''); setPage(0); setPageSize(initialPageSize); setSelection([]); }}><RefreshIcon fontSize="inherit" /></IconButton></span></Tooltip>
          {toolbarExtras}
        </Box>
      )}
      {loading && <Box sx={{ position: 'absolute', inset: 0, pointerEvents:'none', zIndex: 1 }}><LinearProgress sx={{ position: 'absolute', top: 0, left: 0, right: 0 }} /></Box>}
      {!useCards && (
        <Box sx={{ maxHeight, overflow: 'auto' }}>
          {loading && rows.length === 0 ? renderSkeletonTable() : (
            <Table size={size} stickyHeader={stickyHeader} {...tableProps}>
              <TableHead>
                <TableRow>
                  {enableSelection && (
                    <TableCell padding="checkbox" sx={{ width:48 }}>
                      <Checkbox
                        size="small"
                        indeterminate={selection.length > 0 && !isAllSelected}
                        checked={isAllSelected}
                        onChange={toggleSelectAll}
                        inputProps={{ 'aria-label': 'select all rows' }}
                      />
                    </TableCell>
                  )}
                  {visibleColumns.map(c => {
                    const active = sort?.key === c.key;
                    return (
                      <TableCell key={c.key} sx={c.headerSx || c.sx} sortDirection={active ? sort.direction : false}>
                        {c.sortable ? (
                          <TableSortLabel active={active} direction={active ? sort.direction : 'asc'} onClick={() => handleSort(c)}>
                            {c.label}
                          </TableSortLabel>
                        ) : c.label }
                      </TableCell>
                    );
                  })}
                </TableRow>
              </TableHead>
              <TableBody>
                {paged.map((r, idx) => {
                  const rowId = r[selectionKey];
                  const selected = enableSelection && selection.includes(rowId);
                  return (
                    <TableRow key={r.id || r.key || JSON.stringify(r)} hover selected={selected} sx={(dense || (typeof window !== 'undefined' && window.innerWidth < 600)) ? { '& td': { py: 0.6 } } : undefined}>
                      {enableSelection && (
                        <TableCell padding="checkbox">
                          <Checkbox
                            size="small"
                            checked={selected}
                            onChange={() => toggleRow(r)}
                            inputProps={{ 'aria-label': `select row ${rowId}${r.platform ? ' ' + r.platform : ''}` }}
                          />
                        </TableCell>
                      )}
                      {visibleColumns.map(c => (
                        <TableCell key={c.key} sx={{ ...(c.sx || {}), ...(striped && idx % 2 === 1 ? { backgroundColor: 'action.hover' } : {}) }}>
                          {c.render ? c.render(r) : r[c.key]}
                        </TableCell>
                      ))}
                    </TableRow>
                  );
                })}
                {!loading && paged.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={visibleColumns.length + (enableSelection ? 1 : 0)} align="center" sx={{ p:0 }}>
                      {emptyComponent || <Typography variant="body2" color="text.secondary" sx={{ py:3 }}>{empty}</Typography>}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </Box>
      )}
      {useCards && (
        <Box sx={{ maxHeight, overflow:'auto', px:1 }}>
          {cardContent()}
        </Box>
      )}
      {enablePagination && (
        <Box sx={{ display:'flex', alignItems:'center', gap:2, px:1.5, py:1, borderTop: theme=>`1px solid ${theme.palette.divider}`, flexWrap:'wrap' }}>
          <Typography variant="caption">{t('table_total', { total })}{total !== originalTotal ? t('table_filtered_from', { original: originalTotal }) : ''}</Typography>
          <Stack direction="row" spacing={1} alignItems="center">
            <Button size="small" disabled={page===0} onClick={()=>setPage(p=>Math.max(0,p-1))}>{tKey('table_prev','Trước')}</Button>
            <Typography variant="caption">{tKey('table_page_of',`Trang ${page+1}/${pageCount||1}`, { page: page+1, pages: pageCount||1 })}</Typography>
            <Button size="small" disabled={page>=pageCount-1} onClick={()=>setPage(p=>Math.min(pageCount-1,p+1))}>{tKey('table_next','Sau')}</Button>
          </Stack>
          <FormControl size="small" sx={{ minWidth:90 }}>
            <Select value={pageSize} onChange={e=>setPageSize(Number(e.target.value))}>
              {pageSizes.map(ps => <MenuItem key={ps} value={ps}>{t('table_per_page_option', { n: ps })}</MenuItem>)}
            </Select>
            <FormHelperText>{t('table_page_size')}</FormHelperText>
          </FormControl>
          <Box sx={{ flexGrow:1 }} />
          {sort && <Tooltip title={t('table_clear_sort')}><Button size="small" onClick={()=>setSort(null)}>{t('table_reset_sort')}</Button></Tooltip>}
        </Box>
      )}
  <Menu open={!!anchor} onClose={()=>setAnchor(null)} anchorEl={anchor}>
        {columns.map(c => (
          <MenuItem key={c.key} dense onClick={()=>{ toggleHide(c.key); setAnchor(null); }}>
            <Checkbox size="small" checked={!hidden.includes(c.key)} />
            <ListItemText primaryTypographyProps={{ variant:'body2' }}>{c.label}</ListItemText>
          </MenuItem>
        ))}
        {hidden.length > 0 && (
          <MenuItem onClick={()=>setHidden([])} dense><ListItemText primary={t('table_show_all_columns')} /></MenuItem>
        )}
      </Menu>
    </Paper>
  );
}


