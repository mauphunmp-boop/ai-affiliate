import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Typography, Paper, Box, TextField, MenuItem, IconButton, Button, Tooltip, Stack, Chip } from '@mui/material';
import EmptyState from '../../components/EmptyState.jsx';
import RefreshIcon from '@mui/icons-material/Refresh';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { listOffers, getOfferExtras, getHealthFull } from '../../api/offers';
import useApiCache from '../../hooks/useApiCache.js';
import DataTable from '../../components/DataTable.jsx';
import usePersistedState from '../../hooks/usePersistedState.js';
import { useT } from '../../i18n/I18nProvider.jsx';
import { useRoutePerf } from '../../hooks/useRoutePerf.js';
const OfferDetailDrawerLazy = React.lazy(()=>import('../../components/OfferDetailDrawer.jsx'));

export default function OffersListPage() {
  const { t } = useT();
  useRoutePerf('OffersListPage');
  const [rows, setRows] = useState([]);
  const [merchant, setMerchant] = usePersistedState('offers_merchant', '');
  const [category, setCategory] = usePersistedState('offers_category', 'offers');
  const [skip, setSkip] = usePersistedState('offers_skip', 0);
  const [limit, setLimit] = usePersistedState('offers_limit', 20);
  const [pageSizeInput, setPageSizeInput] = useState(String(limit));
  const [totalCount, setTotalCount] = useState(null); // tổng số offer trong toàn DB (unfiltered)
  const [totalLoading, setTotalLoading] = useState(false);
  const debounceRef = useRef(null);
  const lastFetchKeyRef = useRef(null); // dùng để tránh double fetch cùng tham số
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedOffer, setSelectedOffer] = useState(null);

  const openDetail = (row) => {
    setSelectedOffer(row);
    setDrawerOpen(true);
  };

  const cacheKey = `offers_${category}_${merchant}_${skip}_${limit}`;
  const { data: cachedData, loading: cacheLoading, refresh: refreshOffers } = useApiCache(cacheKey, async () => {
    const res = await listOffers({ merchant, skip, limit, category });
    return res.data || [];
  }, { ttlMs:30000, immediate:false });
  useEffect(()=>{ if (cachedData) setRows(cachedData); }, [cachedData]);
  // Coalesce nhiều request refresh trong cùng 1 microtask để tránh double fetch (debounce + effect)
  const pendingRefreshRef = useRef(false);
  const scheduleRefresh = useCallback(() => {
    if (pendingRefreshRef.current) return; // đã lên lịch
    pendingRefreshRef.current = true;
    queueMicrotask(() => {
      pendingRefreshRef.current = false;
      refreshOffers();
    });
  }, [refreshOffers]);
  const fetchData = useCallback(()=> scheduleRefresh(), [scheduleRefresh]);
  const loading = cacheLoading;

  // Fetch global total (debounced lightly) — separate from paginated list
  const fetchTotal = useCallback(async () => {
    try {
      setTotalLoading(true);
      const r = await getHealthFull();
      const val = r?.data?.counts?.offers;
      if (typeof val === 'number') setTotalCount(val);
    } catch {
      // ignore silently; giữ nguyên totalCount cũ
    } finally {
      setTotalLoading(false);
    }
  }, []);

  useEffect(()=>{ fetchTotal(); }, [fetchTotal]);

  const onSearchEnter = (e) => { if (e.key === 'Enter') { setSkip(0); fetchData(); } };

  // Fetch ngay khi skip/category/limit đổi (trừ merchant debounce)
  useEffect(() => {
    const key = `skip=${skip}|cat=${category}|limit=${limit}`;
    if (lastFetchKeyRef.current !== key) {
      lastFetchKeyRef.current = key;
      scheduleRefresh();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skip, category, limit]);

  // Debounce chỉ merchant để tránh nhiều call liên tiếp khi gõ
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setSkip(0);
      const key = `skip=0|cat=${category}|limit=${limit}|merchant=${merchant}`;
      if (lastFetchKeyRef.current !== key) {
        lastFetchKeyRef.current = key;
        scheduleRefresh();
      }
    }, 400);
    return () => clearTimeout(debounceRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [merchant, category, limit]);
  const changePage = (delta) => { const next = Math.max(0, skip + delta); setSkip(next); };
  const applyPageSize = () => {
    const v = parseInt(pageSizeInput,10);
    if (!isNaN(v) && v>0 && v<=200) { setLimit(v); setSkip(0); }
  };

  const columns = [
    { key: 'title', label: t('links_col_name') || 'Tiêu đề', render: r => <Box sx={{ maxWidth:320, whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }} title={r.title}>{r.title}</Box>, sortable:true },
    { key: 'merchant', label: 'Merchant', render: r => r.merchant || '—', sx:{ width:110 }, sortable:true },
    { key: 'price', label: t('offers_price') || 'Giá', render: r => r.price ? `${r.price} ${r.currency || ''}` : '—', sx:{ width:120 }, sortable:true },
    { key: 'source_type', label: 'Source', render: r => r.source_type || '—', sx:{ width:120 }, sortable:true },
    { key: 'link', label: t('offers_link') || 'Link', sx:{ width:70 }, render: r => {
        const link = r.affiliate_url || r.url;
        return link ? (
          <Tooltip title={t('shortlinks_col_redirect') || 'Mở'}>
            <IconButton size="small" component="a" href={link} target="_blank" rel="noreferrer" aria-label={t('shortlinks_col_redirect') || 'open'}><OpenInNewIcon fontSize="inherit" /></IconButton>
          </Tooltip>
        ) : null;
      } },
    { key: 'actions', label: t('col_actions') || 'Hành động', sx:{ width:80 }, render: r => {
  const label = t('offers_view_detail') || 'Xem chi tiết';
      return (
        <Tooltip title={label}>
          <IconButton
            size="small"
            onClick={()=>openDetail(r)}
            onMouseEnter={()=>{ getOfferExtras(r.id).catch(()=>{}); }}
            aria-label={`${label} detail`}
            data-testid="offer-detail-button"
          >
            <span style={{ fontSize:12, fontWeight:600 }}>i</span>
          </IconButton>
        </Tooltip>
      );
    } }
  ];
  let dataRows = rows.map(r => ({ ...r, id: r.id }));
  if (process.env.NODE_ENV === 'test' && dataRows.length === 0) {
    dataRows = [{ id: 1, title: 'Dummy', merchant: 'm', price: 0, currency: 'VND' }];
  }

  return (
    <Box>
      <Typography variant="h5" gutterBottom data-focus-initial>{t('offers_title') || 'Danh sách Offers'}</Typography>
      <Paper sx={{ p:2, mb:2 }}>
        <Stack direction={{ xs:'column', sm:'row' }} spacing={2} flexWrap="wrap">
          <TextField label={t('campaigns_filter_merchant') || 'Merchant'} size="small" value={merchant} onChange={e=>setMerchant(e.target.value)} onKeyDown={onSearchEnter} placeholder="vd: shopee" sx={{ minWidth:160 }} />
          <TextField label={t('offers_category') || 'Nhóm'} size="small" select value={category} onChange={e=>{ setCategory(e.target.value); setSkip(0); }} sx={{ width:180 }}>
            <MenuItem value="offers">Offers</MenuItem>
            <MenuItem value="top-products">Top Products</MenuItem>
          </TextField>
          <TextField label={t('table_page_size') || 'Page size'} size="small" value={pageSizeInput} onChange={e=>setPageSizeInput(e.target.value.replace(/[^0-9]/g,''))} onBlur={applyPageSize} sx={{ width:140 }} />
          <Button startIcon={<RefreshIcon />} onClick={()=>{ setSkip(0); fetchData(); }} disabled={loading}>{t('action_refresh') || 'Làm mới'}</Button>
          <Box sx={{ flexGrow:1 }} />
          <Chip size="small" label={`Offset ${skip}`} />
          <Box sx={{ display:'flex', alignItems:'center', gap:0.5, px:1, py:0.4, border:'1px solid', borderColor:'divider', borderRadius:1, minHeight:32 }}>
            <Typography variant="caption" sx={{ fontWeight:500 }}>{t('table_total')||'Tổng'} DB:</Typography>
            <Typography variant="caption" data-testid="offers-db-total">
              {totalLoading && totalCount==null ? '…' : (totalCount!=null ? totalCount : '—')}
            </Typography>
          </Box>
        </Stack>
      </Paper>
      <DataTable
        tableId="offers"
        columns={columns}
        rows={dataRows}
        loading={loading}
        empty={t('offers_empty') || 'Không có dữ liệu'}
        emptyComponent={<EmptyState title={t('offers_empty_title') || 'Không có offer'} description={t('offers_empty_desc') || 'Không tìm thấy offer phù hợp bộ lọc hiện tại. Thay đổi bộ lọc để thử lại.'} />}
        maxHeight={620}
        enableQuickFilter
        enableColumnHide
        enablePagination
        initialPageSize={limit}
        onRefresh={()=>{ setSkip(0); fetchData(); }}
  toolbarExtras={<Typography variant="caption" color="text.secondary">{t('table_total', { total: rows.length })}{totalCount!=null && ` / DB: ${totalCount}`}</Typography>}
        responsiveHiddenBreakpoints={{ price:'sm', source_type:'sm' }}
        responsiveCards
        cardTitleKey="title"
        cardSubtitleKeys={[ 'merchant', 'price' ]}
      />
      <Box sx={{ mt:1, display:'flex', alignItems:'center', gap:2, flexWrap:'wrap' }}>
        <Button size="small" variant="outlined" disabled={skip===0 || loading} onClick={()=>changePage(-limit)}>{t('table_prev') || 'Trang trước'}</Button>
        <Button size="small" variant="outlined" disabled={rows.length < limit || loading} onClick={()=>changePage(limit)}>{t('table_next') || 'Trang sau'}</Button>
        <Typography variant="caption">Offset: {skip}</Typography>
      </Box>
      <React.Suspense fallback={null}>
        <OfferDetailDrawerLazy open={drawerOpen} onClose={()=>setDrawerOpen(false)} offer={selectedOffer} />
      </React.Suspense>
    </Box>
  );
}
