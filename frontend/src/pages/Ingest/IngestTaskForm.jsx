import React, { useState } from 'react';
import { Paper, Stack, TextField, Switch, FormControlLabel, Button, Typography, Box, Chip, Accordion, AccordionSummary, AccordionDetails, CircularProgress } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import { useT } from '../../i18n/I18nProvider.jsx';

function parseJsonSafe(v) {
  try { return JSON.parse(v); } catch { return null; }
}

// runningTaskId: id của task đang chạy (spinner chỉ hiển thị cho task này)
export default function IngestTaskForm({ task, onRun, loadingTaskIds=new Set(), defaultCollapsed=true }) {
  const { t, lang } = useT();
  const [form, setForm] = useState(() => ({ ...task.defaultPayload }));
  const [raw, setRaw] = useState(() => initRaw(task.defaultPayload, task.fields));
  const [error, setError] = useState(null);
  const [jsonInvalidKeys, setJsonInvalidKeys] = useState(()=> new Set());

  function initRaw(payload, fields) {
    const r = {};
    fields.forEach(f => {
      const val = payload[f.key];
      if (f.type === 'json') r[f.key] = JSON.stringify(val, null, 2);
      else if (f.type === 'list') r[f.key] = Array.isArray(val) ? val.join(', ') : (val || '');
      else r[f.key] = val ?? '';
    });
    return r;
  }

  const resetDefaults = () => {
    const fresh = { ...task.defaultPayload };
    setForm(fresh);
    setRaw(initRaw(fresh, task.fields));
    setError(null);
  };

  const updateField = (f, value) => {
    setRaw(r => ({ ...r, [f.key]: value }));
    if (f.type === 'boolean') {
      setForm(prev => ({ ...prev, [f.key]: !!value }));
    } else if (f.type === 'number') {
      const num = value === '' ? '' : Number(value);
      setForm(prev => ({ ...prev, [f.key]: Number.isNaN(num) ? prev[f.key] : num }));
    } else if (f.type === 'json') {
      const parsed = parseJsonSafe(value);
      setJsonInvalidKeys(keys => {
        const next = new Set(keys);
        if (parsed === null) {
          next.add(f.key);
        } else {
          next.delete(f.key);
          setForm(prev => ({ ...prev, [f.key]: parsed }));
        }
        if (next.size > 0) setError(t('ingest_error_invalid_json') || 'JSON không hợp lệ');
        else if (next.size === 0) setError(null);
        return next;
      });
      return;
    } else if (f.type === 'list') {
      const list = (value || '')
        .split(',')
        .map(s => s.trim())
        .filter(s => s.length > 0);
      setForm(prev => ({ ...prev, [f.key]: list }));
    } else {
      setForm(prev => ({ ...prev, [f.key]: value }));
    }
  };

  const run = () => {
    if (jsonInvalidKeys.size > 0) {
      setError(t('ingest_error_invalid_json') || 'JSON không hợp lệ');
      return;
    }
    // Validate required fields (simple client-side) for new UX guidance
    const missing = (task.fields || []).filter(f => f.required).filter(f => {
      const v = form[f.key];
      if (f.type === 'list') return !Array.isArray(v) || v.length === 0;
      if (f.type === 'json') return v == null; // assume json default always present
      return v === '' || v == null;
    });
    if (missing.length) {
      setError('Thiếu: ' + missing.map(m=>m.key).join(', '));
      return;
    }
    setError(null);
    onRun(form);
  };

  const isRunning = loadingTaskIds.has(task.id);
  const showSpinner = isRunning;

  return (
    <Accordion defaultExpanded={!defaultCollapsed} disableGutters sx={{ '&:before':{ display:'none' }, boxShadow:'none', mb:1, borderRadius:1 }}>
      <AccordionSummary
        expandIcon={<ExpandMoreIcon />}
        sx={{ px:1.5, py:1, bgcolor:'background.paper', border:'1px solid', borderColor:'divider', borderRadius:1, '&.Mui-focusVisible': { outline:'none' }, '&:focus': { outline:'none' }, '& .MuiAccordionSummary-content':{ my:0 } }}
      > 
        <Box sx={{ display:'flex', alignItems:'center', gap:1 }}>
          <Typography variant="subtitle1" sx={{ fontWeight:600 }}>{t(task.titleKey) || task.id}</Typography>
          {showSpinner && <CircularProgress size={16} thickness={5} data-testid={`ingest-running-${task.id}`} />}
        </Box>
        <Typography variant="caption" color="text.secondary" sx={{ ml:2 }}>{t(task.descKey) || ''}</Typography>
      </AccordionSummary>
      <AccordionDetails sx={{ pt:0 }}>
      <Paper elevation={0} sx={{ p:2, pt:0 }}>
      <Stack spacing={2} direction={{ xs:'column', md:'row' }} alignItems="flex-start">
        <Box sx={{ flex:1 }}>
          <Stack spacing={1.2}>
            {task.fields.map(f => {
              if (f.type === 'boolean') {
                return (
                  <FormControlLabel key={f.key}
                    control={<Switch size="small" checked={!!form[f.key]} onChange={e=>updateField(f, e.target.checked)} />}
                    label={t('ingest_field_'+f.key) || f.key}
                  />
                );
              }
              if (f.type === 'json' || f.textarea) {
                return (
                  <TextField key={f.key} label={t('ingest_field_'+f.key) || f.key} value={raw[f.key]}
                    onChange={e=>updateField(f, e.target.value)} multiline minRows={3} fullWidth size="small"
                    helperText={t('ingest_field_'+f.key+'_desc') || f.placeholder || ''} />
                );
              }
              if (f.type === 'list') {
                return (
                  <TextField key={f.key} size="small" fullWidth
                    label={(t('ingest_field_'+f.key) || f.key) + ' (comma separated)'}
                    value={raw[f.key]}
                    onChange={e=>updateField(f, e.target.value)}
                    placeholder={f.placeholder || 'a,b,c'}
                    helperText={f.required ? 'Bắt buộc. Ngăn cách bằng dấu phẩy.' : 'Ngăn cách bằng dấu phẩy.'} />
                );
              }
              return (
                <TextField key={f.key} type={f.type === 'number' ? 'number':'text'} size="small" fullWidth
                  label={t('ingest_field_'+f.key) || f.key} value={raw[f.key]}
                  onChange={e=>updateField(f, e.target.value)} placeholder={f.placeholder}
                  helperText={t('ingest_field_'+f.key+'_desc') || ''} />
              );
            })}
          </Stack>
          {error && <Typography data-testid="ingest-json-error" variant="caption" color="error" sx={{ mt:1 }}>{error}</Typography>}
          <Stack direction="row" spacing={1} sx={{ mt:1 }}>
            <Button data-testid={`ingest-run-${task.id}`} size="small" variant="contained" startIcon={<PlayArrowIcon/>} disabled={isRunning} onClick={run}>
              {t('ingest_run') || 'Chạy'}
            </Button>
            <Button size="small" variant="outlined" startIcon={<RestartAltIcon/>} disabled={isRunning} onClick={resetDefaults}>
              {t('reset_defaults') || 'Reset'}
            </Button>
          </Stack>
        </Box>
        <Box sx={{ flex:1, minWidth:260 }}>
          <Typography variant="subtitle2" gutterBottom>{t('ingest_example_payload') || 'Ví dụ payload'}</Typography>
          <pre style={{ margin:0, fontSize:12, background:'#f7f7f7', padding:8, maxHeight:260, overflow:'auto' }}>
            {JSON.stringify(task.defaultPayload, null, 2)}
          </pre>
          <Box sx={{ mt:2 }}>
            <Typography variant="subtitle2" gutterBottom>{t('ingest_field_legend_title') || 'Field legend'}</Typography>
            <Box sx={{ display:'flex', flexWrap:'wrap', gap:0.75, mb:0.5 }}>
              {task.fields.map(f => {
                const label = f.required ? `${f.key} *` : f.key;
                return <Chip key={f.key} size="small" variant="outlined" color={f.required ? 'error':'default'} label={label} />;
              })}
            </Box>
            <Typography variant="caption" color="text.secondary">{t('ingest_field_legend_hint') || '* Required. Lists: comma + space ("a, b").'}</Typography>
          </Box>
        </Box>
      </Stack>
      </Paper>
      </AccordionDetails>
    </Accordion>
  );
}
