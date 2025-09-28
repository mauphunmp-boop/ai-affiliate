import { Typography, IconButton, Box, Button, Dialog, DialogTitle, DialogContent, DialogActions, TextField, Switch, FormControlLabel, Tooltip, Chip, Stack, Alert, Select, MenuItem, FormControl, InputLabel } from '@mui/material';
import React, { useEffect, useState } from 'react';
import { useNotify } from '../../components/NotificationProvider.jsx';
import { parseJsonWithLineInfo, buildJsonErrorSnippet } from '../../utils/jsonPosition.js';
import EmptyState from '../../components/EmptyState.jsx';
import GlossaryTerm from '../../components/GlossaryTerm.jsx';
import DataTable from '../../components/DataTable.jsx';
import { toCSV, downloadCSV } from '../../utils/csvExport.js';
import ConfirmDialog from '../../components/ConfirmDialog.jsx';
import RefreshIcon from '@mui/icons-material/Refresh';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import TemplateWizard from '../../components/TemplateWizard.jsx';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import BoltIcon from '@mui/icons-material/Bolt';
import { listAffiliateTemplates, upsertAffiliateTemplate, autoGenerateTemplates, deleteAffiliateTemplate, updateAffiliateTemplate } from '../../api/affiliate';
import { useNavigate } from 'react-router-dom';
import { useT } from '../../i18n/I18nProvider.jsx';

