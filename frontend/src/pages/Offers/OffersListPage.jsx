import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Typography, Paper, Box, TextField, MenuItem, IconButton, Button, Tooltip, Stack, Chip, Drawer, CircularProgress, Divider } from '@mui/material';
import EmptyState from '../../components/EmptyState.jsx';
import RefreshIcon from '@mui/icons-material/Refresh';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { listOffers, getOfferExtras } from '../../api/offers';
import DataTable from '../../components/DataTable.jsx';
import usePersistedState from '../../hooks/usePersistedState.js';
import { useT } from '../../i18n/I18nProvider.jsx';

export default function OffersListPage() {
  const { t } = useT();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [merchant, setMerchant] = usePersistedState('offers_merchant', '');
  const [category, setCategory] = usePersistedState('offers_category', 'offers');
  const [skip, setSkip] = usePersistedState('offers_skip', 0);
  const [limit, setLimit] = usePersistedState('offers_limit', 20);
  const [pageSizeInput, setPageSizeInput] = useState(String(limit));
  const debounceRef = useRef(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detail, setDetail] = useState(null);

  const openDetail = async (row) => {
    setDrawerOpen(true); setDetail(null); setDetailLoading(true);
    try {
      const r = await getOfferExtras(row.id);
      setDetail(r.data);
    } catch (e) {
      setDetail({ error: e?.normalized?.message || e.message });
    } finally { setDetailLoading(false); }
  };

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listOffers({ merchant, skip, limit, category });
      setRows(res.data || []);
    } catch (e) {
      console.error('Lỗi tải offers', e);
    } finally { setLoading(false); }
  }, [merchant, skip, limit, category]);

  useEffect(()=>{ fetchData(); }, [fetchData]);

  const onSearchEnter = (e) => { if (e.key === 'Enter') { setSkip(0); fetchData(); } };

  // Debounce merchant/category/limit changes (skip manual refresh)
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => { setSkip(0); fetchData(); }, 400);
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
    { key: 'actions', label: t('col_actions') || 'Hành động', sx:{ width:80 }, render: r => (
      <Tooltip title={t('offers_view_detail') || 'Xem chi tiết'}>
        <IconButton size="small" onClick={()=>openDetail(r)} aria-label={t('offers_view_detail') || 'detail'}>
          <span style={{ fontSize:12, fontWeight:600 }}>i</span>
        </IconButton>
      </Tooltip>
    ) }
  ];
  const dataRows = rows.map(r => ({ ...r, id: r.id }));

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
        toolbarExtras={<Typography variant="caption" color="text.secondary">{t('table_total', { total: rows.length })}</Typography>}
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
      <Drawer anchor="right" open={drawerOpen} onClose={()=>setDrawerOpen(false)} sx={{ '& .MuiDrawer-paper': { width:{ xs:'100%', sm:420 }, p:2 } }}>
        <Stack spacing={1} sx={{ height:'100%' }}>
          <Typography variant="h6" gutterBottom>{t('offers_detail_title') || 'Chi tiết Offer'}</Typography>
          {detailLoading && <Stack flex={1} alignItems="center" justifyContent="center"><CircularProgress size={32} /><Typography variant="body2" sx={{ mt:1 }}>{t('offers_detail_loading')||'Đang tải...'}</Typography></Stack>}
          {!detailLoading && !detail && <Typography variant="body2" color="text.secondary">{t('offers_detail_loading')||'Đang tải...'}</Typography>}
          {!detailLoading && detail && detail.error && <Typography color="error" variant="body2">{detail.error}</Typography>}
          {!detailLoading && detail && !detail.error && (
            <Box sx={{ overflowY:'auto', pr:1 }}>
              <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ mb:1 }}>
                <Chip label={`ID: ${detail.offer.id}`} size="small" />
                {detail.offer.merchant && <Chip label={detail.offer.merchant} size="small" />}
                {detail.offer.price && <Chip label={`${detail.offer.price} ${detail.offer.currency||''}`} size="small" />}
                {detail.offer.source_type && <Chip label={detail.offer.source_type} size="small" />}
                {detail.offer.approval_status && <Chip label={detail.offer.approval_status} size="small" />}
                {detail.offer.eligible_commission && <Chip color="success" label={t('offers_detail_commission_eligible')||'Eligible'} size="small" />}
                {detail.offer.affiliate_link_available && <Chip color="primary" label={t('offers_detail_affiliate_link_available')||'Aff link'} size="small" />}
              </Stack>
              <Typography variant="subtitle2" sx={{ fontWeight:600 }}>{detail.offer.title}</Typography>
              <Typography variant="body2" sx={{ mb:1, wordBreak:'break-word' }}>{detail.offer.desc || detail.offer.url}</Typography>
              {detail.offer.affiliate_url && <Button size="small" variant="outlined" component="a" href={detail.offer.affiliate_url} target="_blank" rel="noreferrer">Affiliate</Button>}
              <Button size="small" sx={{ ml:1 }} variant="text" component="a" href={detail.offer.url} target="_blank" rel="noreferrer">URL</Button>
              <Divider sx={{ my:1.5 }} />
              <Typography variant="subtitle2" gutterBottom>{t('offers_detail_campaign')||'Campaign'}</Typography>
              {!detail.campaign && <Typography variant="body2" color="text.secondary" sx={{ mb:1 }}>{t('offers_detail_no_campaign')||'Không có campaign'}</Typography>}
              {detail.campaign && (
                <Stack spacing={0.3} sx={{ mb:1 }}>
                  <Typography variant="body2">ID: {detail.campaign.campaign_id}</Typography>
                  {detail.campaign.status && <Typography variant="body2">Status: {detail.campaign.status}</Typography>}
                  {detail.campaign.user_registration_status && <Typography variant="body2">User: {detail.campaign.user_registration_status}</Typography>}
                </Stack>
              )}
              <Typography variant="subtitle2" sx={{ mt:1 }} gutterBottom>{t('offers_detail_promotions')||'Promotions'} ({detail.counts?.promotions||0})</Typography>
              {(!detail.promotions || detail.promotions.length===0) && <Typography variant="body2" color="text.secondary" sx={{ mb:1 }}>{t('offers_detail_empty')||'Không có'}</Typography>}
              <Stack spacing={0.8} sx={{ mb:1 }}>
                {detail.promotions && detail.promotions.map(p => (
                  <Box key={p.id} sx={{ border:'1px solid', borderColor:'divider', p:0.7, borderRadius:1 }}>
                    <Typography variant="body2" sx={{ fontWeight:500 }}>{p.name || '—'}</Typography>
                    {p.coupon && <Chip size="small" label={p.coupon} sx={{ mt:0.3 }} />}
                    {p.content && <Typography variant="caption" sx={{ display:'block', mt:0.3 }}>{p.content}</Typography>}
                  </Box>
                ))}
              </Stack>
              <Typography variant="subtitle2" gutterBottom>{t('offers_detail_policies')||'Commission Policies'} ({detail.counts?.commission_policies||0})</Typography>
              {(!detail.commission_policies || detail.commission_policies.length===0) && <Typography variant="body2" color="text.secondary" sx={{ mb:1 }}>{t('offers_detail_empty')||'Không có'}</Typography>}
              <Stack spacing={0.8}>
                {detail.commission_policies && detail.commission_policies.map(p => (
                  <Box key={p.id} sx={{ border:'1px solid', borderColor:'divider', p:0.7, borderRadius:1 }}>
                    <Typography variant="body2" sx={{ fontWeight:500 }}>{p.reward_type || '—'} {p.sales_ratio!=null && <Chip size="small" label={`${p.sales_ratio}%`} />}</Typography>
                    {(p.sales_price!=null) && <Typography variant="caption">Sales price: {p.sales_price}</Typography>}
                  </Box>
                ))}
              </Stack>
              {detail.offer.extra && (
                <Box sx={{ mt:2 }}>
                  <Typography variant="subtitle2" gutterBottom>{t('offers_detail_extra')||'Extra (raw)'}</Typography>
                  <Paper variant="outlined" sx={{ p:1, maxHeight:140, overflow:'auto', fontFamily:'monospace', fontSize:12 }}>
                    {detail.offer.extra}
                  </Paper>
                </Box>
              )}
            </Box>
          )}
        </Stack>
      </Drawer>
    </Box>
  );
}
