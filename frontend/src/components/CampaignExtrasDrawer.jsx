import React from 'react';
import { Drawer, Box, Typography, Divider, Stack, CircularProgress, Chip, List, ListItem, ListItemText, Button } from '@mui/material';
import { useT } from '../i18n/I18nProvider.jsx';

/**
 * CampaignExtrasDrawer - hiển thị extras cho campaign.
 * Nhận props: { open, onClose, extras, loading }
 * (Phần fetch giữ nguyên ở parent để không thay đổi logic notify / error xử lý.)
 */
export default function CampaignExtrasDrawer({ open, onClose, extras, loading }) {
  const { t } = useT();
  return (
    <Drawer anchor="right" open={open} onClose={onClose} PaperProps={{ sx:{ width:{ xs:'100%', sm:500 } } }}>
      <Box sx={{ p:2, height:'100%', display:'flex', flexDirection:'column' }}>
        <Typography variant="h6" gutterBottom>{t('campaigns_extras_title')}</Typography>
        <Divider sx={{ mb:2 }} />
        {loading && <Stack alignItems="center" justifyContent="center" sx={{ flex:1 }}><CircularProgress size={32} /></Stack>}
        {!loading && !extras && <Typography variant="body2" color="text.secondary">{t('campaigns_extras_loading')}</Typography>}
        {!loading && extras && extras.error && <Typography color="error" variant="body2">{extras.error}</Typography>}
        {!loading && extras && !extras.error && (
          <Box sx={{ overflowY:'auto', flex:1 }}>
            <Stack spacing={1} sx={{ mb:2 }}>
              <Chip label={`ID: ${extras.campaign_id}`} size="small" />
              {extras.merchant && <Chip label={t('campaigns_extras_merchant') + ': ' + extras.merchant} size="small" />}
              {extras.detail?.status && <Chip label={t('campaigns_extras_status') + ': ' + extras.detail.status} size="small" />}
              {extras.detail?.approval && <Chip label={t('campaigns_extras_approval') + ': ' + extras.detail.approval} size="small" />}
              {extras.detail?.user_registration_status && <Chip label={t('campaigns_extras_user_status') + ': ' + extras.detail.user_registration_status} size="small" />}
              {extras.detail?.cookie_duration && <Chip label={t('campaigns_extras_cookie') + ': ' + extras.detail.cookie_duration} size="small" />}
            </Stack>
            <Typography variant="subtitle2" gutterBottom>{t('campaigns_extras_promotions')} ({extras.counts?.promotions})</Typography>
            {(!extras.promotions || extras.promotions.length===0) && <Typography variant="body2" color="text.secondary" sx={{ mb:1 }}>{t('campaigns_extras_empty')}</Typography>}
            <List dense sx={{ mb:2 }}>
              {Array.isArray(extras.promotions) && extras.promotions.map((p,i)=>(
                <ListItem key={i} disableGutters>
                  <ListItemText
                    primary={p.name || p.coupon || ('#'+(i+1))}
                    secondary={(p.content||'') + (p.coupon?` | ${p.coupon}`:'')}
                  />
                </ListItem>
              ))}
            </List>
            <Typography variant="subtitle2" gutterBottom>{t('campaigns_extras_policies')} ({extras.counts?.commission_policies})</Typography>
            {(!extras.commission_policies || extras.commission_policies.length===0) && <Typography variant="body2" color="text.secondary" sx={{ mb:1 }}>{t('campaigns_extras_empty')}</Typography>}
            <List dense>
              {Array.isArray(extras.commission_policies) && extras.commission_policies.map((c,i)=>(
                <ListItem key={i} disableGutters>
                  <ListItemText
                    primary={`${c.reward_type || ''} ${c.sales_ratio!=null? ('- ' + c.sales_ratio + '%'):''}`}
                    secondary={c.target_month || ''}
                  />
                </ListItem>
              ))}
            </List>
            <Typography variant="subtitle2" sx={{ mt:2 }}>Raw:</Typography>
            <pre style={{ fontSize:11, maxHeight:160, overflow:'auto', background:'#111', color:'#0f0', padding:8 }}>{JSON.stringify(extras, null, 2)}</pre>
          </Box>
        )}
        <Box sx={{ pt:1 }}>
          <Button fullWidth variant="outlined" onClick={onClose}>Đóng</Button>
        </Box>
      </Box>
    </Drawer>
  );
}
