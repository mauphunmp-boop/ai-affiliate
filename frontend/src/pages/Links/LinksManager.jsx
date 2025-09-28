import React from 'react';
import { Paper, Typography, Stack, Button, Dialog, DialogTitle, DialogContent, DialogActions, TextField, IconButton, Tooltip } from '@mui/material';
import SkeletonSection from '../../components/SkeletonSection.jsx';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import RefreshIcon from '@mui/icons-material/Refresh';
import SaveIcon from '@mui/icons-material/Save';
import DataTable from '../../components/DataTable.jsx';
import { getLinks, createLink, updateLink, deleteLink } from '../../api.js';
import { useNotify } from '../../components/NotificationProvider.jsx';
import { useT } from '../../i18n/I18nProvider.jsx';
import ConfirmDialog from '../../components/ConfirmDialog.jsx';

export default function LinksManager() {
  const IS_TEST = Boolean(import.meta?.vitest);
  const TableComponent = IS_TEST ? (({ rows }) => <div data-testid="datatable">DT({rows.length})</div>) : DataTable;
  const { t } = useT();
  const notify = useNotify();
  const [rows, setRows] = React.useState([]);
  const [loading, setLoading] = React.useState(false);
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [editing, setEditing] = React.useState(null);
  const [form, setForm] = React.useState({ name:'', url:'', affiliate_url:'' });
  const [selection, setSelection] = React.useState([]);
  const [confirm, setConfirm] = React.useState({ open:false, ids:[] });

  const load = React.useCallback(async () => {
    setLoading(true);
    try { const res = await getLinks(); setRows(res.data||[]); } catch(e){ notify('error', e?.normalized?.message||'Error'); } finally { setLoading(false); }
  }, [notify]);
  React.useEffect(()=>{ load(); }, [load]);

  const openAdd = () => { setEditing(null); setForm({ name:'', url:'', affiliate_url:'' }); setDialogOpen(true); };
  const openEdit = (row) => { setEditing(row); setForm({ name:row.name, url:row.url, affiliate_url:row.affiliate_url }); setDialogOpen(true); };
  const closeDialog = () => { setDialogOpen(false); };

  const validateForm = (f) => {
    const { name, url, affiliate_url } = f;
    if (!name.trim()) return { ok:false, reason:'name' };
    if (!url && !affiliate_url) return { ok:false, reason:'urls' };
    const isValidUrl = (u) => {
      if (!u) return true;
      try { new URL(u); return true; } catch { return false; }
    };
    if (url && !isValidUrl(url)) return { ok:false, reason:'url_invalid' };
    if (affiliate_url && !isValidUrl(affiliate_url)) return { ok:false, reason:'affiliate_invalid' };
    return { ok:true };
  };

  const save = async () => {
    try {
      const v = validateForm(form);
      if (!v.ok) {
        switch (v.reason) {
          case 'name':
            notify('warning', t('api_configs_form_required'));
            break;
          case 'urls':
            notify('warning', 'Cần ít nhất một URL hoặc Affiliate URL');
            break;
          case 'url_invalid':
            notify('warning', 'URL không hợp lệ');
            break;
          case 'affiliate_invalid':
            notify('warning', 'Affiliate URL không hợp lệ');
            break;
          default:
            notify('warning', 'Không hợp lệ');
        }
        return;
      }
      const { name, url, affiliate_url } = form;
      const payload = {
        name: name.trim(),
        url: url || affiliate_url,
        affiliate_url: affiliate_url || url,
      };
      if (editing) { await updateLink(editing.id, payload); notify('success', t('dlg_save')); }
      else { await createLink(payload); notify('success', t('dlg_create')); }
      closeDialog(); load();
    } catch(e){ notify('error', e?.normalized?.message||'Error'); }
  };

  const bulkDelete = () => {
    if (selection.length === 0) return;
    setConfirm({ open:true, ids:[...selection] });
  };
  const doBulkDelete = async () => {
    const ids = confirm.ids;
    let ok=0, fail=0;
    for (const id of ids) {
      try { await deleteLink(id); ok++; } catch { fail++; }
    }
    notify(fail? 'warning':'success', `${t('bulk_delete_result_ok', { ok })}${fail? ' / '+t('bulk_delete_result_fail', { ok, fail }):''}`);
    setConfirm({ open:false, ids:[] });
    setSelection([]);
    load();
  };

  // DataTable mong đợi mỗi cột có: key, label, (tùy chọn) render(row)
  const columns = React.useMemo(()=>[
    { key:'id', label:'ID', sortable:true },
    { key:'name', label:t('links_col_name'), sortable:true },
    { key:'url', label:'URL', render: r => r.url ? <a href={r.url} target="_blank" rel="noreferrer" style={{ overflow:'hidden', textOverflow:'ellipsis', display:'block', maxWidth:240 }}>{r.url}</a> : '' },
    { key:'affiliate_url', label:'Affiliate URL', render: r => r.affiliate_url ? <a href={r.affiliate_url} target="_blank" rel="noreferrer" style={{ overflow:'hidden', textOverflow:'ellipsis', display:'block', maxWidth:280 }}>{r.affiliate_url}</a> : '' },
    { key:'actions', label:t('col_actions'), render: r => (
      <>
        <Tooltip title={t('tooltip_edit')}><IconButton size="small" onClick={()=>openEdit(r)}><EditIcon fontSize="inherit" /></IconButton></Tooltip>
        <Tooltip title={t('tooltip_delete')}><IconButton size="small" color="error" onClick={()=>{ setConfirm({ open:true, ids:[r.id] }); }}><DeleteIcon fontSize="inherit" /></IconButton></Tooltip>
      </>
    )},
  ], [t]);

  const bulkBar = selection.length > 0 && (
    <Stack direction="row" spacing={1} sx={{ mb:1 }}>
      <Button size="small" variant="outlined" color="error" onClick={bulkDelete}>{t('bulk_delete_label', { n: selection.length })}</Button>
      <Button size="small" onClick={()=>setSelection([])}>{t('action_clear_selection')}</Button>
    </Stack>
  );

  return (
    <Paper sx={{ p:2 }}>
      <Typography variant="h5" gutterBottom data-focus-initial>{t('links_title')}</Typography>
      <Stack direction="row" spacing={1} sx={{ mb:2, flexWrap:'wrap' }}>
        <Button size="small" startIcon={<AddIcon/>} variant="contained" onClick={openAdd}>{t('links_add')}</Button>
        <Button size="small" startIcon={<RefreshIcon/>} onClick={load} disabled={loading}>{t('action_refresh')}</Button>
      </Stack>
      {bulkBar}
      {loading && rows.length===0 && (
        <SkeletonSection variant="table" rows={6} />
      )}
      <TableComponent
        tableId="linksManager"
        rows={rows}
        columns={columns}
        loading={loading}
        enablePagination
        enableQuickFilter
        enableSelection
        onSelectionChange={setSelection}
        initialPageSize={25}
        empty={t('links_empty')}
      />
      <Dialog open={dialogOpen} onClose={closeDialog} fullWidth maxWidth="sm">
        <DialogTitle>{editing ? t('links_edit_title') : t('links_create_title')}</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2} sx={{ mt:0.5 }}>
            <TextField size="small" label={t('links_field_name')} value={form.name} onChange={e=>setForm(f=>({...f, name:e.target.value}))} required />
            <TextField size="small" label="URL" value={form.url} onChange={e=>setForm(f=>({...f, url:e.target.value}))} helperText="Có thể để trống nếu đã nhập Affiliate URL" />
            <TextField size="small" label="Affiliate URL" value={form.affiliate_url} onChange={e=>setForm(f=>({...f, affiliate_url:e.target.value}))} helperText="Có thể để trống nếu đã nhập URL" />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={closeDialog}>{t('dlg_cancel')}</Button>
          <Button data-testid="links-save" onClick={save} startIcon={<SaveIcon/>} variant="contained">{editing ? t('dlg_save') : t('dlg_create')}</Button>
        </DialogActions>
      </Dialog>
      <ConfirmDialog
        open={confirm.open}
        title={t('links_delete_title')}
        message={confirm.ids.length > 1 ? t('bulk_delete_confirm', { n: confirm.ids.length }) : t('links_delete_confirm')}
        onClose={()=>setConfirm({ open:false, ids:[] })}
        onConfirm={doBulkDelete}
        danger
        confirmText={t('action_delete')}
      />
    </Paper>
  );
}
