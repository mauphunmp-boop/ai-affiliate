import React, { useEffect, useState, useCallback } from 'react';
import { Paper, Typography, Stack, Button, TextField, Divider } from '@mui/material';
import { getApiCacheStats, resetApiCacheStats, clearApiCache } from '../hooks/useApiCache';

/**
 * Developer-only panel hiển thị thống kê cache.
 * Chỉ nên mount trong môi trường development.
 */
export default function CacheStatsPanel() {
  const [stats, setStats] = useState(getApiCacheStats());
  const [prefix, setPrefix] = useState('');

  const refresh = useCallback(()=> setStats(getApiCacheStats()), []);

  useEffect(()=> {
    if (import.meta.env?.TEST) {
      // Bỏ poll trong test để tránh giữ event loop; test vẫn có thể gọi nút refresh thủ công nếu cần
      return;
    }
    const id = setInterval(refresh, 2000); // poll nhẹ ngoài test
    return ()=> clearInterval(id);
  }, [refresh]);

  const handleClear = () => { clearApiCache(prefix || undefined); refresh(); };
  const handleResetStats = () => { resetApiCacheStats(); refresh(); };

  return (
    <Paper elevation={3} sx={{ p:2, fontSize:12, position:'fixed', bottom:16, right:16, width:300, zIndex:1200 }}>
      <Typography variant="subtitle2" gutterBottom>Cache Stats</Typography>
      <Stack spacing={1} sx={{ fontFamily:'monospace', fontSize:12 }}>
        <div>hits: {stats.hits}</div>
        <div>staleHits: {stats.staleHits}</div>
        <div>misses: {stats.misses}</div>
        <div>forcedRefresh: {stats.forcedRefresh}</div>
        <div>errors: {stats.errors}</div>
        <div>inflight: {stats.inflight}</div>
        <div>backgroundRefresh: {stats.backgroundRefresh}</div>
      </Stack>
      <Divider sx={{ my:1 }} />
      <Stack direction="row" spacing={1} alignItems="center">
        <TextField size="small" label="Prefix" value={prefix} onChange={e=>setPrefix(e.target.value)} fullWidth />
      </Stack>
      <Stack direction="row" spacing={1} sx={{ mt:1 }}>
        <Button size="small" onClick={handleClear} variant="outlined">Clear</Button>
  <Button size="small" onClick={handleResetStats}>Reset Stats</Button>
        <Button size="small" onClick={refresh}>⟳</Button>
      </Stack>
    </Paper>
  );
}
