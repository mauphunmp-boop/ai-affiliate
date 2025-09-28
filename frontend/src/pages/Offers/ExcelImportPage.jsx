import React, { useCallback, useState } from 'react';
import { Typography, Paper, Box, Button, Alert, Stack, Chip, Table, TableHead, TableRow, TableCell, TableBody, IconButton, Collapse } from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import { importOffersExcel, downloadExportTemplate } from '../../api/excel.js';

function prettyNumber(n) { return typeof n === 'number' ? n.toLocaleString() : n; }

export default function ExcelImportPage() {
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [showDetails, setShowDetails] = useState(false);
  const [downloadingTemplate, setDownloadingTemplate] = useState(false);

  const onDrop = useCallback((e) => {
    e.preventDefault(); e.stopPropagation();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) setFile(f);
  }, []);

  const onSelect = (e) => {
    const f = e.target.files?.[0];
    if (f) setFile(f);
  };

  const prevent = (e) => { e.preventDefault(); e.stopPropagation(); if (e.type === 'dragenter' || e.type==='dragover') setDragOver(true); if (e.type==='dragleave') setDragOver(false); };

  const reset = () => { setFile(null); setResult(null); setError(''); setShowDetails(false); };

  const doUpload = async () => {
    if (!file) return;
    setLoading(true); setError(''); setResult(null);
    try {
      const res = await importOffersExcel(file);
      setResult(res.data);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Lỗi upload');
    } finally { setLoading(false); }
  };

  const downloadTemplate = async () => {
    setDownloadingTemplate(true); setError('');
    try {
      const res = await downloadExportTemplate();
      const disposition = res.headers['content-disposition'] || '';
      let filename = 'offers_template.xlsx';
      const match = disposition.match(/filename="?([^";]+)"?/i);
      if (match && match[1]) filename = match[1];
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a'); a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove(); setTimeout(()=>URL.revokeObjectURL(url), 2000);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Lỗi tải template');
    } finally { setDownloadingTemplate(false); }
  };

  const summaryChips = result ? [
    { label: 'Products', value: result.imported },
    { label: 'Campaigns', value: result.campaigns },
    { label: 'Commissions', value: result.commissions },
    { label: 'Promotions', value: result.promotions },
  ] : [];

  const hasWarnings = result && (result.skipped_required || (result.errors && result.errors.length));
  const severity = error ? 'error' : (hasWarnings ? 'warning' : 'success');

  return (
    <Paper sx={{ p:2 }}>
      <Typography variant="h5" gutterBottom>Excel Import</Typography>
      <Typography variant="body2" sx={{ mb:2 }}>
        Kéo/thả hoặc chọn file .xlsx định dạng 4 sheet có 2 hàng tiêu đề. Cột bắt buộc Products: merchant, title, price, (url hoặc affiliate_url), source_id (auto nếu trống).
      </Typography>
      <Stack direction="row" spacing={1} sx={{ mb:2, flexWrap:'wrap' }}>
        <Button size="small" variant="outlined" onClick={downloadTemplate} disabled={downloadingTemplate}>{downloadingTemplate?'Đang tải...':'Tải Template'}</Button>
        <Button size="small" variant="text" onClick={reset} startIcon={<RestartAltIcon/>}>Reset</Button>
      </Stack>

      <Box onDrop={onDrop} onDragEnter={prevent} onDragOver={prevent} onDragLeave={prevent}
        sx={{ border:'2px dashed', borderColor: dragOver? 'primary.main':'divider', p:4, textAlign:'center', borderRadius:2, mb:2, backgroundColor: dragOver? 'action.hover':'transparent' }}>
        <Typography variant="subtitle1" gutterBottom>Chọn hoặc thả file Excel (.xlsx)</Typography>
        <Button variant="contained" component="label" startIcon={<UploadFileIcon/>} disabled={loading}>
          Chọn file
          <input type="file" accept=".xlsx" hidden onChange={onSelect} />
        </Button>
        {file && <Typography variant="caption" display="block" sx={{ mt:1 }}>{file.name} ({Math.round(file.size/1024)} KB)</Typography>}
      </Box>

      <Stack direction="row" spacing={2} sx={{ mb:2 }}>
        <Button variant="contained" onClick={doUpload} disabled={!file || loading}>{loading?'Đang import...':'Upload & Import'}</Button>
        {result && <Button variant="outlined" onClick={()=>setShowDetails(s=>!s)} startIcon={showDetails? <ExpandLessIcon/>:<ExpandMoreIcon/>}>{showDetails?'Ẩn chi tiết':'Chi tiết'}</Button>}
      </Stack>

      {error && <Alert severity="error" sx={{ mb:2 }}>{error}</Alert>}
      {result && (
        <Alert severity={severity} sx={{ mb:2 }}>
          Kết quả: {summaryChips.map(c=> <Chip key={c.label} size="small" label={`${c.label}: ${prettyNumber(c.value)}`} sx={{ mr:1 }} />)}
          {result.skipped_required ? <Chip size="small" color="warning" label={`Thiếu bắt buộc: ${result.skipped_required}`} sx={{ mr:1 }} />: null}
          {result.errors && result.errors.length ? <Chip size="small" color="error" label={`Errors: ${result.errors.length}`} />: null}
        </Alert>
      )}

      {result && showDetails && (
        <Collapse in={showDetails}>
          <Box sx={{ mb:3 }}>
            {result.skipped_required ? (
              <Box sx={{ mb:2 }}>
                <Typography variant="subtitle1">Dòng thiếu cột bắt buộc (tối đa 50):</Typography>
                <Table size="small">
                  <TableHead>
                    <TableRow><TableCell>Row</TableCell><TableCell>Thiếu</TableCell></TableRow>
                  </TableHead>
                  <TableBody>
                    {(result.errors||[]).map((er,i)=>(
                      <TableRow key={i}>
                        <TableCell>{er.row}</TableCell>
                        <TableCell>{(er.missing||[]).join(', ')}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Box>
            ): null}
            {result.errors && result.errors.length === 0 && !result.skipped_required && (
              <Typography variant="body2">Không có lỗi chi tiết.</Typography>
            )}
          </Box>
        </Collapse>
      )}
    </Paper>
  );
}
