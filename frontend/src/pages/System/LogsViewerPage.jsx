import React from 'react';
import { Box, Paper, Typography, Stack, Button, Select, MenuItem, TextField, Chip, Tooltip } from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import api from '../../../api';
import { useT } from '../../i18n/I18nProvider.jsx';

export default function LogsViewerPage(){
  const { t } = useT();
  const [files, setFiles] = React.useState([]);
  const [loading, setLoading] = React.useState(false);
  const [file, setFile] = React.useState('');
  const [lines, setLines] = React.useState([]);
  const [limit, setLimit] = React.useState(200);
  const [auto, setAuto] = React.useState(false);
  const [filter, setFilter] = React.useState('');

  const loadFiles = async () => {
    try {
      const r = await api.get('/system/logs');
      if (r.data?.files) {
        setFiles(r.data.files);
        if (!file && r.data.files.length) setFile(r.data.files[0].filename);
      }
    } catch {}
  };
  const loadLines = async () => {
    if (!file) return;
    setLoading(true);
    try {
      const r = await api.get(`/system/logs/${encodeURIComponent(file)}?n=${limit}`);
      setLines(r.data?.lines||[]);
    } catch { /* silent */ } finally { setLoading(false); }
  };
  React.useEffect(()=>{ loadFiles(); }, []);
  React.useEffect(()=>{ loadLines(); }, [file, limit]);
  React.useEffect(()=>{ if(!auto) return; const id=setInterval(()=>loadLines(), 8000); return ()=>clearInterval(id); }, [auto, file, limit]);

  const filtered = React.useMemo(()=>{
    if(!filter.trim()) return lines;
    const f = filter.trim().toLowerCase();
    return lines.filter(l => JSON.stringify(l).toLowerCase().includes(f));
  }, [lines, filter]);

  return (
    <Box>
      <Typography variant="h5" gutterBottom data-focus-initial>Logs</Typography>
      <Paper sx={{ p:2 }}>
        <Stack direction={{ xs:'column', sm:'row' }} spacing={2} sx={{ mb:2 }}>
          <Select size="small" value={file} onChange={e=>setFile(e.target.value)} sx={{ minWidth:220 }}>
            {files.map(f => <MenuItem key={f.filename} value={f.filename}>{f.filename} {f.size!=null?`(${f.size}B)`:''}</MenuItem>)}
          </Select>
          <TextField size="small" type="number" label="Tail" value={limit} onChange={e=>setLimit(Math.min(2000, Math.max(10, Number(e.target.value)||200)))} sx={{ width:110 }} />
          <TextField size="small" label="Filter" value={filter} onChange={e=>setFilter(e.target.value)} sx={{ width:200 }} />
          <Button size="small" variant="outlined" startIcon={<RefreshIcon/>} disabled={loading} onClick={loadLines}>{loading? '...' : t('metrics_refresh')}</Button>
          <Button size="small" variant={auto? 'contained':'text'} onClick={()=>setAuto(a=>!a)}>Auto 8s</Button>
          <Box sx={{ flexGrow:1 }} />
          <Chip label={filtered.length + ' / ' + lines.length} size="small" />
        </Stack>
        <Box sx={{ fontFamily:'monospace', fontSize:12, lineHeight:1.4, maxHeight:500, overflow:'auto', bgcolor:'#111', color:'#0f0', p:1, borderRadius:1 }}>
          {filtered.map((l,i)=>(
            <Tooltip key={i} title={l.ts || ''} placement="right">
              <div>{JSON.stringify(l)}</div>
            </Tooltip>
          ))}
          {!filtered.length && <Typography variant="caption" color="error">Không có dòng</Typography>}
        </Box>
      </Paper>
    </Box>
  );
}
