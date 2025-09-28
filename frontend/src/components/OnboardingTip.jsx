import React from 'react';
import { Collapse, Paper, IconButton, Typography, Box, Button } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';

const LS_KEY = 'onboarding_v1_dismissed';

export default function OnboardingTip() {
  const [open, setOpen] = React.useState(() => {
    try { return localStorage.getItem(LS_KEY) !== '1'; } catch { return true; }
  });
  const dismiss = () => { setOpen(false); try { localStorage.setItem(LS_KEY,'1'); } catch { /* noop */ } };
  if (!open) return null;
  return (
    <Collapse in={open} unmountOnExit>
      <Paper elevation={3} sx={{ p:2, mb:3, position:'relative', background: theme=>theme.palette.mode==='dark'? '#1e293b':'linear-gradient(135deg,#ffffff,#f1f5f9)' }}>
        <IconButton size="small" onClick={dismiss} sx={{ position:'absolute', top:4, right:4 }} aria-label="Đóng giới thiệu"><CloseIcon fontSize="small" /></IconButton>
        <Typography variant="h6" sx={{ mb:1 }}>Chào mừng đến AI Affiliate Dashboard 👋</Typography>
        <Typography variant="body2" sx={{ mb:1.5 }}>
          Bạn có thể:
        </Typography>
        <Box component="ul" sx={{ m:0, pl:3, fontSize:14, lineHeight:1.5 }}>
          <li>Tạo & quản lý shortlink trong mục Shortlinks</li>
          <li>Convert URL nhanh với tham số tracking tuỳ chỉnh</li>
          <li>Quản lý Templates & auto-generate theo network</li>
          <li>Xem Offers, import/export Excel</li>
          <li>Dùng AI Assistant để gợi ý nội dung / sản phẩm</li>
        </Box>
        <Box sx={{ mt:2, display:'flex', gap:1, flexWrap:'wrap' }}>
          <Button size="small" variant="contained" onClick={dismiss}>Bắt đầu</Button>
          <Button size="small" onClick={dismiss}>Ẩn</Button>
        </Box>
      </Paper>
    </Collapse>
  );
}
