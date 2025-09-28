import React from 'react';
import { Box, Typography, Button } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import { useT } from '../i18n/I18nProvider.jsx';

// Sử dụng fallback an toàn: nếu t trả về chính key (missing) hoặc falsy -> dùng fallback VN.
function tSafe(t, key, fallback) {
  try {
    const v = t(key);
    if (!v || v === key) return fallback;
    return v;
  } catch {
    return fallback;
  }
}

export default function NotFound() {
  const { t } = useT();
  return (
    <Box sx={{ p:6, textAlign:'center' }}>
      <Typography variant="h3" gutterBottom data-focus-initial>404</Typography>
      <Typography variant="h6" gutterBottom>{tSafe(t,'not_found_title','Không tìm thấy trang')}</Typography>
      <Typography variant="body2" sx={{ mb:3 }}>{tSafe(t,'not_found_desc','Đường dẫn bạn truy cập không tồn tại hoặc đã được di chuyển.')}</Typography>
      <Button variant="contained" component={RouterLink} to="/">{tSafe(t,'not_found_back_home','Về trang chính')}</Button>
    </Box>
  );
}
