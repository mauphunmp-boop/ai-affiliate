import React from 'react';
import { Box, Paper, Typography, Chip, Stack, Select, MenuItem } from '@mui/material';
import { useT } from '../../i18n/I18nProvider.jsx';

export default function PerfDashboard() {
  const { t } = useT();
  const [metrics, setMetrics] = React.useState(() => (window.__routePerfMetrics || []).slice(-50));
  const [filter, setFilter] = React.useState('all');
  React.useEffect(() => {
    const handler = () => setMetrics((window.__routePerfMetrics || []).slice(-50));
    window.addEventListener('route-perf-update', handler);
    return () => window.removeEventListener('route-perf-update', handler);
  }, []);
  const filtered = filter==='all'? metrics : metrics.filter(m=>m.name===filter);
  const names = Array.from(new Set((window.__routePerfMetrics||[]).map(m=>m.name)));
  return (
    <Box>
      <Typography variant="h5" gutterBottom data-focus-initial>{t('perf_dash_title') || 'Hiệu năng route'}</Typography>
      <Paper sx={{ p:2, mb:3 }}>
        <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
          <Typography variant="body2">{t('perf_dash_total') || 'Tổng'}: {metrics.length}</Typography>
          <Select size="small" value={filter} onChange={e=>setFilter(e.target.value)} sx={{ minWidth:160 }}>
            <MenuItem value="all">{t('perf_dash_all') || 'Tất cả'}</MenuItem>
            {names.map(n=> <MenuItem key={n} value={n}>{n}</MenuItem>)}
          </Select>
          <Chip size="small" label={(t('perf_dash_avg')||'Avg')+': '+ avg(filtered).toFixed(1)+'ms'} />
          <Chip size="small" label={(t('perf_dash_p95')||'p95')+': '+ p(filtered,0.95).toFixed(1)+'ms'} />
        </Stack>
        <MiniChart data={filtered} />
      </Paper>
      <Paper sx={{ p:2 }}>
        <Typography variant="subtitle1" gutterBottom>{t('perf_dash_recent') || 'Gần nhất'}</Typography>
        <Box component="ul" sx={{ m:0, p:0, listStyle:'none', maxHeight:260, overflow:'auto', fontSize:13 }}>
          {filtered.slice().reverse().map((m,i)=>(
            <li key={i} style={{ display:'flex', justifyContent:'space-between', padding:'2px 0', borderBottom:'1px solid #eee' }}>
              <span>{new Date(m.ts).toLocaleTimeString()} — {m.name}</span>
              <span>{m.duration.toFixed(1)}ms</span>
            </li>
          ))}
          {!filtered.length && <li>{t('perf_dash_empty') || 'Chưa có số liệu (hãy điều hướng qua vài trang).'}</li>}
        </Box>
      </Paper>
    </Box>
  );
}

function MiniChart({ data }) {
  const last = data.slice(-40);
  if (!last.length) return <Box sx={{ mt:2, fontSize:12, color:'text.secondary' }}>{'—'}</Box>;
  const max = Math.max(...last.map(d=>d.duration));
  return (
    <Box sx={{ mt:2, display:'flex', alignItems:'flex-end', gap:1, height:80 }}>
      {last.map((d,i)=>{
        const h = (d.duration / (max||1))*70 + 5;
        return <Box key={i} sx={{ width:6, height:h, bgcolor: barColor(d.duration), borderRadius:1 }} title={`${d.name} ${d.duration.toFixed(1)}ms`} />;
      })}
    </Box>
  );
}

function barColor(ms){ if(ms<40) return 'success.main'; if(ms<80) return 'warning.main'; return 'error.main'; }
function avg(arr){ if(!arr.length) return 0; return arr.reduce((a,b)=>a+b.duration,0)/arr.length; }
function p(arr, quant){ if(!arr.length) return 0; const sorted = arr.map(x=>x.duration).sort((a,b)=>a-b); const idx = Math.min(sorted.length-1, Math.floor(sorted.length*quant)); return sorted[idx]; }
