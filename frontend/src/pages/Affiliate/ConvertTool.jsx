import React, { useState, useEffect, useRef } from 'react';
import { Typography, Paper, TextField, Box, Button, IconButton, MenuItem, Tooltip, Divider, Chip, Alert } from '@mui/material';
import GlossaryTerm from '../../components/GlossaryTerm.jsx';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import ContentPasteGoIcon from '@mui/icons-material/ContentPasteGo';
import CopyButton from '../../components/CopyButton.jsx';
import usePersistedState from '../../hooks/usePersistedState.js';
import { convertAffiliateLink } from '../../api/affiliate';

const KNOWN_PLATFORMS = ['shopee','lazada','tiki','tiktok','sendo'];

export default function ConvertTool() {
  const [url, setUrl] = usePersistedState('convert_url', '');
  const [platform, setPlatform] = usePersistedState('convert_platform', '');
  const manualPlatformRef = useRef(false); // đánh dấu user tự chọn để không override ngoài ý muốn
  const [params, setParams] = usePersistedState('convert_params', [{ k: 'sub1', v: '' }]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  const updateParam = (i, field, value) => {
    setParams(p => p.map((row, idx) => idx === i ? { ...row, [field]: value } : row));
  };
  const addParam = () => setParams(p => [...p, { k: '', v: '' }]);
  const removeParam = (i) => setParams(p => p.filter((_, idx) => idx !== i));
  const reset = () => { setUrl(''); setPlatform(''); setParams([{ k:'sub1', v:'' }]); setResult(null); setError(''); };

  // Auto detect platform khi URL đổi: nếu tìm thấy & (platform đang rỗng hoặc platform khác nhưng chưa bị user override thủ công) thì cập nhật
  useEffect(() => {
    if (!url) return;
    const lower = url.toLowerCase();
    const found = KNOWN_PLATFORMS.find(p => lower.includes('//' + p + '.') || lower.includes(p + '.vn'));
    if (found && (!manualPlatformRef.current) && platform !== found) {
      setPlatform(found);
      manualPlatformRef.current = false; // auto detect reset
    }
  }, [url, platform, setPlatform]);

  // Persist state handled by usePersistedState hook


  const onSubmit = async (e) => {
    e.preventDefault();
    setError(''); setResult(null);
    if (!url.trim()) { setError('URL không được trống'); return; }
    const body = {
      url: url.trim(),
      network: 'accesstrade',
      platform: platform.trim() || null,
    };
    const paramObj = {};
    params.filter(p=>p.k.trim()).forEach(p => { paramObj[p.k.trim()] = p.v; });
    if (Object.keys(paramObj).length) body.params = paramObj;
    setLoading(true);
    try {
      const res = await convertAffiliateLink(body);
      setResult(res.data);
    } catch (e) {
      const msg = e?.response?.data?.detail || e.message || 'Lỗi không xác định';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const platformPrev = useRef(platform);
  const [platformFlash, setPlatformFlash] = useState(false);
  useEffect(() => {
    if (platform && platformPrev.current !== platform) {
      setPlatformFlash(true);
      const t = setTimeout(()=>setPlatformFlash(false), 1200);
      return () => clearTimeout(t);
    }
    platformPrev.current = platform;
  }, [platform]);

  const pasteAndDetect = async () => {
    try {
      const clip = await navigator.clipboard.readText();
      if (clip) setUrl(clip);
    } catch {}
  };

  return (
    <Paper sx={{ p:2 }}>
      <Typography variant="h5" gutterBottom>Convert Link Affiliate</Typography>
      <Typography variant="body2" sx={{ mb:2 }}>
        Nhập URL gốc và (tùy chọn) <GlossaryTerm term="platform">platform</GlossaryTerm> để tạo affiliate_url + <GlossaryTerm term="shortlink">shortlink</GlossaryTerm> (/r/&#123;&#123;token&#125;&#125;). Bạn có thể thêm tham số tracking.
      </Typography>
      <Box component="form" onSubmit={onSubmit} sx={{ display:'flex', flexDirection:'column', gap:2 }}>
        <Box sx={{ display:'flex', gap:1, alignItems:'flex-start' }}>
          <TextField label="URL gốc" value={url} onChange={e=>setUrl(e.target.value)} required fullWidth />
          <Tooltip title="Dán từ clipboard và auto detect"><span><IconButton aria-label="paste url from clipboard" onClick={pasteAndDetect}><ContentPasteGoIcon /></IconButton></span></Tooltip>
        </Box>
        <TextField label="Platform" select SelectProps={{ native:true }} value={platform} onChange={e=>{ manualPlatformRef.current = true; setPlatform(e.target.value); }} helperText="Có thể bỏ trống để dùng template mặc định network nếu có" FormHelperTextProps={{ sx: platformFlash ? { animation:'pulse 1.2s ease-in-out' } : undefined }} sx={platformFlash ? { borderRadius:1, animation:'pulse-bg 1.2s' } : undefined}>
          <option value="">(Không chỉ định)</option>
          {KNOWN_PLATFORMS.map(p => <option key={p} value={p}>{p}</option>)}
        </TextField>
        <Box>
          <Box sx={{ display:'flex', alignItems:'center', mb:1, gap:1 }}>
            <Typography variant="subtitle1">Tham số tracking</Typography>
            <Chip label="sub2, utm_source,... tự động nếu thiếu" size="small" />
          </Box>
          {params.map((row,i) => (
            <Box key={i} sx={{ display:'flex', gap:1, mb:1 }}>
              <TextField size="small" label="Key" value={row.k} onChange={e=>updateParam(i,'k',e.target.value)} sx={{ width:180 }} />
              <TextField size="small" label="Value" value={row.v} onChange={e=>updateParam(i,'v',e.target.value)} fullWidth />
              <IconButton aria-label="remove" onClick={()=>removeParam(i)} disabled={params.length===1}><DeleteIcon fontSize="small" /></IconButton>
            </Box>
          ))}
          <Button startIcon={<AddIcon />} size="small" onClick={addParam}>Thêm tham số</Button>
        </Box>
        <Box sx={{ display:'flex', gap:2 }}>
          <Button type="submit" variant="contained" disabled={loading}>{loading ? 'Đang xử lý...' : 'Convert'}</Button>
          <Button onClick={reset} disabled={loading}>Reset</Button>
        </Box>
      </Box>
      <Divider sx={{ my:3 }} />
      {error && <Alert severity="error" sx={{ mb:2 }}>{error}</Alert>}
      {result && (
        <Box>
          <Typography variant="h6" gutterBottom>Kết quả</Typography>
          <Box sx={{ mb:2 }}>
            <Typography variant="subtitle2">Affiliate URL</Typography>
            <Box sx={{ display:'flex', gap:1, alignItems:'center', wordBreak:'break-all' }}>
              <Typography variant="body2" sx={{ flex:1 }}>{result.affiliate_url}</Typography>
              <CopyButton size="small" value={result.affiliate_url} title="Copy" />
            </Box>
          </Box>
          <Box sx={{ mb:2 }}>
            <Typography variant="subtitle2">Shortlink</Typography>
            <Box sx={{ display:'flex', gap:1, alignItems:'center' }}>
              <Typography variant="body2">{result.short_url}</Typography>
              <CopyButton size="small" value={result.short_url} title="Copy" />
              <Button size="small" component="a" href={result.short_url} target="_blank" rel="noreferrer">Mở</Button>
            </Box>
          </Box>
          <Alert severity="info">Nếu shortlink trả 404 khi mở trực tiếp frontend, đảm bảo backend và reverse proxy phục vụ cùng origin hoặc dùng full URL.</Alert>
        </Box>
      )}
    </Paper>
  );
}
