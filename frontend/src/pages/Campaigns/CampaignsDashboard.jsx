import React from 'react';
import { Paper, Typography, Stack, Button, Tabs, Tab, Box, Chip, TextField, IconButton, Tooltip, Drawer, Divider, CircularProgress, List, ListItem, ListItemText } from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import DataTable from '../../components/DataTable.jsx';
import { useNotify } from '../../components/NotificationProvider.jsx';
import { useT } from '../../i18n/I18nProvider.jsx';
import api from '../../api.js';

function useAsync(fn, deps) {
  const [state, set] = React.useState({ loading:false, data:null, error:null });
  const run = React.useCallback(async (...a) => {
    set(s=>({ ...s, loading:true, error:null }));
    try { const data = await fn(...a); set({ loading:false, data, error:null }); return data; } catch (e) { set({ loading:false, data:null, error:e }); throw e; }
  }, deps);
  return [state, run];
}

export default function CampaignsDashboard() {
  const { t } = useT();
  const notify = useNotify();
  const [tab, setTab] = React.useState(0);
  const [summary, setSummary] = React.useState(null);
  const [alerts, setAlerts] = React.useState([]);
  const [campaignRows, setCampaignRows] = React.useState([]);
  const [loadingCampaigns, setLoadingCampaigns] = React.useState(false);
  const [filters, setFilters] = React.useState({ status:'', user_status:'', merchant:'' });
  const [backfillLimit, setBackfillLimit] = React.useState('200');
  const [backfilling, setBackfilling] = React.useState(false);
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [extrasLoading, setExtrasLoading] = React.useState(false);
  const [extras, setExtras] = React.useState(null);

  const openExtras = async (cid) => {
    setDrawerOpen(true); setExtras(null); setExtrasLoading(true);
    try {
      const r = await api.get(`/campaigns/${encodeURIComponent(cid)}/extras`);
      setExtras(r.data);
    } catch (e) { setExtras({ error: e?.normalized?.message || e.message }); }
    finally { setExtrasLoading(false); }
  };

  const loadSummary = async () => {
    try { const r = await api.get('/campaigns/summary'); setSummary(r.data); } catch(e) { notify('error', e?.normalized?.message||e.message); }
  };
  const loadAlerts = async () => {
    try { const r = await api.get('/alerts/campaigns-registration'); setAlerts(r.data||[]); } catch(e) { /* ignore */ }
  };
  const loadCampaigns = async () => {
    setLoadingCampaigns(true);
    try {
      const params = new URLSearchParams();
      if (filters.status) params.append('status', filters.status);
      if (filters.user_status) params.append('user_status', filters.user_status);
      if (filters.merchant) params.append('merchant', filters.merchant);
      const r = await api.get('/campaigns' + (params.toString()?`?${params.toString()}`:''));
      setCampaignRows(r.data||[]);
    } catch(e) { notify('error', e?.normalized?.message||e.message); } finally { setLoadingCampaigns(false); }
  };

  React.useEffect(()=>{ loadSummary(); loadAlerts(); loadCampaigns(); }, []);

  const backfill = async () => {
    setBackfilling(true);
    try { const r = await api.post(`/campaigns/backfill-user-status?limit=${encodeURIComponent(backfillLimit||'200')}`); notify('success', t('campaigns_backfill_done', { fixed: r.data?.fixed||0 })); loadSummary(); loadCampaigns(); }
    catch(e){ notify('error', e?.normalized?.message||e.message); } finally { setBackfilling(false); }
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
          <IconButton size="small" onClick={()=>openExtras(row.campaign_id)}><PlayArrowIcon fontSize="inherit" /></IconButton>
        </Tooltip>
      </Stack>
    )}
  ], [t]);

  const SummaryView = () => (
    <Box>
      {!summary && <Typography variant="body2">{t('campaigns_loading')}</Typography>}
      {summary && (
        <Stack direction="row" spacing={2} flexWrap="wrap" sx={{ mb:2 }}>
          <Chip label={`${t('campaigns_total')}: ${summary.total}`} color="primary" />
          <Chip label={`${t('campaigns_running_approved')}: ${summary.running_approved_count}`} color="success" />
          <Chip label={`${t('campaigns_approved_merchants')}: ${summary.approved_merchants?.length||0}`} />
        </Stack>
      )}
      {summary && (
        <Stack direction={{ xs:'column', md:'row' }} spacing={4} alignItems="flex-start">
          <Box>
            <Typography variant="subtitle2" gutterBottom>{t('campaigns_by_status')}</Typography>
            <Stack spacing={1}>{Object.entries(summary.by_status||{}).map(([k,v])=> <Chip key={k} label={`${k}: ${v}`} size="small" />)}</Stack>
          </Box>
          <Box>
            <Typography variant="subtitle2" gutterBottom>{t('campaigns_by_user_status')}</Typography>
            <Stack spacing={1}>{Object.entries(summary.by_user_status||{}).map(([k,v])=> <Chip key={k} label={`${k}: ${v}`} size="small" />)}</Stack>
          </Box>
        </Stack>
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
        rows={campaignRows}
        columns={columnsTable.map(c => ({ key: c.field, label: c.headerName, sortable: ['campaign_id','merchant','status','user_registration_status'].includes(c.field) }))}
        loading={loadingCampaigns}
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
      <Drawer anchor="right" open={drawerOpen} onClose={()=>setDrawerOpen(false)} PaperProps={{ sx:{ width:{ xs:'100%', sm:500 } } }}>
        <Box sx={{ p:2, height:'100%', display:'flex', flexDirection:'column' }}>
          <Typography variant="h6" gutterBottom>{t('campaigns_extras_title')}</Typography>
          <Divider sx={{ mb:2 }} />
          {extrasLoading && <Stack alignItems="center" justifyContent="center" sx={{ flex:1 }}><CircularProgress size={32} /></Stack>}
          {!extrasLoading && !extras && <Typography variant="body2" color="text.secondary">{t('campaigns_extras_loading')}</Typography>}
          {!extrasLoading && extras && extras.error && <Typography color="error" variant="body2">{extras.error}</Typography>}
          {!extrasLoading && extras && !extras.error && (
            <Box sx={{ overflowY:'auto', flex:1 }}>
              <Stack spacing={1} sx={{ mb:2 }}>
                <Chip label={`ID: ${extras.campaign_id}`} size="small" />
                {extras.merchant && <Chip label={t('campaigns_extras_merchant') + ': ' + extras.merchant} size="small" />}
                {extras.detail?.status && <Chip label={t('campaigns_extras_status') + ': ' + extras.detail.status} size="small" />}
                {extras.detail?.approval && <Chip label={t('campaigns_extras_approval') + ': ' + extras.detail.approval} size="small" />}
                {extras.detail?.user_registration_status && <Chip label={t('campaigns_extras_user_status') + ': ' + extras.detail.user_registration_status} size="small" />}
                {extras.detail?.cookie_duration && <Chip label={t('campaigns_extras_cookie') + ': ' + extras.detail.cookie_duration} size="small" />}
              </Stack>
              <Typography variant="subtitle2" gutterBottom>{t('campaigns_extras_promotions')} ({extras.counts?.promotions})</Typography>
              {(!extras.promotions || extras.promotions.length===0) && <Typography variant="body2" color="text.secondary" sx={{ mb:1 }}>{t('campaigns_extras_empty')}</Typography>}
              <List dense sx={{ mb:2 }}>
                {Array.isArray(extras.promotions) && extras.promotions.map((p,i)=>(
                  <ListItem key={i} disableGutters>
                    <ListItemText
                      primary={p.name || p.coupon || ('#'+(i+1))}
                      secondary={(p.content||'') + (p.coupon?` | ${p.coupon}`:'')}
                    />
                  </ListItem>
                ))}
              </List>
              <Typography variant="subtitle2" gutterBottom>{t('campaigns_extras_policies')} ({extras.counts?.commission_policies})</Typography>
              {(!extras.commission_policies || extras.commission_policies.length===0) && <Typography variant="body2" color="text.secondary" sx={{ mb:1 }}>{t('campaigns_extras_empty')}</Typography>}
              <List dense>
                {Array.isArray(extras.commission_policies) && extras.commission_policies.map((c,i)=>(
                  <ListItem key={i} disableGutters>
                    <ListItemText
                      primary={`${c.reward_type || ''} ${c.sales_ratio!=null? ('- ' + c.sales_ratio + '%'):''}`}
                      secondary={c.target_month || ''}
                    />
                  </ListItem>
                ))}
              </List>
              <Typography variant="subtitle2" sx={{ mt:2 }}>Raw:</Typography>
              <pre style={{ fontSize:11, maxHeight:160, overflow:'auto', background:'#111', color:'#0f0', padding:8 }}>{JSON.stringify(extras, null, 2)}</pre>
            </Box>
          )}
          <Box sx={{ pt:1 }}>
            <Button fullWidth variant="outlined" onClick={()=>setDrawerOpen(false)}>Đóng</Button>
          </Box>
        </Box>
      </Drawer>
    </Paper>
  );
}
