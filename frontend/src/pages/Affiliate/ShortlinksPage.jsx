import React, { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { useNotify } from '../../components/NotificationProvider.jsx';
import { Box, Paper, Typography, TextField, MenuItem, IconButton, Tooltip, InputAdornment, Button, Stack, Chip, Collapse } from '@mui/material';
import EmptyState from '../../components/EmptyState.jsx';
import ConfirmDialog from '../../components/ConfirmDialog.jsx';
import DataTable from '../../components/DataTable.jsx';
import CopyButton from '../../components/CopyButton.jsx';
import DeleteIcon from '@mui/icons-material/Delete';
import SearchIcon from '@mui/icons-material/Search';
import RefreshIcon from '@mui/icons-material/Refresh';
import BarChartIcon from '@mui/icons-material/BarChart';
import HideSourceIcon from '@mui/icons-material/HideSource';
import api from '../../api';
import usePersistedState from '../../hooks/usePersistedState.js';
import { useT } from '../../i18n/I18nProvider.jsx';

// Ghi chú: backend hiện trả list shortlinks theo các filter q, min_clicks, order

export default function ShortlinksPage() {
  const notify = useNotify();
  const { t } = useT();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [q, setQ] = usePersistedState('shortlinks_q', '');
  const [minClicks, setMinClicks] = usePersistedState('shortlinks_min', '');
  const [order, setOrder] = usePersistedState('shortlinks_order', 'newest');
  const [showChart, setShowChart] = usePersistedState('shortlinks_chart', false);
  const debounceRef = useRef(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (q.trim()) params.q = q.trim();
      if (minClicks) params.min_clicks = minClicks;
      if (order) params.order = order;
      const res = await api.get('/aff/shortlinks', { params });
      setRows(res.data || []);
    } catch (err) {
      console.error('Lỗi tải shortlinks', err);
    } finally {
      setLoading(false);
    }
  }, [q, minClicks, order]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Persist handled by hook

  // Debounce fetch
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => { fetchData(); }, 400);
    return () => clearTimeout(debounceRef.current);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, minClicks, order]);


  const [confirm, setConfirm] = useState({ open:false, token:null });
  const doDelete = async () => {
    const token = confirm.token; if (!token) return;
    try {
      await api.delete(`/aff/shortlinks/${token}`);
      setRows(r => r.filter(x => x.token !== token));
      notify('success', t('shortlinks_deleted'));
    } catch {
      notify('error', t('shortlinks_delete_failed'));
    } finally { setConfirm({ open:false, token:null }); }
  };

  const dataRows = rows.map(r => ({ ...r, id: r.token }));
  const columns = useMemo(()=>[
    { key: 'token', label: t('shortlinks_col_token'), sx:{ width:110 } },
    { key: 'click_count', label: t('shortlinks_col_clicks'), sx:{ width:80 } },
    { key: 'last_click_at', label: t('shortlinks_col_last_click'), sx:{ width:170 }, render: r => r.last_click_at ? new Date(r.last_click_at).toLocaleString() : '—' },
    { key: 'affiliate_url', label: t('shortlinks_col_affiliate_url'), render: r => (
        <Stack direction="row" spacing={0.5} alignItems="center" sx={{ maxWidth:280 }}>
          <Box sx={{ flex:1, whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>{r.affiliate_url}</Box>
          <CopyButton value={r.affiliate_url} title={t('shortlinks_copy_affiliate')} />
        </Stack>
      ) },
    { key: 'redirect', label: t('shortlinks_col_redirect'), render: r => {
        const redirect = `${window.location.origin}/r/${r.token}`;
        return (
          <Stack direction="row" spacing={0.5} alignItems="center">
            <a href={redirect} target="_blank" rel="noreferrer">/r/{r.token}</a>
            <CopyButton value={redirect} title={t('shortlinks_copy_redirect')} />
          </Stack>
        );
      }, sx:{ width:170 } },
    { key: 'actions', label: t('shortlinks_col_actions'), sx:{ width:90 }, render: r => (
        <Tooltip title={t('shortlinks_delete_title')}><IconButton size="small" color="error" onClick={()=>setConfirm({ open:true, token:r.token })}><DeleteIcon fontSize="inherit" /></IconButton></Tooltip>
      ) }
  ], [t]);

  // Stats / analytics
  const stats = useMemo(()=>{
    if (!rows.length) return { total:0, totalClicks:0, avg:0, top:[], recent:[] };
    const total = rows.length;
    const totalClicks = rows.reduce((s,r)=>s+(r.click_count||0),0);
    const avg = totalClicks / total;
    const top = [...rows].sort((a,b)=>(b.click_count||0)-(a.click_count||0)).slice(0,5);
    const recent = [...rows].sort((a,b)=> new Date(b.created_at||0) - new Date(a.created_at||0)).slice(0,5);
    return { total, totalClicks, avg, top, recent };
  }, [rows]);

  // Simple chart stub (no external lib) – distribution buckets by click_count
  const chartEl = useMemo(()=>{
    if (!showChart) return null;
    if (rows.length < 3) return <Typography variant="body2" color="text.secondary" sx={{ mb:1 }}>{t('shortlinks_chart_empty')}</Typography>;
    const buckets = [0,1,5,10,25,50,100];
    const counts = buckets.map((b,i)=> rows.filter(r=>{
      const c = r.click_count||0; const next = buckets[i+1];
      return next === undefined ? c >= b : (c >= b && c < next);
    }).length);
    const max = Math.max(...counts,1);
    return (
      <Box sx={{ display:'flex', alignItems:'flex-end', gap:1, mb:2, mt:1 }}>
        {counts.map((c,i)=>{
          const h = (c/max)*120;
          return (
            <Box key={i} sx={{ textAlign:'center' }}>
              <Box sx={{ width:22, height:h, background:'linear-gradient(180deg,#42a5f5,#1976d2)', borderRadius:0.5 }} />
              <Typography variant="caption">{buckets[i]}{buckets[i+1]?'–'+(buckets[i+1]-1):'+'}</Typography>
              <Typography variant="caption" display="block" sx={{ fontWeight:600 }}>{c}</Typography>
            </Box>
          );
        })}
      </Box>
    );
  }, [rows, showChart, t]);

  return (
    <Box>
      <Typography variant="h5" gutterBottom data-focus-initial>{t('shortlinks_title')}</Typography>
      <Paper sx={{ p:2, mb:2 }}>
        <Stack direction="row" spacing={2} flexWrap="wrap" alignItems="center" sx={{ mb:1 }}>
          <TextField size="small" label={t('shortlinks_search')} value={q} onChange={e=>setQ(e.target.value)} InputProps={{ startAdornment:<InputAdornment position="start"><SearchIcon fontSize="small"/></InputAdornment> }} />
          <TextField size="small" label={t('shortlinks_min_clicks')} value={minClicks} onChange={e=>setMinClicks(e.target.value.replace(/[^0-9]/g,''))} sx={{ width:130 }} />
          <TextField size="small" select label={t('shortlinks_sort')} value={order} onChange={e=>setOrder(e.target.value)} sx={{ width:170 }}>
            <MenuItem value="newest">{t('shortlinks_sort_newest')}</MenuItem>
            <MenuItem value="oldest">{t('shortlinks_sort_oldest')}</MenuItem>
            <MenuItem value="clicks_desc">{t('shortlinks_sort_clicks_desc')}</MenuItem>
          </TextField>
          <Button startIcon={<RefreshIcon />} onClick={fetchData} disabled={loading}>{t('shortlinks_refresh')}</Button>
          <Button size="small" variant="outlined" startIcon={showChart ? <HideSourceIcon/> : <BarChartIcon/>} onClick={()=>setShowChart(s=>!s)}>{showChart ? t('shortlinks_hide_chart') : t('shortlinks_show_chart')}</Button>
        </Stack>
        <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ mb: showChart?1:0 }}>
          <Chip label={`${t('shortlinks_stats_total')}: ${stats.total}`} size="small" />
            <Chip label={`${t('shortlinks_stats_total_clicks')}: ${stats.totalClicks}`} size="small" />
          <Chip label={`${t('shortlinks_stats_avg_clicks')}: ${stats.avg.toFixed(1)}`} size="small" />
        </Stack>
        <Collapse in={showChart} timeout="auto" unmountOnExit>{chartEl}</Collapse>
        {stats.top.length > 0 && showChart && (
          <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ mb:1 }}>
            {stats.top.map(tk => <Chip key={tk.token} label={`${tk.token}:${tk.click_count}`} size="small" color="primary" />)}
          </Stack>
        )}
      </Paper>
      <DataTable
        tableId="shortlinks"
        columns={columns}
        rows={dataRows}
        loading={loading}
        empty={t('shortlinks_empty')}
        emptyComponent={<EmptyState title={t('shortlinks_empty')} description="" />}
        enableColumnHide
        enablePagination
        initialPageSize={25}
        responsiveHiddenBreakpoints={{ affiliate_url:'md', last_click_at:'sm' }}
      />
      <ConfirmDialog
        open={confirm.open}
        title={t('shortlinks_delete_title')}
        message={t('shortlinks_delete_confirm', { token: confirm.token })}
        onClose={() => setConfirm({ open:false, token:null })}
        onConfirm={doDelete}
        danger
        confirmText={t('action_delete') || 'Delete'}
      />
    </Box>
  );
}
