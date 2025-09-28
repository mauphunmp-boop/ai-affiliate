import React from 'react';
import { Paper, Typography, Stack, Button, Tabs, Tab, Box, Chip, TextField, IconButton, Tooltip, Collapse } from '@mui/material';
import SkeletonSection from '../../components/SkeletonSection.jsx';
import RefreshIcon from '@mui/icons-material/Refresh';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import DataTable from '../../components/DataTable.jsx';
import { useNotify } from '../../components/NotificationProvider.jsx';
import { useT } from '../../i18n/I18nProvider.jsx';
import api from '../../api.js';
import useApiCache from '../../hooks/useApiCache.js';
import { useRoutePerf } from '../../hooks/useRoutePerf.js';
const CampaignExtrasDrawerLazy = React.lazy(()=>import('../../components/CampaignExtrasDrawer.jsx'));

export default function CampaignsDashboard() {
  const { t } = useT();
  useRoutePerf('CampaignsDashboard');
  const notify = useNotify();
  const [tab, setTab] = React.useState(0);
  const { data: summary, loading: loadingSummary, refresh: refreshSummary } = useApiCache('campaigns_summary', async () => {
    const r = await api.get('/campaigns/summary');
    return r.data;
  }, { ttlMs:60000 });
  const [alerts, setAlerts] = React.useState([]);
  const [filters, setFilters] = React.useState({ status:'', user_status:'', merchant:'' });
  const [backfillLimit, setBackfillLimit] = React.useState('200');
  const [backfilling, setBackfilling] = React.useState(false);
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [extrasLoading, setExtrasLoading] = React.useState(false);
  const [extras, setExtras] = React.useState(null);

  const openExtras = async (cid) => {
    setDrawerOpen(true); setExtras(null); setExtrasLoading(true);
    try { const r = await api.get(`/campaigns/${encodeURIComponent(cid)}/extras`); setExtras(r.data); }
    catch (e) { setExtras({ error: e?.normalized?.message || e.message }); }
    finally { setExtrasLoading(false); }
  };

  const loadSummary = async () => { try { await refreshSummary(); } catch(e) { notify('error', e?.normalized?.message||e.message); } };
  const loadAlerts = async () => {
    try { const r = await api.get('/alerts/campaigns-registration'); setAlerts(r.data||[]); } catch { /* noop */ }
  };
  const campaignsKey = `campaigns_${filters.status}_${filters.user_status}_${filters.merchant}`;
  const { data: campaignsData, loading: campaignsLoading, refresh: refreshCampaigns } = useApiCache(campaignsKey, async () => {
    const params = new URLSearchParams();
    if (filters.status) params.append('status', filters.status);
    if (filters.user_status) params.append('user_status', filters.user_status);
    if (filters.merchant) params.append('merchant', filters.merchant);
    const r = await api.get('/campaigns' + (params.toString()?`?${params.toString()}`:''));
    return r.data||[];
  }, { ttlMs:30000, refreshDeps:[filters.status, filters.user_status, filters.merchant] });
  const loadCampaigns = React.useCallback(async () => { try { await refreshCampaigns(); } catch(e){ notify('error', e?.normalized?.message||e.message); } }, [refreshCampaigns, notify]);

  React.useEffect(()=>{ loadAlerts(); loadCampaigns(); }, [loadCampaigns]);

  const backfill = async () => {
    setBackfilling(true);
    try {
      const r = await api.post(`/campaigns/backfill-user-status?limit=${encodeURIComponent(backfillLimit||'200')}`);
      notify('success', t('campaigns_backfill_done', { fixed: r.data?.fixed||0 }));
      loadSummary();
      loadCampaigns();
    }
    catch(err){ notify('error', err?.normalized?.message||err.message); }
    finally { setBackfilling(false); }
  };

  const columnsAlerts = React.useMemo(()=>[
    { field:'campaign_id', headerName:t('campaigns_alert_campaign_id'), width:120 },
    { field:'merchant', headerName:t('campaigns_alert_merchant'), width:120 },
    { field:'name', headerName:t('campaigns_alert_name'), width:200 },
    { field:'status', headerName:t('campaigns_alert_status'), width:110 },
    { field:'user_status', headerName:t('campaigns_alert_user_status'), width:130 },
    { field:'start_time', headerName:t('campaigns_column_start'), width:140 },
    { field:'end_time', headerName:t('campaigns_column_end'), width:140 },
    { field:'actions', headerName:'', width:70, renderCell:(_,row)=>(
      <Tooltip title={t('campaigns_view_description')}>
        <IconButton size="small" component="a" href={`/api/campaigns/${encodeURIComponent(row.campaign_id)}/description`} target="_blank" rel="noopener noreferrer"><OpenInNewIcon fontSize="inherit" /></IconButton>
      </Tooltip>
    )}
  ], [t]);

  const columnsTable = React.useMemo(()=>[
    { field:'campaign_id', headerName:t('campaigns_column_campaign_id'), width:120 },
    { field:'merchant', headerName:t('campaigns_column_merchant'), width:120 },
    { field:'name', headerName:t('campaigns_column_name'), width:220 },
    { field:'status', headerName:t('campaigns_column_status'), width:110 },
    { field:'user_registration_status', headerName:t('campaigns_column_user_status'), width:140 },
    { field:'start_time', headerName:t('campaigns_column_start'), width:140 },
    { field:'end_time', headerName:t('campaigns_column_end'), width:140 },
    { field:'updated_at', headerName:t('campaigns_column_updated'), width:160 },
    { field:'actions', headerName:'', width:90, renderCell:(_,row)=>(
      <Stack direction="row" spacing={0.5}>
        <Tooltip title={t('campaigns_view_description')}>
          <IconButton size="small" component="a" href={`/api/campaigns/${encodeURIComponent(row.campaign_id)}/description`} target="_blank" rel="noopener noreferrer"><OpenInNewIcon fontSize="inherit" /></IconButton>
        </Tooltip>
        <Tooltip title={t('campaigns_view_extras')}>
          <IconButton
            size="small"
            onClick={()=>openExtras(row.campaign_id)}
            onMouseEnter={()=>{ // prefetch extras nhẹ
              api.get(`/campaigns/${encodeURIComponent(row.campaign_id)}/extras`).catch(()=>{});
            }}
          ><PlayArrowIcon fontSize="inherit" /></IconButton>
        </Tooltip>
      </Stack>
    )}
  ], [t]);

  const [showMerchants, setShowMerchants] = React.useState(false);
  const SummaryView = () => (
    <Box>
  {!summary && loadingSummary && <SkeletonSection variant="table" rows={3} />}
      {summary && (
        <>
          <Stack direction={{ xs:'column', sm:'row' }} spacing={2} flexWrap="wrap" sx={{ mb:2 }}>
            <Box sx={{ p:1.5, flex:1, minWidth:200, borderRadius:2, bgcolor:'primary.main', color:'primary.contrastText' }}>
              <Typography variant="caption" sx={{ opacity:0.8 }}>{t('campaigns_total')}</Typography>
              <Typography variant="h6" sx={{ m:0 }}>{summary.total}</Typography>
            </Box>
            <Box sx={{ p:1.5, flex:1, minWidth:200, borderRadius:2, bgcolor:'success.main', color:'success.contrastText' }}>
              <Typography variant="caption" sx={{ opacity:0.8 }}>{t('campaigns_running_approved')}</Typography>
              <Typography variant="h6" sx={{ m:0 }}>{summary.running_approved_count}</Typography>
            </Box>
            <Box sx={{ p:1.5, flex:1, minWidth:220, borderRadius:2, bgcolor:'info.main', color:'info.contrastText', position:'relative' }}>
              <Typography variant="caption" sx={{ opacity:0.8 }}>{t('campaigns_approved_merchants')}</Typography>
              <Typography variant="h6" sx={{ m:0 }}>{summary.approved_merchants?.length||0}</Typography>
              <Button size="small" variant="outlined" onClick={()=>setShowMerchants(s=>!s)} aria-label={showMerchants ? 'Ẩn danh sách merchants đã duyệt' : 'Xem danh sách merchants đã duyệt'} sx={{ position:'absolute', top:8, right:8, bgcolor:'rgba(255,255,255,0.15)' }}>{showMerchants ? 'Ẩn' : 'Xem'}</Button>
            </Box>
          </Stack>
          <Collapse in={showMerchants} unmountOnExit>
            <Paper variant="outlined" sx={{ p:1.5, mb:2 }}>
              <Typography variant="subtitle2" gutterBottom>{t('campaigns_approved_merchants')}</Typography>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                {(summary.approved_merchants||[]).map(m => <Chip key={m} size="small" label={m} />)}
              </Stack>
            </Paper>
          </Collapse>
          <Stack direction={{ xs:'column', md:'row' }} spacing={4} alignItems="flex-start">
            <Box flex={1}>
              <Typography variant="subtitle2" gutterBottom>{t('campaigns_by_status')}</Typography>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>{Object.entries(summary.by_status||{}).map(([k,v])=> <Chip key={k} label={`${k}: ${v}`} size="small" />)}</Stack>
            </Box>
            <Box flex={1}>
              <Typography variant="subtitle2" gutterBottom>{t('campaigns_by_user_status')}</Typography>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>{Object.entries(summary.by_user_status||{}).map(([k,v])=> <Chip key={k} label={`${k}: ${v}`} size="small" />)}</Stack>
            </Box>
          </Stack>
        </>
      )}
    </Box>
  );

  const AlertsView = () => (
    <Box>
      {alerts.length === 0 && <Typography variant="body2" color="text.secondary" sx={{ mt:1 }}>{t('campaigns_no_alerts')}</Typography>}
      {alerts.length > 0 && (
        <DataTable
          tableId="campaignAlerts"
          rows={alerts}
          columns={columnsAlerts.map(c => ({ key: c.field, label: c.headerName, sortable: ['campaign_id','merchant','status','user_status'].includes(c.field) }))}
          enableQuickFilter
          enablePagination
          initialPageSize={10}
          responsiveCards
          cardTitleKey="name"
          cardSubtitleKeys={[ 'merchant', 'status' ]}
        />
      )}
    </Box>
  );

  const TableView = () => (
    <Box>
      <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ mb:1 }}>
        <TextField size="small" label={t('campaigns_filter_status')} value={filters.status} onChange={e=>setFilters(f=>({...f,status:e.target.value}))} sx={{ width:140 }} />
        <TextField size="small" label={t('campaigns_filter_user_status')} value={filters.user_status} onChange={e=>setFilters(f=>({...f,user_status:e.target.value}))} sx={{ width:170 }} />
        <TextField size="small" label={t('campaigns_filter_merchant')} value={filters.merchant} onChange={e=>setFilters(f=>({...f,merchant:e.target.value}))} sx={{ width:170 }} />
        <Button size="small" variant="contained" onClick={loadCampaigns}>{t('campaigns_apply_filters')}</Button>
        <Button size="small" variant="text" onClick={()=>{ setFilters({status:'', user_status:'', merchant:''}); loadCampaigns(); }}>{t('campaigns_clear_filters')}</Button>
      </Stack>
      <DataTable
        tableId="campaigns"
  rows={campaignsData || []}
  columns={columnsTable.map(c => ({ key: c.field, label: c.headerName, sortable: ['campaign_id','merchant','status','user_registration_status'].includes(c.field) }))}
  loading={campaignsLoading}
        enableQuickFilter
        enablePagination
        initialPageSize={25}
        responsiveCards
        cardTitleKey="name"
        cardSubtitleKeys={[ 'merchant', 'status' ]}
      />
    </Box>
  );

  return (
    <Paper sx={{ p:2 }}>
      <Typography variant="h5" gutterBottom data-focus-initial>{t('campaigns_title')}</Typography>
      <Stack direction="row" spacing={1} sx={{ mb:2, flexWrap:'wrap' }}>
        <Button size="small" startIcon={<RefreshIcon />} onClick={()=>{ loadSummary(); loadAlerts(); loadCampaigns(); }}>{t('campaigns_refresh')}</Button>
        <TextField size="small" label={t('campaigns_backfill_limit')} value={backfillLimit} onChange={e=>setBackfillLimit(e.target.value.replace(/[^0-9]/g,''))} sx={{ width:120 }} />
        <Button size="small" variant="contained" startIcon={<PlayArrowIcon/>} disabled={backfilling} onClick={backfill}>{backfilling ? t('campaigns_backfill_running') : t('campaigns_backfill')}</Button>
      </Stack>
      <Tabs value={tab} onChange={(_,v)=>setTab(v)} sx={{ mb:2 }}>
        <Tab label={t('campaigns_tab_summary')} />
        <Tab label={t('campaigns_tab_alerts')} />
        <Tab label={t('campaigns_tab_table')} />
      </Tabs>
      {tab===0 && <SummaryView />}
      {tab===1 && <AlertsView />}
      {tab===2 && <TableView />}
      <React.Suspense fallback={null}>
        <CampaignExtrasDrawerLazy open={drawerOpen} onClose={()=>setDrawerOpen(false)} extras={extras} loading={extrasLoading} />
      </React.Suspense>
    </Paper>
  );
}
