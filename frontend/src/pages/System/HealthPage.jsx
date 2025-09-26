import React, { useEffect, useState } from 'react';
import { Typography, Paper, Button, Alert, Chip, Box, Stack, Grid, Divider } from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import api from '../../../api';
import { useT } from '../../i18n/I18nProvider.jsx';

export default function HealthPage() {
  const { t } = useT();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [ts, setTs] = useState(null);

  const load = async () => {
    setLoading(true); setError('');
    try {
      const res = await api.get('/health/full');
      setData(res.data);
      setTs(new Date());
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Error');
    } finally { setLoading(false); }
  };
  useEffect(()=>{ load(); }, []);

  const mig = data?.migrations || {};
  const counts = data?.counts || {};
  const env = data?.env || {};

  return (
    <Paper sx={{ p:2 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb:2 }}>
        <Typography variant="h5">{t('health_title')}</Typography>
        <Button size="small" startIcon={<RefreshIcon/>} onClick={load} disabled={loading}>
          {loading ? t('health_loading') : t('health_refresh')}
        </Button>
      </Stack>
      {ts && <Typography variant="caption" sx={{ display:'block', mb:2 }}>{t('health_last_updated')}: {ts.toLocaleTimeString()}</Typography>}
      {error && <Alert severity="error" sx={{ mb:2 }}>{error}</Alert>}
      {data && (
        <Box>
          <Grid container spacing={2}>
            <Grid item xs={12} md={6} lg={4}>
              <Paper variant="outlined" sx={{ p:1.5 }}>
                <Typography variant="subtitle2" gutterBottom>{t('health_db')}</Typography>
                <Stack direction="row" spacing={1} flexWrap="wrap">
                  <Chip size="small" label={data.db?.ok ? t('health_ok') : t('health_not_ok')} color={data.db?.ok ? 'success':'error'} />
                  {data.migrations?.engine && <Chip size="small" label={t('health_engine') + ': ' + data.migrations.engine} />}
                  {data.db?.error && <Chip size="small" color="error" label={(data.db.error || '').slice(0,40)} />}
                </Stack>
              </Paper>
            </Grid>
            <Grid item xs={12} md={6} lg={4}>
              <Paper variant="outlined" sx={{ p:1.5 }}>
                <Typography variant="subtitle2" gutterBottom>{t('health_migrations')}</Typography>
                <Stack direction="row" spacing={1} flexWrap="wrap">
                  <Chip size="small" label={mig.ok ? t('health_ok') : t('health_not_ok')} color={mig.ok ? 'success':'error'} />
                  <Chip size="small" label={t('health_platform_col') + '=' + (mig.affiliate_templates_platform_column ? 'yes':'no')} color={mig.affiliate_templates_platform_column ? 'success':'warning'} />
                  <Chip size="small" label={t('health_legacy_constraint') + '=' + (mig.legacy_constraint_uq_merchant_network_present ? 'yes':'no')} color={mig.legacy_constraint_uq_merchant_network_present ? 'warning':'success'} />
                </Stack>
              </Paper>
            </Grid>
            <Grid item xs={12} md={6} lg={4}>
              <Paper variant="outlined" sx={{ p:1.5 }}>
                <Typography variant="subtitle2" gutterBottom>{t('health_counts')}</Typography>
                <Stack direction="row" spacing={1} flexWrap="wrap">
                  {Object.entries(counts).map(([k,v]) => <Chip key={k} size="small" label={`${k}=${v ?? 'n/a'}`} />)}
                </Stack>
              </Paper>
            </Grid>
            <Grid item xs={12} md={6} lg={4}>
              <Paper variant="outlined" sx={{ p:1.5 }}>
                <Typography variant="subtitle2" gutterBottom>{t('health_env')}</Typography>
                <Stack direction="row" spacing={1} flexWrap="wrap">
                  {Object.entries(env).map(([k,v]) => <Chip key={k} size="small" label={`${k}=${v}`} />)}
                </Stack>
              </Paper>
            </Grid>
          </Grid>
          <Divider sx={{ my:2 }} />
          <Typography variant="subtitle2" gutterBottom>Raw JSON:</Typography>
            <pre style={{ margin:0, fontSize:12, maxHeight:260, overflow:'auto' }}>{JSON.stringify(data, null, 2)}</pre>
        </Box>
      )}
    </Paper>
  );
}
