import React, { useState } from 'react';
import { Typography, Paper, Stack, Button, Box, Alert, Divider, Switch, FormControlLabel, Chip } from '@mui/material';
import { useT } from '../../i18n/I18nProvider.jsx';
import BoltIcon from '@mui/icons-material/Bolt';
import RefreshIcon from '@mui/icons-material/Refresh';
import { setIngestPolicy, setCheckUrlsPolicy, ingestCampaignsSync, ingestPromotions, ingestTopProducts, ingestDatafeedsAll, ingestProducts, ingestCommissions } from '../../api/ingest.js';
import { INGEST_TASKS } from './ingestTaskMeta.js';
import IngestTaskForm from './IngestTaskForm.jsx';

// Simple helper to format JSON safely
const fmt = (v) => {
  try { return JSON.stringify(v, null, 2); } catch { return String(v); }
};

export default function IngestOpsPage() {
  const { t } = useT();
  const [runningTaskIds, setRunningTaskIds] = useState(new Set());
  const [log, setLog] = useState([]); // {ts, action, ok, payload}
  const [error, setError] = useState('');
  const [onlyWithCommission, setOnlyWithCommission] = useState(false);
  const [checkUrls, setCheckUrls] = useState(false);

  const pushLog = (entry) => setLog(l => [{...entry, ts: new Date().toISOString()}, ...l].slice(0, 200));
  // Expose log for tests (no env guard so Vitest can always access)
  if (typeof window !== 'undefined') {
    window.__TEST__getIngestLogs = () => log;
  }

  const run = async (label, fn, taskId=null) => {
    setError('');
    if (taskId) setRunningTaskIds(prev => new Set(prev).add(taskId));
    const started = performance.now();
    try {
      const res = await fn();
      const dur = (performance.now() - started).toFixed(0);
      pushLog({ action: label, ok: true, ms: dur, payload: res.data });
    } catch (e) {
      const msg = e?.response?.data?.detail || e.message || 'Lỗi';
      setError(msg);
      pushLog({ action: label, ok: false, payload: msg });
    } finally { if (taskId) setRunningTaskIds(prev => { const n = new Set(prev); n.delete(taskId); return n; }); }
  };

  const applyPolicy = async () => run('set_ingest_policy', () => setIngestPolicy(onlyWithCommission));
  const applyCheckUrls = async () => run('set_check_urls_excel', () => setCheckUrlsPolicy(checkUrls));

  const apiMap = {
    ingestCampaignsSync,
    ingestPromotions,
    ingestTopProducts,
    ingestDatafeedsAll,
    ingestProducts,
    ingestCommissions
  };

  const handleRunTask = async (task, payload) => {
    const fn = apiMap[task.api];
    if (!fn) return;
    await run(task.id, () => fn(payload), task.id);
  };

  return (
    <Paper sx={{ p:2 }}>
  <Typography variant="h5" gutterBottom>{t('ingest_ops_title') || 'Ingest Operations'}</Typography>
      <Typography variant="body2" sx={{ mb:2 }}>
        Thực thi thủ công các tác vụ ingest dữ liệu (campaigns, promotions, products...). Các thao tác chạy tuần tự và ghi log ngắn bên dưới.
      </Typography>
      {error && <Alert severity="error" sx={{ mb:2 }}>{error}</Alert>}
      <Stack direction={{ xs:'column', md:'row' }} spacing={4} alignItems="flex-start" sx={{ mb:4 }}>
        <Box sx={{ minWidth:260 }}>
          <Typography variant="subtitle1" gutterBottom>{t('ingest_policy_title')}</Typography>
          <FormControlLabel control={<Switch checked={onlyWithCommission} onChange={e=>setOnlyWithCommission(e.target.checked)} />} label={t('ingest_policy_only_with_commission')} />
            <Button size="small" variant="outlined" startIcon={<BoltIcon/>} onClick={applyPolicy} sx={{ mr:1 }}>{t('ingest_policy_apply')}</Button>
          <Divider sx={{ my:2 }} />
          <FormControlLabel control={<Switch checked={checkUrls} onChange={e=>setCheckUrls(e.target.checked)} />} label={t('ingest_policy_check_urls')} />
            <Button size="small" variant="outlined" startIcon={<BoltIcon/>} onClick={applyCheckUrls}>{t('ingest_policy_apply')}</Button>
          <Divider sx={{ my:2 }} />
          <Button size="small" variant="text" startIcon={<RefreshIcon/>} onClick={()=>setLog([])}>{t('common_clear') || 'Clear Log'}</Button>
        </Box>
        <Box sx={{ flex:1 }}>
          <Stack spacing={3}>
            {INGEST_TASKS.map(task => (
              <IngestTaskForm
                key={task.id}
                task={task}
                loadingTaskIds={runningTaskIds}
                onRun={payload=>handleRunTask(task, payload)}
              />
            ))}
          </Stack>
        </Box>
      </Stack>
      <Divider sx={{ mb:2 }} />
  <Typography variant="subtitle1" gutterBottom>{t('ingest_recent_logs') || 'Recent Logs'}</Typography>
  {log.length === 0 && <Typography variant="body2" color="text.secondary">{t('logs_empty')}</Typography>}
      <Stack spacing={1} sx={{ maxHeight: 380, overflowY:'auto' }}>
        {log.map((l, idx) => (
          <Paper key={idx} data-testid="ingest-log-item" variant="outlined" sx={{ p:1.2 }}>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb:0.5, flexWrap:'wrap' }}>
              <Chip data-testid="ingest-log-action" size="small" label={l.action} color={l.ok ? 'success':'error'} />
              {l.ms && <Chip size="small" label={`${l.ms} ms`} />}
              <Typography variant="caption" color="text.secondary">{new Date(l.ts).toLocaleTimeString()}</Typography>
            </Stack>
            <pre style={{ margin:0, fontSize:12, maxHeight:160, overflow:'auto' }}>{fmt(l.payload)}</pre>
          </Paper>
        ))}
      </Stack>
    </Paper>
  );
}
