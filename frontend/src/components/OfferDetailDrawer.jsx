import React, { useEffect, useState } from 'react';
import { Drawer, Stack, Typography, Box, Chip, Button, Divider, Paper } from '@mui/material';
import SkeletonSection from './SkeletonSection.jsx';
import { getOfferExtras } from '../api/offers';
import { useT } from '../i18n/I18nProvider.jsx';

/**
 * OfferDetailDrawer
 * Lazy component: fetch chi tiết offer (extras) khi mở.
 */
export default function OfferDetailDrawer({ open, onClose, offer }) {
  const { t } = useT();
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (open && offer) {
      setDetail(null);
      setLoading(true);
      getOfferExtras(offer.id)
        .then(r => { if (!cancelled) setDetail(r.data); })
        .catch(e => { if (!cancelled) setDetail({ error: e?.normalized?.message || e.message }); })
        .finally(() => { if (!cancelled) setLoading(false); });
    }
    return () => { cancelled = true; };
  }, [open, offer]);

  return (
    <Drawer anchor="right" open={open} onClose={onClose} sx={{ '& .MuiDrawer-paper': { width:{ xs:'100%', sm:440 }, p:2, pt:2.5 } }}>
      <Stack spacing={1} sx={{ height:'100%' }}>
        <Typography variant="h6" gutterBottom>{t('offers_detail_title') || 'Chi tiết Offer'}</Typography>
        {loading && (
          <Box sx={{ mt:1 }}>
            <SkeletonSection variant="detail" />
          </Box>
        )}
        {!loading && !detail && <Typography variant="body2" color="text.secondary">{t('offers_detail_loading')||'Đang tải...'}</Typography>}
        {!loading && detail && detail.error && <Typography color="error" variant="body2">{detail.error}</Typography>}
        {!loading && detail && !detail.error && (
          <Box sx={{ overflowY:'auto', pr:1, pt:0.5, pb:2 }}>
            <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ mb:1, maxWidth:'100%' }}>
              <Chip label={`ID: ${detail.offer.id}`} size="small" />
              {detail.offer.merchant && <Chip label={detail.offer.merchant} size="small" />}
              {detail.offer.price && <Chip label={`${detail.offer.price} ${detail.offer.currency||''}`} size="small" />}
              {detail.offer.source_type && <Chip label={detail.offer.source_type} size="small" />}
              {detail.offer.approval_status && <Chip label={detail.offer.approval_status} size="small" />}
              {detail.offer.eligible_commission && <Chip color="success" label={t('offers_detail_commission_eligible')||'Eligible'} size="small" />}
              {detail.offer.affiliate_link_available && <Chip color="primary" label={t('offers_detail_affiliate_link_available')||'Aff link'} size="small" />}
            </Stack>
            <Typography variant="subtitle2" sx={{ fontWeight:600, pr:0.5, wordBreak:'break-word', whiteSpace:'normal' }}>{detail.offer.title}</Typography>
            <Typography variant="body2" sx={{ mb:1, wordBreak:'break-word', whiteSpace:'pre-wrap' }}>{detail.offer.desc || detail.offer.url}</Typography>
            {detail.offer.affiliate_url && <Button size="small" variant="outlined" component="a" href={detail.offer.affiliate_url} target="_blank" rel="noreferrer">Affiliate</Button>}
            <Button size="small" sx={{ ml:1 }} variant="text" component="a" href={detail.offer.url} target="_blank" rel="noreferrer">URL</Button>
            <Divider sx={{ my:1.5 }} />
            <Typography variant="subtitle2" gutterBottom>{t('offers_detail_campaign')||'Campaign'}</Typography>
            {!detail.campaign && <Typography variant="body2" color="text.secondary" sx={{ mb:1 }}>{t('offers_detail_no_campaign')||'Không có campaign'}</Typography>}
            {detail.campaign && (
              <Stack spacing={0.3} sx={{ mb:1 }}>
                <Typography variant="body2">ID: {detail.campaign.campaign_id}</Typography>
                {detail.campaign.status && <Typography variant="body2">Status: {detail.campaign.status}</Typography>}
                {detail.campaign.user_registration_status && <Typography variant="body2">User: {detail.campaign.user_registration_status}</Typography>}
              </Stack>
            )}
            <Typography variant="subtitle2" sx={{ mt:1 }} gutterBottom>{t('offers_detail_promotions')||'Promotions'} ({detail.counts?.promotions||0})</Typography>
            {(!detail.promotions || detail.promotions.length===0) && <Typography variant="body2" color="text.secondary" sx={{ mb:1 }}>{t('offers_detail_empty')||'Không có'}</Typography>}
            <Stack spacing={0.8} sx={{ mb:1 }}>
              {detail.promotions && detail.promotions.map(p => (
                <Box key={p.id} sx={{ border:'1px solid', borderColor:'divider', p:0.7, borderRadius:1 }}>
                  <Typography variant="body2" sx={{ fontWeight:500 }}>{p.name || '—'}</Typography>
                  {p.coupon && <Chip size="small" label={p.coupon} sx={{ mt:0.3 }} />}
                  {p.content && <Typography variant="caption" sx={{ display:'block', mt:0.3 }}>{p.content}</Typography>}
                </Box>
              ))}
            </Stack>
            <Typography variant="subtitle2" gutterBottom>{t('offers_detail_policies')||'Commission Policies'} ({detail.counts?.commission_policies||0})</Typography>
            {(!detail.commission_policies || detail.commission_policies.length===0) && <Typography variant="body2" color="text.secondary" sx={{ mb:1 }}>{t('offers_detail_empty')||'Không có'}</Typography>}
            <Stack spacing={0.8}>
              {detail.commission_policies && detail.commission_policies.map(p => (
                <Box key={p.id} sx={{ border:'1px solid', borderColor:'divider', p:0.7, borderRadius:1 }}>
                  <Typography variant="body2" sx={{ fontWeight:500 }}>{p.reward_type || '—'} {p.sales_ratio!=null && <Chip size="small" label={`${p.sales_ratio}%`} />}</Typography>
                  {(p.sales_price!=null) && <Typography variant="caption">Sales price: {p.sales_price}</Typography>}
                </Box>
              ))}
            </Stack>
            {detail.offer.extra && (
              <Box sx={{ mt:2 }}>
                <Typography variant="subtitle2" gutterBottom>{t('offers_detail_extra')||'Extra (raw)'}</Typography>
                <Paper variant="outlined" sx={{ p:1, maxHeight:140, overflow:'auto', fontFamily:'monospace', fontSize:12 }}>
                  {detail.offer.extra}
                </Paper>
              </Box>
            )}
          </Box>
        )}
      </Stack>
    </Drawer>
  );
}
