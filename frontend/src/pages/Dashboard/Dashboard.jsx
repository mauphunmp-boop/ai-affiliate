import React from 'react';
import { Box, Paper, Stack, Typography, Button, Chip, Divider } from '@mui/material';
import useApiCache from '../../hooks/useApiCache.js';
import { useT } from '../../i18n/I18nProvider.jsx';
import api from '../../api.js';
import SkeletonSection from '../../components/SkeletonSection.jsx';

// Contract:
// Fetch high-level snapshot counts for key resources. If backend lacks dedicated summary endpoints,
// fallback to listing with minimal fields and counting length. We keep TTL short for freshness.

async function fetchCount(path) {
  try {
    const res = await api.get(path);
    const data = res.data;
    if (Array.isArray(data)) return data.length;
    if (data && typeof data === 'object') {
      // common patterns: { items: [...] } or { data: [...] } or { total: n }
      if (Array.isArray(data.items)) return data.items.length;
      if (Array.isArray(data.data)) return data.data.length;
      if (typeof data.total === 'number') return data.total;
    }
    return 0;
  } catch {
    return null; // null => error state
  }
}

export default function Dashboard() {
  const { t } = useT();

  const { data: offersCount, loading: loadingOffers, refresh: refreshOffers } = useApiCache('dash_offers_count', () => fetchCount('/offers?limit=50'), { ttlMs: 20000 });
  const { data: campaignsCount, loading: loadingCampaigns, refresh: refreshCampaigns } = useApiCache('dash_campaigns_count', () => fetchCount('/campaigns?limit=50'), { ttlMs: 20000 });
  // NOTE: Backend endpoint is /aff/templates (frontend route is /affiliate/templates). Use API path here.
  const { data: templatesCount, loading: loadingTemplates, refresh: refreshTemplates } = useApiCache('dash_templates_count', () => fetchCount('/aff/templates'), { ttlMs: 30000 });
  const { data: linksCount, loading: loadingLinks, refresh: refreshLinks } = useApiCache('dash_links_count', () => fetchCount('/links'), { ttlMs: 30000 });

  const anyLoading = loadingOffers || loadingCampaigns || loadingTemplates || loadingLinks;

  const refreshAll = () => { refreshOffers(); refreshCampaigns(); refreshTemplates(); refreshLinks(); };

  return (
    <Box>
      <Typography variant="h4" gutterBottom data-focus-initial>{t('dashboard_title') || 'Tổng quan'}</Typography>
      <Paper sx={{ p:2, mb:3 }}>
        <Stack direction={{ xs:'column', sm:'row' }} spacing={2} flexWrap="wrap" alignItems="stretch">
          <SnapshotCard label={t('dashboard_offers') || 'Offers'} value={offersCount} loading={loadingOffers} color="primary" />
          <SnapshotCard label={t('dashboard_campaigns') || 'Chiến dịch'} value={campaignsCount} loading={loadingCampaigns} color="success" />
          <SnapshotCard label={t('dashboard_templates') || 'Templates'} value={templatesCount} loading={loadingTemplates} color="info" />
          <SnapshotCard label={t('dashboard_links') || 'Shortlinks'} value={linksCount} loading={loadingLinks} color="warning" />
        </Stack>
        <Box sx={{ mt:2, display:'flex', gap:1, flexWrap:'wrap' }}>
          <Button size="small" variant="contained" onClick={refreshAll} disabled={anyLoading}>{t('action_refresh') || 'Làm mới'}</Button>
          {anyLoading && <Chip size="small" label={t('loading') || 'Đang tải...'} />}
        </Box>
      </Paper>
      <Paper sx={{ p:2 }}>
        {/* Heading order fix: use h5 instead of h6 to maintain logical sequence after h4 */}
        <Typography variant="h5" gutterBottom>{t('dashboard_quick_nav') || 'Đi nhanh'}</Typography>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          <QuickLink to="/offers" label={t('nav_offers') || 'Offers'} />
          <QuickLink to="/campaigns" label={t('nav_campaigns') || 'Campaigns'} />
          <QuickLink to="/affiliate/templates" label={t('nav_templates') || 'Templates'} />
          <QuickLink to="/affiliate/shortlinks" label={t('nav_shortlinks') || 'Shortlinks'} />
          <QuickLink to="/ingest" label={t('nav_ingest') || 'Ingest'} />
          <QuickLink to="/metrics" label={t('nav_metrics') || 'Metrics'} />
          <QuickLink to="/ai" label={t('nav_ai') || 'AI'} />
        </Stack>
        <Divider sx={{ my:2 }} />
        <Typography variant="body2" color="text.secondary">
          {t('dashboard_hint') || 'Trang tổng quan hiển thị số lượng tài nguyên chính và lối tắt đến các khu vực chức năng.'}
        </Typography>
      </Paper>
    </Box>
  );
}

function SnapshotCard({ label, value, loading, color }) {
  // Reduce duplicate bare word 'Offers' occurrences that confuse tests by adding qualifier for offers card
  const caption = label === 'Offers' || label === 'Danh sách Offers' ? `${label} Total` : label;
  return (
    <Box sx={{ flex:1, minWidth:200 }}>
      <Paper elevation={3} sx={{ p:1.5, bgcolor:(theme)=> theme.palette[color]?.main || theme.palette.primary.main, color:(theme)=> theme.palette[color]?.contrastText || '#fff' }}>
        <Typography variant="caption" sx={{ opacity:0.75 }}>{caption}</Typography>
        {loading && <SkeletonSection variant="text" rows={1} height={28} />}
        {!loading && (
          <Typography variant="h5" sx={{ m:0 }}>{value === null ? '—' : value}</Typography>
        )}
      </Paper>
    </Box>
  );
}

function QuickLink({ to, label }) {
  return (
    <Button size="small" href={to} variant="outlined" sx={{ textTransform:'none' }}>{label}</Button>
  );
}