export default function TemplatesPage() {
  if (import.meta.env.DEV) {
    // Render debug (avoid spamming in test env)
    // eslint-disable-next-line no-console
    console.debug('[TemplatesPage] render at', performance.now().toFixed(1));
  }
  React.useEffect(()=>{ if(import.meta.env.DEV){ try { performance.mark?.('TemplatesPage:paint'); } catch {} } }, []);
  const { t } = useT();
  const tt = React.useCallback((k, fb) => { const v = t(k); return v === k ? fb : v; }, [t]);
  const notify = useNotify();
  const navigate = useNavigate();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [autoMsg, setAutoMsg] = useState(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ network:'accesstrade', platform:'', template:'', default_params:'', enabled:true });
  const [jsonError, setJsonError] = useState(null);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [selected, setSelected] = useState([]);
  const [tableState, setTableState] = useState(null);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [bulkMode, setBulkMode] = useState(null); // 'delete' | 'enable' | 'disable'
  const [enabledFilter, setEnabledFilter] = useState('all'); // all | on | off
  const [announce, setAnnounce] = useState('');

  // Test hook: cho phép test thay đổi filter trực tiếp không cần tương tác UI phức tạp (tránh loop MUI trong jsdom)
  if (import.meta.env?.TEST && typeof window !== 'undefined') {
    // Không overwrite nếu đã tồn tại để tránh gây re-render không cần thiết
    if (!window.__TEST__setTemplatesEnabledFilter) {
      window.__TEST__setTemplatesEnabledFilter = (v) => setEnabledFilter(v);
    }
  }

  const load = async () => {
    setLoading(true); setError('');
    try { const res = await listAffiliateTemplates(); setRows(res.data || []); }
  catch(err){ setError(err?.response?.data?.detail || err.message); }
    finally { setLoading(false); }
  };
  useEffect(()=>{ load(); }, []);

  const openNew = () => { setEditing(null); setForm({ network:'accesstrade', platform:'', template:'', default_params:'', enabled:true }); setJsonError(null); setOpen(true); };
  const openEdit = (row) => {
    setEditing(row);
    setForm({
      network: row.network || 'accesstrade',
      platform: row.platform || '',
      template: row.template || '',
      default_params: row.default_params ? JSON.stringify(row.default_params, null, 2) : '',
      enabled: row.enabled !== false
    });
    setOpen(true);
    setJsonError(null);
  };
  const close = () => { setOpen(false); };

  const submit = async () => {
    try {
      let dp = undefined;
      if (form.default_params.trim()) {
        const parsed = parseJsonWithLineInfo(form.default_params);
        if (parsed.error) { notify('error', `default_params JSON lỗi (dòng ${parsed.error.line||'?'} cột ${parsed.error.column||'?'} )`); return; }
        dp = parsed.value;
      }
      const payload = {
        network: form.network.trim(),
        platform: form.platform.trim() || null,
        template: form.template.trim(),
        default_params: dp,
        enabled: form.enabled,
      };
      if (!payload.template) { notify('error', 'Template không được trống'); return; }
      if (editing) {
        await updateAffiliateTemplate(editing.id, payload);
        notify('success', 'Đã lưu template');
      } else {
        await upsertAffiliateTemplate(payload);
        notify('success', 'Đã tạo template');
      }
      await load();
      setOpen(false);
    } catch (err) {
      const msg = err.normalized?.message || err?.response?.data?.detail || err.message || 'Lỗi';
      notify('error', msg);
    }
  };

  const doAuto = async () => {
    setAutoMsg(null);
    try {
      const res = await autoGenerateTemplates('accesstrade');
      setAutoMsg(res.data);
      notify('success', `Auto-generate: tạo mới ${res.data.created?.length || 0}, bỏ qua ${res.data.skipped?.length || 0}`);
      await load();
    } catch (err) {
      const msg = err.normalized?.message || err?.response?.data?.detail || err.message;
      setAutoMsg({ error: msg });
      notify('error', msg);
    }
  };

  const [confirm, setConfirm] = useState({ open:false, row:null });
  const doDelete = async () => {
    const row = confirm.row; if (!row) return;
    try {
      await deleteAffiliateTemplate(row.id);
      setRows(r => r.filter(x => x.id !== row.id));
      notify('success', 'Đã xoá template');
    } catch {
      notify('error', 'Xoá thất bại');
    } finally { setConfirm({ open:false, row:null }); }
  };

  const columns = [
    { key: 'id', label: t('templates_id'), sx:{ width:70 } },
    { key: 'network', label: t('templates_network'), sx:{ width:110 } },
  { key: 'platform', label: t('templates_platform'), render: r => r.platform || <em>{t('templates_platform_default')}</em>, sx:{ width:120 } },
  { key: 'enabled', label: t('templates_enabled'), render: r => r.enabled ? <Chip size="small" label={t('status_on')} color="success"/> : <Chip size="small" label={t('status_off')}/>, sx:{ width:90 } },
    { key: 'template', label: t('templates_template'), render: r => <Box sx={{ maxWidth:260, whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }} title={r.template}>{r.template}</Box> },
    { key: 'default_params', label: t('templates_default'), render: r => <Box sx={{ maxWidth:160, whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>{r.default_params ? JSON.stringify(r.default_params) : '—'}</Box> },
    { key: 'actions', label: t('templates_actions'), sx:{ width:110 }, render: r => (
      <>
        <Tooltip title={t('tooltip_edit')}><IconButton size="small" onClick={()=>openEdit(r)} aria-label={t('tooltip_edit')}><EditIcon fontSize="inherit"/></IconButton></Tooltip>
        <Tooltip title={t('tooltip_delete')}><IconButton size="small" color="error" aria-label={t('tooltip_delete')} onClick={()=>setConfirm({ open:true, row:r })}><DeleteIcon fontSize="inherit"/></IconButton></Tooltip>
      </>
    ) }
  ];

  const doExport = () => {
    const current = tableState?.processed || rows;
    const exportRows = selected.length ? current.filter(r => selected.includes(r.id)) : current;
  if (!exportRows.length) { notify('info', t('export_none')); return; }
    const csv = toCSV(exportRows, columns.filter(c => c.key !== 'actions'));
    downloadCSV('templates_export.csv', csv);
  notify('success', t('export_success_rows', { n: exportRows.length }));
  };
  const doBulkDelete = async () => {
    if (!selected.length) return;
  if (!window.confirm(t('bulk_delete_confirm', { n: selected.length }))) return;
    setBulkBusy(true); setBulkMode('delete');
    let ok=0, fail=0;
    for (const id of selected) {
      try { await deleteAffiliateTemplate(id); ok++; } catch { fail++; }
    }
    setRows(r => r.filter(x => !selected.includes(x.id)));
    setSelected([]);
    setBulkBusy(false); setBulkMode(null);
  const msg = fail ? t('bulk_delete_result_fail', { ok, fail }) : t('bulk_delete_result_ok', { ok });
    notify(fail? 'warning':'success', msg);
    setAnnounce(msg);
  };

  const doBulkSetEnabled = async (value) => {
    if (!selected.length) return;
    setBulkBusy(true); setBulkMode(value ? 'enable' : 'disable');
    let ok=0, fail=0;
    for (const id of selected) {
      const row = rows.find(r => r.id === id);
      if (!row) { fail++; continue; }
      try {
        await updateAffiliateTemplate(id, {
          network: row.network,
          platform: row.platform,
          template: row.template,
          default_params: row.default_params,
          enabled: value
        });
        ok++;
      } catch { fail++; }
    }
    // optimistic update
    setRows(r => r.map(x => selected.includes(x.id) ? { ...x, enabled: value } : x));
    setSelected([]);
    setBulkBusy(false); setBulkMode(null);
  const msg = value ? (fail ? t('bulk_enable_result_fail', { ok, fail }) : t('bulk_enable_result_ok', { ok })) : (fail ? t('bulk_disable_result_fail', { ok, fail }) : t('bulk_disable_result_ok', { ok }));
    notify(fail? 'warning':'success', msg);
    setAnnounce(msg);
  };
  const filtered = React.useMemo(() => rows.filter(r => enabledFilter === 'all' ? true : enabledFilter === 'on' ? r.enabled : !r.enabled), [rows, enabledFilter]);
  // dataRows memo để tránh tạo mảng mới mỗi render khi không đổi -> giảm kích hoạt onState ở DataTable
  const dataRows = React.useMemo(()=> filtered.map(r => ({ ...r, id: r.id })), [filtered]);

  const invertSelection = React.useCallback(() => {
    setSelected(r => rows.filter(row => !r.includes(row.id)).map(row => row.id));
  }, [rows]);
  // Keyboard shortcuts: Alt+A (select all filtered), Alt+I (invert), Alt+C (clear selection)
  React.useEffect(()=>{
    const handler = (e) => {
      if (!e.altKey) return;
      if (e.code === 'KeyA') { e.preventDefault(); setSelected(filtered.map(r=>r.id)); setAnnounce(t('announce_selected_rows', { n: filtered.length })); }
      else if (e.code === 'KeyI') { e.preventDefault(); invertSelection(); setAnnounce(t('announce_inverted')); }
      else if (e.code === 'KeyC') { e.preventDefault(); setSelected([]); setAnnounce(t('announce_cleared')); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [filtered, invertSelection, t]);

  // Test-only: expose deterministic shortcut invoker luôn cập nhật theo state mới nhất (tránh stale closure)
  React.useEffect(() => {
    if (!(import.meta.env?.TEST && typeof window !== 'undefined')) return;
    window.__TEST__templatesShortcut = (code) => {
      if (code === 'KeyA') { setSelected(filtered.map(r=>r.id)); setAnnounce('selected_all'); }
      else if (code === 'KeyC') { setSelected([]); setAnnounce('cleared'); }
      else if (code === 'KeyI') { setSelected(r => rows.filter(row => !r.includes(row.id)).map(row => row.id)); setAnnounce('inverted'); }
    };
    return () => { try { delete window.__TEST__templatesShortcut; } catch { /* ignore */ } };
  }, [filtered, rows]);

  return (
    <React.Fragment>
    { /* Test hook đã chuyển sang useEffect để cập nhật mỗi lần state đổi */ }
    <Box>
  <Typography variant="h5" gutterBottom>Affiliate <GlossaryTerm term="template">{t('nav_templates')}</GlossaryTerm></Typography>
      <Stack direction="row" spacing={1} sx={{ mb:2, flexWrap:'wrap', alignItems:'center' }}>
  <Button startIcon={<AddIcon />} variant="contained" onClick={openNew}>{t('action_add')}</Button>
  <Button startIcon={<AutoAwesomeIcon />} onClick={()=>setWizardOpen(true)}>{t('action_wizard')}</Button>
  <Button startIcon={<BoltIcon />} onClick={doAuto} disabled={loading}>{t('action_auto_generate')}</Button>
  <Button startIcon={<RefreshIcon />} onClick={load} disabled={loading}>{t('action_refresh')}</Button>
        <FormControl size="small" sx={{ minWidth:130 }}>
          <InputLabel id="enabled-filter-label">{tt('filter_enabled','Enabled')}</InputLabel>
          <Select labelId="enabled-filter-label" label="Enabled" value={enabledFilter} onChange={e=>setEnabledFilter(e.target.value)}
            inputProps={{ 'aria-label':'Lọc theo trạng thái bật/tắt' }}>
            <MenuItem value="all">{tt('filter_all','ALL')}</MenuItem>
            <MenuItem value="on">{tt('filter_on','ON')}</MenuItem>
            <MenuItem value="off">{tt('filter_off','OFF')}</MenuItem>
          </Select>
        </FormControl>
        <Tooltip title={t('tooltip_select_all_filtered')}><span>
          <Button size="small" variant="text" disabled={filtered.length===0 || selected.length===filtered.length} onClick={()=>{ setSelected(filtered.map(r=>r.id)); setAnnounce(t('announce_selected_rows', { n: filtered.length })); }}>{t('action_select_all_filtered')}</Button>
        </span></Tooltip>
        <Box sx={{ flexGrow:1 }} />
        {selected.length > 0 ? (
          <Stack direction="row" spacing={1} alignItems="center" {...(import.meta.env?.TEST ? { 'data-testid':'templates-bulk-actions' } : {})}>
            <Button size="small" color="error" disabled={bulkBusy} onClick={doBulkDelete}>{bulkMode==='delete' ? '...' : t('bulk_delete_label', { n: selected.length })}</Button>
            <Button size="small" disabled={bulkBusy} onClick={()=>doBulkSetEnabled(true)}>{bulkMode==='enable' ? '...' : t('bulk_enable_label')}</Button>
            <Button size="small" disabled={bulkBusy} onClick={()=>doBulkSetEnabled(false)}>{bulkMode==='disable' ? '...' : t('bulk_disable_label')}</Button>
            <Button size="small" disabled={bulkBusy} onClick={invertSelection}>{t('action_invert')}</Button>
            <Button size="small" disabled={bulkBusy} onClick={()=>setSelected([])}>{t('action_clear_selection')}</Button>
          </Stack>
        ) : (
          <Stack direction="row" spacing={1}>
            <Button size="small" variant="outlined" onClick={doExport}>{t('action_export_csv')}</Button>
          </Stack>
        )}
      </Stack>
      {error && <Alert severity="error" sx={{ mb:2 }}>{error}</Alert>}
      {autoMsg && (
        <Alert severity={autoMsg.error ? 'error':'info'} sx={{ mb:2 }}>
      {autoMsg.error ? autoMsg.error : t('auto_generate_result', { created: autoMsg.created?.length || 0, skipped: autoMsg.skipped?.length || 0 })}
        </Alert>
      )}
      <DataTable
        tableId="templates"
        rows={dataRows}
        columns={React.useMemo(()=> columns.map(c => ({ ...c, sortable: ['id','network','platform','enabled'].includes(c.key) })), [columns])}
        loading={loading}
  empty={t('templates_empty_title')}
  emptyComponent={<EmptyState title={t('templates_empty_title')} description={t('templates_empty_desc')} actionLabel={t('action_add')} onAction={()=> openNew()} />}
        maxHeight={560}
        enableQuickFilter
        enableColumnHide
        enablePagination
        initialPageSize={25}
        onRefresh={load}
        responsiveHiddenBreakpoints={{ default_params:'md', platform:'sm' }}
        enableSelection
        onSelectionChange={setSelected}
        onState={setTableState}
        // In case DataTable internally uses anchor tags for navigation, force client navigation
        onRowActionNavigate={(to)=>{ if(typeof to==='string'){ navigate(to); } }}
      />
      <Dialog open={open} onClose={close} maxWidth="sm" fullWidth>
  <DialogTitle>{editing ? t('edit_template_title') : t('create_template_title')}</DialogTitle>
        <DialogContent sx={{ display:'flex', flexDirection:'column', gap:2, pt:1 }}>
          <TextField label={t('field_network')} value={form.network} onChange={e=>setForm(f=>({...f, network:e.target.value}))} required />
          <TextField label={t('field_platform')} value={form.platform} onChange={e=>setForm(f=>({...f, platform:e.target.value}))} placeholder={t('wizard_platform_ph')} helperText={t('field_platform_hint')} />
          <TextField label="Template" value={form.template} onChange={e=>setForm(f=>({...f, template:e.target.value}))} required multiline minRows={2} />
          <TextField
            label={t('field_default_params')}
            value={form.default_params}
            onChange={e=>{
              const val = e.target.value; setForm(f=>({...f, default_params:val}));
              if (!val.trim()) { setJsonError(null); return; }
              const parsed = parseJsonWithLineInfo(val);
              if (parsed.error) setJsonError(parsed.error); else setJsonError(null);
            }}
            placeholder='{ "utm_source": "chatbot" }'
            multiline
            minRows={3}
            error={!!jsonError}
            helperText={jsonError ? t('json_error_line_col_pos', { line: jsonError.line||'?', column: jsonError.column||'?', pos: jsonError.position }) : t('field_default_params_hint')}
            FormHelperTextProps={ jsonError ? { sx:{ whiteSpace:'pre-wrap', color:'error.main' } } : undefined }
          />
          {jsonError && (
            <Box sx={{ fontFamily:'monospace', fontSize:12, p:1, border:'1px solid', borderColor:'error.main', borderRadius:1, bgcolor:'error.main', color:'#fff', whiteSpace:'pre', overflow:'auto' }}>
              {buildJsonErrorSnippet(form.default_params, jsonError.position)}
            </Box>
          )}
          <FormControlLabel control={<Switch checked={form.enabled} onChange={e=>setForm(f=>({...f, enabled:e.target.checked}))} />} label={t('templates_enabled')} />
          <Typography variant="caption" color="text.secondary">{t('field_template_placeholders')}</Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={close}>{t('dlg_cancel')}</Button>
          <Button variant="contained" onClick={submit}>{editing ? t('dlg_save') : t('dlg_create')}</Button>
        </DialogActions>
      </Dialog>
      <ConfirmDialog
        open={confirm.open}
        title={t('delete_template_title')}
        message={confirm.row ? t('delete_template_confirm', { id: confirm.row.id }) : ''}
        onClose={() => setConfirm({ open:false, row:null })}
        onConfirm={doDelete}
        danger
        confirmText={t('action_delete')}
      />
      <TemplateWizard open={wizardOpen} onClose={()=>setWizardOpen(false)} onCreated={load} />
      {/* Live region thông báo kết quả bulk actions */}
      <Box role="status" aria-live="polite" sx={{ position:'absolute', width:1, height:1, p:0, m:-1, overflow:'hidden', clip:'rect(0 0 0 0)', whiteSpace:'nowrap', border:0 }}>{announce}</Box>
    </Box>
    </React.Fragment>
  );
}
