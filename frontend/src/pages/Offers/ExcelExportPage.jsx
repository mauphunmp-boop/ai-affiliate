import React, { useState } from 'react';
import { Typography, Paper, Button, Stack, TextField, Box, Alert, Tooltip } from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import DescriptionIcon from '@mui/icons-material/Description';
import RefreshIcon from '@mui/icons-material/Refresh';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { downloadExportExcel, downloadExportTemplate } from '../../../api/excel';

// Utility để trigger download blob
function triggerDownload(blob, fallbackName) {
  try {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fallbackName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(()=> window.URL.revokeObjectURL(url), 2000);
  } catch (e) {
    console.error('Blob download failed', e);
  }
}

export default function ExcelExportPage() {
  const [merchant, setMerchant] = useState('');
  const [title, setTitle] = useState('');
  const [limit, setLimit] = useState('');
  const [maxTextLen, setMaxTextLen] = useState('');
  const [loadingExport, setLoadingExport] = useState(false);
  const [loadingTemplate, setLoadingTemplate] = useState(false);
  const [lastDownloaded, setLastDownloaded] = useState(null);
  const [error, setError] = useState('');

  const buildParams = () => {
    const p = {};
    if (merchant.trim()) p.merchant = merchant.trim().toLowerCase();
    if (title.trim()) p.title = title.trim();
    if (limit.trim()) {
      const n = parseInt(limit,10); if (!isNaN(n) && n>0) p.limit = n; else setLimit('');
    }
    if (maxTextLen.trim()) {
      const n = parseInt(maxTextLen,10); if (!isNaN(n) && n>0) p.max_text_len = n; else setMaxTextLen('');
    }
    return p;
  };

  const handleExport = async () => {
    setError(''); setLoadingExport(true);
    try {
      const res = await downloadExportExcel(buildParams());
      const disposition = res.headers['content-disposition'] || '';
      let filename = 'offers_export.xlsx';
      const match = disposition.match(/filename="?([^";]+)"?/i);
      if (match && match[1]) filename = match[1];
      triggerDownload(res.data, filename);
      setLastDownloaded(new Date());
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Lỗi tải file');
    } finally { setLoadingExport(false); }
  };

  const handleTemplate = async () => {
    setError(''); setLoadingTemplate(true);
    try {
      const res = await downloadExportTemplate();
      const disposition = res.headers['content-disposition'] || '';
      let filename = 'offers_template.xlsx';
      const match = disposition.match(/filename="?([^";]+)"?/i);
      if (match && match[1]) filename = match[1];
      triggerDownload(res.data, filename);
      setLastDownloaded(new Date());
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Lỗi tải template');
    } finally { setLoadingTemplate(false); }
  };

  const resetFilters = () => {
    setMerchant(''); setTitle(''); setLimit(''); setMaxTextLen('');
  };

  return (
    <Paper sx={{ p:2 }}>
      <Typography variant="h5" gutterBottom>Excel Export</Typography>
      <Typography variant="body2" sx={{ mb:2 }}>
        Xuất file Excel gồm 4 sheet: <strong>Products, Campaigns, Commissions, Promotions</strong>. Products chỉ chứa dữ liệu gốc
        (datafeeds / top_products / manual / excel). Template có 2 hàng tiêu đề (kỹ thuật + tiếng Việt).
      </Typography>
      {error && <Alert severity="error" sx={{ mb:2 }}>{error}</Alert>}
      <Box sx={{ display:'flex', flexWrap:'wrap', gap:2, mb:2 }}>
        <TextField size="small" label="Merchant" value={merchant} onChange={e=>setMerchant(e.target.value)} placeholder="vd: shopee" />
        <TextField size="small" label="Title chứa" value={title} onChange={e=>setTitle(e.target.value)} />
        <TextField size="small" label="Limit" value={limit} onChange={e=>setLimit(e.target.value.replace(/[^0-9]/g,''))} sx={{ width:110 }} helperText="Trống = tất cả" />
        <TextField size="small" label="max_text_len" value={maxTextLen} onChange={e=>setMaxTextLen(e.target.value.replace(/[^0-9]/g,''))} sx={{ width:140 }} helperText="Cắt ngắn text dài" />
        <Stack direction="row" spacing={1}>
          <Tooltip title="Xoá bộ lọc"><Button size="small" onClick={resetFilters} startIcon={<RefreshIcon/>}>Reset</Button></Tooltip>
        </Stack>
      </Box>
      <Stack direction={{ xs:'column', sm:'row' }} spacing={2} sx={{ mb:2 }}>
        <Button variant="contained" startIcon={<DownloadIcon />} disabled={loadingExport} onClick={handleExport}>
          {loadingExport ? 'Đang xuất...' : 'Tải Excel Full'}
        </Button>
        <Button variant="outlined" startIcon={<DescriptionIcon />} disabled={loadingTemplate} onClick={handleTemplate}>
          {loadingTemplate ? 'Đang tải...' : 'Tải Template'}
        </Button>
      </Stack>
      {lastDownloaded && (
        <Alert severity="info" icon={<InfoOutlinedIcon fontSize="inherit"/>}>
          Lần tải gần nhất: {lastDownloaded.toLocaleString()}
        </Alert>
      )}
    </Paper>
  );
}
