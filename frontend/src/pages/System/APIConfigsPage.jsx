import React from 'react';
import { Paper, Typography, Stack, Button, Dialog, DialogTitle, DialogContent, DialogActions, TextField, IconButton, Tooltip, Switch, FormControlLabel, Box, Divider, Chip, Alert, Link as MuiLink } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import SaveIcon from '@mui/icons-material/Save';
import RefreshIcon from '@mui/icons-material/Refresh';
import BoltIcon from '@mui/icons-material/Bolt';
import { listApiConfigs, upsertApiConfig, setLinkcheckConfig, getLinkcheckFlags } from '../../api.js';
import { setIngestPolicy, setCheckUrlsPolicy, getIngestLockStatus, releaseIngestLock, runIngestRefresh } from '../../api/ingest.js';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import LockResetIcon from '@mui/icons-material/LockReset';
import LockClockIcon from '@mui/icons-material/LockClock';
import LinkIcon from '@mui/icons-material/Link';
import DataTable from '../../components/DataTable.jsx';
import { useNotify } from '../../components/NotificationProvider.jsx';
import { useT } from '../../i18n/I18nProvider.jsx';

export default function APIConfigsPage() {
  const { t } = useT();
  const notify = useNotify();
  const [rows, setRows] = React.useState([]);
  const [loading, setLoading] = React.useState(false);
  const [open, setOpen] = React.useState(false);
  const [editing, setEditing] = React.useState(null);
  const [form, setForm] = React.useState({ name:'', base_url:'', api_key:'', model:'' });
  const [onlyWithCommission, setOnlyWithCommission] = React.useState(false);
  const [checkUrls, setCheckUrls] = React.useState(false);
  const [linkcheckMod, setLinkcheckMod] = React.useState('');
  const [linkcheckLimit, setLinkcheckLimit] = React.useState('');
  const [flagsLoading, setFlagsLoading] = React.useState(false);
  // Scheduler state
  const [lock, setLock] = React.useState({ owner:null, ts:0, ttl:0, expired:true });
  const [schedLoading, setSchedLoading] = React.useState(false);
  const [adminKey, setAdminKey] = React.useState('');
  const [refreshing, setRefreshing] = React.useState(false);
  const [maxMinutes, setMaxMinutes] = React.useState('8');
  const [maxPages, setMaxPages] = React.useState('3');
  const [limitPerPage, setLimitPerPage] = React.useState('100');
  const [throttleMs, setThrottleMs] = React.useState('50');
  const [pageConcurrency, setPageConcurrency] = React.useState('4');
  const [includeTop, setIncludeTop] = React.useState(false);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const res = await listApiConfigs();
      setRows(res.data || []);
    } catch (err) {
      notify('error', err?.normalized?.message || err.message || 'Error');
    } finally { setLoading(false); }
  }, [notify]);

  const fetchFlags = React.useCallback(async () => {
    setFlagsLoading(true);
    try {
      const res = await getLinkcheckFlags();
      const f = res.data?.flags || {};
      setOnlyWithCommission(!!f.only_with_commission);
      setCheckUrls(!!f.check_urls);
      if (f.linkcheck_mod) setLinkcheckMod(String(f.linkcheck_mod));
      if (f.linkcheck_limit) setLinkcheckLimit(String(f.linkcheck_limit));
      notify('info', t('linkcheck_flags_loaded'));
    } catch {
      // silent
    } finally { setFlagsLoading(false); }
  }, [notify, t]);

  const loadLock = React.useCallback(async () => {
    try {
      const r = await getIngestLockStatus();
      if (r.data) setLock(r.data);
    } catch {
      // silent
    }
  }, []);

  React.useEffect(()=>{ load(); fetchFlags(); loadLock(); }, [load, fetchFlags, loadLock]);

  const openAdd = () => { setEditing(null); setForm({ name:'', base_url:'', api_key:'', model:'' }); setOpen(true); };
  const openEdit = (row) => { setEditing(row); setForm({ name:row.name, base_url:row.base_url, api_key:row.api_key, model:row.model||'' }); setOpen(true); };

  const submit = async () => {
    if (!form.name || !form.base_url || !form.api_key) {
      notify('warning', t('api_configs_form_required'));
      return;
    }
    try {
      await upsertApiConfig(form);
      notify('success', t('api_configs_saved'));
      setOpen(false);
      load();
    } catch (err) {
      notify('error', err?.normalized?.message || err.message || 'Error');
    }
  };

  const columns = React.useMemo(()=>[
    { field:'id', headerName:'ID', width:70 },
    { field:'name', headerName:t('api_configs_name'), width:140 },
    { field:'base_url', headerName:t('api_configs_base_url'), width:200 },
    { field:'api_key', headerName:t('api_configs_api_key'), width:200, renderCell: v => <code style={{ fontSize:12 }}>{String(v||'').slice(0,28)}{String(v||'').length>28?'…':''}</code> },
    { field:'model', headerName:t('api_configs_model'), width:220, renderCell: v => <code style={{ fontSize:12 }}>{v}</code> },
    { field:'actions', headerName:t('api_configs_actions'), width:90, renderCell: (_, row) => (
      <Tooltip title={t('api_configs_edit')}>
        <IconButton size="small" onClick={()=>openEdit(row)}><EditIcon fontSize="inherit" /></IconButton>
      </Tooltip>
    )},
  ], [t]);

  const applyPolicies = async () => {
    try {
      await setIngestPolicy(onlyWithCommission);
      await setCheckUrlsPolicy(checkUrls);
      await setLinkcheckConfig({
        linkcheck_mod: linkcheckMod ? parseInt(linkcheckMod,10) : undefined,
        linkcheck_limit: linkcheckLimit ? parseInt(linkcheckLimit,10) : undefined,
      });
      notify('success', t('api_configs_saved'));
      fetchFlags();
    } catch (err) {
      notify('error', err?.normalized?.message || err.message || 'Error');
    }
  };

  const runScheduler = async () => {
    setRefreshing(true);
    try {
      const payload = {
        max_minutes: parseInt(maxMinutes||'8',10),
        limit_per_page: parseInt(limitPerPage||'100',10),
        max_pages: parseInt(maxPages||'3',10),
        throttle_ms: parseInt(throttleMs||'50',10),
        page_concurrency: parseInt(pageConcurrency||'4',10),
        include_top_products: !!includeTop,
      };
  await runIngestRefresh(payload);
      notify('success', t('ingest_refresh_started'));
      // nếu backend trả 423 sẽ vào catch
      // tải lại trạng thái khoá
      loadLock();
      // gợi ý mở logs
    } catch (err) {
      const msg = err?.normalized?.message || err?.response?.data?.detail?.message || err.message || 'Error';
      notify('error', msg);
      // cố lấy chi tiết khoá từ backend nếu có
      try { await loadLock(); } catch {}
    } finally { setRefreshing(false); }
  };

  const forceRelease = async (force=false) => {
    setSchedLoading(true);
    try {
      await releaseIngestLock(null, force, adminKey || undefined);
      notify('success', t('ingest_lock_released'));
      loadLock();
    } catch (err) {
      notify('error', err?.normalized?.message || 'Error');
    } finally { setSchedLoading(false); }
  };

  return (
    <Paper sx={{ p:2 }}>
      <Typography variant="h5" gutterBottom data-focus-initial>{t('api_configs_title')}</Typography>
      <Typography variant="body2" sx={{ mb:2 }}>{t('api_configs_subtitle')}</Typography>
      <Stack direction="row" spacing={1} sx={{ mb:2, flexWrap:'wrap' }}>
        <Button startIcon={<AddIcon/>} variant="contained" size="small" onClick={openAdd}>{t('api_configs_add')}</Button>
        <Button startIcon={<RefreshIcon/>} variant="outlined" size="small" onClick={load} disabled={loading}>{t('action_refresh')}</Button>
      </Stack>
      <DataTable tableId="apiConfigs" rows={rows} columns={columns} loading={loading} enableQuickFilter enablePagination initialPageSize={10} />
      {rows.length === 0 && !loading && (
        <Typography variant="body2" color="text.secondary" sx={{ mt:1 }}>{t('api_configs_empty')}</Typography>
      )}
      <Divider sx={{ my:3 }} />
  <Typography variant="h6" gutterBottom>Settings</Typography>
      <Stack direction={{ xs:'column', md:'row' }} spacing={4} alignItems="flex-start">
        <Box sx={{ minWidth:260 }}>
          <FormControlLabel control={<Switch checked={onlyWithCommission} onChange={e=>setOnlyWithCommission(e.target.checked)} />} label={t('settings_ingest_policy')} />
          <FormControlLabel control={<Switch checked={checkUrls} onChange={e=>setCheckUrls(e.target.checked)} />} label={t('settings_check_urls')} />
        </Box>
        <Box sx={{ display:'flex', flexDirection:'column', gap:1, minWidth:240 }}>
          <TextField size="small" label={t('settings_linkcheck_mod')} value={linkcheckMod} onChange={e=>setLinkcheckMod(e.target.value.replace(/[^0-9]/g,''))} />
          <TextField size="small" label={t('settings_linkcheck_limit')} value={linkcheckLimit} onChange={e=>setLinkcheckLimit(e.target.value.replace(/[^0-9]/g,''))} />
          <Typography variant="caption" color="text.secondary">{t('settings_rotate_hint')}</Typography>
          <Stack direction="row" spacing={1}>
            <Button size="small" variant="contained" startIcon={<BoltIcon/>} onClick={applyPolicies} disabled={flagsLoading}>{t('settings_apply')}</Button>
            <Button size="small" variant="text" onClick={fetchFlags} disabled={flagsLoading}>{t('action_refresh')}</Button>
          </Stack>
        </Box>
      </Stack>

      <Divider sx={{ my:3 }} />
      <Typography variant="h6" gutterBottom>{t('ingest_refresh_title')}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb:1 }}>{t('ingest_refresh_desc')}</Typography>
      <Paper variant="outlined" sx={{ p:2, mb:2, bgcolor: lock?.expired? 'transparent':'#fff8e1' }}>
        <Stack direction={{ xs:'column', md:'row' }} spacing={2} alignItems="center">
          <Chip icon={<LockClockIcon />} label={lock?.expired ? t('ingest_lock_free') : t('ingest_lock_busy')} color={lock?.expired ? 'success' : 'warning'} />
          {!lock?.expired && (
            <Typography variant="body2">{t('ingest_lock_owner', { owner: lock?.owner || 'unknown' })} • TTL {lock?.ttl}s</Typography>
          )}
          <Box sx={{ flexGrow:1 }} />
          <Button size="small" variant="text" startIcon={<RefreshIcon/>} onClick={loadLock} disabled={schedLoading}>{t('action_refresh')}</Button>
        </Stack>
        <Stack direction={{ xs:'column', md:'row' }} spacing={2} sx={{ mt:2 }}>
          <TextField size="small" label={t('ingest_field_max_minutes')} value={maxMinutes} onChange={e=>setMaxMinutes(e.target.value.replace(/[^0-9]/g,''))} sx={{ width:140 }} />
          <TextField size="small" label={t('ingest_field_limit_per_page')} value={limitPerPage} onChange={e=>setLimitPerPage(e.target.value.replace(/[^0-9]/g,''))} sx={{ width:180 }} />
          <TextField size="small" label={t('ingest_field_max_pages')} value={maxPages} onChange={e=>setMaxPages(e.target.value.replace(/[^0-9]/g,''))} sx={{ width:160 }} />
          <TextField size="small" label={t('ingest_field_throttle_ms')} value={throttleMs} onChange={e=>setThrottleMs(e.target.value.replace(/[^0-9]/g,''))} sx={{ width:150 }} />
          <TextField size="small" label={t('ingest_field_page_concurrency')} value={pageConcurrency} onChange={e=>setPageConcurrency(e.target.value.replace(/[^0-9]/g,''))} sx={{ width:190 }} />
          <FormControlLabel control={<Switch checked={includeTop} onChange={e=>setIncludeTop(e.target.checked)} />} label={t('ingest_field_include_top_products')} />
        </Stack>
        <Stack direction={{ xs:'column', sm:'row' }} spacing={1} sx={{ mt:2 }}>
          <Button size="small" variant="contained" startIcon={<PlayArrowIcon/>} onClick={runScheduler} disabled={refreshing}>{t('ingest_refresh_run')}</Button>
          <TextField size="small" label="X-Admin-Key" value={adminKey} onChange={e=>setAdminKey(e.target.value)} sx={{ width:220 }} placeholder="tuỳ chọn khi Force" />
          <Button size="small" variant="outlined" color="warning" startIcon={<LockResetIcon/>} onClick={()=>forceRelease(false)} disabled={schedLoading}>{t('ingest_release')}</Button>
          <Button size="small" variant="outlined" color="error" startIcon={<LockResetIcon/>} onClick={()=>forceRelease(true)} disabled={schedLoading}>{t('ingest_force_release')}</Button>
          <Box sx={{ flexGrow:1 }} />
          <Tooltip title={t('ingest_open_logs_hint')}>
            <Button size="small" startIcon={<LinkIcon/>} component={MuiLink} href="/system/logs?f=ingest_refresh.jsonl">{t('ingest_open_logs')}</Button>
          </Tooltip>
        </Stack>
        <Alert severity="info" sx={{ mt:2 }}>{t('ingest_refresh_hint')}</Alert>
      </Paper>

      <Dialog open={open} onClose={()=>setOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>{editing ? t('api_configs_edit') : t('api_configs_add')}</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2} sx={{ mt:0.5 }}>
            <TextField label={t('api_configs_name')} value={form.name} onChange={e=>setForm(f=>({...f, name:e.target.value}))} size="small" required />
            <TextField label={t('api_configs_base_url')} value={form.base_url} onChange={e=>setForm(f=>({...f, base_url:e.target.value}))} size="small" required />
            <TextField label={t('api_configs_api_key')} value={form.api_key} onChange={e=>setForm(f=>({...f, api_key:e.target.value}))} size="small" required />
            <TextField label={t('api_configs_model')} value={form.model} onChange={e=>setForm(f=>({...f, model:e.target.value}))} size="small" placeholder="only_with_commission=true;check_urls=true" />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={()=>setOpen(false)}>{t('dlg_cancel')}</Button>
          <Button onClick={submit} startIcon={<SaveIcon/>} variant="contained">{t('dlg_save')}</Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
}
