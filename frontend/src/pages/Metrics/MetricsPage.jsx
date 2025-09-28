import React from 'react';
import { Box, Typography, Stack, TextField, Button, Paper, Chip, Tooltip, Switch, FormControlLabel, Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions, Collapse, IconButton } from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import HideSourceIcon from '@mui/icons-material/HideSource';
import DataTable from '../../components/DataTable.jsx';
import { useT } from '../../i18n/I18nProvider.jsx';
import api, { __registerNotifier } from '../../api.js';
import AdminKeyInput from '../../components/AdminKeyInput.jsx';
import { useNotify } from '../../components/NotificationProvider.jsx';

export default function MetricsPage() {
  const { t } = useT();
  const [rows, setRows] = React.useState([]);
  const [loading, setLoading] = React.useState(false);
  const [nameFilter, setNameFilter] = React.useState('');
  const [ratingFilter, setRatingFilter] = React.useState('');
  const [urlFilter, setUrlFilter] = React.useState('');
  const [histogramMetric, setHistogramMetric] = React.useState(null);
  const [histData, setHistData] = React.useState(null);
  const [refreshTick, setRefreshTick] = React.useState(0);
  const [summary, setSummary] = React.useState(null);
  const [auto, setAuto] = React.useState(false);
  const [windowMinutes, setWindowMinutes] = React.useState(60);
  const [openClear, setOpenClear] = React.useState(false);
  const [showTrends, setShowTrends] = React.useState(false);
  const [trendData, setTrendData] = React.useState(null);
  const [trendLoading, setTrendLoading] = React.useState(false);
  const [trendBuckets, setTrendBuckets] = React.useState(12);
  const notify = useNotify();
  const [openInfo, setOpenInfo] = React.useState(false);

  const fetchData = React.useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (nameFilter.trim()) params.set('name', nameFilter.trim());
      if (ratingFilter.trim()) params.set('rating', ratingFilter.trim());
      if (urlFilter.trim()) params.set('url_sub', urlFilter.trim());
      params.set('limit', '200');
      const res = await api.get('/metrics/web-vitals?' + params.toString());
      setRows(res.data || []);
    } catch {
      // silent: notifications handled globally for network/server
    } finally { setLoading(false); }
  }, [nameFilter, ratingFilter, urlFilter]);

  const fetchSummary = React.useCallback(async () => {
    try {
      const res = await api.get(`/metrics/web-vitals/summary?window_minutes=${windowMinutes}`);
      setSummary(res.data);
    } catch { /* silent */ }
  }, [windowMinutes]);

  const fetchTrends = React.useCallback(async () => {
    if (!showTrends) return;
    setTrendLoading(true);
    try {
      const params = new URLSearchParams();
      params.set('window_minutes', String(windowMinutes));
      params.set('buckets', String(trendBuckets));
      if (nameFilter.trim()) params.set('names', nameFilter.trim());
      const res = await api.get('/metrics/web-vitals/trends?' + params.toString());
      setTrendData(res.data);
    } catch { /* silent */ }
    finally { setTrendLoading(false); }
  }, [showTrends, windowMinutes, trendBuckets, nameFilter]);

  React.useEffect(() => { fetchData(); }, [fetchData, refreshTick]);
  React.useEffect(() => { fetchSummary(); }, [fetchSummary, refreshTick]);
  React.useEffect(() => { fetchTrends(); }, [fetchTrends, refreshTick]);

  React.useEffect(() => {
    if (!auto) return;
    if (import.meta.env?.TEST) {
      // Không tạo interval trong môi trường test để tránh giữ event loop.
      return;
    }
    const id = setInterval(() => { setRefreshTick(x=>x+1); }, 15000); // 15s ngoài test
    return () => clearInterval(id);
  }, [auto]);

  const exportCSV = () => {
    if (!rows.length) return;
    const headers = ['name','value','rating','session_id','timestamp','url'];
    const lines = [headers.join(',')];
    rows.forEach(r => {
      lines.push(headers.map(h => JSON.stringify(r[h] ?? '')).join(','));
    });
    const blob = new Blob([lines.join('\n')], { type:'text/csv;charset=utf-8;' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'web_vitals.csv';
    a.click();
  };

  const thresholdTooltip = (name) => {
    const n = (name||'').toUpperCase();
    if (n === 'LCP') return t('metrics_info_lcp');
    if (n === 'CLS') return t('metrics_info_cls');
    if (n === 'INP') return t('metrics_info_inp');
    return undefined;
  };

  const columns = [
    { key: 'name', label: t('metrics_col_name'), sortable: true, render: r => {
      const tip = thresholdTooltip(r.name);
      const content = <strong>{r.name}</strong>;
      return tip ? <Tooltip title={tip}>{content}</Tooltip> : content;
    }},
  { key: 'value', label: t('metrics_col_value'), sortable: true, render: r => <span style={{ cursor:'pointer', textDecoration:'underline' }} onClick={()=>openHistogram(r)}>{r.value?.toFixed(2)}</span> },
    { key: 'rating', label: t('metrics_col_rating'), sortable: true, render: r => <RatingChip rating={r.rating} t={t} /> },
    { key: 'session_id', label: t('metrics_col_session'), sortable: true },
    { key: 'timestamp', label: t('metrics_col_time'), sortable: true, render: r => new Date(r.timestamp).toLocaleTimeString() },
    { key: 'url', label: t('metrics_col_url'), render: r => <Tooltip title={r.url}><span style={{ maxWidth:180, display:'inline-block', overflow:'hidden', textOverflow:'ellipsis', verticalAlign:'bottom' }}>{r.url?.replace(location.origin,'')}</span></Tooltip> }
  ];

  const stats = React.useMemo(() => {
    const counts = { good:0, needs_improvement:0, poor:0 };
    rows.forEach(r => {
      if (r.rating === 'good') counts.good++; else if (r.rating === 'needs-improvement') counts.needs_improvement++; else if (r.rating === 'poor') counts.poor++; });
    const total = rows.length || 1;
    const pct = k => Math.round((counts[k] / total) * 100);
    return { counts, pct, total: rows.length };
  }, [rows]);

  const openHistogram = (row) => {
    setHistogramMetric(row.name);
    // Lọc cùng tên metric trong cửa sổ caches rows (nhanh, không gọi server riêng)
    const same = rows.filter(r => r.name === row.name).map(r => r.value).filter(v=>v!=null);
    same.sort((a,b)=>a-b);
    if (!same.length){ setHistData(null); return; }
    // chia 10 bins
    const bins = 10;
    const min = same[0]; const max = same[same.length-1];
    const width = (max - min) || 1;
    const counts = Array.from({ length: bins }, ()=>0);
    same.forEach(v => { let idx = Math.floor(((v - min)/width)*bins); if (idx>=bins) idx=bins-1; counts[idx]++; });
    const dist = counts.map((c,i)=>({ bin:i, count:c, from: min + (i/ bins)*width, to: min + ((i+1)/bins)*width }));
    setHistData({ min, max, width, dist, total: same.length });
  };

  return (
    <Box>
      <Typography variant="h5" gutterBottom data-focus-initial>{t('metrics_title')}</Typography>
      <Stack direction={{ xs:'column', sm:'row' }} spacing={2} alignItems={{ sm:'center' }} sx={{ mb:2 }}>
        <TextField size="small" label={t('metrics_filter_name')} value={nameFilter} onChange={e=>setNameFilter(e.target.value)} onKeyDown={e=>{ if(e.key==='Enter') fetchData(); }} />
        <TextField size="small" label={t('metrics_filter_rating')} value={ratingFilter} onChange={e=>setRatingFilter(e.target.value)} placeholder="good|needs-improvement|poor" sx={{ width:200 }} />
        <TextField size="small" label={t('metrics_filter_url')} value={urlFilter} onChange={e=>setUrlFilter(e.target.value)} sx={{ width:200 }} />
        <Button variant="outlined" size="small" disabled={loading} onClick={()=>fetchData()}>{t('metrics_refresh')}</Button>
        <Button variant="text" size="small" onClick={()=>setRefreshTick(x=>x+1)}>⟳</Button>
  <TextField size="small" type="number" label={t('metrics_window_minutes')} value={windowMinutes} onChange={e=>setWindowMinutes(Math.max(1, Number(e.target.value)||60))} sx={{ width:140 }} />
  <FormControlLabel control={<Switch checked={auto} onChange={e=>setAuto(e.target.checked)} />} label={t('metrics_auto_15s')} />
  <Button size="small" onClick={exportCSV} disabled={!rows.length}>{t('metrics_export_csv')}</Button>
  <Button size="small" color="error" onClick={()=>setOpenClear(true)}>{t('metrics_clear')}</Button>
        <Button size="small" startIcon={showTrends ? <HideSourceIcon /> : <ShowChartIcon />} onClick={()=>setShowTrends(s=>!s)}>{showTrends ? t('metrics_trend_hide') : t('metrics_trend_toggle')}</Button>
        <Box sx={{ flexGrow:1 }} />
        <Distribution stats={stats} t={t} />
        <Tooltip title={t('metrics_info_title')}><IconButton size="small" onClick={()=>setOpenInfo(true)}><InfoOutlinedIcon fontSize="inherit" /></IconButton></Tooltip>
        <AdminKeyInput />
      </Stack>
      <Collapse in={showTrends} timeout="auto" unmountOnExit>
        <Paper variant="outlined" sx={{ p:1, mb:2 }}>
          <Stack direction={{ xs:'column', sm:'row' }} spacing={2} alignItems={{ sm:'center' }} sx={{ mb:1 }}>
            <Typography variant="subtitle2">{t('metrics_trend_title')}</Typography>
            <TextField size="small" type="number" label={t('metrics_trend_bucket')} value={trendBuckets} onChange={e=>setTrendBuckets(Math.min(240, Math.max(2, Number(e.target.value)||12)))} sx={{ width:120 }} />
            <Button size="small" disabled={trendLoading} onClick={fetchTrends}>{t('metrics_refresh')}</Button>
            {trendLoading && <Typography variant="caption">{t('metrics_trend_loading')}</Typography>}
          </Stack>
          <TrendSeries data={trendData} t={t} />
        </Paper>
      </Collapse>
      <Paper variant="outlined" sx={{ p:1, mb:2 }}>
        <Typography variant="caption" color="text.secondary" sx={{ display:'block' }}>{t('metrics_recent')}: {rows.length}</Typography>
        {summary && (
          <Box sx={{ mt:0.5, display:'flex', flexWrap:'wrap', gap:1 }}>
            {Object.entries(summary.metrics || {}).map(([name, m]) => (
              <Chip key={name} size="small" label={`${name}: ${t('metrics_label_p75')}=${fmt(m.p75)} ${t('metrics_label_p95')}=${fmt(m.p95)} (${m.count})`} />
            ))}
          </Box>
        )}
      </Paper>
      <DataTable
        tableId="webVitals"
        columns={columns}
        rows={rows}
        loading={loading}
        enableQuickFilter
        enablePagination
        initialPageSize={25}
        empty={t('metrics_no_data')}
        responsiveCards
        cardTitleKey="name"
        cardSubtitleKeys={["rating"]}
      />
      <Dialog open={!!histogramMetric} onClose={()=>{ setHistogramMetric(null); setHistData(null); }} maxWidth="sm" fullWidth>
        <DialogTitle>{histogramMetric} distribution</DialogTitle>
        <DialogContent>
          {!histData && <DialogContentText>{t('metrics_extras_loading')||'Đang tải...'}</DialogContentText>}
          {histData && (
            <Box>
              <Typography variant="body2" sx={{ mb:1 }}>Min: {histData.min.toFixed(2)} – Max: {histData.max.toFixed(2)} (n={histData.total})</Typography>
              <Box sx={{ display:'flex', alignItems:'flex-end', gap:0.5, height:120 }}>
                {histData.dist.map(b => {
                  const p = b.count / histData.total;
                  return <Box key={b.bin} title={`${b.from.toFixed(2)}–${b.to.toFixed(2)}: ${b.count}`} sx={{ flex:1, position:'relative', bgcolor:'primary.main', opacity:0.85, height: Math.max(4, p*110) }} />;
                })}
              </Box>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={()=>{ setHistogramMetric(null); setHistData(null); }}>{t('dlg_cancel')}</Button>
        </DialogActions>
      </Dialog>
      <Dialog open={openClear} onClose={()=>setOpenClear(false)}>
        <DialogTitle>{t('metrics_clear')}</DialogTitle>
        <DialogContent>
          <DialogContentText>{t('metrics_clear_confirm')}</DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={()=>setOpenClear(false)}>{t('dlg_cancel')}</Button>
          <Button color="error" onClick={async()=>{
            try { await api.delete('/metrics/web-vitals', { headers: { 'X-Admin-Key': (localStorage.getItem('admin_api_key')||'') } }); notify('success', t('metrics_cleared')); setRows([]); setSummary(null); }
            catch { /* handled globally */ }
            finally { setOpenClear(false); }
          }}>{t('dlg_ok') || t('confirm_ok')}</Button>
        </DialogActions>
      </Dialog>
      <Dialog open={openInfo} onClose={()=>setOpenInfo(false)}>
        <DialogTitle>{t('metrics_info_title')}</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ whiteSpace:'pre-line', fontSize:14 }}>
            {t('metrics_info_lcp') + '\n' + t('metrics_info_cls') + '\n' + t('metrics_info_inp') + '\n\n' + t('metrics_info_hint')}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={()=>setOpenInfo(false)}>{t('confirm_ok')||'OK'}</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

function RatingChip({ rating, t }) {
  if (!rating) return null;
  let color = 'default';
  if (rating === 'good') color = 'success';
  else if (rating === 'needs-improvement') color = 'warning';
  else if (rating === 'poor') color = 'error';
  const label = rating === 'needs-improvement' ? t('metrics_stats_need') : (rating === 'poor' ? t('metrics_stats_poor') : t('metrics_stats_good'));
  return <Chip size="small" color={color} label={label} />;
}

function Distribution({ stats, t }) {
  const { counts, pct } = stats;
  const bar = [
    { key:'good', color:'#2e7d32', value: counts.good, p:pct('good'), label: t('metrics_stats_good') },
    { key:'needs_improvement', color:'#ed6c02', value: counts.needs_improvement, p:pct('needs_improvement'), label: t('metrics_stats_need') },
    { key:'poor', color:'#d32f2f', value: counts.poor, p:pct('poor'), label: t('metrics_stats_poor') },
  ];
  return (
    <Stack direction="row" spacing={1} sx={{ alignItems:'center' }}>
      {bar.map(b => (
        <Box key={b.key} sx={{ display:'flex', flexDirection:'column', alignItems:'center' }}>
          <Box sx={{ width:40, height:40, borderRadius:'4px', bgcolor:b.color, display:'flex', alignItems:'center', justifyContent:'center', color:'#fff', fontSize:12 }}>{b.p}%</Box>
          <Typography variant="caption" sx={{ mt:0.5 }}>{b.label}</Typography>
        </Box>
      ))}
    </Stack>
  );
}

function fmt(v) { return (v == null) ? '–' : Number(v).toFixed(2); }

function TrendSeries({ data, t }) {
  if (!data) return <Typography variant="caption" color="text.secondary">{t('metrics_trend_empty')}</Typography>;
  const names = Object.keys(data.series || {});
  if (!names.length) return <Typography variant="caption" color="text.secondary">{t('metrics_trend_empty')}</Typography>;
  return (
    <Stack spacing={2}>
      {names.map(name => <TrendChartRow key={name} name={name} points={data.series[name]} />)}
    </Stack>
  );
}

function TrendChartRow({ name, points }) {
  const ref = React.useRef(null);
  React.useEffect(() => {
    if (!ref.current) return;
    const canvas = ref.current;
    const ctx = canvas.getContext('2d');
  canvas.width = canvas.clientWidth * (window.devicePixelRatio||1);
    const h = canvas.height = 60 * (window.devicePixelRatio||1);
    ctx.scale(window.devicePixelRatio||1, window.devicePixelRatio||1);
    ctx.clearRect(0,0,canvas.width,canvas.height);
    const series = ['p75','p95'];
    const colors = { p75:'#1976d2', p95:'#d32f2f' };
    const allVals = [];
    points.forEach(p => series.forEach(s => { if (p[s] != null) allVals.push(p[s]); }));
    const min = allVals.length ? Math.min(...allVals) : 0;
    const max = allVals.length ? Math.max(...allVals) : 1;
    function yScale(v){ if (max === min) return h-5; return h - 5 - ((v - min)/(max-min))*(h-15); }
    function xPos(i){ if(points.length<=1) return 5; return 5 + i*( (canvas.clientWidth-10)/(points.length-1) ); }
    // grid
    ctx.strokeStyle = '#eee';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0,h-5); ctx.lineTo(canvas.clientWidth,h-5); ctx.stroke();
    series.forEach(s => {
      ctx.beginPath();
      ctx.strokeStyle = colors[s];
      ctx.lineWidth = 2;
      let first = true;
      points.forEach((p,i)=>{
        const val = p[s];
        if (val == null) return;
        const x = xPos(i);
        const y = yScale(val);
        if (first){ ctx.moveTo(x,y); first=false; } else ctx.lineTo(x,y);
      });
      ctx.stroke();
    });
    // labels min/max
    ctx.fillStyle = '#666';
    ctx.font = '10px sans-serif';
    ctx.fillText(`${name} (${min.toFixed(2)}–${max.toFixed(2)})`, 4, 10);
  }, [name, points]);
  return (
    <Box sx={{ display:'flex', flexDirection:'column' }}>
      <Box sx={{ position:'relative' }}>
        <canvas ref={ref} style={{ width:'100%', height:60 }} />
      </Box>
    </Box>
  );
}