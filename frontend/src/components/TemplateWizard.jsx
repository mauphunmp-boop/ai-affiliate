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
  // Helper: nếu chưa có bản dịch (trả về đúng key) thì dùng fallback VN
  const tt = React.useCallback((key, fallback, vars) => {
    const v = t(key, vars);
    return v === key ? fallback : v;
  }, [t]);
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
  notify('success', tt('templates_create_success', 'Tạo template thành công'));
      onCreated?.();
      onClose();
    } catch (e) {
  const msg = e?.normalized?.message || e?.response?.data?.detail || e.message || tt('error_generic', 'Có lỗi xảy ra');
      notify('error', msg);
    } finally { setLoading(false); }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
  <DialogTitle>{tt('wizard_title', `Bước ${step+1}`, { step: step+1 })}</DialogTitle>
      <DialogContent dividers sx={{ display:'flex', flexDirection:'column', gap:2 }}>
        {step === 0 && (
          <Box sx={{ display:'flex', flexDirection:'column', gap:2 }}>
            <Typography variant="body2">{tt('wizard_step1_desc', 'Thiết lập thông tin cơ bản cho template affiliate.')}</Typography>
            <TextField label="Platform" value={platform} onChange={e=>setPlatform(e.target.value)} placeholder={tt('wizard_platform_ph', 'Tên platform (tuỳ chọn)')} />
            <FormControlLabel control={<Switch checked={enabled} onChange={e=>setEnabled(e.target.checked)} />} label={tt('templates_enabled', 'Bật')} />
            <Typography variant="caption" color="text.secondary">{tt('wizard_step1_hint', 'Bạn có thể để trống platform nếu không ràng buộc.')}</Typography>
          </Box>
        )}
        {step === 1 && (
          <Box sx={{ display:'flex', flexDirection:'column', gap:2 }}>
            <Box sx={{ display:'flex', alignItems:'center', gap:1 }}>
              <TextField data-testid="wizard-template" label="Template" value={template} onChange={e=>setTemplate(e.target.value)} fullWidth multiline minRows={2} error={!hasTarget} helperText={!hasTarget ? tt('wizard_need_target', 'Template phải chứa {target}') : tt('wizard_target_hint', 'Sử dụng {target} nơi sẽ thay URL gốc')} />
              <Tooltip title={tt('wizard_target_tooltip', 'Placeholder {target} sẽ được thay bằng URL đích')}><IconButton size="small"><InfoOutlinedIcon fontSize="inherit" /></IconButton></Tooltip>
            </Box>
            <Box>
              <Box sx={{ display:'flex', alignItems:'center', mb:1, gap:1 }}>
                <Typography variant="subtitle2">{tt('wizard_default_params', 'Tham số mặc định')}</Typography>
                <Chip label={tt('wizard_optional', 'Tuỳ chọn')} size="small" />
              </Box>
              {params.map((p,i)=>(
                <Box key={i} sx={{ display:'flex', gap:1, mb:1 }}>
                  <TextField size="small" label={tt('wizard_param_key', 'Key')} value={p.k} onChange={e=>updateParam(i,'k',e.target.value)} sx={{ width:140 }} />
                  <TextField size="small" label={tt('wizard_param_value', 'Value')} value={p.v} onChange={e=>updateParam(i,'v',e.target.value)} fullWidth />
                  <IconButton size="small" aria-label="remove" disabled={params.length===1} onClick={()=>removeParam(i)}><DeleteIcon fontSize="inherit" /></IconButton>
                </Box>
              ))}
              <Button onClick={addParam} startIcon={<AddIcon />} size="small">{tt('wizard_add_param', 'Thêm param')}</Button>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">{tt('wizard_json_preview', 'JSON xem trước')}</Typography>
              <Box sx={{ fontFamily:'monospace', fontSize:12, p:1, bgcolor:'background.default', border:'1px solid', borderColor:'divider', borderRadius:1, maxHeight:120, overflow:'auto' }}>
                {JSON.stringify(params.filter(p=>p.k.trim()).reduce((a,p)=>{a[p.k.trim()]=p.v;return a;},{}), null, 2) || '{}'}
              </Box>
            </Box>
          </Box>
        )}
      </DialogContent>
      <DialogActions>
  {step === 1 && <Button onClick={()=>setStep(0)} disabled={loading}>{tt('wizard_back', 'Quay lại')}</Button>}
  <Button onClick={onClose} disabled={loading}>{tt('dlg_cancel', 'Hủy')}</Button>
  {step === 0 && <Button variant="contained" onClick={()=>setStep(1)} disabled={!canNext}>{tt('wizard_next', 'Tiếp tục')}</Button>}
  {step === 1 && <Button variant="contained" onClick={submit} disabled={!canCreate}>{loading ? tt('wizard_creating', 'Đang tạo...') : tt('wizard_create', 'Tạo template')}</Button>}
      </DialogActions>
    </Dialog>
  );
}
