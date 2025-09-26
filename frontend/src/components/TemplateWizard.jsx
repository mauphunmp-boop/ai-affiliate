import React from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, TextField, Button, Box, Typography, IconButton, Tooltip, Switch, FormControlLabel, Chip } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { useNotify } from './NotificationProvider.jsx';
import { useT } from '../i18n/I18nProvider.jsx';
import { upsertAffiliateTemplate } from '../api/affiliate';

// Wizard tạo template nhanh (2 bước)
export default function TemplateWizard({ open, onClose, onCreated }) {
  const notify = useNotify();
  const { t } = useT();
  const [step, setStep] = React.useState(0);
  const [platform, setPlatform] = React.useState('');
  const [enabled, setEnabled] = React.useState(true);
  const [template, setTemplate] = React.useState('https://example.com/{target}?sub1={sub1}');
  const [params, setParams] = React.useState([{ k:'sub1', v:'' }]);
  const [loading, setLoading] = React.useState(false);
  const resetState = () => { setStep(0); setPlatform(''); setEnabled(true); setTemplate('https://example.com/{target}?sub1={sub1}'); setParams([{ k:'sub1', v:'' }]); setLoading(false); };
  React.useEffect(()=>{ if(!open) resetState(); }, [open]);

  const updateParam = (i, field, value) => setParams(p => p.map((row,idx)=> idx===i ? { ...row, [field]:value } : row));
  const addParam = () => setParams(p => [...p, { k:'', v:'' }]);
  const removeParam = (i) => setParams(p => p.filter((_,idx)=>idx!==i));

  const canNext = step === 0 ? true : true; // step 1 always pass (fields optional)
  const hasTarget = template.includes('{target}');
  const canCreate = hasTarget && template.trim().length > 0 && !loading;

  const submit = async () => {
    if (!canCreate) return;
    setLoading(true);
    try {
      const default_params = params.filter(p=>p.k.trim()).reduce((acc,p)=>{ acc[p.k.trim()] = p.v; return acc; }, {});
      await upsertAffiliateTemplate({
        network: 'accesstrade',
        platform: platform.trim() || null,
        template: template.trim(),
        default_params: Object.keys(default_params).length ? default_params : undefined,
        enabled
      });
  notify('success', t('templates_create_success'));
      onCreated?.();
      onClose();
    } catch (e) {
  const msg = e?.normalized?.message || e?.response?.data?.detail || e.message || t('error_generic');
      notify('error', msg);
    } finally { setLoading(false); }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{t('wizard_title', { step: step+1 })}</DialogTitle>
      <DialogContent dividers sx={{ display:'flex', flexDirection:'column', gap:2 }}>
        {step === 0 && (
          <Box sx={{ display:'flex', flexDirection:'column', gap:2 }}>
            <Typography variant="body2">{t('wizard_step1_desc')}</Typography>
            <TextField label="Platform" value={platform} onChange={e=>setPlatform(e.target.value)} placeholder={t('wizard_platform_ph')} />
            <FormControlLabel control={<Switch checked={enabled} onChange={e=>setEnabled(e.target.checked)} />} label={t('templates_enabled')} />
            <Typography variant="caption" color="text.secondary">{t('wizard_step1_hint')}</Typography>
          </Box>
        )}
        {step === 1 && (
          <Box sx={{ display:'flex', flexDirection:'column', gap:2 }}>
            <Box sx={{ display:'flex', alignItems:'center', gap:1 }}>
              <TextField label="Template" value={template} onChange={e=>setTemplate(e.target.value)} fullWidth multiline minRows={2} error={!hasTarget} helperText={!hasTarget ? t('wizard_need_target') : t('wizard_target_hint') } />
              <Tooltip title={t('wizard_target_tooltip')}><IconButton size="small"><InfoOutlinedIcon fontSize="inherit" /></IconButton></Tooltip>
            </Box>
            <Box>
              <Box sx={{ display:'flex', alignItems:'center', mb:1, gap:1 }}>
                <Typography variant="subtitle2">{t('wizard_default_params')}</Typography>
                <Chip label={t('wizard_optional')} size="small" />
              </Box>
              {params.map((p,i)=>(
                <Box key={i} sx={{ display:'flex', gap:1, mb:1 }}>
                  <TextField size="small" label={t('wizard_param_key')} value={p.k} onChange={e=>updateParam(i,'k',e.target.value)} sx={{ width:140 }} />
                  <TextField size="small" label={t('wizard_param_value')} value={p.v} onChange={e=>updateParam(i,'v',e.target.value)} fullWidth />
                  <IconButton size="small" aria-label="remove" disabled={params.length===1} onClick={()=>removeParam(i)}><DeleteIcon fontSize="inherit" /></IconButton>
                </Box>
              ))}
              <Button onClick={addParam} startIcon={<AddIcon />} size="small">{t('wizard_add_param')}</Button>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">{t('wizard_json_preview')}</Typography>
              <Box sx={{ fontFamily:'monospace', fontSize:12, p:1, bgcolor:'background.default', border:'1px solid', borderColor:'divider', borderRadius:1, maxHeight:120, overflow:'auto' }}>
                {JSON.stringify(params.filter(p=>p.k.trim()).reduce((a,p)=>{a[p.k.trim()]=p.v;return a;},{}), null, 2) || '{}'}
              </Box>
            </Box>
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        {step === 1 && <Button onClick={()=>setStep(0)} disabled={loading}>{t('wizard_back')}</Button>}
        <Button onClick={onClose} disabled={loading}>{t('dlg_cancel')}</Button>
        {step === 0 && <Button variant="contained" onClick={()=>setStep(1)} disabled={!canNext}>{t('wizard_next')}</Button>}
        {step === 1 && <Button variant="contained" onClick={submit} disabled={!canCreate}>{loading ? t('wizard_creating') : t('wizard_create')}</Button>}
      </DialogActions>
    </Dialog>
  );
}
