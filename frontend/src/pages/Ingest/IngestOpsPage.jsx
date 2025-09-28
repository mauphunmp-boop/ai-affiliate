import React, { useState } from 'react';
import { Typography, Paper, Stack, Button, Box, Alert, Divider, TextField, Switch, FormControlLabel, Chip } from '@mui/material';
import { useT } from '../../i18n/I18nProvider.jsx';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import BoltIcon from '@mui/icons-material/Bolt';
import CloudDownloadIcon from '@mui/icons-material/CloudDownload';
import RefreshIcon from '@mui/icons-material/Refresh';
import {
  ingestCampaignsSync,
  ingestPromotions,
  ingestTopProducts,
  ingestDatafeedsAll,
  ingestProducts,
  ingestCommissions,
  setIngestPolicy,
  setCheckUrlsPolicy,
  ingestPresetTiktok
} from '../../api/ingest.js';

// Simple helper to format JSON safely
const fmt = (v) => {
  try { return JSON.stringify(v, null, 2); } catch { return String(v); }
};

export default function IngestOpsPage() {
  const { t } = useT();
  const [loading, setLoading] = useState(false);
  const [log, setLog] = useState([]); // {ts, action, ok, payload}
  const [error, setError] = useState('');
  const [merchant, setMerchant] = useState('');
  const [onlyWithCommission, setOnlyWithCommission] = useState(false);
  const [checkUrls, setCheckUrls] = useState(false);
  const [datafeedsLimit, setDatafeedsLimit] = useState('100');
  const [datafeedsPages, setDatafeedsPages] = useState('5');
  const [productsPath, setProductsPath] = useState('/v1/datafeeds');
  const [productsLimit, setProductsLimit] = useState('50');
  const [topProductsLimit, setTopProductsLimit] = useState('50');

  const pushLog = (entry) => setLog(l => [{...entry, ts: new Date().toISOString()}, ...l].slice(0, 200));

  const run = async (label, fn) => {
    setLoading(true); setError('');
    const started = performance.now();
    try {
      const res = await fn();
      const dur = (performance.now() - started).toFixed(0);
      pushLog({ action: label, ok: true, ms: dur, payload: res.data });
    } catch (e) {
      const msg = e?.response?.data?.detail || e.message || 'Lỗi';
      setError(msg);
      pushLog({ action: label, ok: false, payload: msg });
    } finally { setLoading(false); }
  };

  const applyPolicy = async () => {
    await run('set_ingest_policy', () => setIngestPolicy(onlyWithCommission));
  };
  const applyCheckUrls = async () => {
    await run('set_check_urls_excel', () => setCheckUrlsPolicy(checkUrls));
  };

  return (
    <Paper sx={{ p:2 }}>
  <Typography variant="h5" gutterBottom>{t('ingest_ops_title') || 'Ingest Operations'}</Typography>
      <Typography variant="body2" sx={{ mb:2 }}>
        Thực thi thủ công các tác vụ ingest dữ liệu (campaigns, promotions, products...). Các thao tác chạy tuần tự và ghi log ngắn bên dưới.
      </Typography>
      {error && <Alert severity="error" sx={{ mb:2 }}>{error}</Alert>}
      <Stack direction={{ xs:'column', md:'row' }} spacing={4} alignItems="flex-start" sx={{ mb:3 }}>
        <Box sx={{ minWidth:260 }}>
          <Typography variant="subtitle1" gutterBottom>{t('ingest_policy_title')}</Typography>
          <FormControlLabel control={<Switch checked={onlyWithCommission} onChange={e=>setOnlyWithCommission(e.target.checked)} />} label={t('ingest_policy_only_with_commission')} />
          <Button size="small" variant="outlined" startIcon={<BoltIcon/>} disabled={loading} onClick={applyPolicy} sx={{ mr:1 }}>{t('ingest_policy_apply')}</Button>
          <Divider sx={{ my:2 }} />
          <FormControlLabel control={<Switch checked={checkUrls} onChange={e=>setCheckUrls(e.target.checked)} />} label={t('ingest_policy_check_urls')} />
          <Button size="small" variant="outlined" startIcon={<BoltIcon/>} disabled={loading} onClick={applyCheckUrls}>{t('ingest_policy_apply')}</Button>
        </Box>
        <Box sx={{ flex:1 }}>
          <Typography variant="subtitle1" gutterBottom>{t('ingest_quick_params') || 'Tham số nhanh'}</Typography>
          <Stack direction="row" spacing={2} flexWrap="wrap" sx={{ mb:2 }}>
            <TextField size="small" label="Merchant" value={merchant} onChange={e=>setMerchant(e.target.value)} placeholder="vd: tikivn" />
            <TextField size="small" label="Datafeeds limit/page" value={datafeedsLimit} onChange={e=>setDatafeedsLimit(e.target.value.replace(/[^0-9]/g,''))} sx={{ width:150 }} />
            <TextField size="small" label="Datafeeds pages" value={datafeedsPages} onChange={e=>setDatafeedsPages(e.target.value.replace(/[^0-9]/g,''))} sx={{ width:150 }} />
            <TextField size="small" label="Products path" value={productsPath} onChange={e=>setProductsPath(e.target.value)} sx={{ width:200 }} />
            <TextField size="small" label="Products limit" value={productsLimit} onChange={e=>setProductsLimit(e.target.value.replace(/[^0-9]/g,''))} sx={{ width:140 }} />
            <TextField size="small" label="Top products limit" value={topProductsLimit} onChange={e=>setTopProductsLimit(e.target.value.replace(/[^0-9]/g,''))} sx={{ width:170 }} />
          </Stack>
          <Stack direction={{ xs:'column', sm:'row' }} spacing={1} flexWrap="wrap">
            <Button size="small" variant="contained" startIcon={<PlayArrowIcon/>} disabled={loading} onClick={()=>run('campaigns_sync', ()=>ingestCampaignsSync({ provider:'accesstrade', enrich: true }))}>Campaigns Sync</Button>
            <Button size="small" variant="contained" startIcon={<PlayArrowIcon/>} disabled={loading} onClick={()=>run('promotions', ()=>ingestPromotions({ provider:'accesstrade', merchant: merchant || undefined }))}>Promotions</Button>
            <Button size="small" variant="contained" startIcon={<PlayArrowIcon/>} disabled={loading} onClick={()=>run('top_products', ()=>ingestTopProducts({ provider:'accesstrade', merchant: merchant || undefined, limit: topProductsLimit || '50' }))}>Top Products</Button>
            <Button size="small" variant="contained" startIcon={<CloudDownloadIcon/>} disabled={loading} onClick={()=>run('datafeeds_all', ()=>ingestDatafeedsAll({ provider:'accesstrade', limit_per_page: datafeedsLimit || '100', max_pages: datafeedsPages || '5' }))}>Datafeeds All</Button>
            <Button size="small" variant="contained" startIcon={<PlayArrowIcon/>} disabled={loading} onClick={()=>run('products_generic', ()=>ingestProducts({ provider:'accesstrade', path: productsPath, params: { merchant: merchant || undefined, limit: productsLimit || '50', page: '1' } }))}>Products</Button>
            <Button size="small" variant="contained" startIcon={<PlayArrowIcon/>} disabled={loading} onClick={()=>run('commissions', ()=>ingestCommissions({ provider:'accesstrade', merchant: merchant || undefined }))}>Commissions</Button>
            <Button size="small" variant="outlined" startIcon={<PlayArrowIcon/>} disabled={loading} onClick={()=>run('preset_tiktok', ()=>ingestPresetTiktok({ merchant: merchant || 'tiktokshop' }))}>Preset TikTok</Button>
            <Button size="small" variant="text" startIcon={<RefreshIcon/>} disabled={loading} onClick={()=>setLog([])}>Clear Log</Button>
          </Stack>
        </Box>
      </Stack>
      <Divider sx={{ mb:2 }} />
      <Typography variant="subtitle1" gutterBottom>Log gần nhất</Typography>
      {log.length === 0 && <Typography variant="body2" color="text.secondary">Chưa có log.</Typography>}
      <Stack spacing={1} sx={{ maxHeight: 380, overflowY:'auto' }}>
        {log.map((l, idx) => (
          <Paper key={idx} variant="outlined" sx={{ p:1.2 }}>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb:0.5, flexWrap:'wrap' }}>
              <Chip size="small" label={l.action} color={l.ok ? 'success':'error'} />
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
