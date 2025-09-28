import React from 'react';
import { Paper, Typography, Stack, Button, List, ListItem, ListItemText } from '@mui/material';
import { listApiConfigs } from '../api.js';
import { listAffiliateTemplates } from '../api/affiliate';
import { useT } from '../i18n/I18nProvider.jsx';

/**
 * GettingStartedPanel
 * Hiển thị hướng dẫn nhanh khi thiếu dữ liệu nền tảng:
 *  - Không có API Configs
 *  - Không có Affiliate Templates
 */
export default function GettingStartedPanel({ onDismiss }) {
  const { t } = useT();
  const tSafe = (key, fallback) => {
    try {
      const v = t(key);
      if (!v || v === key) return fallback;
      return v;
    } catch { return fallback; }
  };
  const [state, setState] = React.useState({ loading:true, configs:[], templates:[], error:null });

  const load = async () => {
    setState(s=>({ ...s, loading:true, error:null }));
    try {
      const [cfgRes, tplRes] = await Promise.all([
        listApiConfigs().catch(()=>({ data:[] })),
        listAffiliateTemplates().catch(()=>({ data:[] }))
      ]);
      setState({ loading:false, configs: cfgRes.data||[], templates: tplRes.data||[], error:null });
    } catch (e) {
      setState({ loading:false, configs:[], templates:[], error: e?.message||'Load error' });
    }
  };
  React.useEffect(()=>{ load(); }, []);

  const { loading, configs, templates, error } = state;
  const needConfig = !loading && configs.length === 0;
  const needTemplates = !loading && templates.length === 0;
  if (loading) return null; // tránh nhấp nháy – để parent render skeleton khác nếu muốn
  if (!needConfig && !needTemplates) return null;

  return (
    <Paper sx={{ p:2, mb:2, border:'1px dashed', borderColor:'warning.main', bgcolor: theme=>theme.palette.mode==='dark' ? 'warning.900' : 'warning.50' }}>
      <Stack spacing={1}>
  <Typography data-testid="getting-started-heading" variant="h6" sx={{ display:'flex', alignItems:'center', gap:1 }}>{tSafe('getting_started_title','Bắt đầu nhanh')}</Typography>
        {error && <Typography color="error" variant="body2">{error}</Typography>}
  <Typography variant="body2" color="text.secondary">{tSafe('getting_started_intro','Một vài thiết lập cơ bản giúp hệ thống hoạt động đầy đủ.')}</Typography>
        <List dense>
          {needConfig && (
            <ListItem sx={{ alignItems:'flex-start' }}>
              <ListItemText
                primary={tSafe('getting_started_api_config_title','Tạo cấu hình API')}
                secondary={tSafe('getting_started_api_config_desc','Thêm cấu hình endpoint + API key để gọi dịch vụ AI hoặc proxy.')}
              />
              <Button size="small" variant="outlined" href="/system/api-configs">{tSafe('getting_started_open','Mở')}</Button>
            </ListItem>
          )}
          {needTemplates && (
            <ListItem sx={{ alignItems:'flex-start' }}>
              <ListItemText
                primary={tSafe('getting_started_templates_title','Tạo Affiliate Templates')}
                secondary={tSafe('getting_started_templates_desc','Định nghĩa mẫu chuyển đổi link để công cụ Convert hoạt động tối ưu.')}
              />
              <Button size="small" variant="outlined" href="/affiliate/templates">{tSafe('getting_started_open','Mở')}</Button>
            </ListItem>
          )}
        </List>
        <Stack direction="row" spacing={1}>
          {onDismiss && <Button size="small" onClick={onDismiss}>{tSafe('action_dismiss','Ẩn')}</Button>}
          <Button size="small" onClick={load}>{tSafe('action_retry','Thử lại')}</Button>
        </Stack>
      </Stack>
    </Paper>
  );
}
